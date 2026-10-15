#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KeSpeech parquet → 评测清单（manifest）。

为什么用 KeSpeech 而不是 AISHELL-3：
  · 魔搭实测 **8.03 MB/s**（OpenSLR 同期只有 8 KB/s，差 1000 倍）；
  · KeSpeech 一个语料同时覆盖 **普通话 + 8 种方言**，含本项目要的
    东北话（Northeastern）与川渝（Southwestern）；
  · 每个 shard 自带 test 划分，不用来得及全量。

用法:
    py -3.12 _test/asr/make_manifest_ke.py \
        --parquet D:/asr-data/kespeech/data/test-00000-of-00008.parquet \
        --out _test/asr/manifests/kespeech.jsonl \
        --per-dialect 80
"""
from __future__ import annotations

import argparse
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eval_set import Case, DIALECTS, write_manifest  # noqa: E402

# KeSpeech 官方方言名 → 本项目方言码。
# ⚠ 诚实登记：其中四川话/上海话/闽南话**没有一一对应项**：
#   · Southwestern = 川渝（四川话归这一类，但含重庆/西南官话，非纯四川话）
#   · Wu 语系里 KeSpeech 无独立项；Jiang-Huai 是江淮官话，与吴语**不是**同一支
#   · Minnan 完全没有
#   ⇒ 映射只用于评测分组，**不得据此宣称「已覆盖闽南语」**。
KE2CODE = {
    "Mandarin":    "mandarin",
    "Northeastern": "dongbei",      # 东北话 ✔ 用户目标
    "Southwestern": "chuan",        # 川渝（近似四川话）
    "Beijing":     "mandarin",
    "Zhongyuan":   "mandarin",      # 中原官话，暂并入普通话组做对照
    "Jiang-Huai":  "zongyuan",      # 保留独立：不是吴语，别混
    "Ji-Lu":       "zongyuan",
    "Lan-Yin":     "zongyuan",
    "Jiao-Liao":   "zongyuan",
}
EXTRA = {"zongyuan": {"zh": "官话（中原/江淮/冀鲁/兰银/胶辽）", "is_variety": True,
                      "corpus": "KeSpeech test"}}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parquet", required=True, help="KeSpeech test parquet shard")
    ap.add_argument("--out", required=True)
    ap.add_argument("--per-dialect", type=int, default=0, help="每方言取样数；0=全取")
    ap.add_argument("--dump-audio", default="", help="把音频导出到该目录（否则引用原 WavPath）")
    a = ap.parse_args()

    import pyarrow.parquet as pq
    import soundfile as sf

    known = dict(DIALECTS)
    known.update(EXTRA)

    by: dict = {}
    total = 0
    pf = pq.ParquetFile(a.parquet)
    for i in range(pf.num_row_groups):
        t = pf.read_row_group(i, columns=["ID", "Text", "Dialect", "WavPath", "audio"])
        ids = t.column("ID").to_pylist()
        txt = t.column("Text").to_pylist()
        dia = t.column("Dialect").to_pylist()
        wp = t.column("WavPath").to_pylist()
        au = t.column("audio").to_pylist()
        for cid, ref, d, path, blob in zip(ids, txt, dia, wp, au):
            total += 1
            code = KE2CODE.get(d)
            if not code:
                continue
            by.setdefault(code, []).append((cid, ref, path, blob))
        del t

    cases: list[Case] = []
    if a.dump_audio:
        os.makedirs(a.dump_audio, exist_ok=True)
    for code in sorted(by):
        rows = by[code]
        if a.per_dialect:
            rows = rows[: a.per_dialect]
        for cid, ref, path, blob in rows:
            audio_path = path
            if a.dump_audio:
                audio_path = os.path.join(a.dump_audio, f"{code}_{cid}.wav")
                if not os.path.isfile(audio_path) and blob and blob.get("bytes"):
                    with open(audio_path, "wb") as fh:
                        fh.write(blob["bytes"])
            cases.append(Case(
                id=f"kespeech_{code}_{cid}", audio=audio_path, ref=(ref or "").strip(),
                dialect=code, accent="", source="KeSpeech-test", split="test",
                domain="read", real_audio=True,
                meta={"kespeech_dialect": d if False else "", "orig_wav": path},
            ))

    n = write_manifest(cases, a.out)
    print(f"shard rows={total}  映射后用例={n}  →  {a.out}")
    from collections import Counter
    c = Counter((x.dialect, len(x.ref)) for x in cases)
    per = Counter(x.dialect for x in cases)
    for code, cnt in sorted(per.items()):
        chars = sum(len(x.ref) for x in cases if x.dialect == code)
        print(f"   {code:<9} {cnt:>5} 条  {chars:>7} 字   ({known.get(code,{}).get('zh',code)})")
    if not a.dump_audio:
        print(f"[提示] 未导出音频：清单里的 audio 指向 KeSpeech 原始相对路径。"
              f"跑分前需 --dump-audio 导出，或先解压对应 Audio/ 目录。")
    return 0


if __name__ == "__main__":
    sys.exit(main())