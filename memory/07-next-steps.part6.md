# 07-next-steps.part6.md

<!-- 本卷为 07-next-steps.md 的延续 -->

- [ ] **J3/J4 变现（优先级高于继续加功能，2026-09-22 校准后确立）**：⚠️ **「变现」= 让已建成但未启用的能力真正接进产品跑起来（非商业变现）**；更准确的说法是「接入 / 启用」。现状实测 —— 前端 **0 处**调用 `/api/emotion`（仍用本地 `src/js/emotion-engine.js`）、**0 处** `remote:true`（J4 默认关闭）⇒ **J3/J4 目前对演示零可见影响，是"能力就位、生产未启用"**。三件：
  1. ✅ **已做（2026-09-22）**：**两端一致性常驻守卫** —— 新增 `_test/engine_consistency_check.py` + `_test/engine_lexicon_dump.js`，Java 侧加 `GET /api/emotion/lexicon` 与 `eval?detail=1`，JS 侧 `emotion-engine.js` 导出 `NEG/DEG/CRISIS`。
     判据三层：**A 词表结构**（含**重复项与顺序** —— 重复词会被重复计分，"顺手去重"会改分数）/ **B 逐条预测 73 条**（2026-09-23 由 36 扩至 73；只比汇总会漏"两条错误互相抵消"）/ **C 汇总指标**。
     **验证含对照**：`ENGINE-CONSISTENCY-PASS`（两端词表+逐条+汇总全等）+ `--selftest` 注入分叉报出 2 问题 + **端到端对照**（真改 JS 词表 → FAIL 且精确指出 `仅JS=['考上了X'] 仅Java=['考上了']`；还原 → PASS 且文件 SHA 不变）。
     原方案「前端切 `/api/emotion`」**已否决**：会让服务端不可达时情绪识别归零（离线降级是红线），保留本地词典又消不掉重复 —— 改为"把静默重复变成受监控重复"。
  2. ✅ **已做（2026-09-22）**：`src/js/demo-config.js` 预置 `remote: true` → **本地 / fat jar 演示默认开启服务端持久化**（"跨设备、清缓存都不丢"成立）。
     ⚠️ **未做全局默认开**，原因：公网版（Pages/CloudBase）只有 `/api/chat`、没有 `/api/memory`，默认开会给评委看到 404 并打破 `public_check` 的 `CONSOLE_ERRORS: 0`。
     配套加**熔断**（`memory-store.js`）：探测遇 404 或网络失败即 `remoteDown`，本会话不再重试；实测 3 句对话只发 2 个请求（上界 = 页面加载次数）、本地存储照常写入、`is_remote` 熔断后为 False → 新常驻对照组 `_test/j4_remote_down_check.py` **J4-FUSE-PASS**。
  3. ⏳ **fat jar 部署到国内可达机器** —— 摆脱 CloudBase 首访中间页。**2026-09-23 进展：部署包已交付并可独立运行**（`deploy/jar/`：`start.ps1` / `start.sh` / `README-部署.md`）。
     实测（取证时刻 2026-09-23 00:30）：从**系统临时目录**启动（非项目根）+ `-WebRoot` 指向仓库外静态副本 `deploy/xinyu` → `Started SoulIsleApplication in 4.213s`；`/api/health` = `status=UP` / `webRoot` 解析正确 / `indexFound=true` / `vendorFound=true`；`/`、`/js/app.js`、`/js/three-scene.js`、`/vendor/three.min.js`、`/css/style.css` **全 200**；`js/demo-config.js` 610 B **`KEY_LEAK=False`**。
     **踩坑两条（已修进脚本）**：① 本机默认 `JAVA_HOME` = **JDK 8**，Spring Boot 3 起不来 → 脚本改为**探测版本**（要求 major ≥ 17）而不信任 `JAVA_HOME`；② 脚本顶部有 `$ErrorActionPreference='Stop'`，而 `java -version` **只写 stderr** → PowerShell 把原生 stderr 变成终止性 ErrorRecord，探测**恒 false** → 改走 `cmd /c` 合并流。
     **剩余阻塞**：需老大提供目标机器（IP / 登录方式 / 安全组放行端口）。
     **Dockerfile 2026-09-23 修了一条红线级问题**：原 `COPY src/ /app/web/` 会把含真实 Key 的 `src/js/demo-config.js` 打进镜像（与其自身注释矛盾）→ 改 `COPY deploy/xinyu/`（零密钥公网版）+ 根目录新增 `.dockerignore` 纵深防御。三层静态核验已过（gitignore 命中 / deploy-xinyu 0 命中 / jar 抽字节 0 命中）。
     ⚠️ **但镜像构建与运行仍未实测** —— 本机**未安装 Docker**（两条安装路都要老大本人在场：Docker Desktop 需 UAC + 重启；WSL2 Ubuntu 需 sudo 密码且代理未镜像）。`start.sh` 仅静态检查未真机跑（已用 `.gitattributes` 保证 `*.sh` 行尾为 LF）。
