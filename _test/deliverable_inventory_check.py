#!/usr/bin/env python3
r"""交付物清单面常驻判据（r59）：提交包「清单声明 ⇄ 磁盘实况 ⇄ 口径」三方对账。

为什么立这条（一手证据，不是假想需求）
------------------------------------------------
2026-09-28 00:19 实测：`交付物/提交包/` 下 **7 个被 git 跟踪的交付件从工作树消失**
（含唯一的参赛演示视频成片、`render-pdf.ps1`、`提交清单与验收状态.md` 本体），
而 91 套件电池里 **没有任何一条判据引用过这三个名字**（取证见下方「取数面」节），
所以这轮丢失是**零告警**的 —— 距 iCAN 提交硬截止 2026-09-30 剩 2 天。

peers 的同类面是有主的：发布物有 Release 资产 + digest（本仓 r49 探针实测 17 仓里
tier-A 普遍带 assets 数），而 `make distcheck` 一系的做法就是「声明的产物集合 ⇄ 实际
构建产物」对账。本仓此前只有 `plan_pdf_coverage_check`（九项覆盖）与 `pdf_leak_scan`
（文本层泄露）两条**读 PDF** 的判据 ⇒ PDF 一旦消失它们会红，但**清单自己消失**、
**成片消失**、**渲染脚本消失** 三件事无人守。

取数面（四处，缺一即本判据自证不成立）
------------------------------------------------
1. 路径分母 = 从 `提交清单与验收状态.md` 的表格行里**现读** `交付物/...` 前缀 token
   （不手抄清单；字符集 `[^\s` + 反引号 + 竖线 + 半/全角右括号 + 中文句读]，
   排除尾随标点，`--selftest` 的⑦类夹具专门钉「路径后紧跟中文句号不得吞进 token」）。
2. 官方硬约束 = 同一行的「官方硬约束」列现读：`≤N页` → 页数上限、`≤N分钟` → 时长上限。
3. 成片指纹 = 行内 `sha256=<64hex>` 若在册即与实测比对（登记值不是装饰）。
4. **入库面（r82 补，第二次复发才补上的一条腿）** = `git ls-tree -r -l HEAD -- 交付物` 现读
   (路径, blob 字节)，逐条对磁盘在位性。前 3 条分母都来自「清单声明」⇒ **没写进清单的件消失了永远不红**；
   第 4 条把分母换成被检对象**写不进去**的量（HEAD 树），才盖住「5 件未声明的入库件静默消失」那一半。

三态（沿用本仓 GREEN/RED/UNVERIFIED 口径，禁止把未验并入通过）
------------------------------------------------
- rc=0 `...-PASS`：声明面全部在位非空 + 类型断言全过 + 口径零分叉 + 入库件全在位
- rc=1 `...-FAIL`：任一条**违规**（缺失/空文件/页数越界/时长越界/指纹不符/在册件品牌分叉/**入库件从工作树消失**）
- rc=2 `...-UNVERIFIED`：分母为 0、清单不可读、依赖库缺失 ⇒ 只报未验，**绝不判绿**

一条设计取舍（有意为之，写下来免得下轮当成漏洞"修掉"）
------------------------------------------------
未登记进清单的交付物形状文件（例：09-26 落盘的 `心屿MindIsle_参赛方案.pptx`）
默认只**计数并印在门面行**，不判红；**当且仅当它已被 git 跟踪**才升为红。
理由：未跟踪的本机草稿可能正被另一个会话在途编辑，判红等于让别人的半成品锁住整仓；
而一旦有人 `git add` 它，它就进入提交面，品牌分叉必须当场拦（实测该 pptx 文本层
`MindIsle` 12 处，而权威源 `src/index.html` 与 PDF 文本层都是 `SoulIsle` ⇒ 分叉真实存在）。
"""
from __future__ import annotations

import hashlib
import re
import struct
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG_DIR = ROOT / "交付物" / "提交包"
CHECKLIST = PKG_DIR / "提交清单与验收状态.md"
BRAND_AUTHORITY = ROOT / "src" / "index.html"

# ④ 腿的受检面 = 交付面 + 它的归档落面（r90 一处两用）。
# 这条常量同时决定「分母取哪些前缀」和「搬卷的落点允许落在哪」，因为二者必须是同一个集合：
# 若允许搬到面外，55 MB 打包件搬出后就不再被 ④ 腿守着（搬 = 换个没人看的地方放着），
# 而若分母含某面却不认搬到那儿，归档动作会被判成丢失 —— 07 在册的 🟠 R89-01 卡点正是这个。
ARCHIVE_ROOTS = ("交付物", "archive/交付物-历史轮次")
# r93 修（本轮一手）：字符类原本漏了 `A`（新增）与 `B`（broken pairing）。后果不是「解析不出来」，
# 而是「**新增件一进暂存面，整条搬卷判定当场作废**」——`staged_renames()` 返回未验，
# pre-commit 于是把同一提交里所有合法 R100 搬卷判成「入库件从工作树消失」（2026-10-02 实测拦下 r93 提交）。
# 触发条件很普通：任何一次「归档 + 同时新增文件」的提交都会踩到，也就是体量治理的常规动作。
# 与 r70「`rag` 裸子串」同族：尺的匹配面比它自称的窄 ⇒ 结论偏得比看上去更严重。
RENAME_STATUS_RE = re.compile(r"^[ABCMDTUXR]\d*$")
ASSERT_COUNT = [0]  # selftest 实跑断言数（门面行据此打印，禁把条数硬写进文案 —— 抄一次就漂一次）

# 交付物形状：只有这些后缀才算「要交出去的东西」，脚本/图片/中间件不参与未登记判定
ARTIFACT_EXTS = {".pdf", ".mp4", ".pptx", ".docx", ".zip", ".mov", ".key"}
# 尾随标点必须在字符集里排除，否则 token 会被拉长成不存在的路径（假红）
PATH_RE = re.compile(r"交付物/[^\s`|)（），。;、]*")
BRAND_RE = re.compile(r"心屿[\s]*([A-Za-z][A-Za-z0-9]*)")
SHA_RE = re.compile(r"sha256[^0-9a-f]{0,3}([0-9a-f]{64})")
PAGES_RE = re.compile(r"[≤<]=?\s*(\d+)\s*页")
MINUTES_RE = re.compile(r"[≤<]=?\s*(\d+)\s*分钟")


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def table_rows(md_text: str) -> list:
    """清单表格行 → [cells]。分母单位 = 行（不是字符、不是 grep 命中数）。"""
    rows = []
    for line in md_text.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) < 4:
            continue
        if cells[0] == "#" or not cells[0] or set(cells[0]) <= set("-: "):
            continue
        rows.append(cells)
    return rows


def declared_paths(rows: list) -> list:
    """从声明面取路径 token，保持出现序（首现去重）。"""
    out, seen = [], set()
    for cells in rows:
        for line in cells:
            for tok in PATH_RE.findall(line):
                if tok not in seen:
                    seen.add(tok)
                    out.append(tok)
    return out


def row_constraints(row: list) -> dict:
    """该行「官方硬约束」列现读上限值；读不到就不虚构。"""
    text = " ".join(row)
    c = {}
    m = PAGES_RE.search(text)
    if m:
        c["max_pages"] = int(m.group(1))
    m = MINUTES_RE.search(text)
    if m:
        c["max_seconds"] = int(m.group(1)) * 60
    m = SHA_RE.search(text)
    if m:
        c["sha256"] = m.group(1)
    return c


def mp4_seconds(path: Path):
    """零依赖读 MP4 `moov>mvhd` 取时长（ffprobe 不在 PATH 也能判，实测与登记值同尺）。

    立此函数而非 `subprocess(ffprobe)`：常驻判据不得依赖未登记的二进制 —— 09-28 本机
    `shutil.which("ffprobe")` = None，而清单验收列写的是 ffprobe 读数 ⇒ 按 ffprobe 写判据
    等于给成片时长发一张永久的 UNVERIFIED。

    ⚠️ 首版只扫文件头 1 MB，真面当场判红不了自己：成片 `moov` 实测落在 **22,888,322 / 22,954,501 B**
    （非 faststart，盒子在**尾部**）⇒ 只看头会取不到 mvhd 而退成未验。现按「头 1 MB → 尾 1 MB」
    两段取，且都 seek 不整读（22 MB 不该为量一个时长进内存）。
    """
    import struct
    size = path.stat().st_size
    chunks = []
    with path.open("rb") as f:
        chunks.append(f.read(1 << 20))
        if size > (1 << 20):
            f.seek(max(size - (1 << 20), 1 << 20))
            chunks.append(f.read(1 << 20))
    for data in chunks:
        i = data.find(b"mvhd")
        if i < 0:
            continue
        ver = data[i + 4]
        p = i + 8
        try:
            if ver == 1:
                p += 16
                ts, dur = struct.unpack(">IQ", data[p:p + 12])
            else:
                p += 8
                ts, dur = struct.unpack(">II", data[p:p + 8])
        except struct.error:
            return None
        if ts:
            return dur / ts
    return None


def text_layer(path: Path):
    """交付物文本层抽取（品牌口径判据的被审对象）。无文本层形状返回 None = 不参与该判据。"""
    suf = path.suffix.lower()
    try:
        if suf == ".pdf":
            from pypdf import PdfReader
            rd = PdfReader(str(path))
            return "".join((pg.extract_text() or "") for pg in rd.pages), len(rd.pages)
        if suf == ".pptx":
            import zipfile
            z = zipfile.ZipFile(path)
            xml = "".join(z.read(n).decode("utf-8", "replace")
                          for n in sorted(z.namelist()) if n.startswith("ppt/slides/slide"))
            return " ".join(re.findall(r"<a:t>([^<]*)</a:t>", xml)), None
        if suf == ".docx":
            import zipfile
            z = zipfile.ZipFile(path)
            xml = z.read("word/document.xml").decode("utf-8", "replace")
            return " ".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", xml)), None
        if suf in {".md", ".txt"}:
            return path.read_text(encoding="utf-8", errors="replace"), None
        if suf == ".html":
            # 品牌串在 index.html 里是 `心屿<span class="brand-sub">SoulIsle</span>` ——
            # 不剥标签就取不到，权威源取不到 ⇒ 整条口径判据退成未验（首版真面即栽在这）。
            html = path.read_text(encoding="utf-8", errors="replace")
            return re.sub(r"<[^>]+>", " ", html), None
    except Exception as exc:  # 抽取失败必须可见，不得静默当「没有分叉」
        return "!" + type(exc).__name__ + ":" + str(exc)[:120], None
    return None, None


def tracked_by_git(rel: str) -> bool:
    """未跟踪草稿不判红的依据；git 不可用时返回 None = 该项 UNVERIFIED。"""
    try:
        r = subprocess.run(["git", "ls-files", "--error-unmatch", "--", rel],
                           cwd=str(ROOT), capture_output=True, text=True, timeout=20)
    except Exception:
        return None
    if r.returncode == 0:
        return True
    if r.returncode == 1:
        return False
    return None


def parse_ls_tree(out: str):
    """`git ls-tree -r -l -z` 原文 → ([(rel, blob_size)], skipped)。

    实测字段序（2026-09-29 `od -c` 逐字节取，**不是**「sha\\tsize\\tpath」）：
    `100644 blob <40hex>` + 空格填充 + `<size>` + `\\t` + `<path>` + `\\0`
    ⇒ 整条只有 **一个 TAB**（紧贴 path 前），sha 与 size 之间是空格。
    ⚠️ 首版解析按「两个 TAB」写，夹具照同一个假设造 ⇒ `--selftest` 全绿而真面 89 条全判形状不符。
    教训：**夹具的输入必须来自被测数据面的逐字节取数**，不能由解析器的假设反推，否则两边同错、什么都测不出。
    非 blob 条目（tree/commit 的 size 位是 `-`）与残行计入 skipped 交调用方判未验 ——
    静默丢弃等于把「没解析出来」写成「没有这个件」。
    """
    entries, skipped = [], 0
    for rec in out.split("\0"):
        if not rec:
            continue
        head, sep, path = rec.partition("\t")
        if not sep or not path:
            skipped += 1
            continue
        bits = head.rsplit(None, 1)
        if len(bits) != 2:
            skipped += 1
            continue
        try:
            size = int(bits[1])
        except ValueError:
            skipped += 1
            continue
        entries.append((path, size))
    return entries, skipped


def committed_blobs(prefix: str = "交付物", root=None):
    """HEAD 树里 prefix 下的 ([(rel, blob_size)], skipped)；git 不可用/取不到 ⇒ (**None**, 0)。

    分母为什么取 HEAD 树而不是磁盘目录：本腿判的就是「磁盘比提交面少」，
    用磁盘当分母会让被检对象自己写分母（漏检的那件同时消失于分子与分母 ⇒ 永绿）。
    `-z` + `-c core.quotepath=false`：CJK 路径默认会被转成八进制转义串，那条串拿去 `is_file()` 必假 ⇒ 假红。
    ⚠️ `-l` 与 `--name-only` **互斥**（实测 `error: options '--name-only' and '-l' cannot be used together`）；
    首版就是这么写的，真面退成 UNVERIFIED 才暴露 —— 这也是本腿「未验不判绿」第一次生效的实证。
    """
    root = Path(root) if root else ROOT
    try:
        r = subprocess.run(
            ["git", "-c", "core.quotepath=false", "ls-tree", "-r", "-l", "-z", "HEAD", "--", prefix],
            cwd=str(root), capture_output=True, timeout=30)
    except Exception:
        return None, 0
    if r.returncode != 0:
        return None, 0
    return parse_ls_tree(r.stdout.decode("utf-8", "replace"))


def committed_faces(root=None):
    """ARCHIVE_ROOTS 全部前缀的入库条目并集 → ([(rel, size)], skipped, per_root_counts)。

    「某根一条都没有」只可能是**还没往里搬**，不是「取数失效」⇒ 记计数不判未验；
    只有**并集为空**才是分母为 0（那才是 R247 要拦的形态）。把零判据压在单根上会造出一条
    「归档前必红」的闸 —— 正常流程走不通的判据没资格当闸（[[ratchet-floors-need-headroom]]）。
    """
    entries, skipped, per_root = [], 0, {}
    for pfx in ARCHIVE_ROOTS:
        got, skip = committed_blobs(pfx, root=root)
        if got is None:
            return None, 0, per_root
        entries.extend(got)
        skipped += skip
        per_root[pfx] = len(got)
    return entries, skipped, per_root


def parse_name_status_z(raw: bytes):
    """`git diff -M --name-status -z` 原文 → ({old:(new,score)}, unparsed)。

    字段序取于 2026-10-02 本轮 `od` 级实测（**不是**按解析器假设构造）：
    `R100\\0<old>\\0<new>\\0` —— 与无 `-z` 形态的 `R100\\t<old>\\t<new>` 不同，状态与路径之间是 NUL。
    非 R 记录按 `M\\0<path>\\0` 两步走；形状对不上的记录计入 unparsed 交调用方判未验，
    静默丢 = 把「没解析出来」写成「没有这次搬卷」，就会把在途的搬卷误判成丢失。
    """
    toks = [t for t in raw.decode("utf-8", "replace").split("\0") if t != ""]
    moves, i, unparsed = {}, 0, 0
    while i < len(toks):
        st = toks[i]
        if not RENAME_STATUS_RE.match(st):
            unparsed += 1
            break
        if st[0] != "R":
            # r93 修（本轮一手）：非 R 记录（`M`/`A`/`D`…）是**正常记录**，按「状态+路径」两步走。
            # 原实现在这里直接 `unparsed+=1; break`，于是「搬卷 + 任何其他文件同提交」时
            # 解析器在第一个 `M` 上就停 ⇒ staged_renames 返回未验 ⇒ pre-commit 把
            # 45 条合法 R100 搬卷全部判成「入库件从工作树消失」（实测 2026-10-02 r93 提交被拦）。
            # 下方 `else: i += 2` 那一支此前是**死代码**（永远到不了），与本仓 `--slice` 开关
            # 那次「配了但没生效」同族。真正该记 unparsed 的是「形状真的对不上」的记录
            # （首字段不是状态、或状态后面缺路径），不是「这条不是搬卷」。
            if i + 1 >= len(toks):
                unparsed += 1
                break
            i += 2
            continue
        if st[0] == "R":
            if i + 2 >= len(toks):
                unparsed += 1
                break
            try:
                score = int(st[1:])
            except ValueError:
                score = -1
            moves[toks[i + 1]] = (toks[i + 2], score)
            i += 3
        else:
            i += 2
    return moves, unparsed


def staged_renames(root=None):
    """HEAD ⇄ 暂存面的搬卷映射 {old_rel: (new_rel, score)}；git 不可用/解析失效 ⇒ (**None**, 原因)。

    为什么取**暂存面**而不是工作树：本判据的调用点是 pre-commit，那一刻 `git mv` 已入索引，
    HEAD⇄索引 正是「这次提交到底搬了什么」的权威视图；工作树里的未暂存 mv 不享有搬卷认定 ——
    没被声明过的搬迁不该由判据替它背书。
    """
    root = Path(root) if root else ROOT
    try:
        r = subprocess.run(
            ["git", "-c", "core.quotepath=false", "diff", "--cached", "-M",
             "--name-status", "-z", "HEAD"],
            cwd=str(root), capture_output=True, timeout=30)
    except Exception as exc:
        return None, "git diff 不可调用（%s）" % type(exc).__name__
    if r.returncode != 0:
        return None, "git diff rc=%d" % r.returncode
    moves, unparsed = parse_name_status_z(r.stdout)
    if unparsed:
        return None, "搬卷记录有 %d 条解析不出形状 ⇒ 不替任何搬迁背书" % unparsed
    return moves, "%d 条搬卷在册" % len(moves)


def parse_crosscheck():
    """⑫ 独立取数通道对账：同一 HEAD 用**另一条命令**再数一遍条目数（分母 = ARCHIVE_ROOTS 并集）。

    为什么需要这条腿（本轮一手）：解析器与它的夹具当时按同一个错误假设写 ⇒ `--selftest` 全绿、
    真面 89/89 判废。夹具自证不了自己，只有**换一条命令**才可能暴露字段序假设错。
    返回 (True=两通道相等 / False=不等 / None=未验, 说明)。
    """
    indep = []
    for pfx in ARCHIVE_ROOTS:
        try:
            r = subprocess.run(
                ["git", "-c", "core.quotepath=false", "ls-tree", "-r", "--name-only", "-z",
                 "HEAD", "--", pfx],
                cwd=str(ROOT), capture_output=True, timeout=30)
        except Exception as exc:
            return None, "独立通道不可调用（%s）" % type(exc).__name__
        if r.returncode != 0:
            return None, "独立通道 rc=%d（前缀 %s）" % (r.returncode, pfx)
        indep.extend(x for x in r.stdout.decode("utf-8", "replace").split("\0") if x)
    got, skipped, _per_root = committed_faces()
    if got is None:
        return None, "-l 通道不可用"
    if skipped:
        return False, "-l 通道丢条 %d" % skipped
    if len(got) != len(indep):
        return False, "-l 解析 %d 条 ≠ name-only %d 条" % (len(got), len(indep))
    return True, "%d 条两通道一致" % len(indep)


def tracked_missing_check(entries, root=None, moves=None):
    """入库交付件 ⇄ 工作树 对账。返回 (violations, unverified, n_checked, moved)。

    `moves` = `staged_renames()` 的结果；**只有** 逐字节等价（score==100）且落点仍在 ARCHIVE_ROOTS
    某一根内、且该落点在磁盘上真实存在的记录才算「搬」，其余一律照旧判红。三条牙各挡一种滥用：
    score<100 挡「改过内容再搬」（那是内容变更，须人看）；落点须在面内挡「搬到没人守的地方」；
    磁盘须在位挡「索引里写了新路径但文件其实没落地」。`moves=None`（git 取不到）⇒ 不替任何搬迁
    背书，完全回落 r82 的旧行为 —— 宁可把一次真归档判红让人复核，也不给「查不到」发通行证。

    立此腿的一手证据（第二次复发）：2026-09-29 17:4x 实测 `git status --porcelain` 打出
    **7 条 ` D`**（含 22,954,501 B 的参赛成片 `demo_video_out/心屿SoulIsle-演示视频.mp4`、
    `render-pdf.ps1`、`演示视频脚本.md`、`演示视频-录制执行清单.md`、`application-plan.html`、
    `demo_video_out/subtitle.ass`、`timeline.json`），距 iCAN 硬截止 2026-09-30 剩 1 天，
    而本判据当时只报出其中 **2 条**（`render-pdf.ps1`、成片）—— 因为只有清单声明过的那 2 条
    才进分子。**5 条「没写进清单但已入库」的件是零告警的** —— 这正是 r59 立此判据时要治的形态，
    当时只治了「声明面」那一半，漏了「提交面」。
    """
    root = Path(root) if root else ROOT
    if entries is None:
        return [], ["归档面 HEAD 树取不到 ⇒ 入库件在位性未验（不得读成「都在」）"], 0, []
    if not entries:
        return [], ["HEAD 树在 ARCHIVE_ROOTS 上零条目 ⇒ 分母为 0，本腿不判绿（R247）"], 0, []
    bad, moved = [], []
    n = 0
    for rel, size in entries:
        if not any(rel.startswith(p + "/") for p in ARCHIVE_ROOTS):
            continue
        n += 1
        p = root / rel
        if p.is_file():
            if size > 0 and p.stat().st_size == 0:
                bad.append("入库件被清成 0 B: %s（HEAD blob %d B，磁盘 0 B）" % (rel, size))
            continue
        mv = (moves or {}).get(rel)
        if mv:
            new_rel, score = mv
            in_face = any(new_rel.startswith(q + "/") for q in ARCHIVE_ROOTS)
            if score == 100 and in_face and (root / new_rel).is_file():
                moved.append("%s → %s" % (rel, new_rel))
                continue
            why = ("内容不等（score=%s）" % score) if score != 100 else (
                "落点在受检面外" if not in_face else "新落点不在磁盘上")
            bad.append("入库件消失（有搬卷记录但不认）: %s ⇒ %s" % (rel, why))
            continue
        bad.append("入库件从工作树消失: %s（HEAD blob %d B 在，磁盘没有 ⇒ 无人声明也丢）"
                   % (rel, size))
    return bad, [], n, moved


def evaluate(rows, paths, root=None, tracked=None):
    """纯判定：输入清单行与声明路径，返回 (violations, unverified, notes, counters)。

    `root` / `tracked` 可注入是为了让 `--selftest` 能端到端跑「文件消失 / 空件 / 页数越界 /
    时长越界 / 指纹漂移 / 品牌分叉 / 未登记草稿」七形 —— 真实交付件不许被测试改写，
    而只测纯函数的话，「接线」（路径解析、git 跟踪态、文本层抽取）就又没人验过了（R238）。
    """
    root = root or ROOT
    pkg = root / "交付物" / "提交包"
    brand_file = root / "src" / "index.html"
    tracked = tracked or tracked_by_git
    bad, unver, notes = [], [], []
    counters = {"declared": 0, "checked": 0, "undeclared": 0, "brand_checked": 0}

    if not rows:
        return bad, ["清单表格零行 ⇒ 分母为 0，比对结论不作数（R247 零输入不判绿）"], notes, counters
    if not paths:
        return bad, ["声明面零路径 ⇒ 要么清单不再引用交付物路径，要么取数字符集失效；两种都不该判绿"], notes, counters

    counters["declared"] = len(paths)
    for rel in paths:
        p = root / rel
        if p.is_dir():
            # r85 一手代价：清单里的**目录指针**曾被当成「声明要交的文件」判假缺失
            # （红因写成"磁盘没有"，实际是取数面把指针形态当文件形态 —— 同族第四例的一部分）。
            # 处置：在位目录 ⇒ 记 note 跳过（"它是目录"是**取到的事实**，不是没取到数，
            # 写成未验会让清单里出现一个目录路径就把整条判据压成 rc=2）；**不存在的路径仍照旧判红**，
            # 指针指丢了也不许静默（清单引用了不存在的位置本身就是信息丢失）。
            notes.append("声明 token 是目录指针，按指针跳过（不计缺失也不算未验）: %s" % rel)
            continue
        counters["checked"] += 1
        if not p.is_file():
            bad.append("声明缺失: %s（清单写了要交，磁盘没有）" % rel)
            continue
        if p.stat().st_size == 0:
            bad.append("声明件为空文件: %s（存在但 0 B，等同没有）" % rel)
            continue

    # 类型断言：只跑在真的存在的件上（先证输入非空）
    for rel in paths:
        p = root / rel
        if not p.is_file() or p.stat().st_size == 0:
            continue
        row = next((r for r in rows if any(rel in c for c in r)), [])
        cons = row_constraints(row)
        suf = p.suffix.lower()
        if suf == ".pdf":
            txt, pages = text_layer(p)
            if txt is not None and txt.startswith("!"):
                unver.append("PDF 文本层不可读（%s）: %s" % (txt[1:], rel))
            elif pages is None:
                unver.append("pypdf 不可用 ⇒ 页数未验: %s" % rel)
            else:
                lim = cons.get("max_pages")
                if lim is None:
                    unver.append("清单该行未写页数上限 ⇒ 页数约束未验: %s（实测 %d 页）" % (rel, pages))
                elif pages > lim:
                    bad.append("PDF 页数越界: %s 实测 %d 页 > 官方上限 %d 页" % (rel, pages, lim))
                else:
                    notes.append("PDF %d/%d 页内" % (pages, lim))
        elif suf in {".mp4", ".mov"}:
            sec = mp4_seconds(p)
            lim = cons.get("max_seconds")
            if sec is None:
                unver.append("容器无 mvhd 盒 ⇒ 时长未验: %s" % rel)
            else:
                if lim is not None and sec > lim:
                    bad.append("成片时长越界: %s 实测 %.2fs > 上限 %ds" % (rel, sec, lim))
                elif sec < 30:
                    bad.append("成片时长可疑: %s 实测 %.2fs（<30s 不可能是完整路演片）" % (rel, sec))
                else:
                    notes.append("成片 %.2fs（上限 %s）" % (sec, ("%ds" % lim) if lim else "未登记"))
            want = cons.get("sha256")
            if want:
                got = sha256_of(p)
                if got != want:
                    bad.append("成片指纹漂移: %s 实测 sha256=%s ≠ 清单登记 %s（代际可追性断了）"
                               % (rel, got[:12], want[:12]))
                else:
                    notes.append("成片 sha256==清单登记值")

    # 品牌口径：权威源 = src/index.html 的品牌位；只对**在册**件判红，未登记件看是否被 git 跟踪
    auth = None
    if brand_file.is_file():
        a, _ = text_layer(brand_file)
        m = BRAND_RE.search(a or "")
        auth = m.group(1) if m else None
    if not auth:
        unver.append("品牌权威源未取到串（src/index.html 缺「心屿+拉丁名」）⇒ 口径判据 UNVERIFIED")

    # 未登记交付物扫描**不挂在品牌分支里**：否则权威源一缺，这一面就静默变 0 = 把盲区当零
    # （[[blindness-is-not-zero]] 同族）。
    undeclared = []
    for p in sorted(pkg.rglob("*")) if pkg.is_dir() else []:
        if p.is_file() and p.suffix.lower() in ARTIFACT_EXTS:
            rel = p.relative_to(root).as_posix()
            if rel not in paths:
                undeclared.append((rel, p))
    counters["undeclared"] = len(undeclared)
    if not pkg.is_dir():
        unver.append("提交包目录不存在 ⇒ 未登记面未验")

    if auth:
        for rel in paths:
            p = root / rel
            if not p.is_file():
                continue
            txt, _ = text_layer(p)
            if txt is None or txt.startswith("!"):
                continue
            found = {x.group(1) for x in BRAND_RE.finditer(txt)}
            if not found:
                continue  # 无该形状的署名（如 .ps1）不参与口径判据
            counters["brand_checked"] += 1
            odd = {x for x in found if x != auth}
            if odd:
                bad.append("在册交付物品牌分叉: %s 文本层含 %s，权威源是 %s" % (rel, sorted(odd), auth))

    for rel, p in undeclared:
        txt, _ = text_layer(p)
        found = {x.group(1) for x in BRAND_RE.finditer(txt or "")} if txt else set()
        odd = {x for x in found if auth and x != auth}
        is_tracked = tracked(rel)
        label = "已跟踪" if is_tracked else ("未跟踪" if is_tracked is False else "跟踪态未知")
        if not auth:
            notes.append("未登记交付物 %s（%s）⇒ 权威串缺失，分叉判定未验" % (p.name, label))
            unver.append("未登记件 %s 品牌分叉未验" % p.name)
        elif odd and is_tracked:
            bad.append("未登记但已入库的交付物品牌分叉: %s 含 %s，权威源 %s"
                       "（进入提交面前须统一或登记）" % (rel, sorted(odd), auth))
        elif odd:
            notes.append("未登记草稿 %s（%s）文本层含 %s ≠ 权威 %s ⇒ 计数不判红，入库即拦"
                         % (p.name, label, sorted(odd), auth))
        else:
            notes.append("未登记交付物 %s（%s，品牌无分叉）" % (p.name, label))
    return bad, unver, notes, counters


def real_run() -> int:
    if not CHECKLIST.is_file():
        print("DELIVERABLE-INVENTORY-UNVERIFIED: 清单本体不存在 -> %s" % CHECKLIST.relative_to(ROOT))
        return 2
    try:
        text = CHECKLIST.read_text(encoding="utf-8")
    except Exception as exc:
        print("DELIVERABLE-INVENTORY-UNVERIFIED: 清单不可读 %s" % type(exc).__name__)
        return 2
    rows = table_rows(text)
    paths = declared_paths(rows)
    bad, unver, notes, c = evaluate(rows, paths)
    entries, skipped, per_root = committed_faces()
    moves, mv_why = staged_renames()
    if moves is None:
        unver.append("搬卷面未验（%s）⇒ 本轮不认任何搬迁，缺失照旧判红" % mv_why)
    t_bad, t_unver, t_n, moved = tracked_missing_check(entries, moves=moves)
    bad += t_bad
    unver += t_unver
    if skipped:
        unver.append("HEAD 树有 %d 条记录取不到尺寸 ⇒ 入库面分母不完整，本腿不判绿" % skipped)
    for n in notes:
        print("  · " + n)
    for m in moved:
        print("  → 搬卷（逐字节等价、落点仍在受检面内）: " + m)
    for b in bad:
        print("  ✗ " + b)
    for u in unver:
        print("  ? " + u)
    tail = ("声明 %d 条｜受检 %d｜品牌在册比对 %d｜未登记交付物 %d｜入库件在位 %d｜搬卷 %d｜未验 %d"
            "｜分母根 %s（%s）"
            % (c["declared"], c["checked"], c["brand_checked"], c["undeclared"], t_n,
               len(moved), len(unver), len(per_root),
               " ".join("%s=%d" % (k, v) for k, v in sorted(per_root.items()))))
    if bad:
        print("DELIVERABLE-INVENTORY-FAIL: %d 条违规（%s）" % (len(bad), tail))
        return 1
    if not paths or c["declared"] == 0:
        print("DELIVERABLE-INVENTORY-UNVERIFIED: 分母为 0，不判绿（%s）" % tail)
        return 2
    if unver:
        print("DELIVERABLE-INVENTORY-UNVERIFIED: 零违规但 %d 项未验（%s）" % (len(unver), tail))
        return 2
    print("DELIVERABLE-INVENTORY-PASS: 清单声明⇄磁盘⇄口径⇄入库面四方对账全等（%s）" % tail)
    return 0


def selftest() -> int:
    """9 类夹具（全走合成数据，不碰真实交付件）。"""
    bad = []

    def ck(name, cond):
        ASSERT_COUNT[0] += 1
        if not cond:
            bad.append(name)

    rows = [["1", "应用方案 PDF", "≤20页，9项内容齐全", "正文 `交付物/提交包/plan.pdf`"],
            ["2", "演示视频 MP4", "≤5分钟", "`交付物/提交包/v.mp4` sha256=" + "a" * 64]]
    ps = declared_paths(rows)
    ck("①声明面枚举到 2 条", ps == ["交付物/提交包/plan.pdf", "交付物/提交包/v.mp4"])
    ck("②约束现读 20 页", row_constraints(rows[0]).get("max_pages") == 20)
    ck("③约束现读 300 秒", row_constraints(rows[1]).get("max_seconds") == 300)
    ck("④指纹现读", row_constraints(rows[1]).get("sha256") == "a" * 64)

    # ⑤零分母不得判绿
    b5, u5, _, _ = evaluate([], [])
    ck("⑤空表 ⇒ 未验非零", not b5 and len(u5) == 1)
    b6, u6, _, _ = evaluate(rows, [])
    ck("⑥有表零路径 ⇒ 未验非零", not b6 and len(u6) == 1)

    # ⑦token 字符集：路径后紧跟中文句号/全角括号不得被吞
    one = [["1", "x", "≤20页", "见 `交付物/提交包/a.pdf`。以及（`交付物/提交包/b.pdf`）"]]
    tok = declared_paths(one)
    ck("⑦尾随标点不入 token: %s" % tok, tok == ["交付物/提交包/a.pdf", "交付物/提交包/b.pdf"])

    # ⑧时长解析：mvhd v0 合成盒
    import struct
    def mkmp4(sec):
        box = b"mvhd" + bytes([0]) + b"\0\0\0" + b"\0" * 8
        box += struct.pack(">II", 1000, int(sec * 1000)) + b"\0" * 80
        return b"\0\0\0" + struct.pack(">I", len(box) + 4)[1:] + box
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "x.mp4"
        p.write_bytes(mkmp4(218.48))
        got = mp4_seconds(p)
        ck("⑧mvhd 读数与注入值同尺: %s" % got, got is not None and abs(got - 218.48) < 0.01)
        p.write_bytes(b"not-a-mp4")
        ck("⑨无 mvhd ⇒ None（交未验，不猜）", mp4_seconds(p) is None)

    # ⑩⑪ 取数解析层：字段序按 2026-09-29 `od -c` 逐字节实测构造（**不是**按解析器假设构造）
    hex_a, hex_b, hex_c = "a" * 40, "b" * 40, "c" * 40
    ok_out = ("100644 blob " + hex_a + "    8437\t交付物/提交包/a.md\x00"
              "100644 blob " + hex_b + "  22954501\t交付物/提交包/b.mp4\x00")
    e10, m10 = parse_ls_tree(ok_out)
    ck("⑩两条合法记录全解析出来: %s/%d" % (e10, m10),
       len(e10) == 2 and m10 == 0 and e10[1] == ("交付物/提交包/b.mp4", 22954501))
    e11, m11 = parse_ls_tree(ok_out + "no-tab-record\x00"
                             + "100644 blob " + hex_c + " -\t交付物/子目录\x00")
    ck("⑪残行与 tree 记录(size 位为 -)必须计入 skipped 而非静默丢: %s/%d" % (e11, m11),
       len(e11) == 2 and m11 == 2)

    # ⑫ 独立通道交叉核对：同一 HEAD 用另一条命令数一遍条目数，防「夹具与解析器同错」
    x12 = parse_crosscheck()
    ck("⑫解析条目数与独立取数通道不等: %s" % (x12,), x12[0] is True)
    if x12[0] is None:
        print("  ! ⑫独立通道交叉核对未执行（%s）⇒ 该腿本轮未验，不算过" % x12[1])

    bad += fixture_legs()
    print(("DELIVERABLE-INVENTORY-SELFTEST-%s（实跑 %d 条断言：纯函数夹具 + 取数解析腿含独立通道对账 "
           "+ 端到端反向腿含真 git mv 往返）")
          % ("PASS" if not bad else "FAIL: " + "; ".join(bad), ASSERT_COUNT[0]))
    for x in bad:
        print("  ✗ " + x)
    return 1 if bad else 0


def name_status_legs(root: Path, archived: str) -> list:
    """`parse_name_status_z` 的取数层夹具 —— 输入**逐字节**取自 2026-10-02 本轮在同一台机器、
    同一个仓上对真 `git mv` 取回的原文（`R100\\0<old>\\0<new>\\0`），不是按解析器假设构造。

    立此约束的一手教训就在本文件 ⑩⑪ 两条腿的注释里：夹具与解析器按同一个错假设写 ⇒
    `--selftest` 全绿而真面 89/89 判废。所以这三条腿额外做一次**真 git 往返**（在本轮合成的
    temp 仓里 `git mv` 一个文件再看 helper 认不认），把「假设」换成「被测数据面自己吐的字节」。
    """
    bad = []

    def ck(name, cond):
        ASSERT_COUNT[0] += 1
        if not cond:
            bad.append(name)

    measured = ("R100\x00交付物/对标分析报告-2026-09-24.md\x00"
                "交付物/_历史轮次-对标/对标分析报告-2026-09-24.md\x00").encode("utf-8")
    m1, u1 = parse_name_status_z(measured)
    ck("㉑本轮实测字节（R100+两条 CJK 路径，NUL 分隔）解析出 1 条: %s/%d" % (m1, u1),
       len(m1) == 1 and u1 == 0
       and m1["交付物/对标分析报告-2026-09-24.md"][1] == 100)
    m2, u2 = parse_name_status_z(b"M\x00a.txt\x00R100\x00b.txt\x00")
    ck("㉒被截断的 R 必须计入 unparsed 而非静默丢（M 记录本身不该让解析提前中止）: %s/%d" % (m2, u2),
       len(m2) == 0 and u2 == 1)
    # r93 新增腿：真提交形态 = 「搬卷 + 其他文件同提交」。这一腿在修之前是**测不出来的**——
    # 旧夹具的流里 R 后面少一条路径，解析器在更前面的 `M` 上就已经 break，两种实现都给出
    # 同样的 (0, 1)，于是夹具把bug 写成了期望值（与本文件 ⑫ 那条「夹具自证不了自己」同族）。
    m2b, u2b = parse_name_status_z(b"A\x00new.py\x00M\x00README.md\x00R100\x00old.md\x00new2.md\x00")
    ck("㉒b 搬卷与其他文件同提交必须全部解析出（R100 认下、unparsed=0）: %s/%d" % (m2b, u2b),
       len(m2b) == 1 and u2b == 0 and "old.md" in m2b and m2b["old.md"][0] == "new2.md")
    m3, u3 = parse_name_status_z(b"not-a-status\x00x\x00")
    ck("㉓首字段不是状态 ⇒ unparsed=1（调用方据此不替任何搬迁背书）: %s/%d" % (m3, u3),
       not m3 and u3 == 1)

    # ㉔ 真 git 往返：在被检对象自己的仓库视图里做一次搬卷，helper 必须认下来
    import os
    repo = root / "git-probe"
    try:
        (repo / "交付物").mkdir(parents=True)
        src = repo / "交付物" / "p.md"
        src.write_text("同一份字节", encoding="utf-8")
        env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
                   GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
        rq = ["git"]
        if subprocess.run(rq + ["--version"], cwd=str(repo), capture_output=True).returncode != 0:
            ck("㉔真 git 往返未执行（git 不可调用）", False)
            return bad
        subprocess.run(rq + ["init", "-q"], cwd=str(repo), capture_output=True, env=env)
        subprocess.run(rq + ["add", "-A"], cwd=str(repo), capture_output=True, env=env)
        subprocess.run(rq + ["commit", "-q", "-m", "seed"], cwd=str(repo),
                       capture_output=True, env=env)
        (repo / "交付物" / "_历史轮次-对标").mkdir(parents=True)
        subprocess.run(rq + ["mv", "交付物/p.md", "交付物/_历史轮次-对标/p.md"],
                       cwd=str(repo), capture_output=True, env=env)
        moves, why = staged_renames(root=repo)
        got = (moves or {}).get("交付物/p.md")
        ck("㉔真 `git mv` 后 staged_renames 认出搬卷（moves=%s why=%s）" % (moves, why),
           moves is not None and got is not None and got[1] == 100
           and got[0] == "交付物/_历史轮次-对标/p.md")
        tb, _, _, mv = tracked_missing_check([("交付物/p.md", 15)], root=repo, moves=moves)
        ck("㉔同一状态过在位判据 ⇒ 不红且计入搬卷（%s/%s）" % (tb, mv), not tb and len(mv) == 1)
    except Exception as exc:
        ck("㉔真 git 往返异常 %s" % type(exc).__name__, False)
    return bad


def fixture_legs() -> list:
    """端到端反向腿：合成整棵「提交包 + 权威源」，逐形证明判据会红／不红得其所。

    这一组是本轮判据的**存在理由** —— 2026-09-28 真实丢失的就是 B/C 两形（清单写着要交的文件
    从工作树消失），而当时 91 套件零告警。只测正向（真面绿）的判据等于没测（[[negative-control-first]]）。

    r94：函数体整段下移到 `_fixture_legs_body`（146 行，≤150）。拆的动机不是「好看」，
    是 `loc_guard` 的函数长门（≤150，对标 opensoul check:loc）——本函数此前 158 行。
    切点用 AST 求得（前 4 条语句零变量跨越），不是目测。
    """
    return _fixture_legs_body()


def _fixture_legs_body() -> list:
    def mkmp4(sec):
        box = b"mvhd" + bytes([0]) + b"\0\0\0" + b"\0" * 8
        box += struct.pack(">II", 1000, int(sec * 1000)) + b"\0" * 80
        return b"\0\0\0" + struct.pack(">I", len(box) + 4)[1:] + box

    bad = []

    def ck(name, cond):
        ASSERT_COUNT[0] += 1
        if not cond:
            bad.append(name)

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        pkg = root / "交付物" / "提交包"
        (pkg / "demo_video_out").mkdir(parents=True)
        (root / "src").mkdir()
        (root / "src" / "index.html").write_text(
            '<div class="brand">心屿<span class="brand-sub">SoulIsle</span></div>', encoding="utf-8")
        from pypdf import PdfWriter
        w = PdfWriter()
        w.add_blank_page(width=200, height=200)
        w.add_blank_page(width=200, height=200)
        pdf = pkg / "plan.pdf"
        with pdf.open("wb") as f:
            w.write(f)
        vid = pkg / "demo_video_out" / "v.mp4"
        vid.write_bytes(mkmp4(218.48))
        (pkg / "notes.md").write_text("心屿 SoulIsle 正文", encoding="utf-8")
        z = zipfile.ZipFile(str(pkg / "draft.pptx"), "w")
        z.writestr("ppt/slides/slide1.xml", "<a:t>心屿 MindIsle 团队</a:t>")
        z.close()
        real_sha = sha256_of(vid)

        def rows_for(pdf_lim, vid_lim, sha):
            return [["1", "PDF", u"≤%d页" % pdf_lim, "见 `交付物/提交包/plan.pdf`"],
                    ["2", "视频", u"≤%d分钟" % vid_lim,
                     "`交付物/提交包/demo_video_out/v.mp4` sha256=" + sha, "还有 `交付物/提交包/notes.md`"],
                    ["3", "笔记", "无", "`交付物/提交包/notes.md`"]]

        good = rows_for(20, 5, real_sha)
        good_paths = declared_paths(good)
        b0, u0, n0, c0 = evaluate(good, good_paths, root=root, tracked=lambda r: False)
        ck("Ⓐ基线：合成正例不得判红 %s" % b0, not b0 and not u0 and c0["undeclared"] == 1)

        b1, _, _, _ = evaluate(good, good_paths + ["交付物/提交包/ghost.pdf"], root=root,
                               tracked=lambda r: False)
        ck("Ⓑ声明件从磁盘消失 ⇒ 必红（本轮真实事故形）", any("声明缺失" in x for x in b1))

        # Ⓟ/Ⓠ r85 补：清单里的目录 token 不是交付件（本判据曾把它判成假缺失——
        #   同族第四例的现场），修复后必须双向钉住：在位 ⇒ 未验跳过；指丢 ⇒ 照旧红。
        bp, up, np, _ = evaluate(good, good_paths + ["交付物/提交包/demo_video_out"], root=root,
                                 tracked=lambda r: False)
        ck("Ⓟ在位目录 token 不得判假缺失也不得压成未验（记 note 跳过）%s" % np,
           not bp and not up and any("目录指针" in x for x in np))
        bq, _, _, _ = evaluate(good, good_paths + ["交付物/提交包/no-such-dir/"], root=root,
                               tracked=lambda r: False)
        ck("Ⓠ目录 token 指丢了仍须红（指针丢也是信息丢失）", any("声明缺失" in x for x in bq))

        (pkg / "empty.pdf").write_bytes(b"")
        b2, _, _, _ = evaluate(good, good_paths + ["交付物/提交包/empty.pdf"], root=root,
                               tracked=lambda r: False)
        ck("Ⓒ声明件存在但 0 B ⇒ 必红", any("空文件" in x for x in b2))

        b3, _, _, _ = evaluate(rows_for(1, 5, real_sha), good_paths, root=root, tracked=lambda r: False)
        ck("Ⓓ页数超官方上限 ⇒ 必红", any("页数越界" in x for x in b3))

        b4, _, _, _ = evaluate(rows_for(20, 1, real_sha), good_paths, root=root, tracked=lambda r: False)
        ck("Ⓔ时长超官方上限 ⇒ 必红", any("时长越界" in x for x in b4))

        b5, _, _, _ = evaluate(rows_for(20, 5, "0" * 64), good_paths, root=root, tracked=lambda r: False)
        ck("Ⓕ成片指纹与清单登记值不符 ⇒ 必红", any("指纹漂移" in x for x in b5))

        (pkg / "notes.md").write_text("心屿 MindIsle 正文", encoding="utf-8")
        b6, _, _, _ = evaluate(good, good_paths, root=root, tracked=lambda r: False)
        ck("Ⓖ在册交付物品牌与权威源分叉 ⇒ 必红", any("品牌分叉" in x for x in b6))
        (pkg / "notes.md").write_text("心屿 SoulIsle 正文", encoding="utf-8")

        b7, _, _, _ = evaluate(good, good_paths, root=root, tracked=lambda r: True)
        ck("Ⓗ未登记件一旦入库 ⇒ 必红（棘轮）", any("未登记但已入库" in x for x in b7))
        b8, _, n8, c8 = evaluate(good, good_paths, root=root, tracked=lambda r: False)
        ck("Ⓘ未登记草稿不误伤在途件 ⇒ 不红但计数 %s" % c8["undeclared"],
           not any("品牌" in x for x in b8) and c8["undeclared"] == 2
           and any("入库即拦" in x for x in n8))

        # Ⓙ-Ⓝ r82 新腿：入库面（分母 = HEAD 树，被检对象写不进去）
        ghost = "交付物/提交包/demo_video_out/gone.mp4"
        tb1, tu1, tn1, mv1 = tracked_missing_check(
            [(ghost, 22954501), ("交付物/提交包/plan.pdf", 1000)], root=root)
        ck("Ⓙ入库件消失⇒必红（且它**不在声明面**，旧腿抓不到）%s" % tb1,
           ghost not in good_paths and len(tb1) == 1 and "入库件从工作树消失" in tb1[0]
           and tn1 == 2 and not tu1 and not mv1)
        tb2, tu2, tn2, mv2 = tracked_missing_check(
            [("交付物/提交包/plan.pdf", 1000), ("交付物/提交包/notes.md", 50)], root=root)
        ck("Ⓚ入库件都在位 ⇒ 不红且不虚报未验 %s/%s" % (tb2, tu2),
           not tb2 and not tu2 and tn2 == 2 and not mv2)
        (pkg / "zeroed.md").write_text("", encoding="utf-8")
        tb3, _, _, _ = tracked_missing_check([("交付物/提交包/zeroed.md", 512)], root=root)
        ck("Ⓦ入库件被清成 0 B ⇒ 必红", tb3 and "0 B" in tb3[0])
        (pkg / "zeroed.md").unlink()
        tb4, tu4, tn4, _ = tracked_missing_check(None, root=root)
        ck("Ⓜgit 取不到 ⇒ UNVERIFIED 而非判绿 %s" % tu4,
           not tb4 and len(tu4) == 1 and tn4 == 0)
        tb5, tu5, _, _ = tracked_missing_check([], root=root)
        ck("ⓃHEAD 该前缀零条目 ⇒ 分母为 0 不判绿", not tb5 and len(tu5) == 1)

        # ⓣ-ⓙ r90 新腿：搬卷认定（07 在册 🟠 R89-01 卡点）
        # 夹具形态必须忠实于「搬」这件事本身：旧路径**不在磁盘上**、新路径在。
        # 第一版我拿还在磁盘上的 notes.md 当被搬件 ⇒ 五条腿全被判据的 is_file() 分支短路掉
        # （走了「件还在」而不是「件搬走了」），绿是绿不了但红得毫无信息量 —— 同族教训见 ⑩⑪。
        gone_rel = "交付物/提交包/gone.md"
        archived = "交付物/_历史轮次-对标/gone.md"
        (pkg.parent / "_历史轮次-对标").mkdir(exist_ok=True)
        (root / archived).write_text("搬来的正文", encoding="utf-8")
        moved_ok = {gone_rel: (archived, 100)}
        tb6, tu6, tn6, mv6 = tracked_missing_check(
            [(gone_rel, 17)], root=root, moves=moved_ok)
        ck("ⓣ逐字节等价搬卷且落点在面内 ⇒ 不红且计入搬卷 %s/%s" % (tb6, mv6),
           not tb6 and not tu6 and tn6 == 1 and len(mv6) == 1)
        tb7, _, _, mv7 = tracked_missing_check(
            [(gone_rel, 17)], root=root, moves={gone_rel: (archived, 95)})
        ck("ⓕ改过内容再搬（score<100）⇒ 仍判红，不替内容变更背书 %s" % mv7,
           tb7 and "不认" in tb7[0] and not mv7)
        tb8, _, _, _ = tracked_missing_check(
            [(gone_rel, 17)], root=root, moves={gone_rel: ("docs/gone.md", 100)})
        ck("ⓖ搬到受检面外 ⇒ 仍判红（搬=换个没人看的地方，不算归档）%s" % tb8,
           tb8 and "落点在受检面外" in tb8[0])
        tb9, _, _, _ = tracked_missing_check(
            [(gone_rel, 17)], root=root,
            moves={gone_rel: ("交付物/_历史轮次-对标/not-on-disk.md", 100)})
        ck("ⓗ索引写了新路径但磁盘没落地 ⇒ 仍判红 %s" % tb9,
           tb9 and "新落点不在磁盘上" in tb9[0])
        tb10, _, _, mv10 = tracked_missing_check([(gone_rel, 17)], root=root, moves=None)
        ck("ⓘ搬卷面取不到（moves=None）⇒ 回落旧行为判红，绝不因查不到而放行 %s" % mv10,
           len(tb10) == 1 and "无人声明也丢" in tb10[0] and not mv10)
        tba, _, tna, _ = tracked_missing_check(
            [("archive/交付物-历史轮次/lost.md", 123)], root=root)
        ck("ⓙ归档根上的件同样受检（搬进去≠出了守面）%s" % tba,
           len(tba) == 1 and tna == 1 and "从工作树消失" in tba[0])
        (root / archived).unlink()
        tbb, _, _, mvb = tracked_missing_check([(gone_rel, 17)], root=root, moves=moved_ok)
        ck("㉑落点文件随后也没了 ⇒ 不认搬、判红（搬一半丢一半不许绿）%s/%s" % (tbb, mvb),
           len(tbb) == 1 and not mvb)
        (root / archived).write_text("搬来的正文", encoding="utf-8")
        bad += name_status_legs(root, archived)
    return bad


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    sys.exit(real_run())
