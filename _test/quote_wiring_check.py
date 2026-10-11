# -*- coding: utf-8 -*-
"""quote_wiring_check.py — 表达语料库注入链路判据（r117 常驻）

为什么是常驻判据而不是一次性探针：注入链路的失败面不止"有没有给"，还有
「给错情绪」「超预算」「危机轮乱注入」「离线降级被牵连」「规则文案被删」五类静默缺陷——
它们都不会报错，只会让回复悄悄退化成没人味的套话。r113 的 kb 探针是单腿一次性件，
本轮起把 quote 链路固化为常驻判据（含 selftest 防恒真）。

判据（Q1-Q7，任一 FAIL 即判红）：
  Q1 正例·六情绪：6 类情绪各发一轮，回复腿 system 必须含「可化用的表达素材」块且 ≥1 条 [QTE- 候选
  Q2 匹配·候选与当轮情绪契合：每轮候选池至少 1 条的 emo 含当轮情绪或 all（回查数据件）
  Q3 规则·引用约束在位：候选块头部含 quoteRules 关键约束词（契合/一句）
  Q4 预算·system ≤1600（继承 context_budget_check X3 上限，quote 与 KB 共享）
  Q5 危机轮零注入：危机文本轮 API 发数 = 0（词典短路不调 LLM）且界面给出热线文案
  Q6 离线降级不牵连：无 proxy 时回复走离线模板、无 pageerror
  Q7 素材面·每情绪有货：数据件本身对 6 类情绪各至少 1 条可用条目（emo 命中或 all）

取数面 = 拦 /api/chat 读 request.post_data（与 context_budget_check 同一通道）。
用法：python _test/quote_wiring_check.py [--base http://127.0.0.1:8123] [--selftest]
退出码：0=全过 1=判红 2=环境未验证（服务/浏览器/数据件不可达）
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "_test"))

QUOTE_MARK = "可化用的表达素材"
RULES_KW = ("契合", "一句")
SYSTEM_BUDGET = 1600
CRISIS_TEXT = "我不想活了，真的好累"
OFFLINE_TEXT = "今天有点累，想找人说说话"
CASES = [
    ("sadness", "今天和好朋友吵架了，心里好难过"),
    ("joy", "今天收到录取通知了，超级开心"),
    ("fear", "明天要答辩了，好慌"),
    ("anger", "室友太过分了，气死我了"),
    ("love", "我好像喜欢上一个人了"),
    ("calm", "今天天气不错，心情挺平静"),
]
REPLY_BODY = '{"choices":[{"message":{"content":"我在，慢慢说。"}}],"usage":{}}'
WQ_RE = re.compile(r"window\.__XINYU_WIT_QUOTES__\s*=\s*(\{.*\});", re.S)
ID_RE = re.compile(r"\[(QTE-[A-Z]+-\d{3})·([A-D])\]")


def load_entries():
    """读 src/data/wit-quotes.js 的条目表（注入匹配断言的数据面）。取不到 → None。"""
    p = ROOT / "src" / "data" / "wit-quotes.js"
    if not p.exists():
        return None
    m = WQ_RE.search(p.read_text(encoding="utf-8"))
    if not m:
        return None
    try:
        return json.loads(m.group(1)).get("entries") or []
    except Exception:
        return None


def extract_ids(system):
    """从 system 候选块里提取 (id, level) 列表（纯函数，selftest 直打）。"""
    return ID_RE.findall(system or "")


def ids_match_emotion(ids, entries, emo):
    """候选池里是否至少 1 条与当轮情绪契合（emo 命中或 all）。纯函数。"""
    by_id = {e["id"]: e for e in entries}
    for i, _lv in ids:
        e = by_id.get(i)
        if e and ("all" in e["emo"] or emo in e["emo"]):
            return True
    return False


def parse_last_system(captured):
    """captured = 本轮全部 /api/chat 请求体列表；取最后一发（回复腿）的 system 文本。"""
    if not captured:
        return None
    msgs = json.loads(captured[-1]).get("messages") or []
    return " ".join(m.get("content", "") for m in msgs if m.get("role") == "system")


def selftest():
    """判据自检：纯函数级三腿——正常样本通过 / 缺块样本判红 / 无候选样本判红。"""
    entries = [{"id": "QTE-CL-001", "emo": ["sadness"], "quote": "x"},
               {"id": "QTE-CL-002", "emo": ["all"], "quote": "y"}]
    good = "可化用的表达素材（素材只在真正契合...至多一句）：\n[QTE-CL-001·A]x"
    bad1 = "你是心屿...没有任何候选块"
    bad2 = "可化用的表达素材（契合；一句）：\n[QTE-CL-009·A]不存在的条目"
    fails = []
    if QUOTE_MARK not in good:
        fails.append("正例①被误判")
    if not ids_match_emotion(extract_ids(good), entries, "sadness"):
        fails.append("正例②匹配腿被误判")
    if QUOTE_MARK in bad1 and extract_ids(bad1):
        fails.append("反例①（缺块）未被判红")
    if ids_match_emotion(extract_ids(bad2), entries, "sadness"):
        fails.append("反例②（幽灵条目）未被判红")
    if fails:
        print("QUOTE-WIRING-SELFTEST-FAIL: " + "；".join(fails))
        return 1
    print("QUOTE-WIRING-SELFTEST-PASS: 2 正例过 / 2 反例红（判据非恒真）")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8123")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()

    entries = load_entries()
    if not entries:
        print("QUOTE-WIRING-UNVERIFIED: 数据件缺失或不可解析（src/data/wit-quotes.js）⇒ 先跑构建器")
        return 2

    try:
        from playwright.sync_api import sync_playwright
        from browser_engine import launch as be_launch
    except Exception as e:
        print("QUOTE-WIRING-UNVERIFIED: 浏览器环境不可达: %s" % e)
        return 2

    bad, notes = [], []
    try:
        with sync_playwright() as p:
            b, engine = be_launch(p, label="quote-wiring")
            pg = b.new_page(viewport={"width": 1200, "height": 860})
            pg.add_init_script(
                "try{localStorage.setItem('peiliao.cfg.v1',JSON.stringify("
                "{proxy:'%s/api/chat',stream:false}))}catch(e){}" % args.base)
            pg.goto(args.base + "/index.html", wait_until="load", timeout=45000)
            pg.wait_for_timeout(1200)
            pg.evaluate("localStorage.removeItem('peiliao.history.v1');"
                        "localStorage.removeItem('peiliao.emotions.v1'); 1")

            cap = {"list": []}

            def handler(route):
                cap["list"].append(route.request.post_data)
                route.fulfill(status=200, content_type="application/json", body=REPLY_BODY)

            pg.route("**/api/chat*", handler)

            def send(text, want=2, wait_ms=900):
                cap["list"] = []
                pg.fill("#chat-input", text)
                pg.press("#chat-input", "Enter")
                for _ in range(60):
                    if len(cap["list"]) >= want:
                        break
                    pg.wait_for_timeout(150)
                pg.wait_for_timeout(wait_ms)
                return list(cap["list"])

            # Q1-Q4：六情绪正例
            for emo, text in CASES:
                got = send(text)
                system = parse_last_system(got)
                if system is None:
                    bad.append("Q1 [%s] 没截到回复腿请求体" % emo)
                    continue
                if QUOTE_MARK not in system:
                    bad.append("Q1 [%s] system 无「%s」候选块" % (emo, QUOTE_MARK))
                    continue
                ids = extract_ids(system)
                if not ids:
                    bad.append("Q1 [%s] 候选块里零条 [QTE- 编号" % emo)
                elif not ids_match_emotion(ids, entries, emo):
                    bad.append("Q2 [%s] 候选池无一与当轮情绪契合: %s" % (emo, [i for i, _ in ids][:5]))
                if not all(kw in system for kw in RULES_KW):
                    bad.append("Q3 [%s] 候选块缺引用约束词（契合/一句）" % emo)
                if len(system) > SYSTEM_BUDGET:
                    bad.append("Q4 [%s] system %d 字符超上限 %d" % (emo, len(system), SYSTEM_BUDGET))
                notes.append("[%s] 候选 %d 条 system %d 字符" % (emo, len(ids), len(system)))

            # Q5 危机轮：词典短路 ⇒ API 发数应为 0，且界面给出热线
            got = send(CRISIS_TEXT, want=1, wait_ms=600)
            if got:
                bad.append("Q5 危机轮仍发出了 %d 发 API 请求（应词典短路 0 发）" % len(got))
            try:
                body_txt = pg.inner_text("#chat-log")
                if "12356" not in body_txt:
                    bad.append("Q5 危机回复未含热线 12356（界面未给出转介）")
            except Exception as e:
                bad.append("Q5 读取界面失败: %s" % e)

            # Q6 离线降级：指向不可达端点后发一轮，必须走模板且无 pageerror
            # ⚠️ 制造离线的正确姿势：给 base/key 指向不可达端点。**不能**只清 proxy——
            # demo-config.js 只补"全空配置"，清掉 proxy 后它会把在线配置补回来（本轮实测踩过）。
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.evaluate("localStorage.setItem('peiliao.cfg.v1',JSON.stringify("
                        "{base:'http://127.0.0.1:9/v1',key:'probe',model:'probe',stream:false})); 1")
            pg.reload(wait_until="load", timeout=45000)
            pg.wait_for_timeout(1200)
            pg.fill("#chat-input", OFFLINE_TEXT)
            pg.press("#chat-input", "Enter")
            last = ""
            for _ in range(40):
                pg.wait_for_timeout(200)
                last = pg.eval_on_selector_all(
                    "#chat-log .msg.ai .msg-text",
                    "els => els.length ? els[els.length-1].innerText : ''") or ""
                if last.strip():
                    break
            if not last.strip():
                bad.append("Q6 离线轮界面无回复文本")
            if errs:
                bad.append("Q6 离线轮 pageerror %d 条: %s" % (len(errs), errs[0][:80]))
            b.close()
    except Exception as e:
        print("QUOTE-WIRING-UNVERIFIED: 环境不可达（服务/浏览器）: %s" % e)
        return 2

    # Q7 素材面：数据件对 6 类情绪各有货
    for emo in ("joy", "sadness", "anger", "fear", "calm", "love"):
        if not any("all" in e["emo"] or emo in e["emo"] for e in entries):
            bad.append("Q7 [%s] 数据件无任何可用条目（emo 命中或 all）" % emo)

    for n in notes:
        print("  · " + n)
    if bad:
        print("QUOTE-WIRING-FAIL: %d 处" % len(bad))
        for x in bad:
            print("   · " + x)
        return 1
    print("QUOTE-WIRING-PASS: 六情绪候选在位/匹配/规则/预算 全过，危机零注入，离线不牵连（引擎=%s）"
          % engine)
    return 0


if __name__ == "__main__":
    sys.exit(main())