# 07 - 下一步

> 本文件记录下一步行动项，按优先级排序。
> **⚠️ 新对话恢复上下文入口。P0 必须永远有一条可执行指令。**
> 本卷是**索引壳**（≤4096B，R161）：只留「可执行摘要 + 指针」，长段落一律迁分卷（背景见 part17）。

## 🎯 主线目标 — Java 全栈改造（2026-09-20 老大定方向）

J1–J3 已落地，前端零改动；背景块/选型假设/JDK17 与 Maven3.9.9 环境实证（含 JAVA_HOME=JDK8 的坑）全文 `part17`。

## P0 — 必须做

- [ ] **J3/J4 变现** [推荐:R35-02]：① ② ③ 三件均已实测就绪 ⇒ **唯一阻塞 = 老大给目标机器**（IP/登录/安全组）。`part17`
- [ ] 🟠 [推荐:R83-02] **共享环境隔离待老大**：陪聊 / iCAN 门店 / 医 同居一个 CloudBase env，
      子目录避让只是止血；命名空间或独立 env 属跨项目决定，本轮未擅动。`part92` §②
- [ ] **同族坑收口**：台账 `part18`/`part20`；G9 常驻 `repo_config_check`。
- [x] ✅ [r93 → r94 已收] **loc 门超限治理**：r94 先修尺（22→8，14 项为「Java 类 / JS IIFE 被当函数」的误判）
      → 拆 10 个真超限函数 → **超限 0（LOC-PASS）** → 切 `enforce` 并加接线自证（门有牙）。
      报告 `交付物/对标分析报告-2026-10-03-r94.md`；台账 `part107`
- [x] ✅ [R90 新 · r95 已收] **CI 全绿契约**：台账原文记的「须手写 `.ci/contract.json` blocking 清单，再加 step 并
      `--sweep` 复扫」在 r95 查清**两处不成立**——`greencheck bootstrap` 实测 `checks=[]`（自写电池不是标准配置）、
      `greencheck.py` **无 `--sweep` 子命令**（`--help` 实测仅 panel/run/show/bootstrap/ledger/--selftest）。
      真因不是「没写清单」而是**契约从未入库** ⇒ `greencheck run` 恒 UNKNOWN ⇒ pre-push 钩子恒放行。
      已改手写 blocking 14 条（实测 10021ms/20s）**并入库**，回执 `[greencheck] GREEN` rc=0 10.1s；
      另立 `_test/ci_contract_check.py`（9 腿/自检 15 条）盯契约自身。`part108` §①②
- [x] ✅ **推平完成**（本轮代收口）：补r91小节R2c转绿→`1354466`→直推`2d34e7b..1354466`
      →`CI-WATCH-GREEN（2条）`。本地==远端。
- [ ] 🟢 [R89+R90 已收] 门面旧名归零（`brand_consistency` 常驻）｜归档前提已解：判据读
      `git diff --cached -M` 认「逐字节等价搬卷」＋分母=`ARCHIVE_ROOTS` ⇒ 交付物 184.8→**129.5 MB**
      （corpus 全量不搬，分母由 `disclaimer_forensics_lint --all` 现读）｜C7/G19/R7｜电池 **112**
- [ ] 🔴 **P0 需老大在场**：撤销曾进过会话输出的明文 Key（r52/r53 各再犯），再消 `demo-config.js` 那条 404。`part37`

## 分卷目录

- **卷1–16** — J1–J5 验收证据（1–4）／P1·P2（5）／**P0 未完成全文（6）**／已完成+不变量（7）／
  自动拆卷（8–10、12–16）；**卷11** = fat jar/容器部署史
- **卷17–25** — 主线背景｜同族坑｜离线壳｜CI 三判据｜技能治理链｜拆卷续卷｜r35/r36
**26-55 r37–r54 逐轮**｜**56-57 r55-r57**｜**58 r57 补记**｜**59 r58**｜**60 r59**｜**61 r60**｜**66-100 r65-r83**
（卷号按取号序非时间序；89=部署配方，91=r82，**92=r83 全记录**，93-100=r83 收尾时 R199 自动拆出的续卷，
 273 条迁出行逐行可找到、missing=0）
- ⚠️ 该族 **92 份 > 阈 12**：`volume_alloc` 报「先按名册归档再拆；许可未登记 ⇒ 只报不动盘」
- **卷1** `07-next-steps.part93.md` — 07-next-steps 分卷（R199 自动拆卷）
- **卷2** `07-next-steps.part94.md` — 07-next-steps 分卷（R199 自动拆卷）
- **卷3** `07-next-steps.part95.md` — 07-next-steps 分卷（R199 自动拆卷）
- **卷4** `07-next-steps.part96.md` — 07-next-steps 分卷（R199 自动拆卷）
- **卷5** `07-next-steps.part97.md` — 07-next-steps 分卷（R199 自动拆卷）
- **卷6** `07-next-steps.part98.md` — 07-next-steps 分卷（R199 自动拆卷）
- **卷7** `07-next-steps.part99.md` — 07-next-steps 分卷（R199 自动拆卷）
- **卷8** `07-next-steps.part100.md` — 07-next-steps 分卷（R199 自动拆卷）
- **卷9** `07-next-steps.part102.md` — 07-next-steps 分卷（R199 自动拆卷）
- **卷10** `07-next-steps.part103.md` — 07-next-steps 分卷（R199 自动拆卷）
- **卷11** `07-next-steps.part104.md` — 07-next-steps 分卷（R199 自动拆卷）
- **卷12** `07-next-steps.part106.md` — **r93 对标轮**：r92 遗留三项销账、loc 门/rollup 两个新判据、
  corpus 归档（含分母46→46 声明）、r94 入口、方法论留档
- **卷13** `07-next-steps.part107.md` — **r94**：loc 门修尺并转 enforce（超限 0）、CI 口径统一、
  两份台账重采、8 个 probe 的 `date -u` 跨平台修复、r95 入口
- **卷14** `07-next-steps.part108.md` — **r95①**：CI 全绿契约装了 5 轮一次没生效过（未入库 ⇒ greencheck
  恒 UNKNOWN ⇒ pre-push 恒放行，实测坐实）+ 「门恒放行」这一族第三次撞上（r93 j2 / r94 j4 / r95 契约）
- **卷15** `07-next-steps.part109.md` — **r95②**：30 天提交率尺 + **实测「★ 不是维护度的代理」**
  （SillyTavern ★34,083/30天9次 vs my-neuro ★1,387/30天62次）+ 台账 SNAP 刷新（G17 漂移 −4→0）
  + 两件判据自检抓到本件自己的 bug
- **卷16** `07-next-steps.part110.md` — **r95③**：r96 入口（probe 写盘段遗留 / 提交率尺重采节奏 /
  四项维持不立项的**触发条件写死** / 并发无读数 / 体量 E 维 23 项）

