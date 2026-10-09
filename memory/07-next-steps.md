# 07 - 下一步

> 本文件记录下一步行动项，按优先级排序。
> **⚠️ 新对话恢复上下文入口。P0 必须永远有一条可执行指令。**
> 本卷是**索引壳**（≤4096B，R161）：只留「可执行摘要 + 指针」，长段落一律迁分卷（背景见 part17）。

## 🎯 主线目标 — Java 全栈改造（2026-09-20 老大定方向）

J1–J3 已落地，前端零改动；背景块/选型假设/JDK17 与 Maven3.9.9 环境实证（含 JAVA_HOME=JDK8 的坑）全文 `part17`。

## P0 — 必须做
- [ ] WF-r97-v1.8.1发布链 推 main+tag v1.8.1+CI 回执+Release（Pages 面未发布，CI 电池不豁免 live 面）（由 flow 登记；状态: blocked）
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

- **卷24** `07-next-steps.part118.md` — **r96「终点」口径**：回执只描述更早的提交 ⇒ 实质工作终点=41d2de5（第九轮 126/126 ALL-GREEN），1583903 及后为台账承载提交，其受理面由下轮 `ci_status_check` 取；另记 remote_tree 环境性未验 + "python 找不到文件也回 rc=2" 的伪装形
- **卷25** `07-next-steps.part119.md` — **⑦ savepoint 转通**：项目级豁免通道上线 + 本仓 `.noise-exempt`（点名 .ci）+ 提交前后端到端负控制（violation:1→0、exempt:0→1）+ 六条牙齿 + 下轮入口两条；遗留：global_skills 领先 3 提交未推平（github 443 拒连）
- **卷29** `07-next-steps.part123.md` — `flow --sync` 写记忆卷不封顶的缺陷全文（本轮一手 + 我自己同款再犯一次），写入端未修 ⇒ 下轮先取证再动 global_skills
- **卷28** `07-next-steps.part122.md` — 人工拆卷承接 `part5` 尾部三个已完成条目（2026-09-23 评测集扩条 / NEG·DEG 覆盖缺陷 / 语音输入真机验证）；动因是 `flow --sync` 把 P1 镜像写回 part5 后达 4,609B 越过 4KB 硬限、savepoint 判 `single_block` 拒自动拆（逐字节对账已证原文未改）
- **卷27** `07-next-steps.part121.md` — **r97 收口**：冻结树整跑 `124/126 RED: live_sync,live_sync_alt`（同因=公网还跑 v1.8.0 语音模块，curl 两面实测 4148B）；备用线 `tcb hosting deploy` 后 `LIVE-SYNC-PASS 21/21`；Pages 面拦在凭据（第三次同款）⇒ **v1.8.1 不推送**，解封只差 CF API Token
- **卷26** `07-next-steps.part120.md` — **r97 语音退出态修复 + v1.8.1 切版**：未修树先验 RED（A8/A10 三条判红、A9 对照腿绿）⇒ 修 `src/js/voice.js` ⇒ 带 base 复算 11 轮全 rc=0（未修树先验红）；体积上限 4,355→5,038（实测 4,798 ×1.05；先把自写注释 5,039→4,798 B 再登记）；三源 pom/ROADMAP/CHANGELOG 同步 + fat jar 内嵌 1.8.1；收口链（电池 / greencheck / tag / ci_watch / Release）待办**带前提命令**
- **卷30** `07-next-steps.part124.md` — 07-next-steps 分卷（R199 自动拆卷）
- **卷31** `07-next-steps.part125.md` + **卷32** `07-next-steps.part126.md` — **r98 收口**：四项改造回执 ＋ **「验收标准按构造不可达」**新错误族（E2 分子恒≈0 ⇒ r96 写的「N 单调升」永不成立）
- **卷33** `07-next-steps.part127.md` — **r99 收口（对标增量轮）**：r98 标 ✅ 的件**从未进提交面**（`git ls-tree HEAD` 0 命中）⇒ G16 升三面（电池⇄文档⇄git index）；同日同机噪声实测（work=4 带宽最高 255.8%，40% 阈值被 −40.1% 踩穿）⇒ work 4→32、阈值 50%、加口径腿；C1_HARD 16→9 逐件评审 + 完成态等待两种错法（等计数变化 / 等中间态）均被实测否证
- **卷34** `07-next-steps.part128.md` — r99 的 **P0 段全文**（含 CI 五条红的逐条归因：远端缺 `v1.8.1` tag / live_sync 在册旧红 / measure_entry 是其下游影子 / `browser_engine_declare E2b` 未归因）。迁移动因 = part127 追加后顶到 4,180B 撞 4KB 单卷硬限，原卷只留指针＋ 本会话踩坑逐条 ＋ 电池 129→132 ＋ **r99 入口**（①采第二份 ramp 台账让漂移尺脱离诚实未验）
- **卷35** `07-next-steps.part129.md` — **r100 收口（上）**：本轮四项改造各自的复算命令与回执（①三态纪律 ②中位数口径＋**检测限未下压的负面结论** ③`__pendingTurns`+U2g ④peers 错峰重采 16/16 落盘、5 族 rc=1 逐条归因）
- **卷36** `07-next-steps.part130.md` — **r100 收口（下）**：两条会再犯的教训（同日台账后缀字典序＝时间序；LOC 提取让 `timing_coupling` 改判、基线未动）＋ **r101 入口四条**（按档定阈／被审面扩到跨函数消费者／假理由普查／403 补采）＋ ⏸ v1.8.1 仍 blocked（live_sync 现两件）
- **卷37** `07-next-steps.part131.md` — **r101 收口与 r102 入口**：把 12 条 `debt-open` 改成完成态等待（C1 从 22 往下走的唯一正解）／`ledger_age` 摘牌／采一轮带 `machine_tag` 的阶梯台账后分桶重算阈值／peers 两件（SNAP 重采 + 403 补采，前置=先建断点续采）／CHANGELOG 吞行常驻判据／`build_dataset.py` 写侧锁 newline／AIC 13 项行尾红归其会话

