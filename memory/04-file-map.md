# 04 - 核心文件地图

> 本文件记录项目关键文件及其作用。sync 命令会自动更新入口文件部分。
> 归档类型：快照（整体复制到归档）

<!-- SYNC_AUTO_GENERATED_START -->
### 入口文件:
  - `src/index.html`
  - `server/src/main/java/com/xinyu/soulisle/SoulIsleApplication.java`
  - `deploy/cloudbase/functions/chat/index.js`
  - `deploy/xinyu/index.html`
### 文档: `README.md`
<!-- SYNC_AUTO_GENERATED_END -->

> ✅ **sync 自动块已修复（2026-09-22，A-project-handoff V3.44.0）**：入口识别已增 Java 启动类 + `index.html`，并把 `deploy/` 等交付副本降权排后。现自动块正确列出 `src/index.html`（前端真入口）+ `server/.../SoulIsleApplication.java`（后端启动类），`deploy/` 副本仅作次要参考。

## 核心逻辑文件
<!-- 手动补充：核心业务逻辑文件说明 -->

### 前端（`src/js/`，零构建 ES Module）
- `src/js/app.js` — 主编排（五幕叙事 + 对话坞 + 星雾联动）
- `src/js/three-scene.js` — Three.js 星雾粒子 + 情绪点亮（WebGL 不可用降级 CSS 渐变）
- `src/js/chat-agent.js` — 对话逻辑 + 在线/离线切换 + 记忆读写
- `src/js/emotion-engine.js` — 词典情绪引擎（离线降级用，与 Java 侧词表须两端同步）
- `src/js/memory-store.js` — 本地/远端记忆存储（`cfg.remote===true` 才走远端 + 熔断）
- `src/js/scroll-story.js` — GSAP ScrollTrigger 滚动叙事
- `src/js/demo-config.js` — 本地演示配置（**含 Key，已 ignore，禁入库/禁覆盖 deploy 版**）

### 后端（`server/`，Spring Boot 3.2.5 / JDK 17）
- `server/.../SoulIsleApplication.java` — 启动类
- `server/.../llm/LlmProxy.java` — JDK 内置 HttpClient 转发 OpenAI 兼容上游（密钥走 `DEEPSEEK_KEY`）
- `server/.../engine/` — `EmotionLexicon`（词表）/ `EmotionEngine`（scan）/ `EmotionClassifier`（双路+分歧采信 LLM+危机优先）
- `server/.../api/` — `ChatController` / `EmotionController` / `MemoryController` / `HealthController`
- `server/.../service/MemoryService.java` + `entity/` + `mapper/` — 记忆持久化（chat_message / emotion_record）
- `server/.../config/ApiTokenFilter.java` — 可选鉴权（`xinyu.api-token` 空=放行）

## 配置文件
<!-- 手动补充：关键配置文件说明 -->
- `server/pom.xml` — Maven 构建（`com.xinyu:soulisle-server`，fat jar）
- `server/src/main/resources/application.yml` — 端口 + `static-locations` 直读 `src/`
- `server/src/main/resources/schema.sql` — H2/MySQL 双兼容 DDL
- `deploy/wrangler.toml` — Cloudflare Pages 配置
- `deploy/cloudbase/cloudbaserc.json` — 腾讯云 CloudBase 配置
- `.gitignore` / `.aiexclude` — 入库边界 / AI 搜索忽略清单 
