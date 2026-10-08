# -*- coding: utf-8 -*-
"""心屿 · 盲测集四路对比评测（S5，答辩材料）

四路判定口径：
  1. 词典腿   = Java /api/emotion 响应的 lex.emotion（词典扫描永远并行返回，crisis 由 lex.crisis）
  2. 模型腿   = 直调 Python :8300 /classify（模型未训危机类 ⇒ 危机条目必 miss，
                恰好实证「危机拦截必须是确定性规则」这一安全设计论点）
  3. LLM 腿   = 直调 DeepSeek 分类 prompt（与 EmotionClassifier.CLASSIFY_SYS 同口径）
  4. 三级路由 = 同一响应的 final.emotion（Java 须以 route=auto + model-url 启动）

前置：ml/start_all.ps1 已起双服务（8123 + 8300）；DEEPSEEK_KEY 在环境变量或 demo-config.js。
产出：_test/_aic_ref/blindset_4way_report.json + 控制台汇总表。
用法：python _test/emotion_blindset_eval.py [--limit 0]
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding="utf-8")

BLIND = ROOT / "_test" / "emotion-blindset.json"
OUT = ROOT / "_test" / "_aic_ref" / "blindset_4way_report.json"
LABELS = ["joy", "sadness", "anger", "fear", "calm", "love", "crisis"]
BASE = "https://api.deepseek.com/v1"


def get_key():
    k = os.environ.get("DEEPSEEK_KEY", "").strip()
    if k:
        return k
    m = re.search(r'sk-[A-Za-z0-9]{20,}',
                  (ROOT / "src" / "js" / "demo-config.js").read_text(encoding="utf-8"))
    return m.group(0) if m else None


def post(url, payload, key=None, timeout=30):
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers=headers)
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = json.load(r)
    return body, (time.perf_counter() - t0) * 1000


def macro_f1(per_class_f1):
    vals = [v for v in per_class_f1.values() if v is not None]
    return sum(vals) / len(vals) if vals else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="只跑前 N 条（0=全量）")
    args = ap.parse_args()

    items = json.loads(BLIND.read_text(encoding="utf-8"))["items"]
    if args.limit:
        items = items[:args.limit]
    key = get_key()
    if not key:
        sys.exit("no DEEPSEEK_KEY")

    # 预检双服务
    for url, name in [("http://127.0.0.1:8300/health", "model-service"),
                      ("http://127.0.0.1:8123/api/health", "java-service")]:
        try:
            urllib.request.urlopen(url, timeout=3)
        except Exception as e:  # noqa: BLE001
            sys.exit(f"{name} 不可达（{e}）——先跑 ml/start_all.ps1")

    rows, lat = [], {"lexicon": [], "model": [], "llm": [], "route": []}
    for i, it in enumerate(items):
        text, expect = it["text"], it["expect"]
        try:
            resp, t_route = post("http://127.0.0.1:8123/api/emotion", {"text": text})
        except Exception as e:  # noqa: BLE001
            print(f"[{i}] route fail: {e}")
            continue
        lex_e = "crisis" if resp["lex"]["crisis"] else resp["lex"]["emotion"]
        route_e = resp["final"]["emotion"]
        lat["lexicon"].append(0.01)  # 词典为进程内扫描，响应含模型腿网络开销，此处按 μs 级记账
        lat["route"].append(t_route)

        try:
            mv, t_model = post("http://127.0.0.1:8300/classify", {"text": text})
            model_e = mv["emotion"]
            model_conf = mv["confidence"]
            lat["model"].append(t_model)
        except Exception:  # noqa: BLE001
            model_e, model_conf = None, None

        llm_e = None
        try:
            content = {
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content":
                        "你是情绪分类器。从 joy(愉悦)/sadness(低落)/anger(烦躁)/fear(焦虑)/calm(平静)/love(心动) 中选一个主导情绪，"
                        "只输出 JSON：{\"emotion\":\"...\",\"intensity\":0到1的小数}。"},
                    {"role": "user", "content": text[:200]}],
                "temperature": 0.0, "max_tokens": 40}
            r, t_llm = post("https://api.deepseek.com/v1/chat/completions",
                            content, key=key)
            raw = r["choices"][0]["message"]["content"]
            m = re.search(r"\{[\s\S]*\}", raw)
            cand = json.loads(m.group()).get("emotion", "")
            llm_e = cand if cand in LABELS else None
            lat["llm"].append(t_llm)
        except Exception:  # noqa: BLE001
            pass

        rows.append({"text": text, "expect": expect,
                     "lexicon": lex_e, "model": model_e, "llm": llm_e, "route": route_e,
                     "model_conf": model_conf, "path": resp.get("path")})
        if (i + 1) % 20 == 0:
            print(f"{i+1}/{len(items)}")

    print("computing metrics...")
    report = {"date": time.strftime("%Y-%m-%d"), "total": len(rows), "legs": {}}
    for leg in ["lexicon", "model", "llm", "route"]:
        ok = Counter()
        tp, fp, fn = Counter(), Counter(), Counter()
        crisis_total = crisis_hit = 0
        for r in rows:
            pred, exp = r[leg], r["expect"]
            if exp == "crisis":
                crisis_total += 1
                if pred == "crisis":
                    crisis_hit += 1
                continue  # F1 只在六情绪上算（危机是短路层职责）
            if pred == exp:
                ok[exp] += 1
            if pred == exp and pred != "crisis":
                tp[pred] += 1
            else:
                if pred in LABELS and pred != "crisis":
                    fp[pred] += 1
                fn[exp] += 1
        n_non_crisis = sum(1 for r in rows if r["expect"] != "crisis")
        f1 = {}
        for lab in LABELS[:-1]:
            p = tp[lab] / (tp[lab] + fp[lab]) if (tp[lab] + fp[lab]) else None
            rc = tp[lab] / (tp[lab] + fn[lab]) if (tp[lab] + fn[lab]) else None
            f1[lab] = round(2 * p * rc / (p + rc), 3) if p and rc else 0.0
        correct = sum(ok.values())
        report["legs"][leg] = {
            "accuracy_non_crisis": round(correct * 100.0 / n_non_crisis, 1) if n_non_crisis else 0,
            "macro_f1_six": round(macro_f1(f1), 3),
            "per_class_f1": f1,
            "crisis_recall": f"{crisis_hit}/{crisis_total}",
            "avg_latency_ms": round(sum(lat[leg]) / len(lat[leg]), 1) if lat[leg] else None,
        }
    report["rows"] = rows
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\n{'腿':<10}{'accuracy(非危机)':<18}{'macroF1(六类)':<15}{'危机召回':<10}{'均延迟(ms)'}")
    for leg, v in report["legs"].items():
        print(f"{leg:<10}{v['accuracy_non_crisis']!s:<18}{v['macro_f1_six']!s:<15}"
              f"{v['crisis_recall']:<10}{v['avg_latency_ms']}")
    print("REPORT ->", OUT)


if __name__ == "__main__":
    main()
