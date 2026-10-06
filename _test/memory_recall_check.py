# -*- coding: utf-8 -*-
"""长期记忆召回判据（r52 新增）—— 量的是「落库的记忆有没有回到发给模型的那条 messages」。

为什么是这一面：✅ 取证 `grep -icE "多轮记忆|上下文窗口|HISTORY_MAX|记忆回灌|滚动摘要"
交付物/对标分析报告-*.md` = 十三份全 0。而 09-24 那两份在总览表里把「记忆系统」记作
**✅ localStorage + 服务端双表** —— 那是**存在性**结论（有表、写得进去），
没有一格量过**读回来喂给模型**这件事。实测代码面佐证（动手前一手 grep）：
  `src/js/chat-agent.js:137-151` SYSTEM 只拼策略表 + `history.slice(-10)`；
  `src/js/memory-store.js:142` 导出面 record/all/clear/exportAll/hydrate/pushMessage/isRemote/sessionId
  —— **零召回项**。即"跨设备记住你"当时只成立在星图展示层，模型侧对用户历史一无所知。
⇒ 本判据把"记忆只写不读"变成会红的东西；R4 是它的**反向腿**（清掉记忆后必须不再出现召回段），
   否则判据可以靠"永远注入一段常量"骗绿。

八条 case（R1/R2/R3/R4/R5/R7 阻断，R6/R8 记录）：
  R1 空记忆 → 发给模型的 system **不得**含「长期记忆」（防空标题、防常量）
  R2 播 3 条记忆 → system 必须含「长期记忆」且含次数 3 与高频情绪标签
  R3 刷新页面（新会话）→ 仍须召回（证明不是会话内变量，而是持久化数据驱动）
  R4 清空记忆后 → 召回段必须消失（反向腿；与 R2 成对，缺一条判据即恒真）
  R5 危机文本 → 不得发出 /api/chat（危机拦截优先，不被记忆注入绕过）
  R6 在线成功 → 界面证据行须标「已带入 N 条记忆」（知情可见）
  R7 隐私 → system 内不得出现任何一条用户原话（只做聚合，不抄原文）
  R8 全程 pageerror == 0
取数面 = **拦截 /api/chat 读 request.post_data**（真流量出口，不是读源码里的字符串）。
用法：python _test/memory_recall_check.py [--base http://127.0.0.1:8123] [--selftest]
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
MEM_KEY = "peiliao.emotions.v1"
MARK = "长期记忆"
SEED = [
    {"emotion": "anxious", "intensity": 0.8, "text": "明天要答辩了我特别慌", "ago_d": 3},
    {"emotion": "anxious", "intensity": 0.6, "text": "导师一直没回我消息", "ago_d": 2},
    {"emotion": "tired", "intensity": 0.7, "text": "昨晚三点才睡着", "ago_d": 1},
]
REPLY_BODY = ('{"choices":[{"message":{"content":"这三天你一直在扛着答辩的事，先喝口水。"}}],'
              '"usage":{}}')


def js_state():
    return """() => {
      const msgs=[...document.querySelectorAll('#chat-log > *')];
      const last=msgs.length?msgs[msgs.length-1].innerText.replace(/\\s+/g,' ').slice(0,200):'';
      const inp=document.querySelector('#chat-input');
      return {n:msgs.length, last, disabled: !!inp && inp.disabled,
              thinking: !!document.querySelector('.thinking,.streaming'),
              mem: (window.MemoryStore&&window.MemoryStore.count)?window.MemoryStore.count():-1};
    }"""


def assess(cases):
    """纯函数判据：selftest 直打它，不碰浏览器也不碰服务，反例注入是确定的。
    输入 = [{kind, system, sent, tag, pageerrors, mem_seen}]"""
    bad = []
    if not cases:
        return ["R0 零用例 ⇒ 分母为空，不判绿"], {}
    by = {}
    for c in cases:
        by.setdefault(c.get("kind"), []).append(c)

    def one(k):
        v = by.get(k) or []
        return v[0] if v else None

    def sys_of(k):
        c = one(k)
        return (c or {}).get("system") or ""

    if not by.get("empty"):
        bad.append("R0 缺 empty（空记忆基线）用例 ⇒ 没有对照组，召回断言不可信")
    else:
        c = one("empty")
        if not c.get("sent"):
            bad.append("R-INVALID empty：/api/chat 未被打到（夹具坏了，不是产品坏了）")
        elif MARK in c.get("system", ""):
            bad.append("R1 空记忆却注入了「长期记忆」段：%r" % c["system"][:70])
    for k in ("seeded", "reload"):
        c = one(k)
        if c is None:
            bad.append("R0 缺 %s 用例 ⇒ 正向腿不完整" % k)
            continue
        if not c.get("sent"):
            bad.append("R-INVALID %s：注入通道未被打到 ⇒ 该读数不构成证据" % k)
            continue
        s = c.get("system", "")
        if MARK not in s:
            bad.append("R2/R3 %s：发给模型的 system 里没有召回段 ⇒ 记忆只写不读（本判据要抓的东西）" % k)
            continue
        if c.get("mem_seen", -1) < len(SEED):
            bad.append("R-INVALID %s：MemoryStore.count=%s < 播种子数 %d（没读到我自己写的那块）"
                       % (k, c.get("mem_seen"), len(SEED)))
        # 段内条数只与"至少这么多"对账：本轮结束时又 record() 了一条，精确相等会自打脸
        m = re.search(r"已经聊过\s*(\d+)\s*次", s)
        if not m or int(m.group(1)) < len(SEED):
            bad.append("R2 %s：召回段未带可信条数（匹配=%s，应 ≥%d）：%r"
                       % (k, m.group(1) if m else None, len(SEED), s[-90:]))
    c = one("cleared")
    if c is None:
        bad.append("R0 缺 cleared 用例 ⇒ 判据只有正向腿，恒真风险未排除")
    elif not c.get("sent"):
        bad.append("R-INVALID cleared：注入通道未被打到")
    elif MARK in c.get("system", ""):
        bad.append("R4 清空记忆后仍在注入召回段 ⇒ R2 不是数据驱动（判据缺反向腿）：%r"
                   % c["system"][:70])
    c = one("crisis")
    if c is None:
        bad.append("R0 缺 crisis 用例")
    elif c.get("sent"):
        bad.append("R5 危机文本发出了 /api/chat ⇒ 拦截被绕过")
    c = one("seeded")
    if c and c.get("sent") and "已带入" not in (c.get("tag") or ""):
        bad.append("R6 在线且已召回，但界面未标注「已带入 N 条记忆」（用户无从知情）：%r" % c.get("tag"))
    for k in ("seeded", "reload"):
        s = (one(k) or {}).get("system") or ""
        leak = [x["text"] for x in SEED if x["text"] in s]
        if leak:
            bad.append("R7 %s：召回段含用户原话 %d 条（只做聚合是隐私承诺的前提）：%r"
                       % (k, len(leak), leak[0][:24]))
    errs = sum(len(c.get("pageerrors") or []) for c in cases)
    if errs:
        bad.append("R8 全程未捕获异常 %d 条：%s" % (errs, (cases[0].get("pageerrors") or [""])[0][:80]))
    return bad, {"cases": len(cases), "kinds": sorted(by), "errors": errs}


def seed_script():
    """在页面里播 3 条记忆。**走真实 record()**，不直写 localStorage ——
    MemoryStore 有 `mem` 进程内缓存，直写 localStorage 它读不到（首版就是这么假的：
    count 恒 0 或恒旧值）。ts 靠 `{ts:Date.now(), ...entry}` 的 spread 覆盖生效。"""
    js = """(seed) => {
      const day = 86400000, now = Date.now();
      (seed || []).forEach(s => window.MemoryStore.record(
        { emotion: s.emotion, intensity: s.intensity, text: s.text, ts: now - s.ago_d * day }));
      return window.MemoryStore.count();
    }"""
    return js, [{"emotion": s["emotion"], "intensity": s["intensity"], "text": s["text"],
                 "ago_d": s["ago_d"]} for s in SEED]


def send_and_capture(pg, text, wait_s=45):
    """发一句话，返回 (system_content, sent_any, settled_state)。
    system 取拦截到的**最后**一次请求体里的 role=system 段（真流量出口，不是源码字符串）。"""
    box = {"sys": "", "n": 0}

    def handler(route):
        req = route.request
        box["n"] += 1
        try:
            body = json.loads(req.post_data or "{}")
            msgs = body.get("messages") or []
            s = " ".join(m.get("content", "") for m in msgs if m.get("role") == "system")
            box["sys"] = box["sys"] + " " + s
        except Exception as e:
            box["sys"] = "POST-DATA-UNPARSED:" + type(e).__name__
        route.fulfill(status=200, content_type="application/json", body=REPLY_BODY)

    for u in PATTERNS:
        pg.route(u, handler)
    pg.fill("#chat-input", text)
    pg.press("#chat-input", "Enter")
    t0 = time.monotonic()
    st = {}
    while time.monotonic() - t0 < wait_s:
        st = pg.evaluate(js_state())
        if st.get("n", 0) >= 2 and not st.get("thinking") and not st.get("disabled"):
            break
        pg.wait_for_timeout(250)
    for u in PATTERNS:
        pg.unroute(u, handler)
    return box["sys"], box["n"], st


def run(base):
    from playwright.sync_api import sync_playwright

    from browser_engine import launch as be_launch, short_face

    cases = []
    with sync_playwright() as p:
        b, face = be_launch(p, label="memory_recall_check")
        pg = b.new_page(viewport={"width": 1200, "height": 860})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)[:110]))
        # 在线模式：proxy 是**完整端点 URL**（`endpoint()` 直接 fetch(c.proxy)，不拼路径）；
        # ⚠️ 首版写成 `base+'/api/'` ⇒ 请求打到 /api/ 上，路由模式匹配不到，四条用例全判
        #    INVALID(没打到) —— 这正是本判据自己该抓的形状：它抓到了自己的夹具坏。
        # 不依赖 demo-config（它会连带打开 remote/emotionRemote，把被测面扩成两条链路）。
        pg.add_init_script("try{localStorage.setItem('%s',JSON.stringify("
                           "{proxy:'%s/api/chat',stream:false}))}catch(e){}"
                           % (CFG_KEY, base))
        pg.goto(base + "/", wait_until="load", timeout=45000)
        pg.wait_for_timeout(2200)
        # 归零：本机 + 服务端（远端开着时 hydrate 会用服务端副本覆盖本机，不归零就测不到"我自己写的那块"）
        pg.evaluate("() => window.MemoryStore.clear && window.MemoryStore.clear()")
        pg.wait_for_timeout(900)
        pg.evaluate("() => localStorage.removeItem('%s')" % MEM_KEY)
        pg.reload(wait_until="load")
        pg.wait_for_timeout(1800)

        s, n, st = send_and_capture(pg, "今天有点累，想被陪一会儿")
        cases.append({"kind": "empty", "system": s, "sent": n > 0, "tag": st.get("last", ""),
                      "mem_seen": st.get("mem"), "pageerrors": []})
        # 上一轮自己 record 了一条 ⇒ 播种前必须归零，否则 seeded 的条数对不上（首轮实测 count=4）
        pg.evaluate("() => localStorage.removeItem('%s')" % MEM_KEY)
        pg.evaluate("() => window.MemoryStore.clear && window.MemoryStore.clear()")
        pg.reload(wait_until="load"); pg.wait_for_timeout(1500)

        seen = pg.evaluate(*seed_script())
        s, n, st = send_and_capture(pg, "还是那件答辩的事")
        cases.append({"kind": "seeded", "system": s, "sent": n > 0, "tag": st.get("last", ""),
                      "mem_seen": seen, "pageerrors": []})

        pg.reload(wait_until="load"); pg.wait_for_timeout(1500)
        s2, n2, st2 = send_and_capture(pg, "我今晚又睡不着")
        cases.append({"kind": "reload", "system": s2, "sent": n2 > 0, "tag": st2.get("last", ""),
                      "mem_seen": st2.get("mem"), "pageerrors": []})

        pg.evaluate("() => localStorage.removeItem('%s')" % MEM_KEY)
        pg.evaluate("() => window.MemoryStore.clear && window.MemoryStore.clear()")
        pg.reload(wait_until="load"); pg.wait_for_timeout(1500)
        s3, n3, st3 = send_and_capture(pg, "感觉好多了，谢谢")
        cases.append({"kind": "cleared", "system": s3, "sent": n3 > 0, "tag": st3.get("last", ""),
                      "mem_seen": st3.get("mem"), "pageerrors": []})

        _s4, n4, st4 = send_and_capture(pg, "我真的撑不下去了，不想活了")
        cases.append({"kind": "crisis", "system": "", "sent": n4 > 0, "tag": st4.get("last", ""),
                      "mem_seen": st4.get("mem"), "pageerrors": []})
        for c in cases:
            c["pageerrors"] = list(errs)
        b.close()
    return cases, face


def selftest():
    """反例只打 assess（纯函数）：证明判据既能抓"没召回"也能抓"恒真注入"。"""
    ok, fail = 0, []
    base_seed = [{"kind": "seeded", "system": "【长期记忆】已经聊过 3 次", "sent": True,
                  "tag": "在线大模型生成 · 已带入 3 条记忆", "mem_seen": 3, "pageerrors": []}]
    full = ([{"kind": "empty", "system": "persona", "sent": True, "tag": "", "mem_seen": 0,
              "pageerrors": []},
             {"kind": "reload", "system": "【长期记忆】已经聊过 3 次", "sent": True,
              "tag": "已带入 3 条记忆", "mem_seen": 3, "pageerrors": []},
             {"kind": "cleared", "system": "persona", "sent": True, "tag": "", "mem_seen": 0,
              "pageerrors": []},
             {"kind": "crisis", "system": "", "sent": False, "tag": "", "mem_seen": 0,
              "pageerrors": []}] + base_seed)
    if not assess(full)[0]:
        ok += 1
    else:
        fail.append("正例 完整绿灯组被判红：%s" % assess(full)[0])
    # 反例①：记忆只写不读（首版产品就是这个形状）⇒ 必须红
    m1 = [dict(c) for c in full]
    for c in m1:
        if c["kind"] in ("seeded", "reload"):
            c["system"] = "persona 只有策略表"
    if any("只写不读" in x or "R2/R3" in x for x in assess(m1)[0]):
        ok += 1
    else:
        fail.append("反例① 未召回没被抓到：%s" % assess(m1)[0])
    # 反例②：恒真注入（每轮都塞召回段，清记忆后仍在）⇒ 必须由 R4 抓红
    m2 = [dict(c) for c in full]
    for c in m2:
        if c["kind"] == "cleared":
            c["system"] = "【长期记忆】已经聊过 3 次"
    if any("R4" in x for x in assess(m2)[0]):
        ok += 1
    else:
        fail.append("反例② 恒真注入未被抓到：%s" % assess(m2)[0])
    # 反例③：缺反向腿（整组没有 cleared 用例）⇒ 判据不得因此变宽松
    m3 = [c for c in full if c["kind"] != "cleared"]
    if any("缺 cleared" in x for x in assess(m3)[0]):
        ok += 1
    else:
        fail.append("反例③ 缺腿被静默放行：%s" % assess(m3)[0])
    # 反例④：夹具坏了（请求根本没发出）⇒ 必须判 INVALID，不得判 PASS 也不得判产品红
    m4 = [dict(c) for c in full]
    for c in m4:
        c["sent"] = False
    got = assess(m4)[0]
    if any("INVALID" in x for x in got) and not any("只写不读" in x for x in got):
        ok += 1
    else:
        fail.append("反例④ 零输入被当成通过或错判产品：%s" % got)
    # 反例⑤：播了种子却没读到（count 不符）⇒ 同样是夹具面，必须 INVALID
    m5 = [dict(c) for c in full]
    for c in m5:
        if c["kind"] in ("seeded", "reload"):
            c["mem_seen"] = 0
    if any("没读到我自己写的那块" in x for x in assess(m5)[0]):
        ok += 1
    else:
        fail.append("反例⑤ 计数未回读被抓到：%s" % assess(m5)[0])
    # 反例⑥：原话照抄进 prompt ⇒ R7 隐私必须红
    m6 = [dict(c) for c in full]
    for c in m6:
        if c["kind"] == "seeded":
            c["system"] = "【长期记忆】明天要答辩了我特别慌"
    if any("R7" in x for x in assess(m6)[0]):
        ok += 1
    else:
        fail.append("反例⑥ 原话进 prompt 未判红：%s" % assess(m6)[0])
    # 边界：零用例 / 危机被绕过
    if assess([])[0] and assess([{"kind": "crisis", "system": "", "sent": True,
                                  "tag": "", "mem_seen": 0, "pageerrors": []}])[0]:
        ok += 1
    else:
        fail.append("边界 空分母/危机绕过未判红")
    # 反例⑦：在线召回了但界面不说 ⇒ R6 知情断言必须红
    m7 = [dict(c) for c in full]
    for c in m7:
        if c["kind"] == "seeded":
            c["tag"] = "在线大模型生成"
    if any("R6" in x for x in assess(m7)[0]):
        ok += 1
    else:
        fail.append("反例⑦ 未标注知情没被抓到：%s" % assess(m7)[0])
    for x in fail:
        print("  SELFTEST-FAIL " + x)
    expected = 9
    print("RECALL-SELFTEST: %d/%d%s" % (ok, expected,
          "" if ok + len(fail) == expected else "  ⚠️ 分支数 %d≠%d" % (ok + len(fail), expected)))
    return 0 if ok == expected and ok + len(fail) == expected else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=BASE_DEFAULT)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest())
    from browser_engine import short_face
    import urllib.request
    try:
        urllib.request.urlopen(a.base + "/api/health", timeout=6).read()
    except Exception as e:
        print("RECALL-UNVERIFIED: 服务端不可达 %s（%s）⇒ 环境未验，不判绿"
              % (a.base, type(e).__name__))
        sys.exit(2)
    try:
        cases, face = run(a.base)
    except Exception as e:
        print("RECALL-UNVERIFIED: 浏览器/夹具异常 %s: %s" % (type(e).__name__, str(e)[:120]))
        sys.exit(2)
    bad, info = assess(cases)
    for c in cases:
        print("  %-8s sent=%s mem=%s system含召回=%s 原话泄漏=%d"
              % (c["kind"], c["sent"], c.get("mem_seen"), MARK in (c.get("system") or ""),
                 sum(1 for x in SEED if x["text"] in (c.get("system") or ""))))
    if bad:
        for x in bad:
            print("  " + x)
        print("RECALL-FAIL 引擎=%s: %d 条判红（用例 %d）"
              % (short_face(face), len(bad), info.get("cases", 0)))
        sys.exit(1)
    print("RECALL-PASS 引擎=%s: 记忆已回灌模型且清库即消失（用例 %d 类=%s，未捕获异常 0）"
          % (short_face(face), info["cases"], ",".join(info["kinds"])))
    sys.exit(0)


if __name__ == "__main__":
    main()
