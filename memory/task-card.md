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

