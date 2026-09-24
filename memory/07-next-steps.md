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

- [ ] 🔴 **iCAN 提交硬截止 2026-09-30**（2026-09-23 起**剩 7 天**；截止即锁团队信息）：官网报名 + 提交。**缺件三项（2026-09-24 对标轮实测更正）**：①《应用方案》PDF ✅ **已产出**（18 页，9d7442c；成员署名位待名单 PII 齐后重渲染一次）②演示视频 ✅ **自动产片完成**（`交付物/提交包/demo_video_out/心屿SoulIsle-演示视频.mp4`，217s/22.4MB，8 幕真链路+烧录字幕+中文旁白，可经 `_test/demo_video_pipeline.py` 重录；官方口径无人声强制）③报名名单 ⚠️ **5 人已定**（伍昊宇队长/吴涵/姜智文/江文斌/叶书阳，0638513），**仍缺**五人学号/手机号/邮箱 + 指导教师（≤2 非成员）+ 官网填报登录态（三项只有老大能给）→ 清单见 `交付物/提交包/报名信息-待填清单.md` 与 `演示视频-录制执行清单.md`
- [ ] **J3/J4 变现**（「变现」= 让已建成但未启用的能力真正跑起来，非商业变现）：① ✅ **两端一致性常驻守卫**（`engine_consistency_check.py`，含自检与端到端对照）② ✅ **本地演示已开服务端持久化**（`demo-config.js` 置 `remote:true` + 熔断）③ ⏳ **fat jar / 容器部署**：**两条路都已就绪** —— (a) **部署包** `deploy/jar/`（`start.ps1` / `start.sh` / `README-部署.md`，实测从系统临时目录启动 + `-WebRoot` 指向仓库外静态副本，UP、静态全 200、公网版零密钥）；(b) **容器镜像**（2026-09-23 **真 Docker 全链路实测通过**：build 成功 482 MB / run 后 `/api/health` UP + 静态全 200 + 评测 73-98.6%-6-6 + **镜像内密钥 CLEAN** + `docker restart` 后数据仍在）。→ **唯一阻塞 = 老大提供目标机器**（IP / 登录方式 / 安全组放行端口）。**2026-09-24 老大裁决：先不办，降级至 10 月复赛节点**
- [x] ~~⏸ PDF 起草（2026-09-23 老大明确维持冻结）~~ → **2026-09-24 解冻并已产出**：18 页 PDF + 盲审遗留处置 + 路径泄露修复（9d7442c 与当日日志），本项关闭
- [ ] 🔴 **P0（新）· 公网部署未跟进本轮改动**：`deploy/xinyu/` + `deploy/functions/` 内容已同步且 SHA256 三类归零，但**线上仍是旧版**（评委在 `xinyu-soulisle.pages.dev` 看不到流式/TTS/新策略表）。
      命令：`npx wrangler pages deploy deploy/xinyu --project-name xinyu-soulisle` → 跑完 `python _test/public_check.py` 复核 `KEY_LEAK: False` + `CONSOLE_ERRORS: 0`。
      **本轮未代跑的理由（必须记清）**：这是**评委可见的外发变更**，超出"改代码 + Git 版本控制即备份"的授权半径；距 09-30 截止 6 天，上线前需老大一句话（同 `PDF 冻结` 口径）

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
