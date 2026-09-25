# 07-next-steps · part17（人工拆卷：主壳为索引壳却超 4KB，迁出背景块与完整段）

> 换卷理由：`07-next-steps.md` 被 `handoff.py split --check` 判为**索引壳**（主卷不拆、应 ≤4096B），
> r25 实测 5,795B ⇒ 超限。按 R161/R199 零豁免，将「主线目标背景块」原文迁入本卷（字节无损，主壳留指针）。
> 迁入时间：2026-09-25（对标轮 r25）。上卷 `07-next-steps.part16.md`。

## 主线目标 — Java 全栈改造（2026-09-20 老大定方向）

> 把当前「纯静态前端 + Serverless 函数（Cloudflare Pages Function / CloudBase 云函数）」演进为 **Java 全栈**：
> Spring Boot 单体承载全部业务 API 与记忆持久化，**前端保留现有 Three.js 叙事页且零改动**（只换 baseURL）。
> 选型为**假设值**，动手前需老大确认（见 `03-tech-stack.md` 目标技术栈表）。
> 环境实证：本机 JDK 17 = `C:\Program Files\Eclipse Adoptium\jdk-17.0.20.101-hotspot`（JDK 8 是课程作业用，勿混）。
> Maven 3.9.9 = `%USERPROFILE%\.local\maven\apache-maven-3.9.9\bin\mvn`（2026-09-21 新装，**不在 PATH**，需临时加 PATH 或用绝对路径）；`~/.m2/settings.xml` 已配腾讯云镜像加速。
> ⚠️ **默认 `JAVA_HOME` 实测 = JDK 8**（`…jdk-8.0.504.1-hotspot`）→ 每次构建/启动前必须显式 `$env:JAVA_HOME="<JDK17路径>"`，否则 Spring Boot 3 直接编译失败。

### 分阶段（每阶段都要能跑、能回归，禁止一次性推倒重写）

J1 骨架 ✅（2026-09-21）/ J2 API 契约对齐 ✅（2026-09-22）/ J3 情绪引擎 Java 化 ✅（2026-09-22）
→ 逐阶段验收证据与命令在 `part1.md`–`part4.md`（历史）与 `part7.md`（P0 已完成项 + 改造不变量）。

## J3/J4 变现（完整段，主壳留摘要）

**「变现」= 让已建成但未启用的能力真正跑起来，非商业变现。**

- ① ✅ **两端一致性常驻守卫**：`engine_consistency_check.py`（含自检与端到端对照）。
- ② ✅ **本地演示已开服务端持久化**：`demo-config.js` 置 `remote:true` + 熔断。
- ③ ⏳ **fat jar / 容器部署**：**两条路都已就绪** ——
  (a) **部署包** `deploy/jar/`（`start.ps1` / `start.sh` / `README-部署.md`，实测从系统临时目录启动 +
      `-WebRoot` 指向仓库外静态副本，UP、静态全 200、公网版零密钥）；
  (b) **容器镜像**（2026-09-23 **真 Docker 全链路实测通过**：build 成功 482 MB / run 后 `/api/health` UP +
      静态全 200 + 评测 73-98.6%-6-6 + **镜像内密钥 CLEAN** + `docker restart` 后数据仍在）。
  → **唯一阻塞 = 老大提供目标机器**（IP / 登录方式 / 安全组放行端口）。
  **2026-09-24 老大裁决：先不办，降级至 10 月复赛节点。**
  **三件套（V3.55.0 第 16 条首次自用；老大给机器前须齐三项，缺一项即判「不可安全照抄」）**：
  ① 执行目录 = 目标机上仓库根的**绝对路径**（`static-locations=file:${XINYU_WEB_ROOT:./src/}` 按 JVM
     工作目录解析，cwd 错则首页 404 而接口照样 200）；用 `deploy/jar/start.ps1` 时须先 `cd` 进部署包目录。
  ② 日志必见证据 = 启动日志出现 `Started SoulIsleApplication`，且 `GET /api/health` 同时回
     `"status":"UP"` + `indexFound=true` + `vendorFound=true`（缺一判未生效，禁以"端口通/页面能开"代替）。
  ③ 回滚锚 = 动手前先记旧 jar 的 sha256 与 H2 库文件 `server/data/xinyu.mv.db` 的 sha256；
     回滚 = 换回旧 jar **并**还原该库文件（只回滚代码不回滚数据会串号）。
  完整部署史见 `part11.md`（人工拆卷自 part6）。
