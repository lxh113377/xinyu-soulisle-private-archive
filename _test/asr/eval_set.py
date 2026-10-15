#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""评测集清单（manifest）与公开方言语料适配层。

统一清单格式（JSONL，每行一条）—— 所有方言/场景/来源都收敛到这里，
下游 run_eval.py 只认这个格式，因此新增语料不需要改评测代码：

    {
      "id":        "yue_test_000123",     # 全局唯一
      "audio":     "D:/asr-data/wsyue/xxx.wav",
      "ref":       "参考转写文本",          # 未归一化的原始文本
      "dialect":   "yue",                 # 见 DIALECTS
      "accent":    "hk",                  # 可选：口音/地区细分
      "source":    "WenetSpeech-Yue",     # 语料来源（决定许可与可信度）
      "split":     "test",                # train/val/test/eval
      "domain":    "interview",           # 可选：内容域
      "real_audio": true,                  # false = TTS 合成，不可用于对外报数
      "meta":      {}
    }

关键约束 `real_audio`：
闽南语/台语目前只能拿到 TTS 合成语料（lianghsun/tw-hokkien-audio 由
CosyVoice3 生成）。合成音频的声学分布与真实语音不同，用它测出的准确率
**不代表真实用户场景**。故该字段为 false 的条目在跑分时会被单独统计，
不与真实录音混算，避免「合成数据刷高指标」。
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Dict, Iterator, List, Optional

# ── 方言登记表 ────────────────────────────────────────────────────────────────
# code → (中文名, 是否普通话变体, 公开语料现状)
DIALECTS: Dict[str, dict] = {
    "mandarin": {"zh": "普通话", "is_variety": False, "corpus": "WenetSpeech/AISHELL-3/KeSpeech"},
    "yue":      {"zh": "粤语",   "is_variety": True,  "corpus": "WenetSpeech-Yue (1000h+, 含 WSYue-ASR-eval)"},
    "chuan":    {"zh": "四川话", "is_variety": True,  "corpus": "WenetSpeech-Chuan (10000h+)"},
    "wu":       {"zh": "上海话", "is_variety": True,  "corpus": "WenetSpeech-Wu (含 WenetSpeech-Wu-Bench)"},
    "dongbei":  {"zh": "东北话", "is_variety": True,  "corpus": "KeSpeech 八方言（沈阳待核实）"},
    "minnan":   {"zh": "闽南语", "is_variety": True,  "corpus": "仅 TTS 合成 tw-hokkien-audio（不可验收）"},
    "teochew":  {"zh": "潮州话", "is_variety": True,  "corpus": "teochew_wild 18.9h 野外录音（需申请）"},
    "en":       {"zh": "英语",   "is_variety": False, "corpus": "（对照，非验收目标）"},
}

ACCENT_REQUIRED = {"minnan", "yue", "wu", "chuan"}  # 这些方言必须标地区细分


@dataclass
class Case:
    id: str
    audio: str
    ref: str
    dialect: str = "mandarin"
    accent: str = ""
    source: str = ""
    split: str = "test"
    domain: str = ""
    real_audio: bool = True
    meta: Dict = field(default_factory=dict)

    def to_json(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_json(d: dict) -> "Case":
        known = set(Case.__dataclass_fields__)
        kwargs = {k: v for k, v in d.items() if k in known and k != "meta"}
        # 显式 meta 与「未知键」合并；meta 只能传一次，否则构造器报
        # "got multiple values for keyword argument 'meta'"（实测踩过）
        meta = dict(d.get("meta") or {})
        meta.update({k: v for k, v in d.items() if k not in known})
        kwargs["meta"] = meta
        return Case(**kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# 读写
# ─────────────────────────────────────────────────────────────────────────────
def write_manifest(cases: List[Case], path: str) -> int:
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for c in cases:
            f.write(json.dumps(c.to_json(), ensure_ascii=False) + "\n")
    return len(cases)


def read_manifest(path: str) -> List[Case]:
    out: List[Case] = []
    with open(path, "r", encoding="utf-8") as f:
        for ln, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                out.append(Case.from_json(json.loads(line)))
            except Exception as e:
                raise ValueError(f"{path}:{ln} 清单解析失败: {e}") from e
    return out


def filter_cases(cases: List[Case], *, dialects=None, split=None,
                 sources=None, real_only=False) -> List[Case]:
    def keep(c: Case) -> bool:
        if dialects and c.dialect not in dialects:
            return False
        if split and c.split != split:
            return False
        if sources and c.source not in sources:
            return False
        if real_only and not c.real_audio:
            return False
        return True
    return [c for c in cases if keep(c)]


def summarize(cases: List[Case]) -> str:
    """清单体检：一眼看出哪些方言缺样本、哪些是合成音频。"""
    from collections import Counter
    by_d = Counter(c.dialect for c in cases)
    by_src = Counter(c.source for c in cases)
    synth = [c for c in cases if not c.real_audio]
    missing_audio = [c for c in cases if not os.path.isfile(c.audio)]
    lines = [f"清单总数={len(cases)}",
             "方言分布: " + ", ".join(
                 f"{k}({DIALECTS.get(k, {}).get('zh', '未登记')})={v}"
                 for k, v in sorted(by_d.items())),
             "来源分布: " + (", ".join(f"{k}={v}" for k, v in by_src.most_common()) or "—")]
    if synth:
        lines.append(f"⚠ 合成音频 {len(synth)} 条（不计入对外报数）: "
                     + ", ".join(sorted({c.source for c in synth})))
    if missing_audio:
        lines.append(f"❌ 音频文件缺失 {len(missing_audio)} 条（评测前必须先下载）")
    covered = set(by_d)
    for code in ("mandarin", "yue", "chuan", "wu", "dongbei", "minnan"):
        if code not in covered:
            lines.append(f"❌ 方言缺样本: {code}({DIALECTS[code]['zh']})")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# 数据集适配器
# ─────────────────────────────────────────────────────────────────────────────
def from_aishell3(root: str, dialect: str = "mandarin",
                  source: str = "AISHELL-3") -> List[Case]:
    """AISHELL-3（OpenSLR，普通话朗读，无需注册）。
    目录结构: <root>/{train,test,dev}/<speaker>/<utt>.wav + 同名 .txt（拼音+汉字）
    取 test 划分。参考文本取 txt 中的汉字部分（pinyin 段丢弃）。
    """
    cases: List[Case] = []
    for split in ("test", "dev"):
        sd = os.path.join(root, split)
        if not os.path.isdir(sd):
            continue
        for spk in sorted(os.listdir(sd)):
            spd = os.path.join(sd, spk)
            if not os.path.isdir(spd):
                continue
            for fn in sorted(os.listdir(spd)):
                if not fn.endswith(".wav"):
                    continue
                wav = os.path.join(spd, fn)
                txt = wav[:-4] + ".txt"
                if not os.path.isfile(txt):
                    continue
                with open(txt, "r", encoding="utf-8") as f:
                    raw = f.read().strip()
                # 格式: <pinyin tokens> <utterance-id> <汉字串>
                parts = raw.split()
                han = parts[-1] if parts else ""
                if not han:
                    continue
                cases.append(Case(id=f"aishell3_{split}_{spk}_{fn[:-4]}",
                                  audio=wav, ref=han, dialect=dialect,
                                  accent="mandarin-mainland", source=source,
                                  split=split, domain="read",
                                  meta={"pinyin": " ".join(parts[:-2]) if len(parts) > 2 else ""}))
    return cases


def from_generic_pairs(audio_dir: str, pairs_tsv: str, *, dialect: str,
                       source: str, split: str = "test",
                       accent: str = "", real_audio: bool = True) -> List[Case]:
    """通用适配器：TSV 三列 `相对音频路径<TAB>参考文本`（第 3 列可选说话人）。

    WenetSpeech 系列 / KeSpeech / teochew_wild 等都归一到这个格式，
    各语料只需写一个几十行的转换脚本，不用碰评测核心。
    """
    cases: List[Case] = []
    with open(pairs_tsv, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.rstrip("\n")
            if not line.strip() or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            rel, ref = parts[0].strip(), parts[1].strip()
            spk = parts[2].strip() if len(parts) > 2 else ""
            cases.append(Case(id=f"{dialect}_{split}_{i:06d}",
                              audio=os.path.join(audio_dir, rel),
                              ref=ref, dialect=dialect, accent=accent,
                              source=source, split=split, real_audio=real_audio,
                              meta={"speaker": spk} if spk else {}))
    return cases


# ─────────────────────────────────────────────────────────────────────────────
def selftest() -> bool:
    import tempfile
    ok = True

    def check(name, cond):
        nonlocal ok
        print(f"[{'OK ' if cond else 'FAIL'}] {name}")
        if not cond:
            ok = False

    cs = [
        Case(id="a1", audio="/x/a.wav", ref="你好", dialect="mandarin", source="X", split="test"),
        Case(id="a2", audio="/x/b.wav", ref="唔该", dialect="yue", accent="hk",
             source="WenetSpeech-Yue", split="test"),
        Case(id="a3", audio="/x/c.wav", ref="安安", dialect="minnan",
             source="tw-hokkien-audio", split="test", real_audio=False),
    ]
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "m.jsonl")
        n = write_manifest(cs, p)
        back = read_manifest(p)
        check(f"清单往返一致 (写{n} 读{len(back)})", n == 3 and len(back) == 3)
        check("字段无损", back[1].accent == "hk" and back[2].real_audio is False)

        check("按方言过滤", len(filter_cases(back, dialects=["yue"])) == 1)
        check("real_only 过滤掉合成", len(filter_cases(back, real_only=True)) == 2)

    # 未知键必须进 meta 而不是被丢掉（语料常有额外标注列）
    c = Case.from_json({"id": "z", "audio": "/z.wav", "ref": "文", "custom_col": 42})
    check(f"未知键保留进 meta -> {c.meta}", c.meta.get("custom_col") == 42)

    check("方言表含六目标方言",
          {"mandarin", "yue", "chuan", "wu", "dongbei", "minnan"} <= set(DIALECTS))
    print("\n" + summarize(cs))
    print("MANIFEST-SELFTEST-PASS" if ok else "MANIFEST-SELFTEST-FAIL")
    return ok


if __name__ == "__main__":
    import sys
    sys.exit(0 if selftest() else 1)