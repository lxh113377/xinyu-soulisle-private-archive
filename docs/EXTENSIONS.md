# 心屿 SoulIsle 扩展手册（EXTENSIONS）

> 解决对标 G6"有机制无文档"：扩展点本来就存在，本文件让它们可发现、可操作。每节含位置、改法、验证。

## 1. 情绪词表（SSOT 单一真相源）

- 只改一处：`src/data/emotion-lexicon.js`。JS 与 Java 各自加载同一文件（`EmotionLexicon.java` 零硬编码，加载失败 fail-fast）。
- 验证：`python _test/engine_consistency_check.py`（三层：词表结构/73 条逐条/汇总指标）。

## 2. 共情策略

- `src/data/emotion-strategy.js`（前端文案/降级模板）+ `server/.../safety/SafetyGuard.java`（危机词拦截）。
- 注意两套词表分工不同：危机短路词（SafetyGuard 输出侧）≠ 情绪词典危机词（输入侧），不得互相冒充。

## 3. LLM 上游切换（OpenAI 兼容）

- 服务端 `server/.../llm/LlmProxy.java`（JDK 内置 HttpClient，零额外依赖），密钥只读环境变量 `DEEPSEEK_KEY`。
- 换上游 = 换 baseURL + key 的部署配置，不改调用形状；`stream:true` 且上游 SSE 即直通。

## 4. 记忆 provider（三层开关）

- 代码层 `src/js/memory-store.js`（`cfg.remote===true` 才发远端，失败熔断 `remoteDown`）；本地演示 `src/js/demo-config.js: remote:true`；公网 `deploy/xinyu/js/demo-config.js` 刻意不开。
- 服务端 `MemoryService` + `chat_message/emotion_record` 两表（默认 H2 file，可切 MySQL 8）。

## 5. 部署目标与第三方集成

- 本地：`java -jar server/target/soulisle-server.jar`（工作目录=项目根，直读 `src/`）。
- 公网：Cloudflare Pages Function（`/api/chat`）+ CloudBase 云函数（降级/对比路径）；Dockerfile 已交付（本机未装 Docker，镜像未实测）。
- 第三方：DeepSeek（OpenAI 兼容）；Web Speech API 语音输入；Three.js/GSAP 本地 vendor（无 CDN 依赖）。
