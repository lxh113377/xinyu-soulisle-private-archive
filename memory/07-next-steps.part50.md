# 卷50 — r50 协作治理面（上）：三通道实数 + 两个被掩盖的断口（2026-09-27）

> 下卷 `part51`：度量学三条、有意不做的事、未闭环序。轮次号 r50 由 `git log` 实况决定（r48/r49 已被并行会话用掉）。
> 换面取证：✅ 十一份报告对 `社区健康|community profile|health_percent|CODEOWNERS|协作治理` **0 命中**
>（`可观测`、`i18n` 两组亦 0）。此前「维护状态」只有 stars/pushed_at/issues 这类外部信号，
> 没一格量「本仓自己把哪些维护动作制度化了多少」。
## 1. 三通道实数（16 仓 + self，各自独立取数）

声明面（git tree）：`CONTRIBUTING 10/16｜SECURITY 6/16｜issue模板 9/16｜PR模板 5/16｜
CODEOWNERS 1/16｜conduct 2/16｜support 2/16｜dependabot.yml 1/16`
平台面（`community/profile`）：health min 28｜**中位 62**｜max 100；self **71**
行为面（`/pulls?state=all` 过滤 dependabot 作者）：**真开出过 PR 的只有 2 家**
（lobehub 开 30 合 18、SillyTavern 开 7 合 7）；self 开 4 合 3。
恒等式：应测 16 = 可用 11 + NA 5 ⇒ OK。

**最要紧的一行是"声明面 1/16 < 行为面 2/16"**：lobehub 有 30 张 dependabot PR 但 tree 里
没有 `dependabot.yml`（配置挂在组织级）⇒ **仓内找不到 ≠ 没挂**。任何只用文件名的治理检查
在这一格上必然给出错误答案。

## 2. 🔴 本轮主缺陷：漏洞告警整条关着，而"配置在 + 有 PR"把它盖住了

开轮实测：`gh api repos/{slug}/dependabot/alerts` →
**`Dependabot alerts are disabled for this repository`（HTTP 403）**；`GET /vulnerability-alerts` → 404。
同时 `dependabot.yml` 自 r21 在册、也确实开出过 4 张 PR ⇒ 观感是"依赖治理已覆盖"。

处置与读回（不写"应该已开启"）：`PUT /vulnerability-alerts` → 204；
`GET` 由 404 变 **HTTP 204**；alerts 端点由 403 变可读、**当前告警数 0**。
⇒ 连带修正我自己的判断：此前评估"要不要升 Spring Boot 4"只按回归成本算，
漏了"有没有已知 CVE 压力"这一格；现在有平台答案（0 告警），截止日前不升是**有依据的**决定。

## 3. 🔴 第二缺陷：一张结构性永红的自动 PR 挂了 6 天

PR #2 `spring-boot-starter-parent 3.2.5→4.1.1`（09-24 开出）java-build 30s fail、浏览器回归 56s fail。
而同期两张 **major**（`checkout 4→7`、`setup-python 5→7`）**已正常合并**
⇒ 结论不是"major 危险"，是"Spring Boot 跨大版本属需人工评估的迁移，不该自动直送"。
处置：maven 加 `ignore` 大版本（**actions 不扩面**，无此症状）+ 带证据关闭 #2
（回执 `…/pull/2#issuecomment-5852929808`）+ 常驻判据 **G1b** 并入既有 `validate_dependabot`
（自测 48→50，双向：摘 ignore 判红 / actions 无 ignore **不得**判红）。

