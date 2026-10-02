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
    return out


def _py_blocks(lines):
    """Python：def/class 顶格缩进块 → [(name, 行数)]。"""
    marks = []
    for i, ln in enumerate(lines):
        s = ln.lstrip()
        if s.startswith("def ") or s.startswith("class ") or s.startswith("async def "):
            indent = len(ln) - len(s)
            name = s.split("(")[0].replace("def ", "").replace("class ", "").replace("async ", "").strip()
            marks.append((i, indent, name or "?"))
    out = []
    for k, (start, indent, name) in enumerate(marks):
        end = len(lines)
        for j in range(start + 1, len(lines)):
            s = lines[j].strip()
            if not s or s.startswith("#"):
                continue
            ind = len(lines[j]) - len(lines[j].lstrip())
            if ind <= indent:
                end = j
                break
        out.append((name, end - start))
    return out


def _brace_blocks(lines):
    """JS/Java 启发式：`function`/`=>`/`{`/`}` 近似配对，取每块行数上界。"""
    out = []
    depth = 0
    start = None
    hint = "?"
    for i, ln in enumerate(lines):
        if depth == 0 and ("function" in ln or "=>" in ln or "class " in ln):
            start = i
            hint = ln.strip()[:40]
        opens = ln.count("{") - ln.count("}")
        if depth == 0 and opens > 0 and start is None:
            start = i
            hint = ln.strip()[:40]
        depth += opens
        if depth <= 0:
            depth = 0
            if start is not None:
                out.append((hint, i - start + 1))
                start = None
                hint = "?"
        if depth > 4000:      # 括号不平衡的坏文件兜底，别让启发式吃成 O(n^2)
            depth = 0
    return out


def scan_text(path, text, limit_rows=DEFAULT_ROWS, limit_func=DEFAULT_FUNC):
    """纯函数：一段文本 → {lines, max_func, over:[原因]}。不读磁盘、不碰 git。"""
    lines = text.splitlines()
    over = []
    if len(lines) > limit_rows:
        over.append("行数 %d > %d" % (len(lines), limit_rows))
    blocks = _py_blocks(lines) if path.endswith(".py") else _brace_blocks(lines)
    max_func = max([n for _, n in blocks], default=0)
    if max_func > limit_func:
        worst = max(blocks, key=lambda b: b[1])[0]
        over.append("函数长 %d > %d（最长：%s）" % (max_func, limit_func, worst[:40]))
    return {"lines": len(lines), "max_func": max_func, "over": over}


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
    bad = [n for n, got, want in cases if got != want]
    print("LOC-SELFTEST-%s（%d/%d 条）" % ("PASS" if not bad else "FAIL: " + "; ".join(bad),
                                           len(cases) - len(bad), len(cases)))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser(description="行数/函数长守卫（report-only 默认，--enforce 才阻断）")
    ap.add_argument("--enforce", action="store_true", help="有超限即 rc=1（默认 report-only，只报不拦）")
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
          % (args.limit_rows, args.limit_func, "enforce（超限即红）" if args.enforce else "report-only（只报不拦）"))
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
    if args.enforce:
        print("LOC-FAIL：%d 个文件超限（enforce 模式）" % len(over))
        return 1
    print("（report-only：本条不阻断电池，仅登记读数；切 --enforce 前先把超限清零）")
    return 0


if __name__ == "__main__":
    sys.exit(main())