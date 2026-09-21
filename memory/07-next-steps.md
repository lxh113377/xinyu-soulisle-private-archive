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

- [ ] 🔴 **iCAN 提交硬截止 2026-09-30**（剩 8 天；截止即锁团队信息）：官网报名 + 提交。缺件风险 = 《应用方案》PDF（≤20 页），详见 `part6`
- [ ] **J3/J4 变现三件**（「变现」= 让已建成但未启用的能力真正跑起来，非商业变现；更准确说法是「接入/启用」）：① **建两端一致性常驻守卫**（原写"前端切 `/api/emotion`"，**已更正**：那会牺牲离线情绪识别能力，且两份真相并未消除）② 默认开 `cfg.remote`（跨设备记住你，代码已就位）③ fat jar 部署到国内可达机器（摆脱 CloudBase 中间页），详见 `part6`
- [ ] ⏸ **PDF 起草（冻结待解冻）**：与老大 09-19「视频/PPT/PDF 不管」指令冲突，需一句话解冻，详见 `part6`

## 分卷目录

- **卷1** `07-next-steps.part1.md` — 已完成条目（历史）
- **卷2** `07-next-steps.part2.md` — 历史续卷
- **卷3** `07-next-steps.part3.md` — 历史续卷
- **卷4** `07-next-steps.part4.md` — 历史续卷
- **卷5** `07-next-steps.part5.md` — P1 / P2 / 最近对话摘要
- **卷6** `07-next-steps.part6.md` — **P0 未完成项完整描述**（iCAN 截止 / J3-J4 变现 / PDF / CloudBase 决策）
- **卷7** `07-next-steps.part7.md` — P0 已完成项 + 改造不变量 + J4/J5 详情
- **卷8** `07-next-steps.part8.md` — 07-next-steps 分卷（R199 自动拆卷）

