#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""心屿 · 本机 ASR 推理服务（Qwen3-ASR-0.6B）

为什么单独一个进程，而不是塞进 Java 服务：
  - 模型是 Python/PyTorch 生态（transformers + peft），Java 侧只能通过 HTTP 调；
  - 模型常驻显存（RTX 5070 Ti 实测加载 2.2s），**每请求重载一次是不可接受的**；
  - Java 侧沿用既有 `llm/LlmProxy.java` 的 JDK 内置 HttpClient 转发模式，零新依赖。

接口（与 Java `AsrProxy` 一一对应）：
  GET  /health     → 就绪探针，供前端「默认态零探测」红线之外的显式开启路径使用
  POST /transcribe → 原始 WAV 字节流（Content-Type: audio/wav）→ JSON

失败口径（红线：不得伪装在线）：
  模型没起 / GPU 挂 / 解码失败 ⇒ 返 503 + {"error": "asr-unavailable"}。
  **绝不返回任何占位文本或空串冒充成功** —— 前端据此回落到 Web Speech。
"""
import io
import os
import re
import threading
import time
import traceback
from typing import Optional

import numpy as np

# ⚠ 本文件**刻意不写** `from __future__ import annotations`（PEP 563）。
#   写了它，函数注解会变成字符串，FastAPI 再用 get_type_hints 解析 ——
#   而 Request/HTTPException 是在 build_app() **函数内部**导入的，不在模块 globals，
#   解析不到就把 `request: Request` 退化成一个 query 参数，于是所有 POST 得到
#   422 {"loc":["query","request"],"msg":"Field required"}（实测踩过，报错信息极具误导性：
#   看起来像客户端少传参数，实际是服务端注解解析失败）。

# ── 配置（全部可用环境变量覆盖，零配置也能跑）─────────────────────────────
MODEL_DIR = os.environ.get("XINYU_ASR_MODEL", "D:/asr-data/models/Qwen3-ASR-0.6B-hf")
DEVICE = os.environ.get("XINYU_ASR_DEVICE", "cuda")        # cuda | cpu
DTYPE = os.environ.get("XINYU_ASR_DTYPE", "bfloat16")       # bfloat16 | float32
PORT = int(os.environ.get("XINYU_ASR_PORT", "8765"))
SR = 16000
MAX_SECONDS = float(os.environ.get("XINYU_ASR_MAX_SECONDS", "20"))
LORA_DIR = os.environ.get("XINYU_ASR_LORA", "") or None     # 可选：LoRA 已 merge 的权重目录

# 方言 → 模型语言名（取值必须与模型卡 Supported Dialects 逐字一致）。
# ⚠ 只有 yue 能在 language 参数上强制；其余方言名会被 transformers 拒
#   （实测 ValueError: Unsupported language: 'Sichuan'），故一律 None 走自动识别。
DIALECT_LANG = {
    "mandarin": "Chinese",
    "yue": "Cantonese",     # 唯一能用 language 强制的方言（实测见下）
    "en": "English",
    # 其余一律 None = 不带 language 参数，走模型自动语种识别。
    # ⚠ 曾按模型卡 Supported Dialects 表把它们映射成 "Sichuan"/"Dongbei"/"Wu"/"Minnan"，
    #   结果每次请求都 503（ValueError: Unsupported language）。查 transformers 源码确认：
    #   models/qwen3_asr 全目录只有 LANGUAGE_CODE_TO_NAME，**没有任何方言接口**。
    "chuan": None,
    "wu": None,
    "dongbei": None,
    "minnan": None,
    "teochew": None,
    "zongyuan": None,
}

# 领域词典 / 热词偏置（模型卡 Context/hotwords）。零训练成本给方言专名纠偏的手段。
# 🔴 红线：这是**偏置**不是强制 —— 命中不了就按原样输出，绝不替换文本。
#   心屿是情感陪伴场景，词典以情绪词 + 心理术语为主，避免把口语压成书面语。
DEFAULT_VOCAB = (
    "情绪陪伴, 焦虑, 抑郁, 失眠, 睡不着, 情绪低落, 压力, 倾诉, 共情, "
    "心跳, 呼吸, 放松, 崩溃, 麻木, 疲惫, 孤独, 自责, 内耗, 空心, "
    "心屿, 热线, 心理援助, 心理咨询师"
)


def build_prompt(vocab: Optional[str]) -> Optional[str]:
    """拼模型卡要求的格式：`Vocabulary: a, b, c.`

    词表为空则不传 prompt（传空串会让模型多生成一段废话，实测踩过）。"""
    v = (vocab or DEFAULT_VOCAB).strip()
    if not v:
        return None
    return f"Vocabulary: {v}."


class Engine:
    """模型常驻 + 单飞推理。GPU 只有一个，串行化比排队更省显存也更可预测。"""

    def __init__(self) -> None:
        self.model = None
        self.processor = None
        self.device = DEVICE
        self.dtype = DTYPE
        self.load_s: Optional[float] = None
        self.err: Optional[str] = None
        self._lock = threading.Lock()
        self._warm = False

    def load(self) -> bool:
        try:
            import torch
            from transformers import AutoProcessor, AutoModelForMultimodalLM

            if not os.path.isdir(MODEL_DIR):
                self.err = f"model-dir-missing: {MODEL_DIR}"
                return False
            if DEVICE.startswith("cuda") and not torch.cuda.is_available():
                self.err = "cuda-unavailable"          # 不静默回落 CPU（会慢一个量级且掩盖问题）
                return False
            t0 = time.perf_counter()
            self.processor = AutoProcessor.from_pretrained(MODEL_DIR)
            m = AutoModelForMultimodalLM.from_pretrained(
                MODEL_DIR, dtype=getattr(torch, self.dtype))
            self.model = m.to(self.device).eval()
            self.load_s = time.perf_counter() - t0
            self.err = None
            self._warmup()
            return True
        except Exception as e:                        # noqa: BLE001
            self.err = f"{type(e).__name__}: {e}"
            traceback.print_exc()
            return False

    def _warmup(self) -> None:
        """预热：首次 CUDA 调用含 kernel 编译，实测 18s vs 稳态 1.2s。
        不预热的话第一个真实用户请求会替所有人吃这 18s。"""
        if self._warm:
            return
        try:
            self.transcribe(np.zeros(SR, dtype=np.float32), "mandarin")
            self._warm = True
        except Exception:
            pass

    @property
    def ready(self) -> bool:
        return self.model is not None

    def transcribe(self, wav: np.ndarray, dialect: str = "mandarin",
                   prompt: Optional[str] = None) -> dict:
        import torch
        with self._lock:
            kwargs = {}
            lang = DIALECT_LANG.get(dialect)
            if lang:
                kwargs["language"] = lang
            if prompt:
                kwargs["prompt"] = prompt
            audio_s = len(wav) / SR
            t0 = time.perf_counter()
            inputs = self.processor.apply_transcription_request([wav], **kwargs)
            inputs = inputs.to(self.model.device)
            if self.device.startswith("cuda"):
                try:
                    inputs = inputs.to(getattr(torch, self.dtype))
                except Exception:
                    pass
            with torch.inference_mode():
                # **inputs 解包是必须的；位置传 BatchFeature 会让 generate 炸在
                # inputs_tensor.shape[0]（见 _test/asr/README.md 坑1）
                out = self.model.generate(**inputs, max_new_tokens=256, do_sample=False)
            gen = out[:, inputs["input_ids"].shape[1]:]
            text = _decode(self.processor, gen)
            infer = time.perf_counter() - t0
        return {"text": text, "dialect": dialect, "inferMs": int(infer * 1000),
            "audioSeconds": round(audio_s, 3),
            "rtf": round(infer / audio_s, 4) if audio_s > 0 else None,
            "engine": "qwen3-asr-0.6b"}


# 单例，供不经 HTTP 直接冒烟（也供 _test/asr 的判据用）。
def smoke(audio_path: str, dialect: str = "mandarin") -> dict:
    """直接对文件转写，绕过 HTTP。返回与 /transcribe 同构的 dict。"""
    import soundfile as sf
    x, sr = sf.read(audio_path, dtype="float32", always_2d=False)
    if x.ndim > 1:
        x = x.mean(axis=1)
    if sr != SR:
        raise ValueError(f"sample-rate-must-be-{SR}-got-{sr}")
    if not ENGINE.ready and not ENGINE.load():
        raise RuntimeError(f"engine-not-ready: {ENGINE.err}")
    return ENGINE.transcribe(np.ascontiguousarray(x.astype(np.float32)), dialect)


def _decode(proc, gen_ids) -> str:
    """取纯正文。优先官方 transcription_only；退化路径手工剥 `language X<asr_text>`。

    ⚠ `proc.decode()` 在**批量**下返回嵌套 list（如 [[文本]]）而不是 str，
      直接丢给 re.sub 会炸 TypeError: expected string or bytes-like object, got 'list'
      （实测踩过，且它发生在 except 分支里 ⇒ 整个请求 503，错误现场极具误导性）。
      故先统一压成字符串再剥壳。
    """
    def _flat(x) -> str:
        while isinstance(x, (list, tuple)):
            if not x:
                return ""
            x = x[0]
        return x if isinstance(x, str) else str(x)

    try:
        return _flat(proc.decode(gen_ids, return_format="transcription_only")).strip()
    except Exception:            # noqa: BLE001 —— 旧版 transformers 无此参数
        pass
    raw = _flat(proc.decode(gen_ids))
    if "<asr_text>" in raw:
        return raw.split("<asr_text>", 1)[1].strip()
    return re.sub(r"^\s*language\s+\S+\s*", "", raw).strip()


ENGINE = Engine()


# ── WAV 解析（只支持标准 PCM WAV；客户端就该送这个格式）───────────────────
def parse_wav(data: bytes) -> np.ndarray:
    import soundfile as sf
    with io.BytesIO(data) as f:
        x, sr = sf.read(f, dtype="float32", always_2d=False)
    if x.ndim > 1:
        x = x.mean(axis=1)
    if sr != SR:                        # 非 16k 一律拒：重采样会引入二次失真，掩盖问题
        raise ValueError(f"sample-rate-must-be-{SR}-got-{sr}")
    return np.ascontiguousarray(x.astype(np.float32))


def build_app():
    from fastapi import FastAPI, Request, HTTPException
    from fastapi.responses import JSONResponse

    app = FastAPI(title="xinyu-asr", version="1.0")

    @app.on_event("startup")
    def _boot():
        ok = ENGINE.load()
        print(f"[asr] load {'OK' if ok else 'FAILED'} device={ENGINE.device} "
              f"err={ENGINE.err} load_s={ENGINE.load_s}", flush=True)

    @app.get("/health")
    def health():
        return {"ready": ENGINE.ready, "device": ENGINE.device,
                "model": MODEL_DIR, "loadSeconds": ENGINE.load_s,
                "error": ENGINE.err, "sampleRate": SR,
                "dialects": sorted(DIALECT_LANG)}

    @app.post("/transcribe")
    async def transcribe(request: Request):
        if not ENGINE.ready:
            return JSONResponse(status_code=503,
                                content={"error": "asr-unavailable", "detail": ENGINE.err})
        dialect = request.query_params.get("dialect") or "mandarin"
        if dialect not in DIALECT_LANG:
            dialect = "mandarin"
        # 热词：默认走领域词典；?vocab=off 关掉；?vocab=自定义 覆盖。
        # 带上 isVocab 便于前端如实显示「已启用热词」，不假装没开。
        vq = request.query_params.get("vocab")
        vocab = None if vq == "off" else (vq if vq else DEFAULT_VOCAB)
        use_vocab = vocab is not None
        try:
            body = await request.body()
        except Exception as e:
            return JSONResponse(status_code=400, content={"error": "bad-body", "detail": str(e)})
        if not body:
            return JSONResponse(status_code=400, content={"error": "empty-body"})
        if len(body) > 4 * 1024 * 1024:
            return JSONResponse(status_code=413, content={"error": "audio-too-large"})
        try:
            wav = parse_wav(body)
        except Exception as e:                        # noqa: BLE001
            return JSONResponse(status_code=400,
                                content={"error": "bad-audio", "detail": str(e)})
        if wav.size < int(0.15 * SR):
            return JSONResponse(status_code=400, content={"error": "too-short"})
        if wav.size > MAX_SECONDS * SR:
            wav = wav[: int(MAX_SECONDS * SR)]          # 超长截断，不静默丢后面的话
        try:
            r = ENGINE.transcribe(wav, dialect, prompt=build_prompt(vocab))
        except Exception as e:                        # noqa: BLE001
            traceback.print_exc()
            return JSONResponse(status_code=503,
                                content={"error": "asr-failed", "detail": str(e)})
        r["vocab"] = use_vocab
        return r

    return app


app = build_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="info")