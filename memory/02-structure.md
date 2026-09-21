# 02 - 仓库结构

> 本文件记录项目目录结构。sync 命令会自动更新此文件。
> 归档类型：快照（整体复制到归档）

<!-- SYNC_AUTO_GENERATED_START -->
<!-- 以下内容由 sync 命令自动生成，手动修改会在下次 sync 时被覆盖 -->
（运行 `handoff.py sync` 自动生成目录树）
<!-- SYNC_AUTO_GENERATED_END -->

## 模块说明

### 权威源（改这里）
- `src/` — **唯一权威源码**。`index.html`（五幕叙事 + 底部对话坞 + 星雾 canvas）+ `css/` + `js/`（`app.js` 编排 / `three-scene.js` 星雾与情绪点亮 / `chat-agent.js` 对话与记忆 / `emotion-engine.js` 词典情绪引擎 / `scroll-story.js` 滚动叙事 / `demo-config.js` 本地演示配置，**含 Key 已 ignore**）+ `vendor/`（three / gsap / ScrollTrigger 本地 vendor）+ `functions/api/chat.js`（Pages Function 源）

### 交付与部署
- `deploy/` — **部署产物**，改完 `src/` 必须同步此处并做 SHA256 双向比对（MISSING / DIFF / EXTRA 三类归零）
  - `deploy/xinyu/` — 前端公网副本（`js/demo-config.js` 为零密钥代理版，**禁止被 src 版覆盖**）
  - `deploy/functions/` — Cloudflare Pages Function
  - `deploy/` 另有 `wrangler.toml` / CloudBase 相关 JSON
- `交付物/` — iCAN 评审文档与截图（`iCAN评审/`）、提交包大纲（`提交包/`）

### 验证与记忆
- `_test/` — 常驻回归脚本：`browser_check.py`（离线降级链路 + 回滚可见性 + 双色 + 滚动淡入淡出）、`pixel_dual_check.py`（双色像素级三用例）、`lightshow_check.py`、`online_check.py`、`public_check.py`、`emotion_eval.js` + `emotion-eval-dataset.json`（36 条评测集）；`_shots/`（脚本生成的截图，已 ignore）
- `memory/` — 本项目交接记忆（01–08 + `AGENTS.md` 绑定表 + 阶段基线文件）
- `archive/` — 阶段归档（`A-project-handoff archive` 产出）
- `.codebuddy/` — 工作记忆与会话数据（已 ignore，勿删）

### v2 Java 服务端（2026-09-21 J1 已落地）
- `server/` — Spring Boot 工程根：
  - `pom.xml`（`com.xinyu:soulisle-server`，parent = `spring-boot-starter-parent:3.2.5`，`java.version=17`，UTF-8 双 encoding）
  - `src/main/java/com/xinyu/soulisle/SoulIsleApplication.java`（启动类）
  - `src/main/java/com/xinyu/soulisle/api/HealthController.java`（`/api/health`，回传 `webRoot/indexFound/vendorFound` 作可复核判据）
  - `src/main/resources/application.yml`（`server.port=${XINYU_PORT:8080}`；`static-locations=file:${XINYU_WEB_ROOT:./src/}`）
  - `server/target/` — 构建产物（fat jar ≈ 20 MB，**已 ignore**）
- **静态页托管策略：直读 `src/` 权威源，不复制到 `src/main/resources/static/`** —— 避免第三处副本同步点（既有同步红线：`src/` → `deploy/xinyu/`）
- `llm/LlmProxy.java`（J2，JDK 内置 `HttpClient` 转发 OpenAI 兼容上游，零额外依赖）+ `api/ChatController.java`（`/api/chat` 契约 1:1 复刻 v1 Function）
- `engine/`（J3）：`EmotionLexicon`（词表/否定/程度/危机词，逐字对齐 `src/js/emotion-engine.js`）+ `EmotionEngine`（`scan`/`secondaryOf`）+ `EmotionClassifier`（双路 + 分歧采信 + 危机优先）
- `api/EmotionController.java`（J3）：`POST /api/emotion`、`GET /api/emotion/eval`（复跑 `_test/emotion-eval-dataset.json`，输出与 `_test/emotion_eval.js` 同构）
- `entity/` + `mapper/` + `service/MemoryService` + `api/MemoryController`（J4）：`chat_message` / `emotion_record` 两表，`/api/memory/**` CRUD + stats
- `config/ApiTokenFilter.java`（J5）：可选鉴权（`xinyu.api-token` 留空=放行）
- `server/src/main/resources/schema.sql`（J4 DDL，H2/MySQL 双兼容）、`server/Dockerfile`（J5，**未实测**：本机无 Docker）
