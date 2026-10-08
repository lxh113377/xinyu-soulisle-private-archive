# -*- coding: utf-8 -*-
"""心屿 · 情绪模型训练数据管道（S1）

三件套产出：
  ml/data/train.jsonl  (~2000 条，text+label 六类)
  ml/data/dev.jsonl    (~240 条)
  _test/emotion-blindset.json  (~240 条，冻结，不进训练；含危机样本测短路层)

子命令：
  ingest-public   SMP2020-ECDT 镜像 parquet → 公开底料 jsonl（标签映射：happy→joy,
                  angry→anger, sad→sadness, fear→fear, neutral→calm；surprise/disgust 丢弃）
  generate        DeepSeek 扩样（校园倾诉语域，few-shot 取自 73 条评测集）
  verify          DeepSeek 零温二遍标注，与预期不符即丢弃（self-consistency 过滤）
  build           合并+去重+分层 → 三件套
  check           验收：分布表、来源占比、盲测∩训练=0
  audit           抽 10% 人工抽检清单

密钥：环境变量 DEEPSEEK_KEY 优先，否则从 src/js/demo-config.js 抓取（不打印）。
"""
import argparse
import json
import random
import re
import sys
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.stdout.reconfigure(encoding="utf-8")

DATA = ROOT / "ml" / "data"
PUBLIC_RAW = DATA / "public_raw.jsonl"
GEN_RAW = DATA / "gen_raw.jsonl"
BLIND_GEN_RAW = DATA / "blind_gen_raw.jsonl"
TRAIN = DATA / "train.jsonl"
DEV = DATA / "dev.jsonl"
BLIND = ROOT / "_test" / "emotion-blindset.json"
EVALSET = ROOT / "_test" / "emotion-eval-dataset.json"
AUDIT = DATA / "_audit_sample.md"

LABELS = ["joy", "sadness", "anger", "fear", "calm", "love"]
# Um1neko/smp2020 镜像的 label 是数字。映射**不是**按类别名字母序——
# 2026-10-08 按每类抽样内容人工确认：0=火大/烦躁(angry) 1=抑郁/失落(sadness)
# 2=惊恐/害怕(fear) 3=中性陈述(neutral→calm) 4=开心/希望(joy) 5=惊讶句(surprise，丢弃)。
SMP_NUM = {0: "anger", 1: "sadness", 2: "fear", 3: "calm", 4: "joy", 5: None}

BASE = "https://api.deepseek.com/v1"
MODEL = "deepseek-chat"


def get_key():
    k = __import__("os").environ.get("DEEPSEEK_KEY", "").strip()
    if k:
        return k
    m = re.search(r'sk-[A-Za-z0-9]{20,}',
                  (ROOT / "src" / "js" / "demo-config.js").read_text(encoding="utf-8"))
    if not m:
        sys.exit("no key: set DEEPSEEK_KEY or check src/js/demo-config.js")
    return m.group(0)


def chat(key, messages, temperature, max_tokens=4096, retries=3):
    body = json.dumps({"model": MODEL, "messages": messages,
                       "temperature": temperature, "max_tokens": max_tokens}).encode()
    for i in range(retries):
        try:
            req = urllib.request.Request(
                BASE + "/chat/completions", data=body,
                headers={"Content-Type": "application/json",
                         "Authorization": f"Bearer {key}"})
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.load(r)["choices"][0]["message"]["content"]
        except Exception as e:  # noqa: BLE001
            if i == retries - 1:
                raise
            print(f"  retry {i+1}: {e}")


def extract_json_array(text):
    m = re.search(r"\[[\s\S]*\]", text)
    if not m:
        return []
    out = []
    try:
        for it in json.loads(m.group()):
            t = str(it.get("text", "")).strip()
            l = str(it.get("label", "")).strip().lower()
            if t and l in LABELS and 4 <= len(t) <= 60:
                out.append({"text": t, "label": l})
    except json.JSONDecodeError:
        pass
    return out


def cmd_ingest_public(_):
    import pyarrow.parquet as pq  # 延迟导入
    rows, dropped = [], Counter()
    for split in ["train", "test"]:
        p = DATA / f"smp2020_{split}.parquet"
        tbl = pq.read_table(p).to_pylist()
        for r in tbl:
            text = str(r.get("content", r.get("text", ""))).strip()
            raw = r.get("label", r.get("labels"))
            label = SMP_NUM.get(raw if isinstance(raw, int) else str(raw).strip().lower())
            if label and 4 <= len(text) <= 60 and "\u0000" not in text:
                rows.append({"text": text, "label": label,
                             "source": f"smp2020-{split}"})
            else:
                dropped[raw if isinstance(raw, int) else (raw or "empty")] += 1
    with PUBLIC_RAW.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"public raw: {len(rows)} kept -> {PUBLIC_RAW.name}; dropped: {dict(dropped)}")
    print("per-class:", dict(Counter(r["label"] for r in rows)))


SCENES = ["学业考试", "求职面试", "实习工作", "恋爱关系", "暧昧心动", "友情社交",
          "宿舍生活", "家庭沟通", "自我认同", "未来迷茫", "日常小事", "网络生活"]
STYLES = ["直陈叙述", "口语化带梗", "反讽语气", "含否定词（如一点也/并不/毫不）",
          "含程度副词（如特别/超级/稍微）", "两种情绪混合但给出主导"]

ADVERSARIAL_NOTES = {
    "neg": (
        "本轮专项：**否定/反转对抗样本**。句子表面含情绪词但实际主导情绪被否定、反转或降级，"
        "例如：「一点也不开心」→ sadness（joy 被否定）、「没什么好难过的」→ calm、"
        "「我一点都不紧张」→ calm、「不算生气，就是有点失望」→ sadness、"
        "「别难过了，我陪着你」→ calm（安慰语境）。要求每条都含否定/让步结构，"
        "且标注的是说话人**真实主导情绪**而非表面情绪词。"
    ),
    "deg": (
        "本轮专项：**程度修饰对抗样本**。句子含程度副词（特别/超级/极其/稍微/有点/巨）"
        "修饰情绪强度，标注的是修饰后的真实主导情绪，例如「心里特别难受」→ sadness、"
        "「稍微有点烦」→ anger。强度词要与情绪真实匹配，不要全部用最强程度。"
    ),
}


def fewshot_examples():
    items = json.loads(EVALSET.read_text(encoding="utf-8"))["items"]
    by = {}
    for it in items:
        if it["expect"] in LABELS and it["expect"] not in by:
            by[it["expect"]] = it["text"]
    return by


def gen_prompt(label, n, shots, kind=""):
    adv = ADVERSARIAL_NOTES.get(kind, "")
    return (
        "你是中文情绪语料标注专家。为情绪分类模型生成训练样本，要求：\n"
        f"1. 目标主导情绪：{label}（joy=愉悦/开心, sadness=低落/失落, anger=烦躁/愤怒, "
        "fear=焦虑/紧张, calm=平静/无波澜, love=心动/恋爱/想念）\n"
        "2. 语域：大学生或年轻人向朋友倾诉的第一人称短句，10-40 字\n"
        "3. 场景从这些里变化取材：" + "、".join(SCENES) + "\n"
        "4. 表达风格要覆盖：" + "；".join(STYLES) + "\n"
        + (adv + "\n" if adv else "")
        + "5. 不要出现与示例相同的句子；不要出现自杀等危机表述；纯口语、真实、多样\n"
        f"参考示例（勿复制）：{json.dumps(shots, ensure_ascii=False)}\n"
        f"只输出 JSON 数组，共 {n} 条，格式 [{{\"text\":\"...\",\"label\":\"{label}\"}},...]"
    )


def cmd_generate(args):
    key = get_key()
    shots = fewshot_examples()
    out_path = BLIND_GEN_RAW if args.for_blind else GEN_RAW
    per_batch, batches = 50, args.batches
    seen = set()
    if out_path.exists():
        seen = {json.loads(l)["text"] for l in out_path.read_text(encoding="utf-8").splitlines() if l.strip()}
    total = 0
    for b in range(batches):
        label = args.only if args.only in LABELS else LABELS[(b + args.offset) % 6]
        prompt = gen_prompt(label, per_batch, shots, kind=args.kind)
        content = chat(key, [{"role": "system", "content": prompt},
                             {"role": "user", "content": f"第{b+1}批，目标情绪 {label}，换一批不同的场景与表达。"}],
                       temperature=1.05)
        items = extract_json_array(content)
        new = [it for it in items if it["text"] not in seen]
        seen.update(it["text"] for it in new)
        with out_path.open("a", encoding="utf-8") as f:
            for it in new:
                it["source"] = "deepseek-gen"
                f.write(json.dumps(it, ensure_ascii=False) + "\n")
        total += len(new)
        print(f"batch {b+1}/{batches} [{label}]: +{len(new)} (dup {len(items)-len(new)})")
    print(f"generated {total} new -> {out_path.name}")


def cmd_verify(args):
    key = get_key()
    src = BLIND_GEN_RAW if args.for_blind else GEN_RAW
    lines = [json.loads(l) for l in src.read_text(encoding="utf-8").splitlines() if l.strip()]
    kept, dropped = [], 0
    B = 60
    for i in range(0, len(lines), B):
        chunk = lines[i:i + B]
        listing = "\n".join(f'{j}. {it["text"]}' for j, it in enumerate(chunk))
        content = chat(key, [
            {"role": "system", "content":
                "你是零温度情绪标注器。对每条文本判定主导情绪，只能从 joy/sadness/anger/fear/calm/love 中选。"
                "只输出 JSON 数组：[{\"i\":序号,\"label\":\"...\"},...]，条数必须与输入一致。"},
            {"role": "user", "content": listing}], temperature=0.0)
        try:
            marks = {int(m["i"]): str(m["label"]).strip().lower()
                     for m in json.loads(re.search(r"\[[\s\S]*\]", content).group())}
        except Exception:  # noqa: BLE001
            dropped += len(chunk)
            continue
        for j, it in enumerate(chunk):
            if marks.get(j) == it["label"]:
                kept.append(it)
            else:
                dropped += 1
        print(f"verified {min(i+B,len(lines))}/{len(lines)} kept={len(kept)} dropped={dropped}")
    with src.with_suffix(".verified.jsonl").open("w", encoding="utf-8") as f:
        for it in kept:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    print(f"self-consistency: kept {len(kept)} / {len(lines)} -> {src.stem}.verified.jsonl")


def norm_text(t):
    return re.sub(r"[\s，。！？、,.!?~～]+", "", t).lower()


def ngrams(t, n=3):
    t = norm_text(t)
    return {t[i:i + n] for i in range(max(1, len(t) - n + 1))}


def jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def load_jsonl(p):
    p = Path(p)
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def dedup(items, thresh=0.75):
    """3-gram 倒排索引去重：只对共享 gram 的候选比对 Jaccard（原 O(n²) 全比对在 2 万条规模上要跑 10+ 分钟）。"""
    kept, kept_ng = [], []
    inv = {}  # gram -> 已收条目下标列表
    for it in items:
        ng = ngrams(it["text"])
        cands = set()
        for g in ng:
            cands.update(inv.get(g, ()))
        if any(jaccard(ng, kept_ng[c]) >= thresh for c in cands):
            continue
        idx = len(kept_ng)
        kept.append(it)
        kept_ng.append(ng)
        for g in ng:
            inv.setdefault(g, []).append(idx)
    return kept


def cmd_build(_):
    # 已有 73 条评测集文本必须从所有训练/盲测语料中剔除（防泄漏）
    eval_texts = {norm_text(it["text"]) for it in json.loads(
        EVALSET.read_text(encoding="utf-8"))["items"]}

    pub = dedup([it for it in load_jsonl(PUBLIC_RAW) if norm_text(it["text"]) not in eval_texts])
    gen = dedup([it for it in load_jsonl(GEN_RAW.with_suffix(".verified.jsonl"))
                 if norm_text(it["text"]) not in eval_texts])
    blind_gen = dedup([it for it in load_jsonl(BLIND_GEN_RAW.with_suffix(".verified.jsonl"))
                       if norm_text(it["text"]) not in eval_texts])
    blind_gen_text = {norm_text(it["text"]) for it in blind_gen}
    # 盲测文本不得出现在训练池
    pub = [it for it in pub if norm_text(it["text"]) not in blind_gen_text]
    gen = [it for it in gen if norm_text(it["text"]) not in blind_gen_text]

    rng = random.Random(42)
    rng.shuffle(pub)
    rng.shuffle(gen)

    # 公开池分层限额：微博域样本偏多，按类限额防止霸池（每类 train≤300 / dev≤50）；
    # 生成样本（校园域）全量进入。love 公开池为零，全靠生成补。
    PUB_TRAIN_CAP, PUB_DEV_CAP = 300, 50
    pub_by = {}
    for it in pub:
        pub_by.setdefault(it["label"], []).append(it)
    pub_train, pub_dev = [], []
    for lab, items in pub_by.items():
        pub_train += items[:PUB_TRAIN_CAP]
        pub_dev += items[PUB_TRAIN_CAP:PUB_TRAIN_CAP + PUB_DEV_CAP]

    # dev 从两来源各抽；训练池 = 余量
    GEN_DEV_CAP = 120
    gen_by = {}
    for it in gen:
        gen_by.setdefault(it["label"], []).append(it)
    gen_dev, gen_train = [], []
    for lab, items in gen_by.items():
        gen_dev += items[:GEN_DEV_CAP]
        gen_train += items[GEN_DEV_CAP:]
    dev = pub_dev + gen_dev
    train = pub_train + gen_train

    # 盲测：生成批次 + 补危机样本（测短路层，不训模型）+ 从评测集风格补少量边界样例说明
    blind_items = [{"text": it["text"], "expect": it["label"]} for it in blind_gen]
    blind_meta = {
        "name": "心屿情绪模型盲测集 v1",
        "date": "2026-10-08",
        "frozen": True,
        "note": "冻结盲测集：与 train/dev 零交集（build 脚本内断言）。来源=DeepSeek 生成+self-consistency 过滤；"
                "expect=预期主导情绪；含 crisis 样本（危机短路层负责，不进模型训练标签）。",
    }
    # 危机样例：从评测集危机条目风格改写 6 条（不复制原文）
    crisis_seeds = ["感觉撑不下去了，想消失", "压得喘不过气，真的想一了百了",
                    "每天都很痛苦，觉得死了更轻松", "有时候希望一觉睡过去就不用醒了",
                    "撑不住了，想结束这一切", "活得好累，不如没了算了"]
    blind_items += [{"text": t, "expect": "crisis"} for t in crisis_seeds]
    rng.shuffle(blind_items)

    with TRAIN.open("w", encoding="utf-8") as f:
        for it in train:
            f.write(json.dumps({"text": it["text"], "label": it["label"],
                                "source": it.get("source", "?")}, ensure_ascii=False) + "\n")
    with DEV.open("w", encoding="utf-8") as f:
        for it in dev:
            f.write(json.dumps({"text": it["text"], "label": it["label"],
                                "source": it.get("source", "?")}, ensure_ascii=False) + "\n")
    BLIND.write_text(json.dumps({"meta": blind_meta,
                                 "items": blind_items}, ensure_ascii=False, indent=1),
                     encoding="utf-8")

    print(f"train={len(train)} dev={len(dev)} blind={len(blind_items)}")
    print("train per-class:", dict(Counter(it['label'] for it in train)))
    print("train source:", dict(Counter(it.get('source', '?').split('-')[0] for it in train)))


def cmd_check(_):
    train = load_jsonl(TRAIN)
    dev = load_jsonl(DEV)
    blind = json.loads(BLIND.read_text(encoding="utf-8"))["items"]
    tn = {norm_text(it["text"]) for it in train}
    dn = {norm_text(it["text"]) for it in dev}
    bn = {norm_text(it["text"]) for it in blind}
    ev = {norm_text(it["text"]) for it in json.loads(
        EVALSET.read_text(encoding="utf-8"))["items"]}
    assert not (tn & bn), f"blind∩train leak: {len(tn & bn)}"
    assert not (dn & bn), f"blind∩dev leak: {len(dn & bn)}"
    assert not (tn & ev), f"eval73∩train leak: {len(tn & ev)}"
    assert not (bn & ev), f"eval73∩blind leak: {len(bn & ev)}"
    print(f"train={len(train)} dev={len(dev)} blind={len(blind)}")
    print("train per-class:", dict(Counter(it["label"] for it in train)))
    print("dev per-class:", dict(Counter(it["label"] for it in dev)))
    print("blind per-class:", dict(Counter(it["expect"] for it in blind)))
    src = Counter(it.get("source", "?").split("-")[0] for it in train)
    print("train source:", dict(src))
    print("CHECK-PASS: 无泄漏断言全部通过")


def cmd_audit(_):
    rows = load_jsonl(TRAIN) + load_jsonl(DEV)
    rng = random.Random(7)
    sample = rng.sample(rows, max(1, len(rows) * 2 // 20))
    with AUDIT.open("w", encoding="utf-8") as f:
        f.write("# 人工抽检清单（10% 抽样）\n\n判定该句主导情绪是否与标注一致（Y/N）：\n\n")
        f.write("| # | text | label | 一致? |\n|---|---|---|---|\n")
        for i, it in enumerate(sample):
            f.write(f"| {i+1} | {it['text']} | {it['label']} |  |\n")
    print(f"audit sample {len(sample)} -> {AUDIT}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ingest-public")
    g = sub.add_parser("generate")
    g.add_argument("--batches", type=int, default=10)
    g.add_argument("--offset", type=int, default=0)
    g.add_argument("--only", default="", help="只生成指定情绪（如 love），补类缺口用")
    g.add_argument("--kind", default="", choices=["", "neg", "deg"],
                   help="对抗专项：neg=否定反转 / deg=程度修饰")
    g.add_argument("--for-blind", action="store_true")
    v = sub.add_parser("verify")
    v.add_argument("--for-blind", action="store_true")
    sub.add_parser("build")
    sub.add_parser("check")
    sub.add_parser("audit")
    args = ap.parse_args()
    {"ingest-public": cmd_ingest_public, "generate": cmd_generate,
     "verify": cmd_verify, "build": cmd_build, "check": cmd_check,
     "audit": cmd_audit}[args.cmd](args)


if __name__ == "__main__":
    main()
