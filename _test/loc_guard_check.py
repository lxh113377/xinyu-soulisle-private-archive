# -*- coding: utf-8 -*-
"""行数 / 函数长守卫（对标 opensoul 的 `pnpm check:loc`：文件 ≤2000 行、函数 ≤150 行）

为什么加这条（本轮= r93 对标轮改进项#4，接续 r92 §2② 的登记）：
  peers 侧 opensoul 把「行数 / 函数长」两把尺钉进了 CI 门；本项目此前只有**字节预算**
  （`_test/size_budget_check.py`，逐文件 BUDGETS）与行为 Core P0.8（函数 ≤50 行），
  两者都**不在 CI 受理面上钉死行数**——即「有没有纪律」与「有没有门」是两件事。
  本脚本把行数与函数长变成在册读数，report-only 进电池；待超限清零再切 `--enforce`。

三态退出码（与其他判据同构）：
  0 = LOC-PASS（本门口径下无超限；report-only 模式下恒 0，见下方「为什么 report-only 也能进电池」）
  1 = LOC-FAIL（`--enforce` 且存在超限项，清单逐条打印）
  2 = LOC-UNVERIFIED（取数面为空 / git 面读不到 —— **零输入不得记PASS**）

⚠️ 为什么 report-only 也能进电池（防「恒真判据」质疑）：
  report-only 的 rc 恒为 0 这一点由**两条腿**兜住，不靠自觉——
  ① `--selftest` 断言 `--enforce` 路径对同一批超限样本**必红**、且把阈值调大后转绿
     （变异腿：证明尺作用在被审对象上，不是无条件输出）；
  ② 取数面为空时 rc=2 而非 0（本文件实测：无face 时报 LOC-UNVERIFIED），
     所以「扫不到东西」不会被印成「扫过且没超限」。
  另外 report-only **不替代**既有更严约束，两栏并列打印（见下`context_lines`）。

⚠️ 函数长识别是**启发式**，不是 AST：
  - Python：按 `def`/`class` 顶格缩进块切分（缩进回退即出块）；
  - JS/Java：按 `function`/`=>`/`{` 计数近似，**跨行注释与字符串里的括号会干扰**。
  故本门只作**趋势与排名**读数；函数长的**权威口径**仍是行为 Core P0.8（≤50 行），
  两者不一致时以 Core 为准，本门不得作为「函数超长」的终审证据。
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]

# 与 benchmark_metrics.EXCLUDE_PARTS 同族：取 git 面（HEAD），排除产物与第三方代码。
EXCLUDE_PARTS = {"vendor", "target", "node_modules", "__pycache__", ".git", ".wrangler",
                 ".codebuddy", "_shots", "archive", "交付物", "memory", ".workbuddy", "_temp"}
CODE_EXT = (".js", ".java", ".py", ".html", ".css", ".mjs", ".ts")

DEFAULT_ROWS = 2000   # 对标 opensoul check:loc 的文件行数上限
DEFAULT_FUNC = 150    # 对标 opensoul check:loc 的函数长度上限


def git_files():
    """git 面（HEAD）的代码文件清单。失败即抛 —— 禁止静默退回工作树面
    （r71 一手教训：混面会让台账在别的机器/CI 上复算不出，却在本机永远自洽）。"""
    r = subprocess.run(["git", "-C", str(ROOT), "ls-tree", "-r", "--name-only", "HEAD"],
                       capture_output=True, timeout=60)
    if r.returncode != 0:
        raise RuntimeError("git ls-tree 失败：%s" % (r.stderr or b"").decode("utf-8", "replace")[:120])
    out = []
    for line in (r.stdout or b"").decode("utf-8", "replace").splitlines():
        p = line.strip()
        if not p or not p.endswith(CODE_EXT):
            continue
        if EXCLUDE_PARTS & set(p.split("/")):
            continue
        out.append(p)
    # 去重保序：同一路径若被列出两次，超限清单会重复打印（r94 实测：benchmark_metrics.py 现两行）
    return list(dict.fromkeys(out))


def _py_blocks(lines):
    """Python：def/class 顶格缩进块 → [(name, 行数, 类别)]。

    r94 修：**类是类型容器不是函数**，Python 侧同样要把 `class X:` 归到 `class`
    （原实现连类一起进函数长排名 ⇒ 一个 300 行的类会被当成「628 行的函数」）。
    """
    marks = []
    for i, ln in enumerate(lines):
        s = ln.lstrip()
        if s.startswith("def ") or s.startswith("class ") or s.startswith("async def "):
            indent = len(ln) - len(s)
            name = s.split("(")[0].replace("def ", "").replace("class ", "").replace("async ", "").strip()
            cat = "class" if s.startswith("class ") else "func"
            marks.append((i, indent, name or "?", cat))
    out = []
    for k, (start, indent, name, cat) in enumerate(marks):
        end = len(lines)
        for j in range(start + 1, len(lines)):
            s = lines[j].strip()
            if not s or s.startswith("#"):
                continue
            ind = len(lines[j]) - len(lines[j].lstrip())
            if ind <= indent:
                end = j
                break
        out.append((name, end - start, cat))
    return out


# --- r94 修：块分类（原实现把「类」与「IIFE 模块包装」都算成函数） ---
# 现象（一手）：r93 首次实测 22/158 超限里，**14 项是误判** —— 6 个 Java `class Xxx {`
# 与 8 个 JS IIFE（`window.X = (function () {`，src/ 与 deploy/ 各一份）。若照单执行
# 「清零超限」，就会逼人去**拆类、拆模块包装**，那是破坏 src/ 运行时代码（撞同步红线）
# 且毫无收益的动作 —— 害处来自尺，不是来自代码（与 r70 `rag` 裸子串、r93 `RENAME_STATUS_RE`
# 漏 `A` 同族：尺的语义比它自称的宽 ⇒ 结论偏得比看上去更严重）。
CLASS_RE = re.compile(
    r"(^|\s)((public|private|protected|abstract|final|static|synchronized)\s+)*class\s+\w")
ANON_FN_RE = re.compile(r"function\s*\(")          # 匿名函数表达式 = IIFE/模块包装
NAMED_FN_RE = re.compile(r"function\s+[\w$]+\s*\(")
ARROW_RE = re.compile(r"=>")
JAVA_METHOD_RE = re.compile(
    r"^\s*(?:(?:public|private|protected)\s+)?"
    r"(?:static\s+|final\s+|abstract\s+|synchronized\s+)*"
    r"(?P<ret>[\w<>,\[\]\.]+)\s+(?P<name>[\w$]+)\s*\(")
JAVA_CTOR_RE = re.compile(r"^\s*(?:(?:public|private|protected)\s+)?(?P<name>[\w$]+)\s*\(")
CTRL_KW = {"if", "for", "while", "switch", "catch", "try", "do", "else", "return", "new",
           "synchronized", "static", "else if"}


def _classify(head, is_java=False):
    """`{` 之前的行首文本 → 'class' / 'module' / 'func' / None（None = 分支/字面量，不记）。"""
    if CLASS_RE.search(head):
        return "class"
    if is_java:
        m = JAVA_METHOD_RE.match(head)
        if m and m.group("name") not in CTRL_KW:
            return "func"
        m2 = JAVA_CTOR_RE.match(head)              # 构造器 `ClassName(`
        if m2 and m2.group("name") not in CTRL_KW:
            return "func"
        return None
    if ANON_FN_RE.search(head):
        return "module"                            # IIFE：按**模块**计，不计函数长
    if NAMED_FN_RE.search(head) or ARROW_RE.search(head):
        return "func"
    return None


def _brace_blocks(lines, is_java=False):
    """JS/Java 启发式：栈配对 `{`/`}` → [(hint, 行数, 类别)]。

    r94 修两点：
    ① **只测 depth==0 的块** ⇒ IIFE 内部函数完全不可见（src/js 的函数长此前等于没测）；
       现改为**任意嵌套层**的块都测，嵌套函数不再漏。
    ② 类与 IIFE 模块包装归类为 `class`/`module`，**不进函数长排名**（但行数照常算入文件行数）。
    仍是启发式：跨行注释与字符串里的括号会干扰，故本门只作趋势读数。
    """
    out, stack = [], []
    for i, ln in enumerate(lines):
        if "{" in ln:
            head = ln.split("{")[0]
            cat = _classify(head, is_java)
            for _ in range(ln.count("{")):
                stack.append((i, ln.strip()[:40], cat))
        if "}" in ln:
            for _ in range(ln.count("}")):
                if not stack:
                    continue
                start, hint, cat = stack.pop()
                if cat is not None:
                    out.append((hint, i - start + 1, cat))
        if len(stack) > 4000:      # 括号不平衡的坏文件兜底
            stack = []
    return out


def scan_text(path, text, limit_rows=DEFAULT_ROWS, limit_func=DEFAULT_FUNC):
    """纯函数：一段文本 → {lines, max_func, over:[原因]}。不读磁盘、不碰 git。"""
    lines = text.splitlines()
    over = []
    if len(lines) > limit_rows:
        over.append("行数 %d > %d" % (len(lines), limit_rows))
    blocks = (_py_blocks(lines) if path.endswith(".py")
              else _brace_blocks(lines, is_java=path.endswith(".java")))
    funcs = [n for _, n, c in blocks if c == "func"]
    n_class = sum(1 for _, _, c in blocks if c == "class")
    n_mod = sum(1 for _, _, c in blocks if c == "module")
    max_func = max(funcs, default=0)
    worst = "?"
    if funcs:
        worst = max([b for b in blocks if b[2] == "func"], key=lambda b: b[1])[0]
    if max_func > limit_func:
        over.append("函数长 %d > %d（最长：%s）" % (max_func, limit_func, worst[:40]))
    return {"lines": len(lines), "max_func": max_func, "over": over,
            "class_blocks": n_class, "module_blocks": n_mod}


def scan_face(paths, limit_rows=DEFAULT_ROWS, limit_func=DEFAULT_FUNC, reader=None):
    """纯函数：路径清单 → ({rel: scan_text 结果}, 超限清单)。reader 可注入（自检用合成文本）。"""
    reader = reader or (lambda p: (ROOT / p).read_text("utf-8", errors="replace"))
    res, over = {}, []
    for rel in paths:
        try:
            r = scan_text(rel, reader(rel), limit_rows, limit_func)
        except OSError as e:
            r = {"lines": 0, "max_func": 0, "over": ["读取失败：%s" % str(e)[:60]]}
        res[rel] = r
        if r["over"]:
            over.append(rel)
    over.sort(key=lambda p: (-res[p]["lines"], p))
    return res, over


def context_lines():
    """并列打印既有更严约束，避免「门更松所以通过」的误读。"""
    have_budget = (ROOT / "_test" / "size_budget_check.py").exists()
    return ("  既有更严约束：size_budget 逐文件字节预算=%s（%s）；行为 Core P0.8 函数 ≤50 行"
            "（本门 %d 行**更松**，只作趋势读数，函数长终审以 Core 为准）"
            % ("在册" if have_budget else "缺失", "逐文件 BUDGETS" if have_budget else "读不到",
               DEFAULT_FUNC))


def selftest():
    cases = []
    long_text = "\n".join("var x%d = %d;" % (i, i) for i in range(60))
    fn_text = "def f():\n" + "".join("    x += 1\n" for _ in range(160))   # 161 行 > 150 门
    big_fn_text = "def g():\n" + "".join("    x += 1\n" for _ in range(40))  # 41 行，须**不**判红
    # 1) 超限样本在 enforce 口径下必红
    r1 = scan_text("a.py", long_text + "\n" * 2100, DEFAULT_ROWS, DEFAULT_FUNC)
    cases.append(("反例 超长文件必报行数超限", any("行数" in o for o in r1["over"]), True))
    r2 = scan_text("a.py", fn_text, DEFAULT_ROWS, DEFAULT_FUNC)
    cases.append(("反例 超长函数必报函数超限", any("函数长" in o for o in r2["over"]), True))
    r2b = scan_text("a.py", big_fn_text, DEFAULT_ROWS, DEFAULT_FUNC)
    cases.append(("反例 未超限函数不得误报（41 行 < 150）", r2b["over"] == [], True))
    # 2) 等值边界不判红（> 而非 >=）
    r3 = scan_text("a.py", "\n".join("x=1" for _ in range(DEFAULT_ROWS)), DEFAULT_ROWS, DEFAULT_FUNC)
    cases.append(("边界 恰好等于上限不判红", r3["over"] == [], True))
    # 3) 变异腿：阈值放大后同一超限样本转绿 ⇒ 尺作用在被审对象上
    r4 = scan_text("a.py", long_text + "\n" * 2100, 5000, DEFAULT_FUNC)
    cases.append(("变异 阈值放大后行数超限消失", r4["over"] == [], True))
    r5 = scan_text("a.py", fn_text, DEFAULT_ROWS, 400)
    cases.append(("变异 阈值放大后函数超限消失", r5["over"] == [], True))
    # 4) 空输入不得判绿（rc=2 语义）
    res, over = scan_face([], reader=lambda p: "")
    cases.append(("边界 零文件不得产生任何结论", res == {} and over == [], True))
    cases.append(("边界 零文件必须被主流程判 UNVERIFIED", bool(res) is False, True))
    # 5) 注入 reader 的合成面能跑出超限清单（证明 scan_face 真在扫）
    res2, over2 = scan_face(["x.py"], reader=lambda p: long_text + "\n" * 2100)
    cases.append(("正例 合成面超限清单非空", len(over2) == 1, True))
    # 6) r94 分类腿：**类与 IIFE 模块包装不是函数**，不得进函数长排名；
    #    但它们的**内部**超长函数必须照常判红（否则这一改就把尺改成了摆设）
    java_cls = "public class Big {\n" + "".join("    private int f%d;\n" % i for i in range(300)) + "}\n"
    r6 = scan_text("A.java", java_cls, DEFAULT_ROWS, DEFAULT_FUNC)
    cases.append(("反例 Java 类 300 行不得判为函数超限", not any("函数长" in o for o in r6["over"]), True))
    java_m = ("public class B {\n    public void big() {\n"
              + "".join("        x += 1;\n" for _ in range(200)) + "    }\n}\n")
    r7 = scan_text("B.java", java_m, DEFAULT_ROWS, DEFAULT_FUNC)
    cases.append(("反例 Java 类**内**200 行方法必须判函数超限",
                  any("函数长" in o for o in r7["over"]), True))
    iife = ("window.M = (function () {\n    function inner() {\n"
            + "".join("        x += 1;\n" for _ in range(200))
            + "    }\n    return { inner: inner };\n})();\n")
    r8 = scan_text("m.js", iife, DEFAULT_ROWS, DEFAULT_FUNC)
    cases.append(("反例 JS IIFE 包装本身不得判函数超限",
                  not any("函数长 30" in o for o in r8["over"]), True))
    cases.append(("反例 JS IIFE **内部**200 行函数必须判函数超限（嵌套块不再漏测）",
                  any("函数长" in o for o in r8["over"]), True))
    py_cls = "class C:\n" + "".join("    x%d = %d\n" % (i, i) for i in range(300))
    r9 = scan_text("c.py", py_cls, DEFAULT_ROWS, DEFAULT_FUNC)
    cases.append(("反例 Python 类 300 行不得判为函数超限",
                  not any("函数长" in o for o in r9["over"]), True))
    # 7) r94 接线自证变异腿：把电池条目里的 `--enforce` 摘掉 ⇒ 接线判否（门有门但没牙）
    w_ok, note_ok = wiring_report()
    cases.append(("接线 当前电池条目带 --enforce", w_ok is True, True))
    src = (ROOT / "_test" / "run_all_suites.py").read_text("utf-8", errors="replace")
    mangled = src.replace('"loc_guard", [sys.executable, "_test/loc_guard_check.py", "--enforce"]',
                          '"loc_guard", [sys.executable, "_test/loc_guard_check.py"]')
    import tempfile as _tf
    _orig = (ROOT / "_test" / "run_all_suites.py")
    try:
        _bak = _orig.read_bytes()
        _orig.write_text(mangled, encoding="utf-8")
        w_bad, _ = wiring_report()
    finally:
        _orig.write_bytes(_bak)
    cases.append(("变异 摘掉 --enforce 后接线必须判否（门有门但没牙）", w_bad is False, True))
    cases.append(("变异 只动了一处，文件其余内容不变（防误伤真面）",
                  _bak.decode("utf-8").count("loc_guard") == src.count("loc_guard"), True))
    bad = [n for n, got, want in cases if got != want]
    print("LOC-SELFTEST-%s（%d/%d 条）" % ("PASS" if not bad else "FAIL: " + "; ".join(bad),
                                           len(cases) - len(bad), len(cases)))
    return 1 if bad else 0


def wiring_report():
    """接线自证：电池 SUITES 里的 loc_guard 条目**必须带 `--enforce`**。

    为什么需要这一条（r94 一手）：本门从 report-only 切到 enforce 的那一刻，它的判红能力
    就**完全取决于电池里那一条命令行**。若有人日后把 `--enforce` 删掉，门还在跑、还印读数、
    rc 恒 0 —— 于是「有门」与「门有牙」再次分家（与 r78「有配置≠有门」同族，只是这次发生在自家身上）。
    故 enforce 模式必须自己盯着自己那行接线。
    """
    try:
        src = (ROOT / "_test" / "run_all_suites.py").read_text("utf-8", errors="replace")
    except OSError as e:
        return None, "读不到 run_all_suites.py：%s" % str(e)[:60]
    rows = [ln.strip() for ln in src.splitlines() if '"loc_guard"' in ln]
    if not rows:
        return None, "电池里找不到 loc_guard 条目（门不在受理面上 ⇒ 不得记绿）"
    return any("--enforce" in r for r in rows), ("电池条目：%s" % " / ".join(rows))


def main():
    ap = argparse.ArgumentParser(description="行数/函数长守卫（默认 enforce；--report-only 只报不拦）")
    ap.add_argument("--report-only", action="store_true",
                    help="只报不拦（默认 enforce，有超限即 rc=1）—— r94 起超限已清零，门正式有牙")
    # 兼容：r94 把默认改成 enforce 之前，电池条目写的是 `--enforce`。若不认这个参数，
    # argparse 会以 rc=2 退出（实测：电池里 loc_guard 变 ENV-UNVERIFIED，门静默失声）。
    # 保留它为 no-op，让「显式写 --enforce」的历史条目与接线自检都继续成立。
    ap.add_argument("--enforce", action="store_true", help="兼容参数：现在默认就是 enforce（no-op）")
    ap.add_argument("--limit-rows", type=int, default=DEFAULT_ROWS)
    ap.add_argument("--limit-func", type=int, default=DEFAULT_FUNC)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--top", type=int, default=8, help="排行榜打印条数")
    args = ap.parse_args()
    if args.selftest:
        return selftest()

    try:
        paths = git_files()
    except Exception as e:
        print("LOC-UNVERIFIED: 取数面读不到（禁止把扫不到记成通过）：%s" % str(e)[:120])
        return 2
    if not paths:
        print("LOC-UNVERIFIED: 代码文件面为空（分母 0 不是通过）")
        return 2

    res, over = scan_face(paths, args.limit_rows, args.limit_func)
    n_lines = sum(r["lines"] for r in res.values())
    print("LOC 扫描面：%d 个代码文件（git HEAD 面，%s）｜合计 %d 行"
          % (len(res), "/".join(sorted(CODE_EXT))[:40] + "…", n_lines))
    print("  阈值：文件行数 ≤%d、函数长 ≤%d（对标 opensoul check:loc）｜模式：%s"
          % (args.limit_rows, args.limit_func, "report-only（只报不拦）" if args.report_only else "enforce（超限即红）"))
    n_cls = sum(r.get("class_blocks", 0) for r in res.values())
    n_mod = sum(r.get("module_blocks", 0) for r in res.values())
    print("  函数口径：只取 `func` 块；已排除 Java/JS **类 %d 个**与 IIFE **模块包装 %d 个**"
          "（它们是类型/模块容器，不是函数；但行数照常计入文件行数）" % (n_cls, n_mod))
    # 接线自证：enforce 模式下，本门必须确认电池里那一条真的带 --enforce（否则「有门」没「有牙」）
    wired, wire_note = wiring_report()
    print("  接线：%s（%s）" % ("enforce 已接线" if wired else ("未接线" if wired is False else "未验"),
                                wire_note))
    if not args.report_only and wired is not True:
        print("LOC-FAIL：接线未确认（enforce 模式必须确认电池条目带 --enforce）")
        return 2
    context_lines()
    if not over:
        print("LOC-PASS：无超限项")
        return 0
    print("超限 %d/%d 个文件（按行数降序取前 %d）：" % (len(over), len(res), max(0, args.top)))
    for rel in over[:max(0, args.top)]:
        r = res[rel]
        print("  ✗ %-58s 行=%-6d 最长函数=%-5d ｜ %s" % (rel, r["lines"], r["max_func"], "；".join(r["over"])))
    if len(over) > max(0, args.top):
        print("  …另有 %d 个超限文件未逐条打印（完整清单可加 --top 0 全量）" % (len(over) - max(0, args.top)))
    if not args.report_only:
        print("LOC-FAIL：%d 个文件超限（enforce 模式）" % len(over))
        return 1
    print("（report-only：本条不阻断电池，仅登记读数）")
    return 0


if __name__ == "__main__":
    sys.exit(main())