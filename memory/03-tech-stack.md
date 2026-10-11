# 03 - 技术栈

> 本文件记录项目使用的技术栈。sync 命令会自动更新此文件。
> 归档类型：快照（整体复制到归档）

<!-- SYNC_AUTO_GENERATED_START -->
### 语言: Java (Maven) — server/pom.xml
<!-- SYNC_AUTO_GENERATED_END -->

> ✅ **sync 自动块已修复（2026-09-22，A-project-handoff V3.44.0）**：旧版报「未检测到技术栈配置文件」（`pom.xml` 在 `server/` 子目录，旧判据只扫项目根）；现增子目录清单兜底，自动块正确显示 `Java (Maven) — server/pom.xml`。
> **本文件以「当前技术栈」「🎯 目标技术栈」「📋 选型决策记录」三节为准**（自动块仅给构建清单语言，不含运行时/框架细节）。
> 另注：本块**只被 sync 覆盖、不会覆盖块外内容**（已实测：决策记录在 sync 后幸存）。

## 当前技术栈（v1 原型，2026-09-19/20 实测可运行）

### 前端（零构建纯静态，无打包器 / 无 node_modules）
- Three.js（`src/vendor/three.min.js` 本地 vendor）+ 自写 `ShaderMaterial`（逐粒子 `aSize`，暗星 0.05 / 点亮 0.26）
- GSAP + ScrollTrigger（`src/vendor/gsap.min.js`、`src/vendor/ScrollTrigger.min.js` 本地 vendor）
- 经典脚本 JS（`window.X` 挂载；r67 实测更正"ES Module"误称），无框架；Canvas 2D 情绪曲线；Web Speech API（zh-CN）语音输入
- 本机持久化：`localStorage`（键 `peiliao.history.v1`）
- 降级：WebGL 不可用 → CSS 渐变；在线 LLM 不可用 → 离线模板（界面明示模式，禁伪装在线）

### 服务端（Serverless，v1 线上双线）
- Cloudflare Pages Function：`deploy/functions/api/chat.js`（同源代理 `/api/chat`，密钥在 `env.DEEPSEEK_KEY`）
- 腾讯云 CloudBase 云函数 `chat`（Nodejs20.19，HTTP 访问服务 `/api`，环境 `qwer-d4gf2r76o8829463b`，有效期至 2027-03-14）
- 情绪引擎：`src/js/emotion-engine.js`（词典快判）+ LLM 精判，**分歧采信 LLM**；危机信号最高优先级拦截
- LLM：DeepSeek（OpenAI 兼容 `/chat/completions`），浏览器直连已实测（CORS 通过）

## 🎯 目标技术栈（v2 — Java 全栈，2026-09-20 老大定方向 · 选型为假设值待确认）

> ⚠️ **本表未落地项均为「待落地验证」的假设值**（A-project-handoff V3.41.4 立规）：落地阶段必须用**实测值**回填，禁止把计划当既成事实引用。
> **已落地实测**（可作为事实引用，2026-09-22 J1–J5 全部跑通）：JDK 17 / Maven 3.9.9 / Spring Boot 3.2.5 / 静态页 `static-locations` 直读 `src/` / `POST /api/chat` 契约 1:1 / 情绪引擎 Java 化（与 JS 侧对账一致；**2026-09-23 起为 73 条 / 98.6% / 危机 6-6**，前值 36 条 / 94.4% / 3-3）/ **MyBatis-Plus 3.5.7 + H2 file（默认）**、MySQL 8 驱动已引可切 / `/api/memory/**` 持久化（跨重启实测）/ fat jar `server/target/soulisle-server.jar` / 可选 `XINYU_API_TOKEN` 鉴权。
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
| 6 | 流式输出走**同端点 + 可选 `stream` 字段**，不新建 `/api/chat/stream` | 2026-09-24 对标轮 | 已执行（`stream_contract.py` A/B/C PASS） |
| 7 | 共情策略/提示词/危机话术抽为 **`src/data/emotion-strategy.js` SSOT**（纯 JSON 字面量） | 2026-09-24 对标轮 | 已执行 |
| 8 | provider 适配层用**环境变量嵌套占位符 + 兼容别名**，不引入 provider 注册表代码 | 2026-09-24 对标轮 | 已执行 |
| 9 | 长会话用 **DOM 上界 + 配额制折叠展开**，不引入虚拟滚动列表 | 2026-09-24 对标轮 | 已执行 |
| 10 | 情绪判定引入**本地微调模型腿 + 三级共识路由**（Python FastAPI 模型服务，决策 #1 预设演进路径正式触发） | 2026-10-08/09 | 已执行（101 用例全绿 + 73 条双口径 98.6% 恒等 + 盲测四路对比） |
| 11 | 语音合成引擎：浏览器自带降为兜底，首选**本机开源神经引擎 `sherpa-onnx-vits-zh-ll`**（sidecar 只绑回环，默认关） | 2026-10-12 r118 | 已执行（C15 15/15 + sidecar 一手回执）；⚠️ 公网访客拿不到本机引擎、主观听感未验 |

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
  - 支持 Java 的三条真实理由：① 产物干净（fat jar，无需 venv 管理）② 强类型 + 可单测（**73 条**评测可做成 JUnit，比跑 node 脚本正规）③ 部署不受平台风控挟制（⚠️ 此条与语言无关，Python 容器化同样能做到）
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

### 决策 #3 —— J4 前端远端记忆：代码默认关闭 + 本地演示默认开启（2026-09-23 校正）

- **背景**：J4 做了服务端持久化，但改前端默认行为会波及全部浏览器回归套件。
- **结论（原）**：代码层默认关闭，靠 `cfg.remote === true` 显式启用；本地 `localStorage` 保留为降级路径。
- **2026-09-23 校正（非推翻，是补全）**：原条目的「已知代价」写「前端 0 处 `remote:true`」，该陈述**已与磁盘不符** —— 2026-09-22 已在 `src/js/demo-config.js` 预置 `remote: true`。准确现状是三层：
  1. **代码层** `memory-store.js` —— 仍 `cfg.remote === true` 才启用，**默认关闭** + 服务端不可达熔断（`remoteDown`）
  2. **本地演示层** `src/js/demo-config.js` —— **`remote: true`** ⇒ 本地 / fat jar 演示默认开启
  3. **公网部署层** `deploy/xinyu/js/demo-config.js` —— **刻意不含 `remote`** ⇒ Pages / CloudBase 上默认关闭（那里没有 `/api/memory`，开了会给评委看到 404）
- **理由**：零回归风险 + 服务端不可达时功能不变 + 公网不出现 404。
- **已知代价（更正后）**：⚠️ **公网线上（Pages / CloudBase）J4 仍未启用** —— "跨设备记住你"这个卖点**只在本地 / fat jar 演示成立**；要在线上也成立，必须先给公网补 `/api/memory`（Pages Function 或国内部署的 Java 服务端）。
- **校注来源**：2026-09-23 现场实测 `src/js/demo-config.js:19` = `remote: true`，与旧陈述冲突（历史留痕不可改写，故保留原结论 + 增本校正注）。

### 决策 #4 —— 鉴权：轻量 token 过滤器 vs Spring Security

- **背景**：J5 计划里写的是「可选 Spring Security + JWT」。
- **结论**：**不引入 Spring Security**，改用 `ApiTokenFilter`（读 `xinyu.api-token`，留空=完全放行）。
- **理由**：本项目是对外演示的**单体**应用，需求只是"私有部署时别让人随便打接口"；引入全家桶会带来配置复杂度与依赖体积，收益不匹配。
- **已知代价**：**无多用户 / 无角色 / 无会话管理**。若将来要做账号体系，需重新评估（届时 Spring Security 才有价值）。
- **实测**：无 token 放行 200；有 token 时 无头 401 / 错头 401 / 对头 200 / `/api/health` 与静态页放行。

### 决策 #5 —— 评测集不复制进 jar

- **背景**：`GET /api/emotion/eval` 需读评测集（2026-09-23 起为 **71 条**，前值 36 条）。
- **结论**：从 `_test/emotion-eval-dataset.json` **直读**（`XINYU_EVAL_DATASET` 可覆盖），不复制进 `resources/`。
- **理由**：同决策 #2 —— 消灭第二份副本，保证「Java 侧跑的就是 JS 侧跑的那份数据」，这也是双端对账能逐项一致的前提。
- **已知代价**：jar 离开项目目录后需显式设置 `XINYU_EVAL_DATASET`（Docker 已处理）。

### 决策 #6 —— 情绪引擎：否定判定先排除被程度副词覆盖的字符（2026-09-23）

- **背景**：`NEG`（否定词表）含「别」，而否定/程度的取词窗口都是「情绪词前 3 字」。于是「心里**特别**难受」里，「特别」这个**程度副词**的末字「别」落进窗口并被当成否定词 → sadness 乘 −0.7 反号归零 → 主导情绪变成 anger。这是**引擎缺陷，不是标注歧义**：评委只要输入「我特别难受」就会看到「烦躁」，直接翻车。
- **选项**：
  | 选项 | 做法 | 代价 |
  |---|---|---|
  | A 从 `NEG` 删「别」 | 一行改动 | ❌ 会同时废掉「别难过 / 别哭」的否定能力，制造新缺陷 |
  | B **否定前先排除被 DEG 覆盖的字符**（采用） | 先算出窗口里程度副词的字符区间，落在该区间内的否定词不生效 | 判定逻辑变复杂，需双端同步改并重跑全部判据 |
  | C 改评分口径为 top-2 | 不动引擎，允许预测落前二算命中 | 掩盖缺陷、对外口径要改，评委追问难答 |
- **结论**：**B**。JS 端 `emotion-engine.js` 新增 `hasNegation(before)`，Java 端 `EmotionEngine.java` 新增同构私有方法；**词表内容本身一字未改**（故 `engine_consistency_check.py` 的 A 层词表结构判据仍全等）。
- **验收（双向对照，非只测生效路径）**：修复样本 `心里特别难受` / `我特别难受，想一个人待着` → anger **改判 sadness**（anger 降为次情绪 2.8 vs 1.3）；反向样本 `别难过了，我陪着你` → 仍 **calm**（「别」的否定未失效）。评测集补 2 条防回归样本（71 → 73 条），准确率 97.2% → **98.6%**，危机召回 6-6，双端逐项全等，`browser_check.py` ALL-ASSERT-PASS。
- **已知代价**：① 判定逻辑变复杂（多一层字符区间计算）② 对外数字口径再变一次（94.4% → 97.2% → **98.6%**），**所有历史材料里的旧值都要加校正注** ③ 仍剩 1 条真歧义 `没什么好难过的`（人标 calm、引擎 sadness），属标注口径问题，未改。
- **重评触发条件**：若将来要处理「不太」「不怎么」这类**否定+程度**共现且语义仍为否定的组合，需要重新审视本规则（当前实现里 DEG 覆盖优先于 NEG，可能在这类组合上误放行）。

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
- 前端：现代浏览器（WebGL2 + 经典 script 标签）；无 WebGL 时降级 CSS 渐变
- v2 服务端：JDK 17+；MySQL 8（或 H2 演示模式）；需出网访问 `api.deepseek.com`

---

## 📋 选型决策记录 · 详表（对标轮第二轮 2026-09-24，决策 #6–#9）

### 决策 #6 —— 流式输出：同端点 + 可选 `stream` 字段（而非新建 `/api/chat/stream`）

- **背景**：对标 LobeChat（`@lobehub/fetch-sse`）/ Open-LLM-VTuber（WebSocket 流水线）/ SillyTavern 均有流式，心屿原为整包返回（实测在线 965ms 全等）。首轮把此项推到"赛后"，理由是"破坏 AC-OBS-08 契约 1:1"。本轮老大指令为「按优先级直接开工」，故必须在不破契约的前提下落地。
- **选项对比**：
  | 方案 | 优点 | 代价 |
  |---|---|---|
  | A 新建 `/api/chat/stream` 端点 | 职责分离清晰 | 前端要加分支选择逻辑；v1/v2/公网三处各多一个端点；鉴权与日志面翻倍 |
  | B **同端点 + `stream` 可选字段**（选定） | 不带该字段的请求**逐字不变**，AC-OBS-08 自动守住；前端只是"传个 bool" | 一个方法两种返回形态，Spring 侧签名要统一（实测踩坑见下） |
- **结论**：**B**。`stream:true` 属新增可选字段，不是破坏性变更（已写进 CONTRIBUTING 红线 4）。
- **实测踩坑（必须留痕）**：Controller 返回类型若声明 `ResponseEntity<?>`，流式分支报
  `No converter for [...Lambda...] with preset Content-Type 'text/event-stream'` → **HTTP 500**；
  改成 `ResponseEntity<StreamingResponseBody>`（整包 JSON 也用同一个签名写）才通过。
- **已知代价**：① CloudBase 云函数受"HTTP 请求-响应"模型限制**不做流式**（前端按 `content-type` 自动回落整包，属设计内行为，已在函数头注释与 `.env.example` 写明）；② 流式失败重试会多一次请求（先试流式再回落非流式）。
- **重评触发条件**：若要做"中途打断/停止生成"（OLV 的语音打断能力），SSE 单向通道不够，需上 WebSocket 或 `AbortController` + 服务端取消语义 —— 届时另立决策。

### 决策 #7 —— 共情策略表 SSOT：`.js` 纯 JSON 字面量（而非 `.json` + fetch）

- **背景**：`chat-agent.js` 内硬编码 6 类情绪的共情模板与 SYSTEM 提示，"加一类情绪"要改代码，与首轮词表 SSOT 化（e79025b）方向冲突。对标项目里只有 LobeChat 有 prompt 模板库概念，垂类项目普遍硬编码。
- **选项**：① `.json` + `fetch()` —— 会把同步链路 `respond()` 变异步，波及 `app.js` 全链；② **`.js` 挂全局（选定，与词表同形态）**；③ 继续硬编码但加注释 —— 已被证伪（静默回落风险）。
- **结论**：`.js` 文件体为**纯 JSON 字面量**赋给 `window.__XINYU_STRATEGY__`；新增情绪 = 改词表 + 改本表，代码零改动。
- **已知代价**：新风险从"改代码忘同步"变成"**只改一个数据文件**"——由 `_test/strategy_check.py` 兜（键序一致 / 覆盖完备 / 反向不遗 / 危机话术与分类器提示词自洽），并用 `--selftest` 注入分叉证明判据非恒真。
- **重评触发条件**：若共情链路要做"多步策略"（识别→澄清→反映→行动建议）而非单轮模板，本表结构需升级为带阶段/顺序的流程定义。

### 决策 #8 —— provider 适配层：环境变量别名（而非 provider 注册表）

- **背景**：对标三家均多模型；心屿只有 `DEEPSEEK_*`。
- **结论**：`LLM_BASE/LLM_MODEL/LLM_KEY` 为通用名，`DEEPSEEK_*` 保留兼容，Java 侧用 Spring **嵌套占位符** `${LLM_BASE:${DEEPSEEK_BASE:默认}}`，Function 侧用 `||` 短路。**不写注册表代码**——因为上游本来就是 OpenAI 兼容，端点/模型名就是全部差异。
- **已知代价**：非 OpenAI 兼容协议（如 Anthropic 原生 `/v1/messages`）仍接不进来；届时才需要真正的 provider 适配层。
- **前端配套**：设置面板加 5 家快捷预设（只填 base+model，Key 必须用户自己填，前端永不代存）。

### 决策 #9 —— 长会话窗口化：DOM 上界 + 配额展开（而非虚拟滚动）

- **背景**：LobeChat 用 `react-virtuoso`；心屿 `#chat-log` 单调 append。
- **结论**：上界 60 条 + 「展开较早」每次放回 20 条并**临时抬高配额**（否则放回即被同一上限裁回 = 等于没展开，实测踩坑并已修），新消息到达即收回上界。零依赖，符合"零构建"约束。
- **已知代价**：不是真正的虚拟化——无滚动位置锚定，>500 条时反复展开会有视觉跳动。列入 ROADMAP 计划 #2 赛后再做。

### 决策 #10 —— 情绪判定：本地微调模型腿 + 三级共识路由（AIC 补短板轮，2026-10-08/09）

- **背景**：AIC"AI+软件创新"赛道评估指出短板「算法层是规则引擎 + API 调 DeepSeek，无训练/微调」。决策 #1 的重评触发条件（需要本地情绪模型/微调）正式命中 → 按预设路径「**Java 管业务 API + Python 管模型服务**」执行，不用 Java 硬啃 AI 生态。
- **选项**：
  | 方案 | 结果 |
  |---|---|
  | ONNX 内嵌 Java 推理 | ❌ tokenizer Java 化工程量大、训练仍要 Python，双栈维护更差 |
  | 模型高置信直采信（conf≥0.85 主判） | ❌ 设计了但被实测否决：73 条评测集上模型单腿仅 86.6% < 词典 98.6%，主判切换会倒退 |
  | **共识路由（选定）** | 危机规则短路（永不概率化）→ 词典+模型共识采信/分歧词典裁决 → route=lexicon 保留旧双路 |
- **结论**：三级路由 `auto`（默认）+ `lexicon`（旧语义）双模式，`xinyu.emotion.model-url` 留空 = 行为与引入前逐字节一致。模型 = `hfl/chinese-roberta-wwm-ext` 本机微调（3622 条：SMP2020-ECDT 镜像映射底料 1500 + DeepSeek 生成校园域对抗样例 2122，self-consistency 过滤）。数据/训练/服务/评测全链路在 `ml/`。
- **已知代价**：① 演示机多起一个 Python 进程（`ml/start_all.ps1` 一键起）；② 模型单腿在词典主场（73 条人工评测集）86.6% < 词典 98.6%，盲测集（生成域）则反转（模型 92.2% >> 词典 46.3%）——**域偏移未解决前模型不接管主判**，route 开关保留切换能力；③ 盲测暴露词典危机词表改写盲区（6 条改写危机仅命中 2）→ 登记后续 P0。
- **实测（2026-10-09）**：101 JUnit 全绿（LINE 97.00%/BRANCH 95.21%，guard PASS）；73 条路由层**离线/在线双口径 98.6% 恒等**（永不倒退结构保证 + 在线分歧升 LLM 方案实测倒退 94.5% 已否决）；盲测四路：词典 46.3%/模型 92.2%(26.6ms)/LLM 97.0%(647ms)/路由 46.3%（`交付物/AIC/盲测四路对比报告.md`）。
- **踩坑登记**（一手实测进排障表族）：① JDK HttpClient 默认 HTTP_2 发 `Upgrade: h2c` → uvicorn(h11) 丢 body → FastAPI 422，**强制 `.version(HTTP_1_1)` 一次修掉**；② 回环调用须 `.proxy(NO_PROXY)`（系统代理会转手本机请求）；③ Start-Process 子进程对 `$env:` 继承不可靠 → model-url 走命令行参数（`start_all.ps1` 已修）。
- **重评触发条件**：真实用户输入域的公允基准（非词典主场、非生成主场）上模型 ≥ 词典时，route 切模型主判 + 词典兜底；危机词表扩充后重测盲测危机召回。

### 决策 #11 —— 语音合成引擎：本机开源神经引擎优先 + 浏览器兜底 + 字幕终兜（r118，2026-10-12）

- **背景**：r116 裁定「音色 = 浏览器自带 + 变调扩展，零密钥零付费」，实测本机只拿得到 `Microsoft Huihui`（传统合成音，机械感强）。老大 2026-10-12 重发语音通话五条需求，第①条明确要求「多种音色丰富的机器人语音引擎…清晰自然、无明显机械感」⇒ 原裁定不满足该条，触发变更。
- **选项**（三模型同机实测对比，判据先自证：对每个候选造「同容器 4kHz 精确砖墙」+「8k 上采样进该容器」两条阴性对照，砖墙侧 >8k 能量归 0、拐点塌到 ~4.1kHz，真实候选高出 15–25 dB）：

  | 模型 | 采样率 | 4–8k 能量 | 说话人 | 加载 | 单句 RTF | 结论 |
  |---|---|---|---|---|---|---|
  | `vits-zh-aishell3` | **8000** | **0%**（能量 100% 落 4k 以下） | 174 | 1.10s | 0.15–0.24 | ❌ 电话级带宽，「清晰自然」不成立——先按它跑通过，是实测把它否掉的 |
  | **`sherpa-onnx-vits-zh-ll`（选定）** | 16000 | 0.98%（相对语区 −6.3 dB，无砖墙） | 5（含男声，F0 246/219/103 Hz） | 0.83–1.01s | 0.33–0.47（2 线程内不超线） | ✅ 过带宽硬门槛 + 保住多音色 |
  | `vits-melo-tts-zh_en` | 44100 | 0.89%，>8k 0.10%（拐点 11k） | **1** | 3.3–4.7s | 0.53–0.57 ⚠️ 需 4 线程才压到 0.34 | ❌ 带宽最漂亮但单说话人，会直接删掉「多音色」这个卖点；且其 int8 是 133 字节 LFS 指针，不可用 |

- **结论**：浏览器 `speechSynthesis` 降为**兜底腿**，首选 = `sherpa-onnx-vits-zh-ll`，经 `ml/tts_server.py`（FastAPI，**只绑 127.0.0.1:8320**，沿用决策 #10 的「Python 管模型服务」产线）暴露 `/health`（自证 loaded/numSpeakers/sampleRate/loadMs）与 `/tts`（POST 一句 → WAV）。音色目录把本机说话人并进同一张表，通话面板**可直接切换**；引擎不在/探测失败 ⇒ 逐字回到改动前的浏览器路径，浏览器也没有语音合成 ⇒ 只出字幕并把整轮跑完。
- **三层开关**（与 J4 记忆、`emotionRemote` 同口径，不得混为一谈）：① 代码层 `cfg.localTts === true` 才探测，**默认关**；② 本地演示层 `src/js/demo-config.js`（已 ignore）置 true；③ 公网层 `deploy/xinyu/js/demo-config.js` 刻意不含 ⇒ **公网面一次请求都不发**。第③条不是偷懒：失败连接会在 console 留 `ERR_CONNECTION_REFUSED`，会打破 `public_check` 的 `CONSOLE_ERRORS:0` 判据；判据 C15 钉的就是「默认态 0 探测」这半条。
- **已知代价**：① 演示机多起一个 Python 进程（venv `D:/xinyu-ml/tts-venv`，模型 `D:/xinyu-ml/tts/sherpa-onnx-vits-zh-ll`，均不入库）；② 本机引擎首声比浏览器慢——一句实测 0.73–1.32s，而 `speechSynthesis` 近乎即时，所以**它是音质换延迟，不是全面更好**；③ sidecar 只在本机，公网访客拿不到 ⇒ 评委在手机上听到的仍是浏览器音色，除非他们本机也起服务；④ 中英混说在 zh-ll 上会丢词（引擎自报 `Ignore OOV 'laptop'`），只有被否的 melo 真读英文。
- **实测（2026-10-12）**：`_test/voice_call_check.py` **C腿=15/15 rc=0**；C15 实测「默认态 0 探测 / 本机态 8 档进目录 / 2 次找 sidecar 要音频 / 0 次浏览器合成 / 通话中切说话人 0→5 生效」。sidecar 一手回执：`/health` 报 5 说话人 · 16000Hz · 加载 812ms；`POST /tts` 三个说话人各出 1.6–2.4s **非静音** WAV（RMS 0.054–0.069），4–8k 能量占比 27–44%（对照 aishell3 的 0%）；边界三例 坏 Origin 403 / 空文本 400 / 超长 413 各验一次。**⚠️ 未验**：主观听感（无真人盲听）、真机连说 30 分钟（本机无真麦克风）。
- **重评触发条件**：① 需要公网访客也拿到神经音色 ⇒ 得起一个真有出网与算力的托管 TTS（届时才涉及付费/密钥，须另立决策）；② 需要中英混说 ⇒ 回看 melo 或换带中英多说话人的模型；③ 首声延迟成为主要矛盾 ⇒ 把 sidecar 改成分块流式（注意 sherpa-onnx 1.13.8 的 `generate()` 回调**返回值语义与 docstring 相反：实测返 1 才继续**，上一轮就是被这条把音频静默截断的）。
