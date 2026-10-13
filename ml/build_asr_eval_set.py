# -*- coding: utf-8 -*-
"""心屿 · 构建粤语 ASR 评测集（B3，可复现）

数据来源（一手核实，2026-10-14）：
  **Common Voice 22.0 的粤语（yue）子集**，HF 镜像 `JackyHoCL/common_voice_22_yue`
  （gated=False，匿名可下）。字段与官方 CV 完全同构：sentence / audio / client_id /
  sentence_id / sentence_domain / up_votes / down_votes / age / gender / accents / locale。
  规模：test 5,130 条 / train 7,419 / validation 5,130 / validated 191,152。
  Common Voice 数据集自诞生起即 **CC0-1.0**；本脚本只取 test 划分做**评测**，不参与训练。

⚠️ 与「Common Voice Scripted Speech 27.0 - Chinese (Hong Kong)」（MDC 上，CC0-1.0）的关系：
  那才是老大点名的 zh-HK，但 Mozilla 2025-10 起把 CV 全部迁到 Mozilla Data Collective，
  下载端点 **POST /api/datasets/<id>/download 返回 401**（需注册账号）⇒ 本轮取不到，已登记为阻塞。
  yue 与 zh-HK 是两个 locale：yue = 粤语口语，zh-HK = 繁体书面语朗读。**方言场景下 yue 更对口**，
  且它同样出自 Common Voice、同样 CC0。脚本的 --source 参数预留了切换位，账号一到即可换源重跑。

产出（三层，只有第一层入库）：
  1. `_test/asr_eval_manifest.jsonl` —— 评测清单（入库）：每行一条
     {id, ref, dur, domain, age, gender, up, down, wav}
  2. `D:/xinyu-ml/asr-data/cv22-yue-eval/*.wav` —— 16kHz 单声道音频（**不入库**，体积大）
  3. `_test/asr_eval_manifest.meta.json` —— 构建元数据（入库）：来源/版本/条数/总时长/抽样种子/各过滤计数

设计红线：
  · **ref 只做"去空白与标点"的规整，不改字**。把粤语字转成普通话字会让 CER 失去意义
    （那是 r176 红线七"只打分不改写"在评测面的同一条）。
  · 过滤条件全部可配且**逐条计数**（避免"悄悄扔掉一半数据"）。
  · 抽样用固定种子 ⇒ 同一输入必然同一输出（可复现）。

用法：
  D:/xinyu-ml/asr-venv/Scripts/python.exe ml/build_asr_eval_set.py [--limit 500] [--all]
"""
import argparse
import hashlib
import io
import json
import os
import random
import re
import subprocess
import sys
import wave

REPO = "JackyHoCL/common_voice_22_yue"
PARQUET = "data/test-00000-of-00001-*.parquet"
DEST_AUDIO = os.environ.get("XINYU_ASR_EVAL_DIR", "D:/xinyu-ml/asr-data/cv22-yue-eval")
MANIFEST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "_test",
                        "asr_eval_manifest.jsonl")
META = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "_test",
                    "asr_eval_manifest.meta.json")
SEED = 20261014
# 标点与空白：CER 按字算，标点不参与（粤语文本里的「，」「。」「？」会系统性拉高 CER）
PUNCT = re.compile(r"[\s，。！？、；：「」『』（）《》…—\-.,!?;:\"'()\[\]<>~·`@#$%^&*_+=|\\/{}]+")


def fetch_parquet():
    """下载 test 划分的 parquet 到 D:/xinyu-ml/asr-data/（镜像端点，直连 HF 在本机超时）

    ⚠ hf_hub_download **不支持通配符**（那是 snapshot_download 的 allow_patterns 才干的事），
    直接传 "test-00000-of-00001-*.parquet" 会在 filelock 里炸出 WinError 123。
    先用 list_repo_files 拿真实文件名。
    """
    os.makedirs(DEST_AUDIO, exist_ok=True)
    cache = os.path.join(DEST_AUDIO, "_src")
    os.makedirs(cache, exist_ok=True)
    from huggingface_hub import hf_hub_download, list_repo_files
    names = sorted(f for f in list_repo_files(REPO, repo_type="dataset")
                      if f.startswith("data/test-"))
    if not names:
        raise SystemExit("repo 里找不到 data/test-* 分片（上游结构变了？）")
    p = hf_hub_download(REPO, names[0], repo_type="dataset", local_dir=cache)
    print("  parquet: %s (%.1f MB)" % (p, os.path.getsize(p) / 1e6))
    return p


def decode_audio(audio_field):
    """parquet 的 audio 字段（dict，含 bytes/path）→ (samples_float32, sr)

    先试 soundfile（libsndfile 1.2 起支持 mp3）；不支持就落 ffmpeg。
    两条路都返回 16kHz 单声道 float32 —— SenseVoice 的固定输入。
    """
    raw = audio_field.get("bytes") if isinstance(audio_field, dict) else None
    if not raw:
        raise ValueError("audio 字段无 bytes")
    try:
        import soundfile as sf
        samples, sr = sf.read(io.BytesIO(raw), dtype="float32", always_2d=False)
        if samples.ndim > 1:
            samples = samples.mean(axis=1)
    except Exception:                                        # noqa: BLE001
        p = subprocess.run(["ffmpeg", "-v", "error", "-i", "pipe:0", "-f", "wav",
                            "-ac", "1", "-ar", "16000", "pipe:1"],
                           input=raw, stdout=subprocess.PIPE, check=True)
        b = io.BytesIO(p.stdout)
        with wave.open(b, "rb") as w:
            sr = w.getframerate()
            n = w.getnframes()
            samples = np.frombuffer(w.readframes(n), dtype="<i2").astype("float32") / 32768.0
    if sr != 16000:
        import numpy as np
        n = int(round(len(samples) * 16000.0 / sr))
        idx = np.arange(n, dtype=np.float64) * (sr / 16000.0)
        lo = np.floor(idx).astype(np.int64).clip(0, len(samples) - 1)
        hi = np.ceil(idx).astype(np.int64).clip(0, len(samples) - 1)
        frac = idx - lo
        samples = (samples[lo] * (1.0 - frac) + samples[hi] * frac).astype(np.float32)
    return samples, 16000


def norm_ref(s):
    """只去空白与标点，不改字（红线：评测参考文本不做"普通话化"）"""
    return PUNCT.sub("", s or "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=500, help="抽样条数（默认 500）")
    ap.add_argument("--all", action="store_true", help="不抽样，用全部通过过滤的条目")
    ap.add_argument("--min-up", type=int, default=1, help="up_votes 下限（默认 1）")
    ap.add_argument("--max-down", type=int, default=0, help="down_votes 上限（默认 0）")
    ap.add_argument("--min-sec", type=float, default=1.0)
    ap.add_argument("--max-sec", type=float, default=10.0)
    args = ap.parse_args()

    import pandas as pd
    path = fetch_parquet()
    df = pd.read_parquet(path)
    total = len(df)
    print("  test 划分原始 %d 条" % total)

    counts = {"raw": total}
    df = df[df["up_votes"] >= args.min_up]
    counts["up_votes>=%d" % args.min_up] = len(df)
    df = df[df["down_votes"] <= args.max_down]
    counts["down_votes<=%d" % args.max_down] = len(df)
    df = df[df["sentence"].notna()]
    df["_ref"] = df["sentence"].map(norm_ref)
    df = df[df["_ref"].str.len() >= 2]
    counts["ref>=2字"] = len(df)

    # 时长过滤要在解码后才能精确算；先用 audio 的采样数估（parquet 里 audio.bytes 是 mp3，
    # 解一次才知道时长）。为避免全量解码 5000 条，先随机抽 3 倍再过滤。
    rng = random.Random(SEED)
    pool = df.sample(n=min(len(df), max(args.limit * 3, 300)), random_state=SEED)
    rows = []
    for _, r in pool.iterrows():
        try:
            samples, sr = decode_audio(r["audio"])
        except Exception as e:                                # noqa: BLE001
            counts.setdefault("解码失败", 0)
            counts["解码失败"] += 1
            continue
        secs = len(samples) / 16000.0
        if not (args.min_sec <= secs <= args.max_sec):
            counts.setdefault("时长越界", 0)
            counts["时长越界"] += 1
            continue
        rows.append((r, samples, secs))
    counts["通过全部过滤"] = len(rows)

    if not args.all:
        rng.shuffle(rows)
        rows = rows[:args.limit]
    rows.sort(key=lambda x: str(x[0]["sentence_id"]))     # 固定顺序 ⇒ 可复现
    counts["最终入选"] = len(rows)

    os.makedirs(DEST_AUDIO, exist_ok=True)
    out = []
    for r, samples, secs in rows:
        sid = str(r["sentence_id"])
        wav = os.path.join(DEST_AUDIO, "%s.wav" % sid)
        pcm = (samples * 32767.0).clip(-32768, 32767).astype("<i2").tobytes()
        with wave.open(wav, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(16000)
            w.writeframes(pcm)
        out.append({"id": sid, "ref": r["_ref"], "dur": round(secs, 3),
                    "domain": r.get("sentence_domain"), "age": r.get("age"),
                    "gender": r.get("gender"), "up": int(r["up_votes"]),
                    "down": int(r["down_votes"]), "wav": wav})

    mpath = os.path.abspath(MANIFEST)
    with open(mpath, "w", encoding="utf-8", newline="\n") as f:
        for o in out:
            f.write(json.dumps(o, ensure_ascii=False) + "\n")

    meta = {"source": "JackyHoCL/common_voice_22_yue (Common Voice 22.0 · yue · CC0-1.0)",
            "split": "test", "seed": SEED, "counts": counts,
            "total_sec": round(sum(o["dur"] for o in out), 1),
            "audio_dir": os.path.abspath(DEST_AUDIO),
            "manifest": mpath,
            "manifest_sha256": hashlib.sha256(open(mpath, "rb").read()).hexdigest(),
            "filters": {"min_up": args.min_up, "max_down": args.max_down,
                        "min_sec": args.min_sec, "max_sec": args.max_sec,
                        "sampled": not args.all}}
    with open(os.path.abspath(META), "w", encoding="utf-8", newline="\n") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print("EVAL-SET-PASS 入选 %d 条 / 总时长 %.1fs / 过滤链 %s"
          % (len(out), meta["total_sec"], json.dumps(counts, ensure_ascii=False)))
    print("  manifest: %s" % mpath)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
