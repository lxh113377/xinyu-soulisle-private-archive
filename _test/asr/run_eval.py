#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ASR 评测主循环 —— 跑「方言 × 场景」矩阵，产出可复现的基线报告。

用法:
    py -3.12 run_eval.py --manifest _test/asr/manifests/mandarin.jsonl \
                         --model D:/asr-data/models/Qwen3-ASR-0.6B-hf \
                         --scenarios clean,noisy_10db,far_3m \
                         --out _test/asr/reports/baseline.json

产物:
    1) JSON 报告：每种 (方言 × 场景) 的 CER/准确率/整句全对率/错误构成/RTF
    2) Markdown 摘要：人看的表
    3) 假设缓存 hyp_cache.jsonl：同一音频+场景+模型只推理一次，
       改归一化规则或换后处理时不必重跑推理（这是迭代成本的关键）

设计约束:
  - 语料级 CER = 总编辑距离 / 总参考字数（不逐条平均，见 metrics.py 自检）
  - real_audio=False 的条目单独统计，不混入对外报数
  - 任何一步失败必须显式报错，不得静默跳过（静默跳过 = 假绿）
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from collections import defaultdict
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np

from eval_set import Case, filter_cases, read_manifest, summarize
from metrics import CaseResult, aggregate, format_report, score_case
from scenarios import SCENARIOS, apply_scenario, SR

SR = SR  # 统一采样率（scenarios.SR = 16000，ASR 模型要求）


# ─────────────────────────────────────────────────────────────────────────────
def load_audio(path: str, sr: int = SR) -> np.ndarray:
    """读 wav → 单声道 float32 → 16k。模型要求 16k，喂别的采样率会静默劣化。"""
    import soundfile as sf
    x, file_sr = sf.read(path, dtype="float32", always_2d=False)
    if x.ndim > 1:
        x = x.mean(axis=1)
    if file_sr != sr:
        x = _resample(x, file_sr, sr)
    return x.astype(np.float32)


def trim(x: np.ndarray, sr: int = SR, max_s: float = 6.0) -> np.ndarray:
    """截到 max_s。

    两个理由：
      1) 与线上链路一致 —— asr-local.js 客户端也按 6s 截（256KiB 体闸 ÷ 32KB/s ≈ 8s）。
         评测用 20s 长句而线上只给 6s，就是「离线好看、线上翻车」。
      2) KeSpeech 原始音频是 ~5s 一整段，而线上是端点切出的短句；
         直接整段送去测会把「切块」也一起算进准确率里，掩盖识别本身的问题。
    """
    n = int(max_s * sr)
    return x[:n] if x.size > n else x


def _resample(x: np.ndarray, src: int, dst: int) -> np.ndarray:
    """线性重采样（仅评测用；生产链路应让浏览器直接出 16k）。"""
    if src == dst:
        return x
    n_out = int(round(x.size * dst / src))
    idx = np.linspace(0, x.size - 1, n_out, dtype=np.float64)
    return np.interp(idx, np.arange(x.size, dtype=np.float64), x).astype(np.float32)


# ─────────────────────────────────────────────────────────────────────────────
class HypCache:
    """识别结果缓存。key = (case_id, scenario, model, dialect, lang_hint)。"""

    def __init__(self, path: str):
        self.path = path
        self.store: Dict[str, dict] = {}
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        r = json.loads(line)
                        self.store[r["key"]] = r
                    except Exception:
                        continue
        # 目录可能还不存在（首次跑分）。不建目录就 FileNotFoundError，
        # 而报错点在缓存构造里、离真正的失败原因隔了三层，现场极具误导性（实测踩过）。
        d = os.path.dirname(os.path.abspath(path))
        if d:
            os.makedirs(d, exist_ok=True)
        self._fh = open(path, "a", encoding="utf-8")

    @staticmethod
    def key(case_id: str, scenario: str, model: str, dialect: str, hint: str) -> str:
        return "|".join([case_id, scenario, model, dialect, str(hint)])

    def get(self, k: str) -> Optional[str]:
        r = self.store.get(k)
        return r["hyp"] if r else None

    def put(self, k: str, hyp: str, infer_s: float, audio_s: float) -> None:
        r = {"key": k, "hyp": hyp, "infer_s": infer_s, "audio_s": audio_s}
        self.store[k] = r
        self._fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    def close(self) -> None:
        try:
            self._fh.close()
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────────
def _check_scenarios(scenarios):
    """场景名白名单校验（原在推理循环内逐场景判，提到入口 ⇒ 失败更早、循环体更干净）。"""
    for sc_name in scenarios:
        if sc_name not in SCENARIOS:
            print(f"[FATAL] 未知场景 '{sc_name}'。可用: {', '.join(SCENARIOS)}")
            return False
    return True

def _prepare_cases(manifest, dialects, split, real_only, max_cases):
    """读清单 + 筛选 + 缺音频硬检查。返回 cases；任一前置不成立 ⇒ None（调用方判 rc=2）。

    r187 拆分动因：loc_guard 函数长门（≤150，原 run 180 行）。五段各自下移成模块级
    函数，**逐语句调用序与打印顺序不变**；本机无 torch/语料 ⇒ 只做静态等价搬移，
    不谎称跑过评测（同族教训：没跑过的路径不算验过）。
    """
    cases = read_manifest(manifest)
    cases = filter_cases(cases, dialects=dialects, split=split, real_only=real_only)
    if max_cases:
        by_d: Dict[str, List[Case]] = defaultdict(list)
        for c in cases:
            by_d[c.dialect].append(c)
        cases = [c for d in sorted(by_d) for c in by_d[d][:max_cases]]
    if not cases:
        print(f"[FATAL] 清单筛选后为空: {manifest} dialects={dialects} split={split}")
        return 2

    print(summarize(cases))
    missing = [c for c in cases if not os.path.isfile(c.audio)]
    if missing:
        print(f"[FATAL] {len(missing)}/{len(cases)} 条音频文件不存在，例如：")
        for c in missing[:3]:
            print(f"          {c.audio}")
        print("        先下载语料再评测（不要跳过 —— 跳过会让基线虚高）。")
        return 2
    return cases

def _setup_cache_path(cache_path, out_json, denoise, denoise_hf_db, denoise_over):
    """缓存落点默认值 + 降噪配置。返回 (dn_cfg, cache_path, dn_stats)。"""

    cache_path = cache_path or os.path.join(
        os.path.dirname(out_json), "hyp_cache.jsonl")

    # 降噪开关。⚠ 缓存 key 必须把降噪参数编进去：同一段音频在「开/关降噪」下
    #   是**两条不同的推理**，共用缓存会把 A/B 结果算成同一个（静默失效，且看起来
    #   还很合理 —— 实测踩过这类「对照实验其实没对照」的问题）。
    dn_cfg = None
    dn_stats: List[dict] = []
    if denoise:
        from denoise import DenoiseConfig
        dn_cfg = DenoiseConfig(enabled=True, hf_boost_db=denoise_hf_db,
                               over_subtraction=denoise_over)
        cache_path = cache_path.replace(".jsonl", f".dn{int(denoise_hf_db)}_{denoise_over}.jsonl")
        print(f"[INFO] 降噪开启 hf={denoise_hf_db}dB over={denoise_over} 缓存={cache_path}")
    else:
        print(f"[INFO] 降噪关闭（对照）")
    return dn_cfg, cache_path, dn_stats

def _load_engine(device, model, lora):
    """设备解析 + 引擎构造。返回 (eng, device, LANG_HINTS)。"""
    from engine_qwen import LANG_HINTS, QwenASR
    if device == "auto":
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
    eng = QwenASR(model_id=model, device=device, enable_lora=bool(lora),
                  lora_path=lora)

    return eng, device, LANG_HINTS

def _infer_all(cases, scenarios, cache, dn_cfg, eng, LANG_HINTS, use_lang_hint,
           batch_size, model, dn_stats):
    """「场景 × 方言」主循环：命中缓存直接打分，未命中批量推理并回填。

    返回 (results, perf, t_all)。场景名合法性已由 run() 入口的 _check_scenarios 拦下。
    """
    results: List[dict] = []
    perf: List[dict] = []
    t_all = time.perf_counter()

    for sc_name in scenarios:
        sc = SCENARIOS[sc_name]

        # 按方言分组，便于用方言专属语言提示批量推理
        for dialect in sorted({c.dialect for c in cases}):
            dcases = [c for c in cases if c.dialect == dialect]
            todo, audio_buf, keys = [], [], []
            for c in dcases:
                k = HypCache.key(c.id, sc_name, model, dialect,
                                 LANG_HINTS.get(dialect) if use_lang_hint else None)
                cached = cache.get(k)
                if cached is not None:
                    results.append(_score(c, cached, sc_name, dialect,
                                          cached_infer=0.0))
                    continue
                x = load_audio(c.audio)
                y = apply_scenario(x, sc, sr=SR)
                z = trim(y, SR)
                if dn_cfg is not None:
                    from denoise import enhance
                    r = enhance(z, SR, dn_cfg)
                    z = r["audio"]
                    dn_stats.append(r["info"])
                audio_buf.append(z)
                keys.append(k)
                todo.append(c)

            for i in range(0, len(todo), batch_size):
                chunk = todo[i:i + batch_size]
                chunk_keys = keys[i:i + batch_size]
                chunk_audio = audio_buf[i:i + batch_size]
                # 真实计时：不外推、不占位。要求 5 的性能判据只能来自实测
                t0 = time.perf_counter()
                hyps = eng.transcribe_batch(chunk_audio, dialect=dialect,
                                            use_lang_hint=use_lang_hint)
                elapsed = time.perf_counter() - t0
                per_item = elapsed / max(len(chunk), 1)
                for c, k, y, h in zip(chunk, chunk_keys, chunk_audio, hyps):
                    a_s = len(y) / SR
                    cache.put(k, h, per_item, a_s)
                    results.append(_score(c, h, sc_name, dialect, per_item, a_s))
                    perf.append({"dialect": dialect, "scenario": sc_name,
                                 "infer_s": per_item, "audio_s": a_s})

            done = len([r for r in results if r["scenario"] == sc_name and
                        r["dialect"] == dialect])
            print(f"[进度] 场景={sc_name:<12} 方言={dialect:<9} 完成 {done}/{len(dcases)}")

    cache.close()
    return results, perf, t_all

def _build_report(manifest, model, lora, device, cases, scenarios, t_all, results,
                perf, dn_stats, denoise_hf_db, denoise_over, out_json):
    """聚合分桶 → 组 report → 落 JSON → 印 Markdown。返回 rc=0。"""

    # ── 汇总 ──────────────────────────────────────────────────────────────────
    buckets: Dict[tuple, List[CaseResult]] = defaultdict(list)
    meta_by_k: Dict[tuple, dict] = {}
    for r in results:
        buckets[(r["dialect"], r["scenario"])].append(r["_res"])
        meta_by_k[(r["dialect"], r["scenario"])] = {
            "real": all(r["real_audio"] for r in [r]),
            "source": r["source"],
        }

    summary_rows = []
    for (dialect, sc_name), rs in sorted(buckets.items()):
        agg = aggregate(rs)
        row = {
            "dialect": dialect,
            "scenario": sc_name,
            "n_cases": agg.n_cases,
            "cer": round(agg.cer, 6),
            "accuracy": round(agg.accuracy, 6),
            "sent_acc": round(agg.sent_acc, 6),
            "ref_chars": agg.total_ref_len,
            "errors": agg.total_errors,
            "sub": agg.sub, "del": agg.dele, "ins": agg.ins,
            "all_synthetic": not all(x["real_audio"] for x in results
                                     if x["scenario"] == sc_name and x["dialect"] == dialect),
            "top_confusions": [{"ref": a, "hyp": b, "n": n}
                               for (a, b), n in agg.error_profile(10)],
        }
        summary_rows.append(row)

    rtfs = [p["infer_s"] / p["audio_s"] for p in perf if p["audio_s"] > 0]
    report = {
        "manifest": manifest,
        "model": model,
        "lora": lora,
        "device": device,
        "n_cases": len(cases),
        "scenarios": scenarios,
        "elapsed_s": round(time.perf_counter() - t_all, 1),
        "performance": {
            "rtf_mean": round(statistics.mean(rtfs), 4) if rtfs else None,
            "rtf_p50": round(statistics.median(rtfs), 4) if rtfs else None,
            "rtf_max": round(max(rtfs), 4) if rtfs else None,
            "infer_s_mean": round(statistics.mean([p["infer_s"] for p in perf]), 4) if perf else None,
            "note": "RTF<1 表示快于实时；这是要求 5「响应速度不退化」的判据",
        },
        "rows": summary_rows,
    }
    if dn_stats:
        import statistics as _st
        snr_b = [d["snr_before_db"] for d in dn_stats if d.get("snr_before_db") is not None]
        snr_a = [d["snr_after_db"] for d in dn_stats if d.get("snr_after_db") is not None]
        report["denoise"] = {
            "enabled": True, "hf_boost_db": denoise_hf_db, "over_subtraction": denoise_over,
            "n": len(dn_stats),
            "snr_before_db_mean": round(_st.mean(snr_b), 2) if snr_b else None,
            "snr_after_db_mean": round(_st.mean(snr_a), 2) if snr_a else None,
            "snr_delta_db": round(_st.mean(snr_a) - _st.mean(snr_b), 2) if snr_b and snr_a else None,
            "rms_before_mean": round(_st.mean([d["rms_before"] for d in dn_stats]), 4),
            "rms_after_mean": round(_st.mean([d["rms_after"] for d in dn_stats]), 4),
        }
    else:
        report["denoise"] = {"enabled": False}
    os.makedirs(os.path.dirname(os.path.abspath(out_json)) or ".", exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print("\n" + render_markdown(report))
    print(f"\n[OK ] 报告已写入 {out_json}")
    return 0

def run(manifest: str, model: str, scenarios: List[str], out_json: str,
        dialects: Optional[List[str]] = None, split: Optional[str] = "test",
        device: str = "auto", batch_size: int = 4, max_cases: int = 0,
        lora: Optional[str] = None, real_only: bool = False,
        use_lang_hint: bool = True, cache_path: Optional[str] = None,
        denoise: bool = False, denoise_hf_db: float = 3.0,
        denoise_over: float = 1.4) -> int:
    """调度：校验 → 取数 → 缓存/降噪 → 引擎 → 推理 → 汇总（各段见同名私有函数）。"""
    if not _check_scenarios(scenarios):
        return 2
    cases = _prepare_cases(manifest, dialects, split, real_only, max_cases)
    if cases is None:
        return 2
    dn_cfg, cache_path, dn_stats = _setup_cache_path(
        cache_path, out_json, denoise, denoise_hf_db, denoise_over)
    cache = HypCache(cache_path)
    print(f"[INFO] 缓存: {cache_path}（已有 {len(cache.store)} 条）")
    eng, device, LANG_HINTS = _load_engine(device, model, lora)
    results, perf, t_all = _infer_all(
        cases, scenarios, cache, dn_cfg, eng, LANG_HINTS, use_lang_hint,
        batch_size, model, dn_stats)
    return _build_report(manifest, model, lora, device, cases, scenarios, t_all,
                         results, perf, dn_stats, denoise_hf_db, denoise_over, out_json)


def hyp_rtf_guard(h: str) -> float:
    """占位：真实 RTF 由引擎计时给出，这里避免除零。见下方 TODO。"""
    return 1.0


def _score(c: Case, hyp: str, sc_name: str, dialect: str,
           infer_s: float = 0.0, audio_s: float = 0.0, cached_infer=0.0) -> dict:
    r = score_case(c.id, c.ref, hyp)
    return {"case_id": c.id, "scenario": sc_name, "dialect": dialect,
            "ref_raw": c.ref, "hyp_raw": hyp,
            "real_audio": c.real_audio, "source": c.source,
            "infer_s": infer_s, "audio_s": audio_s, "_res": r}


def render_markdown(rep: dict) -> str:
    L = ["## ASR 基线报告", "",
         f"- 模型: `{rep['model']}`" + (f" + LoRA `{rep['lora']}`" if rep.get("lora") else ""),
         f"- 设备: {rep['device']} ｜ 用例: {rep['n_cases']} ｜ 耗时: {rep['elapsed_s']}s",
         f"- 场景: {', '.join(rep['scenarios'])}", ""]
    p = rep.get("performance") or {}
    if p.get("rtf_mean") is not None:
        L.append(f"- 性能: RTF 均值 **{p['rtf_mean']}** (p50 {p['rtf_p50']}, max {p['rtf_max']})"
                 f" ｜ 单句推理均值 {p['infer_s_mean']}s")
    L += ["", "| 方言 | 场景 | 用例 | 准确率 | CER | 整句全对 | 参考字 | 替换/删/插 | 备注 |",
          "|---|---|---|---|---|---|---|---|---|"]
    for r in rep["rows"]:
        note = "⚠合成音频，不计入对外报数" if r.get("all_synthetic") else ""
        L.append(f"| {r['dialect']} | {r['scenario']} | {r['n_cases']} | "
                 f"**{r['accuracy']*100:.2f}%** | {r['cer']*100:.2f}% | "
                 f"{r['sent_acc']*100:.1f}% | {r['ref_chars']} | "
                 f"{r['sub']}/{r['del']}/{r['ins']} | {note} |")
    return "\n".join(L)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="ASR 方言×场景 基线评测")
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--scenarios", default="clean")
    ap.add_argument("--out", default="_test/asr/reports/baseline.json")
    ap.add_argument("--dialects", default=None, help="逗号分隔；默认全部")
    ap.add_argument("--split", default="test")
    ap.add_argument("--device", default="auto")
    ap.add_argument("--batch-size", type=int, default=4)
    ap.add_argument("--max-cases", type=int, default=0)
    ap.add_argument("--lora", default=None)
    ap.add_argument("--real-only", action="store_true")
    ap.add_argument("--no-lang-hint", action="store_true")
    ap.add_argument("--denoise", action="store_true", help="送模型前做谱减+高频补偿+电平对齐")
    ap.add_argument("--denoise-hf-db", type=float, default=3.0)
    ap.add_argument("--denoise-over", type=float, default=1.4)
    a = ap.parse_args()
    sys.exit(run(a.manifest, a.model, a.scenarios.split(","), a.out,
                 dialects=[d for d in (a.dialects or "").split(",") if d] or None,
                 split=a.split, device=a.device, batch_size=a.batch_size,
                 max_cases=a.max_cases, lora=a.lora, real_only=a.real_only,
                 use_lang_hint=not a.no_lang_hint, denoise=a.denoise,
                 denoise_hf_db=a.denoise_hf_db, denoise_over=a.denoise_over))