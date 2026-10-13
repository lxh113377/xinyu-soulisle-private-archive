# 心屿 · 部署副本同步守卫（src/ → deploy/xinyu/）
#
# 立此脚本的原因（2026-09-23 实证）：修完 `src/js/emotion-engine.js` 的缺陷后，
# `deploy/xinyu/`（公网版）**仍是旧引擎** —— 若直接构建镜像/部署，线上会继续跑带缺陷的版本。
# 更隐蔽的是：第一次手工比对时 PowerShell 函数 `H` 被内置别名 `h`(Get-History) 覆盖，
# 两边哈希都取不到 → `None == None` → **8 个文件全报 SAME**（假通过）。
# 因此本脚本强制：① 哈希必须非空 ② 输入必须先证非空 ③ 三类比对全归零才算 PASS。
#
# 用法：python _test/deploy_sync_check.py     → 0 = DEPLOY-SYNC-PASS，1 = FAIL
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
DST = ROOT / "deploy" / "xinyu"

# 不参与前端同步的内容：Pages Function 源单独部署在 deploy/functions/
EXCLUDE_DIRS = {"functions"}
# 刻意不复制的文件：公网零密钥 stub（src 版含真实 Key，绝不能覆盖过去）。
# 它**不参与内容比对**（两端本就该不同），只走下方「红线复核」。
EXCLUDE_FILES = {"js/demo-config.js"}
WHITELIST_EXTRA = {"js/demo-config.js", "_headers"}   # _headers 是 Pages 专属（jar 不读），只存在于部署副本
KEY_RE = "sk-[A-Za-z0-9]{20,}"
# 缺省两个面都量：工作树面管「此刻会被上传的那份」，提交面管「别人 clone 到的那份」。
FACE = "both"


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(p: Path, base: Path) -> str:
    return p.relative_to(base).as_posix()


FN_SRC = ROOT / "src" / "functions"
FN_DST = ROOT / "deploy" / "functions"


def pair_diff(src_dir: Path, dst_dir: Path):
    """通用逐文件比对：返回 (missing, diff, extra)。空哈希也算 diff（防"两边都取不到⇒相同"）。

    立此函数是因为本脚本从 r23 起**只比 `src/ → deploy/xinyu/`**，而 Pages Function 的副本在
    `deploy/functions/`，被 `EXCLUDE_DIRS = {"functions"}` 明确排除在比对面之外 ⇒
    "两份 chat.js 必须一致"这条红线长期只有人手工 SHA256（r57 就是手工证的）。
    手工证明不留在体系里，下一轮改函数就可能悄悄漂移。
    """
    s = {rel(x, src_dir): x for x in sorted(src_dir.rglob("*")) if x.is_file()}
    d = {rel(x, dst_dir): x for x in sorted(dst_dir.rglob("*")) if x.is_file()}
    missing = sorted(set(s) - set(d))
    extra = sorted(set(d) - set(s))
    diff = []
    for r in sorted(set(s) & set(d)):
        a, b = sha256(s[r]), sha256(d[r])
        if not a or not b or a != b:
            diff.append(r)
    return missing, diff, extra


def functions_sync_check(src_dir: Path = FN_SRC, dst_dir: Path = FN_DST):
    """函数出口副本面：src/functions ⇄ deploy/functions 三类归零，且分母非空。返回 (违规列表, 分母)。"""
    if not src_dir.is_dir() or not dst_dir.is_dir():
        return ["函数副本面不可比：src/functions 或 deploy/functions 目录不存在"
                "（Pages Function 是对外出口，静默消失不等于合规）"], 0
    total = len([x for x in src_dir.rglob("*") if x.is_file()])
    if total == 0:
        return ["函数副本面分母为 0：src/functions 里没有任何文件 ⇒ 比对结论不作数（R247 零输入不判绿）"], 0
    missing, diff, extra = pair_diff(src_dir, dst_dir)
    bad = []
    bad += ["函数副本 MISSING: %s" % r for r in missing]
    bad += ["函数副本 DIFF: %s（两端字节不一致）" % r for r in diff]
    bad += ["函数副本 EXTRA: %s（部署副本里有而权威源没有）" % r for r in extra]
    return bad, total


def git_blob_map(prefix: str):
    """从**对象库**取 HEAD 面的 {相对名: blob 号}。返回 (map, 失败原因)。

    立此函数的一手代价（r172 实测）：本脚本自 r23 起只比磁盘工作树，而
    `git show HEAD:src/data/emotion-lexicon.js` 与 `git show HEAD:deploy/xinyu/data/emotion-lexicon.js`
    在 HEAD 面**内容分叉**（公网副本少 8 个情绪词，由 77e7163 单提交引入）。分叉期间工作树两侧
    被并行会话的在途改动改得**逐字节相等** ⇒ 工作树尺一路判绿（只报出一条 EOL 差异），
    真实交付缺陷只有从写不进去的那一面才看得见。blob 号是内容寻址的，等号即字节等。
    """
    import subprocess
    try:
        out = subprocess.run(
            ["git", "-c", "core.quotepath=false", "ls-tree", "-r", "-z", "HEAD", "--", prefix],
            capture_output=True, cwd=str(ROOT), timeout=30)
    except (OSError, subprocess.TimeoutExpired) as e:
        return {}, "%s 取不到 HEAD 面（%s）" % (prefix, type(e).__name__)
    if out.returncode != 0:
        return {}, "%s 取不到 HEAD 面（git 退出码 %s：%s）" % (
            prefix, out.returncode, out.stderr.decode("utf-8", "replace").strip()[:120])
    mapping = {}
    for rec in out.stdout.split(b"\0"):
        if not rec or b"\t" not in rec:
            continue
        meta, _, pathb = rec.partition(b"\t")
        parts = meta.split()
        if len(parts) < 3 or parts[1] != b"blob":
            continue
        raw = pathb.decode("utf-8", "replace")
        if not raw.startswith(prefix + "/"):
            continue
        mapping[raw[len(prefix) + 1:]] = parts[2].decode("ascii", "replace")
    return mapping, None


def face_problems(src_map, dst_map):
    """提交面三类归零（口径与 pair_diff 一致，只是取数来自对象库）。返回 (missing, diff, extra)。"""
    s = {r: h for r, h in src_map.items()
         if not (set(r.split("/")) & EXCLUDE_DIRS) and r not in EXCLUDE_FILES}
    d = {r: h for r, h in dst_map.items() if r not in EXCLUDE_FILES}
    missing = sorted(set(s) - set(d))
    extra = sorted(set(d) - set(s))
    diff = sorted(r for r in set(s) & set(d) if not s[r] or s[r] != d[r])
    return missing, diff, extra


def head_face_check():
    """HEAD 面 src ⇄ deploy/xinyu 对账。返回 (违规列表, 分母, 不可读原因)。"""
    sm, err1 = git_blob_map("src")
    dm, err2 = git_blob_map("deploy/xinyu")
    if err1 or err2:
        return [], 0, err1 or err2
    total = len([r for r in sm if not (set(r.split("/")) & EXCLUDE_DIRS) and r not in EXCLUDE_FILES])
    if total == 0:
        return ["提交面分母为 0：HEAD 里 src/ 没有任何文件 ⇒ 比对结论不作数（R247 零输入不判绿）"], 0, None
    missing, diff, extra = face_problems(sm, dm)
    bad = ["提交面 MISSING: %s（HEAD 里 src 有、deploy/xinyu 没有）" % r for r in missing]
    bad += ["提交面 DIFF: %s（HEAD 两侧 blob 号不同 = 交付副本与权威源不是同一份字节）" % r for r in diff]
    bad += ["提交面 EXTRA: %s（HEAD 的部署副本里有而权威源没有）" % r for r in extra
            if r not in WHITELIST_EXTRA]
    return bad, total, None


def selftest() -> int:
    """夹具全部走临时目录（参数可注入就是为这个），不碰真实 src/deploy。"""
    import tempfile
    bad = []
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        s, d = root / "srcf", root / "deployf"
        (s / "api").mkdir(parents=True)
        (d / "api").mkdir(parents=True)
        w = lambda p, txt: p.write_bytes(txt.encode("utf-8"))
        w(s / "api" / "chat.js", "A")
        w(d / "api" / "chat.js", "A")
        b0, n0 = functions_sync_check(s, d)
        if b0 or n0 != 1:
            bad.append("正例（两份逐字节相同）被判红：%s" % b0)
        w(d / "api" / "chat.js", "B")
        b1, _ = functions_sync_check(s, d)
        if not any("DIFF" in x for x in b1):
            bad.append("注入内容漂移未被抓到 ⇒ 判据恒绿")
        w(d / "api" / "chat.js", "A")
        (d / "api" / "chat.js").unlink()
        b2, _ = functions_sync_check(s, d)
        if not any("MISSING" in x for x in b2):
            bad.append("删除部署副本未被抓到")
        w(d / "api" / "chat.js", "A")
        w(d / "api" / "ghost.js", "A")
        b3, _ = functions_sync_check(s, d)
        if not any("EXTRA" in x for x in b3):
            bad.append("部署副本多出文件未被抓到")
        (d / "api" / "ghost.js").unlink()
        e1, e2 = root / "empty_s", root / "empty_d"
        e1.mkdir()
        e2.mkdir()
        b4, _ = functions_sync_check(e1, e2)
        if not b4:
            bad.append("空分母（0 个文件）被判通过 ⇒ 违 R247")
        b5, _ = functions_sync_check(root / "nope", e2)
        if not b5:
            bad.append("目录不存在被判通过")

        # —— 提交面（HEAD blob）腿：与上面同源的同一条谓词，取数换成对象库 ——
        # face_problems 返回 (missing, diff, extra) 三桶**原始相对名**，格式化在 head_face_check 里做，
        # 所以这里的反例一律按桶位断言（按字符串找 "DIFF" 会恒不命中 = 又一条假绿腿，r172 首跑即抓到）。
        heads = []
        if any(face_problems({"a.js": "x"}, {"a.js": "x"})):
            heads.append("正例（两侧同一 blob 号）三桶不为空")
        if face_problems({"a.js": "x"}, {"a.js": "y"})[1] != ["a.js"]:
            heads.append("注入 blob 漂移未落进 DIFF 桶 ⇒ 提交面腿恒绿")
        if face_problems({"a.js": "x"}, {})[0] != ["a.js"]:
            heads.append("HEAD 里部署副本缺件未落进 MISSING 桶")
        if face_problems({}, {"ghost.js": "g"})[2] != ["ghost.js"]:
            heads.append("HEAD 里部署副本多件未落进 EXTRA 桶")
        if face_problems({}, {"js/demo-config.js": "g"})[2]:
            heads.append("刻意不比对件（公网零密钥 stub）被当成违规多件")
        if face_problems({"functions/api/chat.js": "x"}, {"functions/api/chat.js": "y"})[1]:
            heads.append("函数副本面（单独部署在 deploy/functions/）被混进前端同步面")
        if not face_problems({"a.js": ""}, {"a.js": ""})[1]:
            heads.append("两侧都是空 blob 号被判相等（空输入不判绿）")
        bad += heads
    real_bad, real_total, real_err = head_face_check()
    if real_err:
        print("DEPLOYSYNC-SELFTEST-UNVERIFIED（真面取不到 HEAD：%s）⇒ 提交面这一半没量过，不判绿" % real_err)
        return 2
    if real_total == 0:
        print("DEPLOYSYNC-SELFTEST-FAIL：真面 HEAD 的 src/ 分母为 0 ⇒ 夹具全绿也不作数")
        return 1
    print("DEPLOYSYNC-SELFTEST-%s（提交面腿 %d 条 + 函数面 6 类夹具 + 真面分母 %d 个文件；红=%d）"
          % ("PASS" if not bad else "FAIL", len(heads) + 8, real_total, len(bad)))
    if bad:
        for x in bad:
            print("  -", x)
    return 1 if bad else 0


def main() -> int:
    import re

    if "--selftest" in sys.argv:
        return selftest()

    global FACE
    if "--face" in sys.argv:
        try:
            FACE = sys.argv[sys.argv.index("--face") + 1]
        except IndexError:
            print("DEPLOY-SYNC-UNVERIFIED：--face 后面没跟值（both|worktree）")
            return 2
    if FACE not in ("worktree", "both"):
        print("DEPLOY-SYNC-FAIL：--face=%s 非法（只认 both|worktree；worktree 是旧行为，刻意不看提交面）" % FACE)
        return 1
    fails = []

    if not SRC.is_dir() or not DST.is_dir():
        print("DEPLOY-SYNC-FAIL: src/ 或 deploy/xinyu/ 不存在")
        return 1

    src_files = [
        p for p in SRC.rglob("*")
        if p.is_file()
        and not (set(p.relative_to(SRC).parts) & EXCLUDE_DIRS)
        and rel(p, SRC) not in EXCLUDE_FILES
    ]
    # 输入非空性断言（R247：结论为「0 命中/通过」前必须先证输入非空）
    if len(src_files) < 5:
        fails.append(f"输入可疑：src/ 只扫到 {len(src_files)} 个文件，比对结论不可信")
    print(f"扫描 src/ = {len(src_files)} 个文件")

    src_rel = {rel(p, SRC) for p in src_files}
    dst_rel = {rel(p, DST) for p in DST.rglob("*") if p.is_file()} - EXCLUDE_FILES

    missing = sorted(src_rel - dst_rel)
    extra = sorted(dst_rel - src_rel)
    diff = []
    for p in src_files:
        r = rel(p, SRC)
        q = DST / r
        if q.is_file():
            a, b = sha256(p), sha256(q)
            if not a or not b:
                fails.append(f"哈希为空（比对不可信）: {r}")
            elif a != b:
                diff.append(r)

    for r in missing:
        print(f"  MISSING  {r}")
    for r in diff:
        print(f"  DIFF     {r}")
    unexpected_extra = [r for r in extra if r not in WHITELIST_EXTRA]
    for r in unexpected_extra:
        print(f"  EXTRA    {r}")
    for r in extra:
        if r in WHITELIST_EXTRA:
            print(f"  EXTRA(白名单，符合预期)  {r}")

    if missing:
        fails.append(f"MISSING {len(missing)} 项")
    if diff:
        fails.append(f"DIFF {len(diff)} 项")
    if unexpected_extra:
        fails.append(f"EXTRA {len(unexpected_extra)} 项")

    # 红线复核：公网 stub 必须存在且**零密钥**。
    # 「两份必须不同」只在 src 版真的含 Key 时才是红线 —— r28 CI 实测：全新 clone 里没有 src 版
    # （被 gitignore），CI 会先把公网 stub 复制成 src 版 ⇒ 两份必然相同 ⇒ 被误判红。
    # 那是判据把"本机状态"当成了"普适不变量"；真不变量是"公网副本永不带密钥"。
    for r in WHITELIST_EXTRA:
        stub = DST / r
        origin = SRC / r
        if not stub.is_file():
            fails.append(f"缺少公网零密钥 stub: {r}")
            continue
        text = stub.read_text(encoding="utf-8", errors="replace")
        src_txt = origin.read_text(encoding="utf-8", errors="replace") if origin.is_file() else ""
        stub_key = bool(re.search(KEY_RE, text))
        src_key = bool(re.search(KEY_RE, src_txt))
        same = origin.is_file() and sha256(stub) == sha256(origin)
        if stub_key:
            fails.append(f"红线：公网 stub 含真实 Key -> {r}")
        if src_key and same:
            fails.append(f"红线：src 含 Key 却与公网副本相同（会把密钥推上公网）-> {r}")
        print(f"  红线复核 {r}: 公网零密钥={not stub_key} src含Key={src_key} 两份相同={same}"
              + ("（CI 等效：src 版由 stub 代填，相同属预期）" if same and not src_key else ""))

    fn_bad, fn_total = functions_sync_check()
    for x in fn_bad:
        print("  " + x)
    if not fn_bad:
        print(f"  函数出口面：src/functions ⇄ deploy/functions 逐文件 SHA256 全等（分母 {fn_total} 个）")
    fails.extend(fn_bad)

    # r172：交付副本必须**两个面都对**——工作树面＝此刻 `wrangler/tcb` 会上传的那份，
    # 提交面＝另一个人 clone 出来 / CI checkout 出来的那份。只量前者会漏掉
    # 「分叉已经入库、但被在途改动临时盖住」这一态（r172 一手：HEAD 面公网词表少 8 词，工作树尺一路绿）。
    unverified = []
    if FACE in ("worktree", "both"):
        print(f"工作树面：src ⇄ deploy/xinyu 逐文件 SHA256（分母 {len(src_files)} 个）")
    if FACE == "both":
        h_bad, h_total, h_err = head_face_check()
        if h_err:
            unverified.append(f"HEAD 面不可读：{h_err}（提交面这一半未验，不判绿）")
            print("  提交面 UNVERIFIED: " + h_err)
        else:
            print(f"提交面（HEAD 对象库）：src ⇄ deploy/xinyu 逐 blob 号（分母 {h_total} 个）")
            for x in h_bad:
                print("  " + x)
            fails.extend(h_bad)

    print()
    if fails:
        print("DEPLOY-SYNC-FAIL")
        for f in fails:
            print("  -", f)
        return 1
    if unverified:
        print("DEPLOY-SYNC-UNVERIFIED")
        for f in unverified:
            print("  -", f)
        return 2
    print(f"DEPLOY-SYNC-PASS  (src→deploy/xinyu 三类归零：missing=0 diff=0 extra=0(白名单外)，面={FACE})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
