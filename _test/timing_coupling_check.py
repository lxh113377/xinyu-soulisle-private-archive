# -*- coding: utf-8 -*-
r"""timing_coupling_check.py — 「判据把成败押在机器时刻上」这一类的普查尺（r98 立）。

为什么现在才立（一手代价，不是假想需求）
------------------------------------------------
r96 连吃两条**同根**的 CI 红：
  ① `j4_memory` 的 `say()` 用 `wait_for_timeout(8000)` 押服务端落库时刻 —— 本机实测落库
     1.65s（4.8 倍余量）所以一直绿，CI 慢过 8s 就判红；
  ② `data_rights` 先 `stats()` 再 `exportAll()` 跨时刻取数 —— 本机快的时候恰好相等所以一直绿。
r96 的处置是把这两处升到公共件 `_test/settle_wait.py`，**但同一个类还剩多少处没人普查** ——
那正是本仓在册纪律「修类不修例」要求的另一半。本轮实测：`_test/*.py` 里 AST 现读
`wait_for_timeout` **140 处 / 30 件**，而接进 `settle_wait` 的只有 2 件。

这条尺说什么、不说什么
------------------------------------------------
它只断言**形状**，不断言意图：`定长等待 → 紧接着取数 → 那个数被决策消费` 是一个可 AST 判定的
事实；「这里等错了」不是它的措辞，也不可能是（判据无法知道被等对象什么时候算好）。
红**只由棘轮产生**：`C1_HARD > 基线` 即红 ⇒ 它自称的是「这个形状还剩这么多处」，
不是「这些地方是 bug」。

分母为什么不许由 grep 得出（本件的立身之本）
------------------------------------------------
`grep -rho wait_for_timeout _test/*.py | wc -l` = **142 处 / 31 件**，而 AST 现读 =
**140 处 / 30 件**。多出的 2 处在注释与 docstring 里。按 grep 的面钉基线 = 给尺本身埋一个
「改注释就翻面」的假红 ⇒ 门面行把两个读数**同时印出来**，换尺的人看得见差值。

用法
------------------------------------------------
    python _test/timing_coupling_check.py                 # 普查（进电池：纯静态，零浏览器）
    python _test/timing_coupling_check.py --baseline 27   # 演习口：抬高要求 ⇒ 必须判红
    python _test/timing_coupling_check.py --only browser_check.py
    python _test/timing_coupling_check.py --json <path>   # 逐条落盘
    python _test/timing_coupling_check.py --selftest      # 正例/反例/变异/盲区/恒等式/截断
退出码：0=各腿绿 1=C1_HARD 超基线 / 有解析失败件（被吞的件会在审计里隐身，按判红处理）
        2=**分桶恒等式不成立** 或 分母为 0 ⇒ UNVERIFIED，既不判绿也不判红
"""
import argparse
import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_DIR = ROOT / "_test"
RUNNER = TEST_DIR / "run_all_suites.py"
SELF_NAMES = {"timing_coupling_check.py"}

# 定长等待之后**紧接**的这些调用＝在取被等对象的状态。闭集枚举，命中与否是事实不是猜测。
READ_ATTRS = frozenset({
    "evaluate", "inner_text", "text_content", "content", "title", "get_attribute",
    "eval_on_selector", "eval_on_selector_all", "input_value", "is_visible", "count",
    "http", "stats", "all",
})
# 真正的「完成态信号」等待：等到的是被等对象到场，而不是给一段时间。
DONE_ATTRS = frozenset({
    "wait_for_function", "wait_for_selector", "wait_for_load_state", "wait_for_url",
    "wait_quiescent", "same_reading", "expect",
})
# 消费取数结果的决策函数名（本仓判据的两种写法都覆盖：check(...) 与 ck(...)/ok(...)）
CHECK_NAMES = frozenset({"check", "ck", "ok", "fail", "expect", "record"})
FOLD_LIMIT = 110            # run_all_suites.py:804 的 line[:110]
BUCKETS = ("C1_HARD", "C_GUARDED", "READ_NO_DECIDE", "NEXT_NO_READ", "POLL", "LAST", "VARLEN")


def _attr_name(node):
    """被调用的名字。`ast.Name` 的标识在 `.id` 上（`.name` 是 ast.Attribute 才有的属性）——
    第一版读成 `f.name` ⇒ 任何裸函数调用（`evaluate(...)` / `check(...)` 这类无接收者的写法）
    一进来就抛 AttributeError，整件 rc=1。实测该形态在 _test/*.py 里真实存在，故必须两分支都真读。"""
    f = getattr(node, "func", None)
    if isinstance(f, ast.Attribute):
        return f.attr
    if isinstance(f, ast.Name):
        return f.id
    return None


def _is_read(node):
    return any(_attr_name(x) in READ_ATTRS for x in ast.walk(node) if isinstance(x, ast.Call))


def _has_done_wait(node):
    return any(_attr_name(x) in DONE_ATTRS for x in ast.walk(node) if isinstance(x, ast.Call))


def _const_int(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(node.value, bool):
        return node.value
    return None


def _uses(node, names):
    if node is None or not names:
        return False
    return any(isinstance(x, ast.Name) and x.id in names for x in ast.walk(node))


def _read_names(stmt):
    """该语句里由「取数调用」直接绑定的名字（含 tuple unpack）。"""
    names = set()
    for x in ast.walk(stmt):
        if isinstance(x, ast.Assign) and _is_read(x.value):
            names |= {n.id for n in ast.walk(x) if isinstance(n, ast.Name)
                      and isinstance(n.ctx, ast.Store)}
        elif isinstance(x, (ast.AnnAssign, ast.AugAssign)) and getattr(x, "value", None) is not None \
                and _is_read(x.value) and isinstance(x.target, ast.Name):
            names.add(x.target.id)
    return names


def _blocks(tree):
    """把**所有**语句块摊成一条条有序清单（模块体 + 每个函数体 + 每个 If/With/Try/循环体）。

    为什么必须这样：第一版按「函数体顶层语句」遍历 ⇒ `browser_check.py` 那种
    「模块级 `with sync_playwright() as p:` 里一路嵌到底」的文件整段被静默丢掉，
    总数从 140 掉到 22。**盲区读成零**是本仓在册最贵的一族错误，这条是它的一手现场。"""
    out = []
    for node in ast.walk(tree):
        for field in ("body", "orelse", "finalbody"):
            seq = getattr(node, field, None)
            if isinstance(seq, list) and seq and all(isinstance(x, ast.stmt) for x in seq):
                out.append(sorted(seq, key=lambda s: s.lineno))
        for h in getattr(node, "handlers", None) or []:
            if h.body:
                out.append(sorted(h.body, key=lambda s: s.lineno))
    return out


def _locate(blocks, stmt):
    for b in blocks:
        for i, s in enumerate(b):
            if s is stmt:
                return b, i
    return None, None


def _loop_stmt_ids(tree):
    """循环体（含其嵌套体）里的语句 id 集合 ⇒ 判 POLL。

    轮询里的 250ms 不是「押一个完成时刻」，它每轮都重新问一次状态 —— 那是等信号的形状。"""
    inside = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
            inside |= {id(s) for s in ast.walk(node)}
    return inside


def _tainted_decision(stmts, idx, read_names):
    """从 idx 往后扫同一块：返回 (决策点下标 or None, 中间有无完成态等待, 决策形态名)。

    污点是**传递**的：`msgs = pg.evaluate(...)` 之后断言读的是 `last = msgs[-1]`。
    一跳式污点在 `browser_check.py:49→147` 这个真实形状上漏报，而漏报会被下一轮读成
    「其余都干净」。"""
    tainted = set(read_names)
    between_wait = False
    for j in range(idx + 1, len(stmts)):
        s = stmts[j]
        if _has_done_wait(s):
            between_wait = True
        if isinstance(s, ast.Assert) and _uses(s.test, tainted):
            return j, between_wait, "assert"
        if isinstance(s, ast.If) and _uses(s.test, tainted):
            return j, between_wait, "if"
        for x in ast.walk(s):
            if isinstance(x, ast.Call):
                fn = _attr_name(x)
                if fn in CHECK_NAMES and any(_uses(a, tainted) for a in x.args):
                    return j, between_wait, fn
                if fn in ("append", "extend") and any(_uses(a, tainted) for a in x.args):
                    return j, between_wait, fn
        for x in ast.walk(s):
            if isinstance(x, ast.Assign) and _uses(x.value, tainted):
                tainted |= {n.id for n in ast.walk(x) if isinstance(n, ast.Name)
                            and isinstance(n.ctx, ast.Store)}
            elif isinstance(x, (ast.AnnAssign, ast.AugAssign)) \
                    and getattr(x, "value", None) is not None and _uses(x.value, tainted) \
                    and isinstance(x.target, ast.Name):
                tainted.add(x.target.id)
    return None, between_wait, ""


def classify(text, name=""):
    """单件源码 → (逐条记录, 自报调用总数, 解析错误串 or None)。纯函数，夹具不造文件。"""
    recs = []
    try:
        tree = ast.parse(text)
    except SyntaxError as e:
        return recs, 0, "SyntaxError line %s: %s" % (e.lineno, e.msg)
    blocks = _blocks(tree)
    loops = _loop_stmt_ids(tree)
    total = 0
    for stmt in ast.walk(tree):
        if not isinstance(stmt, ast.Expr):
            continue
        call = stmt.value
        if not (isinstance(call, ast.Call) and _attr_name(call) == "wait_for_timeout"):
            continue
        total += 1
        ms = _const_int(call.args[0]) if call.args else None
        blk, idx = _locate(blocks, stmt)
        nxt = blocks_next(blk, idx) if blk is not None else None
        if blk is None:
            bucket, note = "POLL", "定位不到所属语句块（不该发生，出声不静默）"
        elif ms is None:
            bucket, note = "VARLEN", "定长实参不是字面整数"
        elif id(stmt) in loops:
            bucket, note = "POLL", "在循环体里（轮询形状）"
        elif nxt is None:
            bucket, note = "LAST", "本块最后一条，后面没有取数"
        elif not _is_read(nxt):
            bucket, note = "NEXT_NO_READ", "下一条不取数"
        else:
            j, guarded, how = _tainted_decision(blk, idx, _read_names(nxt))
            if j is None:
                bucket, note = "READ_NO_DECIDE", "取到数但本块内没被决策消费"
            elif guarded:
                bucket, note = "C_GUARDED", "读与决策之间隔着完成态等待(%s)" % how
            else:
                bucket, note = "C1_HARD", "定长→取数→%s 立刻消费" % how
        recs.append({"file": name, "line": stmt.lineno, "ms": ms, "bucket": bucket, "note": note})
    return recs, total, None


def blocks_next(blk, idx):
    return blk[idx + 1] if blk is not None and idx + 1 < len(blk) else None


def battery_face():
    """哪些 `_test/*.py` 在电池里有执行位。取不到 ⇒ 返回 None，由调用方标未验（**不得**读成空集）。"""
    try:
        src = RUNNER.read_text(encoding="utf-8")
    except Exception:                                      # noqa: BLE001
        return None
    return set(re.findall(r'"_test/([A-Za-z0-9_]+\.py)"', src))


def scan_dir(dir_path, only=None):
    rows, totals, broken, unreadable = [], {}, [], []
    in_battery = battery_face()
    for p in sorted(dir_path.glob("*.py")):
        if p.name in SELF_NAMES:
            continue
        if only and p.name not in only:
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except Exception as e:                             # noqa: BLE001
            unreadable.append("%s(%s)" % (p.name, type(e).__name__))
            continue
        recs, total, err = classify(text, p.name)
        if err:
            broken.append("%s: %s" % (p.name, err))
            continue
        totals[p.name] = total
        for r in recs:
            r["in_battery"] = (p.name in in_battery) if in_battery is not None else None
        rows.extend(recs)
    return rows, totals, broken, unreadable, in_battery


def tally(rows):
    c = {b: 0 for b in BUCKETS}
    for r in rows:
        c[r["bucket"]] = c.get(r["bucket"], 0) + 1
    return c


def face_line(total_calls, files_with, hard, hard_bat, baseline, bucketed,
              guarded, poll, is_red, battery_known, ranked):
    """门面行生成器（纯函数，main 与 selftest 共用同一实现）。

    为什么必须是函数而不是 main 里的一段拼装：r98 第一版的门面行 187 字符，
    超 `run_all_suites.py:804` 的 `line[:110]` ⇒ 受理面上基线/恒等式/C1 计数全部不存在。
    当时若把断言写在 selftest 里对着**字面量**跑，改生成代码它不会红 ⇒ 装饰腿。
    现在 selftest 调的是这个函数本身，改这里它立刻咬。"""
    line = ("TIMING-COUPLING-%s: 定长%d处/%d件 C1=%d(电池%d) 基线%d 恒等式%d==%d G=%d P=%d"
            % ("FAIL" if is_red else "PASS", total_calls, files_with, hard, hard_bat,
               baseline, bucketed, total_calls, guarded, poll))
    if not battery_known:
        line += " 电池面未取到"
    spill = []
    for name, cnt in ranked:
        piece = " 最集中=%s:%d" % (name[:-3], cnt)
        if len(line) + len(piece) <= FOLD_LIMIT:
            line += piece
        else:
            spill = ["%s×%d" % (n[:-3], v) for n, v in ranked]
            break
    return line, spill


def selftest():
    """正例 / 四种「不得升格」反例 / 传递污点 / 恒等式 / 变异 / 盲区 / 截断，逐条有名字。"""
    bad, n = [], 0

    def expect(label, cond):
        nonlocal n
        n += 1
        if not cond:
            bad.append(label)

    C1 = ("def run(pg):\n"
          "    pg.wait_for_timeout(8000)\n"
          "    n = pg.evaluate('() => 1')\n"
          "    assert n >= 1\n")
    NOREAD = ("def run(pg):\n"
              "    pg.wait_for_timeout(400)\n"
              "    pg.click('#x')\n")
    PRINT_ONLY = ("def run(pg):\n"
                  "    pg.wait_for_timeout(800)\n"
                  "    n = pg.evaluate('() => 1')\n"
                  "    print(n)\n")
    LOOP = ("def run(pg):\n"
            "    for _ in range(40):\n"
            "        cls = pg.get_attribute('class')\n"
            "        if cls:\n"
            "            break\n"
            "        pg.wait_for_timeout(250)\n")
    GUARD = ("def run(pg):\n"
             "    pg.wait_for_timeout(300)\n"
             "    n = pg.evaluate('() => 1')\n"
             "    pg.wait_for_selector('#x')\n"
             "    assert n >= 1\n")
    TRANSIT = ("def run(pg):\n"
               "    pg.wait_for_timeout(600)\n"
               "    msgs = pg.evaluate('() => [1]')\n"
               "    last = msgs[-1]\n"
               "    assert last\n")
    VARLEN = ("def run(pg, ms):\n"
              "    pg.wait_for_timeout(ms)\n"
              "    n = pg.evaluate('() => 1')\n"
              "    assert n\n")
    TAIL = ("def run(pg):\n"
            "    pg.click('#x')\n"
            "    pg.wait_for_timeout(200)\n")

    def bucket_of(src):
        return classify(src, "f.py")[0][0]["bucket"]

    expect("正例 定长→取数→assert 判 C1_HARD", bucket_of(C1) == "C1_HARD")
    expect("反例 取数只被 print 消费 ⇒ 不得升格成 C1_HARD",
           bucket_of(PRINT_ONLY) == "READ_NO_DECIDE")
    expect("反例 轮询循环里的 250ms 归 POLL（每轮重新问状态，不是押时刻）",
           bucket_of(LOOP) == "POLL")
    expect("反例 读与决策之间有完成态等待 ⇒ C_GUARDED 不算硬耦合",
           bucket_of(GUARD) == "C_GUARDED")
    expect("反例 下一条不取数 ⇒ NEXT_NO_READ", bucket_of(NOREAD) == "NEXT_NO_READ")
    expect("反例 块尾的等待 ⇒ LAST（后面没有取数可谈耦合）", bucket_of(TAIL) == "LAST")
    expect("传递污点 断言读的是派生名 ⇒ 必须抓到 C1_HARD（一跳式会漏报）",
           bucket_of(TRANSIT) == "C1_HARD")
    expect("VARLEN 实参是变量 ⇒ 单独一桶，不判红只计数", bucket_of(VARLEN) == "VARLEN")

    fixtures = [("C1", C1), ("PRINT", PRINT_ONLY), ("LOOP", LOOP), ("GUARD", GUARD),
                ("TRANSIT", TRANSIT), ("VARLEN", VARLEN), ("NOREAD", NOREAD), ("TAIL", TAIL)]
    for label, src in fixtures:
        recs, tot, _e = classify(src, "f.py")
        expect("恒等式 %s：记录数(%d)==自报调用总数(%d)" % (label, len(recs), tot), len(recs) == tot)
        expect("  且 %s 的桶落在已定义集合里（不许造出第 8 桶把恒等式蒙圆）" % label,
               all(r["bucket"] in BUCKETS for r in recs))

    keep = globals()["_is_read"]
    globals()["_is_read"] = lambda node: True
    risen = bucket_of(NOREAD)
    globals()["_is_read"] = keep
    expect("变异体 _is_read 恒真 ⇒ NOREAD 被升格（证明那条腿在咬，不是装饰）",
           risen != "NEXT_NO_READ")
    expect("  还原后同一输入回到 NEXT_NO_READ（动的是尺不是期望值）",
           bucket_of(NOREAD) == "NEXT_NO_READ")

    _r, _t, err = classify("def broken(:\n    pass\n", "bad.py")
    expect("盲区腿 解析失败 ⇒ 必须返回错误串并进红因（不得 except-continue 当 0 条）", bool(err))

    # 门面行封口腿（r98 一手代价）。run_all_suites.py:804 是 `line[:110]`：
    # 超线的部分在受理面上**根本不存在**，于是「基线/恒等式/C1 计数」全丢，
    # 本件在 CI 上只剩一个 PASS 词 —— 正是本仓在册教训 r40b，只是发生在自己身上。
    # 断言调的是 `face_line`（真生成器），不是字面量 ⇒ 改生成代码它会红。
    RANKED = [("ux_guards_check.py", 7), ("rescan_shots_check.py", 3), ("data_rights_check.py", 2),
              ("clean_clone_check.py", 1), ("memory_recall_check.py", 1),
              ("offline_shell_check.py", 1), ("public_check.py", 1)]
    real, spill = face_line(131, 29, 16, 13, 28, 131, 0, 25, False, True, RANKED)
    expect("门面行实测形态 %d 字符 ≤ 截断线 %d" % (len(real), FOLD_LIMIT),
           len(real) <= FOLD_LIMIT)
    expect("门面行自带基线与恒等式两个数（缺任一 ⇒ 受理面无法判断棘轮是否动过）",
           ("基线" in real) and ("恒等式" in real))
    expect("装不下的分布走续行而不是被静默丢掉", bool(spill))
    # 反例腿：r98 第一版的拼装形态（实测 187 字符）必须超线 ⇒ 证明这条腿会咬。
    fat = ("TIMING-COUPLING-PASS: 定长等待 131 处/29 件｜C1 硬耦合 16（电池面 13）｜GUARDED 0"
           "｜POLL 25｜基线 28｜恒等式 131==131｜最集中=ux_guards_check.py:7,rescan_shots_check.py:3")
    expect("反例 第一版门面行形态 %d 字符 > 截断线 ⇒ 这条腿不是恒真" % len(fat),
           len(fat) > FOLD_LIMIT)
    # 红态门面行同样要装得下（红时才最需要读数，而红因走 fold_detail 续行）
    redline, _s2 = face_line(131, 29, 16, 13, 5, 131, 0, 25, True, True, RANKED)
    expect("红态门面行 %d 字符 ≤ 截断线" % len(redline), len(redline) <= FOLD_LIMIT)

    for x in bad:
        print("  不符: " + x)
    print("TIMING-COUPLING-SELFTEST-%s（%d/%d 条）" % ("FAIL" if bad else "PASS", n - len(bad), n))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", type=int, default=28,
                    help="C1_HARD 棘轮上界（r98 取实测值钉住，只降不升）")
    ap.add_argument("--only", default="", help="逗号分隔的文件名子集（定位/演习用）")
    ap.add_argument("--json", default="")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()

    only = {x.strip() for x in a.only.split(",") if x.strip()} or None
    rows, totals, broken, unreadable, in_battery = scan_dir(TEST_DIR, only)
    total_calls = sum(totals.values())
    files_with = sum(1 for v in totals.values() if v)
    c = tally(rows)
    bucketed = sum(c[b] for b in c)
    if not rows and not total_calls:
        print("TIMING-COUPLING-UNVERIFIED: 分母为 0（现读没有 wait_for_timeout ≠ 全类已清）")
        return 2
    if bucketed != total_calls or set(c) - set(BUCKETS):
        print("TIMING-COUPLING-UNVERIFIED: 分桶恒等式 %d != 自报总数 %d（多出桶=%s）"
              "⇒ 有一类落进了没定义的桶，不判绿也不判红"
              % (bucketed, total_calls, sorted(set(c) - set(BUCKETS))))
        return 2
    hard = c["C1_HARD"]
    hard_bat = sum(1 for r in rows if r["bucket"] == "C1_HARD" and r.get("in_battery"))
    red = []
    if hard > a.baseline:
        red.append("C1_HARD %d > 基线 %d" % (hard, a.baseline))
    if broken:
        red.append("SYNTAX %d 件" % len(broken))
    if unreadable:
        red.append("读不到 %d 件" % len(unreadable))
    top = {}
    for r in rows:
        if r["bucket"] == "C1_HARD":
            top[r["file"]] = top.get(r["file"], 0) + 1
    ranked = sorted(top.items(), key=lambda x: -x[1])

    # 门面行由 `face_line` 生成（与 selftest 同一实现，杜绝两处拼装分叉）。
    # 红因走 `- ` 续行，由 `run_all_suites.py:408-414` 的 fold_detail 在 rc≠0 时带出。
    line, spill = face_line(total_calls, files_with, hard, hard_bat, a.baseline, bucketed,
                            c["C_GUARDED"], c["POLL"], bool(red), in_battery is not None, ranked)
    if len(line) > FOLD_LIMIT:
        print("TIMING-COUPLING-NOTE: 门面行 %d 字符 > 电池截断线 %d ⇒ 尾部读数在受理面上不存在"
              % (len(line), FOLD_LIMIT))
    print(line)
    # 续行一律排在门面行**之后**：fold_detail 取的是「命中行之后 5 行内的 `-` 开头者」，
    # 印在门面行前面它看不见，红因就只剩半句。
    for b in broken[:8]:
        print("  - 红-解析失败(隐身件风险): " + b)
    if red:
        print("  - 红因=" + ",".join(red))
    if spill:
        print("  - C1_HARD 分布(门面行已满): " + "，".join(spill[:14]))
    if a.json:
        Path(a.json).write_bytes(json.dumps(
            {"baseline": a.baseline, "total_calls": total_calls, "files": files_with,
             "buckets": c, "c1_hard_battery": hard_bat, "red": red,
             "grep_face_note": "grep 面为 142 处/31 件（含注释与 docstring），本尺取 AST 面",
             "battery_face": "取到" if in_battery is not None else "未取到",
             "worst": top, "records": rows}, ensure_ascii=False, indent=1).encode("utf-8"))
    return 1 if red else 0


if __name__ == "__main__":
    sys.exit(main())
