#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Qwen3-ASR 推理引擎封装（Qwen/Qwen3-ASR-0.6B-hf）。

为什么是 transformers 路径而不是 local-asr skill 的 OpenVINO 路径：
  1) LoRA 微调必须在 PyTorch 原生权重上做（peft 只认 nn.Module）；
  2) 微调后要 merge 回基座再导出 OpenVINO IR 才能继续走 NPU 推理。
  ⇒ PyTorch 是训练+评测的主线，OpenVINO 仅作为交付部署的加速后端。

本模块只负责「音频 → 文本」与计时，不含任何评测逻辑（评测在 run_eval.py）。
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import List, Optional, Sequence

# Qwen3-ASR-0.6B 官方口径：30 语种 + **22 种中国方言**（模型卡 L62 表格）。
# 方言是用「语言名」而不是 ISO 码选的，取值必须与模型卡逐字一致，否则会静默回落
# 成中文通道 —— 实测踩过：language='yue' 与 language='zh' 对普通话音频输出一字不差。
# 已核对的六目标方言（全部命中模型原生支持，见模型卡 Supported Dialects 列）：
#   mandarin→Chinese / yue→Cantonese / chuan→Sichuan
#   dongbei→Dongbei / wu→Wu / minnan→Minnan
LANG_HINTS = {
    # 唯一能强制的方言码（transformers 只认 30 个语种码，方言名一律被拒）
    "yue": "Cantonese",
    "mandarin": "Chinese",
    "en": "English",
    # 其余方言**故意不列**：传 None = 不带 language 参数，走模型自动语种识别。
    # 曾经按模型卡把 chuan/dongbei/wu/minnan 映射成 "Sichuan"/"Dongbei"/"Wu"/"Minnan"，
    # 结果 run_eval 一跑就 ValueError: Unsupported language: 'Sichuan'（实测踩过）。
    "chuan": None,
    "wu": None,
    "dongbei": None,
    "minnan": None,
    "teochew": None,
    "zongyuan": None,
}


def validate_lang_hints() -> None:
    """启动时自检：任何非 None 的映射必须是模型真认的值。

    意义：把「方言名不被接受」这个坑从**跑分跑到一半炸**变成**加载即报**。
    这类错误发生在批处理中途时，报错现场（栈底是某条音频）与真因（映射表写错）
    隔了很远，极易误判成数据问题。"""
    try:
        from transformers.models.qwen3_asr.processing_qwen3_asr import LANGUAGE_CODE_TO_NAME
    except Exception:
        return
    valid = set(LANGUAGE_CODE_TO_NAME.values()) | set(LANGUAGE_CODE_TO_NAME.keys())
    bad = {k: v for k, v in LANG_HINTS.items() if v is not None and v not in valid}
    if bad:
        raise ValueError(
            f"LANG_HINTS 含模型不接受的取值 {bad}；"
            f"方言名（如 Sichuan/Wu/Minnan）不是合法 language，只能留 None 走自动识别")


@dataclass
class Hyp:
    """单条识别结果 + 计时。"""
    text: str
    infer_s: float
    audio_s: float
    load_s: float = 0.0

    @property
    def rtf(self) -> float:
        """实时率：推理耗时 / 音频时长。<1 表示比实时快。"""
        return self.infer_s / self.audio_s if self.audio_s > 0 else 0.0


class QwenASR:
    """Qwen3-ASR 封装。首次构造加载模型，之后复用。"""

    def __init__(self, model_id: str = "Qwen/Qwen3-ASR-0.6B-hf",
                 device: str = "cuda", dtype: str = "bfloat16",
                 max_new_tokens: int = 256, enable_lora: bool = False,
                 lora_path: Optional[str] = None, verbose: bool = True):
        import torch
        from transformers import AutoProcessor, AutoModelForMultimodalLM

        self.torch = torch
        self.verbose = verbose
        self.model_id = model_id
        t0 = time.perf_counter()
        self.device = device if (device != "cuda" or torch.cuda.is_available()) else "cpu"
        if self.device == "cpu" and verbose:
            print("[WARN] CUDA 不可用，回落 CPU —— 推理会慢一个量级，"
                  "确认已装 CUDA 版 torch（--index-url .../whl/cu128）")
        self.dtype = getattr(torch, dtype) if self.device != "cpu" else torch.float32

        validate_lang_hints()          # 先验映射再加载模型（加载要 2s，不值得为验错买单）
        self.processor = AutoProcessor.from_pretrained(model_id)
        self.model = AutoModelForMultimodalLM.from_pretrained(
            model_id, dtype=self.dtype).to(self.device).eval()

        if enable_lora and lora_path:
            from peft import PeftModel
            self.model = PeftModel.from_pretrained(self.model, lora_path)
            self.model = self.model.merge_and_unload()   # 合并后再推理，零额外开销
            if verbose:
                print(f"[OK ] 已加载并合并 LoRA: {lora_path}")
        elif enable_lora:
            raise ValueError("enable_lora=True 必须给 lora_path")

        self.max_new_tokens = max_new_tokens
        self.load_s = time.perf_counter() - t0
        if verbose:
            dev = (f"cuda:{torch.cuda.current_device()}" if self.device == "cuda"
                   else self.device)
            print(f"[OK ] 模型已加载 {model_id} on {dev} ({dtype}) 用时 {self.load_s:.1f}s")

    # ── 推理 ──────────────────────────────────────────────────────────────────
    def transcribe_batch(self, audios: Sequence, dialect: str = "mandarin",
                         use_lang_hint: bool = True,
                         prompt: Optional[str] = None) -> List[str]:
        """批量转写。audios 为等长 float32 numpy（16k 单声道）。

        :param prompt: 领域词典/热词偏置（模型卡 Context/hotwords）。
                       方言专名与俚语的首选手段 —— 不需要 LoRA 就能纠偏。
        """
        torch = self.torch
        if not audios:
            return []
        lang = LANG_HINTS.get(dialect) if use_lang_hint else None
        kwargs = {}
        if prompt:
            kwargs["prompt"] = prompt
        if lang:
            kwargs["language"] = lang

        inputs = self.processor.apply_transcription_request(list(audios), **kwargs)
        inputs = inputs.to(self.model.device)
        if self.device == "cuda":
            # 只在 CUDA 半精度下转 dtype；CPU 上强转会拖慢且无收益
            try:
                inputs = inputs.to(self.dtype)
            except Exception:
                pass

        with torch.inference_mode():
            # ⚠ 必须 **inputs 解包，不能位置传整个 BatchFeature。
            #   位置传时 generate 会把它塞进 model_kwargs，于是
            #   `inputs_tensor.shape[0]` 打在 BatchFeature.__getattr__ 上 → AttributeError
            #   （实测踩过，见 _test/asr/README.md 踩坑记录）
            out = self.model.generate(**inputs, max_new_tokens=self.max_new_tokens,
                                      do_sample=False)
        gen = out[:, inputs["input_ids"].shape[1]:]
        return [self._decode(g) for g in gen]

    def _decode(self, gen_ids) -> str:
        """取纯转写文本。

        首选官方 `return_format='transcription_only'`，它会自动剥掉
        `language Chinese<asr_text>` 前缀；老版本 transformers 不支持时
        退回手工剥壳。两条路都必须产出**纯正文**，否则 CER 全错。
        """
        try:
            return self.processor.decode(gen_ids, return_format="transcription_only").strip()
        except (TypeError, ValueError, AttributeError):
            pass
        raw = self.processor.decode(gen_ids)
        for sep in ("<asr_text>",):
            if sep in raw:
                raw = raw.split(sep, 1)[1]
                break
        else:
            # 没有 asr_text 标记：剥掉前导的 "language XXX" 前缀
            raw = re.sub(r"^\s*language\s+\S+\s*", "", raw)
        return raw.strip()

    def transcribe(self, audio, dialect: str = "mandarin",
                   use_lang_hint: bool = True, prompt: Optional[str] = None) -> Hyp:
        """单条转写 + 计时（用于性能基线，要求 5 的响应速度判据）。"""
        audio_s = len(audio) / 16000.0
        t0 = time.perf_counter()
        text = self.transcribe_batch([audio], dialect, use_lang_hint, prompt)[0]
        return Hyp(text=text, infer_s=time.perf_counter() - t0,
                   audio_s=audio_s, load_s=self.load_s)


def check_env() -> bool:
    """环境自检：把「装没装对」变成可执行判据，而不是等跑分时才发现。"""
    ok = True

    def chk(name, cond, detail=""):
        nonlocal ok
        print(f"[{'OK ' if cond else 'FAIL'}] {name}{(' -> ' + detail) if detail else ''}")
        if not cond:
            ok = False

    import sys
    chk(f"Python {sys.version.split()[0]}", sys.version_info >= (3, 10),
        "需要 >= 3.10（transformers / peft 要求）")
    try:
        import torch
        chk(f"torch {torch.__version__}", True)
        cuda = torch.cuda.is_available()
        chk("CUDA 可用", cuda,
            torch.cuda.get_device_name(0) if cuda else
            "装成了 CPU 版 torch —— LoRA 训练会慢到不可接受，重装："
            "uv pip install torch --index-url https://download.pytorch.org/whl/cu128")
        if cuda:
            vram = torch.cuda.get_device_properties(0).total_memory / 1024**3
            chk(f"显存 {vram:.1f} GB >= 8GB", vram >= 8,
                "0.6B 模型 LoRA 微调建议 >= 8GB")
    except ImportError:
        chk("torch 已安装", False, "pip install torch")
    for m in ("transformers", "peft", "numpy", "soundfile"):
        try:
            __import__(m)
            chk(f"{m} 已安装", True)
        except ImportError:
            chk(f"{m} 已安装", False, f"pip install {m}")

    print("ENGINE-ENV-PASS" if ok else "ENGINE-ENV-FAIL")
    return ok


if __name__ == "__main__":
    import sys
    sys.exit(0 if check_env() else 1)