#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""下载 B2 流式选型模型（spike §16 前置，一次性、约 190MB，不进仓）。

为什么不用 huggingface_hub：本机 asr-venv 里的 httpx2 会把镜像重定向 URL
解析炸掉（InvalidURL: Invalid port ':1]'，r186 一手踩坑）；urllib 直连 hf-mirror 反而稳定。

用法：
    D:/xinyu-ml/asr-venv/Scripts/python.exe _test/asr/dl_stream_model.py
落地：D:/asr-data/models/sherpa-streaming-zh-en/（文件已存则跳过，可重入）
"""
import os
import time
import urllib.request

BASE = "https://hf-mirror.com/csukuangfj/sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20/resolve/main/"
OUT = "D:/asr-data/models/sherpa-streaming-zh-en"
FILES = [
    "tokens.txt",
    "decoder-epoch-99-avg-1.onnx",
    "joiner-epoch-99-avg-1.int8.onnx",
    "encoder-epoch-99-avg-1.int8.onnx",
]


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    for f in FILES:
        dst = os.path.join(OUT, f)
        if os.path.exists(dst) and os.path.getsize(dst) > 100:
            print("SKIP", f, os.path.getsize(dst), flush=True)
            continue
        t0 = time.perf_counter()
        req = urllib.request.Request(BASE + f, headers={"User-Agent": "xinyu-eval/1.0"})
        with urllib.request.urlopen(req, timeout=600) as r, open(dst, "wb") as w:
            while True:
                b = r.read(1 << 20)
                if not b:
                    break
                w.write(b)
        print("OK", f, os.path.getsize(dst), "%.1fs" % (time.perf_counter() - t0), flush=True)
    print("DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
