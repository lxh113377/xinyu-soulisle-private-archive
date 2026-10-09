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


def _store_names(target):
    """赋值左侧被绑定的名字，含**容器写入**的根名。

    `res["ui_count"] = pg.evaluate(...)` 里 `res` 是 Load 上下文，旧口径取不到它 ⇒
    取到的数明明进了 `res`、`res` 又被 return 出去，本尺却看不见这条手递手（r101 实测
    `storage_resilience_check.py:176` 就是这么差点漏掉的）。元组解包逐元素递归。"""
    names = set()
    if isinstance(target, ast.Name):
        names.add(target.id)
    elif isinstance(target, ast.Starred):
        names |= _store_names(target.value)
    elif isinstance(target, (ast.Tuple, ast.List)):
        for el in target.elts:
            names |= _store_names(el)
    elif isinstance(target, (ast.Subscript, ast.Attribute)):
        base = target
        while isinstance(base, (ast.Subscript, ast.Attribute)):
            base = base.value
        if isinstance(base, ast.Name):
            names.add(base.id)
    return names


def _read_names(stmt):
    """该语句里由「取数调用」绑定的名字（含 tuple unpack 与容器写入）。"""
    names = set()
    for x in ast.walk(stmt):
        if isinstance(x, ast.Assign) and _is_read(x.value):
            for t in x.targets:
                names |= _store_names(t)
        elif isinstance(x, (ast.AnnAssign, ast.AugAssign)) and getattr(x, "value", None) is not None \
                and _is_read(x.value):
            names |= _store_names(x.target)
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
    「其余都干净」。

    `return` 只算**交接**不算决策（r101）：形态名回 "return" 由调用方去查返回值在**调用点**
    有没有被消费。把它直接当决策等于发第二条降噪通道 —— 任何函数只要在末尾 `return` 一下
    就能把定长等待洗成"已消费"，与 r100 抓到的「提取函数即降噪」是同一条病换个口。"""
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
        if isinstance(s, ast.Return) and _uses(s.value, tainted):
            return j, between_wait, "return"
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


def owner_map(tree):
    """每个节点的 id → 所属主体（函数名；模块体为 None）。嵌套函数按**最内层**归属。

    `def` 语句本身算外层主体的语句（否则递归找调用点时它不在任何 flat 清单里）。"""
    own = {}

    def visit(node, cur):
        for ch in ast.iter_child_nodes(node):
            if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)):
                own[id(ch)] = cur
                visit(ch, ch.name)
            else:
                own[id(ch)] = cur
                visit(ch, cur)
    visit(tree, None)
    return own


def _not_a_flow_body(node):
    return isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda))


def linear_stmts(node):
    """该语句自身 + 其中**随它一起执行**的语句（if 的两个分支都算「可能执行」）。

    遇函数/类定义即止：`def` 体在定义点不执行，把它的内容算进后续流就是把另一个主体的
    消费当成了这里的消费。"""
    out = []

    def walk(n):
        out.append(n)
        for field in ("body", "orelse", "finalbody"):
            seq = getattr(n, field, None)
            if isinstance(seq, list):
                for s in seq:
                    if isinstance(s, ast.stmt) and not _not_a_flow_body(s):
                        walk(s)
        for h in getattr(n, "handlers", None) or []:
            for s in getattr(h, "body", []) or []:
                if isinstance(s, ast.stmt) and not _not_a_flow_body(s):
                    walk(s)
        if getattr(n, "body", None) is not None and isinstance(n.body, ast.stmt) \
                and not _not_a_flow_body(n.body):
            walk(n.body)
    walk(node)
    return out


def flow_ctx(tree, blocks):
    """(语句→(所属块清单, 序号) 索引) 与 (块清单 id → 拥有它的节点)。"""
    idx_map, list_owner = {}, {}
    for node in ast.walk(tree):
        for field in ("body", "orelse", "finalbody"):
            seq = getattr(node, field, None)
            if isinstance(seq, list) and seq and all(isinstance(x, ast.stmt) for x in seq):
                list_owner[id(seq)] = node
                for i, s in enumerate(seq):
                    idx_map[id(s)] = (seq, i)
        for h in getattr(node, "handlers", None) or []:
            if h.body:
                list_owner[id(h.body)] = node
                for i, s in enumerate(h.body):
                    idx_map[id(s)] = (h.body, i)
    return idx_map, list_owner


def forward_flow(stmt, idx_map, list_owner):
    """stmt 之后**仍可能顺序执行**的语句清单（沿块树上溯取后续兄弟，排除互斥分支与嵌套函数体）。

    为什么不能用 lineno 摊平（r101 一手）：第一版按「同主体、lineno 更大」续扫，实测把平行分支
    （同一 `if/else` 的另一侧等）的消费也算成 C1_HARD ⇒ 分子从 6 虚涨到 27，其中相当一部分在真实
    执行流上根本碰不到那个决策。判据的分子只能由行为决定。
    上溯取的是 `host` **自身作为语句**所在的块（不是它的父节点）：`clean_clone_check.py:121`
    的等待在 `try:` 体内、决策在 try 之后的 `if st is not None:` —— 取父节点会直接跳到函数定义
    之后的语句，那条决策永远够不着（本轮实测踩到，修前该点仍判 READ_NO_DECIDE）。"""
    out, cur = [], stmt
    for _round in range(64):                       # 上溯层数封顶，防御异常树
        loc = idx_map.get(id(cur))
        if loc is None:
            break
        seq, i = loc
        for s in seq[i + 1:]:
            if _not_a_flow_body(s):
                continue                       # 后续出现的 def/class：定义点不执行其体
            out.extend(linear_stmts(s))
        host = list_owner.get(id(seq))
        if host is None or isinstance(host, (ast.FunctionDef, ast.AsyncFunctionDef,
                                             ast.ClassDef, ast.Lambda)):
            break                                  # 跨函数交给 return_consumed，不在这里续
        cur = host
    return out


def _enclosing_stmt(tree, node):
    """包含该节点的最内层语句（用对象同一性判定，不靠行号区间猜）。"""
    best = None
    for s in ast.walk(tree):
        if not isinstance(s, ast.stmt):
            continue
        for x in ast.walk(s):
            if x is node:
                if best is None or _span(s) < _span(best):
                    best = s
                break
    return best


def _span(s):
    ls = [n.lineno for n in ast.walk(s) if hasattr(n, "lineno")]
    return max(ls) - min(ls) if ls else 0


def return_consumed(tree, own, flow, fname):
    """`fname` 的返回值在**调用点**有没有被决策消费。r101 扩面的跨函数那一半。

    三种调用点形状各给一条结论，其余一律算没消费：
      ① `X = fname(...)` / `X, Y = fname(...)` ⇒ 拿绑定名去调用点之后的执行流续扫；
      ② 调用直接长在 `assert/if/check(...)` 里 ⇒ 调用点本身就是消费点；
      ③ 裸调用作 Expr、结果没人接 ⇒ **不判**（反例腿的靶子：把它也算消费，
         「提取函数 + 无人接收」立刻成为第二条降噪通道）。
    """
    if not fname:
        return None
    idx_map, list_owner = flow
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and _attr_name(node) == fname):
            continue
        if own.get(id(node)) == fname:
            continue                           # 自身体内的调用不算调用点（自调不作消费证据）
        host = _enclosing_stmt(tree, node)
        if host is None or own.get(id(host)) == fname:
            continue
        if isinstance(host, (ast.Assert, ast.If)):
            return "cross-fn@%d(%s)" % (host.lineno, "assert" if isinstance(host, ast.Assert) else "if")
        if isinstance(host, ast.Expr):
            for x in ast.walk(host):
                if isinstance(x, ast.Call) and _attr_name(x) in CHECK_NAMES \
                        and any(g is node for a in x.args for g in ast.walk(a)):
                    return "cross-fn@%d(%s)" % (host.lineno, _attr_name(x))
        names = set()
        if isinstance(host, ast.Assign):
            names = {n.id for t in host.targets for n in ast.walk(t) if isinstance(n, ast.Name)}
        elif isinstance(host, (ast.AnnAssign, ast.AugAssign)) and isinstance(host.target, ast.Name):
            names = {host.target.id}
        if not names:
            continue
        seq = forward_flow(host, idx_map, list_owner)
        j, _g, how = _tainted_decision(seq, -1, names) if seq else (None, False, "")
        if j is not None and how != "return":
            return "cross-fn@%d(%s)" % (seq[j].lineno, how)
    return None


def decide_bucket(tree, own, flow, stmt, blk, idx, nxt):
    """定长等待的归类。搜索面三面依次：**同块 → 沿执行流上溯的后续块 → 跨函数的返回值消费点**。

    r100 的一手缺陷是只走第一面：LOC 门（≤150 行/函数）逼着把 `wait+read` 提进 helper、
    决策留在调用方，本尺随即把两处改判 READ_NO_DECIDE —— **提取函数成了一条降噪通道**。
    正解是扩被审面而不是内联驱动件：内联会把 `public_check.main` 从 130 行顶向 150 门
    （在册反例「余量是没锁住的余量，不是成绩」），且 `loc_guard` 取数面是 `git ls-tree HEAD`，
    工作树未入库件根本不被它看见 ⇒ 两侧读数不可比。
    """
    rn = _read_names(nxt)
    j, guarded, how = _tainted_decision(blk, idx, rn)
    if j is not None and how != "return":
        if guarded:
            return "C_GUARDED", "读与决策之间隔着完成态等待(%s)" % how
        return "C1_HARD", "定长→取数→%s 立刻消费" % how
    seq = forward_flow(stmt, *flow)
    j2, g2, how2 = (_tainted_decision(seq, -1, rn) if len(seq) > 1 else (None, False, ""))
    if j2 is not None and how2 != "return":
        if g2:
            return "C_GUARDED", "跨块：读与决策之间隔着完成态等待(%s)" % how2
        return "C1_HARD", "定长→取数→%s 消费(跨块@%d)" % (how2, seq[j2].lineno)
    got = None
    hand = (j is not None and how == "return") or (j2 is not None and how2 == "return")
    if not hand and not rn:
        # 取数直接长在 return 表达式里（`return page.evaluate(...)`）⇒ 没有绑定名可追，
        # 但返回值就是那次取数本身，仍算交接（r101 实测 emotion_wiring_check.py:162）。
        hand = any(isinstance(s, ast.Return) and s.value is not None and _is_read(s.value)
                   for s in seq)
    if hand:
        got = return_consumed(tree, own, flow, own.get(id(stmt)))
    if got:
        return "C1_HARD", "定长→取数→return→调用点消费(%s)" % got
    if guarded or g2:
        return "C_GUARDED", "读与决策之间隔着完成态等待"
    return "READ_NO_DECIDE", "取到数但同块/执行流后续/跨函数三面都没被决策消费"


def classify(text, name=""):
    """单件源码 → (逐条记录, 自报调用总数, 解析错误串 or None)。纯函数，夹具不造文件。"""
    recs = []
    try:
        tree = ast.parse(text)
    except SyntaxError as e:
        return recs, 0, "SyntaxError line %s: %s" % (e.lineno, e.msg)
    blocks = _blocks(tree)
    loops = _loop_stmt_ids(tree)
    own = owner_map(tree)
    flow = flow_ctx(tree, blocks)
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
            bucket, note = decide_bucket(tree, own, flow, stmt, blk, idx, nxt)
        recs.append({"file": name, "line": stmt.lineno, "ms": ms, "bucket": bucket, "note": note,
                     "stmt": norm_stmt(ast.get_source_segment(text, stmt) or "")})
    return recs, total, None


def norm_stmt(seg):
    """语句指纹：取整行的首个物理行、压掉空白差异。评审账锚它，不锚行号。

    为什么不锚行号（本仓在册教训）：行号锚法会让「没改这条的人」也变不了绿——上面任何一次
    插行都会让存量评审项集体错位，而真实缺陷一个没动。锚语句本体后，改那一条才会翻面。
    """
    return " ".join((seg or "").split("\n")[0].split())


# 逐件评审台账（r99）。键 = `文件名::语句指纹`，sites = 该形状在现读面里应出现的次数。
# 口径三条：
#   mis-wait     等错了 ⇒ 本轮已改成被等对象的完成态（改完该形状从 C1_HARD 消失，棘轮自己降）
#   shaped-only  形状命中但**没有可等的异步态**（同步 DOM 变更 / 等待对象就是被断言对象）
#   unobservable 产品没暴露完成态，硬造一个「等」等于替被测对象编造状态 ⇒ 保留定长并记此态
#   debt-open    （r101 新增档，不是把旧三档放宽）形状命中、异步态**真实存在**、产品也已暴露
#                完成态 ⇒ 该改成完成态等待；但本轮只扩尺不动驱动件（动驱动＝三副本同步＋回归＋
#                公网面差距），所以记债并登记 r102。**为什么不塞进 shaped-only**：那个词会被
#                下一轮读成「无需处理」，而这里每一条都是可以直接改成 `wait_for_function` 的真债。
# 更正注 r101（本文件 §「r100 对账」下面那三行的结论仍成立，只是数变了）：把被审面扩到
#   「同块 → 沿执行流上溯的后续块 → 跨函数的返回值消费点」之后，`clean_clone_check.py:122`
#   与 `public_check.py:51/55/59` 按预言回到 C1_HARD；同时另捞出 12 处此前同样被盲区漏掉的
#   真债（browser_check / j2 / j4 / lightshow / emotion_wiring / storage_resilience /
#   stream_contract）。现读由 6 涨到 22 ⇒ **这是口径变更不是活变差**，旧 9 与新 22 不可比，
#   基线随之 9→22 并在 `--baseline` help 里写明「换口径」；下一轮的正解是把 debt-open 那 12 条
#   改成完成态等待（每条改完自己离开 C1_HARD ⇒ 棘轮自己降），而不是把基线再往上抬。
# 本表只是**读数**：判据仍不猜意图（红只由棘轮产生），未覆盖件走续行出声、不判红。
#
# r100 对账（键必须与现读同起同落，所以这里只记「现在仍在 C1_HARD 里」的形状；
# 三条已被移出去的形状连同结论一起写在 交付物/对标分析报告-2026-10-08-r100.md §3-①）：
#   · ux_guards_check.py::pg.wait_for_timeout(6000) —— **真消除**：产品暴露 window.__pendingTurns，
#     U2g 改等它归零（timing_coupling 在册唯一那条 unobservable 由此销账）。
#   · clean_clone_check.py::pg.wait_for_timeout(2500) 与 public_check.py::pg.wait_for_timeout(12000)
#     —— **没有消除**：LOC 门（≤150 行/函数）把 wait+read 提进了 drive_page()/drive_chat()，
#     决策留在调用方 ⇒ 本尺把它们改判 READ_NO_DECIDE。这是**尺变软**，不是活变好，
#     所以 C1_HARD 基线一字未动（仍 9，现读 6）；r101 的正解是把被审面扩到「跨函数返回值的消费者」。
REVIEW = {
    "memory_recall_check.py::pg.wait_for_timeout(1500)": {
        "verdict": "shaped-only", "sites": 1,
        "why": "reload 后清 localStorage 再读播种态，读的是本进程刚写入的确定值，无异步态可等"},
    "offline_shell_check.py::pg.wait_for_timeout(600)": {
        "verdict": "shaped-only", "sites": 1,
        "why": "取数在 evaluate 的 async 体里自带 await fetch，这 600ms 什么都没等（装饰性定长）"},
    "rescan_shots_check.py::pg.wait_for_timeout(2500)": {
        "verdict": "shaped-only", "sites": 2,
        "why": "两处分别等 SW 注册生效与离线重载后结构就位，而等的内容就是被断言的内容 ⇒ "
               "同 clean_clone 那条：先把超时折成 FAIL 才谈改。该件不在电池面（batt=False）"},
    "rescan_shots_check.py::pg.wait_for_timeout(700)": {
        "verdict": "shaped-only", "sites": 1,
        "why": "等 #dlg-settings 打开，而 dlg_open 正是被断言项（同上，改了会把 FAIL 变 CRASH）"},
    "ux_guards_check.py::pg.wait_for_timeout(800)": {
        "verdict": "shaped-only", "sites": 1,
        "why": "展开是 chat-window.js 同步 insertBefore，800ms 押的是同步变更；而可等的完成态"
               "（首条内容变了）就是被断言项"},
    # ── 以下 15 条键 = r101 扩面（跨块 / 跨函数返回值消费）捞出的存量真债，逐条已核决策行 ──
    "clean_clone_check.py::pg.wait_for_timeout(2500)": {
        "verdict": "debt-open", "sites": 1,
        "why": "r100 那条改判点回到分子：wait→evaluate(st) 在 try 体内、决策在 try 之后的 "
               "`if st is not None:`(跨块@138)。等的是页面加载完成 ⇒ 正解 wait_for_selector('#chat-input')"},
    "public_check.py::pg.wait_for_timeout(12000)": {
        "verdict": "debt-open", "sites": 2,
        "why": "r100 那条改判点：wait→inner_text/eval 后 `return probe,…`，调用方 ck(\"P5 双路情绪读数…\") "
               "消费(@194)。产品 r100 已暴露 window.__pendingTurns ⇒ 可等它归零，12s 定长属重复"},
    "public_check.py::pg.wait_for_timeout(8000)": {
        "verdict": "debt-open", "sites": 1,
        "why": "同上第三处（危机词那条腿），消费点同为 @194"},
    "browser_check.py::page.wait_for_timeout(2500)": {
        "verdict": "debt-open", "sites": 1,
        "why": "wait→crisis_readout=inner_text(#probe-result)，决策 `assert \"危机\" in crisis_readout`"
               "(跨块@152) ⇒ 等的是回复落定，__pendingTurns 可替"},
    "browser_check.py::page.wait_for_timeout(500)": {
        "verdict": "debt-open", "sites": 1,
        "why": "wait→dock_collapsed=get_attribute/eval，决策 `assert dock_collapsed`(跨块@153) "
               "⇒ dock 开合是 class 变更，可 wait_for_function 断言 classList"},
    "browser_check.py::page.wait_for_timeout(2000)": {
        "verdict": "unobservable", "sites": 1,
        "why": "滚到底再回滚后读 opacity(back3)，决策 @157 ⇒ 等的是滚动过渡落定，"
               "产品没暴露「过渡结束」这个态；硬造等待等于替被测对象编状态，保留定长并记此态"},
    "browser_check.py::page.wait_for_timeout(800)": {
        "verdict": "unobservable", "sites": 1,
        "why": "面板进屏 opacity(o_enter)，返回值在 @158 的 assert 消费 ⇒ 同上，过渡动画无完成态可等"},
    "lightshow_check.py::page.wait_for_timeout(900)": {
        "verdict": "unobservable", "sites": 1,
        "why": "演示态滚动是否被中断，读 scroll_y/ui_after_scroll 后在 @229 断言 ⇒ 等的是动画帧序，"
               "无完成态暴露"},
    "lightshow_check.py::page.wait_for_timeout(700)": {
        "verdict": "unobservable", "sites": 1,
        "why": "「回到我的记忆」清演示点亮，读 lit_cleared 后 @236 断言 ⇒ 同上（点亮是逐粒子动画）"},
    "j2_chat_contract.py::page.wait_for_timeout(600)": {
        "verdict": "debt-open", "sites": 1,
        "why": "A 组在线腿：wait→取气泡文本 return，调用方 `if \"在线大模型生成\" not in a_last`(@72) 消费 "
               "⇒ 600ms 是回复后的渲染拍，可等 __pendingTurns/气泡 class"},
    "j2_chat_contract.py::page.wait_for_timeout(10000)": {
        "verdict": "debt-open", "sites": 1,
        "why": "同件等回复的 10s 定长，消费点 @72 ⇒ 可等完成态归零"},
    "stream_contract.py::page.wait_for_timeout(14000)": {
        "verdict": "debt-open", "sites": 1,
        "why": "流式契约件：wait→eval_on_selector_all(msgs) 后 `return msgs[-1], had_stream`，"
               "调用方 @136 的 if 消费 ⇒ 本件本就是测逐字流式的，等「流结束」有现成可见证据（.streaming 消失）"},
    "j4_memory_check.py::page.wait_for_timeout(10000)": {
        "verdict": "debt-open", "sites": 1,
        "why": "远端记忆落库回读，决策 `if mem_off < 2`(跨块@127) ⇒ 等的是服务端写入，"
               "可改轮询 /api/memory/stats 计数到位"},
    "emotion_wiring_check.py::page.wait_for_timeout(300)": {
        "verdict": "debt-open", "sites": 1,
        "why": "前置已有 wait_for_function 判流式结束，这 300ms 再等文本节点落定后直接 "
               "`return page.evaluate(...)`，调用方 check(\"W4…\")(@180) 消费 ⇒ 重复定长，"
               "可折进那条 wait_for_function 的谓词里"},
    "storage_resilience_check.py::page.wait_for_timeout(600)": {
        "verdict": "debt-open", "sites": 1,
        "why": "计数槽由 rAF/事件回写（源码注释自陈「给一拍」），写进 res 容器后 @223 的 if 消费 ⇒ "
               "容器写入的污点这条 r101 才追得到；可等「计数文本变了」"},
}


def review_gap(rows, review=None):
    """C1_HARD ⇄ 评审账 双向对账。返回 (覆盖数, 未评审清单, 陈旧/数目不符清单)。纯函数。

    第三项含两种形态：账里有而现读没有（锚点陈旧，多为该形状已被改掉），
    以及指纹对得上但 sites 与现读条数不等（漏登记，或同形状重复出现没记数）。
    """
    review = REVIEW if review is None else review
    need = {}
    for r in rows:
        if r["bucket"] != "C1_HARD":
            continue
        k = "%s::%s" % (r["file"], r.get("stmt") or "")
        need[k] = need.get(k, 0) + 1
    missing = sorted(k for k in need if k not in review)
    mismatched = ["%s（现读 %d 条，账记 sites=%s）" % (k, need[k], review[k].get("sites"))
                  for k in sorted(review) if k in need and review[k].get("sites") != need[k]]
    stale = ["%s（账里有，现读无此形状 ⇒ 锚点陈旧或该件已被改掉）" % k
             for k in sorted(review) if k not in need]
    return sum(v for k, v in need.items() if k in review), missing, mismatched + stale


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


def _st_cross_face(expect, bucket_of):
    """r101 扩面腿：跨块执行流与跨函数返回值消费，正反双向 + 两条回归钉 + 一条变异腿。

    单独成函数是承本文件 ㉑ 那几条的同一条理由（`selftest` 余量不足以再塞 10 行）。
    """
    XFER = ("def drive(pg):\n"
            "    pg.wait_for_timeout(1200)\n"
            "    probe = pg.inner_text('#x')\n"
            "    return probe\n"
            "def main(pg):\n"
            "    v = drive(pg)\n"
            "    assert v\n")
    XFER_BARE = ("def drive(pg):\n"
                 "    pg.wait_for_timeout(1200)\n"
                 "    probe = pg.inner_text('#x')\n"
                 "    return probe\n"
                 "def main(pg):\n"
                 "    drive(pg)\n")
    XFER_PRINT = ("def drive(pg):\n"
                  "    pg.wait_for_timeout(1200)\n"
                  "    probe = pg.inner_text('#x')\n"
                  "    return probe\n"
                  "def main(pg):\n"
                  "    v = drive(pg)\n"
                  "    print(v)\n")
    XFER_INLINE = ("def drive(pg):\n"
                   "    pg.wait_for_timeout(300)\n"
                   "    return pg.inner_text('#x')\n"
                   "def main(pg):\n"
                   "    assert drive(pg)\n")
    EXCL = ("def f(pg):\n"
            "    if pg.inner_text('#a'):\n"
            "        pg.wait_for_timeout(900)\n"
            "        v = pg.inner_text('#b')\n"
            "    else:\n"
            "        assert v == 'x'\n")
    NEST = ("def f(pg):\n"
            "    pg.wait_for_timeout(900)\n"
            "    v = pg.inner_text('#b')\n"
            "def g():\n"
            "    assert v\n")
    expect("正例 提取成 helper 且返回值被调用方断言 ⇒ 仍判 C1_HARD"
           "（这封住的正是 r100 那条「LOC 门逼搬家 ⇒ 尺自动降噪」通道）",
           bucket_of(XFER) == "C1_HARD")
    expect("反例 helper 返回值裸调用无人接收 ⇒ 不得升格", bucket_of(XFER_BARE) == "READ_NO_DECIDE")
    expect("反例 调用方只 print 返回值 ⇒ 仍不判"
           "（把 return 当决策就会开出第二条通道：print 不是决策）",
           bucket_of(XFER_PRINT) == "READ_NO_DECIDE")
    expect("正例 取数直接长在 return 表达式里（无绑定名）⇒ 交接仍成立",
           bucket_of(XFER_INLINE) == "C1_HARD")
    expect("回归钉 if/else 互斥分支里的消费不算"
           "（第一版按 lineno 摊平，实测把分子从 6 虚涨到 27 ⇒ 退回那条写法本腿必红）",
           bucket_of(EXCL) == "READ_NO_DECIDE")
    expect("回归钉 后续 def 的定义体不在调用点执行 ⇒ 不算消费", bucket_of(NEST) == "READ_NO_DECIDE")

    def hard_of(fname):
        p = TEST_DIR / fname
        if not p.is_file():
            return None
        recs, _t, _e = classify(p.read_text(encoding="utf-8", errors="replace"), fname)
        return sum(1 for r in recs if r["bucket"] == "C1_HARD")

    before = {n: hard_of(n) for n in ("clean_clone_check.py", "public_check.py")}
    keep = (globals()["forward_flow"], globals()["return_consumed"])
    try:
        globals()["forward_flow"] = lambda *a, **k: []
        globals()["return_consumed"] = lambda *a, **k: None
        after = {n: hard_of(n) for n in ("clean_clone_check.py", "public_check.py")}
        expect("变异腿 把两条新面打桩成恒空 ⇒ clean_clone/public_check 必须掉出分子"
               "（证明这些读数是新面产出的，不是原本就在）",
               all(before[n] is not None and before[n] > 0 for n in before)
               and all(after[n] == 0 for n in after))
    finally:
        globals()["forward_flow"], globals()["return_consumed"] = keep
    expect("  还原后同一批文件回到原读数（动的是尺不是期望值）",
           {n: hard_of(n) for n in before} == before)


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
    _st_cross_face(expect, bucket_of)

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
    # 评审账腿（r99）：台账与现读面必须双向对得上，否则「已评审」与「没人看过」不可区分。
    fake = [{"file": "a.py", "bucket": "C1_HARD", "stmt": "pg.wait_for_timeout(500)"},
            {"file": "b.py", "bucket": "POLL", "stmt": "pg.wait_for_timeout(9000)"}]
    okk = "a.py::pg.wait_for_timeout(500)"
    cov, mis, st = review_gap(fake, {okk: {"verdict": "shaped-only", "sites": 1}})
    expect("评审账 覆盖齐 ⇒ 零未评审零对账差", cov == 1 and not mis and not st)
    cov2, mis2, _s2 = review_gap(fake, {})
    expect("反例 账清空 ⇒ 该件列为未评审（不得静默）", cov2 == 0 and mis2 == [okk])
    _c3, _m3, st3 = review_gap(fake, {okk: {"verdict": "x", "sites": 7}})
    expect("反例 sites 记 7 而现读 1 ⇒ 必须报对账差", bool(st3) and "sites=7" in st3[0])
    _c4, _m4, st4 = review_gap([], {"ghost.py::pg.wait_for_timeout(9)": {"verdict": "x", "sites": 1}})
    expect("反例 账里有而现读无 ⇒ 锚点陈旧必须点名（防台账变只增不减的坟场）", bool(st4))
    cov5, _m5, _s5 = review_gap(fake, {okk: {"verdict": "x", "sites": 1},
                                       "b.py::pg.wait_for_timeout(9000)": {"verdict": "y", "sites": 1}})
    expect("口径腿 非 C1_HARD 的形状不进覆盖数（POLL 那条不得替评审账凑数）", cov5 == 1)
    # 指纹稳定性：同一语句换行号必须仍是同一个键（锚行号的账会在别人插行时集体错位）
    moved = [{"file": "a.py", "bucket": "C1_HARD", "stmt": "pg.wait_for_timeout(500)", "line": 99}]
    expect("指纹腿 行号变了键不变（评审账不锚行号）", review_gap(moved, {okk: {"sites": 1}})[0] == 1)
    # 真面自证：拿现读面跑一遍，账必须既无未评审也无陈旧（这条红了就是本轮台账没跟上树）
    rrows, _rt, _rb, _ru, _ri = scan_dir(TEST_DIR)
    rcov, rmis, rstale = review_gap(rrows)
    expect("真面 现读 C1_HARD %d 件全部有评审结论（缺 %s）" % (rcov, rmis[:2]), not rmis)
    expect("真面 评审账与现读逐键等值（对不上 %s）" % (rstale[:2],), not rstale)

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
    ap.add_argument("--baseline", type=int, default=22,
                    help="C1_HARD 棘轮上界（只降不升）。r98 建尺实测 16 却把上界写成 28 —— "
                         "help 原文「取实测值钉住」与磁盘不符；r99 改掉 7 处误等后现读 9，"
                         "基线随之 28→9（余量清零才是本意：留 19 的空档等于给新增误等发通行证）。"
                         "⚠️ **22 是 r101 的口径变更值，与旧 9 不可比**：被审面从「同块」扩到"
                         "「同块 → 执行流后续块 → 跨函数返回值消费」后，r100 被 LOC 搬家掩掉的 "
                         "4 处与另外 12 处存量真债一起回到分子。旧 9 不是「当时只有 9 处」而是"
                         "「当时只看得见 9 处」。下一轮的正解是把 12 条 debt-open 改成完成态等待"
                         "（改完自动离开分子 ⇒ 棘轮自己降），不是抬基线。")
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
    # 评审账合并进记录（写进 --json 台账），判据本身仍不猜意图：这里只是把**人工结论**挂在形状上。
    for r in rows:
        if r["bucket"] == "C1_HARD":
            ent = REVIEW.get("%s::%s" % (r["file"], r.get("stmt") or ""))
            r["verdict"] = ent["verdict"] if ent else None
    covered, unreviewed, stale = review_gap(rows)
    red = []
    if hard > a.baseline:
        red.append("C1_HARD %d > 基线 %d" % (hard, a.baseline))
    # 评审账完整性也是红（r99 新挂）：形状普查只报数，评审结论若没有责任方，
    # 下一轮就无法区分「已评审并判定保留」与「没人看过」。两类红因分开点名。
    if unreviewed:
        red.append("C1_HARD 未登记评审结论 %d 处：%s"
                   % (len(unreviewed), "、".join(unreviewed[:3]) + ("…" if len(unreviewed) > 3 else "")))
    if stale:
        red.append("评审账与现读对不上 %d 项（首条：%s）" % (len(stale), stale[0][:70]))
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
    vd = {}
    for r in rows:
        if r["bucket"] == "C1_HARD" and r.get("verdict"):
            vd[r["verdict"]] = vd.get(r["verdict"], 0) + 1
    print("  - 逐件评审账(r99): 覆盖 %d/%d 件（%s）"
          % (covered, hard, "，".join("%s=%d" % kv for kv in sorted(vd.items())) or "空"))
    for s in stale[:6]:
        print("  - 评审账对不上: " + s)
    if a.json:
        Path(a.json).write_bytes(json.dumps(
            {"baseline": a.baseline, "total_calls": total_calls, "files": files_with,
             "buckets": c, "c1_hard_battery": hard_bat, "red": red,
             "grep_face_note": "grep 面为 142 处/31 件（含注释与 docstring），本尺取 AST 面",
             "battery_face": "取到" if in_battery is not None else "未取到",
             "worst": top, "review": {"covered": covered, "c1_hard": hard,
                                      "missing": unreviewed, "stale": stale},
             "records": rows}, ensure_ascii=False, indent=1).encode("utf-8"))
    return 1 if red else 0


if __name__ == "__main__":
    sys.exit(main())
