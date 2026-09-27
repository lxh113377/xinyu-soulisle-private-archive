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
    print("DEPLOYSYNC-SELFTEST-%s（6 类夹具：正例/DIFF/MISSING/EXTRA/空分母/缺目录）"
          % ("PASS" if not bad else "FAIL: " + "; ".join(bad)))
    return 1 if bad else 0


def main() -> int:
    import re

    if "--selftest" in sys.argv:
        return selftest()

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

    print()
    if fails:
        print("DEPLOY-SYNC-FAIL")
        for f in fails:
            print("  -", f)
        return 1
    print(f"DEPLOY-SYNC-PASS  (src→deploy/xinyu 三类归零：missing=0 diff=0 extra=0(白名单外))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
