# 07-next-steps.part4.md

<!-- 本卷为 07-next-steps.md 的延续 -->

- 2026-09-22 r1 — 老大「全部授权，继续执行未完成的任务」→ 完成 **J2**：`POST /api/chat` 与 v1 契约 1:1（契约实读自 `deploy/functions/api/chat.js` + `src/js/chat-agent.js:25-43`）。新增 `llm/LlmProxy.java`（JDK 内置 HttpClient，上游响应**逐字透传**）+ `api/ChatController.java`（no-key 500 / bad-json 400，判定顺序与 v1 一致）；密钥只走 `DEEPSEEK_KEY` 环境变量。**踩坑（判据差点恒真）**：首版验收脚本 A/B 两组都"在线" —— 根因是 `demo-config.js` 只在 `cfg.base` 与 `cfg.key` 都为空时才预置 Key，只设 `{proxy}` 会在 reload 后被硬编码 Key 覆盖，两组都走浏览器直连。修法 = 单变量对照（base/key 设无效值，只让 proxy 不同）⇒ A 在线 965ms 只可能来自 Java / B 3ms 回落离线 ⇒ `j2_chat_contract.py` J2-CONTRACT-PASS + `browser_check` ALL-ASSERT-PASS。同轮老大立规：**非破坏性步骤自动执行不要多问**（授权/继续/升级建议三类）。提交 `fd6804e` 已 push。
- 2026-09-21 r1 — 老大「继续执行未完成的任务」→ 接主线 **J1**，已完成（详见上方分阶段表）。动手前实测拦下三个阻塞：① Maven 未装（新装 3.9.9 到 `~/.local/maven`，配腾讯云镜像）② **默认 `JAVA_HOME` 是 JDK 8 而非 17**（构建必显式切换）③ **版本控制基线缺失**（0 commit + 无远端，纪律 #20 判 🔴）。设计取舍：静态页**不复制进 `src/main/resources/static/`**，改用 `spring.web.resources.static-locations=file:${XINYU_WEB_ROOT:./src/}` 直读权威源 —— 避免造出第三处副本同步点（已有 `src/` → `deploy/xinyu/` 一条同步红线）。验收：`/api/health` UP + 资源全 200 + `browser_check.py` 原样 ALL-ASSERT-PASS + python 服务对照组证明控制台错误与 Java 无关。`.gitignore` 增 `server/target/`。

## 分卷目录
- **卷1** `07-next-steps.part3.md` — 07-next-steps 分卷（R199 自动拆卷）

