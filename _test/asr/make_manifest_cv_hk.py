#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Common Voice zh-HK（粤语）→ 评测清单。

为什么用它：魔搭 `pengzhendong/Common-Voice-Chinese-Hong-Kong` 镜像了整套
Common Voice 粤语（实测 9.44 MB/s）。别的粤语候选要么只有 csv 没有音频
（`tomsawyerhu/cantonese-dialect` 实测只有 3 个 csv，0 个音频文件），
要么体量上千 GB（WenetSpeech-Yue 2346 GB / WenetSpeech-Chuan 1096 GB）。

🔴 许可必须当心：Common Voice 是 **CC0**，但**录音者同意书限定非商业用途**
（CV 的 dataset license 是 CC0 + 一份单独的 terms）。
→ 本模块在清单里写 `real_audio=true` 但**不自动判定可用于商用**，
   `source` 字段如实记录来源，供后续合规判断，不代用户拍板。

用法:
    py -3.12 _test/asr/make_manifest_cv_hk.py \
        --root D:/asr-data/cv17/cv-corpus-17.0-2024-03-15/zh-HK \
        --out D:/asr-data/manifests/yue.jsonl \
        --n 200
"""
from __future__ import annotations

import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eval_set import Case, write_manifest  # noqa: E402

# 粤语常用字 → 简体（评测归一化在 normalize.py 里做，这里只做最低限度清洗）
_PUNCT = "，。！？、；：,.!?;:「」『』（）()《》〈〉—…·　 \t"


def clean(s: str) -> str:
    return "".join(ch for ch in (s or "").strip() if ch not in _PUNCT)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, help="zh-HK 目录（含 clips/ 与 test.tsv）")
    ap.add_argument("--out", required=True)
    ap.add_argument("--split", default="test", choices=["test", "validated"])
    ap.add_argument("--n", type=int, default=200, help="取样数（0=全取）")
    ap.add_argument("--export", default="", help="把 mp3 转 16k wav 导出到该目录")
    ap.add_argument("--min-chars", type=int, default=4)
    ap.add_argument("--max-chars", type=int, default=30)
    a = ap.parse_args()

    tsv = os.path.join(a.root, f"{a.split}.tsv")
    if not os.path.isfile(tsv):
        print(f"[FATAL] 找不到 {tsv}")
        return 2
    clips = os.path.join(a.root, "clips")
    if not os.path.isdir(clips):
        print(f"[FATAL] 找不到 {clips}（音频未解包）")
        return 2

    rows = list(csv.DictReader(open(tsv, encoding="utf-8"),
                               delimiter="\t", quoting=csv.QUOTE_ALL))
    cases: list[Case] = []
    skipped = {"nolabel": 0, "nofile": 0, "toolong": 0}
    for r in rows:
        if a.n and len(cases) >= a.n:
            break
        ref = clean(r.get("sentence", ""))
        if not ref:
            skipped["nolabel"] += 1
            continue
        if not (a.min_chars <= len(ref) <= a.max_chars):
            skipped["toolong"] += 1
            continue
        src = os.path.join(clips, r["path"])
        if not os.path.isfile(src):
            skipped["nofile"] += 1
            continue
        audio = src
        if a.export:
            os.makedirs(a.export, exist_ok=True)
            audio = os.path.join(a.export,
                                  r["path"].replace(".mp3", ".wav"))
            if not os.path.isfile(audio):
                try:
                    import soundfile as sf
                    x, sr = sf.read(src, dtype="float32", always_2d=False)
                    if x.ndim > 1:
                        x = x.mean(axis=1)
                    sf.write(audio, x, sr, subtype="PCM_16")
                except Exception as e:
                    print(f"[SKIP] 转码失败 {r['path']}: {e}")
                    continue
        cases.append(Case(
            id=f"cvzhHK_{os.path.splitext(r['path'])[0]}",
            audio=audio, ref=ref, dialect="yue", accent="hk",
            source="CommonVoice-17.0-zh-HK", split=a.split,
            domain="read", real_audio=True,
            meta={"client_id": r.get("client_id", ""),
                  "up_votes": r.get("up_votes", ""),
                  "down_votes": r.get("down_votes", ""),
                  "license": "CC0 (但录音者同意书限定非商业用途)"},
        ))

    n = write_manifest(cases, a.out)
    chars = sum(len(c.ref) for c in cases)
    print(f"{a.split}.tsv 共 {len(rows)} 条 → 采纳 {n} 条 / {chars} 字  →  {a.out}")
    print(f"  跳过: {skipped}")
    if cases:
        print(f"  示例: {cases[0].ref}")
        print(f"  ⚠ 许可: CC0，但录音者同意书限定**非商业用途**；商用前须自行确认。")
    return 0


if __name__ == "__main__":
    sys.exit(main())