# -*- coding: utf-8 -*-
"""上下文预算与历史截断损失判据（r53 新增）—— 量「本机攒下的对话，模型这一轮真看到了多少」。

为什么是这一面：✅ 取证 `grep -icE "token 预算|上下文预算" 交付物/对标分析报告-*.md` = **十四份全 0**；
`HISTORY_MAX`/`滚动摘要` 只在 r52 出现过，而 r52 把它写作**未做**并留话「有数之后再决定摘要腿」。
一手代码实测（动手前）：`chat-agent.js:11` HISTORY_MAX=10、第 26 行本机封顶 40 条、
第 159 行 `history.slice(-HISTORY_MAX)` 是唯一进 messages 的历史入口
⇒ 聊到第 6 轮，**前面所有轮次对模型永久消失**，且没有任何一格量过这个损失。
演示现场一次正常对话就是 10-15 轮 —— 评委看到的"陪伴感"恰好建立在模型看不见的部分上。

判据（X1-X5 阻断，X0 环境）：
  X1 覆盖率：本轮送进模型的历史条数 / 本机已积累条数，须 ≥ 棘轮下限（**下限只降不升**）
  X2 断崖可证：被截掉的轮数必须出现在「早前对话概要」里且数字对得上
     （不是要求"首条原话必须可见"—— 我们不把原话塞回 prompt，见 X5）
  X3 prompt 成本上限：system 段（persona+策略+记忆段+概要段）字符数 ≤ SYSTEM_CHAR_BUDGET
  X4 反向腿：单轮会话里概要段与记忆段**都不得出现**（否则判据可靠常量注入骗绿）
  X5 隐私：概要段/记忆段内不得出现任何一条已登记的用户原话
  X6 全程未捕获异常 == 0
取数面 = 拦 /api/chat 读 request.post_data（真流量出口，与 r52 memory_recall 同一通道）。
用法：python _test/context_budget_check.py [--base http://127.0.0.1:8123] [--selftest] [--turns N]
退出码：0=全过 1=判红 2=环境未验证（服务/浏览器不可达 ⇒ 不判绿）
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
BASE_DEFAULT = "http://127.0.0.1:8123"
PATTERNS = ("**/api/chat*", "**/*chat/completions*")
CFG_KEY = "peiliao.cfg.v1"
SUM_MARK = "早前对话概要"
MEM_MARK = "长期记忆"
FIRST_TOKEN = "紫苏柠檬茶"           # 第 1 轮的独有词：用来证明"截断真的发生了"
SYSTEM_CHAR_BUDGET = 1600            # X3：persona+策略+记忆+概要 的整段上限（r53 实测 396 起）
COV_FLOOR = 0.30                     # X1 棘轮下限：修前 14 轮实测 10/28=0.357，留 ~16% 余量
TURN_TEXTS = ["明天要答辩了我特别慌", "导师一直没回我消息", "昨晚三点才睡着",
              "感觉努力全白费", "室友打呼我睡不着", "高数挂了很难受", "和男朋友吵架了",
              "妈妈打电话来催我考研", "图书馆占不到位置", "今天天气好闷",
              "面试被刷了两次", "突然很想念 hometown", "胸口一直闷闷的", "不想去上课"]
REPLY_BODY = ('{"choices":[{"message":{"content":"我在，慢慢说。"}}],"usage":{}}')


def parse_body(raw):
    """把一条 /api/chat 请求体拆成判据要的读数（纯函数，selftest 直打）。"""
    try:
        b = json.loads(raw or "{}")
    except Exception:
        return None
    msgs = b.get("messages") or []
    sys_txt = " ".join(m.get("content", "") for m in msgs if m.get("role") == "system")
    hist = [m for m in msgs if m.get("role") in ("user", "assistant")]
    return {"system": sys_txt, "hist": len(hist), "msgs": len(msgs)}


def history_max():
    """从权威源读 HISTORY_MAX（不抄常量：抄了就会和 chat-agent.js 漂移）。取不到 → 0 判环境未验。"""
    try:
        src = (ROOT / "src" / "js" / "chat-agent.js").read_text("utf-8", errors="replace")
    except Exception:
        return 0
    m = re.search(r"HISTORY_MAX\s*=\s*(\d+)", src)
    return int(m.group(1)) if m else 0


def assess(reads, befores):
    """纯函数判据。reads = 每轮 parse_body 的结果；befores[i] = **发第 i 轮之前**本机 history 条数。
    ⚠️ 用"发之前"的条数而不是"发之后"，是为了让 dropped 由判据自己观测得出，
    而不是拿产品报给自己的数字自比（measure() 自比是登记在册的假反例形态）。"""
    bad = []
    if not reads:
        return ["X0 零轮次 ⇒ 分母为空，不判绿"], {}
    got = [r for r in reads if r]
    if len(got) < len(reads):
        bad.append("X-INVALID %d/%d 轮没解析到 messages ⇒ 夹具或通道坏了，本组读数作废"
                   % (len(reads) - len(got), len(reads)))
        return bad, {}
    hm = history_max()
    if hm <= 0:
        return ["X0 取不到 HISTORY_MAX（chat-agent.js 形状变了？）⇒ 分母未验，不判绿"], {}
    last, before = got[-1], befores[-1]
    sent_hist = last["hist"] - 1          # messages 里含本轮用户文本，它不在 history 里
    if sent_hist != min(before, hm):
        bad.append("X1 送 %d 条历史，但发前本机有 %d 条、窗口=%d ⇒ 应送 %d 条，截断逻辑与声明不符"
                   % (sent_hist, before, hm, min(before, hm)))
    cov = round(sent_hist / max(1, before), 3)
    dropped = max(0, before - hm)
    if cov < COV_FLOOR:
        bad.append("X1 覆盖率 %s < 下限 %s（送 %d 条 / 发前 %d 条）" % (cov, COV_FLOOR, sent_hist, before))
    # X2 断崖可证：只要真有被截掉的轮次，就必须有一份写明该数字的概要在 system 里
    if dropped > 0:
        m = re.search(SUM_MARK + r"[：:]\s*此前\s*(\d+)\s*条", last["system"])
        if not m:
            bad.append("X2 截断了 %d 条历史，但 system 里没有「%s」段 ⇒ 模型对早前一无所知"
                       % (dropped, SUM_MARK))
        elif int(m.group(1)) != dropped:
            bad.append("X2 概要写的条数=%s 与实测算出的截断数=%d 不符 ⇒ 概要是假的"
                       % (m.group(1), dropped))
        if FIRST_TOKEN in last["system"]:
            bad.append("X2-INVARIANT 概要段里出现用户原话（%s）⇒ 与 X5 同族，聚合不得抄原文" % FIRST_TOKEN)
    elif SUM_MARK in last["system"]:
        bad.append("X4 反向腿失败：零截断却注入概要段 ⇒ 概要是常量不是数据驱动")
    # X3 成本
    n = len(last["system"])
    if n > SYSTEM_CHAR_BUDGET:
        bad.append("X3 system 段 %d 字符 > 上限 %d ⇒ 记忆/概要注入自身变成新的成本源"
                   % (n, SYSTEM_CHAR_BUDGET))
    # X4 首轮不得有任何注入
    first = got[0]
    if first["hist"] != 1 or MEM_MARK in first["system"] or SUM_MARK in first["system"]:
        bad.append("X4 第 1 轮读数异常（hist=%d 注入=%s/%s）⇒ 空态必须干净"
                   % (first["hist"], MEM_MARK in first["system"], SUM_MARK in first["system"]))
    # X5 隐私：任何一条用户原文都不许出现在 system
    leak = [t for t in TURN_TEXTS + [FIRST_TOKEN] if t in first["system"] or t in last["system"]]
    if leak:
        bad.append("X5 system 段含用户原话 %d 条：%s" % (len(leak), leak[0][:20]))
    return bad, {"cov": cov, "sent_hist": sent_hist, "before": before, "hm": hm,
                 "dropped": dropped, "sys_chars": n, "turns": len(reads)}


def js_state():
    return """() => {
      const msgs=[...document.querySelectorAll('#chat-log > *')];
      const inp=document.querySelector('#chat-input');
      return {n:msgs.length, disabled: !!inp && inp.disabled,
              thinking: !!document.querySelector('.thinking,.streaming'),
              hist: (window.ChatAgent.getHistory?window.ChatAgent.getHistory().length:-1)};
    }"""


def run(base, turns):
    from playwright.sync_api import sync_playwright

    def launch(pw):
        try:
            return pw.chromium.launch()
        except Exception:
            return pw.chromium.launch(channel="msedge")

    reads, errs, befores = [], [], []
    with sync_playwright() as p:
        b = launch(p)
        pg = b.new_page(viewport={"width": 1200, "height": 860})
        pg.on("pageerror", lambda e: errs.append(str(e)[:110]))
        pg.add_init_script("try{localStorage.setItem('%s',JSON.stringify("
                           "{proxy:'%s/api/chat',stream:false}))}catch(e){}" % (CFG_KEY, base))
        box = {}

        def handler(route):
            box["last"] = route.request.post_data
            route.fulfill(status=200, content_type="application/json", body=REPLY_BODY)

        pg.goto(base + "/", wait_until="load", timeout=45000)
        pg.wait_for_timeout(2200)
        pg.evaluate("() => { localStorage.removeItem('peiliao.history.v1');"
                    " localStorage.removeItem('peiliao.emotions.v1');"
                    " return 1; }")
        pg.reload(wait_until="load")
        pg.wait_for_timeout(1800)
        for u in PATTERNS:
            pg.route(u, handler)
        for i in range(turns):
            txt = TURN_TEXTS[i % len(TURN_TEXTS)] + ("#" + FIRST_TOKEN if i == 0 else "")
            box.clear()
            befores.append(pg.evaluate(js_state())["hist"])
            pg.fill("#chat-input", txt)
            pg.press("#chat-input", "Enter")
            t0 = time.monotonic()
            ok = False
            while time.monotonic() - t0 < 40:
                st = pg.evaluate(js_state())
                if st["n"] >= (i + 1) * 2 + 1 and not st["thinking"] and not st["disabled"]:
                    ok = True
                    break
                pg.wait_for_timeout(200)
            if not ok:
                reads.append(None)
                break
            reads.append(parse_body(box.get("last")))
            if not reads[-1]:
                break
        acc = pg.evaluate(js_state())["hist"]
        for u in PATTERNS:
            pg.unroute(u, handler)
        b.close()
    if befores and len(befores) > len(reads):
        befores = befores[:len(reads)]
    return reads, befores, acc, errs


def selftest():
    ok, fail = 0, []
    hm = history_max()
    if hm <= 0:
        print("  SELFTEST-FAIL 取不到 HISTORY_MAX ⇒ 桩无法构造截断场景")
        return 1
    n_turns = 14
    befores = [2 * i for i in range(n_turns)]              # 每轮前后各 +2 条（user+assistant）
    dropped = befores[-1] - hm
    sys_txt = ("persona。" + MEM_MARK + "】已经聊过 3 次 " + SUM_MARK
               + "：此前 %d 条消息未逐条送入上下文；情绪分布 焦虑×6、低落×4。" % dropped)
    good = [{"system": "persona 纯策略", "hist": 1, "msgs": 2}]
    good += [{"system": sys_txt, "hist": hm + 1, "msgs": hm + 2} for _ in range(n_turns - 1)]
    b0, info = assess(good, befores)
    if not b0:
        ok += 1
    else:
        fail.append("正例（概要与截断条数对得上）被判红：%s" % b0)
    if info.get("dropped") == dropped and info.get("cov") == round(hm / befores[-1], 3):
        ok += 1
    else:
        fail.append("读数异常（应 dropped=%s cov=%s）：%s" % (dropped, hm / befores[-1], info))
    # 反例①：截断了却没有概要段（修前真实形状）⇒ X2 必须红
    m1 = [dict(r) for r in good]
    m1[-1] = {"system": "persona 纯策略", "hist": hm + 1, "msgs": hm + 2}
    if any("X2" in x for x in assess(m1, befores)[0]):
        ok += 1
    else:
        fail.append("反例① 无概要未判红：%s" % assess(m1, befores)[0])
    # 反例②：概要写的条数是假的（少报）⇒ X2 数字对账必须红
    m2 = [dict(r) for r in good]
    m2[-1] = {"system": sys_txt.replace("此前 %d 条" % dropped, "此前 2 条"),
              "hist": hm + 1, "msgs": hm + 2}
    if any("不符" in x for x in assess(m2, befores)[0]):
        ok += 1
    else:
        fail.append("反例② 假概要未被抓到：%s" % assess(m2, befores)[0])
    # 反例③：单轮会话却注入概要（常量骗绿）⇒ X4 反向腿必须红
    if any("X4" in x for x in assess([{"system": sys_txt, "hist": 1, "msgs": 2}], [0])[0]):
        ok += 1
    else:
        fail.append("反例③ 常量注入未被判红：%s" % assess([{"system": sys_txt, "hist": 1, "msgs": 2}], [0])[0])
    # 反例④：system 超限 ⇒ X3 红（成本自证有界）
    m4 = [dict(r) for r in good]
    m4[-1] = {"system": "x" * (SYSTEM_CHAR_BUDGET + 10), "hist": hm + 1, "msgs": hm + 2}
    if any("X3" in x for x in assess(m4, befores)[0]):
        ok += 1
    else:
        fail.append("反例④ 超预算未判红：%s" % assess(m4, befores)[0])
    # 反例⑤：请求体根本没解析到（夹具坏）⇒ 必须 INVALID 不判绿
    b5, _i5 = assess([None], [0])
    if any("INVALID" in x for x in b5):
        ok += 1
    else:
        fail.append("反例⑤ 零解析未走 INVALID：%s" % b5)
    # 反例⑥：概要把用户原话抄进去 ⇒ X5/X2-INVARIANT 必须红
    m6 = [dict(r) for r in good]
    m6[-1] = {"system": SUM_MARK + "：此前 %d 条，他说过%s" % (dropped, FIRST_TOKEN),
              "hist": hm + 1, "msgs": hm + 2}
    if any(("X5" in x or "INVARIANT" in x) for x in assess(m6, befores)[0]):
        ok += 1
    else:
        fail.append("反例⑥ 原话进概要未被判红：%s" % assess(m6, befores)[0])
    # 反例⑦（同源第七形态）：窗口送少了 —— 声明窗口 10 实送 6 ⇒ X1 的"应送条数"断言必须红
    m7 = [dict(r) for r in good]
    m7[-1] = {"system": sys_txt, "hist": 7, "msgs": 8}
    if any("截断逻辑与声明不符" in x for x in assess(m7, befores)[0]):
        ok += 1
    else:
        fail.append("反例⑦ 窗口缩水未被抓到：%s" % assess(m7, befores)[0])
    # 边界：零轮次不得判绿
    if assess([], [])[0]:
        ok += 1
    else:
        fail.append("边界 零分母未判红")
    expected = 10
    for x in fail:
        print("  SELFTEST-FAIL " + x)
    print("CTX-SELFTEST: %d/%d%s" % (ok, expected,
          "" if ok + len(fail) == expected else "  ⚠️ 分支数 %d≠%d" % (ok + len(fail), expected)))
    return 0 if ok == expected and ok + len(fail) == expected else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=BASE_DEFAULT)
    ap.add_argument("--turns", type=int, default=14)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest())
    import urllib.request
    try:
        urllib.request.urlopen(a.base + "/api/health", timeout=6).read()
    except Exception as e:
        print("CTXBUDGET-UNVERIFIED: 服务端不可达 %s（%s）⇒ 环境未验，不判绿" % (a.base, type(e).__name__))
        sys.exit(2)
    try:
        reads, befores, acc, errs = run(a.base, a.turns)
    except Exception as e:
        print("CTXBUDGET-UNVERIFIED: 浏览器/夹具异常 %s: %s" % (type(e).__name__, str(e)[:120]))
        sys.exit(2)
    bad, info = assess(reads, befores)
    info["final_hist"] = acc
    if errs:
        bad.append("X6 全程未捕获异常 %d 条：%s" % (len(errs), errs[0][:80]))
    for x in bad:
        print("  " + x)
    if bad:
        print("CTXBUDGET-FAIL: %d 条判红（轮次 %s）" % (len(bad), info.get("turns", len(reads))))
        sys.exit(1)
    print("CTXBUDGET-PASS: 覆盖率 %s（窗口内送 %d 条／发前 %d 条，窗口=%d）｜"
          "截断 %d 条已由概要注意送达且条数对账｜system %d 字符 ≤ 上限 %d｜首轮零注入｜原话泄漏 0 条"
          % (info["cov"], info["sent_hist"], info["before"], info["hm"], info["dropped"],
             info["sys_chars"], SYSTEM_CHAR_BUDGET))
    sys.exit(0)


if __name__ == "__main__":
    main()
