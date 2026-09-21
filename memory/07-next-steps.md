# 07 - 下一步

> 本文件记录下一步行动项，按优先级排序。
> **⚠️ 新对话恢复上下文入口。P0 必须永远有一条可执行指令。**

## 🎯 主线目标 — Java 全栈改造（2026-09-20 老大定方向）

> 把当前「纯静态前端 + Serverless 函数（Cloudflare Pages Function / CloudBase 云函数）」演进为 **Java 全栈**：
> Spring Boot 单体承载全部业务 API 与记忆持久化，**前端保留现有 Three.js 叙事页且零改动**（只换 baseURL）。
> 选型为**假设值**，动手前需老大确认（见 `03-tech-stack.md` 目标技术栈表）。
> 环境实证：本机 JDK 17 = `C:\Program Files\Eclipse Adoptium\jdk-17.0.20.101-hotspot`（JDK 8 是课程作业用，勿混）。
> Maven 3.9.9 = `%USERPROFILE%\.local\maven\apache-maven-3.9.9\bin\mvn`（2026-09-21 新装，**不在 PATH**，需临时加 PATH 或用绝对路径）；`~/.m2/settings.xml` 已配腾讯云镜像加速。
> ⚠️ **默认 `JAVA_HOME` 实测 = JDK 8**（`…jdk-8.0.504.1-hotspot`）→ 每次构建/启动前必须显式 `$env:JAVA_HOME="<JDK17路径>"`，否则 Spring Boot 3 直接编译失败。

### 分阶段（每阶段都要能跑、能回归，禁止一次性推倒重写）
- [x] **J1 骨架** ✅ 2026-09-21：`server/`（Maven 3.9.9 + Spring Boot 3.2.5 + JDK 17）+ `/api/health` + 托管现有前端静态页（**直读 `src/` 权威源，零副本**）→ `java -jar server\target\soulisle-server.jar --server.port=8123` 实测 `status=UP` / `webRoot` 解析到项目 `src/` / `indexFound=true` / `vendorFound=true`，首页与 `js`、`css`、`vendor` 全 200；`_test/browser_check.py` **原样复用（同端口 8123）ALL-ASSERT-PASS**。对照组：换回旧 `python -m http.server` 同为 4 条 `ERR_CONNECTION_REFUSED` ⇒ 该错误出自脚本自注入的不可达端点 `127.0.0.1:18123`（离线降级用），与 Java 服务端无关
- [x] **J2 API 契约对齐** ✅ 2026-09-22：`POST /api/chat` 与 v1 **1:1**（契约实读自 `deploy/functions/api/chat.js` + `src/js/chat-agent.js:25-43`，非凭记忆）。请求认 `{messages,temperature,max_tokens}`；**上游响应逐字透传**（含 status）；错误体与 v1 完全一致（`no-key` 500 / `bad-json` 400 / `upstream-nonjson` / `upstream-error` 502），且**判定顺序一致**（先查 key 再解析 body）。验收：`_test/j2_chat_contract.py` **J2-CONTRACT-PASS**（A 组走 Java 965ms 在线 / B 组不可达端点 3ms 回落离线，单变量对照）+ curl 三例（no-key 500、bad-json 400、真实调用 200 中文无损）+ `browser_check.py` ALL-ASSERT-PASS
- [x] **J3 情绪引擎 Java 化** ✅ 2026-09-22：`engine` 包（`EmotionLexicon` 词表逐字搬 / `EmotionEngine.scan` 同公式 / `EmotionClassifier` 双路）+ `POST /api/emotion` + `GET /api/emotion/eval`。**双端逐项对账完全一致**：Java 侧 `94.4%` / `crisis_recall 3/3` / `per_class` 七类全同 / `misses` 两条逐字相同（JS 侧 `node _test/emotion_eval.js` 为对照）。危机命中**不调 LLM**（实测 `llm=null`）；分歧案例 `lex anger 0.625 vs llm sadness 0.75 → 采信 LLM` 与前端路径一致
- [x] **J4 持久化** ✅ 2026-09-22：`chat_message` / `emotion_record` 两表（MyBatis-Plus 3.5.7 + **H2 file 默认 / MySQL 8 可切**）+ `/api/memory/**` CRUD。实测**跨重启持久**（2 emotion / 2 message 重启后仍在）、`DELETE` 清除 `removed=4` 且会话隔离。前端接入为**可选项**（`cfg.remote===true`，默认关闭）：`_test/j4_memory_check.py` **J4-MEMORY-PASS** —— 核心断言「**清空 localStorage 后刷新星图仍点亮 6 颗**」证明数据真来自数据库；对照组默认关闭时服务端 0/0（判据非恒真）
- [x] **J5 安全与部署** ✅ 2026-09-22：密钥全外置（`DEEPSEEK_KEY` 环境变量，零落盘零入库）；可选鉴权 `XINYU_API_TOKEN`（默认空=放行，非空则 `/api/**` 除 `/api/health` 需 `X-Xinyu-Token`，实测 无头401/错头401/对头200/health 与静态页放行）；`server/Dockerfile` 已交付。⚠️ **Docker 本机未安装 → 镜像构建未实测**（不谎称验证过）
- 部署形态说明：J5 采用**轻量 token 过滤器**而非引入 Spring Security 全家桶（演示场景够用 + 依赖最小化 + 默认关闭零影响）。若后续需要多用户/角色，再评估升级

### 改造期间的不变量（违反 = 回滚）
- 密钥零落前端、零入库（`src/js/demo-config.js` 已在 .gitignore 排除）
- v1 的 Cloudflare / CloudBase 双线**保留为降级与对比路径**，不删
- 每阶段收尾必须跑 `_test/browser_check.py` 确认前端未回归，并在 `05-feature-status.md` 标状态

## P0 — 必须做
- [x] ~~版本控制基线~~ ✅ 2026-09-21 r2（纪律 #20 四步全达标）：首提 `8c4f59d`（73 文件，`--file` 白名单禁 `add -A`）→ 私有远端 `https://github.com/lxh113377/xinyu-soulisle-private-archive` → push → `rev-parse HEAD` == `ls-remote origin main` == `8c4f59d76f3e6ce39b9f054a182cdd3bd8c9f30b`；密钥零入库（`git grep -E "sk-[A-Za-z0-9]{20,}" HEAD` = **0 命中**）。注意：`gh` 在 PowerShell 下因**无扩展名**被判为"文档"无法执行，**须经 Git Bash 调用**
- [x] ~~J2 API 契约对齐~~ ✅ 2026-09-22（详见分阶段表）
- [x] ~~J3 / J4 / J5~~ ✅ 2026-09-22 全部完成（详见分阶段表）→ **Java 全栈主线 J1–J5 已贯通**
- [ ] **J3/J4 变现（优先级高于继续加功能，2026-09-22 校准后确立）**：现状实测 —— 前端 **0 处**调用 `/api/emotion`（仍用本地 `src/js/emotion-engine.js`）、**0 处** `remote:true`（J4 默认关闭）⇒ **J3/J4 目前对演示零可见影响，是"能力就位、生产未启用"**。三件：
  1. 前端切到 `/api/emotion` —— **消除"情绪引擎两份真相"隐患**（`emotion-engine.js` 与 `EmotionLexicon.java` 改一边忘一边就分叉）；必须先跑 `_test/emotion_eval.js` 双端对账 + `browser_check.py` + `pixel_dual_check.py`
  2. 默认开 `cfg.remote` —— 让"跨设备记住你"成立（演示才能讲）；须先跑 `_test/j4_memory_check.py` + `browser_check.py`
  3. fat jar 部署到国内可达机器 —— 摆脱 CloudBase 首访中间页；Dockerfile 已交付但**本机无 Docker，镜像未实测**
- [ ] 🔴 **iCAN 提交硬截止 2026-09-30**（今天 09-22，剩 8 天；截止即锁团队信息）：官网报名 + 提交。缺件风险：官方要《应用方案》PDF（≤20 页），而该项此前按老大 09-19「视频/PPT/PDF 不管」指令被冻结 —— 需一句话解冻即开做
- [x] ~~CloudBase 国内线决策~~ ✅ 2026-09-22 老大定：**接受中间页，仅作备用**（零成本，保持现状）。注意：CloudBase 云函数的 Key 仍是旧值（CLI 无 `fn env push`，只能控制台改）；若旧 Key 被平台作废，国内备用线会失效，需在控制台同步新 Key
- [x] ~~云端密钥轮换~~ ✅ 2026-09-22：新 Key 实测 `200 OK` → `wrangler pages secret put DEEPSEEK_KEY`（**wrangler@3 报错，@4 成功**）+ `pages deploy` 重部署使其生效（secret 需新部署才绑定）→ 生产 `PUBLIC-ONLINE-ALL-PASS`（在线 AI 1206ms、`KEY_LEAK: False`）
- [x] ~~部署在线演示~~ ✅ 2026-09-19 Cloudflare：**https://xinyu-soulisle.pages.dev** （Pages + Function 代理 /api/chat，密钥在 env，前端零密钥）；✅ 2026-09-20 加国内线：**https://qwer-d4gf2r76o8829463b-1458054906.tcloudbaseapp.com**（CloudBase 静态托管 + 云函数 chat，环境有效期至 2027-03-14）。两端均实测 PUBLIC-ONLINE-ALL-PASS；前端 demo-config 按域名自适应指向对应代理
- [ ] 🔴 **待老大决策**：CloudBase 测试域名首访有「风险提醒」中间页（点一次放行；官方无免备案开关，需绑 ICP 备案自定义域名才能去掉，且默认域名有风控关停风险）。选项：①接受中间页并把 CloudBase 仅作备用（零成本，当前状态）②办域名+ICP 备案后绑自定义域名（约 1–3 周，赶得上 10 月复赛）③撤回国内线，仅用 pages.dev
- [ ] ⏸ **已冻结（范围冲突待老大一句话解冻）**：起草《应用方案》PDF（大纲：交付物/提交包/应用方案大纲.md；AI核心作用章节可直接引用：双路情绪引擎实测分歧案例 + 词典层评测 94.4%/危机召回3/3 + **Serverless密钥隔离架构**，见 _test/emotion_eval.js / src/functions/api/chat.js）

## P1 — 应该做
- [ ] 情绪引擎评测集扩到 ≥60 条（当前36条、94.4%；剩2误判=真歧义类，可标注为"混合情绪"改评分口径为top-k命中）
- [ ] 语音输入真机验证（Web Speech API 代码已就位，msedge 实测需麦克风权限，演示前过一遍）
- [ ] DeepSeek Key 已出现在对话中——**建议到 platform.deepseek.com 轮换**，轮换后 `wrangler pages secret put DEEPSEEK_KEY` 更新 + 重部署

## P2 — 可以做
- [ ] 待老大决策（2026-09-21 提出）：`03-tech-stack.md` / `02-structure.md` 里的**目标技术选型**（如「前端置于 `src/main/resources/static/`」）在 J1 落地时被证明会造第三处副本同步点 → 是否给「规划中」条目统一加「待落地验证」标注，避免计划被当成事实
- [x] 多情绪混合展示：双色星雾 ✅ 2026-09-20 完成（沿螺旋 6 条交替色带做空间分离 + 同色系次色做色相分离 ≥100°，次情绪须达主情绪 40% 权重；常驻断言 = _test/browser_check.py 两条 + _test/pixel_dual_check.py 像素级三用例）
- ~~角色形象（VRM 或 SVG 表情脸）~~ ❌ 老大 2026-09-19 指示：不做，已从待办移除

## 最近对话摘要
- 2026-09-22 r2 — 老大「全部授权」+ 定 CloudBase 决策 + 给新 Key + 要求**完成 J3/J4/J5** → 主线 Java 全栈 J1–J5 **全部贯通**。要点：**J3** 词表逐字移植（注意 JS 里 `难受`/`不` 有重复项会被重复计分，必须原样保留否则对不上 94.4%），双端对账逐项一致；**J4** H2 file 默认/MySQL 可切，核心断言是「清空 localStorage 后刷新星图仍点亮」；**J5** 轻量 token 过滤器（不引 Spring Security）+ Dockerfile（Docker 未装未实测）。踩坑：① 我一度写出**重复的 `spring:` YAML 键**（SnakeYAML 会直接启动失败），读盘自查后合并 ② `wrangler@3` 报错、**`@4` 成功** ③ Pages **secret 需重新部署才生效** ④ 顺手修了 `src/js/demo-config.js` 缺 `!cur.proxy` 守卫的老坑（J2 踩到的就是它）。生产 `PUBLIC-ONLINE-ALL-PASS`。
- 2026-09-22 r1 — 老大「全部授权，继续执行未完成的任务」→ 完成 **J2**：`POST /api/chat` 与 v1 契约 1:1（契约实读自 `deploy/functions/api/chat.js` + `src/js/chat-agent.js:25-43`）。新增 `llm/LlmProxy.java`（JDK 内置 HttpClient，上游响应**逐字透传**）+ `api/ChatController.java`（no-key 500 / bad-json 400，判定顺序与 v1 一致）；密钥只走 `DEEPSEEK_KEY` 环境变量。**踩坑（判据差点恒真）**：首版验收脚本 A/B 两组都"在线" —— 根因是 `demo-config.js` 只在 `cfg.base` 与 `cfg.key` 都为空时才预置 Key，只设 `{proxy}` 会在 reload 后被硬编码 Key 覆盖，两组都走浏览器直连。修法 = 单变量对照（base/key 设无效值，只让 proxy 不同）⇒ A 在线 965ms 只可能来自 Java / B 3ms 回落离线 ⇒ `j2_chat_contract.py` J2-CONTRACT-PASS + `browser_check` ALL-ASSERT-PASS。同轮老大立规：**非破坏性步骤自动执行不要多问**（授权/继续/升级建议三类）。提交 `fd6804e` 已 push。
- 2026-09-21 r1 — 老大「继续执行未完成的任务」→ 接主线 **J1**，已完成（详见上方分阶段表）。动手前实测拦下三个阻塞：① Maven 未装（新装 3.9.9 到 `~/.local/maven`，配腾讯云镜像）② **默认 `JAVA_HOME` 是 JDK 8 而非 17**（构建必显式切换）③ **版本控制基线缺失**（0 commit + 无远端，纪律 #20 判 🔴）。设计取舍：静态页**不复制进 `src/main/resources/static/`**，改用 `spring.web.resources.static-locations=file:${XINYU_WEB_ROOT:./src/}` 直读权威源 —— 避免造出第三处副本同步点（已有 `src/` → `deploy/xinyu/` 一条同步红线）。验收：`/api/health` UP + 资源全 200 + `browser_check.py` 原样 ALL-ASSERT-PASS + python 服务对照组证明控制台错误与 Java 无关。`.gitignore` 增 `server/target/`。
- 2026-09-20 r16 — **方向定调**：老大要求把陪聊后续计划改为「**Java 全栈**」目标，已落进本文件「主线目标」章节（J1–J5 分阶段 + 不变量）。同轮补齐项目**版本控制基线**（此前唯一无 `.git`/`.gitignore` 的项目）：`git init -b main` + 新建 `.gitignore`（密钥 `src/js/demo-config.js` / `_test/cors_probe.py` / `.env*`；生成物 `__pycache__`、`_test/_shots/`；元数据 `.codebuddy/` 等），**未 commit**。
- 2026-09-20 r6 — 「越聊越点亮」星雾 + 底部对话坞（老大点子）：初始星雾全暗（极暗灰白微光轮廓），每句对话按其情绪点亮 1–8 颗星并持久化重放，清除数据即熄灭；第二幕探针 + 第三幕聊天融合为**底部常驻对话坞**（`#chat-dock`，可折叠、点叙事区自动收起）。为让"被点亮的星"看得见，`PointsMaterial` 换成 `ShaderMaterial` 支持逐粒子尺寸（暗星 0.05 / 点亮 0.22，实测有效像素 29 → 323）。踩坑：① 悬浮坞遮住第四幕清除按钮（已 padding 预留 + 自动收起 + 测试断言坞可收起）② 像素判据单比色距会被 1 像素噪点骗过 → 改双条件（色距 >0.25 且少数簇占比 >0.10）③ 次情绪必须入库否则重放少点。回归：browser_check（lit 0→5→17→刷新 17→清除 0）+ pixel_dual_check（多色 0.488/33.4% vs 单色 0.197/0.2%）双绿，console 0；deploy/xinyu 哈希全一致。
- 2026-09-20 r5 — 双色可分辨轮：老大反馈「双色看着像一个颜色」。根因=按**径向单调渐变**分色（内核主色→外晕次色），在 AdditiveBlending 下屏幕均值仍是单色；旧验证只看粒子数组 head/tail 色距（0.676）=内部数据不同≠屏幕看得出。修法：①6 条交替色带（软方波+纯色平台）取得空间分离；②`makeDistinct` 对同色系次色做色相分离（色相环距 <0.28 即旋开+提饱和）。验证=像素级 2-means（有效像素先证非空 1983/2306/2767；双色 0.522/0.384 vs 单色对照 0.088），常驻脚本 _test/pixel_dual_check.py + browser_check 两条断言全绿。同轮把上轮遗留的升级建议闭环：R255 落盘 A-memory-start 速查区第 ⑧ 条 + 版本历史 V10.52.0（rule_editor 补丁 6/6，镜像 SHA256 已同步，三门禁 mirror/noise/evolution 全 pass，提交 0002d3d）。部署副本 deploy/xinyu 哈希比对一致。
- 2026-09-19 r4 — 体验修复轮：①P2 双色星雾完成（内核主情绪/外晕次情绪，`EmotionEngine.secondaryOf` 单一真相源 + 40% 权重阈值），角色形象按老大指示从待办删除；②修「滚到底再往上滚文案消失」——根因是每幕有两条补间争抢同一元素 y/opacity，scrub 淡出补间把未入场时的 opacity:0 记成起点，回滚即恢复错误值。改法=每幕合并为一条可逆 scrub 时间轴（start:top bottom → end:bottom top）；③文本框/面板透明度上调（--card .72→.40、chat-shell .6→.24、输入框 .06→.045 等，blur 提到 14px 保可读）。回归：browser_check 新增「回滚可见性 + 双色星雾」两断言 → ALL-ASSERT-PASS（ROLLBACK_OPACITY=1.0、MIST=焦虑内核+愉悦外晕、console 0）；deploy/xinyu 副本 SHA256 比对已同步归零（demo-config.js 按设计的公网代理版不参与同步）。
- 2026-09-19 r3 — 部署轮：Cloudflare Pages 项目 xinyu-soulisle 建成上线。踩坑：functions/ 放 build output 内不生效（GET /api/chat 返回 index.html、POST 405）→ 治本=deploy/ 下 functions 与 xinyu/ 同级 + wrangler.toml 声明 pages_build_output_dir → "Compiled Worker successfully" 出现即正常。密钥架构：DEEPSEEK_KEY 进 Pages secret（env），前端 proxy=/api/chat 同源代理，公网源码零密钥（扫描754KB 0命中）。验收：生产 curl 代理 OK + public_check.py PUBLIC-ONLINE-ALL-PASS（评委即见在线AI+双路分歧1287ms）+ 本地双套回归全绿。
- 2026-09-19 r2 — 老大给 DeepSeek Key，完成 M1：在线接入✅ + 双路情绪识别（词典快判+LLM精判，分歧采信LLM，实测"平静25% vs 低落85%"分歧案例）+ 评委体验模式（demo-config.js 预置Key+提示条+一键清除）；CORS 实测浏览器直连 DeepSeek 通过。追加：多轮上下文持久化、语音输入按钮、情绪曲线6色图例、评测集36条（72.2%→迭代词典→94.4%，危机召回3/3）。回归：browser_check（降级链路版）ALL-ASSERT-PASS + online_check ONLINE-ALL-PASS + console 0。老大指令：视频/PPT/PDF 不管，专注代码。
- 2026-09-19 — 从零建原型+评审5文档（详见交付物/iCAN评审/）

## 已完成
- [x] **J3/J4/J5**（2026-09-22）：情绪引擎 Java 化（双端对账 94.4%/3-3 一致）、持久化（H2/MySQL 可切，跨重启实测）、安全与部署（密钥外置 + 可选 token + Dockerfile）→ **Java 全栈主线贯通**
- [x] **J1 Java 骨架**（2026-09-21）：`server/` Spring Boot 3.2.5 + `/api/health` + 直读 `src/` 托管前端；`browser_check.py` 原样 ALL-ASSERT-PASS
- [x] 原型可运行 + 评审文档落盘（2026-09-19）
- [x] M1 LLM在线+双路+体验模式（2026-09-19，ONLINE-ALL-PASS）
- [x] 上下文持久化/语音输入/曲线图例/评测集（2026-09-19）
- [x] 「越聊越点亮」星雾 + 底部常驻对话坞（2026-09-20，browser_check + pixel_dual_check 双绿）
- [x] 静息更透 / 聚焦回弹的玻璃面板（2026-09-20，hover + focus-within 双态）→ **r7 已改为随滚动淡入淡出**
- [x] 一键点亮（六色各一簇）+ 滚动驱动透明度（2026-09-20，lightshow_check / browser_check / pixel_dual_check 三套全绿）
- [x] R256 落盘 A-memory-start（V10.53.0，固定悬浮层遮挡 + 像素判据双条件，三门禁全 pass）
- [x] R257 落盘 A-memory-start（V10.54.0，过程类动画须采关键帧 + 定时器 cancel + 结束/退出分路径，三门禁全 pass）
- [x] R258 落盘 A-memory-start（V10.55.0，全屏 canvas 像素判据须先隐藏浮层 UI + 恒保留未渲染对照组，三门禁全 pass）
- [x] R259 落盘 A-memory-start（V10.56.0，「实现了效果」≠「看得出效果」——可见性需求须在元素自身可见区间采样量化分布 + 弱化值设为常态，三门禁全 pass）
- [x] 一键点亮：UI 让位（showtime）+ 点得更满更散（1080 颗 / 覆盖 16/16 格 / 立体厚盘分布）
- [x] 播完停留不跳回 + 右下角「回到心屿（保留星雾）」按钮（2026-09-20，滚动/Esc 均不中断）
- [x] 文本框随滚动淡入淡出（2026-09-20 二轮：trigger 改挂面板自身 + 退场提前；实测 0.06→1.00→0.64→0，已入常驻断言）
- [x] 部署上线 xinyu-soulisle.pages.dev + 密钥隔离代理架构（2026-09-19，PUBLIC-ONLINE-ALL-PASS）
- [x] 双色星雾 + 滚动回滚可见性修复 + 玻璃面板透明度优化（2026-09-19，ALL-ASSERT-PASS）
