# -*- coding: utf-8 -*-
"""quote_eval.py — 表达语料库效果验收：全自动盲评对照（r117，老大定的「全自动验收」）

机制（三段）：
  ① 生成：浏览器内直调 `ChatAgent.respond()`，对 30 条测试用例分别生成「新版回复」（含
     quote 候选注入）与「旧版回复」（临时清空 `__XINYU_WIT_QUOTES__.entries` 模拟注入前）。
     同一页面、同一模型、同一温度，唯一变量 = quote 注入有无（单变量对照）。
  ② 盲评：LLM 评委（DeepSeek，temperature=0）对隐去版本标签的 A/B 两回复三维打分
     （适配度/自然度/丰富度，1-5）+ 生硬引用判定；A/B 顺序随机（固定种子可复现）。
  ③ 判据：新版三维均分 ≥ 旧版（每维容差 -0.1）；新版生硬引用率 ≤ 10%；汇总报告落
     交付物/表达语料库/验收报告.md，明细落 _test/_shots/quotes_eval_detail.json。

安全：Key 从 src/js/demo-config.js 动态读取（已 ignore 的本地文件），**任何输出与报告不落 Key**。
用法：python _test/quote_eval.py [--base http://127.0.0.1:8123] [--smoke] [--seed 42]
退出码：0=PASS 1=FAIL 2=环境未验证
"""
import argparse
import json
import random
import re
import sys
import time
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "_test"))

DIMS = ("适配度", "自然度", "丰富度")
HARD_REFUSE = 0.10          # 新版生硬引用率上限
TOL = 0.1                   # 三维均分容差
CLEAN = ("ChatAgent.setCfg({}); "
         "localStorage.removeItem('peiliao.history.v1'); 1")
USE_NEW = ("if(!window.__XINYU_WIT_QUOTES_SAVE__){window.__XINYU_WIT_QUOTES_SAVE__="
           "window.__XINYU_WIT_QUOTES__.entries.slice()} "
           "window.__XINYU_WIT_QUOTES__.entries=window.__XINYU_WIT_QUOTES_SAVE__.slice(); 1")
USE_OLD = ("if(!window.__XINYU_WIT_QUOTES_SAVE__){window.__XINYU_WIT_QUOTES_SAVE__="
           "window.__XINYU_WIT_QUOTES__.entries.slice()} "
           "window.__XINYU_WIT_QUOTES__.entries=[]; 1")

CASES = [
    ("sadness", "和谈了三年的女朋友分手了，感觉心里空了一块"),
    ("sadness", "考研二战又失败了，觉得自己特别没用"),
    ("sadness", "今天是我爸的忌日，我一个人在外地，很想他"),
    ("sadness", "朋友都说我该翻篇了，可我就是走不出来，是不是我太没出息了？"),
    ("sadness", "有时候觉得难过是件很丢人的事，我是不是不该总这样？"),
    ("joy", "今天收到了理想的 offer，第一时间想告诉全世界"),
    ("joy", "和冷战一个月的室友和好了，心里一块石头落地"),
    ("joy", "第一次跑完半程马拉松，觉得自己太棒了"),
    ("joy", "开心的时候总担心乐极生悲，这种心态正常吗？"),
    ("joy", "怎么才能把好状态留得久一点呢？"),
    ("anger", "组里有人把我做的方案说成是他的，气炸了"),
    ("anger", "室友半夜打游戏开麦，说过几次都不改"),
    ("anger", "被家里人拿去和表姐比较，越听越火大"),
    ("anger", "我知道生气伤身，可就是咽不下这口气，怎么办？"),
    ("anger", "是不是我太敏感了，一点小事就炸？"),
    ("fear", "下周要毕业答辩了，一想到上台就心慌"),
    ("fear", "投了二十份简历都没有回音，怕自己真的找不到工作"),
    ("fear", "最近总失眠，怕身体是不是出问题了"),
    ("fear", "别人都说不焦虑就赢了，可到底怎么才能不焦虑？"),
    ("fear", "我总是把还没发生的事想得很糟，这算毛病吗？"),
    ("calm", "考完试了，今天就想安安静静发会呆"),
    ("calm", "下雨天在宿舍听歌，感觉日子也可以这么慢"),
    ("calm", "晚上散步看到月亮很圆，想和人聊聊"),
    ("calm", "平静的日子里总觉得少了点什么，这种空是正常的吗？"),
    ("calm", "想慢慢把生活过好，有什么小建议吗？"),
    ("love", "好像喜欢上一起做项目的同学了，不知道要不要说"),
    ("love", "异地恋第三年，最近总觉得他没那么在乎我了"),
    ("love", "刷到前任的动态，还是会多看好几眼"),
    ("love", "喜欢一个人到失去自己，是不是很傻？"),
    ("love", "怎么判断自己是真喜欢还是一时上头？"),
]

JUDGE_SYS = ("你是资深心理陪伴产品评测专家。评审两位候选回复（A/B 顺序随机），"
             "只输出 JSON。评判不因回复长短加分，关注是否像真人陪伴者说的话。")
JUDGE_TMPL = """用户留言：{case}
候选回复 A：{a}
候选回复 B：{b}
请对 A、B 各打三项 1-5 整数分（5 最好）：
1) 适配度：是否切合用户此刻的情绪与具体处境（不跑题、不说教）
2) 自然度：像不像真人在说话（无机械感、无套话感、无总结腔）
3) 丰富度：表达是否饱满有层次（恰当的点拨或引用；为引而引不给高分）
再各判一位点：「生硬引用」= 是否出现硬贴式引经据典/堆砌名言/文不对题引用（true/false）。
只输出 JSON：{{"A":{{"适配度":n,"自然度":n,"丰富度":n,"生硬引用":true|false}},"B":{{...}},"winner":"A|B|平"}}"""


def read_llm_cfg():
    """从已 ignore 的 demo-config.js 动态读 base/key/model（只进内存，不进任何输出）。"""
    text = (ROOT / "src" / "js" / "demo-config.js").read_text(encoding="utf-8")
    base = re.search(r'base:\s*"([^"]+)"', text)
    key = re.search(r'key:\s*"([^"]+)"', text)
    model = re.search(r'model:\s*"([^"]+)"', text)
    if not (base and key and model):
        return None
    return {"base": base.group(1), "key": key.group(1), "model": model.group(1)}


def llm_call(cfg, messages, temperature=0.0, max_tokens=500):
    body = json.dumps({"model": cfg["model"], "messages": messages,
                       "temperature": temperature, "max_tokens": max_tokens}).encode("utf-8")
    req = urllib.request.Request(cfg["base"].rstrip("/") + "/chat/completions", data=body,
                                 headers={"Content-Type": "application/json",
                                          "Authorization": "Bearer " + cfg["key"]})
    with urllib.request.urlopen(req, timeout=90) as r:
        data = json.loads(r.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"].strip()


def parse_judge(raw):
    m = re.search(r"\{[\s\S]*\}", raw or "")
    if not m:
        return None
    try:
        j = json.loads(m.group(0))
    except Exception:
        return None
    for side in ("A", "B"):
        d = j.get(side) or {}
        for dim in DIMS:
            v = d.get(dim)
            if not isinstance(v, (int, float)) or not (1 <= v <= 5):
                return None
    if j.get("winner") not in ("A", "B", "平"):
        return None
    return j


def avg(rows, side, dim):
    xs = [r[side][dim] for r in rows if side in r]
    return round(sum(xs) / len(xs), 3) if xs else 0.0


def cited_rate(rows, side, entries):
    """引用检出率（报告级指标）：素材句去标点后按 8 字滑窗检测是否出现在回复里。
    粗糙但可复现；用途是证明"素材真的被用上了"（防"机制空转、评语全靠自然度"）。"""
    strip_re = re.compile(r"[\s，。！？、；：\"'（）()【】\[\]~·—…\u2011\-]")

    def hit(reply):
        r = strip_re.sub("", reply or "")
        for e in entries:
            q = strip_re.sub("", e.get("quote") or "")
            if len(q) < 6:
                continue
            for i in range(0, max(1, len(q) - 7), 4):
                if q[i:i + 8] in r:
                    return True
            if len(q) <= 8 and q in r:
                return True
        return False

    return round(sum(1 for x in rows if hit(x["%s_reply" % side])) / max(1, len(rows)), 3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8123")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    cases = CASES[:4] if args.smoke else CASES

    cfg = read_llm_cfg()
    if not cfg:
        print("QUOTE-EVAL-UNVERIFIED: demo-config.js 缺 base/key/model（密钥面不可用）")
        return 2
    try:
        from playwright.sync_api import sync_playwright
        from browser_engine import launch as be_launch
    except Exception as e:
        print("QUOTE-EVAL-UNVERIFIED: 浏览器环境不可达: %s" % e)
        return 2

    rng = random.Random(args.seed)
    rows, bad = [], []
    try:
        with sync_playwright() as p:
            b, engine = be_launch(p, label="quote-eval")
            pg = b.new_page(viewport={"width": 1200, "height": 860})
            pg.add_init_script(
                "try{localStorage.setItem('peiliao.cfg.v1',JSON.stringify("
                "{base:'%s',key:'%s',model:'%s',stream:false}))}catch(e){}"
                % (cfg["base"], cfg["key"], cfg["model"]))
            pg.goto(args.base + "/index.html", wait_until="load", timeout=45000)
            pg.wait_for_timeout(1500)
            has = pg.evaluate("!!(window.__XINYU_WIT_QUOTES__ && "
                              "window.__XINYU_WIT_QUOTES__.entries.length)")
            if not has:
                print("QUOTE-EVAL-UNVERIFIED: 页面未见 wit-quotes 数据件（先起含 src/data 的服务）")
                b.close()
                return 2

            def gen(text, mode):
                pg.evaluate(CLEAN)
                pg.evaluate(USE_NEW if mode == "new" else USE_OLD)
                reply = pg.evaluate(
                    "async (t) => { const r = await window.ChatAgent.respond(t); return r.reply; }",
                    text)
                return reply

            for i, (emo, text) in enumerate(cases):
                t0 = time.time()
                old_reply = gen(text, "old")
                new_reply = gen(text, "new")
                pg.evaluate(USE_NEW)   # 恢复
                # 洗牌：新/旧随机占 A/B 位
                new_is_a = rng.random() < 0.5
                a, bb = (new_reply, old_reply) if new_is_a else (old_reply, new_reply)
                judge = None
                for _try in range(3):
                    try:
                        raw = llm_call(cfg, [
                            {"role": "system", "content": JUDGE_SYS},
                            {"role": "user", "content": JUDGE_TMPL.format(case=text, a=a, b=bb)}])
                        judge = parse_judge(raw)
                        if judge:
                            break
                    except Exception:
                        pass
                    time.sleep(2)
                if not judge:
                    bad.append("用例 %d 评委三次均失败/非 JSON" % (i + 1))
                    continue
                map_ab = ({"new": "A", "old": "B"} if new_is_a else {"new": "B", "old": "A"})
                rows.append({
                    "i": i + 1, "emo": emo, "case": text,
                    "old": judge[map_ab["old"]], "new": judge[map_ab["new"]],
                    "winner": ("新版" if judge["winner"] == map_ab["new"] else
                               "旧版" if judge["winner"] == map_ab["old"] else "平"),
                    "old_reply": old_reply, "new_reply": new_reply,
                })
                print("  用例 %02d/%d [%s] 完成（%.0fs）" % (i + 1, len(cases), emo, time.time() - t0))
            b.close()
    except Exception as e:
        print("QUOTE-EVAL-UNVERIFIED: 运行异常: %s" % e)
        return 2

    if bad:
        print("QUOTE-EVAL-UNVERIFIED: %d 条评委失败 ⇒ 不判绿" % len(bad))
        for x in bad[:5]:
            print("   · " + x)
        return 2

    # 汇总
    summary = {"cases": len(rows), "seed": args.seed}
    for label, side in (("old", "old"), ("new", "new")):
        for dim in DIMS:
            summary["%s_%s" % (label, dim)] = avg(rows, side, dim)
    summary["new_win"] = sum(1 for r in rows if r["winner"] == "新版")
    summary["old_win"] = sum(1 for r in rows if r["winner"] == "旧版")
    summary["tie"] = sum(1 for r in rows if r["winner"] == "平")
    summary["new_hard_refuse"] = sum(1 for r in rows if r["new"].get("生硬引用")) / len(rows)
    summary["old_hard_refuse"] = sum(1 for r in rows if r["old"].get("生硬引用")) / len(rows)
    try:
        from quote_wiring_check import load_entries
        entries = load_entries() or []
    except Exception:
        entries = []
    summary["new_cite_rate"] = cited_rate(rows, "new", entries)
    summary["old_cite_rate"] = cited_rate(rows, "old", entries)

    fails = []
    for dim in DIMS:
        if summary["new_%s" % dim] + TOL < summary["old_%s" % dim]:
            fails.append("新版[%s]均分 %.2f 低于旧版 %.2f（容差 %.1f）"
                         % (dim, summary["new_%s" % dim], summary["old_%s" % dim], TOL))
    if summary["new_hard_refuse"] > HARD_REFUSE:
        fails.append("新版生硬引用率 %.0f%% > 上限 %.0f%%"
                     % (summary["new_hard_refuse"] * 100, HARD_REFUSE * 100))
    if entries and summary["new_cite_rate"] < 0.05:
        fails.append("新版引用检出率 %.0f%% < 5%%（信号过弱：素材未被真实使用，机制空转）"
                     % (summary["new_cite_rate"] * 100))

    # 报告与明细
    shots = ROOT / "_test" / "_shots"
    shots.mkdir(parents=True, exist_ok=True)
    detail = shots / "quotes_eval_detail.json"
    detail.write_text(json.dumps({"summary": summary, "rows": rows},
                                 ensure_ascii=False, indent=1), encoding="utf-8")
    report = ROOT / "交付物" / "表达语料库" / "验收报告.md"
    lines = ["# 表达语料库 · 全自动验收报告（r117）", "",
             "> 方法：30 条测试用例（6 情绪 × 5）× 新旧两版回复（单变量：quote 注入有无），"
             "LLM 评委盲评（A/B 顺序随机，种子 %d 可复现）。明细：`_test/_shots/quotes_eval_detail.json`。" % args.seed,
             "> 生成模型与评委阈值：见 `_test/quote_eval.py`（判据硬编码于脚本）。", "",
             "## 汇总", "",
             "| 维度 | 旧版（无注入） | 新版（含候选注入） |", "|---|---|---|"]
    for dim in DIMS:
        lines.append("| %s | %.2f | %.2f |" % (dim, summary["old_%s" % dim], summary["new_%s" % dim]))
    lines += ["| 生硬引用率 | %.0f%% | %.0f%% |" % (summary["old_hard_refuse"] * 100,
                                                     summary["new_hard_refuse"] * 100),
              "| 引用检出率 | %.0f%% | %.0f%% |" % (summary["old_cite_rate"] * 100,
                                                     summary["new_cite_rate"] * 100),
              "", "| 胜负 | 新版胜 %d / 旧版胜 %d / 平 %d |" % (summary["new_win"], summary["old_win"],
                                                              summary["tie"]), "",
              "## 判定", ""]
    if fails:
        lines.append("**QUOTE-EVAL-FAIL**：" + "；".join(fails))
    else:
        lines.append("**QUOTE-EVAL-PASS**：三维均分新版不低于旧版（容差内）且生硬引用率达标。")
    lines += ["", "## 逐条明细（节选：用例 / 新版胜否 / 新版三维 / 生硬引用）", "",
              "| # | 情绪 | 用例 | 胜者 | 适配 | 自然 | 丰富 | 新版生硬 |", "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append("| %d | %s | %s | %s | %s | %s | %s | %s |" % (
            r["i"], r["emo"], r["case"][:18], r["winner"],
            r["new"]["适配度"], r["new"]["自然度"], r["new"]["丰富度"],
            "是" if r["new"].get("生硬引用") else "否"))
    report.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("报告 -> 交付物/表达语料库/验收报告.md；明细 -> _test/_shots/quotes_eval_detail.json")
    print("QUOTE-EVAL-%s: cases=%d new[适配%.2f 自然%.2f 丰富%.2f] vs old[适配%.2f 自然%.2f 丰富%.2f] "
          "胜率新版=%d 生硬引用新版=%.0f%%" % (
              "FAIL" if fails else "PASS", len(rows),
              summary["new_适配度"], summary["new_自然度"], summary["new_丰富度"],
              summary["old_适配度"], summary["old_自然度"], summary["old_丰富度"],
              summary["new_win"], summary["new_hard_refuse"] * 100))
    for f in fails:
        print("   · " + f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())