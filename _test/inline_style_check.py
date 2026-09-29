#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""markup 级内联样式扫描（轮81，r81 对标轮立）。

判据对象 = 会被 CSP `style-src 'self'` 拦下的**标记层**写法：模板串/HTML 里的
`style="…"`、`<style>` 元素、`setAttribute("style", …)`、`.cssText =`。
**不判** CSSOM 逐属性赋值（`el.style.color = "…"`）—— 那条不受 style-src 约束，
是本仓线上唯一可行的动态着色路子。

立此判据的一手代价：线上 8 条 `Applying inline style violates … 'style-src 'self'`
（`python _test/public_check.py` rc=1），根因在 `src/js/app.js` 把 style 属性拼进
`innerHTML`；后果不止控制台噪声 —— 情绪强度条的 `width:${pct}%` 也在同一写法里，
线上那条读数是失效的。本地无 CSP 头，`browser_check.py` 看不见这类破坏，故须静态面补。

欠账基线按**整行归一化后的 sha256 前 12 位**锚定（不按行号：行号会因上方插入而漂移，
那会让一次正常提交变不了绿）。基线条目消失只报清偿，不判红 ⇒ 修的人不必同时改本文件。
"""
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 取数面（结构枚举，非 glob 命中数）：两面各一份 app.js，必须同法扫
FACES = [
    ("src/index.html", "file"),
    ("src/js", "dir"),
    ("deploy/xinyu/index.html", "file"),
    ("deploy/xinyu/js", "dir"),
]

# vendor 属第三方压缩产物，不在本判据承诺范围（改它即改上游版本）
EXCLUDE_PARTS = ("vendor",)

PATTERNS = [
    ("markup-style-attr", re.compile(r"""\bstyle\s*=\s*["']""")),
    ("markup-style-el", re.compile(r"<style[\s>/]")),
    ("setattribute-style", re.compile(r"""setAttribute\(\s*["']style["']""", re.I)),
    ("csstext-write", re.compile(r"\.cssText\s*=")),
]

# 欠账基线（r81 现读 14 处 = 7 个唯一行 × src 与 deploy 两面）。
# 状态：**r82 已清偿**（真面 `扫描=30｜命中=0｜新增=0`，14 个指纹全部不再出现）。
# 修法照 r81 §4 第 1 条：静态部分进 style.css 的 .crisis-chip/.readout-line/.readout-lead，
# 动态部分写 data-fg/data-bg/data-w 再由 app.js 的 paint() 一趟 CSSOM 落属性；**没有**放宽 CSP。
# 基线清空后本判据即「纯网」：任何新写的 markup 内联 style 当场判红（selftest ⑬ 钉住这条腿仍会咬人）。
DEBT = {}
DEBT_FACES = ("src/js/app.js", "deploy/xinyu/js/app.js")


def norm(line):
    """CRLF/LF 与缩进不参与指纹：CI 在 Linux（LF）、本机可能是 CRLF，
    同一行两端必须得同一个 hash，否则基线第一次上受理面就假红。"""
    return line.replace("\r", "").strip()


def fingerprint(line):
    return hashlib.sha256(norm(line).encode("utf-8")).hexdigest()[:12]


def rel_key(p):
    try:
        rel = Path(p).resolve().relative_to(ROOT)
    except ValueError:
        rel = Path(Path(p).name)
    return str(rel).replace("\\", "/")


def gather_files(rel_root=None):
    """取数面的文件清单（与 collect 同源，避免两处各数一遍）。"""
    base = ROOT if rel_root is None else Path(rel_root)
    files = []
    for entry, kind in FACES:
        p = base / entry
        if kind == "file":
            if p.is_file():
                files.append(p)
        elif p.is_dir():
            files.extend(sorted(x for x in p.glob("*.js") if x.is_file()))
    return files


def collect(rel_root=None, files=None):
    """返回 ([(relpath, lineno, kind, raw_line)], 扫描文件数)；files=None 走真实取数面。"""
    hits = []
    if files is None:
        files = gather_files(rel_root)
    for p in files:
        rel = rel_key(p)
        if any(part in EXCLUDE_PARTS for part in Path(rel).parts):
            continue
        text = p.read_bytes().decode("utf-8", errors="replace")
        for i, line in enumerate(text.replace("\r", "").split("\n"), 1):
            for kind, pat in PATTERNS:
                if pat.search(line):
                    hits.append((rel, i, kind, line))
                    break
    return hits, len(files)


def dead_debt_faces(scanned, root=None, debt=None):
    """基线锚定的文件必须真实存在且被扫到（锚到已改名/已删的文件＝死豁免，永远不会有人来清偿）。

    ⚠️ r82 一手修正：本腿首版写成 `scanned = {命中里的 rel}` ⇒ **欠账一旦清零（命中=0）就反过来说
    「基线锚空面」**，13 腿里红 1 条。红因不是代码变坏了，是判据把「没命中」当成了「没扫到」——
    取数面要由 `gather_files()` 给，与命中与否无关。按 R263 修判据，不为了让腿绿而回滚修复。
    """
    root = Path(root) if root else ROOT
    return [rel for rel in (DEBT if debt is None else debt)
            if rel not in scanned or not (root / rel).is_file()]


def measure(hits):
    """按基线把命中分成 新增 / 欠账 / 清偿三桶，互斥不重叠。"""
    new, known = [], []
    for rel, i, kind, line in hits:
        (known if fingerprint(line) in DEBT.get(rel, ()) else new).append((rel, i, kind, line))
    gone = []
    present = {rel for rel, _, _, _ in hits}
    for rel, hs in DEBT.items():
        if rel in present:
            continue
        for h in sorted(hs):
            gone.append((rel, h))
    return new, known, gone


def gate(hits, n_files):
    """返回 (状态词, 读数行)。零输入不判绿；新增判红；基线只降格为欠账。"""
    if n_files == 0:
        return "UNVERIFIED", "INLINE-STYLE-UNVERIFIED: 取数面一个文件都没扫到（面配置失效不等于合规）"
    new, known, gone = measure(hits)
    kinds = sorted({k for _, _, k, _ in hits})
    # 读数行不得在基线已清空时仍写「未修，线上 CSP 仍拦」——那是判据替别人做的未成立判断
    debt_note = "%d 处（未修，线上 CSP 仍拦）" % len(known) if known else "0 处（已清偿，本判据现为纯网）"
    readout = ("扫描=%d 文件｜命中=%d（类型 %d 种：%s）｜欠账基线=%s"
               "｜新增=%d｜本次清偿=%d" % (n_files, len(hits), len(kinds), ",".join(kinds) or "-",
                                         debt_note, len(new), len(gone)))
    if new:
        return "FAIL", readout
    return "PASS", readout


def selftest():
    """正例（CSSOM 合规不判红）+ 反例（四种 markup 写法各判红）+ 基线与盲区腿。"""
    import tempfile
    ok = bad = 0

    def case(name, cond, detail=""):
        nonlocal ok, bad
        if cond:
            ok += 1
        else:
            bad += 1
            print("SELFTEST-FAIL: %s %s" % (name, detail))

    tmp = Path(tempfile.mkdtemp(prefix="inline_style_"))
    for entry, kind in FACES:
        (tmp / entry).parent.mkdir(parents=True, exist_ok=True)
        if kind == "file":
            (tmp / entry).write_text("", encoding="utf-8")
        else:
            (tmp / entry).mkdir(parents=True, exist_ok=True)

    def scan(name, content):
        f = tmp / "src" / "js" / name
        f.write_text(content, encoding="utf-8")
        hits, n = collect(rel_root=tmp, files=[f])
        return hits, n

    # ① 正例：CSSOM 逐属性赋值是本仓认可的路子，不得判红
    hits, _ = scan("a.js", 'el.style.color = "#fff"; el.style.width = pct + "%";')
    case("CSSOM 正例不得判红", len(hits) == 0, str(hits))
    # ②..⑤ 反例：四类 markup 写法各须命中且具名
    for label, body, want in (
        ("模板串 style 属性", '`<b style="color:${hex}">${n}</b>`', "markup-style-attr"),
        ("HTML style 属性", '<p class="muted" style="margin-top:8px">x</p>', "markup-style-attr"),
        ("<style> 元素", "<style>.a{color:red}</style>", "markup-style-el"),
        ("setAttribute style", 'el.setAttribute("style", css)', "setattribute-style"),
        ("cssText 写入", "el.style.cssText = css", "csstext-write"),
    ):
        hits, _ = scan("b.js", body)
        case("反例 %s 必须命中" % label, len(hits) == 1 and hits[0][2] == want, str(hits))
    # ⑥ 恒真守卫：空白文件不得判出任何命中（防"取数即命中"）
    hits, _ = scan("c.js", "// no style here at all\n")
    case("恒真守卫：无 style 字样不得判出命中", len(hits) == 0, str(hits))
    # ⑦ 基线精确性：欠账行降格为 known，同类改写（多一个空格以外无差）仍须算新增
    hits, _ = scan("d.js", '<i class="dot" style="background:#ff5566"></i>')
    case("基线按面锚定：非基线文件的新增必须判新", len(hits) == 1 and measure(hits)[1] == [], str(measure(hits)))
    # ⑧ 行尾归一：同一行的 LF 与 CRLF 形态必须同指纹（否则基线在 CI 侧假红）
    lf, crlf = '  <p style="margin-top:8px">x</p>', '  <p style="margin-top:8px">x</p>\r\n'
    case("CRLF/LF 同指纹", fingerprint(lf) == fingerprint(crlf), "%s vs %s" % (fingerprint(lf), fingerprint(crlf)))
    # ⑨ 零输入不得判绿
    st, line0 = gate([], 0)
    case("零输入不判绿", st == "UNVERIFIED", line0)
    # ⑩ 真面自证：本仓现读命中必须全部落进基线（新增=0），否则要么有人新写了内联样式，要么基线抄错
    real, n = collect()
    st, readout = gate(real, n)
    case("真面新增=0（基线与磁盘对得上）", st == "PASS", readout)
    # ⑪ 阻断分支端到端：基线外的一条命中必须让 gate 判 FAIL（否则闸门只会印数字不会拦）
    st2, _ = gate([("src/js/x.js", 1, "markup-style-attr", '<i style="color:red"></i>')], 5)
    case("gate 阻断分支：基线外命中判 FAIL", st2 == "FAIL", st2)
    # ⑫ 基线不得锚空面：DEBT 的每个文件都须真实存在且**在取数面里**（锚到已改名/已删的文件＝死豁免）。
    #     r82 修正：取数面取自 gather_files()，不是取自命中 —— 欠账清零后命中为空，
    #     旧写法会把「我没扫到」误报成「基线锚空面」（一手：本轮 13 腿红 1 条就是这么来的）。
    scanned = {rel_key(p) for p in gather_files()}
    case("基线不得锚空面（死豁免）", dead_debt_faces(scanned) == [], str(dead_debt_faces(scanned)))
    # ⑬ 反例：基线指向不存在的文件必须被抓到，否则 ⑫ 是一条恒真腿（清空的基线尤其需要它）
    hit_ghost = dead_debt_faces(scanned, debt={"src/js/gone-r82-ghost.js": {"x" * 12}})
    case("⑬死豁免反例必须判红", hit_ghost == ["src/js/gone-r82-ghost.js"], str(hit_ghost))
    # ⑭ 命中清零不得被读成「尺瞎了」：取数面分母仍须 >0
    case("⑭真面命中=0 时分母仍非空（%d 文件）" % n, n > 0 and st == "PASS", "%s %s" % (st, n))
    print("INLINE-STYLE-READOUT: %s" % readout)

    print("INLINE-STYLE-SELFTEST: %d/%d%s" % (ok, ok + bad, "" if bad == 0 else "（%d 条失败）" % bad))
    return 0 if bad == 0 else 1


def main(argv):
    if "--selftest" in argv:
        return selftest()
    hits, n_files = collect()
    state, readout = gate(hits, n_files)
    new, known, gone = measure(hits)
    for rel, i, kind, line in new:
        print("  · 新增 %s:%d [%s] %s" % (rel, i, kind, norm(line)[:90]))
    for rel, h in gone:
        print("  · 已清偿（基线里的该指纹不再出现，可从 DEBT 移除）%s %s" % (rel, h))
    print("%s: %s" % ({"PASS": "INLINE-STYLE-PASS", "FAIL": "INLINE-STYLE-FAIL",
                       "UNVERIFIED": "INLINE-STYLE-UNVERIFIED"}[state], readout))
    return {"PASS": 0, "FAIL": 1, "UNVERIFIED": 2}[state]


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
