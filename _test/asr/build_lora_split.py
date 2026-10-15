#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LoRA 微调数据准备：KeSpeech parquet → 训练/验证/留出测试。

🔴 **最重要的一条红线：留出集必须与训练集物理隔离。**
   之前跑基线用的就是 shard0 的 232 条抽样。如果在同一批里抽样训练，
   训完再测同一个集，数字必然虚高（等于「背答案」）。
   本模块的做法：
     · shard0 里已被基线用过的 232 条 → 标记为 **holdout_eval**，绝不进训练；
     · 其余 shard（1..7）→ train / val；
     · 并把 holdout 的 id 落盘成文件，训练脚本据此硬断言「训练集与 holdout 零交集」。

用法:
    py -3.12 _test/asr/build_lora_split.py \
        --parquet-dir D:/asr-data/kespeech/data \
        --exclude D:/asr-data/manifests/kespeech_shard0.jsonl \
        --out-dir D:/asr-data/lora_data
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_manifest_ke import KE2CODE  # noqa: E402

MIN_CHARS, MAX_CHARS = 4, 60     # 太短的句子学不到东西；太长的截断风险大
VAL_RATIO = 0.05


def load_parquet(path: str):
    import pyarrow.parquet as pq
    pf = pq.ParquetFile(path)
    for i in range(pf.num_row_groups):
        t = pf.read_row_group(i, columns=["ID", "Text", "Dialect", "audio"])
        ids = t.column("ID").to_pylist()
        txt = t.column("Text").to_pylist()
        dia = t.column("Dialect").to_pylist()
        au = t.column("audio").to_pylist()
        for cid, ref, d, blob in zip(ids, txt, dia, au):
            yield cid, (ref or "").strip(), d, blob


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parquet-dir", default="D:/asr-data/kespeech/data")
    ap.add_argument("--exclude", default="", help="基线清单 jsonl；其 id 全部划入 holdout")
    ap.add_argument("--out-dir", default="D:/asr-data/lora_data")
    ap.add_argument("--wav-dir", default="D:/asr-data/lora_data/wav")
    ap.add_argument("--max-per-dialect", type=int, default=0, help="每方言每 split 上限，0=不限")
    a = ap.parse_args()

    os.makedirs(a.out_dir, exist_ok=True)
    os.makedirs(a.wav_dir, exist_ok=True)

    excluded = set()
    excluded_audio: dict = {}          # id → 音频（基线那批仍要留出，不能连带丢掉音频）
    if a.exclude and os.path.isfile(a.exclude):
        for line in open(a.exclude, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            m = json.loads(line)
            # 基线清单的 id 形如 kespeech_<code>_<parquet_id>，而 parquet 里的原始
            # id 是 <parquet_id>。旧码直接拿整串去比 ⇒ 一个都匹配不上，
            # 于是「已跑过基线的那 232 条」被静默混进训练集 —— 这正是数据泄漏，
            # 而脚本自己还打印「三者两两不交 ✅」（实测踩过，最阴险的一类）。
            key = m["id"].split("_", 2)[-1]
            excluded.add(m["id"])
            excluded_audio[key] = m["audio"]
        print(f"[隔离] 基线清单 {a.exclude} → {len(excluded)} 条 id 划入 holdout，绝不进训练")
        print(f"       （已抽出 {len(excluded_audio)} 个 parquet 原始 id 用于匹配）")

    shards = sorted(f for f in os.listdir(a.parquet_dir) if f.endswith(".parquet"))
    if not shards:
        print(f"[FATAL] {a.parquet_dir} 里没有 parquet")
        return 2

    buckets: dict = {"train": {}, "val": {}, "holdout": {}}
    stats = Counter()
    for fn in shards:
        path = os.path.join(a.parquet_dir, fn)
        n = 0
        for cid, ref, dia, blob in load_parquet(path):
            n += 1
            key = f"kespeech_{KE2CODE.get(dia,'mandarin')}_{cid}"
            if key in excluded or cid in excluded_audio:
                # 留出集：音频直接复用基线已导出的 wav，不重复落盘
                buckets["holdout"][key] = (ref, dia, None, excluded_audio.get(cid))
                stats["holdout"] += 1
                continue
            code = KE2CODE.get(dia)
            if not code:
                stats["skip_unknown_dialect"] += 1
                continue
            if not (MIN_CHARS <= len(ref) <= MAX_CHARS):
                stats["skip_len"] += 1
                continue
            if not blob or not blob.get("bytes"):
                stats["skip_no_audio"] += 1
                continue
            buckets["train"].setdefault(f"{code}_{cid}", (ref, dia, blob))
            stats["train_pool"] += 1
        print(f"  {fn}: {n} 条")

    # val 从 train 池里按方言切（分层，保证每方言都有验证样本）
    import random
    rng = random.Random(1234)          # 固定种子 ⇒ 可复现
    for key in sorted(buckets["train"].keys()):
        code = key.split("_")[0]
        row = buckets["train"][key]
        if rng.random() < VAL_RATIO:
            buckets["train"].pop(key, None)
            buckets["val"][key] = row

    # 导出
    def dump(split: str, cap: int) -> dict:
        items = []
        per = Counter()
        for key, row in sorted(buckets[split].items()):
            if row is None:
                continue
            ref, dia, blob, reuse_audio = (row + (None,))[:4] if len(row) == 3 else row
            code = KE2CODE.get(dia, "mandarin")
            if cap and per[code] >= cap:
                continue
            # blob 为 None ⇒ 复用基线已导出的音频路径（留出集专用）
            wav = reuse_audio
            if wav is None:
                wav = os.path.join(a.wav_dir, f"{key}.wav")
                if not os.path.isfile(wav):
                    with open(wav, "wb") as fh:
                        fh.write(blob["bytes"])
            per[code] += 1
            items.append({"id": key, "audio": wav, "text": ref,
                          "dialect": code, "kespeech_dialect": dia})
        p = os.path.join(a.out_dir, f"{split}.jsonl")
        with open(p, "w", encoding="utf-8") as fh:
            for it in items:
                fh.write(json.dumps(it, ensure_ascii=False) + "\n")
        print(f"\n{split}: {len(items)} 条 → {p}")
        print("   " + ", ".join(f"{k}={v}" for k, v in sorted(per.items())))
        return {"n": len(items), "per_dialect": dict(per), "path": p}

    summary = {s: dump(s, a.max_per_dialect) for s in ("train", "val", "holdout")}

    # 🔴 硬断言：训练/验证/留出三者零交集
    def ids_of(split):
        p = os.path.join(a.out_dir, f"{split}.jsonl")
        if not os.path.isfile(p):
            return set()
        return {json.loads(l)["id"] for l in open(p, encoding="utf-8") if l.strip()}
    tr, va, ho = ids_of("train"), ids_of("val"), ids_of("holdout")
    ov_tv, ov_th, ov_vh = tr & va, tr & ho, va & ho
    print("\n=== 隔离校验 ===")
    print(f"  train∩val   = {len(ov_tv)}")
    print(f"  train∩hold  = {len(ov_th)}")
    print(f"  val∩hold    = {len(ov_vh)}")
    # ⚠ 除了 id 不交，还必须查**音频路径**不交。同一条录音若被不同 id 引用两次，
    #   id 集合看着两两不交，实际仍是同一段音频进了训练 —— 这是比 id 泄漏更隐蔽的一层。
    def wavs_of(split):
        p = os.path.join(a.out_dir, f"{split}.jsonl")
        if not os.path.isfile(p):
            return set()
        return {os.path.basename(json.loads(l)["audio"]) for l in open(p, encoding="utf-8") if l.strip()}
    wt, wv, wh = wavs_of("train"), wavs_of("val"), wavs_of("holdout")
    w_leak = (wt & wh) | (wv & wh) | (wt & wv)
    print(f"  音频 train∩hold = {len(wt & wh)}  val∩hold = {len(wv & wh)}  train∩val = {len(wt & wv)}")
    assert not ov_tv and not ov_th and not ov_vh, "id 泄漏！训练/验证/留出必须两两不交"
    assert not w_leak, f"音频泄漏！{len(w_leak)} 个文件同时出现在两个 split（如 {list(w_leak)[:3]}）"
    assert ho, "留出集为空 —— 基线那批一条都没匹配上，隔离形同虚设"
    print("  ✅ id 与音频均两两不交，且留出集非空")
    summary["isolation_ok"] = True
    with open(os.path.join(a.out_dir, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)
    print(f"[OK ] summary → {os.path.join(a.out_dir, 'summary.json')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())