# -*- coding: utf-8 -*-
"""r94：把 docs/quality-gates.md 里 loc_guard / bench_rollup 两行登记更新到本轮实况。"""
from pathlib import Path

P = Path("docs/quality-gates.md")
lines = P.read_text(encoding="utf-8").splitlines(keepends=True)

NEW = {
    "loc_guard_check.py  ": " python _test/loc_guard_check.py                # r94 起**默认 enforce**（超限即 rc=1，进了电池就会红）。行数 ≤2000 / 函数长 ≤150（对标 opensoul `check:loc`，其 `--max 2000 --max-function 150` 已实测坐实）。**函数口径只取 `func` 块**：Java/JS 的类与 IIFE 模块包装是类型/模块容器，不计函数长（行数照常计入文件行数）；嵌套函数**会**被测量。面板打印被排除的类/模块数 + 既有更严约束（size_budget 字节预算、Core P0.8 函数 ≤50 行）。`--report-only` 只报不拦\n",
    "loc_guard_check.py --selftest": " python _test/loc_guard_check.py --selftest      # r94 判据桩：17 条（超限必报／未超限不误报／等值边界／两条阈值放大变异腿／零文件不产生结论且必判 UNVERIFIED／合成面超限非空／类 300 行与 IIFE 包装**不得**判函数超限而其内部 200 行函数必红／接线三腿：当前电池条目带 --enforce、摘掉后判否、只动一处不误伤）\n",
    "bench_rollup.py  ": " python _test/bench_rollup.py                   # r93 起提供两新增维度的只读汇总（只读、零网络、数字带来源）：①测试与可复现性（self 套件数／Java 测试类与 @Test 数／jacoco LINE≥0.90∧BRANCH≥0.90 ⇄ peers 同址尺 coverage_gate 等）②零构建成本-收益（前端构建链配置 0 个 ⇒ 零构建成立；平台函数依赖清单单列；首屏预算；CI workflow 文件数与 job 条数）。**r94 起输入/产物都不写死轮次号**：自动取最新 `benchmark-metrics-*.json` 与 `peer-quality-tooling-*.json`／`peer-repro-*.json`，产物名跟随输入轮次；stale 标记按台账内容判定（含旧 letta 行才标 stale，不再硬编码）\n",
    "bench_rollup.py --selftest": " python _test/bench_rollup.py --selftest         # r94 判据桩：5 条（缺源检出／合成样本出表／成本项未取数不得写成 0／job 计数不得把 job 内保留键算成 job／无 jobs 块时不得凭空数出 job）\n",
}

out, hit = [], 0
for ln in lines:
    done = False
    for key, new in NEW.items():
        if key in ln and ("loc_guard" in ln or "bench_rollup" in ln):
            out.append(new)
            hit += 1
            done = True
            break
    if not done:
        out.append(ln)
P.write_text("".join(out), encoding="utf-8")
print("替换 %d 行" % hit)
