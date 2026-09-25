# AGENTS.md — 陪聊 项目级 Skill 绑定表（P-1，A-project-handoff）

> 手动维护。agent 检测到本项目路径时第一动作 Read 本文件；命中触发条件 → 加载对应 skill，禁裸跑。

## Skill 强制绑定（命中即加载）

| 触发条件 | 必加载 skill |
|---------|-------------|
| 任何项目修改操作（代码/记忆/技能/文档/配置） | A-project-handoff |
| 每轮复杂任务开场 | A-memory-start |
| 任务结束/复盘/经验沉淀 | A-get-memory |
| 动手前需求澄清 | A-ask-questions |
| **任何 Java 代码 / 编译运行 / JDK 环境相关** | **A-java-problem**（铁律 #45，禁绕过） |
| **技术栈 / 架构选型决策（新增、变更、推翻）** | **A-project-handoff** —— 唯一落盘位置 `03-tech-stack.md` 的「📋 选型决策记录」节（2026-09-22 老大定：此类决定由该 skill 负责，禁止散落在对话或 `.codebuddy/` 记忆里） |
| （按需追加：部署/审计/UI 等专用 skill） | 项目名-deploy 等 |

## 铁律

- `memory/07-next-steps.md` P0 永不为空；`savepoint` 后才能结束对话
- **当前主线 = Java 全栈改造（2026-09-20 定）**：分阶段 J1–J5 落在 `07-next-steps.md`，每阶段必须能跑 + 过 `_test/browser_check.py`，禁止一次性推倒重写
- **密钥红线**：密钥零落前端、零入库。`src/js/demo-config.js`（含 Key）已在 `.gitignore`；`deploy/xinyu/js/demo-config.js`（零密钥代理版）**禁止**被 src 版覆盖
- **同步红线**：改 `src/` 必须同步 `deploy/xinyu/` 并做 SHA256 双向比对（MISSING / DIFF / EXTRA 三类全归零）→ **已固化为 `python _test/deploy_sync_check.py`**（2026-09-23 立）。
  ⚠️ 立规缘由：修完 `src/js/emotion-engine.js` 缺陷后公网副本**仍是旧引擎**，差点把带缺陷的版本部署上线；且首次手工比对被 PowerShell 别名 `h`(Get-History) 覆盖自定义函数 → 两端哈希都取不到 → `None==None` → **全报 SAME（假通过）**。故脚本强制哈希非空 + 输入非空断言，并自带对照组用法。
  `js/demo-config.js` **不参与内容比对**（两端本就该不同：src 版含真实 Key，deploy 版是零密钥 stub），只做红线复核（零密钥 + 与 src 版不同）。
- Java 任务（v2 起）：源码一律 UTF-8，编译必须 `javac -encoding UTF-8`；JDK 版本切换后必须重验编码
- **Java 构建环境（2026-09-21 实测，禁凭记忆猜路径）**：JDK 17 = `C:\Program Files\Eclipse Adoptium\jdk-17.0.20.101-hotspot`；Maven = `%USERPROFILE%\.local\maven\apache-maven-3.9.9\bin\mvn`（不在 PATH）。⚠️ **默认 `JAVA_HOME` 是 JDK 8，每次构建/启动前必须显式切换**，否则 Spring Boot 3 编译失败
- **静态页托管红线**：服务端直读 `src/`（`static-locations=file:${XINYU_WEB_ROOT:./src/}`），**禁止**把前端复制进 `src/main/resources/static/`（会造出第三处副本同步点）
- **评测集红线（J3）**：`GET /api/emotion/eval` 从 `_test/emotion-eval-dataset.json` **直读权威源**（`XINYU_EVAL_DATASET` 可覆盖），**禁止**把评测集复制进 jar/资源目录
- **🔴 词表一致性红线（J3，2026-09-22 立）**：情绪引擎在 JS / Java **各有一份**（本地那份是**离线降级**用的，不可删）。**改任一端的词表，必须两端同步改，并跑 `python _test/engine_consistency_check.py`**（三层判据：词表结构含重复项与顺序 / **逐条预测 73 条**（2026-09-23 由 36 扩至 73）/ 汇总指标）—— **不一致即失败**，禁止只看 `emotion_eval.js` 单侧通过就提交
- **J4 开关（2026-09-23 校正：此前只写「默认关闭」，与磁盘实况不符）**：分三层，**不得混为一谈**
  1. **代码层**（`src/js/memory-store.js`）—— 判定仍是 `cfg.remote === true` 才发远端请求，**默认关闭**；服务端不可达即熔断（404/网络失败 → `remoteDown`，本会话不再重试），本地 `localStorage` 照常写入
  2. **本地演示预置层**（`src/js/demo-config.js`）—— 已置 **`remote: true`** ⇒ **本地 / fat jar 演示默认开启**服务端持久化（"跨设备、清缓存都不丢"成立）
  3. **公网部署层**（`deploy/xinyu/js/demo-config.js`）—— **刻意不含 `remote`** ⇒ Pages / CloudBase 上默认关闭（那里只有 `/api/chat`、没有 `/api/memory`，开了会给评委看到 404）
  改动任一层都须先跑 `_test/j4_memory_check.py` + `_test/j4_remote_down_check.py` + `_test/browser_check.py`
- **密钥红线（J5）**：`DEEPSEEK_KEY` 只从环境变量读；`XINYU_API_TOKEN` 留空=不鉴权（演示默认），私有部署时置非空

## 架构决策（索引 —— 详表见 `03-tech-stack.md`「📋 选型决策记录」）

> **约定（2026-09-22 老大立）**：技术栈/架构选型类决定由 **A-project-handoff** 负责，唯一落盘位置 = `03-tech-stack.md`「📋 选型决策记录」；每条须含五要素（背景 / 选项 / 结论 / 已知代价 / 重评触发条件），未落地项标「待落地验证」，被推翻的决策保留原条目 + 增更正注。

- **后端语言 = Java(Spring Boot)** —— 已执行；但**复核结论：若重做本作品会选 Python**，不返工。重评触发条件 = 需要本地模型/Embedding/RAG/微调/AI 生态 → 届时起 **Python 侧服务由 Java HTTP 调用**，不用 Java 硬啃 AI 生态
- **静态页直读 `src/`**（不复制进 `resources/static/`）—— 消灭第三处副本同步点；代价 = 启动工作目录必须是项目根
- **J4 远端记忆默认关闭**（`cfg.remote`）—— 零回归风险；代价 = 不主动开启则"跨设备记住你"不成立
- **鉴权用轻量 token 过滤器**（未引 Spring Security）—— 够用 + 依赖最小；代价 = 无多用户/角色/会话管理
- **评测集不复制进 jar**（服务端直读 `_test/`）—— 保证 Java 侧与 JS 侧跑的是同一份数据


## 排障手册（本轮一手实测，进仓即读）

> 只登记**本机本仓亲测复现过**的报错特征，一条一测；未复现的传闻不写（写进来就会有人当真理）。

| 症状 / 报错原文 | 真因 | 处置 |
|---|---|---|
| `[GATE:dag-fail] ... 块内找不到本次改动标识 require_mark=` 但 `blocks` 数在涨 | `dag_precheck.py` 的块体＝**锚点行之后到空行之前**；把"本次标识"写在 `##` 标题行 = 在块体外 | 标识必须写在 `【数据流假设】` 锚点**下面的块体内**（如 `本次标识: xxx`）；且该工具只扫 GM 日志 `D:/global_memory/memory/`，写项目日志无效 |
| `gh api` 调用抛 `json.decoder.JSONDecodeError` / 结果恒空 | 本仓 `_test/benchmark_metrics.py:gh()` 会 `json.loads(整个响应)` 且非零退出即抛 ⇒ 带 `--jq` 出来的**裸字符串不是合法 JSON** | 取整份 dict 再自己挑字段（`gh("repos/x")["description"]`）；要用 `--jq` 就得绕开该 helper |
| 文档里某条红线/条目**表头整行消失**，只剩续行 | 用"既有条目行的前缀"当 Edit 锚点，替换文本里没把原表头回写（长行台账同族第四形态） | 锚点须含被改动的**整行**并在 new 里回写；改完必查 `git diff --stat`：**只有 +N 无 -M** 才算没吞行 |
| `SyntaxError: bytes can only contain ASCII literal characters` | 写了 `b"中文"`（bytes 字面量不能含非 ASCII） | 用 `文本.decode/encode` 或先 `.decode("utf-8", errors="replace")` 再做子串判断 |
| Python 里 `/tmp/xxx` 报 `FileNotFoundError: '\tmp\xxx'` | Git Bash 的 `/tmp` ≠ Windows Python 的 `/tmp`（后者按当前盘根解析） | 跨 bash/python 传文件用显式 `C:/Users/37533/AppData/Local/Temp/...` |
