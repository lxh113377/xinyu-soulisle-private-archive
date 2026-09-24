# -*- coding: utf-8 -*-
"""共情策略表守卫：`src/data/emotion-strategy.js` 与词表 SSOT 必须成对成立。

## 为什么需要（2026-09-24 对标轮）
共情模板原先硬编码在 `chat-agent.js`，"新增一种情绪"要改代码 —— 与词表 SSOT 化（e79025b）方向不一致。
抽表之后新增情绪 = 改两个数据文件（词表 + 策略表）。**新的风险变成"只改了一个"**：
词表加了 `envy` 而策略表没加 ⇒ 运行时 `strategyOf()` 静默回落 calm，
用户说"我嫉妒同桌"得到的却是"平平淡淡的一天也挺好"。这类缺陷不会报错，只会答非所问。

## 判据（任一不符即 FAIL）
  A 两份数据文件都是**纯 JSON 字面量**（禁 JS 表达式，否则 Java/Python 侧无法同构解析）
  B 键序对账：`strategy` 的插入序 == 词表 `lex` 的插入序（平分兜底顺序依赖它）
  C 覆盖完备：词表每个情绪在策略表必有 `lead` + 非空 `templates`，且参数在合法区间
  D 反向不遗：策略表不得有词表没有的情绪键（否则 LLM 会输出词典侧无法着色的情绪）
  E `fallback` 必须存在；`classify.sys` 必须逐个提到所有情绪键（分类器提示词与表脱节=选了个表里没有的）
  F 危机话术：`crisis` 不在 `strategy` 内（走独立分支），且热线清单 ≥3 条且都出现在正文里

用法：
  python _test/strategy_check.py
  python _test/strategy_check.py --selftest   # 判据自检：故意注入分叉，必须报 FAIL（防判据恒真）
"""
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
LEX = ROOT / "src" / "data" / "emotion-lexicon.js"
STR = ROOT / "src" / "data" / "emotion-strategy.js"


def load_global(path, global_name):
    """从 `window.__X__ = { ... };` 里取出 JSON 字面量并解析。解析失败即判 FAIL（不静默跳过）。

    「必须是纯 JSON 字面量」这条由 `json.loads` 本身来证：字符串相加（`"a" + "b"`）、
    标识符、行注释都会让它抛错 —— 比正则更可靠（正则会把 URL 里的 `//` 误判成注释）。
    """
    text = path.read_text(encoding="utf-8")
    # 锚点必须按「全局赋值」定位，不能用裸 `index("{")`：
    # 词表头注释里写着 `${XINYU_LEXICON}`，那个 `{` 在前，会让切片起点跑到注释里（实测踩过）。
    m = re.search(re.escape(global_name) + r"\s*=\s*", text)
    if not m:
        raise ValueError(f"{path.name}: 未找到全局挂载 {global_name}")
    start = text.index("{", m.end())
    end = text.rindex("}")
    body = text[start:end + 1]
    try:
        return json.loads(body)
    except Exception as e:
        raise ValueError(f"{path.name}: 文件体不是纯 JSON 字面量（禁 JS 表达式/注释/多余字符）→ {e}")


def check(lex, strat):
    problems = []
    emotions = list(lex["lex"].keys())
    skeys = list(strat.get("strategy", {}).keys())

    # B 键序对账
    if emotions != skeys:
        only_lex = [e for e in emotions if e not in skeys]
        only_str = [e for e in skeys if e not in emotions]
        if only_lex or only_str:
            problems.append(f"情绪键集合不匹配: 仅词表={only_lex} 仅策略表={only_str}")
        elif emotions != skeys:
            problems.append(f"情绪键**顺序**不同（影响平分兜底）: 词表={emotions} 策略表={skeys}")

    # C 覆盖完备
    for e in emotions:
        s = strat.get("strategy", {}).get(e)
        if not s:
            continue                      # 已由 B 报出，避免重复
        if not str(s.get("lead", "")).strip():
            problems.append(f"[{e}] 缺 lead（共情要点）→ SYSTEM 提示会退化成通用套话")
        tpl = s.get("templates")
        if not isinstance(tpl, list) or not tpl or not all(str(t).strip() for t in tpl):
            problems.append(f"[{e}] templates 缺失或含空串 → 离线降级无话可说")
        t = s.get("temperature")
        if not isinstance(t, (int, float)) or not (0 < t <= 2):
            problems.append(f"[{e}] temperature 非法: {t!r}（须在 0~2）")
        # maxTokens 允许缺省（走 defaultMaxTokens），但一旦显式写就必须合法
        if "maxTokens" in s:
            m = s.get("maxTokens")
            if not isinstance(m, int) or not (16 <= m <= 4096):
                problems.append(f"[{e}] maxTokens 非法: {m!r}")
    dm = strat.get("defaultMaxTokens")
    if not isinstance(dm, int) or not (16 <= dm <= 4096):
        problems.append(f"defaultMaxTokens 非法: {dm!r}（缺省 maxTokens 的情绪靠它兜底）")

    # E fallback + 分类器提示词一致性
    fb = strat.get("fallback")
    if fb not in skeys:
        problems.append(f"fallback={fb!r} 不在 strategy 键内 → 回落会取到 undefined")
    sysprompt = strat.get("classify", {}).get("sys", "")
    missing_in_sys = [e for e in skeys if e not in sysprompt]
    if missing_in_sys:
        problems.append(f"classify.sys 未提及这些情绪键（LLM 不可能输出它们）: {missing_in_sys}")

    # F 危机话术
    if "crisis" in skeys:
        problems.append("crisis 不应出现在 strategy 内：危机走独立转介分支（不调 LLM）")
    cr = strat.get("crisis", {})
    body = cr.get("reply", "")
    lines = cr.get("hotlines", [])
    if len(body) < 40:
        problems.append("危机话术过短")
    if not isinstance(lines, list) or len(lines) < 3:
        problems.append(f"热线清单需 ≥3 条，实际 {lines!r}")
    else:
        absent = [n for n in lines if n not in body]
        if absent:
            problems.append(f"热线号未出现在话术正文里（用户看不到号码）: {absent}")

    # 其余必备字段
    if not str(strat.get("persona", "")).strip():
        problems.append("缺 persona")
    if not isinstance(strat.get("rules"), list) or len(strat.get("rules", [])) < 3:
        problems.append("rules 需 ≥3 条共情约束")
    if not lex.get("crisis"):
        problems.append("词表 crisis 列表为空 → 危机拦截形同虚设")
    return problems


def main():
    selftest = "--selftest" in sys.argv
    try:
        lex = load_global(LEX, "window.__XINYU_LEXICON__")
        strat = load_global(STR, "window.__XINYU_STRATEGY__")
    except Exception as e:
        print(f"🔴 STRATEGY-CHECK-FAIL（读取/解析）: {e}")
        return 1

    if selftest:
        print("【判据自检】故意注入两处分叉：删掉 love 策略 + 抹掉 crisis 热线 → 期望 FAIL")
        strat["strategy"].pop("love", None)
        strat["crisis"]["hotlines"] = []

    problems = check(lex, strat)
    emotions = list(lex["lex"].keys())
    print(f"词表情绪 {len(emotions)} 类: {emotions}")
    print(f"策略表情绪 {len(strat['strategy'])} 类 | 模板条数 "
          f"{ {k: len(v.get('templates', [])) for k, v in strat['strategy'].items()} }")
    print(f"fallback={strat.get('fallback')} | rules={len(strat.get('rules', []))} 条")

    if selftest:
        if not problems:
            print("🔴 SELFTEST-FAIL：注入分叉后判据仍通过 ⇒ 判据恒真（形同虚设）")
            return 1
        print(f"✅ SELFTEST-PASS：注入分叉后报出 {len(problems)} 个问题 ⇒ 判据非恒真")
        for p in problems[:4]:
            print("   ·", p)
        return 0

    if problems:
        print(f"🔴 STRATEGY-CHECK-FAIL：{len(problems)} 处问题")
        for p in problems:
            print("   ·", p)
        print("   处置：策略表与词表必须成对修改（加情绪=两处都加），改完重跑本脚本。")
        return 1
    print("✅ STRATEGY-CHECK-PASS：策略表与词表键序一致、覆盖完备、危机话术与分类器提示词自洽")
    return 0


if __name__ == "__main__":
    sys.exit(main())
