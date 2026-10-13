# -*- coding: utf-8 -*-
"""心屿 · 本地语音识别 sidecar（B1，架构照抄决策 #11 的语音合成产线）

与 ml/tts_server.py 同一条产线（"Python 管模型服务，浏览器/Java 管调用"）：
  · FastAPI，127.0.0.1:8321 —— **只绑回环**，不出公网（情绪模型 8300 / TTS 8320 同源红线）。
  · /health 自证：引擎已加载 + 模型名 + 采样率 + 语言档 + provider，缺任一项不算"起成功了"。
  · 零密钥、零付费、离线可跑（模型在 D:/xinyu-ml/asr，见 .gitignore 的 ml/ 资产段）。

为什么需要它（不是重复造轮子）：浏览器 Web Speech 的声学/语言模型我们一行都碰不到，
而方言场景的核心缺口恰好在那一层 —— 粤语用户说的话常被谐音错字压过（r176 实证）。
本 sidecar 提供**有粤语原生能力**的转写腿，作为 Web Speech 的替代/对照。

能力边界（如实声明，别当成已有）：
  1. **只做文件转写**，不做流式、不接麦克风 —— 浏览器端若要实时，仍需在 Web Speech 的
     onresult 里调 /asr 做二次确认（属下一步，未做）。
  2. 输入音频一律重采样到 16kHz 单声道（SenseVoice 的固定输入）；非 16k 输入走线性插值，
     响应里 resampled=true 会标出来（线性插值不是高质量重采样，这是已知代价）。
  3. provider 默认 cpu。GPU 需另装 onnxruntime-gpu 并置 XINYU_ASR_PROVIDER=cuda，
     本机 RTX 5070 Ti 的 sm_120 兼容性未实测，**不预设能用**。

安全边界（与 tts_server 同三条）：
  1. 只绑 127.0.0.1；
  2. Origin 白名单：回环 + localhost + 本项目的 Cloudflare Pages 域，其它来源 403；
  3. 体积/时长硬上限，越界即拒，不做无界接收。

环境变量：
  XINYU_ASR_MODEL_DIR  模型目录（默认 D:/xinyu-ml/asr/sensevoice-int8-2024-07-17）
  XINYU_ASR_LANG       语言档 auto|zh|yue|en|ja|ko（默认 auto，让模型自己判）
  XINYU_ASR_PROVIDER   推理后端 cpu|cuda（默认 cpu）
  XINYU_ASR_PORT       端口（默认 8321）
  XINYU_ASR_ORIGINS    额外放行 origin，逗号分隔
用法：D:/xinyu-ml/asr-venv/Scripts/python.exe ml/asr_server.py
"""
import base64
import binascii
import io
import os
import time

import numpy as np
import soundfile as sf
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from pydantic import BaseModel

DEFAULT_MODEL_DIR = "D:/xinyu-ml/asr/sensevoice-int8-2024-07-17"
MODEL_DIR = os.environ.get("XINYU_ASR_MODEL_DIR", DEFAULT_MODEL_DIR)
MODEL_FILE = "model.int8.onnx"
LANG = os.environ.get("XINYU_ASR_LANG", "auto")
PROVIDER = os.environ.get("XINYU_ASR_PROVIDER", "cpu")
PORT = int(os.environ.get("XINYU_ASR_PORT", "8321"))
MAX_BYTES = 8 * 1024 * 1024        # 8MB ≈ 16kHz 单声道 16bit 约 4 分钟，远超 30s 上限
MAX_SECONDS = 30.0                 # 一句而已：分句队列与通话浮层都不送长音频
ALLOWED_LANGS = ("auto", "zh", "yue", "en", "ja", "ko")
ALLOWED_HOSTS = ("127.0.0.1", "localhost", "[::1]")

app = FastAPI(title="xinyu-local-asr")
_state = {"rec": None, "error": "", "load_ms": 0.0}


def origin_ok(req: Request):
    """与 tts_server 逐条同构：无 Origin 头（命令行/同源探测）放行，其余按白名单"""
    o = (req.headers.get("origin") or "").strip()
    if not o:
        return True
    try:
        host = o.split("//", 1)[1].split(":", 1)[0].strip("[]") if "//" in o else ""
    except IndexError:
        return False
    extra = [x.strip() for x in os.environ.get("XINYU_ASR_ORIGINS", "").split(",") if x.strip()]
    if o in extra:
        return True
    if o.endswith(".pages.dev") or o.endswith(".xinyu.app"):
        return True
    return host in ALLOWED_HOSTS


def load():
    """一次性构造识别器。失败不抛（/health 如实报 error），但 /asr 会 503。"""
    if _state["rec"] or _state["error"]:
        return _state["rec"]
    path = os.path.join(MODEL_DIR, MODEL_FILE)
    if not os.path.isfile(path):
        _state["error"] = "模型缺失：%s（先跑 ml/fetch_asr_models.py）" % path
        return None
    try:
        import sherpa_onnx as s
    except ImportError as e:
        _state["error"] = "sherpa-onnx 未安装：%s" % e
        return None
    if LANG not in ALLOWED_LANGS:
        _state["error"] = "XINYU_ASR_LANG=%r 不在 %s" % (LANG, ALLOWED_LANGS)
        return None
    t0 = time.perf_counter()
    try:
        # API 形状（sherpa-onnx 1.13.8 实测，与旧文档不同）：
        # 顶层 OfflineRecognizer() 已不接 config，须走 from_sense_voice 工厂；
        # 且 tokens/num_threads/provider 属于 OfflineModelConfig 而非顶层。
        _state["rec"] = s.OfflineRecognizer.from_sense_voice(
            model=path,
            tokens=os.path.join(MODEL_DIR, "tokens.txt"),
            language=LANG, use_itn=True,
            num_threads=int(os.environ.get("XINYU_ASR_THREADS", "2")),
            provider=PROVIDER, debug=False)
        _state["load_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    except Exception as e:                                    # noqa: BLE001
        _state["error"] = "%s: %s" % (type(e).__name__, e)
    return _state["rec"]


def to_16k_mono(data: bytes):
    """读上传音频 → (samples_float32_16k, 原采样率, 是否重采样)。解析失败一律抛给调用方。"""
    samples, sr = sf.read(io.BytesIO(data), dtype="float32", always_2d=False)
    if samples.ndim > 1:
        samples = samples.mean(axis=1)                       # 多声道先混单
    if sr != 16000:
        n = int(round(len(samples) * 16000.0 / sr))
        if n <= 0:
            raise ValueError("重采样后长度为 0（原采样率 %s，样本 %d）" % (sr, len(samples)))
        idx = np.arange(n, dtype=np.float64) * (sr / 16000.0)
        lo = np.floor(idx).astype(np.int64).clip(0, len(samples) - 1)
        hi = np.ceil(idx).astype(np.int64).clip(0, len(samples) - 1)
        frac = idx - lo
        samples = (samples[lo] * (1.0 - frac) + samples[hi] * frac).astype(np.float32)
        return samples, int(sr), True
    return samples, int(sr), False


@app.get("/health")
def health():
    rec = load()
    return {"status": "UP" if rec else "DOWN", "engine": "sherpa-onnx/sense-voice",
            "model": os.path.basename(MODEL_DIR) + "/" + MODEL_FILE,
            "language": LANG, "provider": PROVIDER,
            "sampleRate": 16000, "loaded": bool(rec),
            "loadMs": _state["load_ms"], "error": _state["error"][:200]}


class AsrJson(BaseModel):
    audio_b64: str = ""          # base64 整段音频：浏览器端 multipart 不便时的备选入口


@app.post("/asr")
async def asr(request: Request):
    """两个入口：multipart 的 file 字段，或 JSON 的 audio_b64。

    ⚠ 不用 FastAPI 的 `file: UploadFile = File(None), payload: AsrJson = None` 双 body 签名：
    实测那样写时纯 JSON 请求会被当成"缺 file"而 400（两个可选 body 组合的解析顺序问题），
    错误信息还指向不到根因。改成自己按 Content-Type 分派，行为可预测。
    """
    if not origin_ok(request):
        raise HTTPException(403, "origin not allowed")
    ctype = (request.headers.get("content-type") or "").split(";")[0].strip().lower()
    if ctype == "application/json":
        try:
            body = await request.json()
        except Exception as e:                                # noqa: BLE001
            raise HTTPException(400, "JSON body 解析失败：%s" % str(e)[:100])
        b64 = (body or {}).get("audio_b64") or "" if isinstance(body, dict) else ""
        if not b64:
            raise HTTPException(400, "audio_b64 为空")
        try:
            data = base64.b64decode(b64, validate=True)
        except (binascii.Error, ValueError) as e:
            raise HTTPException(400, "audio_b64 不是合法 base64：%s" % e)
    else:
        form = await request.form()
        up = form.get("file")
        if up is None or not getattr(up, "filename", ""):
            raise HTTPException(400, "缺音频：multipart 的 file 或 JSON 的 audio_b64 至少要给一个")
        data = await up.read()
    if not data:
        raise HTTPException(400, "empty audio")
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "audio too large (max %d B)" % MAX_BYTES)
    rec = load()
    if not rec:
        raise HTTPException(503, "engine not loaded: " + (_state["error"] or "unknown")[:120])
    try:
        wav, sr, resampled = to_16k_mono(data)
    except Exception as e:                                    # noqa: BLE001
        # 坏音频是**调用方**的错，不是引擎的错 ⇒ 400 而不是 502
        raise HTTPException(400, "音频解析失败：%s: %s" % (type(e).__name__, str(e)[:120]))
    secs = len(wav) / 16000.0
    if secs > MAX_SECONDS:
        raise HTTPException(413, "audio too long (%.1fs > %.0fs)" % (secs, MAX_SECONDS))
    if secs < 0.05:
        raise HTTPException(400, "audio too short (%.3fs)" % secs)
    t0 = time.perf_counter()
    st = rec.create_stream()
    st.accept_waveform(16000, wav.tolist())
    rec.decode_stream(st)
    ms = round((time.perf_counter() - t0) * 1000, 1)
    text = (st.result.text or "").strip()
    if not text:
        raise HTTPException(502, "engine returned empty text")
    return {"text": text, "seconds": round(secs, 3), "decodeMs": ms,
            "language": LANG, "sampleRateIn": sr, "resampled": resampled,
            "provider": PROVIDER}


if __name__ == "__main__":
    import uvicorn
    load()
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
