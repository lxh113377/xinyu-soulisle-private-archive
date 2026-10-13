# 07 - 下一步

> 本文件记录下一步行动项，按优先级排序。
> **⚠️ 新对话恢复上下文入口。P0 必须永远有一条可执行指令。**
> 本卷是**索引壳**（≤4096B，R161）：只留「可执行摘要 + 指针」，长段落一律迁分卷（背景见 part17）。

## 🎯 主线目标 — Java 全栈改造（2026-09-20 老大定方向）

J1–J3 已落地，前端零改动；背景块/选型假设/JDK17 与 Maven3.9.9 环境实证（含 JAVA_HOME=JDK8 的坑）全文 `part17`。

## P0 — 必须做
- [ ] 🔴 **R172-01 词表提交面分叉（上线件与权威源是两份不同字节）**（2026-10-14 r172）：`data/emotion-lexicon.js` 磁盘两侧 `cmp` 相同，而 HEAD 两侧 blob 不同（`b6bb4506` src vs `56fffc7a` deploy，5068B vs 4976B）⇒ 部署取提交面，**上线的那份是旧词表**。归因 = `77e7163`（10-12 00:55）把两侧提交成不同字节。**阻塞（不是我方能单方完成）**：这两个文件正被并行会话在途修改（`git status` 双双 ` M`，工作树里已对齐未入库）⇒ 不代提交他人 WIP。前提（复算）：`git rev-parse HEAD:src/data/emotion-lexicon.js HEAD:deploy/xinyu/data/emotion-lexicon.js` 两侧同号 且 `python _test/deploy_sync_check.py` rc=0。另欠一条**词条级差集**（本轮只量到字节，R172-05）。
- [ ] **R172-02 perf 作业的关闸配置尚无远端回执**（2026-10-14 r172）：本轮把 `.github/workflows/perf-baseline.yml` 的 perf job 改成 `XINYU_GUARD_ENABLED: false`（带默认 `burst=20` 时并发档 48 发只有 18 发拿到 2xx ⇒ rc=2 无读数；阶梯档单 rep 对 `/api/emotion` 是 2048 发，任何 burst 都跑不完）。**未闭环原因 = 推不上去**：本地独有 210 提交 ⇄ 远端独有 18 提交，本轮禁 force-push（会毁远端那 18 个）⇒ 需先与并行会话对齐推送顺序。完成标准：`gh run view --json conclusion` 该 job = success 且日志含 `闸态=unguarded`。
- [ ] 🔴 **语音识别方言优化（r172 spike → r173 A1 → r174 A2，2026-10-14）**：证据全文
      `交付物/语音识别/ASR方言识别可行性-spike-2026-10-14.md`，决策 #12 已登记 `03-tech-stack.md`。
      **98%/92%/噪声降幅≤3% 三项明确不承诺**（引擎是浏览器 Web Speech、我们碰不到；6 方言里仅粤语有 CC0 语料，
      四川话 ND 禁衍生，东北/上海/闽南无成体系公开语料）。
      **A1 已完成**：`_test/asr_replay_check.py` + `_test/asr_replay_fixtures.json`，四态 PASS/FAIL/UNVERIFIED/GAP。
      **A2 已完成**：新增 `src/js/asr-normalize.js`（口头语清洗）+ `voice-call.js` 两级接线（选候选与清洗分离，
      保住 pickBest 零改写不变量）+ index.html/sw.js 登记 + deploy 两面同步。
      实跑 `ASR-REPLAY-PASS 样本=24 全过 E6=12/12 已知缺口=0 E5相对下降=100.0%`（rc=0，自检 11 腿 PASS）；
      回归 `voice_call_check` C腿23/23 PASS、`browser_check` ALL-ASSERT-PASS、`js_syntax` 37/37 PASS。
      **A2 被 E5 门槛推翻过一次自己的设计**：初版剥句末语气词，E5 实测 CER 0.0288→0.0462（相对 -60%）判红
      ⇒ 立红线三「句末语气词一律保留」（情感陪伴场景语气本身是信息），只保留句首口头语清洗。
      ✅ **公网已发布**（老大 10-14 拍板「只部署我这四个文件」）：`public_check` 线上 **判红=0（10/10）**，
      `/api/chat` **200**，线上 PRECACHE 30 条全可达且含 `js/asr-normalize.js`。提交 `b8cc842`（12 files/1410）
      + `5218164`（app.js 括号 1 行）。
      🔴 **发布中踩三坑，已全部处置（详见 spike 报告 §10）**：① `cca2ce5` 把括号笔误提交进
      `deploy/xinyu/js/app.js:571` ⇒ 整站不初始化（本地工作树已修好，属「本地绿+线上白屏」，被受理面单独验抓出）；
      ② 我第一次 `wrangler pages deploy <产物目录>` **把 Pages Functions 丢了**（Function 从 cwd 下的
      `functions/` 找，不在产物目录里）⇒ 线上 P6/P8/P9 判红 3 条，改以 `deploy/` 为 cwd 重发、回执出现
      `Uploading Functions bundle` 才转绿；③ `git commit` 在 numstat 核对与提交之间的窗口卷走并行会话 8 件，
      `reset --soft` + 按路径撤暂存后重做为 12 files。
      ⚠️ **三件未收**：① `_test/asr_replay_check.py` **仍未接电池**（r105 铁律）；
      ② `offline_shell_check` **A10 红** = 工作树 `src/index.html`（他人轮未提交）引用 `kb-source-panel.js`
      而 `src/sw.js` 预缓存未登记 ⇒ 属他人轮缺口，其静态审计中断使 R8/R9a 跑不到，R9a 已用直连独立验证；
      ③ **git 未推送**（本地领先 origin 216 / 落后 18，仓库早已分叉，推 216 个提交不在本轮授权内）。
      下一步 = 电池接线 → **B1** 抄决策 #11 产线起 `ml/asr_server.py` sidecar（SenseVoice 粤语 /
      sherpa-onnx 流式普通话）。
- [ ] ✅ **心理学知识库已推进到第 14 轮（r177-KB14，2026-10-14 实测 210 条）** —— 本行以下仍记第 12 轮(r172)原状，**以本行为现状**：
      210 条 / 35 篇章（A45 B84 C39 D42，E=0）｜判据全绿：`psych_kb_build --check` PASS、`--selftest` 16/16、integrity PASS（零悬空零孤岛·索引双向差集 0·关联边 840·有进出 210/210）、`kb_wiring` K1-K7 PASS、`kb_citation` C1-C7 PASS、`kb_source_panel` P1-P3 PASS、`core_capability_baseline` PASS（N1 105/99%/6-6、N2 31/31、F1 rc=0，双能力无回退）、`psych_kb_doi_audit`（联网人工轮工具）711 行 / 430 唯一 DOI / 硬性错配 0；`size_budget` 我方两项转 OK（psych-kb.js 196,791/206,631、psych-kb-sources.js 350,109/367,615，按「实测 +5%」惯例重登记并写明理由；同轮余 3 项超限 app.js / face-engine.js / face-smile-rules.js 实测为并行会话在途件，不归本轮、未代改）。
      **第 14 轮内容**：① 新域 `WV`（工作价值观与选择过载）+ 新篇章 35，9 卡（代际工作价值观 Twenge 2010、选择过载经典实验与其两份元分析之争 D 级、最大化/满足者与求职最大化代价、生涯决策困难 10 类结构、双元认同两轴、后悔时间形状、「选错了/还能改吗」回应纪律）；② PSY-HU-006 幽默双刃（Bitterly 2017，闭环第 13 轮遗留 N7「幽默是否降低信任感/感知专业度」）；③ PSY-ID-006 生涯干预元分析（Milot-Lapointe 2025 + Langher 2018，补证 N3，ID-004 按更正规则补行、C 级不变）；④ `psych_kb_doi_audit.py` 抽取面自检门（N2 闭环：非 ASCII ⇒ rc=1 作废读数，3 腿 selftest 含变异腿）。
      **部署未做**：KB 两件数据件已同步 deploy 副本（双侧 SHA256 一致、`deploy_sync_check` 工作树面 DIFF 归零、零密钥扫描公网侧 True）；但提交面 2 项 DIFF（index.html / chat-agent.js）收尾实测为**并行会话当时正在把 deploy 副本对齐 src**（两文件工作树 ` M` 未提交）⇒ 按并发纪律不代提交他人 WIP、不代部署，留待并行会话收敛后整跑电池再上线（遗留 N1/N8，详见 `交付物/心理学知识库/_下轮计划/2026-10-14-第14轮遗留.md`）。
- [ ] 🔴 **心理学知识库第 10 轮入口**（r166-KB，2026-10-13，**已被上条覆盖**）：沿革 = 第 5/6 轮 34 条（17-22 篇）→ 第 7 轮 r132 12 条（23/24 篇，144 条，README v1.7）→
      第 8 轮 r134-KB 2 条 EM-005/006 + 双库并轨 + 数据件改 `ensureKb()` 懒加载（146 条）→ 第 9 轮 r135-KB EW 域 7 条（153 条，README v1.8）→
      **第 10 轮 r166-KB 11 条**：EW 追加 6 条（PSY-EW-008~013，并入第 9 轮篇章 25）+ PO 域首批 5 条（新建篇章 26），**164 条 A41/B65/C25/D33、E=0，README v1.9**。
      **⚠️ 本轮撞号事故与处置**：开工只读了会话初的快照，落卡时发现并行会话（r135-KB）已落盘 EW 域 7 条并升 README v1.8——两轮同取 `PSY-EW-001` 起，
      `psych_kb_build` 当场判红「条目 ID 重复」⇒ 按「先落盘者保留原号、后落盘者改号并入」处置（我的 6 条改号 EW-008 起并入其 `25-表达性书写与倾诉披露.md`，
      我原拟文件 `25-表达性书写与情绪披露.md` 删除，[[关联]] 互指，篇章头注/索引 25 行/README v1.9 三处记明口径）。
      **教训（写进流程）**：多会话项目里「定选题→取号」前必须**重查目录与取号面**，会话初读的快照会过期；判据当场抓撞号是兜底不是流程。
      判据四件常驻全绿：build `--check` PASS（164 条）｜integrity PASS（零悬空零孤岛、索引双向差集 0、关联边 629）｜size_budget psych-kb 149,701/157,186 OK｜
      `core_capability_baseline_check` PASS（N1 105 条/99%/危机 6-6、N2 31/31、F1 rc=0，双能力无回退）。
      **顺带修**：integrity 抓住第 9 轮 7 行索引「一句话」与卡内不逐字一致（EW-001~007）⇒ 按「卡为唯一真相源」改正索引面。
      **未收**：① KB 新内容上线（仍受「先清存量红再上线」+ 语音轮在途约束，r131 口径不变：那三面入库 → deploy_sync_check 归零 → 整跑电池 → live/public）；
      ② `--links` 联网复探（人工轮工具，上轮 7 项未核待单线程复探）；③ D 级 33 条人工抽查提示位；
      ④ size_budget 三项**他人轮存量**超限（face-engine 26,561/25,317、face-smile-rules 18,405/14,911、voice-call.css 4,711/4,690）不归本轮，待其轮次自理。
      **选题队列（机器给）**：`python _test/psych_kb_integrity_check.py --backlog`（现读 164 卡 / 未闭合 400+ 项；最重面 06 多模态、14 哀伤、20 拖延）。全文 `part162`
- [ ] 🟠 **表达优化专项 r171 第 3 轮（2026-10-13；前两轮 = r117 / r134）**：语料 **161→174 条**
      （A90/B58/C8/D18，E=0；定向补最薄三层 joy 11→16 / anger 15→22 / 庆祝 11→16）；
      **机制改动 = 注入候选带「适配条件」fit**：构建期三级取（卡面直写 → 用法压缩 → 场景回落），
      实测 174 条 = 直写 26（含 `04-哲学思辨` 整卷 22 条）/派生 148/回落 0；注入面排序改用 quote+fit 双信号、
      排名前 2 条带出 `（用：fit）`，上限 420 **未动**（不挤知识库 N2 面）。同轮删掉产物里零消费者的
      `usage` 截断副本 ⇒ **条目 +13 而首屏 −20,914B**（104,128→83,214），`size_budget` 逐文件上限
      **下调** 109,334→86,960（实测 +5%，理由登记在代码注释）。判据：`wit_quotes_build --selftest` 20 腿
      （补齐 r134 清场丢掉的"真面产物改一字节必判不一致"变异腿 + 其对照腿）、`quote_wiring Q8`
      （fit 在位 + 首候选逐字对账 + 评测旗标零泄漏）、`quote_eval --selftest` 16 腿**已接进电池**（190→191）。
      🔴 **本轮欠着的唯一验收件 = 承载面 15 例配对读数：未验**。一手取证：**DeepSeek 余额耗尽**
      （HTTP 402 Insufficient Balance）⇒ 在线 AI 全链路（本地 jar / fat jar / 公网两线）现在实际都落离线模板，
      **只有老大能解**（充值或换 Key）；本轮两次跑批（约 700 次调用）确实是余额消耗方之一，如实记。
      前提命令：`python _test/quote_eval.py --base http://127.0.0.1:8129 --focus heavy15 --judges 3 --reps 2`
      （上游断时量尺现在 17 秒点名退出 —— 修前是 38 分钟空跑且明细全丢）。
      4 例冒烟的方向信号（**不构成判定**，p=0.25）：full-vs-old 配对 −0.50/−0.50/−0.88，
      rules-only 臂 0/8 全胜 full ⇒ 下一轮若承载面仍"受损"，机制二选一：候选 5→1 条，或退 rules-only。
      全文 `交付物/表达语料库/验收报告.md` r171 节（r134 节含 `_test/` 清场事件披露，勿删）
- [ ] 🟠 **存量红已清、待整跑复跑 + 双线上线**（老大 10-12 定「先清存量红再上线」）：G8（评测集入库）／
      loc_guard 4→0／G12（切 v1.8.3 打 tag，三源同绿）三项已清，回执 `REPO-CONFIG-PASS 18/18`。**下一步 = 整跑电池复跑，
      绿则双线上线**（单跑全绿 ≠ 电池绿，见 part159 的教训）。全文 `part159`
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
- [ ] 🔴 **R173-face：面部情绪支「90% 断言」三处缺口（2026-10-14 r173）**，证据与逐类数字见
      `交付物/面部情绪识别-优化与测试报告-2026-10-14-r173.md`（本轮新跑，非引用旧值）。
      **本轮已闭环**：① 新建 `_test/face_prf_report.py`（F13 逐类 P/R/F1+混淆矩阵+切片，
      一眼看出 fear 召回率长期 = **0**）② 新建 `_test/face_latency_check.py`（F14 真脸 y4m 假摄像头，
      实测单帧整链 **p95 7.5~8.5ms ≤ 100ms**，CPU delegate 路径未测列债）
      ③ 修 fear 召回 0（取消 `need:{fear:2}`；同时把遗留项 **C1 fear@0.12 笃定错报关闭**：笃定错报 1→0，
      有把握帧 96.7%→**100%**，代价是不确定帧 40.0%→**42.0%**）④ 新增 8 个细分子维度
      （neutral/duchenne/social/masked/worry/tense/micro/asymmetric，**UI 未接线**）。
      **未闭环三缺口**：**M3** 光照/角度/人群切片**不可测**（12 张 fixture 无 meta；luma/yaw 引擎已在算、
      导出没存）⇒ 先给 `face_au_export.py` 加 meta；**M1** fear/sadness/disgust/contempt **零真实标定照**
      ⇒ 这是「综合 ≥90%」唯一真门槛（REAL 语料现 **83.3%**，差 6.7 个点）；**A6** 2 张中性真人照被读成低落
      （blendshape 不做身份归一化，个体差异）⇒ per-person 静息基线，但**单张照片自减是自比恒等**，
      必须有同一个人的「静息+表达」成对样本才算证据。
      ⚠️ 本轮**未推公网**：face 面 deploy 副本已逐字节归零，但仍有并行会话在途件（`css/style.css`、
      `data/psych-kb-sources.js` MISSING 等）⇒ 按纪律不代同步，待在途收敛后走标准发版链。
      **追加实测（同轮补腿）**：F14 加 `--delegate CPU` 腿后量到最差情况 —— GPU p95 10.7ms /
      CPU p95 15.5ms 均远在 100ms 内，但 **CPU 单帧 max 114.2ms 偶发越线** ⇒ 「≤100ms」只在
      p95 口径成立；若需求是"每帧必达"，取舍是降 fps（牺牲跟手度）或锁 GPU delegate（牺牲设备面）。
      **同轮再闭两项**：① 8 个细分子维度**已接进界面**（表情 chip + 悬浮 HUD，上限 3 标签、
      刻意不加色点；`src/js/app.js` + `src/css/style.css`）② 新建 `_test/face_subs_check.py`（F15）
      9 用例亮/灭双向断言 + **5 条针对性变异腿**（第一版"抽掉 rules.subs 整块"的变异实测**无效**——
      subsOf 对 R.subs 有硬编码兜底；改为按维度逐条打，其中 weak.on 方向、tense 的 OR 结构、
      ratioOn 该盯哪个维度，各错过一次，已把错法写进注释）。

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
- **卷150** `07-next-steps.part150.md` — **r127 收尾推荐 R127-01..05**（影子族判据=**已落 `fc48446`**；face-diag S1 低强度分母可开工；issue 维验收口径改判；向 peers 提 issue/P0R 待授权；漂移第五次值守）+ 本轮四条一手自纠（夹具形状/口径虚高/百分号/rc 管道）。
- **卷152** `07-next-steps.part152.md` — **r127-S6 第 5 维「可裁决选项清单」**（向量长记忆 / i18n / 插件协议：代价实测 + 可复算前提 + 最小可逆试验；三项均引既有「维持不立项」判定，只补决策所需材料、不重开判定）。
- **卷153** `07-next-steps.part153.md` — 07-next-steps 分卷（R199 自动拆卷）
- **卷154** `07-next-steps.part154.md` — 07-next-steps 分卷（R199 自动拆卷）
- **卷43** `07-next-steps.part160.md` — **r130 收口（八维对标四项改造）**：性能可复算尺／成本总量闸／记忆可携带／教程防腐烂，各闭合一个维度；棘轮 H1-H4→H1-H6；电池 185→188、JUnit 134→169；**轮次号入场先看 HEAD 提交信息（r129 已被并行会话占用，本轮取 r130）**。r131 入口五条见该卷
- **卷155** `07-next-steps.part160.md` — 07-next-steps 分卷（R199 自动拆卷）
- **卷156** `07-next-steps.part161.md` — 07-next-steps 分卷（R199 自动拆卷）
- **卷157** `07-next-steps.part163.md` — 07-next-steps 分卷（R199 自动拆卷）
- **卷158** `07-next-steps.part164.md` — 07-next-steps 分卷（R199 自动拆卷）
- **卷159** `07-next-steps.part165.md` — 07-next-steps 分卷（R199 自动拆卷）
- **卷160** `07-next-steps.part166.md` — 07-next-steps 分卷（R199 自动拆卷）
- **卷161** `07-next-steps.part167.md` — 07-next-steps 分卷（R199 自动拆卷）
- **卷162** `07-next-steps.part168.md` — 07-next-steps 分卷（R199 自动拆卷）

