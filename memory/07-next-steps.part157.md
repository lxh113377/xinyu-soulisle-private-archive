# 07 分卷 — r133 表达优化专项收口 · 本轮做了什么

（起点核验与四条要求的对账表在 `part158.md` 开头）

## 本轮做的三件事（归因复跑与遗留见 part158）

### ① verifyCitations 接线（r132 的真缺陷，已修）
**先纠正一个误判**：本轮开工时我判定「verifyCitations 未实现」，依据是 grep 命中两行都在注释里。**这是错的** ——
`chat-agent.js:196-214` 有完整实现（CITE_RE + 三结局 + checked/matched/unmatched）。
真缺口是**零调用点**：r132 建了函数没接线，输出面等于无核对。

修法（`chat-agent.js` onlineReply）：`llmFetch` 之后调 `verifyCitations(raw, sys.kbUsed)`，非流式改写回复，
**流式走原文只回计数**（流式已逐字吐给用户，改写会让屏幕文字与内存不一致）；返回 `citeApplied` 把口径差异显式化。
同步加引用消费遥测 `citeChecked/citeMatched/citeUnmatched`（降级/离线恒 0，口径同 memory/dropped）。

**判据** `_test/quote_wiring_r133_check.py`：A1-A5 接线腿 + B1-B5 语料库侧消费面，10/10 PASS；
`--selftest` 把零调用点真注入回产品面，A2/A3 转红。
⚠️ 自证必须走**二进制**读写：文本模式把 `\n` 翻成 `\r\n`，还原校验逐字节对不上（本仓排障手册已登记同族）。

**退役的重复件**：`_test/quote_citation_check.py`（本轮自造）—— verifyCitations 三结局已由
`kb_citation_check.py` C1-C7 全覆盖且**已在电池**，另造一套不同契约（剥离 vs 标注）= 第二把尺。
已走回收站（id `20261012-212726-f1bd5e`），git `f5f0c21` 可回滚。
一手里途：它一度是「已入库却电池/CI 两头都不跑的孤儿判据」，被 G16 亲自抓出。

### ② 语料库构建器接线（存量缺口，已修）
`wit_quotes_build.py` 实测**已有** `--selftest`（15 腿全过），缺的只是接线（`run_all_suites.py:160` 的旧注释
已过期）。本轮补 `--check` + `--selftest` 入电池，理由照抄 psych_kb 那次「漂移活 3 轮零告警」的实证。

### ③ 预算上限重登记（存量超限，已查根因）
`size_budget_check` 报 `chat-agent.js 25,166 / 25,451`。**根因不是本轮**：r132 上调上限时记的「实测 24,239」是错的
—— 该数取自 r132 自己改动之前，而同窗口 face/voice 面又往该文件追加代码。实测：f9c7ee6 面 = 21,177 B；
**r133 动手前的 HEAD 面 = 25,706 B** ⇒ 存量已超 255 B，本轮改动只 +9 B。按「先报实测再调线、禁静默抬限」
重登记为 27,000（实测 +5%）。

**遗留与一手教训见 `part158.md`**（归因复跑方向不稳、规则文案未动的理由、本轮两次同族误判的根因）。

