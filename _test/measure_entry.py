# -*- coding: utf-8 -*-
"""取数入口前置自证（r82 · 落地 r81 建议 5）——「跑尺之前先跑尺的尺」，并把红因归到**人**。

为什么需要它（r81 一手，不是假想需求）
------------------------------------------------
r81 那轮开局直接调 `_test/benchmark_metrics.py` 取 peers 七维读数，撞上第 1074 行少一个比较运算符
⇒ **整文件 SyntaxError**，`--cap-channel/--doc-perf/--quality-gates` 全部起不来（rc=1）。
当时盘面其实**有**这道闸（`repo_config_check` 的 G9 能点名坏尺与行号），问题是**顺序**：
拿尺的人没先跑闸，于是第一次撞到的是「我的命令挂了」，而不是「哪条判据红、红在谁身上」。
本轮再补一次同族实证：我给自己的 H6 夹具写 ls-tree 解析时，**夹具与解析器按同一个错误假设写**
⇒ `--selftest` 13 腿里自管全绿、真面 89 条全判废（见 对标分析报告 r82 §2 G7）。

它做什么（三步，缺一不可）
------------------------------------------------
1. **语法面**：对「本轮要跑的尺」逐件 `ast.parse`。坏件必须给出 `文件:行:列 + 错误原文`。
2. **归属面**：同一件再取 `git show HEAD:<path>` 解析一次 ——
   HEAD 能解析而工作树不能 ⇒ 判「**未入库改动把它写坏了**」（在途件持有），
   两边都不能 ⇒ 判「已入库的坏尺」（须立即修，且此前任何跑在主树上的读数不可信）。
   这一层是分叉点：只看第 1 步会写出「去修它」，而正确处置可能是「去找持有在途 hunk 的那一路」。
3. **口径面**：跑本仓既有的全量尺体检 `repo_config_check.py`（G9 import-safe + 解析得动），
   它的 rc 原样并进来 —— 不另写一套「什么算好尺」的标准（derive, not duplicate）。
4. **管道吞 rc 面**（r83 加）：扫全部已跟踪 `*.sh`，凡「命令替换里接了管道、随后又用 `$?` 取退出码」
   即判红 —— 那个 `rc` 是管道末端的，不是命令的。立此腿的代价：同一形制在本仓第三次复发，
   一次让 25 次远端删除失败全部隐形（`out=$(cmd 2>&1 | tail -1); rc=$?`）。

三态
------------------------------------------------
- rc=0 `MEASURE-ENTRY-PASS`：要跑的尺全部解析得动，且全量体检绿
- rc=1 `MEASURE-ENTRY-FAIL`：任一件解析失败或体检判红（**红因带归属**）
- rc=2 `MEASURE-ENTRY-UNVERIFIED`：git 不可用 / 目标文件不存在 ⇒ 归属面失明，不得读成「没问题」

用法
------------------------------------------------
    python _test/measure_entry.py                      # 默认面 = peers 尺全集（现读，不手抄）
    python _test/measure_entry.py _test/foo.py …       # 只验本轮要点名的那几件
    python _test/measure_entry.py --selftest           # 正例 + 三种坏形（含归属分叉）
"""
from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
FULL_FACE = "_test/repo_config_check.py"

# 形如 `out=$(cmd | tail -1)` 的命令替换赋值：括号内允许一层嵌套括号，够用且不吞分号
CAP_ASSIGN = re.compile(r"\w+=\$\((?:[^()]|\([^()]*\))*\)")


def pipe_rc_defects(text):
    """纯函数：找出「命令替换里接了管道，随后又用 `$?` 取退出码」的行。

    为什么算取数入口的前置缺陷：`out=$(cmd 2>&1 | tail -1); rc=$?` 里的 `rc` 是 **tail** 的，
    命令本身的退出码死在管道里 ⇒ 25 次远端删除全部失败而账面报「0 失败」（r83 本仓第三次同族复发）。
    返回 [(行号, 原文片段)]；单行形与跨行形（下一行才是 `rc=$?`）都算。
    """
    hits = []
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        m = CAP_ASSIGN.search(ln)
        if not m or "|" not in m.group(0):
            continue
        if "$?" in ln or (i + 1 < len(lines) and "$?" in lines[i + 1]):
            hits.append((i + 1, ln.strip()[:90]))
    return hits


def shell_faces():
    """取数面 = 已跟踪的 `*.sh`（分母由 git 现读，不手抄名单）；取不到给 (None, 原因)。"""
    r = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z", "--", "*.sh"], capture_output=True)
    if r.returncode != 0:
        return None, "git ls-files rc=%d" % r.returncode
    return sorted(p for p in r.stdout.decode("utf-8", "replace").split("\0") if p), None


def default_faces():
    """peers 取数尺的**现读**清单 = `_test/benchmark_metrics.py` + 全部 `peer_*_probe.py`。

    分母从目录现读而不是抄一份名单：新增探针若没人记得登记，就会出现「尺没人验、读数照用」的空档
    （与 `plan_pdf_coverage_check` 把分母取自大纲同一思路）。
    """
    out = [str(ROOT / "_test" / "benchmark_metrics.py")]
    out += [str(p) for p in sorted((ROOT / "_test").glob("peer_*_probe.py"))]
    return out


def head_blob(rel: str):
    """HEAD 里该路径的原文；返回 (text|None, 说明)。None = 取不到 ⇒ 归属面失明（不判绿）。"""
    try:
        r = subprocess.run(["git", "show", "HEAD:" + rel], cwd=str(ROOT),
                           capture_output=True, timeout=30)
    except Exception as exc:
        return None, "git 不可调用（%s）" % type(exc).__name__
    if r.returncode != 0:
        return None, "HEAD 无此路径（新文件，尚未经版本控制）"
    return r.stdout.decode("utf-8", "replace"), ""


def parse_error(text: str):
    """能解析返回 None；不能则返回 `行:列 + 原文`。"""
    try:
        ast.parse(text)
    except SyntaxError as e:
        return "%s:%s %s" % (e.lineno, e.offset or 0, e.msg)
    except Exception as e:  # 递归过深/编码等：一样是「这把尺起不来」
        return "0:0 %s: %s" % (type(e).__name__, e)
    return None


def classify(work_text, head_err):
    """纯判定：把工作树与 HEAD 两个读数归成一句话。分离出来是为了能离线夹测。"""
    work_err = parse_error(work_text) if work_text is not None else "文件不在盘上"
    if work_err is None:
        return "ok", None
    if head_err is None:
        return "broken-in-worktree", (
            "工作树坏而 HEAD 能解析 ⇒ **未入库改动把它写坏了**（在途持有者须自行收口；"
            "本轮不要替他人提交，也不要绕开它取数）｜%s" % work_err)
    if head_err.startswith("HEAD 无此路径"):
        return "broken-new-file", "新建尺且解析不过 ⇒ 提交前必须修｜%s" % work_err
    return "broken-in-head", (
        "HEAD 与工作树都解析不过 ⇒ **已入库的坏尺**：任何跑在树上的该路读数都不可信｜%s" % work_err)


def check(paths):
    """返回 (violations, unverified, 逐件读数行)。"""
    bad, unver, rows = [], [], []
    for p in paths:
        fp = Path(p)
        rel = fp.relative_to(ROOT).as_posix() if fp.is_absolute() and str(fp).startswith(str(ROOT)) else p
        try:
            work_text = (ROOT / rel).read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            unver.append("%s 读不出原文（%s）⇒ 该件未验，不算通过" % (rel, type(exc).__name__))
            continue
        head_text, head_why = head_blob(rel)
        head_err = None if head_text is None else parse_error(head_text)
        if head_text is None:
            unver.append("%s 归属面失明（%s）" % (rel, head_why))
        state, why = classify(work_text, head_err)
        if state == "ok":
            rows.append("  · %s 解析得动" % rel)
        else:
            bad.append("%s [%s] %s" % (rel, state, why))
    return bad, unver, rows


def run_face(paths, with_full=True):
    bad, unver, rows = check(paths)
    # 第 3 步：全量尺体检原样并入。这里**不解析**它的输出文本 —— 判据的 rc 才是结论，
    # 把「它印了什么」当成「它过了」是 R247 那一族（零命中/空输出被读成通过）。
    full_rc = None
    if with_full:
        try:
            full_rc = subprocess.run([sys.executable, FULL_FACE], cwd=str(ROOT),
                                     capture_output=True, text=True,
                                     encoding="utf-8", errors="replace", timeout=300).returncode
        except Exception as exc:
            unver.append("全量体检不可调用（%s）⇒ 口径面未验" % type(exc).__name__)
    # 第 4 步（r83）：管道吞 rc 静态腿 —— 退出码一旦经过管道就不是命令自己的。
    # 立此腿的一手代价见 交付物/对标分析报告-2026-09-30-r83.md §2 G7。
    shs, sh_err = shell_faces()
    shell_stat = "未验"
    if sh_err:
        unver.append("管道吞rc 腿取数面失明（%s）⇒ 不得读成「没有这种写法」" % sh_err)
    elif not shs:
        unver.append("管道吞rc 腿取到 0 个 .sh ⇒ 零输入不判绿")
    else:
        n_hit = 0
        for rel in shs:
            try:
                body = (ROOT / rel).read_text(encoding="utf-8", errors="replace")
            except Exception as exc:
                unver.append("%s 读不到（%s）⇒ 该件未验" % (rel, type(exc).__name__))
                continue
            for ln, snip in pipe_rc_defects(body):
                n_hit += 1
                bad.append("%s:%d 退出码死在管道里（`rc=$?` 取到的是管道末端的）：%s" % (rel, ln, snip))
        shell_stat = "扫 %d 件命中 %d" % (len(shs), n_hit)
    return bad, unver, rows, full_rc, shell_stat


def selftest():
    """正例 + 四种坏形；全部走合成文本，不碰真实判据（真实件由真面自己跑）。"""
    fails = []

    def ck(name, cond):
        if not cond:
            fails.append(name)

    good = "import os\nprint(os.name)\n"
    missing_op = "blind_cur[0][\"tree_error\"] \"boom\"\n"        # r81 那一形的最小复现
    deep_bad = "def f(:\n    pass\n"

    ck("①正例判 ok", classify(good, None) == ("ok", None))
    st, why = classify(missing_op, None)
    ck("②工作树坏而 HEAD 好 ⇒ 归到在途持有者 %s" % st,
       st == "broken-in-worktree" and "未入库改动" in why)
    st2, why2 = classify(deep_bad, parse_error(deep_bad))
    ck("③两边都坏 ⇒ 已入库的坏尺 %s" % st2, st2 == "broken-in-head" and "不可信" in why2)
    st3, why3 = classify(deep_bad, "HEAD 无此路径（新文件，尚未经版本控制）")
    ck("④新文件且坏 ⇒ 提交前必须修 %s" % st3, st3 == "broken-new-file")
    ck("⑤r81 原形必须被 parse_error 点名行号", parse_error(missing_op).startswith("1:"))
    ck("⑥正例不得被误报", parse_error(good) is None)
    # r83 第 4 步的腿：管道吞 rc 静态判据（正例 + 本轮真形 + 跨行形 + 零输入不判绿）
    clean_sh = "set -e\nOUT=$(git status --porcelain)\nrc=$?\necho \"$OUT rc=$rc\"\n"
    ck("⑧合规脚本不得误报（`$()` 里没有管道）", pipe_rc_defects(clean_sh) == [])
    real_sh = 'out=$(tcb hosting delete "$k" 2>&1 | tail -1); rc=$?\nif [ $rc -ne 0 ]; then :; fi\n'
    hits = pipe_rc_defects(real_sh)
    ck("⑨本轮真形必须被点名（含行号）%s" % hits, len(hits) == 1 and hits[0][0] == 1)
    ck("⑩跨行形也要抓到", len(pipe_rc_defects("o=$(a | b)\nrc=$?\n")) == 1)
    ck("⑪有管道但不取 `$?` 不算（它没在拿退出码下结论）",
       pipe_rc_defects("n=$(git ls-files | wc -l)\necho $n\n") == [])
    # 真面自证：默认清单里的每一件此刻必须解析得动（否则这条判据自己是坏的尺）
    real = run_face(default_faces(), with_full=False)
    ck("⑫run_face 的返回元数变了就必须同步改调用点（r82 A9 同族）", len(real) == 5)
    real_bad, real_unver, _rows, _rc, _stat = real
    ck("⑬真面默认清单全绿（坏 %d｜未验 %d）" % (len(real_bad), len(real_unver)),
       not real_bad and not real_unver)
    print("MEASURE-ENTRY-SELFTEST-%s（10 类文本桩 + 1 条元数钉 + 1 条真面自证｜管道腿=%s）"
          % ("PASS" if not fails else "FAIL: " + "; ".join(fails), _stat))
    return 1 if fails else 0


def main(argv):
    if "--selftest" in argv:
        return selftest()
    paths = [a for a in argv if not a.startswith("-")] or default_faces()
    bad, unver, rows, full_rc, shell_stat = run_face(paths)
    for r in rows:
        print(r)
    for b in bad:
        print("  ✗ " + b)
    for u in unver:
        print("  ? " + u)
    tail = "点名 %d 件｜解析坏 %d｜归属失明 %d｜管道吞rc %s｜全量体检 rc=%s" % (
        len(paths), len(bad), len(unver), shell_stat, "未跑" if full_rc is None else full_rc)
    if bad or (full_rc not in (None, 0)):
        print("MEASURE-ENTRY-FAIL: 尺没验过，禁止拿它的读数下结论（%s）" % tail)
        return 1
    if unver:
        print("MEASURE-ENTRY-UNVERIFIED: 零违规但 %d 件归属面失明（%s）" % (len(unver), tail))
        return 2
    print("MEASURE-ENTRY-PASS: 要跑的尺全部解析得动且归属清楚（%s）" % tail)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
