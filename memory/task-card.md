# 任务卡 — 2026-09-24 对标分析与工程文档补齐轮

## 本轮目标
与 GitHub 同类优质开源项目（LobeChat / Open-LLM-VTuber / SillyTavern）七维度对标，产出结构化报告，并直接执行报告中**非破坏性高优先级改进**（纯新增文件 + README 增补，零运行时代码改动）。

## 验收判据
1. `交付物/对标分析报告-2026-09-24.md` 含：对比总览表 / 逐项差距 / 改进建议清单(高中低) / 实施路径
2. 新增 `.env.example`、`CONTRIBUTING.md`、`SECURITY.md`、`CHANGELOG.md`、`.github/workflows/ci.yml`、issue/PR 模板、README badge 化 + TOC + `README.en.md`
3. 红线不破：不改 `src/`、`deploy/`、`server/` 任何运行时代码；不碰 `demo-config.js`；不触碰上轮被 Mimosa 钩子拦截的 7 个暂存文件（提交用 pathspec 限定）
4. 提交后 push 并核对 SHA（R20 #20 四步基线）

## 备选方案与取舍
- A. 本轮连 SSE 流式输出一起做 —— **弃**：违反 J2「契约 1:1」验收判据红线，距 09-30 截止仅 6 天，波及前端渲染/双后端/18 个回归脚本，风险不对称。
- B. 只出报告不动手 —— **弃**：用户明示直接执行；且 badge/CI/贡献文档是评委可见的低成本高收益项。
- C. **选定**：报告 + 纯文档/CI 类执行，流式/PWA/移动端列为赛后 P1。

## to-do
① 报告 ② .env.example ③ CONTRIBUTING/SECURITY/CHANGELOG ④ CI workflow ⑤ issue/PR 模板 ⑥ README 增补 + 英文版 ⑦ 本地可跑项验证 ⑧ pathspec 提交 + push

## checkpoint / 回滚预案
全部为新增文件或 README 单文件改动；回滚 = `git revert` 本轮提交（pathspec 提交不含他人在制改动），或逐文件移入回收站（`handoff.py recycle`）。

## 决策记录
- SSE 流式、PWA、i18n、主题令牌化 → 登记为赛后 P1（详见报告 §4）

---

# 任务卡 · 对标轮第二轮（2026-09-24，QD 端自动执行轮）

> ⚠️ 诚实标注：本卡为**执行中补建**（17:40 前后），非动手前建立。根因 = 首轮行为惯性 + 用户「严禁询问、直接执行」的自动化指令压过了门禁检查点。违反致命纪律 #15 的"执行前必须有任务卡"，记为流程缺陷，下轮改序。

## 本轮目标
把首轮对标报告里被推到"赛后"的中高优先项**当场落地**，并为首轮未覆盖的「同体量垂类项目」补一层实测横向对账。

## 验收判据（全部要求当场跑出）
1. `_test/stream_contract.py` A/B/C 三判据 PASS，且 A 证明非流式契约未破
2. `_test/strategy_check.py` PASS + `--selftest` 报 FAIL（判据非恒真）
3. `_test/ux_guards_check.py` 逐项判定，零失败
4. 既有回归全绿：`browser_check` / `pixel_dual_check` / `lightshow_check` / `j2_chat_contract` / `j4_memory_check` / `j4_remote_down_check` / `voice_check` / `engine_consistency_check` / `emotion_eval`
5. `deploy_sync_check` 三类归零 + 零密钥红线复核
6. Java 构建 BUILD SUCCESS（JDK 17）

## 备选方案与取舍（≥2，实际取舍记录）
| 决策点 | 选了 | 否掉的 | 理由 |
|---|---|---|---|
| 流式端点形态 | 同端点 + `stream` 可选字段 | 新建 `/api/chat/stream` | 不破 AC-OBS-08；三处代理少一个端点（决策 #6） |
| 策略表载体 | `.js` 纯 JSON 字面量挂全局 | `.json` + fetch | 同步加载，避免把 `respond()` 全链变异步（决策 #7） |
| provider 适配 | env 嵌套占位符 + 别名 | 写 provider 注册表 | 上游本就 OpenAI 兼容，差异只有端点/模型名（决策 #8） |
| 长会话 | DOM 上界 + 配额展开 | 虚拟滚动 | 零依赖约束；>500 条的滚动锚定留给赛后（决策 #9） |
| 公网部署 | **不做**，登记为 P0 待一句话 | 直接 `wrangler pages deploy` | 评委可见的外发变更，超出"改码 + Git 备份"授权半径 |

## to-do / checkpoint
① 候选池 211 仓 + 14 仓深指标 ✅ → ② M1 三端流式 ✅（中途踩 `ResponseEntity<?>` 500 坑）→ ③ M2 策略表 + 判据 ✅ → ④ M3 provider 别名 ✅ → ⑤ M4/M5/M6 + `ux_guards_check` ✅（首跑 2 失败：展开即被裁回 + 判据误把既存 40 条上限当 bug）→ ⑥ M7 CI ✅（本机实跑抓到 workflow 自伤命中）→ ⑦ M8 ROADMAP/版本/标签 ✅ → ⑧ 文档与记忆回写 ✅ → ⑨ 全量复跑 + 提交推送 + CI 状态核对（见下）

## 回滚预案
- 每个可验证关卡一次提交（已按纪律 #20「每关一存」执行），回滚 = `git revert <sha>`，禁 `reset --hard`
- 代码与文档分簇提交；`deploy/` 副本随 `src/` 同提交（同步红线）
- 上游遗留的未提交改动（`交付物/提交包/*`、`memory/07*`、`_test/screenshots_resubmit.py`）属老大在途工作 → **未纳入本轮任何提交**，用 pathspec 提交隔离

## 新方向（P2，登记不执行）
- 流式中途打断（需 WebSocket 或取消语义）→ 决策 #6 重评触发条件
- `tick()` 每帧 CPU 侧遍历 2600 粒子 → GPU 侧/分帧着色 + 真机 FPS 实测
- 危机干预事件服务端留痕（只留时间戳+类别，不留原文）

---

# 任务卡 · 对标轮 r95（2026-10-04 起 / 2026-10-05 收口，自动化执行轮）

> ⚠️ 轮次跨天：r95 于 2026-10-04 04:0x 起了个头（`.ci/contract.json`、`bench_quality_gates.py`、
> `verdict_exit_parity_check.py`、G9 换 AST 尺、`j4_memory_check` 补退出码）后**中断，未提交、未写报告**；
> 2026-10-05 续接收口。台账/台面两处都按「r95 一轮」记，不拆成 r95a/r95b ——
> 拆轮次的代价是**同一批改动被两轮各记一半**，而这两半本来就互为前提。

## 本轮目标
把「CI 全绿契约」从**在位**变成**有牙**（r90 登记 5 轮未动的 P0），并补上「维护状态」维的
30 天提交率同址尺。**边界：零 `src/` 与零 `server/` 改动**（沿用 r93/r94 口径，
改动全部落在 `_test/`、`.ci/`、`docs/`、`README.md`、`交付物/`）。

## 验收判据（全部要求当场跑出）
1. `greencheck run --repo-dir .` 从 `UNKNOWN` 转 `GREEN`（rc=0）—— **本轮唯一的一票否决项**
2. `ci_contract_check.py` → `CI-CONTRACT-PASS`；`--selftest` 全绿
3. `peer_maintenance_probe.py` 两腿交叉验证，落 `交付物/对标数据/peer-maintenance-2026-10-05.json`
4. `BENCHMARK-METRICS-PASS` 16/16；G17 台账漂移 −4 → 0
5. `REPO-CONFIG-PASS` 17 项 / 18 判据号；`LOC-PASS`；`EOL-PARITY-PASS`；`SECRET-SCAN-PASS`
6. `DISCLAIMER-CLEAN` 49 份缺取证 0 处
7. 收口全量电池（116 → 120 套件）取最终绿回执

## 备选方案与取舍
| 决策点 | 选了 | 否掉的 | 理由 |
|---|---|---|---|
| 契约怎么生成 | **手写** blocking 清单 | 继续 `greencheck bootstrap` | bootstrap 实测 `checks=[]`（本仓门禁是自写电池，不是标准配置）⇒ 自动生成只能得到空契约 = 零保护还像成功了。07 P0 原文就是「禁造空契约；须手写」 |
| 契约里放不放全量电池 | **deferred + 写明承接面** | 放进 blocking（10.1s → 700s） | pre-push 预算 20s；放进去的后果是每条都被自动 defer，等于没列。本地便宜代理取其 4 条元判据 |
| 契约门放哪 | **同时进电池与契约 blocking 自身** | 只放电池 | 「契约是否入库」正是 greencheck/pre-push 能不能生效的前提 ⇒ 门必须站在门里面 |
| 30 天提交率怎么验 | **两腿交叉验证 + 印历史跨度** | 只取分页法一腿 | 分页法单腿曾静默塌成常数（14/16 失败而不影响分母）；self 历史仅 13 天，单腿会诱导写出「月更 314 次」 |
| 落后格（lint / vector / i18n / mutation） | **全部维持不执行**，但把**触发条件写死** | 各做一个 | 尺的语义窄（零构建）+ 架构级代价（决策 #1 重评触发条件）⇒ 排序依据已写进报告 §3 #7/#8，不是「以后再说」 |

## to-do
① 现状核验（在途 6 件 + 21 条 git 未入库面）✅
② 契约手写重做 ✅ ③ 契约结构门 ✅ ④ 30 天提交率尺 ✅
⑤ 权威 SNAP 重采 + G17 对账 ✅ ⑥ 报告落盘 ✅
⑦ 在途四件入库 ✅ ⑧ 收口电池 ⏳ ⑨ 台账回写 ⏳ ⑩ push + CI 回执 ⏳

## 回滚预案
- 判据层新增（`ci_contract_check.py` / `peer_maintenance_probe.py`）= 单文件 `git revert`；
- `.ci/contract.json` 若判据过敏，`git revert 5bd5bc3` 即回到「恒放行」旧态（**旧态是已知假绿，
  回滚它等于主动恢复一个假绿面，回滚前须在报告登记**）；
- 台账覆盖前已备份到 `交付物/对标数据/_superseded/`（旧 SNAP / 10-04 的 r95 残件）。
- `src/` 与 `server/` 本轮未动 ⇒ 演示期红线不受影响。

## 本轮新发现（两条比正产物更值钱）

1. **「门恒放行」有一整族，本轮是第三次撞上**：`j2_chat_contract`（r93）→ `j4_memory_check`（r94）
   → `pre-push + 未入库契约`（r95）。三次形态不同、根因同一条：**执行方按 rc 记账，
   而失败那一侧没被翻译成非零 rc**。立族的动作是 `verdict_exit_parity_check`（判据的判据）
   + `ci_contract_check`（契约的判据），两件都带自检与变异腿。
2. **★ 不是维护度的代理**（一手，同址尺）：`SillyTavern` ★34,083 / 30 天 9 次 vs
   `morettt/my-neuro` ★1,387 / 30 天 62 次。前 94 轮的「维护状态」维一直在用 ★，
   这一维读数此前**没有横向可比性**。

---

# 任务卡 · 对标轮 r93（2026-10-02，自动化执行轮）

## 本轮目标
八维对标（功能/架构/实现/性能/可扩展/维护/文档/场景）+ 落地四项改进：loc 门、两个新增维度量化、corpus 归档、peers 全量重采落工作区。执行边界＝含运行时改动（老大逐题确认），实际改动**全部落在判据层与文档层**，`src/` 与 `server/` 零改动。

## 验收判据（全部要求当场跑出）
1. `benchmark_metrics.py --cap-channel --doc-perf --quality-gates` rc=0，产物落 `交付物/对标数据/benchmark-metrics-r93.json`，日志落工作区（**禁落 %TEMP%**）
2. `loc_guard_check.py --selftest` PASS，且 report-only rc=0 / `--enforce` rc=1
3. `bench_rollup.py --selftest` PASS 且主流程 rc=0
4. `disclaimer_forensics_lint --all` 分母 46 = 归档前 46（覆盖面不缩）
5. `deliverable_inventory_check` 认搬卷 45 且未验 0
6. `repo_config_check` 17 项 0 红（含 G4 套件数、G16 脚本登记、G9 import-safe）
7. 收口全量电池 116 全绿

## 备选方案与取舍
| 决策点 | 选了 | 否掉的 | 理由 |
|---|---|---|---|
| 归档判据 vs 搬文件顺序 | **先扩判据双面分母，再搬** | 直接搬 | 直接搬会让 `--all` 分母归零 ⇒ 电池那条从 PASS 变 rc=2，CI 电池跟着红 |
| 归档目录名 | `交付物/_历史轮次-对标/` | 另造名 | `deliverable_inventory_check` 的搬卷 selftest 夹具已把该名字写死 |
| loc 门是否直接阻断 | report-only | 直接 enforce | 阈值 2000/150 比既有纪律**更松**，直接阻断＝用更松的尺卡已在位的纪律；先记读数 |
| corpus 是否连历史报告一起搬 | 搬（46 份） | 只出索引不搬 | 老大选定方向④；CHANGELOG 原「判定不搬」的前提是单目录 glob，扩面后前提已变，本轮改判并显式声明分母 46→46 |
| letta 换址 vs 加新仓 | 换址（分母仍 16） | 加 letta-code 变 17 仓 | 换址不换人口，横向分母稳定 |

## to-do
① 全通道重采落工作区 ✅ ② loc 门 ✅ ③ rollup 两维度 ✅ ④ corpus 归档 + 合并索引 ✅ ⑤ r93 报告 ✅ ⑥ 连带修 G4/G16/G9 ✅ ⑦ 收口三绿 ⏳ ⑧ 台账回写 + pathspec 提交 + CI 回执

## 回滚预案
- 判据层改动（4 个 .py + docs）＝单文件可 revert；corpus 搬卷 `git revert` 即可整批回退（判据认 R100 搬卷，回退后分母回到单根 46）。
- `src/` 与 `server/` 本轮未动 ⇒ 演示期红线不受影响。

## 本轮新发现（一手，值得单列）
`j2_chat_contract.py` 印 `J2-CONTRACT-FAIL` 却 `exit 0`，电池长期记 PASS —— **判据主动报绿**。修复时又踩 G9（顶层 `sys.exit` 破坏 import-safe），当场被 `repo_config_check` 抓红，改成 `main() + __main__` 守卫。教训：「补一行退出码」在本仓要连带守住 import-safe 与文档登记两条线。

---

# 任务卡 · 表达优化专项 r117（2026-10-12，动态工作流执行轮）

## 本轮目标
为心屿构建心理疏导「表达语料库」（文言古句 / 名家名句 / 网络热句 / 哲学思辨），
经动态工作流（dwf 引擎）4 研究员并行搜集+考据 → 审读核对 → 构建器编译产品数据件 →
chat-agent.js 按情绪+话题注入候选（每轮给候选）→ 引用规则写死（不契合不引 / 每轮≤1 句）→
全自动验收（脚本判据 + LLM 评委盲评）→ 双线部署。

## 验收判据（全部要求当场跑出）
1. `_test/wit_quotes_build.py --check` → WIT-QUOTES-BUILD-PASS（条目数 ≥100，E 级构建期排除并计数）
2. `_test/quote_wiring_check.py` PASS（每轮候选在 / 情绪匹配 / 预算内 / 离线不受影响 / 危机轮零注入）
3. `_test/quote_eval.py` 全自动盲评：新版三维均分 ≥ 旧版 且 引用生硬率 ≤ 阈值（报告落 `交付物/表达语料库/验收报告.md`）
4. 回归全绿：`browser_check` / `context_budget_check` / `size_budget_check` / `deploy_sync_check`
5. 双线部署 + `live_sync_check` + `public_check` 回执
6. 核心能力复算器 `CORE-CAP-BASELINE-PASS`（无回退）

## 备选方案与取舍（老大逐项拍板 + 技术项）
| 决策点 | 选了 | 否掉的 | 理由 |
|---|---|---|---|
| 落地形态 | **全量工程**（老大选 A） | 轻量快跑 / 只改提示词 | 与心理学知识库同规格做透 |
| 引用机制 | **每轮给候选**（老大选） | 契合才引 / 限场景 | 覆盖面大；防堆砌由引用规则硬约束（≤1 句 / 不契合不引）兜住 |
| 争议素材 | **辩证收录+来源严检**（老大选） | 从严剔除 / 逐条过目 | 误传不冒充（如"鲁迅"句如实标存疑）；讽刺梗按正面诠释入库+用法禁忌 |
| 验收 | **全自动**（老大选） | 机器+人工盲测 / 人工为主 | LLM 评委盲评 + 脚本判据，汇总报告供审查，样本可随时抽验 |
| 训练路径 | **素材库+注入**（提示词工程） | 真微调 | 在线链路是 DeepSeek API 权重不可得；ml/ 分类模型与表达无关（86.6% 未过门） |

## to-do
① .dwf 接入（doctor 12/12 全绿）✅ ② 语料库 README + 5 份任务书 ③ 4 研究员 dwf 派发+回灌
④ 审读核对 ⑤ 构建器+数据件 ⑥ chat-agent 注入 + 引用规则 ⑦ 判据+全自动盲评 ⑧ 部署双线 ⑨ 收口

## checkpoint / 回滚预案
- 产物以**新增文件**为主（`交付物/表达语料库/`、`_test/wit_quotes_build.py` 等）+ `src/` 三件小改
  （chat-agent.js / emotion-strategy.js / index.html + sw.js）；`deploy/xinyu/` 按同步红线随行；
- 回滚 = `git revert` 本轮 pathspec 提交；src 改动逐文件可 revert；语料库目录整体走回收站；
- `.dwf/`（config/owns）为引擎接入新增，不触碰既有判据面；子代理 leases/briefs 限于 `memory/sessions/`。

## 决策记录
- 执行载体 = **dwf 引擎**（动态工作流）：4 研究员 `subagent:general` broker 模式，主控 spawn + `submit` 回灌（sha256 磁盘验收）
- 候选预算：SYSTEM 1600 字符上限内，quote 块 ≤220 字符与 KB 块共享余量（不足则本轮让位，绝不挤记忆/概要段）

---

# 任务卡 · 心理学知识库第4轮+存量校准 r123（2026-10-12，多代理并行研读轮）

## 本轮目标
完成心理学知识库第 4 轮：新建篇章 13-16（13 焦虑与担忧 / 14 哀伤与丧失 / 15 睡眠运动与情绪 / 16 弹性与创伤知情），每篇 5-6 条共约 22 条，A-E 五级定级+可核对来源；同时做存量 74 条校准（定级/来源可访问性/引用完整/索引一致/跨卡题录五维复核，问题卡按 README §3 追加「- 更正：」行不静默改写）；重建 psych-kb.js 使 `psych_kb_build --check` 由 FAIL 转 PASS；判据全绿后双线部署（老大 Q4-b）。

## 验收判据（全部当场跑出）
1. 4 篇章文件条目卡 100% 遵 README §3 行式；编号零撞号（grep 实证）；每篇 5-6 条
2. `python _test/psych_kb_build.py --check` → PASS（源产物一致，构建标签 v1.3 收口）
3. `python _test/deploy_sync_check.py` MISSING/DIFF/EXTRA 三类归零（src↔deploy 双副本）
4. `size_budget_check` / `context_budget_check` PASS（KB 注入 ≤1600 字符双向管住）
5. 整跑电池 `python _test/run_all_suites.py --exclude-llm` 全绿（部署前硬门槛）
6. 双线部署回执：DEPLOY-SYNC-PASS + LIVE-SYNC-PASS + PUBLIC-ONLINE-ALL-PASS
7. 核心能力棘轮 `CORE-CAP-BASELINE-PASS`（语意 85 条/100%、危机 6-6 无回退）

## 负面测试用例
1. 无来源/E 级条目混入 → 构建期必须排除并计数（excludedE），禁作事实依据
2. 编号撞号（AX/GR/SL/RS 与既有域混号）→ 入库前 grep 篇章+索引双确认
3. 编造来源（URL 打不开/题录不实）→ 核对轮逐条核验，不通即降级或剔除
4. D 级条目只写一方 → 打回，必须两方并陈
5. 临床/治疗类论断越界 → 须带「不构成治疗建议」边界句
6. psych-kb.js 增体积超 size_budget → 先报实测值再按惯例调线，禁静默抬限
7. 并发会话（对标/voice 在途）→ git 提交只 pathspec 本轮文件，提交前 numstat 逐行核归属

## 备选方案与取舍（老大逐题拍板）
| 决策点 | 选了 | 否掉的 | 理由 |
|---|---|---|---|
| 本轮范围 | 第4轮+存量校准一起做 | 只做第4轮 / 只修工程面 | 老大 Q1 选 B |
| 规模 | 每篇 5-6 条共约 22 条 | 3-4 条快跑 / 8 条+深做 | 与前轮同规格 |
| 执行方式 | 多代理并行（4 研究员+2 校准员，主进程入库） | 单人顺序 / 先 1 篇试点 | 同 r114/r116 模式 |
| 发布 | 判据绿即上线双线（Pages+CloudBase） | 只提交不上线 / 先交草稿 | 老大 Q4 选 b，r110 立规惯例 |
| 取材 | 库现行红线（Europe PMC REST/OpenAlex/Crossref+出版社官网） | 只国内源 / 自定义清单 | README §7 红线 |

## To-Do
① 门禁+G8+任务卡 ✅ ② 6 子代理并行研读/校准 ⏳ ③ 主进程入库+索引更新 ④ 规范核对+独立审读整改 ⑤ 重建 psych-kb.js+同步 deploy ⑥ 判据全跑+整跑电池 ⑦ CHANGELOG r123+白名单提交 ⑧ 双线部署+在线回执 ⑨ savepoint+经验反哺

## Checkpoint / 回滚预案
- 每完成一篇章入库即一次 pathspec 提交（仅 交付物/心理学知识库/），回滚 = `git revert <sha>`，禁 reset --hard
- psych-kb.js 为构建器产物，回滚 = revert 源卡后重跑构建器，数据件禁手改
- 部署回滚锚 = 上一版 Pages 部署 ID（部署时记录）
- 并行会话在途改动不纳入本轮任何提交；若电池因他人在途件判红 ⇒ 暂停发布、只本地提交并报老大

## 决策记录
- 存量校准拆 2 名校准员（篇章 01-06 / 07-12），问题清单主进程统一处置，逐条落更正行
- 研究员不直接落盘，草稿回传主进程入库（格式/编号纪律集中把控）
- 保持 E=0 目标：查不到来源就不入库，缺口写进索引变更记录
- 篇章按体裁分 4 篇：01 文言与古诗词 / 02 名家名句 / 03 网络热句与流行文化 / 04 哲学思辨


# 任务卡 · 语音通话收口 r128（2026-10-12，动态工作流执行轮）

## 本轮目标
按老大五项要求收口端到端语音通话模块（r116/r118 已建骨架，工作树有语音面在途改动）：
①多音色+可配置接口+通话中动态切换；②纯音频链路与视频/摄像头完全解耦；③完整理解语义前提下的
低延迟首响（收句×流式出声流水线）；④采集/降噪/端点检测/语义理解/合成/实时播放全链路+状态展示/
静音/挂断；⑤30 分钟量级连续稳定（不卡顿/不断连/无回声）。执行形态=独立复核+补齐差距+判据全绿
+src→deploy 同步，禁止推倒重写。

## 验收判据（全部当场跑出）
1. `python _test/voice_call_check.py <url>` → VOICECALL-PASS（C1-C15 全绿）
2. `python _test/voice_call_soak_check.py <url>` → SOAK-PASS（S1-S8 全绿，含 120 轮等效长稳）
3. `python _test/browser_check.py <url>` → ALL-ASSERT-PASS（通话面不破主链路）
4. `python _test/deploy_sync_check.py` → MISSING/DIFF/EXTRA 三类归零
5. `python _test/size_budget_check.py` → PASS（改动不顶超预算）
6. 五项需求逐项复核表（covered/partial/gap+证据）落工作流报告；缺口按 severity 处置

## 备选方案与取舍
| 决策点 | 选了 | 否掉的 | 理由 |
|---|---|---|---|
| 执行形态 | 复核+补齐+收口 | 推倒重写 / 只跑判据不动 | 既有产物前置探测：r116/r118 已落地，重写=高风险低收益 |
| 执行载体 | ZCode CreateWorkflow（动态工作流） | wflow TOML 引擎 | 老大本轮 /workflow 指令在本端映射为 CreateWorkflow 强制 |
| 真机 30min | 判据层 120 轮快放+人测登记 | 强行桩 30 分钟墙钟 | soak 头已声明：快放只压墙钟、结构 1:1，真麦实录归人测 |

## to-do
① 门禁+G8+任务卡 ✅ ② 摸底跑判据（C/S/browser/sync/budget）③ 五项需求独立复核
④ 按缺口补齐（先根因，禁凑绿） ⑤ 复跑收口全绿 ⑥ 报告落盘 ⑦ pathspec 提交+savepoint

## checkpoint / 回滚预案
- 语音面在途改动+本轮新增 = pathspec 白名单提交（src/js/voice-call.js、src/js/app.js、
  deploy 同步副本、_test/voice_call_soak_check.py 等），回滚=git revert <sha>，禁 reset --hard
- 并行轮（对标 r126、psych r123）在途文件零触碰；提交前 numstat 逐行核归属
- HEAD 漂移（≠8bcce16）即停手重验并发态势

## 决策记录
- 判据红处置顺序固定：先根因（src 缺陷修 src / 判据缺陷修判据+变异证据），禁改判据凑绿（R263）
- 本轮不推送：整跑电池（run_all_suites --exclude-llm）是推送前硬门槛，留给推送轮执行

---

# 任务卡 · 语音回声误触发收口（WF-voice-echo-guard / wb-echo-L0，2026-10-13）

## 本轮目标
堵「TTS 念白被麦克风回读、被 ASR 当用户输入送进共情链路」的误触发管道（直连先例：GM lessons.part567）。
改法：`src/js/voice-call.js` 收句面新增准入闸（isEchoFuzzy 模糊回声判 + 尾音窗 TAIL_MS）；bargeIn 念白移入 recentSpoken；commit 二次校验。配套：C16 判据腿（先验红后验绿）、deploy 同步、预算行按实测重登记。

## 验收判据（全部当场跑出）
1. `node --check src/js/voice-call.js` PASS（语法）
2. `python _test/voice_call_check.py http://127.0.0.1:8123`：C16 旧码先验红 → 新码全绿（VOICECALL-PASS）
3. `python _test/voice_call_soak_check.py http://127.0.0.1:8123`：SOAK-PASS（S1 打断面零回归）
4. `python _test/deploy_sync_check.py`：三类归零（本次范围）
5. `python _test/size_budget_check.py`：voice-call.js 按实测+5% 重登记后 OK（余 3 项 OVER 为并行轮在途，非本轮）
6. `python _test/browser_check.py http://127.0.0.1:8123`：主链路不回退

## 备选方案与取舍
| 决策点 | 选了 | 否掉的 | 理由 |
|---|---|---|---|
| 修法 | 准入过滤（onresult 前置丢弃）+ 尾音窗 | 仅半双工 pauseRec 兜底 | 保全双工可打断；半双工也治不了 listening 态残留 |
| 相似度 | 精确互含 + 2-gram Dice 滑窗（阈值 0.6） | 声纹 / 自建 AEC | 零依赖当日落地；后两者归 P2 架构级 |
| 落点 | voice-call.js 原文件 | 新建独立脚本 | 依赖闭包私有态（speakingBuf/recentSpoken） |

## to-do
① G8 块+precheck ✅ ② src 改码 ✅ ③ C16 红→绿 ✅（16/16） ④ deploy 同步 ✅ ⑤ 复跑+预算调线 ✅（27,672） ⑥ CHANGELOG+pathspec 提交 ✅ `3d81d72`（未推送：电池归推送轮）

## checkpoint / 回滚预案
- 回滚=`git revert <sha>`（pathspec 白名单：src/js/voice-call.js、deploy 副本、_test/voice_call_check.py、_test/size_budget_check.py、CHANGELOG.md、memory/2026-10-13-wb-echo-L0.md）
- 并行会话在途文件零触碰；提交前 numstat 逐行核归属；本轮不推送（整跑电池归推送轮）

## 决策记录
- 标识 wb-echo-L0（r163 号已被判据线占用，避撞号）
- 预算调线随提交披露（非静默抬限，实测值入 CHANGELOG）

---

# 任务卡 · face-diag 全案复核续期（r166，2026-10-13）

## 本轮目标
对「面部表情识别准确率」战役做全案复核（原始需求模板复跑）：以磁盘/Git/判据电池实测重建现状，
产出六段对标文档（诊断复核/三阶段/执行台账/验证与基线/质量标准/风险预案），
落 `交付物/表情识别准确率优化方案-2026-10-13-全案复核.md`；不重做诊断、不碰 src/、不代同步并行在途件。

## 验收判据（全部当场跑出）
1. 判据电池五件套实跑留档：core rc=0（N1 105/99%、N2 31/31、F1 rc=0）｜lowintensity rc=0（96.7%、1/50、40.0%）｜F11 26/26｜replay 有把握 8/8
2. deploy_sync：face 面归零维持；唯一 DIFF=css/voice-call.css（并行在途，如实披露不代同步）
3. 复核文档含六段 + 三维根因现状台账（含新发现 A8 fear@0.12 / A9 replay 读数不一致）
4. 双门禁：dag_precheck [GATE:dag-pass] + upgrade_footer_gate [GATE:evolution-pass]

## 备选方案与取舍
| 决策点 | 选了 | 否掉的 | 理由 |
|---|---|---|---|
| 形态 | 全案复核+续期（新文档） | 重写诊断 / 原地改 10-12 文档 | 既有产物前置探测（Step 0.55 §6.5）：诊断已完成，10-12 为历史执行版留档不动 |
| 口径 | 按项目架构映射（表情识别/标定样本/判据阈值） | 按人脸识别模板字面硬套 | 项目无自训练模型，硬套会建在错误前提上（r124 同口径） |
| 数值 | r124 定版值填实占位符（95% / 100ms·500ms） | 重新拍板 | 授权口径已在册，复核轮不重开决策 |

## to-do
① 现状核验（电池+git）✅ ② GM 锚点（G8+footer+双门禁）✅ ③ 复核文档落盘 ✅
④ 任务卡/日志/回执 ⑤ pathspec 提交 ⑥ volume 快照 + savepoint

## checkpoint / 回滚预案
- 回滚 = git revert <本轮 sha>（pathspec 白名单：复核文档 + 回执 + 10-12 文档进度行）
- 并行会话在途件零触碰；提交前 numstat 逐行核归属；本轮不推送（整跑电池归推送轮）

## 决策记录
- 模板 ${target_accuracy}/${max_latency} 填实 = r124 定版：有把握帧 top-1 ≥95% / 单帧 p95 ≤100ms 且端到端 ≤500ms
- 复核新发现：fear@0.12 与 replay 2 张读数不一致 → 均登记 M1 复核项（不改判据不掩盖）
