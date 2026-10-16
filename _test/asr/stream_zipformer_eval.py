#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B2 流式选型评测（spike §16）：sherpa-onnx streaming-zipformer 双语，同尺跑 KeSpeech 232x3。

为什么单独立一件而不是塞进 run_eval.py：run_eval 的引擎面是 Qwen3（transformers 常驻 GPU），
本件引擎面是 sherpa-onnx 的**流式** OnlineRecognizer（CPU int8 即可），两者的取流方式不同
（批式一口喂 vs 60ms 块喂 + 端点检测）。硬塞会让 run_eval 长出第二条引擎分支，违背它
「清单驱动、引擎单一」的形状。

单一口径源的保证（与 §14/§15 读数可比的前提）：本件**不自己实现任何评分**，
直接 import 同目录的 scenarios（同一份场景合成、同一随机行为）、metrics.score_case/aggregate
（同一份归一化与编辑距离）、run_eval.load_audio/trim（同一份取流）。改评分只需改那三件，
本件自动跟随 —— 这是「两份尺子必然漂移」红线的正面规避。

前置（一次性，约 190MB，不进仓）：
    D:/xinyu-ml/asr-venv/Scripts/python.exe _test/asr/dl_stream_model.py
    （模型 = csukuangfj/sherpa-onnx-streaming-zh-en-2023-02-20，hf-mirror 可达；
      卡 front-matter 标 apache-2.0 但正文仅 296B，正式采用前需补训练数据许可复核）
    落地目录：D:/asr-data/models/sherpa-streaming-zh-en/{encoder,decoder,joiner,tokens}

用法：
    D:/xinyu-ml/asr-venv/Scripts/python.exe _test/asr/stream_zipformer_eval.py
输出：D:/asr-data/reports/r186_stream_zipformer.json

⚠ 不进电池（先例同 asr_chain_check/engine_switch_check：要真下模型才能跑，
  接进整跑等于把「没装 sherpa-onnx 的机器」常年刷成红项）。r186 一手读数：
  12/12 组 err=0，mandarin/clean CER 32.45%（同尺 Qwen3 为 5.06%）⇒ §16 判负。

"""

import json, os, sys, time, statistics
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scenarios import SCENARIOS, apply_scenario, SR
from metrics import aggregate, score_case
from run_eval import load_audio, trim
import sherpa_onnx as s

DIR = "D:/asr-data/models/sherpa-streaming-zh-en"
rec = s.OnlineRecognizer.from_transducer(
    tokens=DIR + "/tokens.txt",
    encoder=DIR + "/encoder-epoch-99-avg-1.int8.onnx",
    decoder=DIR + "/decoder-epoch-99-avg-1.onnx",
    joiner=DIR + "/joiner-epoch-99-avg-1.int8.onnx",
    num_threads=4, provider="cpu", decoding_method="greedy_search",
    enable_endpoint_detection=True, rule2_min_trailing_silence=1.0,
    modeling_unit="cjkchar",
)

def stream_text(x):
    st = rec.create_stream()
    CH = 960  # 60ms 块
    for i in range(0, len(x), CH):
        st.accept_waveform(SR, x[i:i + CH])
        while rec.is_ready(st):
            rec.decode_stream(st)
    st.input_finished()
    while rec.is_ready(st):
        rec.decode_stream(st)
    t = str(rec.get_result(st)).strip()
    rec.reset(st)
    return t

cases = [json.loads(l) for l in open("D:/asr-data/manifests/kespeech_shard0.jsonl", encoding="utf-8") if l.strip()]
rows, perf = [], []
t_all = time.perf_counter()
for sc_name in ["clean", "noisy_10db", "far_3m"]:
    sc = SCENARIOS[sc_name]
    for dialect in sorted({c["dialect"] for c in cases}):
        rs = []
        for c in (d for d in cases if d["dialect"] == dialect):
            z = trim(apply_scenario(load_audio(c["audio"]), sc, sr=SR), SR)
            t0 = time.perf_counter()
            hyp = stream_text(z)
            infer_s = time.perf_counter() - t0
            audio_s = len(z) / SR
            perf.append({"infer_s": infer_s, "audio_s": audio_s})
            rs.append(score_case(c["id"], c["ref"], hyp))
        agg = aggregate(rs)
        rows.append({"dialect": dialect, "scenario": sc_name, "n_cases": agg.n_cases,
                     "cer": round(agg.cer, 6), "accuracy": round(agg.accuracy, 6),
                     "sent_acc": round(agg.sent_acc, 6), "ref_chars": agg.total_ref_len,
                     "errors": agg.total_errors, "sub": agg.sub, "del": agg.dele, "ins": agg.ins})
        print(dialect, sc_name, "cer=%.4f rtf=%.4f" % (agg.cer, infer_s / audio_s), flush=True)
rtfs = [p["infer_s"] / p["audio_s"] for p in perf if p["audio_s"] > 0]
out = {"model": "sherpa-streaming-zipformer-bilingual-zh-en-2023-02-20 int8", "device": "cpu",
       "manifest": "D:/asr-data/manifests/kespeech_shard0.jsonl", "n_cases": len(cases),
       "scenarios": ["clean", "noisy_10db", "far_3m"],
       "elapsed_s": round(time.perf_counter() - t_all, 1),
       "performance": {"rtf_mean": round(statistics.mean(rtfs), 4),
                       "rtf_p50": round(statistics.median(rtfs), 4),
                       "rtf_max": round(max(rtfs), 4),
                       "note": "流式端到端解码墙钟/音频时长"},
       "rows": rows}
json.dump(out, open("D:/asr-data/reports/r186_stream_zipformer.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("DONE rows=", len(rows))
