# docs/ — 工程文档索引

> 与根目录文档的分工：`README.md` 面向使用者（能力/快速开始），`ROADMAP.md`/`CHANGELOG.md` 面向节奏与版本，
> `memory/` 面向 **AI 会话交接**（9 个结构化文件 + 分卷）。本目录放**可被工具消费的工程规格**。

| 文件 | 内容 | 谁在用（机器强制） |
|---|---|---|
| [`openapi.yaml`](openapi.yaml) | 服务端 11 条接口的**唯一机器可读契约**（请求/响应 schema、错误码、SSE 语义） | `_test/api_contract_check.py`：C1 不缺文档 / C2 不虚文档（幽灵路径）/ C3 前端不得偷调 / C4 运行态状态码与必需键一致 / C6 覆盖度精确对账 / C5 自证判据非恒真。已入全量电池与 CI `java-build` |
| [`API.md`](API.md) | 人读 API 手册（curl 示例、字段、错误码、三层 memory 开关） | `_test/api_contract_check.py` C7（r89 新增）：yaml 每条路径必须在手册出现 / 手册不得虚报接口 / 手册声明的路径计数必须等于实值 |
| [`EXTENSIONS.md`](EXTENSIONS.md) | 扩展手册：词表 SSOT、共情策略、LLM 上游切换、记忆 provider、部署目标、第三方集成清单 | 人工维护；接口面变动由 C7 与 `_test/engine_consistency_check.py` 兜住，本目录由 `_test/repo_config_check.py` G19 盯「在不在索引里」 |
| [`PERF-BASELINE.md`](PERF-BASELINE.md) | 性能基线口径与预算表（p95 / 吞吐 / 四目标预算），把"自证"变成可引用的数 | `_test/perf_baseline_check.py`（同机棘轮，超限即红） |
| [`tutorial-01-offline-demo.md`](tutorial-01-offline-demo.md) | 教程 01：离线演示——三条降级路（WebGL／在线 LLM／服务端记忆）、零密钥三步起步、单变量对照为什么有效、三个"看起来坏了" | 存在性由 `_test/peer_docs_probe.py` 计入本仓教程位（**按文件名判**，故命名带 `tutorial-`）；引用的脚本路径须实测存在，索引一致性由 G19 双向对账 |
| [`tutorial-02-crisis-referral.md`](tutorial-02-crisis-referral.md) | 教程 02：危机转介——优先级为什么在调模型之前、转介落点、**危机词表 ⇄ SafetyGuard 高危词表不得互相冒充**（「跳楼」实测只在后者） | 断言由 `python _test/browser_check.py` 与 `mvn -B -f server/pom.xml test` 复算；条数一律现读不写死 |
| [`tutorial-03-memory-switches.md`](tutorial-03-memory-switches.md) | 教程 03：记忆三层开关——代码层 `isRemote()`／本地演示 `remote: true`／公网层刻意不开，以及熔断为什么必须存在 | 复算 `_test/j4_memory_check.py` + `GET /api/memory/stats`；对外表述红线见 `memory/AGENTS.md` 决策 #3 |
| [`tutorial-04-running-the-checks.md`](tutorial-04-running-the-checks.md) | 教程 04：跑判据——三态退出码（没量到 ≠ 达标）、改完至少跑哪四条、G4/G8/G12/G16/G19 各咬什么、反例腿的三种形态、Windows 三个执行坑 | 本仓自述面：套件数一律 `run_all_suites.py --list` 现读，README 那句由 `_test/suite_count_sync.py --apply` 对齐（不手抄） |
| [`quality-gates.md`](quality-gates.md) | 判据体系明细：每条套件的口径 + 复算命令（**条数一律从 `run_all_suites.py` 的 SUITES 现读，本文件不抄数**） | `_test/repo_config_check.py` G16：电池脚本 ⇄ 本文档双向对账（漏登/幽灵登都红） |
| [`QUICKSTART.md`](QUICKSTART.md) | 三步上手：静态页 / fat jar / 容器，每条路的「起来了」判据、给密钥的三种落点、十分钟自证清单与起不来的排查顺序 | 人工维护；本文的存在性由 `_test/peer_docs_probe.py` 计入本仓文档四类位（教程位），命令真伪随 `docs/quality-gates.md` 与 `_test/repo_config_check.py` G19 一起对账 |
| [`data-and-privacy.md`](data-and-privacy.md) | 数据与隐私面：本地存储什么、谁能清除、危机转介的边界 | `_test/data_rights_check.py`（真点击清除 + 落库回执） |
| [`THIRD-PARTY-NOTICES.md`](THIRD-PARTY-NOTICES.md) | 第三方授权边界（three=MIT、GSAP=GreenSock 标准许可 **非 MIT**、axe-core=MPL-2.0） | `_test/repo_config_check.py` G6+G7：分母从 `_test/vendor-manifest.json` 现读，逐文件带条款表行 |

## 为什么放在这里（一条诚实记录）

对标实测 16 个参照仓里只有 **1 家**存在机器可读 API 规范（`api_spec=1/16`，见
`../交付物/对标数据/benchmark-metrics.json`），所以这份契约**不是"被同类项目甩开"的对标差距**，
而是本项目自身的**契约分散**问题：`/api/chat` 的形状此前同时写在
`_test/j2_chat_contract.py`、`src/js/chat-agent.js` 的常量、`deploy/jar/README-部署.md` 三处，
改一端忘两端全靠人记。收敛成单一声明源并加守卫，属于自我登记的可维护性改进 —— 报告里也照此表述，
不冒充竞品压力（对标轮 r21，2026-09-25）。

## 改接口时的正确顺序

1. 先改 `openapi.yaml`（含 `x-live-check` 标注）→ 2. 跑 `python _test/api_contract_check.py`（应因"代码缺实现"报红）
   → 3. 改控制器/前端 → 4. 同步 `API.md`（C7 会因"手册缺这条 / 计数过期"报红，r89 起这条不再靠人记）
   → 5. `--selftest` 确认判据仍能抓红 → 6. 跑全量电池 `python _test/run_all_suites.py`。

> 新增一份 `docs/*.md` 时：必须同时进上面的索引表，否则 `_test/repo_config_check.py` G19 判红
> （动因与口径见该脚本 G19 行；「写了但索引里没有」= 对读者不存在）。
