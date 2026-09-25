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
## P0 — 必须做

> ⚠️ 本卷为**索引壳**（R199 自动拆卷后）。以下为**当前可执行摘要**（满足致命纪律 #1：主卷 P0 不得为空）；
> 完整描述在分卷里（见文末「分卷目录」，主要落在 `07-next-steps.part6.md`）。

- [x] **对标轮 r24（2026-09-25 第五轮）已落地**：外部有漂移（4 处），但本轮主产出是**把连续两轮被我登记成「下一件」却没做的
      `app.js` 切分真正开工** —— 语音模块（TTS+ASR）外提为 `src/js/voice.js`（99 行），`app.js` 471 → 403 行，
      行为零改动（`ux_guards` U1 与 `voice_check` A1-A6 是它的专门判据）。
      接线全链已跑通：`index.html` 顺序 → `deploy/xinyu` 同步 → `size_budget` 登记新文件 → 公网重部署 `41dea397`
      → 三判据 rc=0 → 电池 **28/28 rc=0**。连续推迟已作为排产缺陷写进本轮反思，不再登记第三次。

- [ ] 🔴 **iCAN 提交硬截止 2026-09-30**（剩 5 天；截止即锁团队信息）：官网报名 + 提交。
      三项缺件现状（2026-09-25 r20 复核）：①《应用方案》PDF ✅ 已产出（18 页，成员署名位待 PII 齐后重渲染一次）
      ②演示视频 ✅ 已交付（217s/22.4MB，`_test/demo_video_pipeline.py` 可重录）
      ③**报名名单 PII ⚠️ 仍挂账，且只有老大能给**：五人学号/手机号/邮箱 + 指导教师（≤2 非成员）+ 官网填报登录态。
      **09-25 起演示视频建议重录一次**：本轮 gsap 3.15.0 已上线 + 情绪后端化改变了叙事链路（可加一句"后端引擎"演示），
      旧成片仍是 3.12.5 时代画面；重录成本约 10 分钟，走 `_test/demo_video_pipeline.py` 一键

- [ ] **J3/J4 变现**（「变现」= 让已建成但未启用的能力真正跑起来，非商业变现）：① ✅ **两端一致性常驻守卫**（`engine_consistency_check.py`，含自检与端到端对照）② ✅ **本地演示已开服务端持久化**（`demo-config.js` 置 `remote:true` + 熔断）③ ⏳ **fat jar / 容器部署**：**两条路都已就绪** —— (a) **部署包** `deploy/jar/`（`start.ps1` / `start.sh` / `README-部署.md`，实测从系统临时目录启动 + `-WebRoot` 指向仓库外静态副本，UP、静态全 200、公网版零密钥）；(b) **容器镜像**（2026-09-23 **真 Docker 全链路实测通过**：build 成功 482 MB / run 后 `/api/health` UP + 静态全 200 + 评测 73-98.6%-6-6 + **镜像内密钥 CLEAN** + `docker restart` 后数据仍在）。→ **唯一阻塞 = 老大提供目标机器**（IP / 登录方式 / 安全组放行端口）。**2026-09-24 老大裁决：先不办，降级至 10 月复赛节点**
## 分卷目录

- **卷1** `07-next-steps.part1.md` — 已完成条目（历史）
- **卷2** `07-next-steps.part2.md` — 历史续卷
- **卷3** `07-next-steps.part3.md` — 历史续卷
- **卷4** `07-next-steps.part4.md` — 历史续卷
- **卷5** `07-next-steps.part5.md` — P1 / P2 / 最近对话摘要
- **卷6** `07-next-steps.part6.md` — **P0 未完成项完整描述**（iCAN 截止 / J3-J4 变现 / PDF / CloudBase 决策）
- **卷7** `07-next-steps.part7.md` — P0 已完成项 + 改造不变量 + J4/J5 详情
- **卷8** `07-next-steps.part8.md` — 07-next-steps 分卷（R199 自动拆卷）
- **卷9** `07-next-steps.part9.md` — 07-next-steps 分卷（R199 自动拆卷）
- **卷10** `07-next-steps.part10.md` — 07-next-steps 分卷（R199 自动拆卷）
- **卷11** `07-next-steps.part11.md` — J3/J4 变现第 3 件：fat jar / 容器部署完整史（R199 人工拆卷自 part6）
- **卷12** `07-next-steps.part12.md` — 07-next-steps 分卷（R199 自动拆卷）
- **卷13** `07-next-steps.part13.md` — 07-next-steps 分卷（R199 自动拆卷）
- **卷14** `07-next-steps.part14.md` — 07-next-steps 分卷（R199 自动拆卷）

