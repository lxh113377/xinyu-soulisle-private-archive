# 07 分卷 54 — 对标轮 r53（上下文窗口预算与截断损失）条目全文

> 迁卷动因：07 主壳 4,077 B / 上限 4,096 B，r53 要加一行只能同时把 r52 那条瘦身。
> 完整报告：`交付物/对标分析报告-2026-09-27-r53.md`。

## r53 上下文窗口预算与截断损失面（已完成，→ 电池 85）

**换面取证**：`grep -icE "token 预算|上下文预算" 交付物/对标分析报告-*.md` = 十四份全 0；
`HISTORY_MAX`/`滚动摘要` 仅 r52 出现且写作**未做**，留话「有数之后再决定摘要腿」。

**一手实测（动手前）**：`chat-agent.js:11` `HISTORY_MAX=10`、第 26 行本机历史封顶 40 条、
第 159 行 `history.slice(-HISTORY_MAX)` 是历史进 messages 的**唯一入口** ⇒ 聊到第 6 轮，
前面所有轮次对模型永久不可见。修前判据实测：**14 轮里 16 条被截断且零补偿**（覆盖率 10/26=0.385）。

**落地**
- `_test/context_budget_check.py`（+2 套件，桩 10 例）：拦 `/api/chat` 读 `request.post_data` 反解 messages；
  截断条数由**判据自己**用「发该轮前 history 条数 − 窗口」算，不采信产品报的数（防 `measure()` 自比）。
  X1 覆盖率棘轮（下限 0.30）／X2 截断必须由概要注意送达且条数对账／X3 system 段 ≤1,600 字符／
  X4 零截断不得有注入（反向腿）／X5 概要内不得出现用户原话／X6 异常 0。
  修前以 `X2 截断了 16 条历史，但 system 里没有「早前对话概要」段` **真判红**。
- `summaryOfDropped()` + `droppedCount()`：滑出窗口的历史压成一行结构化摘要（条数 + 情绪分布 top3 +
  危机次数），**只扫情绪标签、不抄原话**；界面标「早前 N 条已概要」。
- `size_budget`：chat-agent.js 先压注释（14,747→14,573，省 174B）再登记 13,024→15,302，理由与 X3 上限同写。

**peers 侧（同一把尺，本轮换到逐类读数）** ✅
`memory 10/16｜summary 3/16（lobehub/leemo/opensoul）｜ctx 窗口管理 3/16｜retrieval 3/16`；
**正向引用边 4/16**（OLV、my-neuro、sapphire、leemo）。不给横向百分比：其余是 `none-in-sample(n=6)`
（我的抽样上界）或 `NA`（取数失败），都**不构成**"该仓没做"。

⚠️ **本轮改过一次取数面，后果如实登记**：结构探针原先不排除测试/夹具目录，
而我自己新写的 `_test/context_budget_check.py`（词元 context+budget）被算成"本仓有上下文窗口管理器"
⇒ self 从真实的 1/4 **虚高**到 2/4。加排除后 self 与 peers 同尺变化三处：`summary 4→3`、
`引用边 yes 2→4`（排除测试件后每家抽到的装配件更多是产品件）、`chibi 边 none-in-sample(n=6)→NA(n=0)`。
方向与自利相反（self 读数变差），配**对偶**用例防"一删了之"（`src/context/context_budget.ts` 必须照常命中），桩 9→11。
⇒ 结论口径：本项目**结构面仍在 1/4**（摘要是函数级、藏在 chat-agent.js 里，文件粒度探针取不到），
本轮只主张**行为面 X2 已过**。"我改了判据口径"和"我进了那一格"必须分开写。

**未做（不写成"已建议即完成"）**
- token 预算器（按 token 而非条数滑窗）：需依赖或自估口径，先量三条注入段各占多少 token 再立尺。
- retrieval / RAG：决策 #1 重评触发条件未到；届时走 Python 侧服务 + Java 调用。
- 真机复跑 r51/r52/r53 三条运行时判据：连续三轮挂账。
- 后端分类腿（`/api/emotion` + Java `LlmProxy` 60 s）的挂起注入仍不在取数面内（r52 §6-2 原样挂着）。

⚠️ **环境（不归本会话修）**：`A-project-handoff/scripts/handoff_lib/volumegov.py:3456` SyntaxError
⇒ `handoff.py` 跑不动、`savepoint` 链断。该文件 mtime=16:53（当分钟）、`D:\global_skills` 内另有 3 个
在途改动 ⇒ 并行会话正在写，不代修。本轮手工完成 savepoint 等价校验（07 P0 非空 / P-1 在册 /
07 全卷 ≤4,096 B / 文本 LF），r54 首件事=复跑 `handoff.py savepoint`。
