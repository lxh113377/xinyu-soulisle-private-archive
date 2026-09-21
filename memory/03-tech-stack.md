# 03 - 技术栈

> 本文件记录项目使用的技术栈。sync 命令会自动更新此文件。
> 归档类型：快照（整体复制到归档）

<!-- SYNC_AUTO_GENERATED_START -->
（未检测到技术栈配置文件）
<!-- SYNC_AUTO_GENERATED_END -->

> ⚠️ **sync 自动块对本项目失效（2026-09-22 实测）**：它报「未检测到技术栈配置文件」—— 因为 `pom.xml` 在 `server/` 子目录，而 sync 只扫项目根。
> **本文件以「当前技术栈」「🎯 目标技术栈」「📋 选型决策记录」三节为准**，自动块仅作参考。
> 另注：本块**只被 sync 覆盖、不会覆盖块外内容**（已实测：决策记录在 sync 后幸存）。

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

| 层 | 选型（✅=已实测落地） | 备注（含实际落地差异） |
|---|---|---|
| 语言 / 运行时 | ✅ **JDK 17** | 本机实测 `C:\Program Files\Eclipse Adoptium\jdk-17.0.20.101-hotspot`；JDK 8（`…jdk-8.0.504.1-hotspot`）是课程作业用，本项目勿混 |
| 构建 | ✅ **Maven 3.9.9** | `mvn -f server/pom.xml package` → fat jar `server/target/soulisle-server.jar` |
| Web 框架 | ✅ **Spring Boot 3.2.5**（`spring-boot-starter-web`） | 单体应用，不引入微服务 |
| 持久层 | ✅ **MyBatis-Plus 3.5.7**；默认 **H2 file**；MySQL 8 驱动已引**可切但未实测** | 表 `chat_message` / `emotion_record`；⚠️ 与初版计划的差异：默认由"H2 内存库"改为 **H2 file**（`server/data/`，已 ignore），因为内存库重启即丢、不算持久 |
| 鉴权 | ⚠️ **改为轻量 token 过滤器**（`xinyu.api-token`，默认空=放行） | ⚠️ 与初版计划的差异：**未引入 Spring Security + JWT**。理由见「决策 #4」 |
| LLM 接入 | ✅ **JDK 内置 `HttpClient`**（零额外依赖） | 密钥走环境变量 `DEEPSEEK_KEY`，**禁入库** |
| 情绪引擎 | ✅ Java 已实现（`engine/`）；⚠️ **前端仍用 JS 引擎，尚未接入 `/api/emotion`** | ⚠️ 当前存在**两份真相**（`src/js/emotion-engine.js` + `server/.../EmotionLexicon.java`），已登记为下一 P0 要消除 |
| 前端 | ✅ **保留现有 Three.js 静态页，零代码改动**（J4 远端记忆为可选项） | ⚠️ 与初版计划的差异：**不由 `static/` 托管**，改**直读 `src/`**（见「决策 #2」） |
| 部署 | ✅ `java -jar`；`server/Dockerfile` 已交付 | ⚠️ **Docker 本机未安装 → 镜像构建未实测**；v1 的 Cloudflare / CloudBase 保留为降级与对比路径 |

## 📋 选型决策记录（由 A-project-handoff 负责维护）

> **本节即「技术栈/架构选型」的落盘位置**（老大 2026-09-22 定：此类决定归 A-project-handoff 管）。
> 规则：① 新增/推翻决策都写这里，不散落在对话或 `.codebuddy/` 里；② 每条决策必须有**背景 / 选项 / 结论 / 已知代价 / 重评触发条件**五要素；③ 遵循 V3.41.4 —— 未落地项标注**待落地验证**，落地后用实测值回填；④ 决策被推翻时**保留原条目 + 增更正注**（历史留痕不可改写），不直接删除。

| # | 决策 | 日期 | 状态 |
|---|---|---|---|
| 1 | 后端语言选 **Java(Spring Boot)** 而非 Python(FastAPI) | 2026-09-20 定向 / 2026-09-22 复核 | 已执行（J1–J5 跑通）；**复核结论：若重做会选 Python，但不返工** |
| 2 | 前端静态页**直读 `src/`**，不复制进 `src/main/resources/static/` | 2026-09-21 | 已执行 |
| 3 | J4 前端远端记忆**默认关闭**（`cfg.remote===true` 才启用） | 2026-09-22 | 已执行 |
| 4 | 鉴权用**轻量 token 过滤器**，不引入 Spring Security | 2026-09-22 | 已执行 |
| 5 | 情绪评测集 `_test/emotion-eval-dataset.json` **不复制进 jar**，服务端直读 | 2026-09-22 | 已执行 |

### 决策 #1 —— 后端语言：Java(Spring Boot) vs Python(FastAPI)

- **背景**：v1 是纯静态前端 + Serverless 函数（Pages Function / 云函数）。老大 2026-09-20 定方向要演进为全栈后端；核心诉求是「密钥外置 + 记忆持久化 + 可部署可控」。
- **选项对比**（客观维度 + 本项目实证）：

  | 维度 | Java | Python |
  |---|---|---|
  | 开发速度 / 代码量 | 慢、需分层（本项目 12 类 ≈800 行 + Maven 配置） | **快**，同功能约 1/3 代码量（估约 150 行） |
  | 类型安全 / 重构 | **强静态类型**，敢重构 | 运行期才暴露 |
  | 依赖 / 部署产物 | **单一 fat jar + JRE，无依赖漂移** | venv 地狱（同批项目实证：门店 `.venv` 196.51MB、医项目清理释放 518MB） |
  | 性能 / 并发 | **真并行**（线程池/虚拟线程） | GIL 限制 CPU 并行（异步 IO 对本项目够用） |
  | AI / 模型生态 | 弱（LangChain4j 是追赶者） | **碾压**（transformers / numpy / jieba / 向量库） |
  | 冷启动 / 内存 | 慢重（Spring 起 2-4s、数百 MB） | 快轻（~0.5s、数十 MB） |
  | 工程化 / 测试 | **强**（JUnit / Maven 仲裁） | 有了，但依赖冲突排查更痛 |
  | 评审认知 | 高校主流课程语言，评委熟悉 | 也主流，AI 方向更亲 |

- **结论**：**按原定方向继续用 Java**，不返工。
  - 支持 Java 的三条真实理由：① 产物干净（fat jar，无需 venv 管理）② 强类型 + 可单测（36 条评测可做成 JUnit，比跑 node 脚本正规）③ 部署不受平台风控挟制（⚠️ 此条与语言无关，Python 容器化同样能做到）
  - **诚实复核（2026-09-22 老大追问后新增）**：本项目真正需要的只有「1 个 LLM 代理 + 2 张表 + 1 个词典引擎」。**若从零重做，本作品会选 Python**（开发量小一个量级，且 AI 生态是主场）。选 Java 属于「方向先定、已投入且验收通过」的路径依赖，**返工成本 > 收益**。
- **已知代价**：① 两套后端并行维护（v1 Serverless 保留为降级路径）② 情绪引擎出现**两份真相**（JS + Java）③ 代码量约为 Python 方案的数倍。
- **重评触发条件**（命中即重新评估，届时按「Python 侧服务 + Java HTTP 调用」演进，**不要用 Java 硬啃 AI 生态**）：
  - 需要本地情绪模型 / Embedding / 向量检索 / RAG 记忆 / 模型微调
  - 需要引入 Python 专属 NLP 生态（jieba、snownlp、transformers）
  - 需要重型数据分析（pandas / numpy）
  - → 届时形态为 **Java 管业务 API + Python 管模型服务**（业界常态，不是失败）

### 决策 #2 —— 前端静态页托管：直读 `src/` vs 复制进 resources

- **背景**：Spring Boot 常规做法是把前端产物放进 `src/main/resources/static/`。
- **结论**：**改为直读权威源** —— `spring.web.resources.static-locations=file:${XINYU_WEB_ROOT:./src/}`，不复制。
- **理由**：项目已有 `src/` → `deploy/xinyu/` 一条同步红线；再引入 `resources/static/` 就是**第三处副本**，必然出现"改了 src 忘了同步第三份"。零副本从根上消灭该风险。
- **已知代价**：`./src/` 是相对 JVM 工作目录的路径 → **启动时工作目录必须是项目根**；Docker 里需把 `src/` COPY 进镜像（`server/Dockerfile` 已处理）。

### 决策 #3 —— J4 前端远端记忆默认关闭

- **背景**：J4 做了服务端持久化，但改前端默认行为会波及全部浏览器回归套件。
- **结论**：默认关闭，靠 `cfg.remote === true` 显式启用；本地 `localStorage` 保留为降级路径。
- **理由**：零回归风险 + 服务端不可达时功能不变。
- **已知代价**：⚠️ **默认状态下 J4 等于没被用上**（前端 0 处 `remote:true`）→ "跨设备记住你"这个卖点**要主动开启才成立**；已登记为下一 P0。

### 决策 #4 —— 鉴权：轻量 token 过滤器 vs Spring Security

- **背景**：J5 计划里写的是「可选 Spring Security + JWT」。
- **结论**：**不引入 Spring Security**，改用 `ApiTokenFilter`（读 `xinyu.api-token`，留空=完全放行）。
- **理由**：本项目是对外演示的**单体**应用，需求只是"私有部署时别让人随便打接口"；引入全家桶会带来配置复杂度与依赖体积，收益不匹配。
- **已知代价**：**无多用户 / 无角色 / 无会话管理**。若将来要做账号体系，需重新评估（届时 Spring Security 才有价值）。
- **实测**：无 token 放行 200；有 token 时 无头 401 / 错头 401 / 对头 200 / `/api/health` 与静态页放行。

### 决策 #5 —— 评测集不复制进 jar

- **背景**：`GET /api/emotion/eval` 需读 36 条评测集。
- **结论**：从 `_test/emotion-eval-dataset.json` **直读**（`XINYU_EVAL_DATASET` 可覆盖），不复制进 `resources/`。
- **理由**：同决策 #2 —— 消灭第二份副本，保证「Java 侧跑的就是 JS 侧跑的那份数据」，这也是双端对账能逐项一致的前提。
- **已知代价**：jar 离开项目目录后需显式设置 `XINYU_EVAL_DATASET`（Docker 已处理）。

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
