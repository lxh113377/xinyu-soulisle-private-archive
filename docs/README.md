# docs/ — 工程文档索引

> 与根目录文档的分工：`README.md` 面向使用者（能力/快速开始），`ROADMAP.md`/`CHANGELOG.md` 面向节奏与版本，
> `memory/` 面向 **AI 会话交接**（9 个结构化文件 + 分卷）。本目录放**可被工具消费的工程规格**。

| 文件 | 内容 | 谁在用（机器强制） |
|---|---|---|
| [`openapi.yaml`](openapi.yaml) | 服务端 11 条接口的**唯一机器可读契约**（请求/响应 schema、错误码、SSE 语义） | `_test/api_contract_check.py`：C1 不缺文档 / C2 不虚文档（幽灵路径）/ C3 前端不得偷调 / C4 运行态状态码与必需键一致 / C6 覆盖度精确对账 / C5 自证判据非恒真。已入全量电池与 CI `java-build` |
| [`API.md`](API.md) | 人读 API 手册（curl 示例、字段、错误码、三层 memory 开关） | `_test/api_contract_check.py` C7（r89 新增）：yaml 每条路径必须在手册出现 / 手册不得虚报接口 / 手册声明的路径计数必须等于实值 |
| [`EXTENSIONS.md`](EXTENSIONS.md) | 扩展手册：词表 SSOT、共情策略、LLM 上游切换、记忆 provider、部署目标、第三方集成清单 | 人工维护；接口面变动由 C7 与 `_test/engine_consistency_check.py` 兜住，本目录由 `_test/repo_config_check.py` G19 盯「在不在索引里」 |
| [`PERF-BASELINE.md`](PERF-BASELINE.md) | 性能基线口径与预算表（p95 / 吞吐 / 四目标预算），把"自证"变成可引用的数 | `_test/perf_baseline_check.py`（同机棘轮，超限即红） |
| [`quality-gates.md`](quality-gates.md) | 判据体系明细：每条套件的口径 + 复算命令（**条数一律从 `run_all_suites.py` 的 SUITES 现读，本文件不抄数**） | `_test/repo_config_check.py` G16：电池脚本 ⇄ 本文档双向对账（漏登/幽灵登都红） |
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
