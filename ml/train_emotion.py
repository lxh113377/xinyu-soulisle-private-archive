# -*- coding: utf-8 -*-
"""心屿 · 情绪分类模型微调（S2）

模型：hfl/chinese-roberta-wwm-ext（110M，六类分类头）
数据：ml/data/train.jsonl + dev.jsonl（build_dataset.py 产出，六类，危机不进模型）
指标：dev 宏 F1 早停；训练后在 **73 条评测集**（_test/emotion-eval-dataset.json）上对账
      —— 危机条目由路由层词典短路负责（6/6 永远成立），模型只对账 67 条非危机条目。
硬门：67 条非危机 accuracy ≥ 现词典基线才允许接入主判（route=auto 默认才真正接管）。

用法：ml/.venv/Scripts/python.exe ml/train_emotion.py [--epochs 5] [--no-cuda]
"""
import argparse
import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding="utf-8")

DATA = ROOT / "ml" / "data"
CKPT = ROOT / "ml" / "checkpoints" / "best"
REPORTS = ROOT / "ml" / "reports"
EVALSET = ROOT / "_test" / "emotion-eval-dataset.json"

LABELS = ["joy", "sadness", "anger", "fear", "calm", "love"]
L2I = {l: i for i, l in enumerate(LABELS)}
# 本地权重优先（ml/base，curl 直下；hf-mirror 对 400MB 大文件的 xet 协议不稳，r-t1 实测）
_BASE = ROOT / "ml" / "base"
MODEL_NAME = (str(_BASE) if (_BASE / "config.json").exists()
              and (_BASE / "pytorch_model.bin").exists() else "hfl/chinese-roberta-wwm-ext")
BASELINE = 98.6  # 73 条评测集上词典引擎基线（72/73，2026-10-08 node _test/emotion_eval.js 当次复跑）
BASELINE_NON_CRISIS = 98.5  # 非危机口径：65/66（唯一 miss =「没什么好难过的」expect calm → 词典判 sadness）


def load_jsonl(p):
    return [json.loads(l) for l in Path(p).read_text(encoding="utf-8").splitlines() if l.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=5)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--no-cuda", action="store_true")
    args = ap.parse_args()

    import torch
    from torch.utils.data import Dataset
    from transformers import (AutoModelForSequenceClassification, AutoTokenizer,
                              Trainer, TrainingArguments)
    from sklearn.metrics import f1_score

    device = "cuda" if (torch.cuda.is_available() and not args.no_cuda) else "cpu"
    print(f"device={device}", flush=True)

    train_rows = load_jsonl(DATA / "train.jsonl")
    dev_rows = load_jsonl(DATA / "dev.jsonl")
    print(f"train={len(train_rows)} dev={len(dev_rows)}")

    tok = AutoTokenizer.from_pretrained(MODEL_NAME)

    class DS(Dataset):
        def __init__(self, rows):
            self.rows = rows

        def __len__(self):
            return len(self.rows)

        def __getitem__(self, i):
            r = self.rows[i]
            enc = tok(r["text"], truncation=True, max_length=64)
            return {"input_ids": enc["input_ids"],
                    "attention_mask": enc["attention_mask"],
                    "labels": L2I[r["label"]]}

    def collate(batch):
        maxlen = max(len(b["input_ids"]) for b in batch)
        pad = tok.pad_token_id
        return {
            "input_ids": torch.tensor([b["input_ids"] + [pad] * (maxlen - len(b["input_ids"])) for b in batch]),
            "attention_mask": torch.tensor([b["attention_mask"] + [0] * (maxlen - len(b["attention_mask"])) for b in batch]),
            "labels": torch.tensor([b["labels"] for b in batch]),
        }

    def compute_metrics(p):
        preds = p.predictions.argmax(-1)
        return {"macro_f1": f1_score(p.label_ids, preds, average="macro")}

    model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME, num_labels=6)
    targs = TrainingArguments(
        output_dir=str(ROOT / "ml" / "checkpoints"),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch,
        per_device_eval_batch_size=64,
        learning_rate=args.lr,
        fp16=(device == "cuda"),
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="macro_f1",
        greater_is_better=True,
        save_total_limit=1,
        logging_steps=20,
        report_to=[],
        seed=42,
        use_cpu=(device == "cpu"),
    )
    trainer = Trainer(model=model, args=targs, train_dataset=DS(train_rows),
                      eval_dataset=DS(dev_rows), data_collator=collate,
                      compute_metrics=compute_metrics)
    t0 = time.time()
    trainer.train()
    print(f"train wall: {time.time()-t0:.0f}s")

    metrics = trainer.evaluate()
    print("dev metrics:", metrics)
    CKPT.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(CKPT))
    tok.save_pretrained(str(CKPT))

    # ---- 评测集对账（模型单腿；危机条目由路由层短路层负责，不进模型成绩）----
    import torch as _t
    model.eval()
    items = json.loads(EVALSET.read_text(encoding="utf-8"))["items"]
    correct, total, crisis_ok = 0, 0, 0
    misses = []
    for it in items:
        if it["expect"] == "crisis":
            crisis_ok += 1  # 短路层 100% 负责（词典危机词命中即拦截，r76 已 6/6）
            continue
        enc = tok(it["text"], truncation=True, max_length=64, return_tensors="pt").to(device)
        with _t.no_grad():
            logits = model(**enc).logits
        pred = LABELS[int(logits.argmax(-1))]
        total += 1
        if pred == it["expect"]:
            correct += 1
        else:
            misses.append({"text": it["text"], "expect": it["expect"], "pred": pred})
    acc = round(correct * 100.0 / total, 1)
    REPORTS.mkdir(parents=True, exist_ok=True)
    report = {
        "date": time.strftime("%Y-%m-%d"),
        "model": MODEL_NAME,
        "device": device,
        "dev_metrics": {k: round(v, 4) for k, v in metrics.items()},
        "eval73_model_only": {"total_non_crisis": total, "correct": correct,
                              "accuracy": acc,
                              "note": "危机 6 条由词典短路层负责（路由层 6/6 保证），不进模型单腿成绩"},
        "eval73_misses": misses,
        "baseline_lexicon_73": BASELINE,
        "gate": "accuracy(67 non-crisis) 与词典引擎同口径对账；正式基线见 _test/emotion_eval.js 输出",
    }
    (REPORTS / "eval_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"eval73 model-only: {acc}% ({correct}/{total}) misses={len(misses)}")
    print("REPORT ->", REPORTS / "eval_report.json")


if __name__ == "__main__":
    main()
