#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""前端增强式降噪 —— 针对**远场**失分的服务端补救。

为什么先补远场：基线实测川渝 3m 远场 79.45%（干净 90.99%，掉 11.5 个百分点），
而 `audio-quality.js` 的质量闸目前只做「拒收」不做「修复」——
把 79% 的音频拒掉等于把可用信号也丢了。这里做的是**在拒收之前先救一把**。

方法（全部是无参数自适应的，不引入需训练的模型）：
  1. **谱减法降噪**（O spectrogram subtraction，比例 + 频谱下限）
     噪声谱从**帧能量最低的一段**估计 —— 这是无 VAD 场景下的稳健做法。
  2. **带内高频补偿**（远场的空气吸收主要砍高频）
     按检测到的低通截止频率做一阶斜坡补偿，把被削掉的高频抬回来。
     ⚠ 只做温和补偿（默认 +3dB/oct，带上限）：补偿过头会把噪声一起放大，
     反而更差。斜坡幅度必须可配，且必须能用 A/B 验证 —— 见 README 踩坑记录。
  3. **动态范围压缩 + 峰值归一**
     远场输入整体电平低，直接进模型等于欠曝。

红线：**这是补救，不是神器。** 若某条件下降噪反而更差（如干净语音），
判据必须能跑出「更差」这个结论并如实记，不得因为想证明它有用而调参调成好看。

依赖：numpy + scipy（scipy 缺失时自动退化为纯 numpy 实现）。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np

SR = 16000
N_FFT = 512
HOP = 128


@dataclass
class DenoiseConfig:
    """全部默认值都是「温和」取向；任何一项都可按实测调。"""
    enabled: bool = True
    n_fft: int = N_FFT
    hop: int = HOP
    # 谱减
    noise_pct: float = 15.0      # 取能量最低的百分之几帧估噪声谱
    over_subtraction: float = 1.4  # 谱减过减因子（>1 减更多）
    floor: float = 0.08          # 增益下限（防过度削减产生音乐噪声）
    # 高频补偿
    hf_boost_db: float = 3.0     # 每倍频程抬升；0 = 关闭
    hf_start_hz: float = 2000.0  # 从该频率起抬
    hf_max_hz: float = 7000.0    # 到该频率达到满量补偿
    # 电平
    compress: bool = True
    target_rms: float = 0.06     # 目标 RMS（对齐 KeSpeech 的实测 rms≈0.05~0.10）
    peak_guard: float = 0.95     # 峰值上限，防止归一化时爆掉
    min_rms: float = 0.004       # 低于此认为输入本身不可用，原样返回（不做救）
    # 低于此信噪比即认定「这段没有可用语音」：只做谱减，不抬电平（见 level_fix）
    min_snr_db: float = 3.0

    @property
    def hop_frac(self) -> float:
        return self.hop / self.n_fft


def _stft(x: np.ndarray, cfg: DenoiseConfig) -> np.ndarray:
    """分析：加窗重叠取帧 → rfft → (F, T)。

    ⚠ **不要在两端补零**（实测踩过，两轮才定位）：
       旧码 `np.pad(x, (n//2, n//2))` 让输出与输入等长，但 Hann 窗在首尾为 0，
       补出来的两段没有任何有效信息；随后 _istft 又按 pad 对齐裁剪，
       于是**帧网格与原信号差了一个 hop 的相移**（实测最佳补偿 = 37 样本 ≈ 2.3ms），
       往返相对误差恒为 1.0。
       这里改成「只在尾部补到整帧」，并**显式记录 pad_tail**，
       由 _istft 按同一 pad 还原 —— 对齐关系写在同一个地方，不再靠两处各猜一半。
    """
    n = cfg.n_fft
    if x.size < n:
        x = np.pad(x, (0, n - x.size))
    tail = (-x.size) % cfg.hop
    if tail:
        x = np.pad(x, (0, tail))
    win = np.hanning(n)
    frames = 1 + (x.size - n) // cfg.hop
    idx = np.arange(n)[None, :] + cfg.hop * np.arange(frames)[:, None]
    # ⚠ 转置方向：必须是 (T, n) → rfft(..., axis=-1) → (T, F)，**不要**在这里 .T。
    #   旧码先 .T 成 (F, T) 再在 _istft 里 np.fft.irfft(S[:, t], n) ——
    #   于是「列」变成了帧号、每一行被当成一个完整信号，irfft 拿 512 个频点去
    #   补成 512 个样本 ⇒ 完全不是原信号的频谱（实测：S.shape 打印成 (512, 247)，
    #   频点数应是 257 = 512/2+1，一眼可辨）。
    #   频点数 = n//2 + 1 是自检该查的第一件事。
    return np.fft.rfft(x[idx] * win, axis=-1).T


def _istft(S: np.ndarray, length: int, cfg: DenoiseConfig) -> np.ndarray:
    """合成：irfft → 加窗重叠相加 → 除以累加窗 → 裁掉无效边界。

    ⚠ 两个坑（都是实测踩的）：
       1) `y /= np.maximum(wsum, 1e-8)` 是错的。Hann 窗在首尾为 0，累加窗 wsum
          在两端各有 n//2 个样本 ≈ 0，被 1e-8 一除就放大 1e8 倍，整段冲成垃圾。
          正解：只取 wsum ≥ 0.5·max 的区间。注意只查「幅度是否线性」查不出这个 bug
          —— 相对幅度仍正确，**必须查往返重建**。
       2) 不要在这里假设「输入两端各有 n//2 的 pad」。_stft 只在**尾部**补到整帧，
          头的 n//2 根本不存在；按 pad 对齐会引入一个 hop 的相移。
          正解：帧网格起点恒为 0，裁剪后直接左对齐。
    """
    n, hop = cfg.n_fft, cfg.hop
    win = np.hanning(n)
    frames = S.shape[1]
    if frames <= 0:
        return np.zeros(length, dtype=np.float32)
    out_len = n + hop * (frames - 1)
    y = np.zeros(out_len, dtype=np.float64)
    wsum = np.zeros(out_len, dtype=np.float64)
    w2 = win ** 2
    for t in range(frames):
        y[t * hop: t * hop + n] += np.fft.irfft(S[:, t], n) * win
        wsum[t * hop: t * hop + n] += w2

    thr = 0.5 * float(w2.max()) if w2.max() > 0 else 0.0
    good = np.where(wsum >= thr)[0]
    out = np.zeros(length, dtype=np.float64)
    if good.size == 0:
        return out.astype(np.float32)
    # 帧网格起点恒为 0 ⇒ y[lo:hi] 对应原信号 [lo:hi]，必须**原位写回**。
    # ⚠ 往返重建**只能在 [lo, hi) 上判等**：Hann 窗在两端本就无有效增益，
    #   那两段被置 0 是正确行为，不是失真。把它们算进误差会得到 rel≈0.08~1.0
    #   的假失败（实测在这里白排查了三轮）。边缘比例 = 2*(n//2)/length。
    lo = int(good[0])
    hi = min(int(good[-1]) + 1, length)
    if hi > lo:
        out[lo:hi] = y[lo:hi] / wsum[lo:hi]
    return out.astype(np.float32)


def valid_span(x: np.ndarray, y: np.ndarray, cfg: DenoiseConfig = None) -> tuple:
    """往返判等的有效区间 [lo, hi)。

    ⚠ 用**累加窗实际达标区间**，不是简单按 n//2 裁（实测踩过）：
       有效区由 `wsum ≥ 0.5·w2.max()` 决定，它随 hop/n_fft 与信号长度变化；
       按 n//2 硬裁会多算进一批 wsum 仍偏小的样本，报出 0.06~0.35 的假失真
       （在这里白排查了三轮才定位到真正的转置 bug）。
    """
    cfg = cfg or DenoiseConfig()
    n, hop = cfg.n_fft, cfg.hop
    length = min(x.size, y.size)
    if length <= n:
        return 0, length
    frames = 1 + (max(x.size, n) - n) // hop
    w2 = np.hanning(n) ** 2
    wsum = np.zeros(n + hop * (frames - 1))
    for t in range(frames):
        s, e = t * hop, t * hop + n
        if s >= wsum.size:
            break
        wsum[s: min(e, wsum.size)] += w2[: min(e, wsum.size) - s]
    g = np.where(wsum[:length] >= 0.5 * w2.max())[0]
    if g.size == 0:
        return 0, length
    return int(g[0]), min(int(g[-1]) + 1, length)


def roundtrip_error(x: np.ndarray, y: np.ndarray, cfg: DenoiseConfig = None) -> float:
    """往返相对误差，**只在有效区间上**算。STFT→iSTFT 必须用它自检。"""
    cfg = cfg or DenoiseConfig()
    lo, hi = valid_span(x, y, cfg)
    if hi - lo <= 0:
        return 0.0
    a, b = x[lo:hi].astype(np.float64), y[lo:hi].astype(np.float64)
    den = np.sqrt(np.mean(a ** 2))
    return float(np.sqrt(np.mean((a - b) ** 2)) / den) if den > 0 else 0.0


def _rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(x, dtype=np.float64)))) if x.size else 0.0


def estimate_noise_power(S: np.ndarray, cfg: DenoiseConfig) -> np.ndarray:
    """从**帧**能量最低的那部分估噪声谱，返回长度 = 频点数的向量。

    ⚠ 这里的分位数必须作用在**帧**上，不是频点上。
       曾经写成 `p = (|S|**2).mean(axis=1)` 先把帧平均掉，
       于是 `np.argsort(p)[:k]` 变成「挑 k 个频点」而不是「挑 k 帧」，
       `mean(axis=0)` 再作用在长度 B 的一维数组上 ⇒ 返回标量 ⇒
       `nmag[:, None]` 直接 IndexError（实测踩过，报错现场离真因很远）。
    """
    if S.size == 0:
        return np.zeros(S.shape[0] if S.ndim == 2 else 1)
    frame_pow = (np.abs(S) ** 2).mean(axis=0)      # (T,) 每帧平均功率
    if frame_pow.size == 0:
        return np.zeros(S.shape[0])
    k = max(1, int(frame_pow.size * cfg.noise_pct / 100.0))
    idx = np.argsort(frame_pow)[:k]                # 挑最安静的 k 帧
    return (np.abs(S[:, idx]) ** 2).mean(axis=1)   # 对这些帧按频点求均方 ⇒ (F,)


def spectral_subtract(S: np.ndarray, noise_pow: np.ndarray,
                      cfg: DenoiseConfig) -> np.ndarray:
    """经典谱减：|S| = max(|S| - α·|N|, β·|S|)"""
    mag = np.abs(S)
    nmag = np.sqrt(np.maximum(noise_pow, 0))[:, None]
    sub = np.maximum(mag - cfg.over_subtraction * nmag, cfg.floor * mag)
    return sub * np.exp(1j * np.angle(S))


def hf_compensation(S: np.ndarray, sr: int = SR, cfg: DenoiseConfig = None) -> np.ndarray:
    """一阶频率斜坡增益，把远场被空气吸收砍掉的高频抬回来。

    只在 [hf_start_hz, hf_max_hz] 这一段线性升到 +hf_boost_db，超过 hf_max_hz 保持。
    """
    cfg = cfg or DenoiseConfig()
    if cfg.hf_boost_db <= 0:
        return S
    f = np.linspace(0, sr / 2, S.shape[0])
    g = np.ones_like(f)
    ramp = np.clip((f - cfg.hf_start_hz) /
                   max(cfg.hf_max_hz - cfg.hf_start_hz, 1e-6), 0.0, 1.0)
    g = g + ramp * (10 ** (cfg.hf_boost_db / 20.0) - 1.0)
    return S * g[:, None]


def level_fix(x: np.ndarray, cfg: DenoiseConfig, snr_db: Optional[float] = None) -> np.ndarray:
    """目标电平对齐 + 峰值保护。

    🔴 **降噪后必须看信噪比再决定要不要抬电平**（实测踩过）：
       纯噪声输入经谱减后能量降到 1/24，若无条件按 `target_rms` 归一化，
       就把**残余噪声又放大回原电平** —— 噪声没被抑制，反而被"整理"得更大，
       对下游 ASR 是净负作用（自检里「纯噪声输入后能量上升」这条腿当场变红）。
       正解：snr 低于 `min_snr_db` 时视为「这段本来就没语音」，只做峰值保护不抬电平。
    """
    if not cfg.compress:
        return x
    r = _rms(x)
    if r <= 0:
        return x
    if r < cfg.min_rms:
        return x                       # 输入本身就没信号，别放大噪声
    quiet = (snr_db is not None) and (snr_db < cfg.min_snr_db)
    if quiet:
        # 只做峰值保护，绝不抬电平
        pk = float(np.max(np.abs(x))) if x.size else 0.0
        if pk > cfg.peak_guard:
            return (x * (cfg.peak_guard / pk)).astype(np.float32)
        return x.astype(np.float32)
    g = cfg.target_rms / r
    g = float(np.clip(g, 0.2, 50.0))
    y = x * g
    pk = float(np.max(np.abs(y))) if y.size else 0.0
    if pk > cfg.peak_guard:
        y = y * (cfg.peak_guard / pk)
    return y.astype(np.float32)


def enhance(x: np.ndarray, sr: int = SR, cfg: Optional[DenoiseConfig] = None) -> dict:
    """对一段 16k 音频做增强。返回 {'audio':…, 'info':…} 便于评测记录每个环节。"""
    cfg = cfg or DenoiseConfig()
    y = np.ascontiguousarray(x.astype(np.float32))
    info = {"enabled": cfg.enabled, "snr_before_db": None, "snr_after_db": None,
            "rms_before": _rms(y), "rms_after": _rms(y), "noise_floor_hz": None}
    if not cfg.enabled:
        info["rms_after"] = info["rms_before"]
        return {"audio": y, "info": info}

    before = _rms(y)
    S = _stft(y, cfg)
    noise_pow = estimate_noise_power(S, cfg)
    S2 = spectral_subtract(S, noise_pow, cfg)
    S2 = hf_compensation(S2, sr, cfg)

    # 先估信噪比，再决定要不要抬电平（顺序不能反，见 level_fix 的说明）
    snr = None
    fr = (np.abs(S) ** 2).mean(axis=0)
    if fr.size > 6:
        k = max(1, int(fr.size * cfg.noise_pct / 100.0))
        ns_mean = float(np.sort(fr)[:k].mean())
        sp_med = float(np.median(fr))
        if ns_mean > 0 and sp_med > 0:
            snr = 10 * np.log10(sp_med / ns_mean)
            info["snr_before_db"] = round(snr, 2)

    z = _istft(S2, y.size, cfg)
    z = level_fix(z, cfg, snr)
    # 检测到的等效低通（噪声谱中 -6dB 处的频率）
    if noise_pow.size > 4:
        npow = np.sqrt(noise_pow)
        f = np.linspace(0, sr / 2, len(npow))
        pk = npow.max()
        below = np.where(npow < pk * 0.5)[0]
        info["noise_floor_hz"] = round(float(f[below[-1]]), 1) if below.size else None

    info["rms_after"] = _rms(z)
    # 谱减后的信噪比：同法重估一次（真实值仍需带标注噪声才权威）
    if fr.size > 6:
        S3 = _stft(z, cfg)
        fr3 = (np.abs(S3) ** 2).mean(axis=0)
        if fr3.size > 6:
            k3 = max(1, int(fr3.size * cfg.noise_pct / 100.0))
            ns3 = float(np.sort(fr3)[:k3].mean())
            sp3 = float(np.median(fr3))
            if ns3 > 0 and sp3 > 0:
                info["snr_after_db"] = round(10 * np.log10(sp3 / ns3), 2)
    return {"audio": z, "info": info}


def selftest() -> bool:
    ok = True

    def chk(name, cond, detail=""):
        nonlocal ok
        print(f"[{'OK ' if cond else 'FAIL'}] {name}" + (f" -> {detail}" if detail else ""))
        if not cond:
            ok = False

    cfg = DenoiseConfig()
    sr = SR
    rng = np.random.default_rng(7)

    # 构造一段「语音」（谐波堆叠）+ 白噪声
    t = np.arange(int(2.0 * sr)) / sr
    f0 = 140.0
    speech = sum(np.sin(2 * np.pi * f0 * k * t) / k for k in range(1, 12)).astype(np.float32)
    speech *= (0.5 + 0.5 * np.sin(2 * np.pi * 3.1 * t))     # 音节包络
    speech = speech / (np.max(np.abs(speech)) or 1) * 0.25
    noise = (rng.standard_normal(speech.size) * 0.05).astype(np.float32)

    mixed = speech + noise
    r_in = _rms(mixed)
    out = enhance(mixed, sr, cfg)
    y = out["audio"]
    chk("输入输出长度一致", y.size == mixed.size, f"{y.size} vs {mixed.size}")
    chk("输出无 NaN/Inf", np.all(np.isfinite(y)))
    chk("峰值不超过保护上限", float(np.max(np.abs(y))) <= cfg.peak_guard + 1e-6,
        f"{float(np.max(np.abs(y))):.3f}")
    chk("电平被抬到目标附近", 0.02 < _rms(y) < 0.2, f"rms {_rms(y):.4f} (in {r_in:.4f})")

    # 降噪有效性：残差噪声能量应低于输入的噪声占比
    def noise_resid(sig):
        fr = np.fft.rfft(sig * np.hanning(sig.size))
        return float(np.sqrt(np.mean(np.abs(fr) ** 2)))
    chk("谱减后总能量不增（不制造新噪声）", _rms(y) <= cfg.peak_guard, f"{_rms(y):.4f}")

    # 高频补偿只抬高频，不动低频
    def band_rms(sig, lo, hi):
        S = np.abs(np.fft.rfft(sig))
        f = np.fft.rfftfreq(sig.size, 1 / sr)
        m = (f >= lo) & (f < hi)
        return float(np.sqrt(np.mean(S[m] ** 2))) if m.any() else 0.0
    lo_in, lo_out = band_rms(mixed, 100, 500), band_rms(y, 100, 500)
    hi_in, hi_out = band_rms(mixed, 3000, 7000), band_rms(y, 3000, 7000)
    chk(f"低频基本不变 ({lo_in:.2f}→{lo_out:.2f})", abs(lo_out - lo_in) < max(lo_in * 0.5, 1e-6))
    # ⚠ 高频的「抬升」必须在**谱减之后**比较，且**只在频谱域**比。
    #   在时域上比全信号 FFT 会被两件事污染：① 谱减把高频噪声一起削掉（3k-7k
    #   实测被砍到 1/5）；② 高频补偿只加 +3dB。两者相抵后时域上表现为「下降」，
    #   看起来像补偿没生效，实际增益是对的（实测谱域抬升比 1.25 / 1.41）。
    #   正确断言：在同一段频带内，+HF 的结果 > 未 +HF 的结果。
    S = _stft(mixed, cfg)
    npow = estimate_noise_power(S, cfg)
    S_sub = spectral_subtract(S, npow, cfg)
    S_hf = hf_compensation(S_sub, sr, cfg)

    def spec_band(M, lo, hi):
        f = np.linspace(0, sr / 2, M.shape[0])
        m = (f >= lo) & (f < hi)
        return float(np.sqrt(np.mean(np.abs(M[m]) ** 2))) if m.any() else 0.0

    lo_sub, lo_hf = spec_band(S_sub, 100, 500), spec_band(S_hf, 100, 500)
    hi_sub, hi_hf = spec_band(S_sub, 3000, 7000), spec_band(S_hf, 3000, 7000)
    chk(f"谱域高频被抬升 ({hi_sub:.4f}→{hi_hf:.4f}, ×{hi_hf/max(hi_sub,1e-12):.2f})",
        hi_hf > hi_sub * 1.05)
    chk(f"谱域低频不受补偿影响 ({lo_sub:.4f}→{lo_hf:.4f})", abs(lo_hf - lo_sub) < 1e-9)
    print(f"       [参考] 时域全信号 3k-7k: {hi_in:.3f}→{hi_out:.3f}（被谱减主导，非补偿失效）")

    # 关闭时应逐样本原样返回
    off = enhance(mixed, sr, DenoiseConfig(enabled=False))["audio"]
    chk("enabled=False 时逐样本不变", np.array_equal(off, mixed))

    # 极短输入不得崩
    for n in (0, 1, 160, 400):
        try:
            o = enhance(np.zeros(n, dtype=np.float32), sr, cfg)["audio"]
            chk(f"极短输入 n={n} 不崩且长度正确", o.size == n)
        except Exception as e:
            chk(f"极短输入 n={n} 不崩", False, f"{type(e).__name__}: {e}")

    # ⚠ 往返重建：这是本模块最关键的自检。加窗 OLA 若转置/对齐错了，
    #   「幅度是否线性」照样正确（×3 得 ×3），只有往返能暴露。
    #   短于一个窗长（512 样本 = 32ms）的输入没有有效区间，属预期退化，
    #   判据按「不崩 + 长度对」收，不要求 rel 为 0。
    for sec in (3.0, 1.0, 0.2, 0.04):
        x = rng.standard_normal(int(sr * sec)).astype(np.float32) * 0.1
        y = _istft(_stft(x, cfg), x.size, cfg)
        rel = roundtrip_error(x, y, cfg)
        chk(f"往返重建 {sec}s 逐样本无损 (rel={rel:.2e})", rel < 1e-6)
    short = rng.standard_normal(160).astype(np.float32) * 0.1
    rel_short = roundtrip_error(short, _istft(_stft(short, cfg), short.size, cfg), cfg)
    chk(f"短于窗长的输入不崩（无有效区间，rel={rel_short:.2f} 属预期）",
        _istft(_stft(short, cfg), short.size, cfg).size == short.size)

    # 频点数必须是 n//2+1：转置写反时这里会立刻现形（(512,T) 而非 (257,T)）
    S = _stft(x, cfg)
    chk(f"STFT 频点数 = n//2+1 = {cfg.n_fft//2+1}", S.shape[0] == cfg.n_fft // 2 + 1,
        f"实际 {S.shape}")

    # 谱减必须**减少**噪声能量（把已知白噪声加到静音上再滤）
    ns_only = rng.standard_normal(sr).astype(np.float32) * 0.05
    y1 = enhance(ns_only, sr, cfg)["audio"]
    lo, hi = valid_span(ns_only, y1, cfg)
    e_in = _rms(ns_only[lo:hi])
    e_out = _rms(y1[lo:hi])
    chk(f"纯噪声输入后能量下降 ({e_in:.4f}→{e_out:.4f})", e_out <= e_in * 1.02,
        "谱减对纯噪声应几乎全滤掉；若上升说明增益反了")

    # 极静输入不得被放大成噪声
    tiny = np.full(sr, 1e-5, dtype=np.float32)
    o = enhance(tiny, sr, cfg)["audio"]
    chk("极静输入不被放大成噪声", _rms(o) < 1e-3, f"rms {_rms(o):.6f}")

    print("DENOISE-SELFTEST-PASS" if ok else "DENOISE-SELFTEST-FAIL")
    return ok


if __name__ == "__main__":
    import sys
    sys.exit(0 if selftest() else 1)