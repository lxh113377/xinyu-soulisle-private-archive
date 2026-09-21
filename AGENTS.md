# AGENTS.md — 陪聊

> 自动生成: 2026-09-22 00:47:31


---

# 01 - 项目目标

## 项目名称
心屿 SoulIsle（原"陪聊"）

## 一句话描述
对话陪聊 + 情感陪伴的 AI 网页应用：以滚轮驱动的 3D 情绪叙事页（WebGL+GSAP）承载真实 AI 共情链路。

## 核心价值
- 解决：大学生/年轻群体情绪倾诉需求与"陪伴产品只聊天不感知情绪"的落差
- 差异：情绪识别（本地引擎）→ 共情策略 → 在线 LLM 生成 → 情绪可视化（3D 星雾变色）的闭环，而非套壳聊天框
- 给谁用：高校学生、独居青年；场景=互联网+智能终端

## 当前阶段目标
- [x] 可运行原型（本地实测：console 0 报错、5 幕叙事、情绪探针/对话/降级/危机转介/曲线全断言通过）
- [ ] 按官方 9 项清单完成《应用方案》PDF（≤20 页）
- [ ] 部署稳定在线链接（须活过 2026-10 复赛 + 11 决赛）
- [ ] 2026-09-30 前官网报名+提交（截止即锁团队信息）

## 已完成目标
- [x] 2026-09-19 评审基线：官方评分规则逐字核验（组委会发〔2026〕29号：创新30/技术30/实用20/体验10/展示10）

---

# 02 - 仓库结构

```
├── .codebuddy/
├── .wrangler/
│   └── cache/
│       └── wrangler-account.json
├── _test/
│   ├── _shots/
│   │   ├── dual_mixed-contrast.png
│   │   ├── dual_mixed-similar.png
│   │   ├── dual_single.png
│   │   ├── lightshow_after.png
│   │   ├── lightshow_before.png
│   │   ├── lightshow_blackout.png
│   │   ├── lit_multi.png
│   │   └── lit_single.png
│   ├── browser_check.py
│   ├── cors_probe.py
│   ├── emotion-eval-dataset.json
│   ├── emotion_eval.js
│   ├── j2_chat_contract.py
│   ├── j4_memory_check.py
│   ├── lightshow_check.py
│   ├── online_check.py
│   ├── pixel_dual_check.py
│   ├── public_check.py
│   ├── screenshots.py
│   └── screenshots_online.py
├── deploy/
│   ├── .wrangler/
│   │   ├── cache/
│   │   │   ├── pages.json
│   │   │   └── wrangler-account.json
│   │   └── tmp/
│   ├── cloudbase/
│   │   ├── functions/
│   │   │   └── chat/
│   │   └── cloudbaserc.json
│   ├── functions/
│   │   └── api/
│   │       └── chat.js
│   ├── xinyu/
│   │   ├── assets/
│   │   ├── css/
│   │   │   └── style.css
│   │   ├── js/
│   │   │   ├── app.js
│   │   │   ├── chat-agent.js
│   │   │   ├── demo-config.js
│   │   │   ├── emotion-engine.js
│   │   │   ├── memory-store.js
│   │   │   ├── scroll-story.js
│   │   │   └── three-scene.js
│   │   └── index.html
│   └── wrangler.toml
├── server/
│   ├── data/
│   │   └── xinyu.mv.db
│   ├── src/
│   │   └── main/
│   │       ├── java/
│   │       └── resources/
│   ├── Dockerfile
│   └── pom.xml
├── src/
│   ├── assets/
│   ├── css/
│   │   └── style.css
│   ├── functions/
│   │   └── api/
│   │       └── chat.js
│   ├── js/
│   │   ├── app.js
│   │   ├── chat-agent.js
│   │   ├── demo-config.js
│   │   ├── emotion-engine.js
│   │   ├── memory-store.js
│   │   ├── scroll-story.js
│   │   └── three-scene.js
│   └── index.html
├── 交付物/
│   ├── _参考资料-非提交/
│   ├── iCAN评审/
│   │   ├── 截图/
│   │   │   ├── 01-第一幕-相遇.png
│   │   │   ├── 02-第二幕-情绪探针.png
│   │   │   ├── 02-第二幕-情绪读数.png
│   │   │   ├── 03-第三幕-AI对话.png
│   │   │   ├── 04-第四幕-情绪曲线.png
│   │   │   ├── 05-在线模式-徽章与体验条.png
│   │   │   ├── 06-双路情绪探针-词典与LLM分歧.png
│   │   │   └── 07-在线对话-双路证据标签.png
│   │   ├── 01-评分维度与权重-实证.md
│   │   ├── 02-逐维度诊断报告.md
│   │   ├── 03-优化优先级与实施路径.md
│   │   ├── 04-答辩逻辑与仿真数据风险应对.md
│   │   └── 05-获奖作品差距分析.md
│   └── 提交包/
│       ├── 应用方案大纲.md
│       ├── 提交清单与验收状态.md
│       └── 演示视频脚本.md
├── .aiexclude
├── AGENTS.md
└── README.md
```

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

---

# 03 - 技术栈

（未检测到技术栈配置文件）

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

---

# 04 - 核心文件地图

### 入口文件:
  - `deploy/cloudbase/functions/chat/index.js`
### 文档: `README.md`

## 核心逻辑文件
- `` — 

## 配置文件
- `` — 

---

# 05 - 功能状态

## ✅ 已实现
- [x] 3D 情绪星雾 — Three.js 粒子星云，滚动驱动镜头；WebGL 不可用降级 CSS 渐变

## 分卷目录
- **卷1** `05-feature-status.part1.md` — 05-feature-status 分卷（R199 自动拆卷）


---

# 06 - 已知约束

## 已知 Bug

## 技术债

## 红线（不能改）
- 

## 性能/兼容性约束
- 

## 环境隔离（R196，init 必填）
- env_mode: development（枚举：development / staging / production）
- 红线：dev/staging 禁止连接 production 数据库与 API key
- production 操作前检查：近期备份存在（archive/ 或 DR 快照 ≤7 天）+ 密钥不复用
- 保护文件 .env.prod / .env.production 禁止入库（.gitignore 已含规则）

## 评测集隔离（R196）
- 测试专用文件清单：（如 eval/testset_provenance.json / blindset / frozen）
- 红线：训练/生产数据禁止写入测试专用文件；新增评测数据先登记来源（provenance）

---

# 07 - 下一步

## 🎯 主线目标 — Java 全栈改造（2026-09-20 老大定方向）

### 分阶段（每阶段都要能跑、能回归，禁止一次性推倒重写）
- [x] **J1 骨架** ✅ 2026-09-21：`server/`（Maven 3.9.9 + Spring Boot 3.2.5 + JDK 17）+ `/api/health` + 托管现有前端静态页（**直读 `src/` 权威源，零副本**）→ `java -jar server\target\soulisle-server.jar --server.port=8123` 实测 `status=UP` / `webRoot` 解析到项目 `src/` / `indexFound=true` / `vendorFound=true`，首页与 `js`、`css`、`vendor` 全 200；`_test/browser_check.py` **原样复用（同端口 8123）ALL-ASSERT-PASS**。对照组：换回旧 `python -m http.server` 同为 4 条 `ERR_CONNECTION_REFUSED` ⇒ 该错误出自脚本自注入的不可达端点 `127.0.0.1:18123`（离线降级用），与 Java 服务端无关
- [x] **J2 API 契约对齐** ✅ 2026-09-22：`POST /api/chat` 与 v1 **1:1**（契约实读自 `deploy/functions/api/chat.js` + `src/js/chat-agent.js:25-43`，非凭记忆）。请求认 `{messages,temperature,max_tokens}`；**上游响应逐字透传**（含 status）；错误体与 v1 完全一致（`no-key` 500 / `bad-json` 400 / `upstream-nonjson` / `upstream-error` 502），且**判定顺序一致**（先查 key 再解析 body）。验收：`_test/j2_chat_contract.py` **J2-CONTRACT-PASS**（A 组走 Java 965ms 在线 / B 组不可达端点 3ms 回落离线，单变量对照）+ curl 三例（no-key 500、bad-json 400、真实调用 200 中文无损）+ `browser_check.py` ALL-ASSERT-PASS
- [x] **J3 情绪引擎 Java 化** ✅ 2026-09-22：`engine` 包（`EmotionLexicon` 词表逐字搬 / `EmotionEngine.scan` 同公式 / `EmotionClassifier` 双路）+ `POST /api/emotion` + `GET /api/emotion/eval`。**双端逐项对账完全一致**：Java 侧 `94.4%` / `crisis_recall 3/3` / `per_class` 七类全同 / `misses` 两条逐字相同（JS 侧 `node _test/emotion_eval.js` 为对照）。危机命中**不调 LLM**（实测 `llm=null`）；分歧案例 `lex anger 0.625 vs llm sadness 0.75 → 采信 LLM` 与前端路径一致

## P0 — 必须做

- [ ] 🔴 **iCAN 提交硬截止 2026-09-30**（剩 8 天；截止即锁团队信息）：官网报名 + 提交。缺件风险 = 《应用方案》PDF（≤20 页），详见 `part6`
- [ ] **J3/J4 变现三件**（优先级高于继续加功能）：① 前端切 `/api/emotion`（消除情绪引擎"两份真相"）② 默认开 `cfg.remote`（跨设备记住你）③ fat jar 部署到国内可达机器（摆脱 CloudBase 中间页），详见 `part6`
- [ ] ⏸ **PDF 起草（冻结待解冻）**：与老大 09-19「视频/PPT/PDF 不管」指令冲突，需一句话解冻，详见 `part6`

## 分卷目录

- **卷1** `07-next-steps.part1.md` — 已完成条目（历史）
- **卷2** `07-next-steps.part2.md` — 历史续卷
- **卷3** `07-next-steps.part3.md` — 历史续卷
- **卷4** `07-next-steps.part4.md` — 历史续卷
- **卷5** `07-next-steps.part5.md` — P1 / P2 / 最近对话摘要
- **卷6** `07-next-steps.part6.md` — **P0 未完成项完整描述**（iCAN 截止 / J3-J4 变现 / PDF / CloudBase 决策）
- **卷7** `07-next-steps.part7.md` — P0 已完成项 + 改造不变量 + J4/J5 详情


---

# 08 - AC-OBS 验收标准

## 验收标准列表

### 前端叙事与可视化（证据来源：`_test/browser_check.py` / `pixel_dual_check.py` / `lightshow_check.py`）

- [x] AC-OBS-01: 3D 情绪星雾渲染且 WebGL 不可用时可降级 → `browser_check.py` 断言 `typeof THREE`/`gsap`/`ScrollTrigger` 已加载、`#gl` 活跃、五幕叙事存在 | 测试输出
- [x] AC-OBS-02: 每句对话按其情绪点亮星雾并持久化 → 同套件断言 `LIT: init=0 after1=5 after2=17 reload=17 clear=0` | 测试输出
- [x] AC-OBS-03: 双色星雾在**屏幕像素上**可分辨 → `pixel_dual_check.py` 判据**双条件**：两簇中心色距 > 0.25 **且** 少数簇占比 > 0.10；并带**单色对照**（对照不通过才算判据有效） | 测试输出
- [x] AC-OBS-04: 一键点亮是"清屏 + 播放过程"而非瞬间切换 → `lightshow_check.py` 采**黑屏关键帧**有效像素 = 0（证明清屏真发生）+ 结束后六色各占 8.4%~20.9% | 测试输出
- [x] AC-OBS-05: 叙事卡片随滚动淡入淡出且"明显可感" → `browser_check.py` 断言 `SCROLL_FADE: enter<0.6 / center>0.9 / leaving<0.5 且 <center` | 测试输出
- [x] AC-OBS-06: 危机信号最高优先级拦截并推送求助热线 → 同套件断言 `CRISIS: True` | 测试输出

### 后端服务（v2 Java 全栈，证据来源：`_test/j2_chat_contract.py` / `j4_memory_check.py` / `public_check.py` + curl）

- [x] AC-OBS-07: 服务端托管前端静态页且能自证源命中 → `GET /api/health` 返回 `status=UP` + `webRoot` 绝对路径 + `indexFound=true` + `vendorFound=true`；首页与 `js/css/vendor` 均 200 | API响应
- [x] AC-OBS-08: `POST /api/chat` 与 v1 契约 1:1（前端零代码改动即可切换） → `j2_chat_contract.py` **单变量对照**：A（proxy=Java）在线、B（不可达）回落离线；curl 补验 `no-key` 500 / `bad-json` 400 且**判定顺序与 v1 一致** | 测试输出 + API响应
- [x] AC-OBS-09: 情绪引擎评测可现场复跑且双端一致 → `GET /api/emotion/eval` 返回 `accuracy=94.4%` / `crisis_recall=3/3`，且 `per_class`、`misses` 与 `node _test/emotion_eval.js` **逐项相同** | API响应 + 测试输出
- [x] AC-OBS-10: 情绪记忆真落库（跨浏览器、跨重启不丢） → `j4_memory_check.py` **核心断言**：清空 `localStorage` 后刷新星图仍点亮；`GET /api/memory/stats` 计数正确；重启服务后计数不变 | 数据库查询 + 测试输出
- [x] AC-OBS-11: 密钥零落前端、零入库 → `public_check.py` 报 `KEY_LEAK: False`；`git grep -E "sk-[A-Za-z0-9]{20,}" HEAD` 0 命中 | 测试输出
- [x] AC-OBS-12: 可选鉴权可开可关且边界正确 → 无 token 时全放行 200；有 token 时 无头 401 / 错头 401 / 对头 200，且 `/api/health` 与静态页**始终放行** | API响应

## 已识别的判据误报（保留记录，不修改数据）

- ⚠️ `handoff.py review` 的「交叉一致性」会对 05 已完成项与 07 P0 未勾选项做**关键词重叠**匹配。
  2026-09-22 实测报出 5 条「05 已完成 X ↔ 07 P0 未勾选 J3/J4 变现」—— 核对后确认**全部为误报**
  （05 里的条目是"3D 情绪星雾/点亮/对话坞"等已实现功能，与 07 的"J3/J4 变现"是两件事，仅因命中同名词而挂钩）。
  处置：**判定为判据假阳性，不改 05/07 以求绿**（同 R263 精神：先证判据再动数据）。

- ⚠️ `handoff.py sync` 的自动检测对本项目结构**部分失效**（实测 2026-09-22）：02 目录树可用但含 `.codebuddy/`/`.wrangler/` 等 ignore 目录；03 报「未检测到技术栈配置文件」（因 `pom.xml` 在 `server/` 子目录，sync 只扫项目根）；04 会把 `deploy/cloudbase/functions/chat/index.js` 当入口（真入口是 `src/index.html` + `SoulIsleApplication.java`）。
  处置：**以手工区内容为准**，自动块仅作参考；已在 02/03/04 的手工区加注记说明。

