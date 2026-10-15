#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CER / WER 计算 + 错误来源定位。

为什么自己实现而不用 jiwer：需求 1 要求「定位核心误差来源」，这需要拿到
**对齐后的错误明细**（哪些字错了、错在哪类、集中在哪些词），jiwer 只给一个总分。
jiwer 仍用于交叉校验（见 selftest 末尾的一致性断言）。

CER 定义（中文标准口径）：
    CER = (替换 S + 删除 D + 插入 I) / 参考文本字符数 N
    准确率 = 1 - CER          ← 验收指标 98% / 92% 指的是这个，不是 WER
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Sequence, Tuple

from normalize import normalize  # noqa: F401  (供上层直接复用)


@dataclass
class AlignOp:
    """对齐后的单个操作。"""
    op: str          # 'equal' | 'sub' | 'del' | 'ins'
    ref: str         # 参考字符（ins 时为空）
    hyp: str         # 识别字符（del 时为空）


@dataclass
class CaseResult:
    """单条评测结果。"""
    case_id: str
    ref_raw: str
    hyp_raw: str
    ref: str                       # 归一化后
    hyp: str                       # 归一化后
    errors: int = 0
    ref_len: int = 0
    ops: List[AlignOp] = field(default_factory=list)

    @property
    def cer(self) -> float:
        return self.errors / self.ref_len if self.ref_len else 0.0

    @property
    def sub(self) -> int: return sum(1 for o in self.ops if o.op == "sub")
    @property
    def dele(self) -> int: return sum(1 for o in self.ops if o.op == "del")
    @property
    def ins(self) -> int: return sum(1 for o in self.ops if o.op == "ins")

    @property
    def accuracy(self) -> float:
        """字符准确率 = 1 - CER。空参考按 1.0 记（无可罚）。"""
        return 1.0 - self.cer if self.ref_len else 1.0


def align(ref: str, hyp: str) -> List[AlignOp]:
    """标准 Levenshtein 回溯，返回逐字操作序列。

    用滚动数组求编辑距离表，再回溯出对齐路径 —— O(N*M) 时间 / O(M) 额外空间的表，
    回溯需要整表，故此处保留 O(N*M) 内存。评测句长通常 < 200 字，可接受。
    """
    n, m = len(ref), len(hyp)
    if n == 0:
        return [AlignOp("ins", "", c) for c in hyp]
    if m == 0:
        return [AlignOp("del", c, "") for c in ref]

    # dp[i][j] = ref[:i] 与 hyp[:j] 的最小编辑距离
    dp: List[List[int]] = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        dp[i][0] = i
    for j in range(m + 1):
        dp[0][j] = j
    for i in range(1, n + 1):
        ri = ref[i - 1]
        row, prev = dp[i], dp[i - 1]
        for j in range(1, m + 1):
            cost = 0 if ri == hyp[j - 1] else 1
            row[j] = min(prev[j] + 1, row[j - 1] + 1, prev[j - 1] + cost)

    ops: List[AlignOp] = []
    i, j = n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0:
            cost = 0 if ref[i - 1] == hyp[j - 1] else 1
            if dp[i][j] == dp[i - 1][j - 1] + cost:
                ops.append(AlignOp("equal" if cost == 0 else "sub", ref[i - 1], hyp[j - 1]))
                i, j = i - 1, j - 1
                continue
        if i > 0 and dp[i][j] == dp[i - 1][j] + 1:
            ops.append(AlignOp("del", ref[i - 1], ""))       # 参考有、识别漏
            i -= 1
            continue
        ops.append(AlignOp("ins", "", hyp[j - 1]))            # 识别多出来
        j -= 1
    ops.reverse()
    return ops


def score_case(case_id: str, ref_raw: str, hyp_raw: str, *, dialect_map=None) -> CaseResult:
    """归一化 → 对齐 → 计数。单条用例的完整评测。"""
    ref, hyp = normalize(ref_raw, dialect_map=dialect_map), normalize(hyp_raw, dialect_map=dialect_map)
    ops = align(ref, hyp)
    res = CaseResult(case_id=case_id, ref_raw=ref_raw or "", hyp_raw=hyp_raw or "",
                     ref=ref, hyp=hyp, ref_len=len(ref))
    res.ops = ops
    res.errors = sum(1 for o in ops if o.op != "equal")
    return res


@dataclass
class Aggregate:
    """一组用例的汇总。"""
    n_cases: int = 0
    total_errors: int = 0
    total_ref_len: int = 0
    sub: int = 0
    dele: int = 0
    ins: int = 0
    cases: List[CaseResult] = field(default_factory=list)

    @property
    def cer(self) -> float:
        """语料级 CER = 总编辑距离 / 总参考字数（不是逐条 CER 求平均 —— 后者会偏袒短句）。"""
        return self.total_errors / self.total_ref_len if self.total_ref_len else 0.0

    @property
    def accuracy(self) -> float:
        return 1.0 - self.cer

    @property
    def sent_acc(self) -> float:
        """完全正确句子的占比（整句零编辑距离）。辅助观察，不作验收。"""
        return (sum(1 for c in self.cases if c.errors == 0) / self.n_cases) if self.n_cases else 0.0

    def add(self, r: CaseResult) -> None:
        self.n_cases += 1
        self.total_errors += r.errors
        self.total_ref_len += r.ref_len
        self.sub += r.sub
        self.dele += r.dele
        self.ins += r.ins
        self.cases.append(r)

    def worst(self, k: int = 20) -> List[CaseResult]:
        return sorted(self.cases, key=lambda c: -c.cer)[:k]

    def error_profile(self, k: int = 20) -> List[Tuple[str, str, int]]:
        """定位核心误差来源：最常见的混淆对（ref→hyp）。

        这是要求 1「定位核心误差来源」的直接产物 —— 把错误聚成
        「方言同音字混淆 / 漏字 / 多字 / 专名错拼」几类，用于决定纠错层该补什么。
        """
        from collections import Counter
        cnt: Counter = Counter()
        for c in self.cases:
            for o in c.ops:
                if o.op == "sub":
                    cnt[(o.ref, o.hyp)] += 1
        return cnt.most_common(k)


def aggregate(results: Sequence[CaseResult]) -> Aggregate:
    agg = Aggregate()
    for r in results:
        agg.add(r)
    return agg


def format_report(agg: Aggregate, title: str = "", top_k: int = 15) -> str:
    lines = []
    if title:
        lines.append(f"=== {title} ===")
    lines.append(
        f"CER={agg.cer * 100:.2f}%  准确率={agg.accuracy * 100:.2f}%  "
        f"用例={agg.n_cases}  参考字数={agg.total_ref_len}  编辑距离={agg.total_errors}"
    )
    if agg.total_errors:
        pct = lambda v: f"{v / agg.total_errors * 100:5.1f}%"  # noqa: E731
        lines.append(f"  错误构成: 替换 {agg.sub}({pct(agg.sub)}) "
                     f"删除 {agg.dele}({pct(agg.dele)}) 插入 {agg.ins}({pct(agg.ins)})")
    lines.append(f"  整句全对率={agg.sent_acc * 100:.2f}%")
    prof = agg.error_profile(top_k)
    if prof:
        lines.append(f"  Top{top_k} 混淆对(ref→hyp): " +
                     ", ".join(f"{a}→{b}×{n}" for (a, b), n in prof))
    return "\n".join(lines)


if __name__ == "__main__":
    ok = True
    r = score_case("t1", "今天天气不错", "今天天气不好")
    assert r.errors == 1 and r.ref_len == 6, r
    assert abs(r.accuracy - 5 / 6) < 1e-9
    print(f"[OK ] 1 替换: CER={r.cer:.4f}")

    r = score_case("t2", "今天天气不错", "今天天不错")
    assert r.dele == 1, r.ops
    print(f"[OK ] 1 删除")

    r = score_case("t3", "今天天气不错", "今天今天天气不错")
    assert r.ins == 2, r.ops
    print(f"[OK ] 2 插入")

    r = score_case("t4", "完全一致", "完全一致")
    assert r.errors == 0 and r.accuracy == 1.0
    print(f"[OK ] 零错误")

    # 归一化口径必须生效：标点/全角/繁简差异不得计错
    r = score_case("t5", "這是什麼，", "这是什 么！")
    assert r.errors == 0, r.ops
    print("[OK ] 归一化后繁简+标点+空格等价")

    # 语料级聚合 ≠ 逐条平均
    rs = [score_case("a", "一二三", "一二三"), score_case("b", "一二三四五六七八九十", "一二三四五六七八九零")]
    agg = aggregate(rs)
    assert agg.total_ref_len == 13 and agg.total_errors == 1, agg
    assert abs(agg.cer - 1 / 13) < 1e-9, agg.cer
    print(f"[OK ] 语料级聚合 CER={agg.cer:.4f} (逐条平均会是 {(0 + 0.1) / 2:.4f})")

    # 与 jiwer 交叉校验（若已安装）。
    # ⚠ 必须用 **字符级** process_characters，不能用 process_words：
    #   中文没有空格分词，词级 WER 会把整句当成 1 个词，
    #   「今天天气不错/不好」在词级下是 2 替 1 = 2.0，与字级 CER 0.1667 毫无可比性
    #   （实测踩过：装上 jiwer 后本断言反而变红，是校验本身写错了）。
    try:
        from jiwer import process_characters  # type: ignore
        # process_characters 返回 CharacterOutput，字段是 .cer（不是 .wer）
        got = process_characters("今天天气不错", "今天天气不好").cer
        mine = score_case("x", "今天天气不错", "今天天气不好").cer
        assert abs(got - mine) < 1e-9, (got, mine)
        print(f"[OK ] 与 jiwer process_characters 交叉校验一致 ({got:.4f})")
    except ImportError:
        print("[SKIP] jiwer 未安装，跳过交叉校验")

    print("METRICS-SELFTEST-PASS")