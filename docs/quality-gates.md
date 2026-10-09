# 判据体系明细（从 README 迁出，r39 体量体检）

> README 是每轮注入件，超 16,384B 预算即算**每轮重复付费**；本节明细改放这里，README 留指针。
> 内容逐字迁自 README「## ✅ 验证」一节，未改写（取证见当日会话日志）。


```powershell
python _test/run_all_suites.py           # ★ 全量电池（套件条数以 `--list` 实算为准，本文件不抄数；逐条直取 rc，聚合不掩盖单项失败） ⇒ 更正注 r100：新增 **BLIND-RED 档**（`blind_reds()` 纯函数 + `blind_selftest()`）——rc=1 却**一行判据结论都没有** = 仪器自己崩了，不是产品红。此前这类与真红在收口面同形（r99 三处 Playwright 超时的现场），判红名单照收但没人知道该查的是判据而不是产品代码。红照判、rc 判定一字未动，只是单列点名；桩双向含「FAIL 行即结论不得再记盲红」「rc=2/rc=3 不抢档」。
python _test/fault_injection_check.py    # r51 故障注入：上游 500/非JSON/断连/黑洞挂起/恢复 五类，看界面说不说真话（徽章同帧翻面 + hit_count 全非零证注入真打到通道）
python _test/fault_injection_check.py --selftest  # r51 判据自身桩：12 例（含「注入 0 命中记 INVALID 不记 PASS」+ r52「归因缺失总预算内也判红」）
python _test/peer_fault_probe.py --selftest       # r51 故障可见性对标探针桩：6 例（边界=不得写成报错体验对比结论）
python _test/memory_recall_check.py               # r52 长期记忆召回：拦 /api/chat 读 post_data，证「落库的记忆真进了 messages」；R4 清库后必须消失（反向腿）
python _test/memory_recall_check.py --selftest    # r52 召回判据桩：9 例（含「恒真注入」「没读到我自己写的那块」「原话进 prompt」三形）
python _test/peer_memory_probe.py                 # r52 记忆/上下文面对标：16 仓三通道，引用边只认正向回执（none-in-sample/NA 两态不构成结论）
python _test/peer_memory_probe.py --selftest      # r52 记忆探针桩：9 例（歧义形状四连：storage 含 rag／React context／泄漏件／GPU memory）
python _test/readme_troubleshooting_check.py      # r52 README 排障段 ⇄ 代码状态标签双向对账（T1 漏写状态／T2 凭空造状态 都判红）
python _test/readme_troubleshooting_check.py --selftest  # r52 文档对账桩：5 例（含"取数面退化成空集"与"抽到注释"两形）
python _test/context_budget_check.py             # r53 上下文预算：14 轮实测窗口内送 10／发前 26，截断 16 条须由概要注意送达且条数对账
python _test/context_budget_check.py --selftest  # r53 判据桩：10 例（含"无概要""假条数""常量注入""窗口缩水""原话进概要"）
python _test/headers_csp_check.py             # r54 安全头/CSP：本地按 Pages 语义回放 _headers，逐路径逐条对账 + CSP 下应用可用
python _test/headers_csp_check.py --selftest  # r54 判据桩：8 例（含"H5 夹具没在施加 CSP"与"H0 取数面为空"两条专属反例）
python _test/headers_csp_check.py --live https://xinyu-soulisle.pages.dev  # r54 线上复测：入口 CSP 在位且无放宽；不可达按 UNVERIFIED 带状态码（未进 CI，见报告 §6-1）
python _test/peer_sec_headers_probe.py --selftest  # r54 安全头对标探针桩：6 例（csp⊂.csproj、helmet 散文化两形歧义）
python _test/clean_clone_check.py         # r43 干净克隆可跑性：从 HEAD 克隆到临时目录再跑，未知报错即红（已登记缺口须计数命中，0 命中要销账） ⇒ 更正注 r100（三态纪律）：导航/求值层异常不再逃出进程——页面驱动段提成 `drive_page()`，Playwright 超时折成 **C2 判红 + 异常原因**（**不**折 UNVERIFIED：走到这里说明浏览器起得来、克隆也建成了，那份页面真打不开正是要抓的缺陷；环境档由 git/克隆/launch 三处各自 `return 2`），并把 C3/C4/C5 记未验、在结论行点名（分母不缩水）；`guarded_main()` 兜底腿 `C6` 保证任何未预期异常也留下一行 `CLEAN-CLONE-FAIL`。新增演习口 `--nav-timeout`（`1`=逼真实超时，`abc`=让仪器自己崩）。真机三向回执：正常 `CLEAN-CLONE-PASS` rc=0 ／ `--nav-timeout 1` rc=1 点名 `TimeoutError: Page.goto: Timeout 1ms exceeded` ＋ C3/C4/C5 未验 ／ `--nav-timeout abc` rc=1 出 `C6`。同轮 `rescan_shots_check.py`（腿名册 12 条 + `report()` 单出口 + `SX` 兜底）与 `public_check.py`（腿名册 10 条 + `PX`）按同一口径修，演习口同款。
python _test/data_rights_check.py            # r44 数据权利：披露随模式翻转 + 删除回执并复核归零 + 导出与计数对齐
python _test/peer_data_rights_probe.py --selftest  # r44 对标探针桩：10 例（路径 7｜README 2｜边界 1）
python _test/a11y_check.py               # r42 运行时无障碍：6 状态 x 2 主题 x 含 experimental 规则集 + 动效降档像素实测 + 反例自证
python _test/a11y_check.py --selftest    # r42 判据自身桩：合成图像走同一条像素通道 + A5/A7 双向 12 例
python _test/peer_repro_probe.py --selftest  # r43 可复现面探针桩：19 例（路径 10/钉版 6/边界 3），含「一行 JSON 也逐条数分母」专属反例
python _test/browser_check.py            # 离线降级 / 双色 / 滚动淡入淡出，输出 ALL-ASSERT-PASS
python _test/deploy_sync_check.py        # src → deploy/xinyu 三类比对（MISSING/DIFF/EXTRA 归零）
python _test/engine_consistency_check.py # JS 引擎 ↔ Java 引擎逐项对账（词表结构级）
python _test/java_test_guard.py          # r41 in-build 单测资产守卫：用例数下限 + pom 依赖在位 + CI 构建步未跳测（T4）
python _test/peer_test_asset_probe.py --selftest   # 对标测试资产面的匹配器自证（16 仓反例：依赖目录/包标记不算用例）
python _test/emotion_wiring_check.py     # 情绪后端化接线：接线顺序/公网零开关/危机短路/熔断回落/双端一致（9 项 + --selftest）
python _test/strategy_check.py           # 共情策略表 ↔ 词表成对性（--selftest 注入分叉证判据非恒真）
node _test/emotion_eval.js               # 前端情绪评测集复跑
python _test/stream_contract.py          # A 非流式契约不破 / B SSE 含内容帧≥2 / C 前端逐字且回落不冒充
python _test/ux_guards_check.py          # TTS 朗读 / 对话窗口化 / 响应式与粒子降档（逐项 21 判据）（判据条数由脚本自印「合计 N 项」，本行不抄数——抄了就会漂）⇒ 更正注 r100：U2 的 45 条连发不再 `wait_for_timeout(6000)`，改等产品自报的 `window.__pendingTurns` 归零（`src/js/chat-agent.js` 的 `turn()` 包 `respond`，异常与提前 return 都过 `finally`；轮询按 raf——`respond` 的 finally 减到 0 之后 `app.js` 的渲染在同一微任务续体里紧接着跑，所以帧边界上看到 0 时那一轮必然已渲染）。新增腿 **U2g**；双向反例实测：抹掉钩子 ⇒ 等待超时、该腿判红并印 `typeof=undefined`；真往返 ⇒ 归零通过。
python _test/size_budget_check.py        # 首屏体积预算 + 「新文件必须登记」覆盖判据（漏登记即红）
python _test/vendor_freshness_check.py   # vendor 完整性哈希 + 版本对账；--check-upstream 报上游漂移
python _test/benchmark_metrics.py        # 对标源数据台账（16 仓指标 + 与上次快照逐字段漂移）；联网采集，人工轮次跑
python _test/bench_quality_gates.py      # ↑ 的「质量门同址尺」子系统（r95 整块迁出，14 节点 ast.dump 全等）：五类「能不能让构建失败」+ CI 面相关性取样 `qg_ci_pick` + 三值门面行 `qg_gate_line`。不是电池条目（无 main），由 benchmark_metrics 的 `--quality-gates` 通道调用；变异腿必须改 **本模块** 的全局名（改 benchmark_metrics 的同名变量=空腿，本轮实测两条腿各踩过一次）
python _test/peer_maintenance_probe.py   # 「维护状态」维的同址尺：**30 天提交率**（r95 立）。分腿=分页 Link 的 `page=(\d+)` 正则 / 独立路径=`search/commits` 计数，两腿不等即该格判不可用（不取平均）；self 侧走 `git rev-list` 并印**历史跨度**（本仓仅 13 天 ⇒ 30d 读数无横比资格，写明不横比）。联网采集，人工轮次跑；`--self-only` 零网络、`--selftest` 14 条（当日值，现值由脚本自印；含 Link 字段序颠倒 / `+` 未编码 / 对账非恒真 三条变异腿）
python _test/peer_hygiene_probe.py       # 发布可得性/维护响应/工程治理三面（r37 立）。**r96 改判两处**：① 假 NA（样本陈述写成总体陈述）——原 B 面只取 `per_page=20` 样本，客户端排 PR 后样本落空就写 `NA(无真issue)`，而人口是另一件事；现服务端 `search/issues?q=repo:X type:issue is:closed` 单独取人口（实测 `my-neuro` 实有 **102** 条、`chibi` 7 条，旧台账两处都记成 NA），`NA(no-closed-issue)` 仅当人口真为 0 才可达，样本落空改判 `NA(sample-miss …人口=N)`；② `SELF` 常量自 r37 定义在 `:23` 却**零使用点**（docstring 写着"同一把尺量自己 M5⑧"没兑现）⇒ 现 self 进分母，`--self-only` 只跑 self。`--selftest` 12 条（当日值，现值由脚本自印；正例/变异/边界，含"摘掉人口闸后 my-neuro 必得旧假 NA"）
python _test/peer_capability_safety_probe.py # 产品安全与评测能力矩阵 + README 可信度件（r38 立，双通道：默认分支递归树 + README 正文）。TOOLISH 排除是它的命门——本仓自己写的 `safety_probe.py` 一类文件名带 safety/moderation/jailbreak，不排除会**给自己凭空加能力位**（对 peers 同样生效，对称）。`--selftest` 13 条（当日值，现值由脚本自印；r96 补，含摘掉 TOOLISH 的变异腿 + JS `Array.filter`/`dependency injection` 两条误伤边界）
python _test/peer_issue_response_probe.py  # **「issue 响应速度」这一维的第一把尺（r96 立）**。r95:10-11 与 :241 两次写「不可测 / 多数仓已关闭 issue 无人工评论痕迹」，95 轮无人建尺、本轮实测**证伪**：12 仓各取最近 30 条已关闭真 issue，with_comments = 30/30、27/30、26/30、28/30、25/30、29/29…，唯一真零 issue 的是 CheaperjamRen/leemo（人口 0）。三腿取数：search type:issue is:open / is:closed closed:>=窗口（取**人口**不是样本）→ issues/{n}/comments → issues/{n}/timeline（交叉腿，两腿不等即该格 unverified，不取平均不择优）。「人工」定义排两类噪声：bot 后缀/名单 **加 issue 作者本人**——24 条抽样里 7 条首评是作者自追问，不排会虚高 32%（naive 12.0h vs 排除后 17.7h）。三态不塌缩 measured/silent/bot-only（silent 是读数=沉默关闭率，不是 NA）；p90 复用 perf_baseline_check.pct 最近秩（小样本禁插值）。search 层间隔 2.2s（=30/min 实测倒数）+ 403/429 照 Retry-After 等最多 3 次。网络面不入电池（承 r37 口径 + 本轮实测同轮 burst 重采会撞 GitHub secondary rate limit），只入 --selftest 18 条（当日值，现值由脚本自印）
python _test/settle_wait.py            # **「等系统静止」的唯一实现（r96 立）**。两条 CI 红同因取证：`j4_memory` 定长 8s 押完成时刻（run 37294500147）、`data_rights` 快照⇄导出跨时刻（run 37299161773）。两条约束：等待条件里禁现业务阈值（否则=等自己要证的数）；`settled=False` 必须记取数失败不得折 0。`--selftest` 13 条（当日值，现值由脚本自印）含"写入发生在观察之前"的正反两腿（不传 baseline 会把成功读成假红，实测踩过）。
python _test/perf_ramp_delta_check.py   # **阶梯并发读数的漂移尺（r98 立）**。立因与 `ledger_age` 同族：r96 跑出了 8/16/32/64 四档曲线并写下「无塌方点」，但那条曲线当时**只有一个点** ⇒「漂移」此后无人量过；而地板（`rps≥50`、`p95≤400ms`）只防塌方**不防悄悄劣化**（rps 从 2368 掉到 900 仍在地板之上，判据一声不响）。只比**同一档位**的相邻两份台账、只对**劣化**判红（改善不判红——与「指标变好」无关的判红是噪声源）。档集不同 ⇒ 逐档记 `NA(tier-missing)`，**不缩档、不补插、不取平均**。「上一份」按**文件名日期**取（不按 mtime——那正是 `ledger_age` 实测踩过的红绿翻面点）；取不到两份 ⇒ rc=2 **不判绿也不判红**。更正注 r99：原文「第二份由 `perf_baseline_check --ramp` 落盘时自动变可比」**不成立**（--json 路径由人工给，无任何自动日期命名，命名纪律唯一出处 = docs/PERF-BASELINE.md）；原文「只把 --selftest 档接进电池（主流程要网络与起服务，不适合整跑）」同样**不成立**（本尺取数面是 `交付物/对标数据/perf-ramp-*.json` 两份落盘件，零网络零起服务，实测 2s）⇒ 主流程已接进电池，套件 132→133。同日两份（间隔 ≥30min）当**噪底测量**用，跨日两份**不可单独下退化结论**（台账无机器状态字段，实测 10-05 与 10-07 同机相差 +35%~+76%）。`--tol-pct` 是演习口，实测收到 1% 时同档 −1.9% 立刻翻红；真机三腿实测：注入 −60% ⇒ rc=1 且点名 `t8/health rps -60.0% < -40%` ／ 阈值 5% ⇒ rc=1 ／ 全恢复 ⇒ rc=0（台账按字节还原）。`--selftest` **14 条（r99 当日值）⇒ 更正注 r100 40 条 ⇒ 更正注 r101 现测 49/49**（r101 加按档定阈桩 9 条：派生／只更严不放宽／t32 −8% 新红旧绿／t64 −45% 保持不红／变异打桩／机器维双向／台账不足回落出声；现值由脚本自印）。更正注 r99（噪底实测轮）：①**采集口径 `RAMP_WORK` 4→32**——同机静置连测 5 轮实测档内 rps 带宽 work=4 为 13.5%~**255.8%**（首轮冷启 t8=986.6 rps），work=32 收窄到 9.2%~**38.4%**；每档只有「档位×4」个请求（t8=32 个请求、`took_s`≈0.01s）时，两次读数的差主要来自这台机器此刻在忙什么，不来自被测对象。②**阈值 40%→50%**：原理由「同机同档波动 −13.8%」量错了对象（那是同一次运行的 8 档 vs 16 档，本尺只比同档、永不这样比）；同日 30 分钟间隔的两份 work=4 台账实测最坏 **−40.1%**，当场把 40% 阈值踩穿一次（判红而什么都没坏）。③**新增口径腿** `caliber_gaps()`：`work_per_thread` 或 `tiers` 不同 ⇒ 整尺 rc=2 UNVERIFIED，**不判绿也不判红** —— 把 4 与 32 两种口径的 rps 相减会产出「既有读数又判了红的假证据」，比诚实未验更坏；真面反例实测 rc=2 点名 `work_per_thread 4→32`，同口径两份对照 rc=0。④**检测限请如实读：本尺只能检出 ≥50% 的档内回退**，30% 量级检不出；要看得更细的正解是每档重复取中位数（r100 入口），不是把阈值调小假装看得见。⑤本轮另加 `--dir`（验牙与噪底测量打在临时副本，禁动权威台账，承 r98 §5 的 mtime 事故）；上文「注入 −60% ⇒ 点名 `-60.0% < -40%`」是 r98 当日阈值下的回执，现阈值 50%。 ⇒ 更正注 r100：①口径腿 `caliber_gaps()` 加两维 `reps_per_tier`/`warmup_per_tier`（旧台账读 None ⇒ 判口径差 rc=2，不冒充『没差』）。②新增 `noise_floor()`：本轮该档面自报带宽 ≥ 阈值 ⇒ 门面行加 `噪声档=N`、明细行点名「该档漂移不具因果判定力（须复跑）」，**红照判、rc 不放宽**（把量不出来说成通过，比说成回归更坏）。③同日多份台账的后缀必须**随时间递增且字典序递增**（`-a` 是第一份，禁止无后缀件）：本轮把当天第一份写成无后缀，`.`(0x2E) > `-`(0x2D) 于是`ledgers()` 比的成了「第一份 vs 最后一份」，实测产出 2 条 `t16 p95 +67.9%` 的**假红**；命名纪律唯一出处 = docs/PERF-BASELINE.md §1b。④**分母自卫**（本轮自造之后修类）：`is_ramp_ledger()` 只把
「有 `ramp` 键且是非空 dict」的件当台账——坏 JSON **仍算**（fail-closed，不许静默跳过坏件），`ramp=null`
算非台账但必须由 `foreign_files()` **出声点名**；六向桩含「不同前缀的件根本不进视野，glob 没匹配 ≠ 我判过
它不是台账」。立因：本轮一件 `perf-ramp-noise-*.json` 撞进 `perf-ramp-*.json` 这个 glob，整跑电池当场
`ENV-UNVERIFIED: perf_ramp_delta` ⇒ 纪律：**新写产物前先 grep 它的名字落在谁的 glob / 分母里**。
python _test/timing_coupling_check.py   # **「判据把成败押在机器时刻上」这一族的普查尺（r98 立）**。立因是 r96 连吃两条同根 CI 红（`j4_memory` 定长 8s 押落库时刻 / `data_rights` 快照⇄导出跨时刻），当时把两处升到 `settle_wait` 公共件——但**同一个类还剩多少处没人普查**，而「修类不修例」要求的是普查不是修两例。只断言可 AST 判定的**形状**（定长等待 → 紧接取数 → 该数被决策消费），**不断言意图**（「这里等错了」不是它的措辞，判据无法知道被等对象何时算好）；红**只由棘轮产生**（`C1_HARD > 基线`），即它自称的是「这个形状还剩多少处」不是「这些是 bug」。六桶 `C1_HARD/C_GUARDED/READ_NO_DECIDE/NEXT_NO_READ/POLL/LAST/VARLEN` 之和 == AST 现读总数，不等即 rc=2 **不判绿也不判红**（有类落进未定义桶）。分母取 AST 面（grep 面 142 处/31 件，多出 2 处在注释与 docstring；按 grep 钉基线 = 给尺埋「改注释就翻面」的假红，门面行两读数并印）。**门面行必须 ≤110 字符**（`run_all_suites.py` 的 `line[:110]`）：第一版 187 字符 ⇒ 受理面上基线/恒等式/C1 计数**全部不存在**，与在册教训 r40b 同族只是落在自己身上 ⇒ 生成器抽成 `face_line`，selftest 真调它（对字面量断言的话改生成代码不会红）。`--baseline` 是演习口（`--baseline 5` 实测 rc=1 点名 `C1_HARD 16 > 基线 5`）；`--selftest` **32 条（r99 当日值）⇒ 更正注 r101 现测 48/48**（r101 扩面新增 8 条腿：跨函数搬家正例／裸调用与 print 两反例／return 内联取数形／平行分支与 def 体两条回归钉／变异打桩两条新面必掉回 6／还原复验；现值由脚本自印）**含传递污点（断言读派生名）与四种「不得升格」反例。r98 实测：定长 131 处/29 件、**C1_HARD 16（电池面 13）**、基线 28、`ux_guards_check` 占 7。更正注 r99（逐件评审轮）：①基线 28 与 r98 自报的实测 16 不符，`--baseline` 的 help 原文「取实测值钉住」是空话 —— 现按实测钉 **9**（改掉 7 处误等后现读 9；留 19 的空档等于给新增误等发通行证）；②r99 改掉 7 处（`ux_guards_check` 5 + `data_rights_check` 2，改的是**被等对象的完成态**：TTS 开关 aria-pressed 翻面、对话回合「最后一条气泡带 data-emotion 且非上轮那条」）⇒ 定长 131→123、C1_HARD 16→9（电池面 13→6）；完成态取「身份章」而非「计数 +1」与「中间态」两种写法均被实测否证（窗口化从 #chat-log 顶部裁气泡 ⇒ +1 永不成立；离线模板 3ms 回完 ⇒ 中间态在首次轮询前已过去）；③评审结论落 `REVIEW` 台账（键 = `文件名::语句指纹`，**不锚行号**——行号锚法会让没改这条的人也变不了绿），三档 `mis-wait / shaped-only / unobservable`，`--json` 里 `review.covered/missing/stale` 可复算；④新增两类红因：C1_HARD 未登记评审结论、评审账与现读对不上（形状数仍只由棘轮产生，本尺不猜意图）。 更正注 r100（LOC 重构的代价，如实登记）：①`ux_guards_check.py::pg.wait_for_timeout(6000)` 是**真消除**（改等 `__pendingTurns` 归零；那条在册 `unobservable` 由此销账）。②`clean_clone_check.py::…(2500)` 与 `public_check.py::…(12000)` **没有消除**——LOC 门（≤150 行/函数）把 wait+read 提进了 `drive_page()`/`drive_chat()`，决策留在调用方 ⇒ 本尺把它们改判 `READ_NO_DECIDE`。这是**尺变软**，不是活变好，所以 **C1_HARD 基线 9 一字未动**（现读 6，余量是没锁住的余量，不是成绩）；`REVIEW` 台账按「键必须与现读同起同落」摘掉这三条，结论留在本行与 r100 报告 §3。r101 的正解＝把被审面扩到「跨函数返回值的消费者」，让提取函数不能成为降噪通道。
python _test/ledger_age_check.py         # **对标台账的龄期尺（r96 立）**。只做「龄期」这一件事：「哪份最新」与「内容是否过时」归 bench_rollup 所有，同一事实只许一处判 ⇒ 判据词全程用 AGE/OVER-FUSE，刻意避开 stale。阈值 **读 .ci/contract.json 的 refresh_days**（不抄数字，读不到判 UNVERIFIED 而非回落 7）；龄期以**文件名日期**为权威——同批台账 mtime 全是 2026-09-28（一次批量重写留痕），按 mtime 算龄=7 恰在线内 ⇒ **取数源一换红绿翻面**，故另设「mtime 最新 ⇄ 文件名最新」交叉腿（`git checkout`/搬卷会让 mtime 整体刷新，"最新"会静默换成旧的一份）。`--fuse-days` 是演习口（**0 是合法值**，第一版 `if a.fuse_days` 把 0 当没传，已修并有自测腿）；`--selftest` 原文写 27 条（r96 当日值）⇒ **更正注 r98 现测 32/32 ⇒ 更正注 r101 现测 44/44**（r101 加**第二面**：`na_census()` 按件内 NA 位置数与顶层声明对账，四态 CLEAR/DECLARED/DIVERGE/UNKNOWN；形状**按键形自动识别**、认不出判 UNKNOWN 并整尺 rc=2（未知≠完整）；`NA_DIVERGE_WAIVED` 是机器可读名单+expiry，清空必红、跨族不生效、死项必出声 —— 一手分叉 `peer-memory-2026-10-08.json` 声明 blind=0 而件内 5 处 NA。此前 degraded 只按「文件是否在 `_partial/`」判 ⇒ **按日期新鲜 ≠ 取数完整**，本面补的就是这个缺口；现值由脚本自印）（r96 收口轮把 CI 的 mtime 同值那条腿降档时加到 32，没人回扫这一行；G16 只核脚本名在不在、不核条数，所以这种数字漂移它看不见）；首跑实测点名 **12/15 族超 fuse** ——**r101 CI 段口径变更**：交叉腿的「mtime 有没有信息」由`全族同值`改为**同族 mtime 跨度 ≥ fuse（重采节奏）**——runner 的 checkout 会让同族 mtime 互不相等却只差亚秒，旧守卫不触发 ⇒ CI 判红本机永不复现（run 37886693021）；跨度不足只记本腿未验，龄期照判（逐条降档不整判据降档）。同时把红因改成 `- 红-分歧/红-NA/红-超龄` 续行并移到门面行**之后**，否则电池的 fold 只留半句、点名不到族；门面行 `NA分叉=` 两个出口统一为「未豁免数」（原 FAIL 行是 未豁免+已豁免，与 PASS 行同名不同分子）
python _test/browser_engine_declare_check.py # **浏览器面的「声明⇄实际引擎」门（r96 立）**。立因实测：本机 `chromium.launch()` 抛 `Executable doesn't exist at …chromium_headless_shell-1223…`（playwright 1.60.0 要 1223，缓存只有 1228/1243），于是 32 个套件各自手写回退 `channel="msedge"`，而**没有一处打印过实际用了哪台浏览器** ⇒ "本地浏览器套件全绿"这句话不可归因，且受理面（CI ubuntu + 受管 chromium）跑的不是同一台。五腿：E1 回退必须被 CONTRIBUTING 声明（四要素齐：playwright/chromium/msedge/一条修复命令）｜E2 唯一实现**棘轮**（AST 扫 `chromium.launch(`，未接 `browser_engine` 者 32/32，基线取实测值、**只降不升**——本轮不批量改 32 个文件，那是排障手册「吞 def 而 py_compile 全过」的事故面。**更正注 r98**：该分子按构造恒 ≈0（接完一件就离开 `chromium.launch(` 分母）⇒ r96 §4 给下轮写的「统一入口 N/32 已接、N 单调升」不可达；现取数面换 AST 并加 E2b（离开分母者必须「在册 ∧ import ∧ 裸 launch==0」）/E2c（半接入残留==0）/E2d（隐身件点名），已接数 = 起点名册 32 − 现读；本轮迁 8 件 ⇒ 余量 24、基线随之 32→24，且 `--census` 逐件对 defs 防吞行）｜E3 `--machine` 真起一次并把引擎身份**折进含判据词的那一行**（电池只留末行 verdict，各套件顺手多打一行进不了 CI）｜E4 面文件最近一条须与现算同引擎｜E5 CONTRIBUTING 不得虚报依赖（原文「仅标准库，无需 pip 安装」与 `_test/requirements.txt` 的 4 个依赖矛盾 ⇒ 新人照做第一批判据全 import 失败）。豁免只按**行**生效且要求同行带 `更正注`（保留被推翻原文是本仓规矩，按 R236 白名单排除法而非删规则本体），selftest 里两向各一条腿。静态档进电池；`--machine` 原文写「挂 CI browser-regression」在 r96/r97 是**空头主张**（实测 `.github/workflows/` 全文对本脚本 0 引用，r98 §2 F2）⇒ r98 才真加了那一步（rc=2 走 ::notice 不判红）；更正注 r99b（受理面那条 `E2b 名册核对=红` 归因到位）：**分母与起点名册改取 git 跟踪面**（`git_tracked()`；取不到 ⇒ 整尺 rc=2，**禁止回落本机磁盘面**）。一手代价：r99 首轮我把这条红标成"未归因"，实际是 `git clone --no-hardlinks` 本地就能逐字复现（`E2b RED 红因=cors_probe.py(文件不在了——删除/改名不等于接入)`，与 CI 同一句）——根因是起点名册 32 件里的 `cors_probe.py` 被 `.gitignore:11` **故意**挡在库外（注释原文「含同一 Key」⇒ 不可入库），本机目录面当分母就等于让 CI 永远背一件不存在的文件。修法二选一里只有"请出分母"可行（另一选是入库，违密钥红线）：起点 32→31、基线 24→**23**，**这是换口径不是接入进步**（已接仍 8 件，E2b 的三条件核对没被抹平）。⚠️ 本轮另记一次自造第二次错：先跑了 `--write-roster`，它按**现读面**重定起点 ⇒ 起点变 23、已接掉回 0、E2b 差集恒空变成装饰腿；正解是从 `git show HEAD:` 只读重建、只摘那一件（`git checkout --` 是破坏性动作，能只读取回就不该用它），重建后自证 `site_count == len(sites) == 31` 且 `call_points == Σ launch_points == 60`、行尾 CR=0。新增 6 条 selftest 腿（跟踪面过滤 / 排除出声 / 不给面时的对照 / E2b 把"名册有跟踪面无"判成删除而非接入 / 真面跟踪面非空 / **回归钉：`cors_probe.py` 不在分母里**）；`--selftest` 37→43 条（当日值，现值由脚本自印）
python "D:/global_skills/A-project-handoff/scripts/greencheck.py" run --repo-dir .   # 跨项目「CI 全绿契约」执行体（**在受管根 global_skills 内，不是本仓文件**；本仓这一侧只有 .ci/contract.json）。pre-push 钩子跑它；契约未入库 ⇒ 恒回 UNKNOWN ⇒ 钩子恒放行（2026-10-05 实测坐实），故本仓另立 _test/ci_contract_check.py 盯契约本身
python _test/measure_entry.py            # r82 取数入口前置自证：peers 尺全集 ast 解析 + HEAD 归属（坏在未入库改动/坏在已入库 两种红因分开报）+ 并跑 repo_config_check
python _test/live_sync_check.py          # 线上 `/` 与 deploy/xinyu 逐字节比对（部署未跟进即红）
python _test/safety_guard_check.py        # 输入侧护栏行为验证：注入 6 例必须点名 + 正常 6 例不得误伤（含 --selftest）
python _test/eol_parity_check.py         # 行尾确定性：工作树字节 == 仓库 blob 字节 + binary 形状（E1–E4，8 类 --selftest）
python _test/patch_apply.py --selftest       # 补丁器自证：锚点失配/歧义/同义/插入/正常/缺失 + 行尾两侧 八类行为（防"没报错=生效了"）
python _test/api_contract_check.py       # 接口契约三方对账（控制器↔docs/openapi.yaml↔前端）+ 11 条运行态真实打 + C6 零漏探测 + C7（r89）人读手册 API.md ⇄ yaml 双向对账（缺/虚/计数过期都红，`--selftest` ㉑类篡改各证一腿）
python _test/repo_config_check.py --online # 仓库配置自洽：dependabot schema/目录可达 + 文档数字断言==机器实测 + 默认分支受理面

# ↓ r57 补登记：以下 16 条在电池里，而本节（被当作"判据清单"来读）从来没有它们。
#   一句话说明逐字取自各脚本自己的 docstring 首行，不凭记忆改写。
#   同族盲区常驻由 `repo_config_check.py` 的 **G16** 钉住：电池脚本 ⇄ 本节 双向对账
#   （电池有、本节没有 ⇒ 红；本节写了、`_test/` 里查无此件 ⇒ 也算红）。
python _test/perf_baseline_check.py      # 性能基线判据（r40）：把"性能表现"这一维从连续几轮的「未实测」变成有数、有预算、有回归棘轮的一格 ⇒ 更正注 r100：阶梯每档改为**跑 5 次取中位数 + 丢 1 次冷启**（`--ramp-reps` / `--ramp-warmup`，默认 5/1；`reduce_reps()` 纯函数，selftest 双向打过「取中不取均」「冷启不掺」「LLM 从严」「空样本不得折 ok」「judge_ramp 吃得动中位数产物」）。台账每档面自报 `band_rps`/`reps`/`reps_warmup_dropped`，整轮记 `worst_band_pct`；`llm_used` 必须**每一次**都是 False 才算 False。实测结论（10 份同口径台账）写在 docs/PERF-BASELINE.md §1b：**跨轮噪声没被压掉**（t8/t16 带宽 55.9%~76.7%，5 次 reps 共享同一机器状态、噪声相关），检测限仍 ±50%。
python _test/disclaimer_forensics_lint.py --all  # 边界声明取证判据（M5⑫ 执行器）：免责声明不得顶替一整维的测量（r57 由 CI 判红实证它在管）
python _test/plan_pdf_coverage_check.py  # 应用方案 PDF 的九项覆盖判据（iCAN 硬截止前的交付面自证）
python _test/settings_panel_check.py     # 设置面板行为守卫（r27，第四刀的前置判据）
python _test/offline_shell_check.py      # 只读离线壳（sw.js）+ 缓存头策略判据（r28）
python _test/pdf_leak_scan.py            # PDF 文本层泄露复扫（R242：二进制产物须抽文本后再扫）
python _test/tracked_secret_scan.py      # 跟踪文件密钥形态扫描（r35）—— 与 CI 密钥门禁同一把尺，且本地也跑
python _test/remote_tree_audit.py        # 远端树洁净度审计（r37）：评委看得见的是远端 main 的文件树，不是本机工作树
python _test/mobile_check.py             # 移动端与触屏可达性判据（r47）—— 量真实几何，不量"有没有写 @media"
python _test/release_governance_check.py # 发布治理判据（r45，双通道同尺）—— 盯「版本在动、内容没切版」这一族；R2c 的「归属轮次」口径 r101 收窄为**只认 `type(rNNN …)` 括号内轮号**，标题正文引用别轮（`fix(r101 收口): … + r102 入口建卷` 曾判红点名一个还没有提交的轮次）降为 `R2c(口径)` 告警；无 scope 的 feat/fix 仍按整条标题判，收窄不留后门（条数由 `--selftest` 自印）
python _test/j2_chat_contract.py         # J2 契约验收：POST /api/chat 与 v1 1:1，前端零代码改动即可切到 Spring Boot
python _test/j4_memory_check.py          # J4 持久化验验收：记忆从 localStorage 迁到服务端数据库（并保留本地降级）
python _test/j4_remote_down_check.py     # J4 熔断对照：服务端没有 /api/memory 时，远端记忆必须"试一次就闭嘴"
python _test/online_check.py             # 在线模式全链路回归：徽章 + 双路情绪探针 + 在线对话 + 危机拦截 + console 0 报错
python _test/public_check.py             # 公网版验收：评委打开即在线AI（走服务端代理），密钥零暴露，console 0 ⇒ 更正注 r100：裸 `assert` 改判据链——腿名册 `LEGS`（10 条）是唯一分母，未走到的腿逐条记未验，`report()` 单出口保证结论行在任何出口都印出来，`PX` 兜底腿接住未预期异常；退出码补成三态 0/1/2（playwright 或浏览器双档不可达 ⇒ rc=2 并印 `PUBLIC-CHECK-ENV-UNVERIFIED`）。在册对外 token `PUBLIC-ONLINE-ALL-PASS` 与 `KEY_LEAK: False` 两行**一字未动**（CONTRIBUTING.md / SECURITY.md / pull_request_template.md / AGENTS.md 的 AC-OBS-11 按它们取证），计数按 r40b 折进同一结论行：`PUBLIC-ONLINE-ALL-PASS 判红=0 未验=0 腿名册=10`。演习口 `--nav-timeout`：`1` ⇒ 真实导航超时 （P0 判红 + 其余 9 条记未验，rc=1）；`abc` ⇒ 仪器自崩，出 `PX` 结论行。
node _test/emotion_eval.js               # 情绪引擎评测：词典层准确率（技术实现维度的可复现数字）
# ↓ 同批第二刀：G16 首跑又抓到 10 条（r35–r50 落地的判据/探针/通道件，同样从未进本文明细）
python _test/ci_watch.py                 # push 后的 CI 回执看守（把"看 CI"从人记得住，变成一条命令必跑）
python _test/lightshow_check.py          # 一键点亮验收：清屏（UI 让位）+ 六色各自可见 + 铺得够满够散 + 播完不自动跳回
python _test/pixel_dual_check.py         # 星雾「是不是真的变彩色了」——像素级回归（判断据不看内部数组）
python _test/server_preflight.py         # 被测服务前置探针（r35）—— 把"服务没起"与"代码有缺陷"分开报。更正注 r99c（产物新鲜度换权威）：该腿原先判 `jar mtime < 最新源码 mtime ⇒ FAIL`，而 **mtime 在 CI 上由"文件怎么搬来"决定**（checkout / cache 还原各写一套时间）——同一份代码同一天两次运行一次红（`jar mtime 00:00:00 < schema.sql 17:03:06`）一次绿，确诊"判据把成败押在机器时刻上"（r98 那把 `timing_coupling` 尺只扫 `_test/` 判据面，没扫到这条产品侧用法）。现权威换成两条**任何机器同值**的判据：(A) jar 内 `BOOT-INF/classes/*` 逐件 SHA256 ⇄ git 跟踪的 `server/src/main/resources/*`（实测 2 件：application.yml / schema.sql）；(B) jar 清单 `Implementation-Version` ⇄ `server/pom.xml` 工程版本（解析须先剥 `<parent>` 段，否则先命中 Spring Boot 的 3.2.5 ⇒ 假红）。三态不变，另出 `fresh=ok|fail|unverified`：取不到 git ⇒ unverified（**既不折成 ok 也不冒判红**）；mtime 只留提示文本并标明"机器局域量，不参与判定"。夹具 selftest 的 `total` 原先**手抄常量 5**（加腿即报 11/5），现改结构推导 `ok + len(fails)`；新增 7 条腿含回归钉「**把 jar 的 mtime 拨早于源码 ⇒ 必须仍 PASS**」（真机复现：拨回 2 小时后 `JAR-SHAPE-PASS`，随后 mtime 已还原）。java 编译件无法从产物侧证新鲜 ⇒ 该面如实留未验，"构建时写 stamp"的补法登记 r100。
python _test/voice_check.py              # 语音输入（Web Speech API）实测：只认真实发生过的事实（API 在否/start 真被调用/监听态出现过/能恢复）。r97 起另加三条**桩化腿** A8/A9/A10：把 `window.SpeechRecognition` 整体换成可控桩，分别测「`stop()` 后不派发 `end`」「正常派发 `end` 的对照」「`start()` 直接抛异常」三种形状，退出态必须复位。这三条与环境无关 ⇒ CI 里也必须判、不许走 `no_input_device` 的 SKIP（r96 的缺口是「退出态只在有麦克风的机器上才可能被撞到」；⚠️ A4 自身走哪个分支在受理面仍无读数，那是另一把尺）
python _test/peer_a11y_probe.py          # 对标 r42 探针：无障碍与制度化（a11y）（16 仓 + self，三通道同尺）
python _test/peer_community_probe.py     # 对标 r50 探针：协作治理与健康度的制度化程度（16 仓 + self，三通道同尺）
python _test/peer_license_probe.py       # 对标 r46 探针：许可与供给链合规（16 仓 + self，双通道同尺）
python _test/peer_mobile_probe.py        # 对标 r47 探针：移动端与触屏支持的结构性证据（16 仓 + self，双通道）
python _test/peer_release_probe.py       # 对标 r45 探针：发布与版本治理（16 仓 + self，同一把尺）
# ↓ r58 质量工程面（JS 侧从「0 个单元测试」起账；Java 侧 4 类 30 用例早已在册）
node _test/js/emotion-engine.unit.test.mjs   # 被测件本身：node:test + vm 载入浏览器全局脚本（含跨 realm 归一与夹具自证）
python _test/js_unit_check.py                # r58 JS 单测执行判据：枚举 _test/js/*.test.mjs 真跑，判据行自带 tests/pass/fail 计数
python _test/js_unit_check.py --selftest     # r58 判据桩：7 类（零分母/计数不自洽/tests=0/stderr 挤行/node 缺失）+ 恒绿守卫
python _test/deliverable_inventory_check.py               # r59 交付物清单面：提交包「清单声明⇄磁盘⇄口径」三方对账（缺失/空件/页数越界/时长越界/指纹漂移/品牌分叉皆红）；r90 起分母 = 交付面 + 归档面（archive/交付物-历史轮次），并认「逐字节等价的暂存搬卷」
python _test/deliverable_inventory_check.py --selftest    # r59 判据桩：纯函数夹具 + 取数解析腿含独立通道对账 + 端到端反向腿含**真 git mv 往返**（条数由脚本自己印，本行不抄数；r90 加的搬卷五形：面外/改过内容/落点未落地/查不到/落点随后消失 皆须仍红）
python _test/hook_wiring_check.py                          # r83 交付面在位闸的「接线回执」：_test/hooks/pre-commit 源在位 + sh -n 解析得动 + .git 副本按字节==源 + 被拦判据三态在位（CI/无 .git ⇒ 未验不判红）
python _test/hook_wiring_check.py --selftest               # r83 判据桩：12 腿（副本漂一个字节必须红／CI 面不得判红／硬崩 rc 不得并入「环境未验」／端到端删一件入库件真被拦）
python _test/hook_wiring_check.py --install                # 装法唯一入口（写后读回证明装的==声明的；异版先备份）
python _test/live_sync_check.py https://qwer-d4gf2r76o8829463b-1458054906.tcloudbaseapp.com/xinyu/   # r84 备用线同尺对账（那条也曾"200 但页面换人"，只盯 pages.dev 看不见）
python _test/backup_online_check.py                        # r86 备用线真实在线判据：真开浏览器经「确定访问」验证页进 /xinyu/，stub 须指 pages.dev、发一条消息须见「在线大模型生成」、console 零 error（改回已死的 service 域名即红）
python _test/run_logged.py --selftest                      # r84 后台测量退出码回执桩：8 腿（转发真 rc／stderr 落盘／零输入与落点坏都判未验）
python _test/run_logged.py --name peers -- python _test/benchmark_metrics.py --cap-channel   # 用法：把测量丢后台时的唯一合法包装，日志尾行 NAME_RC 才是结论
python _test/hook_wiring_check.py --drill                  # 真注入演习：删一件「已入库但未写进声明面」的交付件 ⇒ 钩子必须 rc=1 且点名它，随后按字节复原并复验 rc=0
python _test/api_egress_headers_check.py                  # r59 函数出口面：node 假 fetch 驱动真 chat.js，6 条 return 出口各断 5 类安全头 + 状态码 + 错误体形状
python _test/api_egress_headers_check.py --selftest       # r59 判据桩：7 腿（正例／摘 CSP／摘 no-store／缺出口／状态码漂移／错误体漂移／SSE 语义被换）；首跑即抓到"没发 stream:true 导致 SSE 腿空转"
python _test/storage_resilience_check.py                 # r60 持久层异常面：真开浏览器注 storage 禁用/内容损坏/配额写满/删不掉 四类故障 + 对照组，断"零未捕获异常／界面计数==数据源／星雾仍点亮／清空回执如实"
python _test/storage_resilience_check.py --selftest      # r60 判据桩：10 腿（合规正例不假红 + 六形必红 + 坏页端到端真崩 + 零读数不判绿）
python _test/js_syntax_check.py                     # r67 JS 语法面：src/js 与 deploy/xinyu/js 双份逐文件 node --check（覆盖面=可解析性；不覆盖面=风格/未定义变量/lint 规则）
python _test/js_syntax_check.py --selftest           # r67 判据桩：5 腿（坏文件点名 + 未闭合字符串 + 合规正例不假红 + 零输入不判绿 + 枚举下限防 FACES 拼错静默少测）
python _test/brand_consistency_check.py              # r89 作品名门面：24 个门面面（README/docs/LICENSE/.env.example/openapi title/deploy jar/memory 01）剥掉技术标识白名单后不得再现旧作品名，另带品牌位在场反向腿（缺 B2 时 B1 可靠"整页没品牌"骗绿）
python _test/brand_consistency_check.py --selftest    # r89 判据桩：3 腿（挂旧显示名必须被抓／纯技术标识不误伤／旧名与技术标识混排不得放过——白名单过宽等于没有门）
python _test/suite_resource_census.py               # r70 资源普查：全部套件（分母从 SUITES 现读）按**目标脚本源码证据**分类（碰 8123/自绑端口/起浏览器/出公网），分桶恒等式 + BLIND 单列；天花板只报"算出的下界"并标明非实测
python _test/suite_resource_census.py --selftest     # r70 判据桩：11 腿（漏报/误报两侧 + 恒真守卫"纯函数源码不得判出资源" + port=0 不算排他 + 盲区不得落进 free 桶 + 无台账不得报已计时）
python _test/peer_quality_tooling_probe.py   # r58 对标探针：lint／类型／单元可测性／CI 执行位（16 仓 + self，双通道）；r66 修「只印不写」＋r67 拆 struct 两态：null=未测、[]=测到零命中）
python _test/peer_quality_tooling_probe.py --selftest  # r58 探针桩：7 类桩 + 恒真守卫（含「NOISE 不得滤掉 tests 目录」反例）
python _test/ci_perf_wiring_check.py          # r91 性能接线面：C-IPW-1..5（workflow 名被 RE_CI_PERF 认下／正文真调 perf_baseline_check／java -jar 且等 /api/health 就绪／README 命中 published_numbers 且引用基线文档／README 与 PERF-BASELINE 的 p95 不超预算且不分叉）；正则从 benchmark_metrics 同源 import，不内联
python _test/ci_perf_wiring_check.py --selftest  # r91 判据桩：11 条（当日值，现值由脚本自印；正例 + 删 workflow／空正文／不调判据／不等 health／README 抽数字／抽基线引用／两处数量级分叉／超预算／基线失联 九反例 + 零输入恒真守护）
 python _test/loc_guard_check.py                # r94 起**默认 enforce**（超限即 rc=1，进了电池就会红）。行数 ≤2000 / 函数长 ≤150（对标 opensoul `check:loc`，其 `--max 2000 --max-function 150` 已实测坐实）。**函数口径只取 `func` 块**：Java/JS 的类与 IIFE 模块包装是类型/模块容器，不计函数长（行数照常计入文件行数）；嵌套函数**会**被测量。面板打印被排除的类/模块数 + 既有更严约束（size_budget 字节预算、Core P0.8 函数 ≤50 行）。`--report-only` 只报不拦
 python _test/loc_guard_check.py --selftest      # r94 判据桩：17 条（当日值，现值由脚本自印；超限必报／未超限不误报／等值边界／两条阈值放大变异腿／零文件不产生结论且必判 UNVERIFIED／合成面超限非空／类 300 行与 IIFE 包装**不得**判函数超限而其内部 200 行函数必红／接线三腿：当前电池条目带 --enforce、摘掉后判否、只动一处不误伤）
 python _test/bench_rollup.py                   # r93 起提供两新增维度的只读汇总（只读、零网络、数字带来源）：①测试与可复现性（self 套件数／Java 测试类与 @Test 数／jacoco LINE≥0.90∧BRANCH≥0.90 ⇄ peers 同址尺 coverage_gate 等）②零构建成本-收益（前端构建链配置 0 个 ⇒ 零构建成立；平台函数依赖清单单列；首屏预算；CI workflow 文件数与 job 条数）。**r94 起输入/产物都不写死轮次号**：自动取最新 `benchmark-metrics-*.json` 与 `peer-quality-tooling-*.json`／`peer-repro-*.json`，产物名跟随输入轮次；stale 标记按台账内容判定（含旧 letta 行才标 stale，不再硬编码）
 python _test/bench_rollup.py --selftest         # r94 判据桩：5 条（当日值，现值由脚本自印；缺源检出／合成样本出表／成本项未取数不得写成 0／job 计数不得把 job 内保留键算成 job／无 jobs 块时不得凭空数出 job）
 python _test/verdict_exit_parity_check.py      # r94 发现、r95 接线的**判据的判据**：门面印 `XXX-FAIL/-RED/判红` 却没有任何非零退出路径的套件 ⇒ DEFECT。取数面 `_test/*.py` 全量现读（分母不手抄），分四档：OK-explicit（有 sys.exit/raise）／OK-exception（纯 assert 型，靠未捕获异常转 rc=1，**合法不判红**）／N/A（不印门面行）／DEFECT。电池按 rc 记账，所以这一族坏一次就等于「验收判据报红而记绿」：r93 抓到 `j2_chat_contract`（只修那一件），r94 类扫 90 套件又抓到 `j4_memory_check`（AC-OBS-10 的判据）。零网络零浏览器，可进任意档
 python _test/verdict_exit_parity_check.py --selftest  # r95 判据桩：10 条（当日值，现值由脚本自印；三形态正例／无门面行／软面钉死：assert 不在 FAIL 分支 ⇒ 归 OK-exception 不判红，只作趋势读数／反例印 FAIL 无退出必判 DEFECT／同形态修好必转绿／两个变异体各翻一侧／坏语法单独成档不判绿）
 python _test/ci_contract_check.py                  # r95 立：「CI 全绿契约」本身的**结构性**门。9 条腿：契约已入库（未入库 ⇒ greencheck run 恒 UNKNOWN ⇒ pre-push 钩子恒放行，实测已坐实）／checks 非空／blocking name 唯一／每条 blocking 有 cmd+timeout_s+cost_ms+cost_source／声明的总预算 == 各条之和（可复算）／blocking 合计 <= 20s pre-push 预算／**接线自证**（每条 blocking 的脚本或 `-m` 模块在 CI workflow 与电池里都有执行位，否则"列了但没人跑"）／deferred 必带 reason 且 reason 必须点名承接面。**不调用 greencheck run**（会递归），静态零网络零浏览器；同时进电池与契约 blocking 自身
 python _test/ci_contract_check.py --selftest      # r95 判据桩：15 条（当日值，现值由脚本自印；3 正例含 `python -m 模块` 形态／8 反例逐条注入一手形态／结构腿空契约／变异体补上执行位后必须转绿／变异体两者皆无必须点名）—— 正例腿是必须的：第一版把 `any(s in x for x in (集合,集合))` 写成对容器做成员判定，恒 False，14 条合法 blocking 全被误报"没人跑"，只有正例腿抓得到
 python _test/jar_shape_check.py                   # r101 接线（**此前已入库却电池与 CI 两头都不执行**，由 G16 第五腿抓到）。部署产物形态与新鲜度守卫：fat jar 必须含 `BOOT-INF/lib`、pom⇄jar 版本同源、**jar 内资源字节的 SHA256 == 源码**（r99c 定的口径：mtime 只证明"文件被动过"，不证明"内容对得上"）。ci.yml 的 java-build 作业虽有 unzip 一行，但那不是本件（本件还管新鲜度）
 python _test/jar_shape_check.py --selftest        # 12 类夹具（当日值，现值由脚本自印；形态 4 + 新鲜度 7，含回归钉「mtime 早于源码必须仍绿」——否则下一轮就会有人把尺改回按 mtime 判）
 python _test/entry_reach_check.py                 # r101 接线（同上抓到）。窄屏能力入口可达性判据（r48 立）：盯「桌面点得到、手机整块没了」这类静默消失。接线的真正理由是**账实相符**——`memory/` 在册结论写着「再 display:none 会被 entry_reach 判红」，而它此前既不在电池也不在 CI，那句话在受理面上无人执行；`--selftest` 印 cases=11 fails=0 ALL-OK，真面本轮实测 `ENTRY-REACH-PASS visible=7/8 gap=0 undetermined=0 state_gated_excluded=1[btn-exit-show]`（需 jar@8123 + 浏览器，与电池内既有 33 条 playwright 套件同前置 ⇒「要浏览器」不构成豁免理由）
 python _test/docker_image_sim_check.py            # r101 接线（同上抓到）。Dockerfile 的 COPY/ENV/WORKDIR/ENTRYPOINT 在磁盘上做等价实现后逐项断言 ⇒ **本机无 Docker 也能判**（`server/Dockerfile` 自 J5 起挂着「未实测」标签，这条就是那块没被量到的面；真面实测 `DOCKER-SIM-PASS`）
 python _test/rescan_shots_check.py                # r101 接线（同上抓到，且它此前**已写在本文档明细里却两头不执行**——正是 r96 给 peers 判过的那类「永不开火的门」）。交付物回扫：为「离线壳」与「评委自助设置面板」出两张实证截图，腿名册 LEGS 是唯一分母，任一条没被记录 = 记未验并在结论行点名（r100 三态纪律）。⚠️ 本件**没有 `--selftest` 口**（传该旗标会被 argparse 之外的路径吞掉而照跑真面，本轮实测踩到）⇒ 只有真面一条腿，需 jar@8123
```

> 前置：多数判据需 fat jar 起在 8123（`java -jar server/target/soulisle-server.jar --server.port=8123`，
> 工作目录 = 项目根，`DEEPSEEK_KEY` 走进程环境）。⚠️ 改 `src/` 后**必须重启 jar** 再验（进程内静态资源有缓存）。

GitHub Actions 四条门禁（`.github/workflows/ci.yml`）：同步守卫+评测+策略表+体积+**vendor 供给链**+密钥扫描、Java 构建+**词表一致性红线**（此前只写在 `memory/AGENTS.md` 靠人记，现已机器化）、浏览器回归（runner 无 GPU，强制 SwiftShader）、公网新鲜度。
四条 job 都挂在 `main` push 上真跑；浏览器 job 首轮就抓到本机看不到的真实缺陷：`src/js/demo-config.js` 被 gitignore，全新 clone 下 `<script>` 静态引它 → 首屏 3 个 404 打破「console 0 报错」。修法＝CI 自动用公网零密钥 stub 补占位（本地按 `CONTRIBUTING.md` 第一步手工补一次）。

**受理面状态以远端为准，不在本文件写死**：`python _test/ci_status_check.py`（HEAD 最近一次 run 三态分类：PASS / CODE_FAIL / ENV_BLOCKED）。r35（2026-09-26）实测到一次"本机 37 条全绿、CI 两条 job 真红"的分叉，三条根因与修法见 `交付物/_历史轮次-对标/对标分析报告-2026-09-26.md` §2；同类分叉已封成常驻判据（密钥扫描两侧同源 + `voice_selftest` + settings 落盘完成态等待）。

最近实测（2026-09-26 对标轮 r35）：全量电池 **47 条套件实跑全绿**（该计数已被 r41 的 58 与 r42 的 61 取代，现行值由 `repo_config_check` 的 G10 恒等式当场复算，本行只保留 r35 当时的取证事实）（r36 增 `eol_parity`±自证：工作树字节 == 仓库 blob 字节，于是本仓「逐字节 / SHA256 / 字节预算」类主张在任何机器 clone 上可复算），且远端 HEAD run `36220200506` 四条 job 逐项 `success`（r35 收口，2026-09-26 实测）。前置探针 `preflight` 打头：被测服务没起时收口行写 `ENV-UNVERIFIED` 而不是判红）（含受理面体检 ci_status，在 CI 内部自动 SKIP）；情绪评测 **73 条 / 98.6% / 危机 6-6**（JS ↔ Java 逐项全等）；`emotion_wiring_check` 9/9（后端路径实测生效 + 不可达即熔断不伪装 + 危机未经后端）；gsap 3.15.0 升级后 `browser_check`/`lightshow`/`pixel_dual` 全绿；首屏关键路径 831,152 B（预算 858,752 B 内；r36 行尾归一后从 832,382 降为现值，复算 `python _test/size_budget_check.py`）；公网已重新部署并 `LIVE-SYNC-PASS`。


---


## 无障碍（r42 新增，README 的指针落在这里）

判据：`python _test/a11y_check.py`（运行时 axe-core 4.10.2 本地 vendored + 像素级动效实测）。
收口行必须自带实测值（电池对每套件只留含判据词的那一行）。

| 判据 | 盯什么 | 为什么单独列 |
|---|---|---|
| A1 | 每个审计单元 `passes > 0` | 证明审计真落在填充后的 DOM 上，而不是"页面没渲染完也报 0 违规" |
| A2 | 6 状态 x 2 主题 = 12 单元，违规节点必须为 0 | 首屏只覆盖 5 幕里的第 1 幕；亮色主题（r15）不测就从不被执行 |
| A3 | 注入 4 类已知缺陷，axe 必须抓到 | 反例自证：一把量不出东西的尺，它的 0 没有信息量 |
| A4 | 对比度 `incomplete` 计数 <= 30 且逐格点名 | 暗底 + 半透明卡片 + WebGL 背景 ⇒ 有效背景静态算不出，工具只能弃权（实测 23 格，样本 `.brand`、`.brand-sub`） |
| A5a | 正常态帧间像素差 > 0.002 | 若星雾本来就不动，"减弱动效已实现"就是空判；这一条是防"删光动画来通过判据" |
| A5b | reduce 态像素差 <= 15% 正常态 | 实测 0.0516 -> 0.0000（比值 0.000）；CSS 那两行 media query 管不到 WebGL 自走时钟 |
| A6 | 首个 Tab 落点有可见焦点环 | **下限断言**：全序 Tab 遍历未做，登记在 `memory/07-next-steps` |
| A7 | 可见文字须为无障碍名子串（WCAG 2.5.3） | 语音用户说"点击 模型设置"却点不到，因无障碍名叫"设置"；纯图标按钮先剥装饰符再判"不适用" |
| A8 | 对话日志与探针读数须在可访问性树里 `aria-live` | 读屏用户能不能听到回复，取决于这一个属性 |

规则集口径：`wcag2a / wcag2aa / wcag21a / wcag21aa / best-practice / experimental`。
**`experimental` 不可省**——`label-content-name-mismatch` 只挂这个标签，默认集与"严格 wcag"集都跑不到它；
r42 首跑不传 `runOnly` 得到 `violations=0`，加该标签即命中 `serious:2`（同页对照，实测 05:2x）。

自证桩：`python _test/a11y_check.py --selftest` = `A11Y-SELFTEST: 12/12`
（像素通道 3 例含"尺寸不一致必须给 -1 而非 0"、动效判定 4 例含"正常态不动即空判"、标签判定 5 例含两个纯图标按钮）。
像素数学单一实现 `mean_abs_delta()`，main 与桩共用，禁两处写。

环境三态：服务不可达 / axe 件缺失或长度不符 / PIL 不可用 ⇒ `rc=2 ENV-UNVERIFIED`，不给绿也不给红；
vendored 件**禁在线回落**（判据不接受"顺手下一个"，那会让一次坏下载伪装成一次通过）。
