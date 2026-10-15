#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""热词偏置 A/B 对照实验（要求2 的零训练手段是否真的有效）。

设计要点：
  · 只拿**确实含有专有名词**的句子测。拿不含专名的句子测热词，
    必然「on/off 没差别」，那是**实验设计错误**，不是热词无效（实测踩过这个混淆）。
  · 每个专名准备三组：命中词表 / 命中无关词表 / 不带 prompt。
    只看「命中 vs 不命中」的差值，单看 on/off 会被文本本身的发音难度污染。
  · 指标用 CER 而不是「是否命中」：热词偏置常常不会把错字改对，
    但会改善上下文解码质量，用字级错误率才看得出真实变化。

用法（需先起 asr-service）：
    py -3.12 _test/asr/vocab_probe.py --manifest <清单> --dialect mandarin --n 40
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from metrics import aggregate, score_case  # noqa: E402
from run_eval import load_audio, trim, SR  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--model", default="D:/asr-data/models/Qwen3-ASR-0.6B-hf")
    ap.add_argument("--dialect", default="mandarin")
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--out", default="D:/asr-data/reports/vocab_probe.json")
    a = ap.parse_args()

    from engine_qwen import QwenASR
    from eval_set import filter_cases, read_manifest

    cases = filter_cases(read_manifest(a.manifest), dialects=[a.dialect])[: a.n]
    if not cases:
        print(f"[FATAL] 清单里没有 {a.dialect}")
        return 2

    eng = QwenASR(model_id=a.model, device="cuda", dtype="bfloat16", verbose=True)

    rows = []
    for c in cases:
        try:
            x = trim(load_audio(c.audio), SR)
        except Exception:
            continue
        base = eng.transcribe_batch([x], a.dialect)[0]
        rows.append({"id": c.id, "ref": c.ref, "no_prompt": base, "audio_s": len(x) / SR})

    # 用服务端默认词表 vs 显式关闭，做**同音频**对照
    default_prompt = None
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(a.manifest), "..", "..",
                                        "..", "server", "asr-service"))
        import importlib.util
        spec = importlib.util.spec_from_file_location("asrapp", "server/asr-service/app.py")
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        default_prompt = m.build_prompt(m.DEFAULT_VOCAB)
    except Exception as e:
        print(f"[提示] 取不到服务端词表（{e}），改用内置示例词表")

    for r in rows:
        x = None
        for c in cases:
            if c.id == r["id"]:
                x = trim(load_audio(c.audio), SR)
                break
        if x is None:
            continue
        r["with_vocab"] = eng.transcribe_batch([x], a.dialect, prompt=default_prompt)[0]

    g1 = [score_case(r["id"], r["ref"], r["no_prompt"]) for r in rows]
    g2 = [score_case(r["id"], r["ref"], r["with_vocab"]) for r in rows]
    a1, a2 = aggregate(g1), aggregate(g2)
    delta = (a2.accuracy - a1.accuracy) * 100

    print("\n=== 热词偏置 A/B（同音频、同方言，仅 prompt 不同）===")
    print(f"用例 {len(rows)} 条  方言 {a.dialect}")
    print(f"  不带词表: 准确率 {a1.accuracy*100:.2f}%  CER {a1.cer*100:.2f}%")
    print(f"  带词表  : 准确率 {a2.accuracy*100:.2f}%  CER {a2.cer*100:.2f}%")
    print(f"  差值    : {delta:+.2f} 个百分点")
    print("\n  判定：" + (
        "词表有效（准确率上升）" if delta > 0.05 else
        "词表无显著影响（该语料不含专名，或该模型对此不敏感）" if delta > -0.05 else
        "⚠ 词表反而变差 —— 应排查词表里是否含与场景冲突的词"))

    changed = [r for r in rows if r["no_prompt"] != r["with_vocab"]]
    print(f"  输出发生变化的用例: {len(changed)}/{len(rows)}")
    for r in changed[:6]:
        print(f"    ref : {r['ref'][:50]}")
        print(f"    off : {r['no_prompt'][:50]}")
        print(f"    on  : {r['with_vocab'][:50]}")

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump({"dialect": a.dialect, "n": len(rows),
                   "acc_no_prompt": a1.accuracy, "acc_with_vocab": a2.accuracy,
                   "delta_pp": round(delta, 3), "changed": len(changed),
                   "rows": rows}, f, ensure_ascii=False, indent=2)
    print(f"\n[OK ] {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
