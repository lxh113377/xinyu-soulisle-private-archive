#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""声学场景合成 —— 让「安静/嘈杂/近场/远场」今天就可测，而不必去录四种环境。

方法论依据（不是拍脑袋，是 CHiME / DNS Challenge 的标准做法）：
用**干净语料 + 可控退化**复现声学条件差异。好处是条件可复现、SNR 可精确对齐、
比人工录制更省事；代价是合成条件不等于真实录音，故本模块产出的场景
**用于横向对比与回归**，绝对数值另需真实录音校验。

场景定义：
  clean     原样
  noisy     噪声混音，SNR ∈ {0,5,10,15,20} dB
  reverb    房间脉冲响应卷积，RT60 ∈ {0.3,0.6,1.0} s
  near      近场：+6dB 增益、高频保留（贴嘴说话）
  far       远场：距离衰减 + 空气吸收低通 + 混响 + 底噪

远场建模（四个可测物理量）：
  1) 球面扩散   声压 ∝ 1/r        ⇒ 每倍距离 -6 dB
  2) 空气吸收   高频先衰减        ⇒ 低通截止随距离下降
  3) 混响       直达声之外的能量堆积
  4) 底噪       房间本底噪声（本底随距离/混响上升，信噪比恶化）

依赖 numpy/scipy；无 scipy 时自动降级为纯 numpy 实现（低通用 FFT 掩模）。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

SR = 16000  # ASR 统一采样率（Qwen3-ASR / Whisper 系均为 16k）


# ─────────────────────────────────────────────────────────────────────────────
# 噪声源
# ─────────────────────────────────────────────────────────────────────────────
def synth_noise(kind: str, n: int, sr: int = SR, seed: int = 0) -> np.ndarray:
    """合成定长噪声（seed 固定 ⇒ 可复现）。

    kind: white / pink / brown / babble(多说话人重叠的近似) / hum(交流声)
    生产环境请用 MUSAN 或 DEMAND 的真实噪声替换 —— 本模块的合成噪声
    频谱特性是理想化的，用于回归可以，用于对外报数偏乐观。
    """
    rng = np.random.default_rng(seed)
    if kind == "white":
        return rng.standard_normal(n)

    if kind in ("pink", "brown"):
        # 1/f^p 谱：FFT 域幅度整形
        f = np.fft.rfftfreq(n, 1 / sr)
        p = 1.0 if kind == "pink" else 2.0
        shape = np.ones_like(f)
        shape[1:] = 1.0 / np.power(np.maximum(f[1:], f[1]), p / 2.0)
        # 去掉 DC 与 Nyquist 的奇异
        shape[0] = 0.0
        spec = (rng.standard_normal(len(f)) + 1j * rng.standard_normal(len(f))) * shape
        out = np.fft.irfft(spec, n)
        m = np.max(np.abs(out)) or 1.0
        return out / m

    if kind == "babble":
        # 多路不同速率的类语音调制噪声叠加，近似人群喧哗
        out = np.zeros(n)
        for k in range(6):
            rate = rng.uniform(3.0, 7.0)
            env = 0.5 + 0.5 * np.sin(2 * np.pi * rate * np.arange(n) / sr + rng.uniform(0, 6.28))
            out += env * rng.standard_normal(n)
        m = np.max(np.abs(out)) or 1.0
        return out / m

    if kind == "hum":
        t = np.arange(n) / sr
        return sum(np.sin(2 * np.pi * f * t) for f in (50, 100, 150)) / 3.0

    raise ValueError(f"未知噪声类型: {kind}")


def load_noise_bank(paths: List[str]) -> Dict[str, np.ndarray]:
    """从 wav 读入真实噪声（推荐 MUSAN noise）。"""
    import soundfile as sf
    bank = {}
    for p in paths:
        x, sr = sf.read(p, dtype="float32", always_2d=False)
        if x.ndim > 1:
            x = x.mean(axis=1)
        bank[p] = x
    return bank


# ─────────────────────────────────────────────────────────────────────────────
# 基础处理
# ─────────────────────────────────────────────────────────────────────────────
def rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(x, dtype=np.float64)))) if x.size else 0.0


def add_noise(sig: np.ndarray, noise: np.ndarray, snr_db: float) -> np.ndarray:
    """按目标 SNR 混噪。噪声长度不足则循环补足，过长则截断。"""
    if noise.size == 0:
        return sig
    if noise.size < sig.size:
        reps = int(np.ceil(sig.size / noise.size))
        noise = np.tile(noise, reps)
    noise = noise[: sig.size]
    ss, ns = rms(sig), rms(noise)
    if ss <= 0 or ns <= 0:
        return sig
    scale = ss / (ns * (10 ** (snr_db / 20.0)))
    return sig + noise * scale


def _lowpass(x: np.ndarray, cutoff_hz: float, sr: int = SR) -> np.ndarray:
    """FFT 域理想低通（无 scipy 依赖）。"""
    if cutoff_hz >= sr / 2:
        return x
    n = x.size
    spec = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / sr)
    spec[f > cutoff_hz] = 0.0
    return np.fft.irfft(spec, n)


def apply_gain(x: np.ndarray, db: float) -> np.ndarray:
    return x * (10 ** (db / 20.0))


# ─────────────────────────────────────────────────────────────────────────────
# 房间脉冲响应（镜像声源法）
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class Room:
    """鞋盒房间 + 简单吸声系数。"""
    lx: float = 6.0
    ly: float = 4.0
    lz: float = 2.8
    rt60: float = 0.4
    order: int = 12          # 镜像声源阶数（越高越准也越慢）
    absorption: float = 0.35 # 0~1，越大反射越少

    def rir(self, mic_pos: Tuple[float, float, float],
            src_pos: Tuple[float, float, float], sr: int = SR) -> np.ndarray:
        """一阶镜像法生成 RIR。够用于相对比较，不用于绝对声学仿真。"""
        c = 343.0
        refl = 1.0 - self.absorption
        img: List[Tuple[float, float, float, float]] = []
        for nx in range(-self.order, self.order + 1):
            for ny in range(-self.order, self.order + 1):
                for nz in range(-self.order, self.order + 1):
                    d = math.sqrt(nx * nx + ny * ny + nz * nz)
                    if d > self.order:
                        continue
                    amp = (refl ** d)
                    if amp < 1e-4:
                        continue
                    px = src_pos[0] + nx * self.lx
                    py = src_pos[1] + ny * self.ly
                    pz = src_pos[2] + nz * self.lz
                    dist = math.dist((px, py, pz), mic_pos)
                    img.append((dist, amp, px, py, pz))

        if not img:
            return np.array([1.0], dtype=np.float32)

        max_delay = max(int(d / c * sr) for d, _, _, _, _ in img) + 1
        # RIR 长度必须由 RT60 决定。镜像声源阶数只覆盖到 ~0.2s，
        # 若沿用镜像法长度，RT60 大的场景会被静默截断成 0.2s（实测踩过：
        # rt60=0.3 与 rt60=1.0 生成的 RIR 长度完全相同 ⇒ 混响场景形同虚设）。
        rt60_samples = int(math.ceil(max(self.rt60, 0.05) * sr))
        h = np.zeros(max(max_delay + 8, rt60_samples), dtype=np.float32)
        for d, amp, _, _, _ in img:
            k = int(round(d / c * sr))
            if k < h.size:
                h[k] += amp
        # 直达声归一：保证源在 1m 处音量一致，便于跨房间比较
        direct = min(img, key=lambda t: t[0])
        h = h / max(direct[1], 1e-6) * 0.6
        # 指数衰减尾（补足镜像法对高频衰减的缺失）
        t = np.arange(h.size) / sr
        tail = np.exp(-6.9078 * t / max(self.rt60, 1e-3))   # -60dB @ rt60
        h *= tail
        return h


def apply_reverb(sig: np.ndarray, rir: np.ndarray) -> np.ndarray:
    n = sig.size + rir.size
    return np.convolve(sig, rir)[: sig.size + 4].astype(np.float32)


# ─────────────────────────────────────────────────────────────────────────────
# 场景定义
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class Scenario:
    """一个可复现的声学条件。"""
    name: str
    kind: str                       # clean/noisy/reverb/near/far
    noise_kind: str = "white"
    snr_db: float = 20.0
    rt60: float = 0.0
    dist_m: float = 0.3
    seed: int = 0
    note: str = ""
    extra: Dict = field(default_factory=dict)


# 场景矩阵：安静 → 噪声 → 混响 → 近场 → 远场。覆盖要求 1 的四个维度。
SCENARIOS: Dict[str, Scenario] = {s.name: s for s in [
    Scenario("clean", "clean", note="原始干净语音"),
    Scenario("noisy_20db", "noisy", "babble", 20, note="轻度背景人声"),
    Scenario("noisy_10db", "noisy", "babble", 10, note="常规环境噪声"),
    Scenario("noisy_5db", "noisy", "white", 5, note="明显噪声"),
    Scenario("noisy_0db", "noisy", "white", 0, note="强噪声（信噪比 1:1）"),
    Scenario("reverb_0.3s", "reverb", rt60=0.3, note="小房间"),
    Scenario("reverb_0.6s", "reverb", rt60=0.6, note="中型空间"),
    Scenario("reverb_1.0s", "reverb", rt60=1.0, note="大空间/空旷"),
    Scenario("near_10cm", "near", dist_m=0.1, noise_kind="white", snr_db=25, note="贴嘴近场"),
    Scenario("far_1m", "far", dist_m=1.0, noise_kind="pink", snr_db=20, note="1 米远场"),
    Scenario("far_3m", "far", dist_m=3.0, noise_kind="pink", snr_db=15, note="3 米远场"),
    Scenario("far_5m", "far", dist_m=5.0, noise_kind="brown", snr_db=10, rt60=0.8,
             note="5 米远场 + 混响 + 棕噪（最恶劣）"),
]}


def apply_scenario(sig: np.ndarray, sc: Scenario, sr: int = SR,
                   noise_bank: Optional[Dict[str, np.ndarray]] = None) -> np.ndarray:
    """把一条干净语音变成指定声学条件下的音频。"""
    y = sig.astype(np.float32).copy()

    if sc.kind == "clean":
        return y

    if sc.kind == "near":
        # 近场：增益大、高频保留、混响少、底噪低
        y = apply_gain(y, +6.0)
        y = _lowpass(y, 8000, sr)
        y = add_noise(y, _pick_noise(sc, y.size, sr, noise_bank), sc.snr_db)
        return y

    if sc.kind == "noisy":
        return add_noise(y, _pick_noise(sc, y.size, sr, noise_bank), sc.snr_db)

    if sc.kind == "reverb":
        room = Room(rt60=sc.rt60)
        rir = room.rir(mic_pos=(room.lx / 2, room.ly / 2, 1.2),
                       src_pos=(room.lx / 2, room.ly / 2, 1.5), sr=sr)
        return apply_reverb(y, rir)

    if sc.kind == "far":
        d = max(sc.dist_m, 0.05)
        # 1) 球面扩散：声压 ∝ 1/d，相对 1m 归一 ⇒ d=1 时 0dB，每倍距离 -6dB
        y = apply_gain(y, -20.0 * math.log10(d))
        # 2) 空气吸收：高频随距离滚降
        cutoff = float(np.clip(8000.0 / (1.0 + 0.45 * d), 1800.0, 8000.0))
        y = _lowpass(y, cutoff, sr)
        # 3) 混响
        room = Room(rt60=sc.rt60 if sc.rt60 > 0 else 0.3 + 0.12 * d)
        rir = room.rir(mic_pos=(room.lx / 2, room.ly / 2, 1.2),
                       src_pos=(room.lx / 2, room.ly / 2 + d, 1.5), sr=sr)
        y = apply_reverb(y, rir)
        # 4) 底噪：远场信噪比恶化
        y = add_noise(y, _pick_noise(sc, y.size, sr, noise_bank), sc.snr_db)
        return y

    raise ValueError(f"未知场景类型: {sc.kind}")


def _pick_noise(sc: Scenario, n: int, sr: int, bank: Optional[Dict[str, np.ndarray]]) -> np.ndarray:
    if bank:
        keys = sorted(bank)
        return bank[keys[sc.seed % len(keys)]]
    return synth_noise(sc.noise_kind, n, sr, seed=sc.seed)


# ─────────────────────────────────────────────────────────────────────────────
def selftest() -> bool:
    ok = True
    sr = SR
    t = np.arange(int(0.6 * sr)) / sr
    tone = (0.3 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)

    def check(name, cond):
        nonlocal ok
        print(f"[{'OK ' if cond else 'FAIL'}] {name}")
        if not cond:
            ok = False

    check("clean 原样", np.allclose(apply_scenario(tone, SCENARIOS["clean"], sr), tone))

    # 噪声越强，有效信噪比越低 → 残差能量越大
    e20 = rms(apply_scenario(tone, SCENARIOS["noisy_20db"], sr) - tone)
    e10 = rms(apply_scenario(tone, SCENARIOS["noisy_10db"], sr) - tone)
    e0 = rms(apply_scenario(tone, SCENARIOS["noisy_0db"], sr) - tone)
    check(f"SNR 单调 (20dB={e20:.4f} < 10dB={e10:.4f} < 0dB={e0:.4f})", e20 < e10 < e0)

    # 远场：高频应被削掉
    hi = np.sin(2 * np.pi * 7000 * t).astype(np.float32) * 0.3
    near = apply_scenario(hi, SCENARIOS["near_10cm"], sr)
    far = apply_scenario(hi, SCENARIOS["far_3m"], sr)
    hf_near = rms(np.diff(near))    # 微分近似高频能量
    hf_far = rms(np.diff(far))
    check(f"远场高频衰减 (near={hf_near:.4f} > far={hf_far:.4f})", hf_near > hf_far)

    # 远场总增益应低于近场
    check("远场整体能量低于近场",
          rms(apply_scenario(tone, SCENARIOS["far_5m"], sr)) < rms(apply_scenario(tone, SCENARIOS["near_10cm"], sr)))

    # 混响：RT60 越大尾越长
    room_s = Room(rt60=0.3).rir((3, 2, 1.2), (3, 2, 1.5), sr)
    room_l = Room(rt60=1.0).rir((3, 2, 1.2), (3, 2, 1.5), sr)
    check(f"混响尾随 RT60 变长 ({room_s.size} < {room_l.size})", room_s.size < room_l.size)

    # 可复现性：同 seed 必须逐样本相同
    a = apply_scenario(tone, SCENARIOS["noisy_5db"], sr)
    b = apply_scenario(tone, SCENARIOS["noisy_5db"], sr)
    check("同 seed 完全可复现", np.array_equal(a, b))

    # 覆盖度：矩阵必须覆盖四类场景
    kinds = {s.kind for s in SCENARIOS.values()}
    check(f"场景矩阵覆盖 clean/noisy/reverb/near/far -> {sorted(kinds)}",
          {"clean", "noisy", "reverb", "near", "far"} <= kinds)
    check(f"场景数 {len(SCENARIOS)} >= 12", len(SCENARIOS) >= 12)

    print("SCENARIOS-SELFTEST-PASS" if ok else "SCENARIOS-SELFTEST-FAIL")
    return ok


if __name__ == "__main__":
    import sys
    sys.exit(0 if selftest() else 1)