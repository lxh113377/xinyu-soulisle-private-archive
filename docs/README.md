# docs/ — 工程文档索引

> 与根目录文档的分工：`README.md` 面向使用者（能力/快速开始），`ROADMAP.md`/`CHANGELOG.md` 面向节奏与版本，
> `memory/` 面向 **AI 会话交接**（9 个结构化文件 + 分卷）。本目录放**可被工具消费的工程规格**。

| 文件 | 内容 | 谁在用（机器强制） |
|---|---|---|
| [`openapi.yaml`](openapi.yaml) | 服务端 11 条接口的**唯一机器可读契约**（请求/响应 schema、错误码、SSE 语义） | `_test/api_contract_check.py`：C1 不缺文档 / C2 不虚文档（幽灵路径）/ C3 前端不得偷调 / C4 运行态状态码与必需键一致 / C5 自证判据非恒真。已入全量电池与 CI `java-build` |

## 为什么放在这里（一条诚实记录）

对标实测 16 个参照仓里只有 **1 家**存在机器可读 API 规范（`api_spec=1/16`，见
`../交付物/对标数据/benchmark-metrics.json`），所以这份契约**不是"被同类项目甩开"的对标差距**，
而是本项目自身的**契约分散**问题：`/api/chat` 的形状此前同时写在
`_test/j2_chat_contract.py`、`src/js/chat-agent.js` 的常量、`deploy/jar/README-部署.md` 三处，
改一端忘两端全靠人记。收敛成单一声明源并加守卫，属于自我登记的可维护性改进 —— 报告里也照此表述，
不冒充竞品压力（对标轮 r21，2026-09-25）。

## 改接口时的正确顺序

1. 先改 `openapi.yaml`（含 `x-live-check` 标注）→ 2. 跑 `python _test/api_contract_check.py`（应因"代码缺实现"报红）
   → 3. 改控制器/前端 → 4. `--selftest` 确认判据仍能抓红 → 5. 跑全量电池 `python _test/run_all_suites.py`。
