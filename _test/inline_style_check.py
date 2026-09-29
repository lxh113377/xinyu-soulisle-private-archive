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
# 状态：未修。修法见 交付物/对标分析报告-2026-09-29-r81.md §4 第 1 条（改 CSSOM，不放宽 CSP）。
DEBT = {
    "src/js/app.js": {
        "51f8335fd152", "974941e13f90", "f80da40bcabf", "70b7a6c60ab1",
        "05f4f400b320", "8feb64653ac4", "e0c681fc7b2b",
    },
    "deploy/xinyu/js/app.js": {
        "51f8335fd152", "974941e13f90", "f80da40bcabf", "70b7a6c60ab1",
        "05f4f400b320", "8feb64653ac4", "e0c681fc7b2b",
    },
}

DEBT_FACES = ("src/js/app.js", "deploy/xinyu/js/app.js")


def norm(line):
    """CRLF/LF 与缩进不参与指纹：CI 在 Linux（LF）、本机可能是 CRLF，
    同一行两端必须得同一个 hash，否则基线第一次上受理面就假红。"""
    return line.replace("\r", "").strip()


def fingerprint(line):
    return hashlib.sha256(norm(line).encode("utf-8")).hexdigest()[:12]


def collect(rel_root=None, files=None):
    """返回 [(relpath, lineno, kind, raw_line)]；files=None 走真实取数面。"""
    hits = []
    if files is None:
        base = ROOT if rel_root is None else Path(rel_root)
        files = []
        for entry, kind in FACES:
            p = base / entry
            if kind == "file":
                if p.is_file():
                    files.append(p)
            elif p.is_dir():
                files.extend(sorted(x for x in p.glob("*.js") if x.is_file()))
    for p in files:
        try:
            rel = p.resolve().relative_to(ROOT)
        except ValueError:
            rel = Path(p.name)
        if any(part in EXCLUDE_PARTS for part in rel.parts):
            continue
        text = p.read_bytes().decode("utf-8", errors="replace")
        for i, line in enumerate(text.replace("\r", "").split("\n"), 1):
            for kind, pat in PATTERNS:
                if pat.search(line):
                    hits.append((str(rel).replace("\\", "/"), i, kind, line))
                    break
    return hits, len(files)


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
    readout = ("扫描=%d 文件｜命中=%d（类型 %d 种：%s）｜欠账基线=%d 处（未修，线上 CSP 仍拦）"
               "｜新增=%d｜已清偿=%d" % (n_files, len(hits), len(kinds), ",".join(kinds) or "-",
                                        len(known), len(new), len(gone)))
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
    # ⑫ 基线不得锚空面：DEBT 的每个文件都须真实存在且被扫到（锚到已改名/已删的文件＝死豁免，
    #     永远不会有人来清偿它）。注意本腿**不**要求指纹仍在盘上——修好了就该报清偿，那正是出口。
    scanned = {rel for rel, _, _, _ in real}
    dead_face = [rel for rel in DEBT if rel not in scanned or not (ROOT / rel).is_file()]
    case("基线不得锚空面（死豁免）", dead_face == [], str(dead_face))
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
