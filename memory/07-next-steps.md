# 07 - 下一步

> 本文件记录下一步行动项，按优先级排序。
> **⚠️ 新对话恢复上下文入口。P0 必须永远有一条可执行指令。**
> 本卷是**索引壳**（≤4096B，R161）：只留「可执行摘要 + 指针」，长段落一律迁分卷（背景见 part17）。

## 🎯 主线目标 — Java 全栈改造（2026-09-20 老大定方向）

J1–J3 已落地，前端零改动；背景块/选型假设/JDK17 与 Maven3.9.9 环境实证（含 JAVA_HOME=JDK8 的坑）全文 `part17`。

## P0 — 必须做
- [ ] 🔴 **心理学知识库 r129 收尾六件（第 6 轮入口）**：篇章 18 失恋与被拒（RJ）待入库 → README 升 v1.4
      与构建器 `KB_VERSION/BUILT_TAG` **同批**改 → KB 新内容上线（本轮故意没部署：语音轮在
      `app.js`/`chat-agent.js`/`voice-call.js` 有未入库改动）→ src 侧「回复里的〔依据:编号·级〕必须与实际注入
      编号集合比对，未命中标未查证」→ `wit_quotes_build.py` 同族接线 → 选题队列改由
      `python _test/psych_kb_integrity_check.py --backlog` 给（现读 116 卡 / 未闭合 332 项）。全文 `part151`
- [ ] 🔴 **每轮第一要务：表情识别 · 语意理解**（用户 2026-10-11 立规）—— 每轮必跑
      `python _test/core_capability_baseline_check.py`（棘轮只降不升）；目标/指标/轨迹 = `memory/10-core-capabilities.md`
- [ ] 🔴 **表情识别准确率攻坚（face-diag，2026-10-12 立）**：诊断+方案全文 = `memory/11-face-accuracy.md`
      （主壳+四卷）。实测根因：真人 0.2~0.45 低强度段表情系统性沉底 calm（轻微笑 .22/轻怒 browDown .20 实测 MISS），
      标定史全是表演级强度（Duchenne 4 张/peak 17 合成）。老大定口径：**有把握帧 top-1 ≥95% + 不确定帧 ≤30%；
      端到端 ≤500ms 且单帧 ≤100ms；路线=规则派**。执行次序：S4 真照片 AU 批跑尺（T+7，先尺后改）
      → S1 动态分母（T+3）→ S2 弱信号档（T+5）→ S3 anger 复标（T+10）→ M1 权重复标（T+28）。排期假设待老大确认。
- [ ] 🟠 **[推荐:R116-01/02｜用户操作]** 语音通话已落地但**只在本地**：main 与 origin 分叉 18/52 ⇒ push 待老大选；
      公网未发布 ⇒ `offline_shell` R9a / `live_sync` / `live_sync_alt` 三条必红。全文 `07-next-steps.part139.md`
- [ ] WF-r97-v1.8.1发布链 推 main+tag v1.8.1+CI 回执+Release（Pages 面未发布，CI 电池不豁免 live 面）（由 flow 登记；状态: blocked）
- [ ] **J3/J4 变现** [推荐:R35-02]：① ② ③ 三件均已实测就绪 ⇒ **唯一阻塞 = 老大给目标机器**（IP/登录/安全组）。`part17`
- [ ] 🟠 [推荐:R83-02] **共享环境隔离待老大**：陪聊 / iCAN 门店 / 医 同居一个 CloudBase env，
      子目录避让只是止血；命名空间或独立 env 属跨项目决定，本轮未擅动。`part92` §②
- [ ] **同族坑收口**：台账 `part18`/`part20`；G9 常驻 `repo_config_check`。
- [ ] 🔴 **E2 棘轮降数（r97 首务，r105 已降 3 件）**：`browser_engine` 统一入口现 **已接 10／未接入 21**（基线 23，起点 31）。
      逐个接走手写回退的套件；判据 `python _test/browser_engine_declare_check.py`（只降不升），每改一件跑 AST 清点。`part135`
- [ ] 🔴 **[推荐:R105-01｜用户操作]** **G12 与「本地/远端 main 分叉」一并待选**：`git ls-remote origin refs/heads/main` = **e8462ca**
      （远端 main 正停在只改版本号三处的 v1.8.2 提交上），`rev-list --left-right --count origin/main...HEAD` = **18 / 41**
      ⇒ 普通 push 必被拒。三选一：merge 并回旧线 ／ force 覆盖（重写已发布历史，须先 bundle 备份）／ 现状挂账并把对外口径改成「v1.8.2 未生效，下一版从 v1.8.3 起」。全文 `part136` §1
- [ ] 🟠 **[推荐:R105-02｜agent 自动]** **BLIND-RED 余下 4 条的崩溃面**：`j4_memory_check` 死于未捕获
      `playwright TimeoutError: wait_for_function 15000ms`（r105 ③ 同族第二形态：超时须落「未验/点名红」而非抛栈）。
      前提：`python _test/j4_memory_check.py` 复现；`lightshow` 那条归并行会话（对照组真信号）。`part136` §2
- [ ] 🟡 **[推荐:R105-03｜P2 可选]** **E2 继续降数**：现 21／基线 23，最便宜的一件是 `_test/mobile_check.py`
      （单一 `launch()` 出口）。每接一件跑 AST 清点。`part136` §3
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
- **卷38** `07-next-steps.part132.md` — **r101 部署段（公网两条线重部实测）**：Pages 直传的 Functions 取数面是 **cwd** 不是上传目录（第一发把 `/api/chat` 打成 405 的一手证据与修法）＋ Pages git 连接自 `c567ad3` 停摆（合并前先核 build output 目录）＋ `tcb hosting deploy` 被 MSYS 改写云端路径（`MSYS_NO_PATHCONV=1` 正解，误造的 1 个野对象已删并复量）＋ 桶内 24 个 09-30 野键待裁决 ＋ LFS 属性⇄裸 blob 不一致致新 clone 恒脏、rebase 被拦（绕行=临时 clone + cherry-pick）＋ linked worktree 的 `--autostash` 写的是**全仓共用** `refs/stash`

- **卷39** `07-next-steps.part134.md` — **r104 收口（判据层对标杆）**：四项改造回执（整跑韧性／peers 受理面重采+端点修复+断点续采／耦合尺 C1 29→18 含 j4 改判 unobservable／peer_memory 声明位摘豁免）＋ TDZ 核验结论（并行会话已修但未入库）＋ **r105 入口**（face 7 条 debt-open 结转、perf 分桶、R1 切版待裁决、共享端口无属主协议）。

- **卷40** `07-next-steps.part135.md` — **r105 收口（受理面假门/棘轮/崩仪器）**：G16 孤儿判据接线（两侧先测）／E2 24→21（3 件收编，判定行带引擎身份）／vendor_freshness 五字段门＋`detect:null` 显式语义／端口 8123 属主四档协议（默认只停本工具起的）。**新事实：`v1.8.2` tag 不在 main 祖先面上**。
- **卷41** `07-next-steps.part136.md` — **r106 入口**（G12 方向待选／BLIND-RED 余 4 条崩溃面／E2 继续降／face_check 结转前提／rollup 派生件等干净窗口／peers 错峰重采）。
- **卷42** `07-next-steps.part138.md` — **r105 追加段**：执行器改造（挂起第三档根因实测确认，换后整跑跑完 131/143、红 22→11、BLIND-RED 6→1）＋ 一条"把一次性迁移取证当不变量"的腿改判（AST ⊆ 子串 + 差集解释义务 + 变异腿）＋ **分叉三条路代价实测**（merge 冲突 9 文件／force 仅作废 v1.8.2 一枚 tag／挂账改口径几乎零对外代价）。
- **卷42** `07-next-steps.part137.md` — 07-next-steps 分卷（R199 自动拆卷）
- **卷140** `07-next-steps.part140.md` — **r118 语音腿补口轮**：三条真缺口（降噪显式化/无 TTS 兜底/长轮次稳定）+ 决策 #11 本机神经语音引擎；判据 11/15→**15/15** 且四腿变异演习 4/4；**两条未闭环均被客观前提拦住**（公网发布撞上他人未入库内容已在线上；分叉 merge 撞上并行会话正在提交），各带回滚锚与开工先决条件。

- **卷148** `07-next-steps.part148.md` — **r126 入场与四项回执**：让位轮次号（并行半程改写）+ G4/G16 两条常驻红清到 4→2 + 台账形状契约推广（全目录 53 族）+ 教程四章 + cap-channel 首采。
- **卷149** `07-next-steps.part149.md` — **r126 收尾推荐 R126-01..08**（切版/分叉 18/72 需拍板；通道重采节律、拟编辑文件先比字节再动手、按线程记账、漂移第四次值守）+ 他人面归因表。
