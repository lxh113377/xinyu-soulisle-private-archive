# -*- coding: utf-8 -*-
"""心屿 · 本地神经语音合成服务（r118，决策 #11）

形态沿用 ml/server.py 的既有产线（同一条「Python 管模型服务，浏览器/Java 管调用」路径）：
  · FastAPI，127.0.0.1:8320 —— **只绑回环**，不出公网（与情绪模型腿 8300 同源红线）。
  · /health 自证：引擎已加载 + 说话人数 + 采样率 + 设备，缺任一项就不算「起成功了」。
  · 零密钥、零付费、离线可跑（模型在 D:/xinyu-ml/tts，见 .gitignore 的 ml/ 资产段）。

为什么是 sidecar 而不是直接把音频入库：浏览器自带 speechSynthesis 的中文音色机械感强，
老大定的替换路径是「本机开源引擎优先 + 浏览器兜底 + 字幕终兜」——引擎不在时前端必须
无感回落，公网面默认不探测（否则 CONSOLE_ERRORS:0 判据会被一条 ERR_CONNECTION_REFUSED 打破）。

安全边界（这个端口是"本机的"，不是"没人的"）：
  1. 只绑 127.0.0.1；
  2. Origin 白名单：回环 + localhost + 本项目的 Cloudflare Pages 域，其它来源 403
     （别的网站可以让这个端口替它跑推理，所以不放开 `*`）；
  3. 文本长度硬上限 + 说话人号越界即拒，不做无界拼接。

环境变量：
  XINYU_TTS_MODEL_DIR  模型目录（默认 D:/xinyu-ml/tts/vits-zh-aishell3）
  XINYU_TTS_MODEL      目录内 onnx 文件名（默认 vits-aishell3.onnx）
  XINYU_TTS_PORT       端口（默认 8320）
  XINYU_TTS_ORIGINS    额外放行 origin，逗号分隔
用法：D:/xinyu-ml/tts-venv/Scripts/python.exe ml/tts_server.py
"""
import io
import os
import time
import wave

import numpy as np
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel

DEFAULT_MODEL_DIR = "D:/xinyu-ml/tts/vits-zh-aishell3"
MODEL_DIR = os.environ.get("XINYU_TTS_MODEL_DIR", DEFAULT_MODEL_DIR)
MODEL_FILE = os.environ.get("XINYU_TTS_MODEL", "vits-aishell3.onnx")
PORT = int(os.environ.get("XINYU_TTS_PORT", "8320"))
MAX_TEXT = 300                      # 一句而已：分句朗读队列已经把长回复切短了
# 文本规整 FST（日期/数字/电话/多音字），文件名与模型包一致；缺文件就少一条，不硬撑。
RULE_FST_NAMES = ("date.fst", "number.fst", "phone.fst", "new_heteronym.fst")
ALLOWED_HOSTS = ("127.0.0.1", "localhost", "[::1]")

app = FastAPI(title="xinyu-local-tts")
_state = {"tts": None, "error": "", "load_ms": 0.0}


def origin_ok(req: Request):
    o = (req.headers.get("origin") or "").strip()
    if not o:                                    # 同源/命令行/无 CORS 的探测：无 Origin 头
        return True
    try:
        host = o.split("//", 1)[1].split(":", 1)[0].strip("[]") if "//" in o else ""
    except IndexError:
        return False
    extra = [x.strip() for x in os.environ.get("XINYU_TTS_ORIGINS", "").split(",") if x.strip()]
    if o in extra:
        return True
    if o.endswith(".pages.dev") or o.endswith(".xinyu.app"):
        return True
    return host in ALLOWED_HOSTS


def load():
    """一次性构造引擎。失败不抛（/health 如实报 error），但 /tts 会 503。"""
    if _state["tts"] or _state["error"]:
        return _state["tts"]
    try:
        import sherpa_onnx
    except ImportError as e:
        _state["error"] = " sherpa-onnx 未安装：%s" % e
        return None
    path = os.path.join(MODEL_DIR, MODEL_FILE)
    if not os.path.isfile(path):
        _state["error"] = "模型缺失：%s" % path
        return None
    fsts = [os.path.join(MODEL_DIR, f) for f in RULE_FST_NAMES if os.path.isfile(os.path.join(MODEL_DIR, f))]
    # 不同中文模型的文本前端布局不一样（aishell3 用 lexicon.txt；melo-tts 还带 jieba 的 dict/ 目录），
    # 存在才传，缺就传空串 —— 硬填不存在的路径会让 validate() 直接 False，报出来的还是"模型不完整"。
    def opt(sub):
        p = os.path.join(MODEL_DIR, sub)
        return p if os.path.exists(p) else ""
    t0 = time.perf_counter()
    try:
        cfg = sherpa_onnx.OfflineTtsConfig(
            model=sherpa_onnx.OfflineTtsModelConfig(
                vits=sherpa_onnx.OfflineTtsVitsModelConfig(
                    model=path,
                    lexicon=opt("lexicon.txt"),
                    tokens=opt("tokens.txt"),
                    data_dir=opt("espeak-ng-data"), dict_dir=opt("dict"),
                    noise_scale=0.667, noise_scale_w=0.8, length_scale=1.0),
                num_threads=2, debug=False, provider="cpu"),
            rule_fsts=",".join(fsts), rule_fars="", max_num_sentences=1, silence_scale=0.2)
        if not cfg.validate():
            _state["error"] = "OfflineTtsConfig.validate() 返回 False（模型目录不完整）"
            return None
        _state["tts"] = sherpa_onnx.OfflineTts(cfg)
        _state["load_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    except Exception as e:                                    # noqa: BLE001
        _state["error"] = "%s: %s" % (type(e).__name__, e)
    return _state["tts"]


class TtsReq(BaseModel):
    text: str = ""
    sid: int = 0
    speed: float = 1.0


@app.get("/health")
def health():
    tts = load()
    return {"status": "UP" if tts else "DOWN", "engine": "sherpa-onnx/vits",
            "model": os.path.basename(MODEL_DIR) + "/" + MODEL_FILE,
            "loaded": bool(tts), "numSpeakers": int(tts.num_speakers) if tts else 0,
            "sampleRate": int(tts.sample_rate) if tts else 0,
            "loadMs": _state["load_ms"], "error": _state["error"][:200]}


@app.post("/tts")
def tts(req: TtsReq, request: Request):
    if not origin_ok(request):
        raise HTTPException(403, "origin not allowed")
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(400, "empty text")
    if len(text) > MAX_TEXT:
        raise HTTPException(413, "text too long (max %d)" % MAX_TEXT)
    tts_engine = load()
    if not tts_engine:
        raise HTTPException(503, "engine not loaded: " + (_state["error"] or "unknown")[:120])
    sid = max(0, min(int(req.sid), int(tts_engine.num_speakers) - 1))
    speed = req.speed if 0.5 <= float(req.speed) <= 2.0 else 1.0
    t0 = time.perf_counter()
    audio = tts_engine.generate(text, sid=sid, speed=float(speed))
    ms = round((time.perf_counter() - t0) * 1000, 1)
    x = np.asarray(audio.samples, dtype=np.float32)
    if x.size == 0:
        raise HTTPException(502, "engine returned empty audio")
    peak = float(np.max(np.abs(x)))
    if peak > 1.0:
        x = x / peak
    pcm = np.clip(x * 32767.0, -32768, 32767).astype("<i2").tobytes()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(int(audio.sample_rate))
        w.writeframes(pcm)
    return Response(content=buf.getvalue(), media_type="audio/wav",
                    headers={"X-Tts-Ms": str(ms), "X-Tts-Sid": str(sid),
                             "X-Tts-Sample-Rate": str(int(audio.sample_rate))})


if __name__ == "__main__":
    import uvicorn
    load()
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
