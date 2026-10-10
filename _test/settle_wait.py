# -*- coding: utf-8 -*-
"""settle_wait.py — 「等系统静止」的唯一实现（r96 立）。

为什么要有这一个文件（不是再造一把尺）：`j4_memory` 与 `data_rights` 在 CI 上各判红一次
（run 37294500147 / 37299161773），**两条红因同因**：判据把"某一时刻的读数"当"本轮写完的状态"用。
- `j4_memory`：定长 `wait_for_timeout(8000)` 押完成时刻（本机逐 0.25s 采样实测：占位气泡 0.05s、服务端落库 1.65s）；
- `data_rights` D3：先 `stats()` 再 `exportAll()`，两次取数**跨时刻**，CI 上拿到
  `server.messages 实得 2 / 期望 1` —— 导出比快照新，比较的其实不是同一个状态。

两条硬约束（缺一条这文件就没资格当唯一实现）：
1. **等待条件里不许出现业务阈值** —— 只问"变了吗／还在变吗"，不问"够不够"。
   否则就是"等自己要证的数"，判据恒绿。
2. **静止 ≠ 正确**：返回 `(settled, value)`；`settled=False` 表示"到点没观察到变化"，
   调用方必须据此记**取数失败**（不得折成 0，也不得判产品红）。
用法：`from settle_wait import wait_quiescent, same_reading`；自查 `python _test/settle_wait.py --selftest`。
退出码：0=通过 1=判据自身不成立（本文件不碰被检对象，故无 rc=2 档）。
"""
import sys
import time


_UNSET = object()


def wait_quiescent(read_fn, budget_s=25.0, poll=0.25, baseline=_UNSET):
    """两步静止：① 相对**起账**出现变化；② 再连续两次读数**相等**。返回 (settled, last_value)。

    `baseline` 要由调用方在**做那件事之前**取好传进来。
    一手（r96 同轮自查）：不传 baseline 时首读被当起账，若写入发生在"观察者开始看之前"，
    读数从此永远不变 ⇒ 判 `settled=False`，把一次**成功**读成取数失败（假红）。
    传了 baseline，进入时 `首读 ≠ baseline` 即视为"已变化"，只需再看到两次相等。
    没写就是没写：值始终等于 baseline ⇒ 仍判 False，不得读成"写完且稳定"。"""
    base = read_fn()
    prev = base
    if baseline is not _UNSET and base != baseline:
        t0 = time.monotonic()
        while time.monotonic() - t0 < budget_s:
            cur = read_fn()
            if cur == prev:
                return True, cur
            prev = cur
            time.sleep(poll)
        return False, prev
    t0 = time.monotonic()
    changed = False
    while time.monotonic() - t0 < budget_s:
        cur = read_fn()
        if not changed:
            if cur != base:
                changed, prev = True, cur
        elif cur == prev:
            return True, cur
        else:
            prev = cur
        time.sleep(poll)
    return False, prev if changed else base


def same_reading(a, b, keys=()):
    """两次读数是否同一状态：只比 `keys` 指定字段（缺省比整值）。
    用于"导出 ⇄ 快照"这类**必须同刻**的比较——不等就记未验，不判产品红。"""
    if a is None or b is None:
        # None = 取数失败；它只能与 None 相等。混进 {} 会把"没读到"读成"状态一致"
        return a is None and b is None
    if not keys:
        return a == b
    return all(a.get(k) == b.get(k) for k in keys)


# ── r102：对话回合的完成态（从 ux_guards_check 上收，五处判据共用一处实现）──
# 为什么上收：r101 的同族教训是「同一个事实三处各写一份，改了 2 个忘 1 个」
# （gh_cred.py 就是这么从三个探针里收出来的）。TURN_DONE_JS 原在 ux_guards，
# r102 起 browser_check / public_check / j2 / stream_contract 全改完成态等待，
# 再各抄一份就等于给那个教训开门。
TURN_DONE_JS = """() => { const m = document.querySelectorAll('#chat-log .msg');
  const last = m[m.length - 1];
  if (!last || last.hasAttribute('data-r99-prev')) return false;
  if (last.hasAttribute('data-emotion')) return true;
  const tag = last.querySelector('.tag');
  return !!tag && tag.textContent === '友好错误态'; }"""


def mark_last(pg):
    """给**当前**最后一条消息打私有标记。必须在点提交**之前**调用。

    为什么必须在 click 前（r102 一手实测的缺陷，本函数上收前的写法把它放在 click 后）：
    离线共情模板 ~15ms 就回完 => click 之后再 mark，标记会打到**本轮新产生的终态气泡**
    上 => 谓词里的 `!last.hasAttribute('data-r99-prev')` 永不成立 => 30s 超时。
    现场：emotion_wiring W3b 危机腿，`n` 已 +2、`data-emotion=crisis` 已就位、
    `pendingTurns` 归零，唯一卡住的是"标记打错了对象"——判据崩在一个本来是对的谓词上。
    标记只服务判据（产品代码不读它）；没有消息时无害（空列表取不到 last）。
    """
    pg.evaluate("""() => { const m = document.querySelectorAll('#chat-log .msg');
      if (m.length) m[m.length-1].setAttribute('data-r99-prev', '1'); }""")


def before_send(pg):
    """点提交**之前**调用：给当时的最后一条气泡做身份记号（ux_guards 形态，唯一正确时序）。

    这个名字比 `mark_last` 更值得用：它把"必须先标记再发送"的时序要求写进函数名，
    下一位读者不会再把顺序搞反（搞反的代价是 30s 超时 + 一条无法归因的红）。
    """
    mark_last(pg)


def wait_reply(pg, timeout=20000):
    """点提交**之后**调用：等这一轮的**终态**气泡落地（渲染完成），不押毫秒数。

    前置：调用方必须先 `before_send(pg)`（或自己 mark_last）再 click。
    两种终态都收（缺一种就是把后门当前门）：
      · 正常路 = 最后一条带 `data-emotion`（app.js 渲染回包时写；#probe-result 的
        renderReadout 在同一同步块内随后执行 => 看到标记时探针读数必然已更新）；
      · 异常路 = 最后一条带「友好错误态」标签（app.js catch 里的气泡）。
    中途的 thinking / 逐字流式气泡两者都不满足 => 不会被误判成立。
    故障路径因此仍是"快速明确的断言失败"，不会退化成超时（红因文案不丢）。
    """
    pg.wait_for_function(TURN_DONE_JS, timeout=timeout, polling="raf")


def _counter(start=0):
    """假读数器：每次都吐新值（模拟"到预算点仍在写"）。
    ⚠️ 这里原来直接用 `_scripted([0,1,2,3,…])` —— 那个夹具用完会**重复最后一个值**，
    于是"仍在变化"的用例被夹具自己静止掉了：selftest 首跑三条不符里有两条是这个原因。
    夹具的前提必须与被测前提同构，否则反例打在死假设上不算数。"""
    box = {"i": start}

    def f():
        box["i"] += 1
        return box["i"]
    return f


def _scripted(seq):
    """假读数器：按脚本吐值，用完重复最后一个（模拟"已经静止"）。"""
    box = {"i": 0}

    def f():
        v = seq[min(box["i"], len(seq) - 1)]
        box["i"] += 1
        return v
    return f


def selftest():
    cases = []

    def eq(label, got, want):
        cases.append((label, got, want))

    # 正例：先变化、再两次相等 ⇒ 判静止，且带回首值
    eq("正例 0→1→2→2… 静止于 2", wait_quiescent(_scripted([0, 1, 2]), budget_s=2, poll=0.001), (True, 2))
    # 边界：全程无变化 ⇒ False（不得把"没变化"读成"静止且已验"）
    eq("边界 读数从不变化 ⇒ settled=False",
       wait_quiescent(_scripted([7, 7, 7]), budget_s=0.05, poll=0.001)[0], False)
    # 边界：到点仍在变化 ⇒ False，并带回最后一次读数（供调用方印进红因）
    eq("边界 到点仍在变 ⇒ 不判静止",
       wait_quiescent(_counter(), budget_s=0.05, poll=0.001)[0], False)
    # 正例：等待条件不含业务阈值 ⇒ 变化后的值"不达标"也照样静止（达标与否归调用方判）
    # 正例（r96 自查补）：写入发生在开始观察之前 ⇒ 传 baseline 必须仍判静止，否则成功被读成取数失败
    eq("正例 首读已含写入 + 给了 baseline ⇒ 判静止",
       wait_quiescent(_scripted([5, 5, 5]), budget_s=2, poll=0.001, baseline=0), (True, 5))
    eq("变异对照 同序列不给 baseline ⇒ 观察不到变化（假红的来源，实测曾把 data_rights 判红）",
       wait_quiescent(_scripted([5, 5, 5]), budget_s=0.05, poll=0.001)[0], False)
    eq("边界 给了 baseline 但值从未离开 baseline ⇒ False（没写不能读成「写完且稳定」）",
       wait_quiescent(_scripted([0, 0, 0]), budget_s=0.05, poll=0.001, baseline=0)[0], False)
    eq("正例 变化后的值小于任何阈值仍静止",
       wait_quiescent(_scripted([9, 0, 0]), budget_s=2, poll=0.001), (True, 0))
    # 变异体：只要求"出现过变化"而不要求两次相等 ⇒ 序列 1→2 必须被现在的实现拒判静止
    eq("变异对照 只见到一次变化不足以判静止（一直在变 ⇒ 预算内不得返回 True）",
       wait_quiescent(_counter(1), budget_s=0.05, poll=0.001)[0], False)
    # same_reading：子集字段比较 + 缺省整值比较
    eq("same_reading 只比指定 keys（无关字段漂移不误伤）",
       same_reading({"m": 2, "ts": 1}, {"m": 2, "ts": 9}, keys=("m",)), True)
    eq("same_reading 指定 keys 下真差异要抓到",
       same_reading({"m": 2}, {"m": 1}, keys=("m",)), False)
    eq("same_reading 无 keys ⇒ 等于整值比较", same_reading({"a": 1}, {"a": 1, "b": 2}), False)
    # 边界：None 与空 dict 不得混为相等（取数失败不能读成"状态一致"）
    eq("same_reading None ≠ {}", same_reading(None, {}, keys=("m",)), False)
    # 异常路径：读数器抛错必须抛出去，不许被吞成"静止"
    raised = False
    try:
        wait_quiescent(lambda: (_ for _ in ()).throw(RuntimeError("boom")), budget_s=1, poll=0.001)
    except RuntimeError:
        raised = True
    eq("异常 读数器抛错 ⇒ 原样抛出（吞掉就会把取数失败伪装成静止）", raised, True)

    bad = [(n, g, w) for n, g, w in cases if g != w]
    for n, g, w in bad:
        print("  用例不符: %s ｜ got=%r want=%r" % (n, g, w))
    print("SETTLE-SELFTEST-%s（%d/%d 条：静止两步/无变化不算/预算到点不算/阈值不入等待/同刻比较/异常不吞）"
          % ("PASS" if not bad else "FAIL", len(cases) - len(bad), len(cases)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(selftest() if "--selftest" in sys.argv[1:] else 0)
