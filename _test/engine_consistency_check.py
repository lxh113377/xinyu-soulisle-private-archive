# -*- coding: utf-8 -*-
"""J3 一致性守卫：JS 侧与 Java 侧情绪引擎必须逐项一致。

## 为什么需要（设计取舍，2026-09-22 定）
情绪引擎在两端各有一份实现：
  · `src/js/emotion-engine.js`（本地）—— 保留它是因为**离线时情绪识别不能归零**
    （服务端不可达仍要能识别，界面明示「仅词典（离线）」；`browser_check` 专测这条降级链路）
  · `server/.../EmotionLexicon.java`（服务端）—— `/api/chat` 链路与 `/api/emotion/eval` 用

所以**不能简单地删掉一份**（删本地 = 牺牲离线能力；删服务端 = 评测数字没有服务端承载）。
真正的问题是「两份实现靠人工维护必然**静默**分叉」——
本脚本把「静默重复」升级为「**受监控重复**」：改一边忘一边 → 当场失败。

## 判据（三层，任一不符即 FAIL）
  A 词表结构：lex / neg / deg / crisis **深度相等**
    ⚠️ 比对的是**有序列表**而非集合 —— 词表里 `难受`、`不` 存在**重复项**且会被**重复计分**，
       「顺手去重」会直接改变分数，必须能抓到这类改动。
  B 逐条预测：36 条评测集的 `{text, expect, pred}` 三元组**逐条**相等
    （只比汇总指标会漏掉「两条错误互相抵消」这类分叉）
  C 汇总指标：total / accuracy / crisis_recall / per_class / misses 相等

用法：
  ① 先起 Java 服务端在 8123（工作目录 = 项目根）
  ② python _test/engine_consistency_check.py
  ③ python _test/engine_consistency_check.py --selftest   # 判据自检：故意注入分叉，必须报 FAIL
"""
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BASE = "http://127.0.0.1:8123"


def get_json(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def js_side():
    out = subprocess.run(
        ["node", str(HERE / "engine_lexicon_dump.js")],
        capture_output=True, cwd=str(ROOT), timeout=60,
    )
    if out.returncode != 0:
        raise RuntimeError("node 导出失败: " + out.stderr.decode("utf-8", "replace")[:400])
    return json.loads(out.stdout.decode("utf-8"))


def java_side():
    lex = get_json(f"{BASE}/api/emotion/lexicon")
    ev = get_json(f"{BASE}/api/emotion/eval?detail=1")
    return lex, ev


def diff_words(a, b):
    """返回 (词表差异描述, 差异条数)。a=JS, b=Java"""
    problems = []
    if list(a.keys()) != list(b.keys()):
        problems.append(f"情绪键顺序/集合不同: JS={list(a.keys())} vs Java={list(b.keys())}")
    for k in a:
        if k not in b:
            problems.append(f"[{k}] Java 侧缺失")
            continue
        ja, jb = a[k], b[k]
        for field in ("weight", "color"):
            if ja.get(field) != jb.get(field):
                problems.append(f"[{k}].{field}: JS={ja.get(field)} vs Java={jb.get(field)}")
        wa, wb = ja.get("words"), jb.get("words")
        if wa != wb:
            if sorted(wa) == sorted(wb):
                problems.append(f"[{k}].words 顺序不同（影响可忽略但属分叉）")
            else:
                only_js = [w for w in wa if w not in wb]
                only_java = [w for w in wb if w not in wa]
                problems.append(f"[{k}].words 集合不同: 仅JS={only_js} 仅Java={only_java}")
        # 重复项守卫：词表内重复词会被重复计分，去重即改变分数
        dup_a = sorted({w for w in wa if wa.count(w) > 1})
        if dup_a and sorted(wa) != sorted(wb):
            problems.append(f"[{k}] 重复项集合变化（重复词会被重复计分）: JS={dup_a}")
    return problems


def compare(js, lex_java, ev_java):
    """返回 (判断通过?, 问题列表)"""
    problems = []

    # ── A 词表结构 ─────────────────────────────────────────────
    problems += diff_words(js["lex"], lex_java["lex"])
    for key in ("neg", "crisis"):
        if js[key] != lex_java[key]:
            problems.append(f"{key} 不同: JS={js[key]} vs Java={lex_java[key]}")
    if list(js["deg"].items()) != list(lex_java["deg"].items()):
        problems.append(f"deg 不同: JS={list(js['deg'].items())} vs Java={list(lex_java['deg'].items())}")

    # ── B 逐条预测 ─────────────────────────────────────────────
    jr, vr = js["results"], ev_java["results"]
    if len(jr) != len(vr):
        problems.append(f"逐条结果条数不同: JS={len(jr)} vs Java={len(vr)}")
    else:
        for a, b in zip(jr, vr):
            if a != b:
                problems.append(
                    f"逐条不一致: text={a.get('text')!r} JS={a.get('pred')} vs Java={b.get('pred')}"
                )

    # ── C 汇总指标 ─────────────────────────────────────────────
    for field in ("total", "accuracy", "crisis_recall", "per_class", "misses"):
        if js.get(field) != ev_java.get(field):
            problems.append(f"汇总 {field} 不同: JS={js.get(field)} vs Java={ev_java.get(field)}")

    return (not problems), problems


def summarize(js, lex_java, ev_java):
    print("=== 两端规模 ===")
    for k, v in js["lex"].items():
        print(f"  {k:<8} words={len(v['words']):<3} w={v['weight']} "
              f"| Java words={len(lex_java['lex'].get(k, {}).get('words', []))}")
    print(f"  neg={len(js['neg'])} deg={len(js['deg'])} crisis={len(js['crisis'])}")
    print("=== 汇总指标 ===")
    for field in ("total", "accuracy", "crisis_recall"):
        print(f"  {field:<14} JS={js.get(field)}  Java={ev_java.get(field)}")


def main():
    selftest = "--selftest" in sys.argv

    try:
        js = js_side()
        lex_java, ev_java = java_side()
    except Exception as e:
        print(f"🔴 环境不满足，无法比对：{e}")
        print("   检查：① node 可用 ② Java 服务端已起在 8123（工作目录=项目根）")
        return 2

    if selftest:
        print("【判据自检】故意注入一处词表分叉（JS 侧 joy 词数 -1）→ 期望报 FAIL")
        js["lex"]["joy"]["words"] = js["lex"]["joy"]["words"][:-1]
        js["results"][0]["pred"] = "__mutated__"

    summarize(js, lex_java, ev_java)
    ok, problems = compare(js, lex_java, ev_java)

    if selftest:
        if ok:
            print("🔴 SELFTEST-FAIL：注入分叉后判据仍报通过 ⇒ 判据无效（形同虚设）")
            return 1
        print(f"✅ SELFTEST-PASS：注入分叉后成功报出 {len(problems)} 个问题 ⇒ 判据非恒真")
        for p in problems[:4]:
            print("   ·", p)
        return 0

    if ok:
        print("✅ ENGINE-CONSISTENCY-PASS：JS 与 Java 两侧词表 + 逐条预测 + 汇总指标全等")
        return 0

    print(f"🔴 ENGINE-CONSISTENCY-FAIL：发现 {len(problems)} 处分叉")
    for p in problems:
        print("   ·", p)
    print("   处置：以 `src/js/emotion-engine.js` 为词表权威源，同步修正 `EmotionLexicon.java`（或反向），"
          "并重跑本脚本 + `_test/emotion_eval.js`")
    return 1


if __name__ == "__main__":
    sys.exit(main())
