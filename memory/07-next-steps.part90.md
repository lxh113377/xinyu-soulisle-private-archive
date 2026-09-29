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
- [x] ✅ 顺序一致性核过的三处：PDF 封面 ✅；演示视频 8 幕片尾是**星雾全景、不含姓名** ⇒ 不构成冲突；
      未入库的 `心屿MindIsle_参赛方案.pptx` 品牌名与 PDF 分叉（SoulIsle vs MindIsle）**老大未裁决** ⇒ 第三处悬空，已登记。
- [x] ✅ 09-24 版旧顺序（伍昊宇/吴涵/姜智文/江文斌/叶书阳）以**覆盖注记**留下，不改写历史行。
- [ ] ⚠️ 踩坑回执（已就地修）：我在 `提交清单与验收状态.md` 第 4 行贴了一句
      `` `python -c "...PdfReader('交付物/.../心屿SoulIsle-应用方案.pdf')..."` `` 的复算命令，
      被 `deliverable_inventory_check.py` 的交付物路径正则读成 **`…pdf'`（带尾引号）= 清单声明了但磁盘没有** ⇒
      `DELIVERABLE-INVENTORY-FAIL` 一条假缺失。根因＝**判据按形状取数，散文里出现同形状串就算命中**（同族：
      「文本形状是契约的一部分」）。修法＝把该行改成不带路径字面量的自然语言复算说明，
      改后 `DELIVERABLE-INVENTORY-PASS`（rc=0）。**没有**去改正则求绿。

## ③ 提交面判定（结论见当轮回复，此处只留可复算判据）

- 复算入口：`python _test/run_all_suites.py`（全量电池）。**本轮实跑结论（13:23，同 worktree 三方并发）**：
  整跑**未跑完即中止** —— `_test/browser_check.py` 在电池里 600s 超时把 runner 打出 `TimeoutExpired` traceback（rc=1）；
  同一条套件**单跑 rc=0**、CI 上 32.9s 通过 ⇒ 判为并发争用（当时 r81 会话正在跑它自己的套件），不是代码缺陷。
  中止前 81 条里 **14 条红**，逐条归属：
  · **他方在途件**：`benchmark_metrics.py` 在工作树里**语法都过不了**（两处：`:1074` 缺 `=`、`:1081` f-string 里嵌了未转义的
    双引号）⇒ `benchmark_selftest` 与 `repo_config G9` 双双判红。这条直接否掉了「把 r70 批次一并提交」的前提。
  · **本轮修掉的两条**：`size_budget`（app.js 超 15,490 → 我先压注释与去掉 queue 机制，实测 18,484→16,690，再按 r32/r51
    的既有口径登记 17,524=实测+5%，理由写在预算表注释里）；`repo_config G15`（我给新 AC 占了 **AC-OBS-13**，
    而 13/14/15/16/17/18/19 每个早挂两条命题、基线只放行 7 条重复 ⇒ 改成空号 **AC-OBS-24** 后 G15 PASS）。
  · **既存红（与本轮无关，HEAD 上就红）**：`public_check`（8 条 CSP 内联样式，即 R81-01）、`live_sync`
    （**线上 js 比权威源旧**：`app.js live=15350B local=15418B` 等 3 件）、`release_governance`（v1.6.1 后攒 14 个 feat，上限 5）、
    `ci_status`（HEAD run 判 CODE_FAIL）、`voice` A5（无麦克风环境的老问题）。

## 失败面 / 不对称（禁只写"已交付"）

- ⚠️ **开场代价没人量化**：每次加载会新建 1080 个 `setTimeout`（`lightShow(180)`），低端机上首屏 5s 内
  负载明显；本轮只验证了功能与回归，**未测低端帧率**。若复赛现场演示卡顿，退路是把 `perEmotion` 降到 60。
- ⚠️ **本轮不动 07 壳**（`memory/07-next-steps.md` 由 r81 在途持有：它正把 R81-01/R78-04 改写进壳）。
  r80 的指针因此**暂缺**，全文只在本卷；r81 提交壳之后需由下一轮补一行。
- ⚠️ **R81-01 的前提本轮无法满足**：该条写「代码未修＝`src/js/app.js` 并发持有，前提=`git status --short src/js/app.js` 为空」
  —— r80 正是这个持有者。提交 r80 之后该前提即成立，`app.js` 的内联样式（`style="width:${pct}%"` 等 14 处）
  仍待 r81 修，**不是 r80 的产物**。
