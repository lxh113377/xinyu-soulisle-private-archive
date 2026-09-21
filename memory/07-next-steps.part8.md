# 07-next-steps.part8.md

<!-- 本卷为 07-next-steps.part7.md 的延续 -->

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

## 分卷目录
- **卷1** `07-next-steps.part6.md` — 07-next-steps 分卷（R199 自动拆卷）

- [x] **J1 骨架** ✅ 2026-09-21：`server/`（Maven 3.9.9 + Spring Boot 3.2.5 + JDK 17）+ `/api/health` + 托管现有前端静态页（**直读 `src/` 权威源，零副本**）→ `java -jar server\target\soulisle-server.jar --server.port=8123` 实测 `status=UP` / `webRoot` 解析到项目 `src/` / `indexFound=true` / `vendorFound=true`，首页与 `js`、`css`、`vendor` 全 200；`_test/browser_check.py` **原样复用（同端口 8123）ALL-ASSERT-PASS**。对照组：换回旧 `python -m http.server` 同为 4 条 `ERR_CONNECTION_REFUSED` ⇒ 该错误出自脚本自注入的不可达端点 `127.0.0.1:18123`（离线降级用），与 Java 服务端无关

- [x] **J2 API 契约对齐** ✅ 2026-09-22：`POST /api/chat` 与 v1 **1:1**（契约实读自 `deploy/functions/api/chat.js` + `src/js/chat-agent.js:25-43`，非凭记忆）。请求认 `{messages,temperature,max_tokens}`；**上游响应逐字透传**（含 status）；错误体与 v1 完全一致（`no-key` 500 / `bad-json` 400 / `upstream-nonjson` / `upstream-error` 502），且**判定顺序一致**（先查 key 再解析 body）。验收：`_test/j2_chat_contract.py` **J2-CONTRACT-PASS**（A 组走 Java 965ms 在线 / B 组不可达端点 3ms 回落离线，单变量对照）+ curl 三例（no-key 500、bad-json 400、真实调用 200 中文无损）+ `browser_check.py` ALL-ASSERT-PASS

- [x] **J3 情绪引擎 Java 化** ✅ 2026-09-22：`engine` 包（`EmotionLexicon` 词表逐字搬 / `EmotionEngine.scan` 同公式 / `EmotionClassifier` 双路）+ `POST /api/emotion` + `GET /api/emotion/eval`。**双端逐项对账完全一致**：Java 侧 `94.4%` / `crisis_recall 3/3` / `per_class` 七类全同 / `misses` 两条逐字相同（JS 侧 `node _test/emotion_eval.js` 为对照）。危机命中**不调 LLM**（实测 `llm=null`）；分歧案例 `lex anger 0.625 vs llm sadness 0.75 → 采信 LLM` 与前端路径一致
