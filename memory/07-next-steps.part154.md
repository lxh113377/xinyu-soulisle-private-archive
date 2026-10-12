# 07-next-steps.part154.md

<!-- 本卷为 07-next-steps.part150.md 的延续 -->

## 收尾推荐（带稳定 id 与可复算前提）

- [x] 🟡 **[推荐:R127-06｜agent 自动｜已落 卷152]** **第 5 维三项可裁决选项清单**：向量长记忆（引 r88 不立项判定 + 触发现读未命中）／
      i18n（代价**首测**：128 件套件里 92 件、454 行中文串参与判定）／插件协议（池内**无分母**，对手那 7/16 是记忆不是插件市场）。
      三案均附「最小可逆试验 + 停手条件」，决策权在老大。全文 `07-next-steps.part152.md`
- [x] 🔴 **[推荐:R127-07｜agent 自动｜本轮已落]** **质量门尺三处漏检修复**（核验 S7 候选时自证伪衍生，非原计划）：
      `bench_quality_gates.py` ① 阈值正则改跨行 `[\s\S]{0,60}?` 并补 `branches`（vitest 换行写法）
      ② 候选取样改**深度优先** `qg_pick_files`（根级配置不再被深路径挤出取数面）
      ③ **部分候选未读到 ⇒ 记未验，不折成 False**（Unavailable is not zero）；
      `bench_eight_dims_check.py` 第 3 维格改由同一 run 的 `quality_gate_channel` 现算（原为硬编码「均 0/16」）。
      读数：`coverage_gate 0/16（未验0）` → **`1/15（未验1）例：NJX-njx/opensoul`**（对手真有覆盖率门：
      根级 `vitest.config.ts` thresholds lines70/branches55 ＋ ci.yml 内 iOS 43% 内联门）。
      ⚠️ 同族第三次「手抄文字与数据脱节」（前两处＝「r126 首采」标签、「本格改前抄台账的 152」注释）。
      **同日第二条腿（S9，精读 Open-LLM-VTuber 衍生）**：`benchmark_metrics.py::vector_memory` 只认
      `vector/embedding/独立 rag`，认不出 mem0/letta 这类产品名后端 ⇒ 全池 **7/16 → 9/16**（差距比已发布更大）。
      修法＝产品名按**词元边界**纳入（有意不收 `chroma`：`chroma.min.js` 是配色库），配 3 真阳 + 3 假阳反例腿。
- [x] 🟡 **[推荐:R127-11｜agent 自动｜本轮已落]** **能力面复核（验证性负结论，零改动）**：16 仓真树 × 10 组写法变体
      （`Dockerfile.*`/`compose.{yml,yaml}`/`devcontainer`/`dependabot.yaml`/`renovate.json5`/`serviceWorker` 驼峰/
      `site.webmanifest`/`puppeteer·selenium`/`stream.ts`/mutation 工具名族）⇒ i18n 扩面**零漏检**、mutation 变体**零命中**；
      两处疑似判为**不构成假阴**（文档站资产 / 全树无 sse 锚）⇒ **不改规则**（不拿模糊词换假阳）。
      方法论：与 S8/S9 同源——「对手都没有 X」必须拿真树证伪过一次；负结论要**声明取数面**才配写进报告。
- [x] 🟡 **[推荐:R127-12｜agent 自动｜已落 `9315ccf`，收口详情与两处衍生尺伤见 卷155]** **记忆探针的 retrieval 轴漏检**：`peer-memory-2026-10-12.json` 里
      Open-LLM-VTuber 的 `retrieval: []`（空），而它同目录有 `mem0_llm.py`/`letta_agent.py` ⇒ 该轴与 `vector_memory`
      同病（只认通用词）。**高层读数未受影响**（该仓经 memory/assembly 轴已计入 usable），故低优先；
      修法＝复用 S9 同一份产品名词元表（不另立第二把尺）+ 重采该族。
