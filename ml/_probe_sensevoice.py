# -*- coding: utf-8 -*-
"""一次性探针：确认 sherpa-onnx 1.13.8 的 SenseVoice 配置在本机能跑通（B1 摸 API 用）

只做三件事：建 config → validate() → 用上游自带的 test_wavs/yue.wav 跑一次解码，
打出识别文本。探针通过才值得把 API 抄进 ml/asr_server.py。

API 形状（1.13.8 实测，与文档里的旧写法不同）：tokens / num_threads / provider 都在
**OfflineModelConfig** 里，不在顶层 OfflineRecognizerConfig；顶层只收 feat_config /
model_config / decoding_method 等。按文档旧写法会 TypeError，pybind 连错误参数名都不给。
"""
import time

import sherpa_onnx as s

DIR = "D:/xinyu-ml/asr/sensevoice-int8-2024-07-17"

cfg = s.OfflineRecognizerConfig(
    feat_config=s.FeatureExtractorConfig(sampling_rate=16000, feature_dim=80),
    model_config=s.OfflineModelConfig(
        sense_voice=s.OfflineSenseVoiceModelConfig(
            model=DIR + "/model.int8.onnx",
            language="auto",
            use_itn=True,
        ),
        tokens=DIR + "/tokens.txt",
        num_threads=2,
        debug=False,
        provider="cpu",
    ),
)
print("model_config.validate():", cfg.model_config.validate())

t0 = time.perf_counter()
rec = s.OfflineRecognizer.from_sense_voice(
    model=DIR + "/model.int8.onnx",
    tokens=DIR + "/tokens.txt",
    language="auto",
    use_itn=True,
    num_threads=2,
    provider="cpu",
    debug=False,
)
print("load_ms:", round((time.perf_counter() - t0) * 1000, 1))
print("sample_rate:", rec.config.feat_config.sampling_rate)

import soundfile as sf

st = rec.create_stream()
wav, sr = sf.read(DIR + "/test_wavs/yue.wav", dtype="float32")
if wav.ndim > 1:
    wav = wav.mean(axis=1)          # 多声道先混单，别让模型听双份
st.accept_waveform(sr, wav.tolist())
t1 = time.perf_counter()
rec.decode_stream(st)
print("decode_ms:", round((time.perf_counter() - t1) * 1000, 1))
print("TEXT:", repr(st.result.text))
