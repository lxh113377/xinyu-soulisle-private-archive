# -*- coding: utf-8 -*-
"""quote_citation_check.py — 引用标记输出面核对判据（r133）

验的是什么（对应老大要求 #2「从机制上避免强行插入」的最后一环）：
  知识面（注入哪些条目）由 quote_wiring_check 把关；本件管**输出面 + 接线**。
  r132 建了 verifyCitations 但**零调用点** —— 函数在、效果不在，模型可自行标
  〔依据:PSY-XX-999·A〕凭空编出处。r133 把它接进 onlineReply。

  实现的既定契约（src/js/chat-agent.js verifyCitations，本判据照它验，**不改实现**）：
    ① 命中注入集且级一致 → 原样保留，matched++
    ② 命中但级不符 → 按库里真实级**更正**并写明「模型标X，已更正」（挡 E 冒充 A）
    ③ 未命中 → 改为〔依据:<编号>·未查证〕，**编号原样保留不擅自改写**，unmatched++
    三种结局一律**只改标记本体、逐字保留其余文本**（不删原文）
    used 为空（未注入/离线/降级）⇒ 任何标记都算未命中

  腿分三类：真腿（正常路径必过）+ 接线腿（零调用点必须转红）+ 不变量腿（正文逐字不变）。

用法: python _test/quote_citation_check.py [--selftest]
退出码: 0=PASS 1=FAIL 2=环境未验证
"""
import json
import re
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / "src" / "js" / "chat-agent.js"

# 把 chat-agent.js 里的 verifyCitations 原样抽出来在 node 里跑（单一真相源，判据零复制实现）
HARNESS = r"""
const __RAW__ = require("fs").readFileSync(__ARG0__, "utf8");
const __M__ = __RAW__.match(/  const CITE_RE = [\s\S]*?function verifyCitations\(reply, used\) \{[\s\S]*?\n  \}\n/);
if (!__M__) { console.log(JSON.stringify({__missing__: true})); process.exit(0); }
eval(__M__[0]);
const CASES = JSON.parse(__ARG1__);
const out = CASES.map(c => {
  try { return { name: c.name, ok: true, r: verifyCitations(c.text, c.used) }; }
  catch (e) { return { name: c.name, ok: false, err: String(e) }; }
});
console.log(JSON.stringify(out));
"""


def run_cases(cases):
    js = (HARNESS.replace("__ARG0__", json.dumps(str(AGENT)))
                .replace("__ARG1__", json.dumps(json.dumps(cases, ensure_ascii=False))))
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=str(ROOT), timeout=90)
    if r.returncode != 0:
        raise RuntimeError("node 退出 %d: %s" % (r.returncode, (r.stderr or "")[:400]))
    line = (r.stdout or "").strip().splitlines()[-1]
    data = json.loads(line)
    if isinstance(data, dict) and data.get("__missing__"):
        raise RuntimeError("chat-agent.js 里找不到 CITE_RE/verifyCitations —— 实现缺失，判据不得放行")
    return data


def legs():
    res = []

    def leg(name, ok, detail=""):
        res.append((name, bool(ok), detail))

    used = [{"id": "PSY-ANX-001", "level": "A"}, {"id": "PSY-SLP-002", "level": "A"}]
    cases = [
        # ① 命中 + 级一致 ⇒ 原样保留
        {"name": "命中保留", "text": "你现在的紧绷很真实。〔依据:PSY-ANX-001·A〕", "used": used},
        # ② 命中但级不符 ⇒ 更正并写明
        {"name": "级不符更正", "text": "先睡够。〔依据:PSY-ANX-001·C〕", "used": used},
        # ③ 未命中（不存在编号）⇒ 标未查证、编号保留、正文不动
        {"name": "未命中标注", "text": "这很正常。〔依据:PSY-XXX-999·A〕你要允许自己慢一点。", "used": used},
        # ④ 零标记 ⇒ 逐字返回
        {"name": "零标记不变", "text": "今天先歇一歇吧。", "used": used},
        # ⑤ 崩溃面：used 空 / null ⇒ 不抛栈，全部算未命中
        {"name": "空注入集", "text": "〔依据:PSY-ANX-001·A〕你好", "used": []},
        {"name": "null注入集", "text": "〔依据:PSY-ANX-001·A〕你好", "used": None},
        # ⑥ 正文误伤面：括号/中点/「依据」字样不得被动
        {"name": "正文括号不误伤", "text": "他说（真的会好）·我不信。", "used": used},
        {"name": "正文依据字样不误伤", "text": "你说的「依据」是指什么呢？", "used": used},
        {"name": "正文方括号不误伤", "text": "参考 [1] 这篇。", "used": used},
        # ⑦ 多标记混合
        {"name": "混合标记", "text": "甲〔依据:PSY-ANX-001·A〕乙〔依据:PSY-ZZZ-999·B〕丙", "used": used},
        # ⑧ 计数口径
        {"name": "计数", "text": "甲〔依据:PSY-ANX-001·A〕乙〔依据:PSY-ZZZ-999·B〕", "used": used},
        # ⑨ 半角冒号（全角/半角都该认）
        {"name": "半角冒号", "text": "〔依据:PSY-ANX-001·A〕", "used": used},
        # ⑩ 全文角括号
        {"name": "全角冒号", "text": "〔依据：PSY-ANX-001·A〕", "used": used},
        # ⑪ 大小写
        {"name": "小写编号", "text": "〔依据:psy-anx-001·A〕", "used": used},
        # ⑫ 无等级形态：编号对上了只是没标级 ⇒ 按库里真实级补齐（不是未命中）
        {"name": "无等级标记", "text": "〔依据:PSY-ANX-001〕", "used": used},
    ]
    try:
        got = run_cases(cases)
    except Exception as e:
        print("QUOTE-CITATION-UNVERIFIED: %s" % e)
        return None
    by = {g["name"]: g for g in got}

    a = by["命中保留"]
    leg("命中+级一致原样保留",
        a["ok"] and "〔依据:PSY-ANX-001·A〕" in a["r"]["text"]
        and a["r"]["matched"] == 1 and a["r"]["unmatched"] == 0)

    b = by["级不符更正"]
    leg("级不符按库里真实级更正并写明",
        b["ok"] and "已更正" in b["r"]["text"] and "·C〕" not in b["r"]["text"]
        and "先睡够。" in b["r"]["text"], b["r"]["text"] if b["ok"] else b.get("err", ""))

    c = by["未命中标注"]
    leg("未命中标「未查证」且编号原样保留",
        c["ok"] and "PSY-XXX-999" in c["r"]["text"] and "未查证" in c["r"]["text"]
        and "你要允许自己慢一点。" in c["r"]["text"] and c["r"]["unmatched"] == 1,
        c["r"]["text"] if c["ok"] else c.get("err", ""))

    d = by["零标记不变"]
    leg("零标记逐字不变且计数为 0",
        d["ok"] and d["r"]["text"] == "今天先歇一歇吧。"
        and d["r"]["checked"] == 0 and d["r"]["matched"] == 0)

    e = by["空注入集"]
    leg("used 空 ⇒ 全判未命中且不抛栈",
        e["ok"] and "未查证" in e["r"]["text"] and e["r"]["matched"] == 0 and e["r"]["unmatched"] == 1)
    f = by["null注入集"]
    leg("used null ⇒ 不抛栈", f["ok"] and "未查证" in f["r"]["text"])

    leg("正文圆括号不误伤", by["正文括号不误伤"]["ok"]
        and by["正文括号不误伤"]["r"]["text"] == "他说（真的会好）·我不信。")
    leg("正文「依据」字样不误伤", by["正文依据字样不误伤"]["ok"]
        and by["正文依据字样不误伤"]["r"]["text"] == "你说的「依据」是指什么呢？")
    leg("正文方括号数字不误伤", by["正文方括号不误伤"]["ok"]
        and by["正文方括号不误伤"]["r"]["text"] == "参考 [1] 这篇。")

    g = by["混合标记"]
    leg("混合标记逐个处理（命中留/未命中标）",
        g["ok"] and "〔依据:PSY-ANX-001·A〕" in g["r"]["text"]
        and "PSY-ZZZ-999·未查证" in g["r"]["text"]
        and g["r"]["text"].startswith("甲") and g["r"]["text"].endswith("丙")
        and g["r"]["matched"] == 1 and g["r"]["unmatched"] == 1,
        g["r"]["text"] if g["ok"] else g.get("err", ""))

    h = by["计数"]
    leg("checked/matched/unmatched 三计数自洽",
        h["ok"] and h["r"]["checked"] == 2 and h["r"]["matched"] == 1
        and h["r"]["unmatched"] == h["r"]["checked"] - h["r"]["matched"])

    i = by["半角冒号"]
    leg("半角冒号形态可识别", i["ok"] and i["r"]["matched"] == 1, i["r"]["text"] if i["ok"] else "")
    j = by["全角冒号"]
    leg("全角冒号形态可识别", j["ok"] and j["r"]["matched"] == 1, j["r"]["text"] if j["ok"] else "")
    k = by["小写编号"]
    leg("小写编号按大写归一后仍可命中", k["ok"] and k["r"]["matched"] == 1,
        k["r"]["text"] if k["ok"] else "")
    n = by["无等级标记"]
    leg("无等级标记按库里真实级补齐后算命中", n["ok"] and n["r"]["matched"] == 1
        and n["r"]["text"] == "〔依据:PSY-ANX-001·A〕", n["r"]["text"] if n["ok"] else "")

    # 不变量：多标记 + 换行/制表/重复空格，标记之外逐字不变
    inv = run_cases([{"name": "不变量", "used": [],
                      "text": "前\n后〔依据:QTE-A-001·A〕中  尾\t〔依据:QTE-A-002·A〕"}])
    t = inv[0]
    leg("标记之外文本逐字不变（换行/双空格/制表）",
        t["ok"] and t["r"]["text"] == "前\n后〔依据:QTE-A-001·未查证〕中  尾\t〔依据:QTE-A-002·未查证〕",
        repr(t["r"]["text"]) if t["ok"] else t.get("err", ""))

    # 接线腿：r132 的真缺陷 = 定义了但零调用点
    raw = AGENT.read_text(encoding="utf-8")
    defs = len(re.findall(r"function verifyCitations\s*\(", raw))
    calls = len(re.findall(r"(?<!function )\bverifyCitations\s*\(", raw))
    leg("verifyCitations 有且仅有一份定义（禁重复实现）", defs == 1, "defs=%d" % defs)
    leg("verifyCitations 已接进调用链（r132 缺陷：零调用点）", calls >= 1, "calls=%d" % calls)
    leg("调用点在 onlineReply 内（改写最终回复）",
        re.search(r"onlineReply[\s\S]{0,900}?verifyCitations\(", raw) is not None)

    # 遥测出口腿：引用消费计数须能回到 respond() 返回值
    leg("respond 返回值含引用消费遥测",
        all(k in raw for k in ("citeChecked", "citeMatched", "citeUnmatched")))
    # crisis 分支不得带引用口径（危机轮零注入）
    seg = re.search(r'if \(emo === "crisis"\) \{[\s\S]*?\n    \}', raw)
    leg("危机分支不含引用口径",
        seg is not None and "citeChecked" not in seg.group(0) and "verifyCitations" not in seg.group(0))
    # 流式口径：流式不改写（避免屏幕文字与内存不一致），但仍回计数
    leg("流式不改写、只回计数（citeApplied 口径显式）",
        "citeApplied" in raw and re.search(r"streamed\s*\?\s*raw\s*:\s*v\.text", raw) is not None)

    return res


def main():
    if "--selftest" in sys.argv:
        return run_selftest()
    res = legs()
    if res is None:
        return 2
    bad = [r for r in res if not r[1]]
    for name, ok, detail in res:
        print("  %s  %s%s" % ("PASS" if ok else "FAIL", name, ("  <- " + detail) if (detail and not ok) else ""))
    if bad:
        print("QUOTE-CITATION-FAIL: %d/%d 腿通过，失败 %d 条" % (len(res) - len(bad), len(res), len(bad)))
        return 1
    print("QUOTE-CITATION-PASS: %d/%d 腿（三结局/只改标记/不抛栈/接线/遥测/危机零注入）" % (len(res), len(res)))
    return 0


def run_selftest():
    """可逆注入自证：故意把产品面的门/接线弄坏，本判据必须逐条转红。"""
    src = AGENT.read_text(encoding="utf-8")
    base_src = src
    cases = [{"name": "未命中标注", "text": "这很正常。〔依据:PSY-XXX-999·A〕你要允许自己慢一点。",
              "used": [{"id": "PSY-ANX-001", "level": "A"}]}]
    try:
        base = run_cases(cases)[0]
    except Exception as e:
        print("QUOTE-CITATION-SELFTEST-UNVERIFIED: %s" % e)
        return 2

    results = []

    def mut(name, old, new, probe):
        nonlocal src
        if old not in src:
            results.append((name, False, "锚点未找到"))
            return
        try:
            AGENT.write_text(src.replace(old, new, 1), encoding="utf-8")
            got = run_cases(probe)[0]
            results.append((name, bool(probe_ok(got)), got))
        except Exception as e:
            results.append((name, False, str(e)[:80]))
        finally:
            src = base_src
            AGENT.write_text(base_src, encoding="utf-8")

    def probe_ok(got):
        return got.get("ok") and "PSY-XXX-999" not in got["r"]["text"]

    # 变异1：把「未命中就标注」改成「未命中原样放过」⇒ 必须转红
    mut("变异1 未命中原样放过→红",
        'if (!real) return "〔依据:" + key + "·未查证〕";',
        'if (!real) return whole;', cases)
    # 变异2：删掉调用点（还原 r132 缺陷）⇒ 接线腿必须转红
    mut("变异2 调用点摘除→红",
        "const v = verifyCitations(raw, sys.kbUsed);",
        "const v = { text: raw, checked: 0, matched: 0, unmatched: 0 };", cases)
    # 变异3：正则只认全角冒号 ⇒ 半角/无等级腿须红
    mut("变异3 只认全角冒号→红",
        "〔依据[:：]", "〔依据：", cases)
    # 变异4：吞掉标记之外正文 ⇒ 不变量腿须红（锚点只动函数体，不碰 CITE_RE 那行，
    # 否则抽取正则匹配不到、判据自己崩而不是"转红"——那是自伤不是门）
    mut("变异4 吞掉正文→红",
        "      checked++;",
        '      if (1) return "";\n      checked++;', cases)

    # 接线腿的独立验证：删掉调用点后接线腿必红（不靠 probe）
    wiring_red = False
    try:
        AGENT.write_text(base_src.replace("const v = verifyCitations(raw, sys.kbUsed);",
                                          "const v = { text: raw, checked: 0, matched: 0, unmatched: 0 };"),
                         encoding="utf-8")
        res2 = legs()
        wiring_red = (res2 is not None) and any(
            n == "verifyCitations 已接进调用链（r132 缺陷：零调用点）" and not ok for n, ok, _ in res2)
    except Exception as e:
        print("  接线腿变异异常: %s" % str(e)[:120])
    finally:
        AGENT.write_text(base_src, encoding="utf-8")

    restored = AGENT.read_bytes() == base_src.encode("utf-8")
    ok_all = base["ok"] and "PSY-XXX-999" not in base["r"]["text"]
    names = [r[0] for r in results]
    print("  %s  变异1 未命中原样放过→红" % ("PASS" if dict(results)["变异1 未命中原样放过→红"] else "FAIL"))
    print("  %s  变异2 调用点摘除→红" % ("PASS" if dict(results)["变异2 调用点摘除→红"] else "FAIL"))
    print("  %s  变异3 只认全角冒号→红" % ("PASS" if dict(results)["变异3 只认全角冒号→红"] else "FAIL"))
    print("  %s  变异4 吞掉正文→红" % ("PASS" if dict(results)["变异4 吞掉正文→红"] else "FAIL"))
    print("  %s  接线腿对「零调用点」转红" % ("PASS" if wiring_red else "FAIL"))
    print("  %s  磁盘还原（逐字节）" % ("PASS" if restored else "FAIL"))
    for n, ok, det in results:
        if not ok:
            print("    · %s 未转红: %s" % (n, str(det)[:160]))
    if ok_all and all(r[1] for r in results) and wiring_red and restored:
        print("QUOTE-CITATION-SELFTEST-PASS: 6 腿（判据非恒真）")
        return 0
    print("QUOTE-CITATION-SELFTEST-FAIL: 变异腿未全部转红")
    return 1


if __name__ == "__main__":
    sys.exit(main())