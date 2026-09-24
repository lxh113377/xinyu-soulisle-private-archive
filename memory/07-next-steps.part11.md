# 07-next-steps.part11.md — J3/J4 变现第 3 件：fat jar / 容器部署（自 part6 迁入）

<!-- 本卷为 07-next-steps.md 的延续；R199 拆卷自 part6，内容零改写 -->

- [ ] 3. ⏳ **fat jar 部署到国内可达机器** —— 摆脱 CloudBase 首访中间页。**2026-09-23 进展：部署包已交付并可独立运行**（`deploy/jar/`：`start.ps1` / `start.sh` / `README-部署.md`）。

     实测（取证时刻 2026-09-23 00:30）：从**系统临时目录**启动（非项目根）+ `-WebRoot` 指向仓库外静态副本 `deploy/xinyu` → `Started SoulIsleApplication in 4.213s`；`/api/health` = `status=UP` / `webRoot` 解析正确 / `indexFound=true` / `vendorFound=true`；`/`、`/js/app.js`、`/js/three-scene.js`、`/vendor/three.min.js`、`/css/style.css` **全 200**；`js/demo-config.js` 610 B **`KEY_LEAK=False`**。

     **踩坑两条（已修进脚本）**：① 本机默认 `JAVA_HOME` = **JDK 8**，Spring Boot 3 起不来 → 脚本改为**探测版本**（要求 major ≥ 17）而不信任 `JAVA_HOME`；② 脚本顶部有 `$ErrorActionPreference='Stop'`，而 `java -version` **只写 stderr** → PowerShell 把原生 stderr 变成终止性 ErrorRecord，探测**恒 false** → 改走 `cmd /c` 合并流。

     **剩余阻塞**：需老大提供目标机器（IP / 登录方式 / 安全组放行端口）。

     **Dockerfile 2026-09-23 修了一条红线级问题**：原 `COPY src/ /app/web/` 会把含真实 Key 的 `src/js/demo-config.js` 打进镜像（与其自身注释矛盾）→ 改 `COPY deploy/xinyu/`（零密钥公网版）+ 根目录新增 `.dockerignore` 纵深防御。三层静态核验已过（gitignore 命中 / deploy-xinyu 0 命中 / jar 抽字节 0 命中）。

     **2026-09-23 无 Docker 时的替代证据已取得**：新增 `_test/docker_image_sim_check.py`（**DOCKER-SIM-PASS**）—— 把 Dockerfile 的 COPY/ENV/WORKDIR/ENTRYPOINT **从文件解析**后在磁盘等价实现：写入 14 文件、评测集 73 条、**镜像内密钥 0 命中**、`/api/health` UP、4 条静态资源 200、评测 73/98.6%/6-6；带 `--selftest` 隔离桩证明「0 命中」判据非恒真。

     ✅ **同日已用真 Docker 收口**：Docker Desktop 4.91.0（daemon `Server 29.8.0 / linux / overlayfs`）→ `docker build` 成功（镜像 482 MB）、`docker run` 后 `/api/health` UP + 静态全 200 + 评测 73/98.6%/6-6 + **镜像内密钥 CLEAN**（附注入对照）；**持久化实测**：写 2 情绪+1 消息 → `docker restart` → 仍 2/1（DB 确实落在 `VOLUME /app/data`）。上述模拟脚本（`docker_image_sim_check.py`）降级为「Docker 就绪前的过渡证据」，不再是对外主证据。

     ⚠️ **两个已实测的坑**：① `winget install Docker.sbx` 装到的是 **Docker Sandboxes**（无 `docker` CLI、daemon 不可达、非构建器）—— 正确包 ID 是 `Docker.DockerDesktop`；② 本机**访问不了 Docker Hub**（`registry-1.docker.io` = 000），必须先 `docker pull docker.1ms.run/library/eclipse-temurin:17-jre` 再 `docker tag` 成本地名，否则 build 必失败。

     `start.sh` 仍仅静态检查未真机跑（已用 `.gitattributes` 保证 `*.sh` 行尾为 LF）。

- [x] ✅ **对标轮第二轮 M1–M8 全部落地（2026-09-24）**：流式 SSE / 共情策略表 SSOT / provider 别名 / TTS 朗读 / 对话窗口化 / 响应式+粒子降档 / CI 三门禁 / ROADMAP+`v1.3.0` 标签。
      判据全绿：`stream_contract` A/B/C、`strategy_check`（+`--selftest` 防恒真）、`ux_guards_check` 21/21、`browser_check` ALL-ASSERT-PASS、`engine_consistency` 98.6%/6-6 双端全等、`deploy_sync` 三类归零。
      详表见 `05-feature-status.md`「对标轮第二轮」，架构取舍见 `03-tech-stack.md` 决策 #6–#9，对标数据见 `交付物/对标分析报告-2026-09-24-v2.md`

- [x] ~~⏸ PDF 起草（2026-09-23 老大明确维持冻结）~~ → **2026-09-24 解冻并已产出**：18 页 PDF + 盲审遗留处置 + 路径泄露修复（9d7442c 与当日日志），本项关闭
