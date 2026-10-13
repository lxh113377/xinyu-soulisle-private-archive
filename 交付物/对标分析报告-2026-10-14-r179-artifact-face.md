# 心屿 MindIsle ⇄ GitHub 同类开源项目 · 八维对标报告（2026-10-14 · r179 产物面线）

> **性质**：第 22 次重发同一指令 ⇒ 整跑一轮（复核 + 增量），不做「已做过所以只核验」的降格。
> **本轮主线**：前几轮（r172-r178）连续在审「自家尺的取数面」，而八维表里**维度 1/6/7 连着三轮写「未重采 ⇒ 无结论」**。
> 本轮先把 peers 面重采齐（四台账当日现采），再把刀口对准一个更基础的东西：**回归基座跑的产物到底是不是当前代码**。
> HEAD 起点 `7e0ebae`（r178 收口①）；本轮开工后并行会话又提交到 `83c8540` ⇒ 全程路径限定提交、不代提他人 WIP。

## 0. 取证面声明（先看我没量到什么）

| 面 | 取法（可复算命令） | 现读 |
|---|---|---|
| peers 维护/社区/文档/质量门 | `python _test/peer_{maintenance,community,docs,quality_tooling}_probe.py --json 交付物/对标数据/peer-<族>-2026-10-14-r179.json` | maintenance rc=0（16/16 两腿一致）｜community rc=0（NA 0）｜**docs rc=1（2 仓 unverified(RuntimeError) ⇒ 该维分母 14/16 可用）**｜quality-tooling rc=0（BLIND 0） |
| 八维总览表 | `python _test/bench_eight_dims_check.py --round r179` | `EIGHT-DIMS-PASS 维 8/8｜格 26｜NA声明 1｜补法死链 0｜退化红 0｜变化 10`（表由件生成，非手抄） |
| API 契约三方对账 | `python _test/api_contract_check.py --selftest`；`--base http://127.0.0.1:8124` | 桩 `SELFTEST-PASS 八类样本均被抓到`；**新产物面 `合计 20 项，失败 0 项 / 探测 16 + 豁免 0 == 操作 16`**；默认 8123 面仍 `rc=1`（C4 `/api/health/db -> 404`，根因见 §2） |
| 配置/接线对账 | `python _test/repo_config_check.py{,--selftest}` | 主流程 rc=1（仅 G8 受理面，本轮提交即转绿）；桩 `SELFTEST-PASS 91 条…（CI 实跑 212 套件 / 豁免 3）` |
| 耦合尺 | `python _test/timing_coupling_check.py{,--selftest}` | `TIMING-COUPLING-FAIL …C1=22 基线20` ＋ 新印 `棘轮余量(r179) 提交面: 余量=-2｜已越限`；桩 57/58（唯一不符＝他方两条定长等待无评审账） |
| 回归基座产物 | `python _test/server_preflight.py`；`jar_shape_check` 新鲜度腿 | `PREFLIGHT-FAIL 资源比产物新：application.yml, db/migration/V1__j4_baseline_schema.sql(jar 内无此件)`｜运行实例产物身份 `jar:…:1c6703d5e2d3:28486290`（10-13 08:57），本轮新构建 `jar:…:95d5d9799a8d:29249397` |
| 新产物可否构建 | `mvn -B -f <副本>/server/pom.xml clean package`（JDK 17） | `Tests run: 203, Failures: 0, Errors: 0` + `BUILD SUCCESS` ⇒ **提交面源码是绿的，红在产物没跟上** |
| **本轮没量到的面** | ① 整跑电池未重跑（`--only` 子集读数按在册纪律**不覆盖全量台账**；最近全量仍是 r172 的 172/199，套件数已 172→212）② peers 性能/安全/移动端等 8 族探针未重采 ③ `eol_parity_check` 237 项既存红未治（他因：行尾策略未锁死）④ 远端 CI 回执（本地领先 origin/main 235 提交，未推送即无 run id） | 四条均记未验，不写成通过 |

## 1. 对比总览表（八维）

| # | 维度 | 心屿 MindIsle（self，本轮实测） | peers（16 仓，10-14 现采） | 判定 |
|---|---|---|---|---|
| 1 | 功能模块覆盖 | 计数位 6 项（api_spec/container/deps_autoupdate/emotion_backend_wired/pwa_manifest/pwa_offline）+ 本轮补齐契约面的第 16 条端点 | `vector_memory` 最高格 9/16；streaming：token_stream 2/16；e2e_browser：1/16 | **不追**：向量记忆已裁定不立项（`交付物/向量记忆评估-2026-10-01-r88.md`，重启触发条件在册）；SSE 已落地（r88 核验）⇒ 广度差是定位差，不是缺陷差 |
| 2 | 技术架构设计 | 零构建静态前端 + Spring Boot 单体，词表 SSOT 单源（JS/Java 各加载同一文件） | 依赖自动更新 2/16（有包清单才挂得上） | 中：架构自证强，`src ⇄ deploy` 提交面分叉本轮 rc=0（r175 记的三条已闭合） |
| 3 | 实现方式（质量门） | 电池 **212 套件**（本轮 +2 接线）；Java **26 件 / 203 例**，门 LINE/BRANCH ≥ 0.90；每把尺带反例桩（本轮 api_contract 八类、timing 58 腿、repo_config 91 腿） | 有测试结构 **7/16**｜CI 有单测执行位 **6/16**（较 10-13 的 5/16 +1）｜linter 配置 2/16｜tsconfig 5/16 | **self 唯一领先维**，且本轮领先面加宽一条（孤儿判据入阻断链） |
| 4 | 性能表现 | 首屏预算 30 件 / 1,231,022 B；`perf_api_check` self 侧可复算 | `measured* = 0/16 仓`（形态 files-only=1／none=13／unverified=2） | **不可横比**：peers 无分母。self 数字只作自身趋势，禁止写「领先/落后」 |
| 5 | 可扩展性 | 缺位：插件协议（`docs/EXTENSIONS.md` 五个扩展点是**文档化**非机制化）、向量长记忆、i18n | `vector_memory` 9/16｜`i18n_locale` 3/16｜记忆形态 usable 12／blind 5／分母 17 | 中：i18n 在 peers 也只 3/16，属低优先；插件机制化是真实缺口但非参赛期目标 |
| 6 | 维护状态 | 30 天窗口内 616 次提交，但 `history_days=24 <30 ⇒ window_full=false` | 提交率 top：lobehub 32.40/日、letta-code 12.00/日、ryza-ai-revive 1.97/日；release/semver tag 11/16；issue 响应 **NA-DECLARED 17 条**（样本<3 ⇒ 该维不作差距项） | **self 无横比资格**（窗口未满），只报自身趋势；tag 14 个不落后 |
| 7 | 文档完善程度 | 21 件文档；四类位 **4/4**；`openapi 16 paths ⇄ Java 16 映射 ⇄ 前端引用`（本轮由 -1 修平）；`docs/API.md` 被 C7 三面钉住 | 四类位齐（4/4）仅 **1/16**（lobehub）；分布 0/4=4、1/4=1、2/4=4、3/4=4、4/4=1；**2 仓 unverified** | **self 领先，且本轮领先面从「位齐」升级到「位齐且与实现等值」**：修前 16 条端点有 1 条没写进机器契约，「API 文档 4/4」这句话当时是虚的 |
| 8 | 适用场景 | 演示级单用户 + 离线可完整演示 + 三路情绪 + 危机转介 | 定位抽样：lobehub(A)、SillyTavern(A)、Open-LLM-VTuber(B)、my-neuro(B)、letta-code(D)、MASCOT(C) | 不重判：tier 分级由台账给，本轮无新增证据 |

## 2. 逐项差距说明

**这一轮最值得写的差距，不在 peers 侧，在 self 的基座上。**
`server_preflight` 报「资源比产物新」，`api_contract_check` 报「控制器有 16 条路由、契约只有 15 条」——
两条红合起来指向同一件事：**8123 上跑的 jar 是 10-13 08:57 的产物，而 `DatabaseHealthController`（r169）在它之后才进仓**。
于是这一轮所有 C4「运行态一致」的绿，测的其实是旧代码。
本仓并不缺发现能力（`/api/health` 从 r131 起就回吐 `build` 产物身份，`jar_shape_check` 从 r99c 起用**资源 SHA**而不是 mtime 判新鲜度），
缺的是**处置通道**：重建产物要停掉 8123，而 8123 的持有者不是本工具起的 ⇒ `build_jar.py` 按 r104 立的属主纪律**拒绝停**（默认档只停 `ours`，`--takeover` 需人明确授权）。
我把 jar 改名探测过一次：`mv` 报 `Device or resource busy` ⇒ jar 被进程锁住，`mvn clean` 会失败或截断产物。**这是客观前提，不是可以绕的口子。**
所以本轮的处置＝在仓外副本树用同一份 `server/` 源码构建（203 用例全绿），起在 **8124** 把契约面真验一遍，
8123 面的红**如实留着**并写明解除前提（见 §4）。

**第二个差距是「接口面被写了两遍」。**
补 `/api/health/db` 进契约后，C6 立刻报「探测 15 + 豁免 0 == 操作 16」——不是因为文档写漏，
而是因为 `_test/api_contract_check.py:149` 有一份**手抄探测名单**：spec 的 `x-live-check` 标注只被当成「有没有解释」，
真打哪几条由名单决定。这条形态与本仓 AGENTS.md 决策 #5、AC-OBS-09 的旧值漂移同族（同一事实两处实现，漏改一处只在运行态暴露）。
修法是把它改成**成员资格由 spec 决定、名单只管先后**（先写后查再删的语义仍是硬约束，不能按书写顺序跑）。

**第三个差距是棘轮的可读性，本轮当场兑现了它的价值。**
R175-03 要求「所有 `基线=N` 的门面行加 `余量=`」。核对后实情是：全仓只有 4 把尺印 `基线=`，
其中 `blindred_guard` 已在 r175 做过，`asr_cantonese_eval.py` 是他方未入库新件（不碰），
真正欠的是 `timing_coupling_check` 一把。补上余量位之后**第一次跑就照出提交面 C1=22 > 基线 20、余量 -2 已越限**——
这个红此前一直存在，只是门面行不印，读者看到 `C1=22 基线20` 得自己减、还得知道该减哪一面。
同时否证了 R175-03 的一条子句：`inline_style_check` 的「欠账基线」是**被点名欠账的清单**，不是额度，
硬套 `余量=基线-现值` 会造出一个语义不存在的数。本轮改为让它自印口径说明。

**peers 侧本轮的量化读数**：CI 有单测执行位 6/16、有测试结构 7/16、有 linter 配置 2/16、
CONTRIBUTING 10/16、SECURITY 5/16、CODEOWNERS 1/16、dependabot 件 1/16；
`health_percentage` min 28 / 中位 62 / max 100。
对照 self：203 个 JUnit 用例 + 212 套件 + 每把尺带反例桩 ⇒ **自证密度仍是领先维，功能广度与产品化配套（release 流程、多语言、插件机制）仍是落后维**，方向与前 21 轮一致，没有反转。

## 3. 改进建议清单

| 级 | id | 建议 | 依据（一手） | 完成标准 | 本轮状态 |
|---|---|---|---|---|---|
| 高 | **R179-01** | 补齐 `/api/health/db` 的机器契约与人读手册，并把**探测成员资格**从手抄名单改成由 spec 标注决定 | `api_contract_check` C1 红因 `控制器有路由未文档化 [('GET','/api/health/db')]`；补文档后 C6 报 `15+0==16` | `api_contract_check` rc=0 且 `探测 16 + 豁免 0 == 操作 16`；桩含「spec 新增而名单未写仍被探测」的反例腿 | ✅ 已在 8124 新产物面达成（20 项 0 失败，桩 PASS）；8123 面受 R179-05 前提阻塞 |
| 高 | **R179-02** | 三件承担裁决作用的 ASR 数据件登记 provenance（R196 红线机器化） | `repo_config_check` G8 两面红：`_eval_last.json`/`asr_eval_baseline.json`/`asr_eval_manifest.meta.json` 未在 06 登记；`git cat-file -e HEAD:<面>` 逐件复算后两件已在库、第一件按 `.gitignore:115` 永不入库 | `repo_config_check` G8 两面绿 | ✅ 工作树面已绿；HEAD 面随本轮提交转绿。登记行内**明写「`_eval_last.json` 禁止登记条数」**——登记了就会让受理面腿去数一个永不在 HEAD 的件，变成不可满足的永红 |
| 高 | **R179-03** | 余量位按**尺的语义**推广，不是按格式套齐 | 全仓 `基线=` 仅 4 件；`timing_coupling` 缺 ⇒ 补出即照出 `余量=-2 已越限`；`inline_style` 是欠账清单型，套余量=造假 | `grep -rl "基线=" _test/*.py` 的每一件要么自印余量，要么自印「为何无余量位」 | ✅ timing 两面各一 + 4 条桩腿；inline_style 自印口径；asr_cantonese_eval 属他方未入库，归因不碰 |
| 高 | **R179-04** | 已入库却「电池与 CI 两头都不执行」的孤儿判据接入阻断链 | G16 点名 `asr_eval_check.py`、`asr_sidecar_check.py`；07 在册同类欠账（`asr_replay_check` 那条已由 r178 接上） | `repo_config_check` G16 绿且 `run_all_suites.py --list` 与 README 等值 | ✅ 两条 `--selftest` 腿入电池（210→212），G16/G4 双绿；接线动作连带暴露 `requests` 未进清单（G11 红），按 r130 先例补登记并让 G11 红因**自己印出来**（原先只印计数，取证要手拼三个内部函数） |
| 高 | **R179-05** | 重建 `server/target/soulisle-server.jar`，让 8123 回归面 == 提交面 | `server_preflight` rc=1；`mv` jar 报 `Device or resource busy`；`build_jar.py` 默认档对 `same-artifact` 持有者判 `拒绝停` | `python _test/server_preflight.py` rc=0 且 `python _test/api_contract_check.py`（不带 --base）rc=0 | ⛔ **未闭环，前提=持有 pid=30648 的会话自行停服**后跑 `python _test/build_jar.py --restart`。绕法（`--takeover`）会把并行会话的服务杀掉，r104 已记过三次同类事故，不做 |
| 中 | **R179-06** | `timing_coupling` 的两条未登记定长等待补评审账（`dock_auto_check.py::pg2.wait_for_timeout(500/600)`） | 桩 57/58 唯一不符腿点名这两件；门面行 `C1=22 基线20` | `timing_coupling_check` rc=0 | ⛔ **不归本轮**：这两处等待是他人提交的代码，评审账＝替别人判断「这个等待为什么必须存在」。只归因，不代写 |
| 中 | **R179-07** | 负测夹具禁止投真依赖名（⑬c 的幽灵针改成由 import 面自证不在其中） | 本轮实测：R179-04 让 `requests` 成为真依赖，`repo_config_check` 篡改⑬c 当场判失败——夹具写的正是「往清单里加 requests」 | `repo_config_check --selftest` rc=0（现 91 条全过） | ✅ 已随 R179-04 一并修掉，并补前置断言「幽灵针确实没人 import」，否则点名判失败而不是静默跳过该腿 |
| 中 | R179-08 | `eol_parity_check` 的 237 项既存红：先把行尾策略钉进 `.gitattributes`，再按面清 | 本轮 `python _test/eol_parity_check.py` rc=1；我改过的 8 个文件 wt_CR == 行数 ⇒ **全文统一 CRLF，本轮没引入混排**，红是存量 | `EOL-PARITY-PASS` | ⛔ 未动：属存量治理，且 `.gitattributes` 影响所有人 clone 的字节面，需老大点头 |
| 低 | R179-09 | peers docs 探针的 2 仓 `unverified(RuntimeError)` 补采（错峰单跑 `--repo` 增量合并） | `peer-docs-...-r179.json` 门面行 `失明或未验 2`；探针 rc=1 是**诚实读数**，不是缺陷 | 该维分母回到 16/16 或明记 NA 原因 | ⛔ 未做：本轮 docs 维其余 14 仓已有读数，够写结论；补采列 P-2 |
| 低 | R179-10 | perf 远端回执（R172-02/R175-06 续） | 本地领先 origin/main 235、落后 0 ⇒ 分叉已由 r178 的 merge 解开，推送不再需要 force | `gh run view --json conclusion` = success 且含 `闸态=unguarded` | ⛔ 未做：推送 235 个提交含他人轮内容，属对外共享状态动作，待老大点头 |

## 4. 可实施路径

| 阶段 | 时间 | 内容 | 里程碑（可复算） |
|---|---|---|---|
| **P-1 本轮已完成** | 2026-10-14 | S1=R179-01｜S2=R179-02｜S3=R179-03（+G11 红因自印、R179-07 夹具纠偏）｜S4=R179-04 | `api_contract --base 8124`：`合计 20 项，失败 0 项`；桩 `SELFTEST-PASS`；`repo_config --selftest`：`91 条…CI 实跑 212 套件`；`asr_sidecar_selftest`/`asr_eval_selftest` 各 rc=0；`bench_eight_dims --round r179`：`EIGHT-DIMS-PASS 维 8/8` |
| **P-2 解基座** | 并行会话停服后（本机当天可做） | `python _test/build_jar.py --restart` ⇒ 8123 换新产物；复跑 `server_preflight` + `api_contract_check`（不带 --base） | 两条均 rc=0；`/api/health` 的 `build` 指纹变成新摘要 |
| **P-3 清既存红** | 2026-10-16 | R179-06（他方评审账，归属轮次自理）＋ R179-09（docs 两仓补采）＋ 整跑电池一次全量（212 套件，分段跑并让收据并集 == 212） | `timing_coupling` rc=0；peers docs 分母 16/16；全量台账不再停在 r172 的 172/199 |
| **P-4 存量治理** | 2026-10-20 | R179-08 `.gitattributes` 行尾钉死（需点头）＋ G20 名册扩到本轮三处新声称 | `EOL-PARITY-PASS`；`repo_config` G20 红 0 点名 0 |
| **P-5 对外** | 2026-10-25 | R179-10 推送 + perf 远端回执（含他人 235 提交，属共享状态） | `git ls-remote origin main` == `git rev-parse HEAD`；run conclusion=success |

> **P-2/P-3 的动手前提**（复算命令）：
> `git status --porcelain -- _test/dock_auto_check.py` 为空 ⇒ R179-06 才可归给归属轮次；
> `python -c "import subprocess;print(subprocess.run(['powershell','-NoProfile','-Command','Get-NetTCPConnection -LocalPort 8123 -State Listen'],capture_output=True).stdout)"` 查不到监听者 ⇒ R179-05 才可执行。
