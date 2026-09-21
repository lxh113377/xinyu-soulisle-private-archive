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
| （按需追加：部署/审计/UI 等专用 skill） | 项目名-deploy 等 |

## 铁律

- `memory/07-next-steps.md` P0 永不为空；`savepoint` 后才能结束对话
- **当前主线 = Java 全栈改造（2026-09-20 定）**：分阶段 J1–J5 落在 `07-next-steps.md`，每阶段必须能跑 + 过 `_test/browser_check.py`，禁止一次性推倒重写
- **密钥红线**：密钥零落前端、零入库。`src/js/demo-config.js`（含 Key）已在 `.gitignore`；`deploy/xinyu/js/demo-config.js`（零密钥代理版）**禁止**被 src 版覆盖
- **同步红线**：改 `src/` 必须同步 `deploy/xinyu/` 并做 SHA256 双向比对（MISSING / DIFF / EXTRA 三类全归零）
- Java 任务（v2 起）：源码一律 UTF-8，编译必须 `javac -encoding UTF-8`；JDK 版本切换后必须重验编码
- **Java 构建环境（2026-09-21 实测，禁凭记忆猜路径）**：JDK 17 = `C:\Program Files\Eclipse Adoptium\jdk-17.0.20.101-hotspot`；Maven = `%USERPROFILE%\.local\maven\apache-maven-3.9.9\bin\mvn`（不在 PATH）。⚠️ **默认 `JAVA_HOME` 是 JDK 8，每次构建/启动前必须显式切换**，否则 Spring Boot 3 编译失败
- **静态页托管红线**：服务端直读 `src/`（`static-locations=file:${XINYU_WEB_ROOT:./src/}`），**禁止**把前端复制进 `src/main/resources/static/`（会造出第三处副本同步点）
- **评测集红线（J3）**：`GET /api/emotion/eval` 从 `_test/emotion-eval-dataset.json` **直读权威源**（`XINYU_EVAL_DATASET` 可覆盖），**禁止**把评测集复制进 jar/资源目录；改词表必须同时改 `src/js/emotion-engine.js` 并重跑 `node _test/emotion_eval.js` 对账
- **J4 开关**：前端远端记忆默认**关闭**，靠 `cfg.remote === true` 启用（`memory-store.js`）；改动该默认值会波及全部浏览器回归，须先跑 `_test/j4_memory_check.py` + `browser_check.py`
- **密钥红线（J5）**：`DEEPSEEK_KEY` 只从环境变量读；`XINYU_API_TOKEN` 留空=不鉴权（演示默认），私有部署时置非空
