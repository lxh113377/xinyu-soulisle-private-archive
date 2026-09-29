# 07-next-steps.part90.md

<!-- 本卷为 07-next-steps.part89.md 的延续 -->

## 失败面 / 不对称（禁只写"已交付"）

- [x] ✅ `deploy/xinyu/js/app.js` 逐字节同步（`DEPLOY-SYNC-PASS`，`src ⇄ deploy` 三类归零；
      公网零密钥 `demo-config.js` 未被覆盖，红线复核行在案）。

## ② 团队名单署进提交面（老大给定顺序：伍昊宇(队长)/姜智文/江文斌/叶书阳/吴涵）

- [x] ✅ `application-plan.html` 封面「团队成员」由 `＿＿＿（按官网报名顺序填写）` 填为实名五人；
      重跑 `render-pdf.ps1` ⇒ **20 页 / 图 10≥期望 9 / ≤20 页硬约束满足**，
      `plan_pdf_coverage_check.py` → `PLAN-PDF-COVERAGE-PASS 9/9`，`pdf_leak_scan.py` → `PDF-LEAK-CLEAN`（五类零命中）。
- [x] ✅ 「指导教师」行**仍留白**（≤2 且非成员，只有老大能给）；`报名信息-待填清单.md` 与
      `提交清单与验收状态.md` 第 4 行同步为新顺序，并登记「剩余缺口＝学号/手机号/邮箱 + 指导教师 + 官网登录态」。
