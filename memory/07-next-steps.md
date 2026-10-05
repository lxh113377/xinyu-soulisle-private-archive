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
- [ ] 🔴 **r97 首务（可执行）**：**E2 棘轮降数** —— `browser_engine` 统一入口现 0/32 已接，逐个接走手写
      回退的套件；判据 `python _test/browser_engine_declare_check.py`（基线 32 只降不升），每改一个跑 AST 清点。`part111` §③
- [ ] 🟠 **台账重采须错峰**：`ledger_age_check` 现 16/16 在 fuse 内、契约 fuse=7 天 ⇒ ~10-12 会再超龄；
      burst 重采本轮实测撞限流。判「降级」须比对 NA 相对上一份认可台账是否**增长**。`part111` §③-2
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
- **卷17** `07-next-steps.part111.md` — **r96**：三条改判（r95「不可测」被 12 仓实测证伪 / 假 NA 产地 /
  并发口径自相矛盾）+ 本轮 8 件新套件 + **r97 入口**（E2 棘轮降 32 / 重采须错峰 / 阶梯基线已立）

- **卷18** `07-next-steps.part112.md` — **r96 收口**：发版链三处自伤逐条归因（tag 前未同步三源 / 先推 main 后推 tag /
  tag 指向旧提交后 force 前移）+ 两条方法论（门禁要挑"可能有输入"的状态跑；`ci_status` 读远端 ⇒ 本地全绿成环）
- **卷19** `07-next-steps.part113.md` — **r96 最终回执**：第八轮冻结树 `124/125 RED: voice`（**未取到 ALL-GREEN**）+
  **voice 由「在册 flaky」改判为产品真缺陷**（`stopped:1` 而 `ev` 无 `end` ⇒ 按钮卡"正在听"；CI 走 A4 SKIP 从未覆盖）
  ⇒ P1 待老大 + 本轮与计划的两处偏离（`ledger_age` 落 deferred 非 blocking / peers 未 burst 重采）
- **卷20** `07-next-steps.part114.md` — **r96 受理面四轮链最终回执**：`3d99e9d` CI-WATCH-GREEN（124/126 零判红）+ 四条红逐轮归因去向 + r97 新增两条入口（改 md 必复跑 disclaimer_forensics / 时刻耦合普查）
- **卷21** `07-next-steps.part115.md` — 07-next-steps 分卷（R199 自动拆卷）
- **卷22** `07-next-steps.part116.md` — 07-next-steps 分卷（R199 自动拆卷）
- **卷23** `07-next-steps.part117.md` — 07-next-steps 分卷（R199 自动拆卷）

