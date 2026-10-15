#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ASR 评测文本归一化 —— 中文 ASR 的 CER 对分母极其敏感，归一化规则即口径。

设计要点（与本项目 ASR 评测矩阵配套）：
1. 标点/空白全剥离：中文 CER 以「字」为单位，标点不入分母，否则读句读得对也会被扣分。
2. 全角→半角：数字/字母/标点统一，避免「全角逗号 vs 半角逗号」被判成替换错误。
3. 繁→简：WenetSpeech 系列（粤/川/吴）与 AISHELL 转写表繁简混用，不统一则 CER 虚高数个百分点。
4. 大小写折叠：英文借词、拼音标注混排时需要。
5. 方言字表：钩子留给各方言正字法（如潮州话「歹看正字法」的 祇/只/介），
   由调用方注入，避免把方言专用字误判为错字。

刻意不做的事：
- 不做同音字纠正：那属于「模型该做的事」，评测里帮忙改 = 掩盖真实错误。
- 不做简繁之外的语义归一：会掩盖真实识别错误。
"""
from __future__ import annotations

import re
import unicodedata
from typing import Callable, Iterable, Mapping, Optional

# ── 标点/符号（含全角）──────────────────────────────────────────────────────
# 覆盖 CJK 标点、ASCII 标点、常见符号类 Unicode 区段。
_PUNCT = (
    "\u3000-\u303f"   # CJK 标点（。、《》「」等）
    "\uff00-\uffef"   # 全角 ASCII（，！？ＡＢＣ）
    "\u2018-\u201f"   # 弯引号 / 破折号
    "\u2026"          # 省略号
    "\u00b7"          # 间隔号
    "\u00a0"          # 不换行空格
)
_PUNCT_RE = re.compile("[" + _PUNCT + "]")

# ── 需要显式剔除的 ASCII 符号（不在上面区段内）──────────────────────────────
_ASCII_JUNK_RE = re.compile(r"[!-/:-@\[-`{-~]")   # 标点与符号，但不误伤汉字/字母/数字

# 保留的字符类：汉字、字母、数字
_KEEP_RE = re.compile(r"[^0-9a-z\u4e00-\u9fff\u3400-\u4dbf]+")

# 语料自带的**噪声段标记**：KeSpeech 用 <SPOKEN_NOISE> 标出该处本人没说清/有杂音。
# 它是标注元信息，不是「该被识别出来的字」⇒ 归一化阶段必须剥掉，
# 否则模型识别对了反而被判成删除错误（CER 虚高）。
# 实测：232 条里 2 条含此标记，两条都因此把 CER 从 ~20% 抬到 50–65%。
# ⚠ 必须**在 ASCII 标点剥离之前**执行：否则尖括号先被当普通标点删掉，
#   只剩字母 "SPOKENNOISE" 被当英文保留 ⇒ 凭空多出 11 个字符，CER 虚高（实测踩过）。
#   收录范围写成显式清单而不是正则：正则如 <[A-Z_]+> 会连带吃掉
#   真实文本里可能出现的合法尖括号内容（如 <3 或 <UNK> 之外的比较式），
#   而清单里的每一项都是**确认过的**语料标记。
CORPUS_TAGS = ("<SPOKEN_NOISE>", "<UNK>", "<UNKNOWN>", "<SILENCE>", "<NOISE>", "<INAUGIBLE>")

# 简繁映射表：优先用 opencc（有则更好），否则用内置小表覆盖高频。
_T2S_FALLBACK = str.maketrans({
    "個": "个", "們": "们", "這": "这", "麼": "么", "說": "说", "時": "时",
    "會": "会", "對": "对", "過": "过", "還": "还", "沒": "没", "後": "后",
    "來": "来", "學": "学", "國": "国", "點": "点", "為": "为", "與": "与",
    "樣": "样", "開": "开", "關": "关", "現": "现", "實": "实", "進": "进",
    "動": "动", "麼": "么", "應": "应", "該": "该", "當": "当", "經": "经",
    "給": "给", "讓": "让", "從": "从", "頭": "头", "麼": "么", "話": "话",
    "語": "语", "讀": "读", "聽": "听", "講": "讲", "認": "认", "識": "识",
})

_opencc_conv: Optional[Callable[[str], str]] = None
_opencc_probed = False


def _get_opencc() -> Optional[Callable[[str], str]]:
    """惰性探测 opencc；没装就退回内置小表（只影响覆盖率，不影响口径一致性）。"""
    global _opencc_conv, _opencc_probed
    if _opencc_probed:
        return _opencc_conv
    _opencc_probed = True
    try:
        from opencc import OpenCC  # type: ignore

        _opencc_conv = OpenCC("t2s").convert
    except Exception:
        _opencc_conv = None
    return _opencc_conv


def normalize(
    text: str,
    *,
    to_simplified: bool = True,
    fold_case: bool = True,
    dialect_map: Optional[Mapping[str, str]] = None,
    drop_punct: bool = True,
) -> str:
    """把一条转写归一化成可比对序列。

    :param text: 原始转写（可为 None/空）
    :param to_simplified: 繁→简（需 opencc，缺失时退内置小表）
    :param fold_case: 英文字母小写化
    :param dialect_map: 方言正字映射，如 {"祇":"只", "侬":"你"}；在简繁转换之后应用，
                        这样映射表写简体即可。
    :param drop_punct: 剥离标点与空白。设 False 时保留非空白字符（用于 WER 分词场景）。
    """
    if not text:
        return ""
    s = unicodedata.normalize("NFKC", str(text))   # 全角→半角、兼容字符折叠
    # ⚠ 顺序有讲究：标注标记必须在**大小写折叠之前**剥掉，且大小写不敏感。
    #   NFKC 会把全角尖括号 ＜SPOKEN_NOISE＞ 折成半角，而 fold_case 会把标记
    #   变成 "<spoken_noise>" —— 若按清单里的大写原样 replace 就会**一个都匹配不上**，
    #   尖括号随后被当普通标点删掉，只剩字母 "spokennoise" 被当英文保留
    #   ⇒ 凭空多出 11 个字符，CER 虚高（实测踩过：自检里 <UNKNOWN>→'unknown' 当场变红）。
    for tag in CORPUS_TAGS:        # 先剥标注标记（清单式，不用正则）
        s = s.replace(tag, "").replace(tag.lower(), "").replace(tag.upper(), "")
    if fold_case:
        s = s.lower()
    if to_simplified:
        conv = _get_opencc()
        s = conv(s) if conv else s.translate(_T2S_FALLBACK)
    s = _PUNCT_RE.sub("", s)
    s = _ASCII_JUNK_RE.sub("", s)
    if dialect_map:
        for k, v in dialect_map.items():
            s = s.replace(k, v)
    s = _KEEP_RE.sub("", s)
    return s


def normalize_pair(ref: str, hyp: str, **kw) -> tuple[str, str]:
    """参考/假设用同一套规则归一化 —— 这是 CER 可复现的前提。"""
    return normalize(ref, **kw), normalize(hyp, **kw)


def load_dialect_map(path: str) -> dict:
    """从 `字<TAB>字` 每行一个的文本文件加载方言正字映射。忽略 # 注释与空行。"""
    out: dict = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) >= 2:
                out[parts[0]] = parts[1]
    return out


if __name__ == "__main__":
    # 自检：归一化的口径必须是可预测的
    cases = [
        ("你好，世界！", "你好世界"),
        ("這是什麼？", "这是什么"),
        ("ＡＢＣ１２３", "abc123"),
        ("我想說：唔該", "我想说唔该"),
        ("心态<SPOKEN_NOISE>膨胀这点上大同小异", "心态膨胀这点上大同小异"),
        ("但层出不穷的<SPOKEN_NOISE>监测数据造假", "但层出不穷的监测数据造假"),
        ("<UNKNOWN>", ""),
        ("", ""),
        (None, ""),
    ]
    ok = True
    for src, want in cases:
        got = normalize(src)
        flag = "OK " if got == want else "FAIL"
        if got != want:
            ok = False
        print(f"[{flag}] {src!r} -> {got!r} (want {want!r})")
    print("NORMALIZE-SELFTEST-PASS" if ok else "NORMALIZE-SELFTEST-FAIL")
    raise SystemExit(0 if ok else 1)