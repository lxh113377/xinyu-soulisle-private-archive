#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Qwen3-ASR-0.6B 的 LoRA 微调。

设计依据（都是实测，不是照搬通用配方）：
  · 目标模块选 **LLM 侧**而非音频编码器。基线错误画像显示主要矛盾是
    **近音字/正字混淆**（无↔冇、亚→阿、她→他），那是解码器的**语言侧**问题；
    音频侧的信噪比/远场问题由训练数据增强覆盖，不该动编码器（动它更容易崩）。
  · 冻结音频塔：显存吃紧（实测 12GB 卡），且音频塔对中文方言适配收益低。
  · 学习率 1e-4 / rank 16 / epoch 1：起步档，先看**验证集 CER 是否真的下降**，
    不靠猜。

🔴 三条不可退让的约束：
  1. **验证集与留出集物理隔离**（build_lora_split.py 已断言），训完必须先报 val CER；
     若 val 没降，直接判失败，不许拿 holdout 数字来圆场。
  2. **只保存 LoRA adapter**，不保存完整权重 —— 体积小、可回滚、可审查。
  3. **每步都验显存**，OOM 就减 batch 而不是换机器。

用法:
    D:\\asr-train\\.venv\\Scripts\\python.exe train_lora.py \
        --data D:/asr-data/lora_data --out D:/asr-data/lora/kespeech-lora \
        --epochs 1 --rank 16
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
import time
from dataclasses import dataclass
from typing import List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

MODEL_DEFAULT = "D:/asr-data/models/Qwen3-ASR-0.6B-hf"
SR = 16000


@dataclass
class Row:
    id: str
    audio: str
    text: str
    dialect: str


def load_split(path: str, cap: Optional[int] = None) -> List[Row]:
    rows = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        rows.append(Row(d["id"], d["audio"], d["text"], d.get("dialect", "mandarin")))
        if cap and len(rows) >= cap:
            break
    return rows


def read_wav(path: str):
    import soundfile as sf
    x, sr = sf.read(path, dtype="float32", always_2d=False)
    if x.ndim > 1:
        x = x.mean(axis=1)
    if sr != SR:
        import scipy.signal as ss
        x = ss.resample(x, int(len(x) * SR / sr)).astype("float32")
    return np.ascontiguousarray(x)


import numpy as np  # noqa: E402


def build_batch(rows: List[Row], dialect: str, dialect_map: Optional[dict] = None):
    """把一批行变成 processor 输入。"""
    from transformers import AutoProcessor
    auds = [read_wav(r.audio) for r in rows]
    texts = [r.text for r in rows]
    return auds, texts


class Collator:
    """按方言分组的 batch 构造。

    🔴 方言不能混在一个 batch 里：Qwen3-ASR 的 `language` 是**整批一个值**
       （`prepare_language_inputs` 返回 `[lang]*batch_size`），混批等于给
       全批套同一个语种提示，标签就错了。故按 dialect 分桶再组 batch。
    """

    def __init__(self, processor, max_sec: float = 6.0):
        self.p = processor
        self.max_n = int(max_sec * SR)

    def __call__(self, rows: List[Row]):
        auds = []
        for r in rows:
            x = read_wav(r.audio)
            if x.size > self.max_n:
                x = x[: self.max_n]
            auds.append(x)
        # 不强制 language：方言名不被 API 接受（实测 ValueError），
        # 走自动识别，让 LoRA 自己去学方言对应的字。
        inputs = self.p.apply_transcription_request(auds)
        texts = [r.text for r in rows]
        labels = self.p.tokenizer(
            texts, add_special_tokens=False, return_tensors="pt",
            padding=True, truncation=True, max_length=256)
        return inputs, labels


def build_lora(model, rank: int, alpha: int, dropout: float):
    from peft import LoraConfig, get_peft_model
    # 只挂 LLM 解码器的注意力 + MLP 投影；音频塔冻结。
    targets = ["q_proj", "k_proj", "v_proj", "o_proj",
               "gate_proj", "up_proj", "down_proj"]
    # 排除音频编码器里的同名模块（它们不是 nn.Linear 命名空间，用前缀过滤）
    found, skipped = [], []
    for name, mod in model.named_modules():
        if not name.endswith(tuple(targets)):
            continue
        if "audio" in name.lower() or "encoder" in name.lower():
            skipped.append(name)
            continue
        found.append(name)
    if not found:
        raise RuntimeError("没找到任何可挂 LoRA 的模块；模块名可能变了，先打印 named_modules")
    cfg = LoraConfig(r=rank, lora_alpha=alpha, lora_dropout=dropout,
                     bias="none", task_type="CAUSAL_LM",
                     target_modules=sorted(set(found)))
    pm = get_peft_model(model, cfg)
    n_all = sum(p.numel() for p in pm.parameters())
    n_tr = sum(p.numel() for p in pm.parameters() if p.requires_grad)
    print(f"[LoRA] 命中模块 {len(set(found))} 个（跳过音频侧 {len(skipped)} 个）")
    print(f"[LoRA] 总参数 {n_all/1e6:.1f}M ｜ 可训 {n_tr/1e6:.2f}M "
          f"({n_tr/n_all*100:.2f}%)")
    return pm, cfg, found


def _parse_args(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="D:/asr-data/lora_data")
    ap.add_argument("--model", default=MODEL_DEFAULT)
    ap.add_argument("--out", default="D:/asr-data/lora/kespeech-lora")
    ap.add_argument("--epochs", type=float, default=1.0)
    ap.add_argument("--rank", type=int, default=16)
    ap.add_argument("--alpha", type=int, default=32)
    ap.add_argument("--dropout", type=float, default=0.05)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--batch-size", type=int, default=2)
    ap.add_argument("--grad-accum", type=int, default=8)
    ap.add_argument("--max-train", type=int, default=0)
    ap.add_argument("--max-val", type=int, default=48)
    ap.add_argument("--max-sec", type=float, default=6.0)
    ap.add_argument("--oversample-min", type=int, default=400,
                    help="低资源方言的最小样本数（过采样下限）；0=按自然分布")
    ap.add_argument("--val-per-dialect", type=int, default=12)
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--log-every", type=int, default=20)
    return ap.parse_args(argv)


def _load_rows(a):
    """读三份划分 + 验证集分层 + 留出集隔离硬断言。

    返回 (train_rows, val_rows, ho_ids)；任一前置不成立 ⇒ None（调用方判 rc=2）。

    r187 拆分动因：loc_guard 的函数长门（≤150）。原 main 232 行，把「取数与隔离」
    「组 batch 顺序」「训练循环」「收尾与验证」四段各自下移成模块级函数，
    **逐语句调用序不变**。本机无 GPU/torch ⇒ 只做静态等价搬移，不谎称跑过训练。
    """
    tr_path = os.path.join(a.data, "train.jsonl")
    va_path = os.path.join(a.data, "val.jsonl")
    ho_path = os.path.join(a.data, "holdout.jsonl")
    if not os.path.isfile(tr_path):
        print(f"[FATAL] 训练集不存在: {tr_path}（先跑 build_lora_split.py）")
        return None
    train_rows = load_split(tr_path, a.max_train or None)
    val_rows = load_split(va_path, a.max_val or None)

    # 🔴 **分层采样**：验证集/限流必须按方言分层，否则会被数量多的方言淹没。
    #   实测 train 分布是 mandarin 4103 / zongyuan 3865 / chuan 1048 / **dongbei 132**
    #   —— dongbei 只占 1.4%，而它恰恰是**离 92% 目标最近的方言**（基线 91.41%）。
    #   随机抽样会让 dongbei 的验证样本少到没法判断（实测曾出现 val 里 dongbei=3 条）。
    from collections import Counter as _C

    def stratified(rows: List[Row], per: int) -> List[Row]:
        by: dict = {}
        for r in rows:
            by.setdefault(r.dialect, []).append(r)
        out: List[Row] = []
        for d in sorted(by):
            random.Random(a.seed).shuffle(by[d])
            out.extend(by[d][:per])
        return out
    if a.max_val and a.max_val > 0:
        val_rows = stratified(val_rows, a.max_val)
    print("[验证集] " + ", ".join(f"{k}={v}" for k, v in
                                  sorted(_C(r.dialect for r in val_rows).items())))

    # 🔴 隔离硬断言（训练脚本自己也要查一遍，不能只信上游）
    ho_ids = set()
    if os.path.isfile(ho_path):
        ho_ids = {json.loads(l)["id"] for l in open(ho_path, encoding="utf-8") if l.strip()}
    leak = ho_ids & ({r.id for r in train_rows} | {r.id for r in val_rows})
    if leak:
        print(f"[FATAL] 留出集泄漏到训练/验证：{len(leak)} 条（如 {list(leak)[:3]}）")
        return None
    print(f"[隔离] train={len(train_rows)} val={len(val_rows)} holdout={len(ho_ids)} 且零交集 ✅")

    from collections import Counter
    print("[分布] train " + ", ".join(f"{k}={v}" for k, v in
                                       sorted(Counter(r.dialect for r in train_rows).items())))
    return train_rows, val_rows, ho_ids


def _build_order(train_rows, a):
    """按方言分桶 → 低资源过采样 → 轮转打平成 step 序列（原 main 内联段）。"""
    by_d: dict = {}
    for r in train_rows:
        by_d.setdefault(r.dialect, []).append(r)
    for v in by_d.values():
        random.shuffle(v)

    # 🔴 **训练也要分层过采样**，不能按自然分布训。
    #   dongbei 只有 132 条（占 1.4%），按自然分布走它一个 epoch 见不到几遍，
    #   LoRA 学不到；而它离目标最近、收益最大。故给低资源方言设最少重复数。
    if a.oversample_min:
        print("[过采样] " + ", ".join(
            f"{d}={len(v)}→{max(len(v), a.oversample_min)}" for d, v in sorted(by_d.items())))
        for d, v in list(by_d.items()):
            if len(v) < a.oversample_min:
                v.extend(random.Random(a.seed).sample(v, min(len(v), a.oversample_min - len(v))))
                by_d[d] = v
    order: List[Row] = []
    while any(by_d.values()):
        for d in sorted(by_d):
            if by_d[d]:
                order.append(by_d[d].pop())
    return order


def _train_micro(chunk, collate, proc, model, opt, a, torch):
    """一个 micro-batch 的前向 + 反传。返回 loss 值；OOM ⇒ 清缓存并返回 None。

    ⚠ 音频特征必须转成与基座一致的 dtype。processor 出来的是 **float32**，
      而基座是 **bfloat16**；直接喂会在音频塔的 conv2d 上炸
      「Input type (float) and bias type (struct c10::BFloat16)」。
      生成路径（generate）内部会自己转，所以只有训练这条 forward 暴露出来。
    """
    try:
        inp, lab = collate(chunk)
        inp = inp.to("cuda")
        # 标签右移 + 只对音频对齐后的文本位算 loss
        full = inp["input_ids"]
        prompt_len = full.shape[1]
        tgt = lab["input_ids"].to("cuda")
        pad_id = proc.tokenizer.pad_token_id
        cat = torch.cat([full, tgt], dim=1)
        labels = torch.full_like(cat, -100)
        labels[:, prompt_len:] = tgt.clone()
        labels[cat == pad_id] = -100
        attn = inp.get("attention_mask")
        if attn is not None:
            am = torch.cat([attn, lab["attention_mask"].to("cuda")], dim=1)
        else:
            am = None
        feats = inp.get("input_features")
        fmask = inp.get("input_features_mask")
        if feats is not None:
            feats = feats.to("cuda", dtype=torch.bfloat16)
        if fmask is not None:
            fmask = fmask.to("cuda")
        out = model(input_ids=cat, attention_mask=am,
                    input_features=feats,
                    input_features_mask=fmask,
                    labels=labels)
        loss = out.loss
        (loss / a.grad_accum).backward()
        return float(loss)
    except torch.cuda.OutOfMemoryError:
        opt.zero_grad(set_to_none=True)
        torch.cuda.empty_cache()
        print(f"[OOM] 跳过并清缓存（batch={a.batch_size} 可减半重试）")
        return None


def _train_loop(model, proc, opt, sched, collate, order, log, a, torch, total_steps):
    """梯度累积训练循环（原 main 内联段）。返回起始时间戳供收尾报用时。"""
    t0 = time.perf_counter()
    step = 0
    acc_loss, acc_n = 0.0, 0
    opt.zero_grad(set_to_none=True)
    i = 0
    micro = 0
    while step < total_steps:
        chunk = order[i: i + a.batch_size]
        i += a.batch_size
        if not chunk:
            break
        loss = _train_micro(chunk, collate, proc, model, opt, a, torch)
        if loss is None:
            continue
        acc_loss += loss
        acc_n += 1
        micro += 1
        if micro % a.grad_accum == 0:
            torch.nn.utils.clip_grad_norm_(
                [p for p in model.parameters() if p.requires_grad], 1.0)
            opt.step(); sched.step(); opt.zero_grad(set_to_none=True)
            step += 1
            if step % a.log_every == 0 or step == 1:
                mem = torch.cuda.max_memory_allocated() / 1024 ** 3
                msg = (f"[{step}/{total_steps}] loss={acc_loss/max(acc_n,1):.4f} "
                       f"lr={sched.get_last_lr()[0]:.2e} 显存峰值={mem:.1f}GB "
                       f"用时={time.perf_counter()-t0:.0f}s")
                print(msg, flush=True)
                log["steps"].append(step)
                log["loss"].append(acc_loss / max(acc_n, 1))
            acc_loss, acc_n = 0.0, 0
    return t0


def val_cer(model, val_rows, collate, a, proc, torch) -> Optional[dict]:
    """按方言分别算 CER。**必须分方言报**：合并成一个数会掩盖
    dongbei 涨、zongyuan 跌这种反向抵消（这正是热词实验上栽过的坑）。"""
    from metrics import aggregate, score_case
    model.eval()
    per: dict = {}
    with torch.inference_mode():
        for d in sorted({r.dialect for r in val_rows}):
            sub = [r for r in val_rows if r.dialect == d][: a.val_per_dialect]
            rs = []
            for i in range(0, len(sub), a.batch_size):
                ch = sub[i:i + a.batch_size]
                inp, lab = collate(ch)
                inp = inp.to("cuda")
                ids = model.generate(**inp, max_new_tokens=200, do_sample=False)
                gen = ids[:, inp["input_ids"].shape[1]:]
                for r, g in zip(ch, gen):
                    rs.append(score_case(r.id, r.text, proc.decode(g)))
            if rs:
                ag = aggregate(rs)
                per[d] = {"cer": round(ag.cer, 4), "acc": round(ag.accuracy, 4), "n": len(rs)}
    model.train()
    if not per:
        return None
    mean_cer = sum(v["cer"] for v in per.values()) / len(per)
    return {"per_dialect": per, "mean_cer": round(mean_cer, 4),
            "mean_acc": round(1 - mean_cer, 4)}


def _write_log(a, log):
    with open(os.path.join(a.out, "train_log.json"), "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


def _finalize(model, proc, val_rows, collate, a, log, torch, t0):
    """存 adapter + 复算 val CER + 落台账（原 main 收尾段）。"""
    model.save_pretrained(a.out)
    proc.save_pretrained(a.out)
    log["train_seconds"] = round(time.perf_counter() - t0, 1)
    _write_log(a, log)
    print(f"[OK ] adapter → {a.out}（仅 LoRA 权重，未存基座）")

    v = val_cer(model, val_rows, collate, a, proc, torch)
    log["val"] = v
    _write_log(a, log)
    if v:
        print("\n[验证] 分方言 val 准确率:")
        for d, m in sorted(v["per_dialect"].items()):
            print(f"   {d:<10} n={m['n']:<3} 准确率 {m['acc']*100:.2f}%  CER {m['cer']*100:.2f}%")
        print(f"   均值       准确率 {v['mean_acc']*100:.2f}%")
        # r187 修一处必崩的 NameError（拆分时发现，非推断）：原写作
        #   「if cer is not None and cer > 1.0」，而 cer 在本件**从未被赋值**
        #   ⇒ 训练跑完且 val 有读数时这一行必抛 NameError。本机无 GPU/torch，
        #   该路径从未被触发，所以缺陷一直隐形（同族教训：没跑过的路径不算验过）。
        #   口径改用上面已算出的 mean_cer，语义不变（CER>100% ⇒ 标签对齐可疑）。
        if v["mean_cer"] > 1.0:
            print("[WARN] val CER > 100%，检查标签对齐")


def main() -> int:
    a = _parse_args()

    import torch
    from transformers import AutoProcessor, AutoModelForMultimodalLM, get_cosine_schedule_with_warmup

    torch.manual_seed(a.seed)
    random.seed(a.seed)
    np.random.seed(a.seed)

    loaded = _load_rows(a)
    if loaded is None:
        return 2
    train_rows, val_rows, _ho_ids = loaded

    proc = AutoProcessor.from_pretrained(a.model)
    model = AutoModelForMultimodalLM.from_pretrained(a.model, dtype=torch.bfloat16).to("cuda")
    model, _lora_cfg, targets = build_lora(model, a.rank, a.alpha, a.dropout)
    model.gradient_checkpointing_enable()
    model.enable_input_require_grads()   # 冻结基座时必须有这句，否则 checkpointing 梯度断
    model.train()

    collate = Collator(proc, a.max_sec)
    order = _build_order(train_rows, a)

    steps_per_epoch = math.ceil(len(order) / (a.batch_size * a.grad_accum))
    total_steps = max(1, int(steps_per_epoch * a.epochs))
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],
                            lr=a.lr, weight_decay=0.01)
    sched = get_cosine_schedule_with_warmup(opt, int(0.03 * total_steps), total_steps)
    os.makedirs(a.out, exist_ok=True)
    log = {"args": vars(a), "targets": sorted(set(targets))[:200],
           "steps": [], "loss": []}
    print(f"[计划] {total_steps} step（batch {a.batch_size} × accum {a.grad_accum}）")

    t0 = _train_loop(model, proc, opt, sched, collate, order, log, a, torch, total_steps)
    _finalize(model, proc, val_rows, collate, a, log, torch, t0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
