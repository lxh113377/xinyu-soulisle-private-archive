# 03 - 技术栈

> 本文件记录项目使用的技术栈。sync 命令会自动更新此文件。
> 归档类型：快照（整体复制到归档）

<!-- SYNC_AUTO_GENERATED_START -->
<!-- 以下内容由 sync 命令自动生成，手动修改会在下次 sync 时被覆盖 -->
（运行 `handoff.py sync` 自动检测技术栈）
<!-- SYNC_AUTO_GENERATED_END -->

## 当前技术栈（v1 原型，2026-09-19/20 实测可运行）

### 前端（零构建纯静态，无打包器 / 无 node_modules）
- Three.js（`src/vendor/three.min.js` 本地 vendor）+ 自写 `ShaderMaterial`（逐粒子 `aSize`，暗星 0.05 / 点亮 0.26）
- GSAP + ScrollTrigger（`src/vendor/gsap.min.js`、`src/vendor/ScrollTrigger.min.js` 本地 vendor）
- 原生 ES Module JS，无框架；Canvas 2D 情绪曲线；Web Speech API（zh-CN）语音输入
- 本机持久化：`localStorage`（键 `peiliao.history.v1`）
- 降级：WebGL 不可用 → CSS 渐变；在线 LLM 不可用 → 离线模板（界面明示模式，禁伪装在线）

### 服务端（Serverless，v1 线上双线）
- Cloudflare Pages Function：`deploy/functions/api/chat.js`（同源代理 `/api/chat`，密钥在 `env.DEEPSEEK_KEY`）
- 腾讯云 CloudBase 云函数 `chat`（Nodejs20.19，HTTP 访问服务 `/api`，环境 `qwer-d4gf2r76o8829463b`，有效期至 2027-03-14）
- 情绪引擎：`src/js/emotion-engine.js`（词典快判）+ LLM 精判，**分歧采信 LLM**；危机信号最高优先级拦截
- LLM：DeepSeek（OpenAI 兼容 `/chat/completions`），浏览器直连已实测（CORS 通过）

## 🎯 目标技术栈（v2 — Java 全栈，2026-09-20 老大定方向 · 选型为假设值待确认）

> ⚠️ **本表未落地项均为「待落地验证」的假设值**（A-project-handoff V3.41.4 立规）：落地阶段必须用**实测值**回填，禁止把计划当既成事实引用。
> **已落地实测**（可作为事实引用，2026-09-22 J1–J5 全部跑通）：JDK 17 / Maven 3.9.9 / Spring Boot 3.2.5 / 静态页 `static-locations` 直读 `src/` / `POST /api/chat` 契约 1:1 / 情绪引擎 Java 化（与 JS 侧对账 94.4%、危机 3-3 一致）/ **MyBatis-Plus 3.5.7 + H2 file（默认）**、MySQL 8 驱动已引可切 / `/api/memory/**` 持久化（跨重启实测）/ fat jar `server/target/soulisle-server.jar` / 可选 `XINYU_API_TOKEN` 鉴权。
> **未落地**（仍属假设）：**Spring Security + JWT 未引入**（J5 改用轻量 token 过滤器，默认关闭）；**Dockerfile 未实测**（本机无 Docker）；**MySQL 实际连接未实测**（仅 H2 跑通）。

| 层 | 选型（待确认） | 备注 |
|---|---|---|
| 语言 / 运行时 | **JDK 17** | 本机实测 `C:\Program Files\Eclipse Adoptium\jdk-17.0.20.101-hotspot`；JDK 8（`…jdk-8.0.504.1-hotspot`）是课程作业用，本项目勿混 |
| 构建 | **Maven** | `mvn -q package` 产出可执行 fat jar |
| Web 框架 | **Spring Boot 3.2.x**（`spring-boot-starter-web`） | 单体应用，不引入微服务 |
| 持久层 | **MyBatis-Plus + MySQL 8** | 表 `chat_message` / `emotion_record`；本机演示可切 H2 内存库 |
| 鉴权 | Spring Security + JWT（可选，J5） | 评委体验模式保留匿名会话，不强制登录 |
| LLM 接入 | JDK 内置 `HttpClient`（零额外依赖）或 langchain4j | 密钥走环境变量 / 外部化配置，**禁入库** |
| 情绪引擎 | Java 重写 `EmotionEngine`（复用现词典 JSON） | 双路（词典 + LLM）与分歧采信规则必须与 v1 一致 |
| 前端 | **保留现有 Three.js 静态页，零改动** | 由 Spring Boot `static/` 托管，或前置 Nginx |
| 部署 | `java -jar`（预留 Dockerfile） | v1 的 Cloudflare / CloudBase 保留为降级与对比路径 |

## 构建与部署
- v1（当前线上）：前端静态产物 → Cloudflare Pages（`wrangler pages deploy`）+ CloudBase 静态托管；服务端为 Pages Function / 云函数
- v2（目标）：`mvn package` → `java -jar soulisle-server.jar`。**J1 实际做法与规划不同（2026-09-21 实测决策）**：前端**不复制**进 `src/main/resources/static/`，改为 `spring.web.resources.static-locations=file:${XINYU_WEB_ROOT:./src/}` **直读权威源**，避免造出第三处副本同步点；fat jar 部署时可用 `XINYU_WEB_ROOT` 指向产物目录

### v2 已实测工具链（2026-09-21）
| 项 | 实测路径 / 值 |
|---|---|
| JDK 17 | `C:\Program Files\Eclipse Adoptium\jdk-17.0.20.101-hotspot`（`java -version` = 17.0.20.1） |
| Maven | `%USERPROFILE%\.local\maven\apache-maven-3.9.9\bin\mvn`（新装，**不在 PATH**） |
| 镜像 | `~/.m2/settings.xml` → 腾讯云 `mirrors.cloud.tencent.com/nexus/repository/maven-public/` |
| ⚠️ JAVA_HOME | 系统默认 **JDK 8**（`…jdk-8.0.504.1-hotspot`）→ 构建/启动前必须显式切换到 JDK 17 |
| 起服务 | `java -jar server\target\soulisle-server.jar --server.port=8123`（工作目录 = 项目根，`./src/` 才能解析） |
- 红线：**密钥零落前端、零入库**；`deploy/xinyu/js/demo-config.js` 是公网零密钥代理版，禁止被 `src/js/demo-config.js`（含 Key，已 ignore）覆盖

## 运行时要求
- 前端：现代浏览器（WebGL2 + ES Module）；无 WebGL 时降级 CSS 渐变
- v2 服务端：JDK 17+；MySQL 8（或 H2 演示模式）；需出网访问 `api.deepseek.com`
