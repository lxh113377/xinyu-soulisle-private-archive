# -*- coding: utf-8 -*-
"""心屿 · 本地情绪模型推理服务（S3）

FastAPI，127.0.0.1:8300（回环，默认不对外）：
  POST /classify {"text":"..."} → {"emotion","intensity","confidence","probs","latency_ms"}
  GET  /health → {"status":"UP","model":...,"device":...,"labels":[...]}
      —— 仿 Java /api/health 的自证风格：能答 = 模型已加载 + 设备明确。

模型：ml/checkpoints/best（train_emotion.py 产出）。
intensity 口径：模型单分类头无强度回归，取 softmax top-1 置信度作为强度读数
（语义 = 「模型对判定的自信」，与词典/LLM 腿的 0-1 强度同尺度可比）。

启动：ml/.venv/Scripts/python.exe ml/server.py   （或 ml/start_server.ps1）
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding="utf-8")

CKPT = ROOT / "ml" / "checkpoints" / "best"
LABELS = ["joy", "sadness", "anger", "fear", "calm", "love"]
MAX_LEN = 64

import torch  # noqa: E402
from transformers import AutoModelForSequenceClassification, AutoTokenizer  # noqa: E402

device = "cuda" if torch.cuda.is_available() else "cpu"
_tokenizer = AutoTokenizer.from_pretrained(str(CKPT))
_model = AutoModelForSequenceClassification.from_pretrained(str(CKPT)).to(device).eval()

from fastapi import FastAPI  # noqa: E402
from pydantic import BaseModel  # noqa: E402

app = FastAPI(title="xinyu-emotion-model")


class Body(BaseModel):
    text: str


@app.get("/health")
def health():
    return {"status": "UP", "model": "chinese-roberta-wwm-ext",
            "device": device, "labels": LABELS, "max_len": MAX_LEN}


@app.post("/classify")
def classify(b: Body):
    t0 = time.perf_counter()
    text = (b.text or "")[:200]
    enc = _tokenizer(text, truncation=True, max_length=MAX_LEN, return_tensors="pt").to(device)
    with torch.no_grad():
        probs = torch.softmax(_model(**enc).logits, dim=-1)[0]
    idx = int(probs.argmax())
    conf = float(probs[idx])
    return {
        "emotion": LABELS[idx],
        "intensity": round(conf, 4),
        "confidence": round(conf, 4),
        "probs": {LABELS[i]: round(float(p), 4) for i, p in enumerate(probs)},
        "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
    }


if __name__ == "__main__":
    import uvicorn
    # 回环地址：本地模型服务不出公网（密钥/内网红线同源精神）
    uvicorn.run(app, host="127.0.0.1", port=8300, log_level="warning")
