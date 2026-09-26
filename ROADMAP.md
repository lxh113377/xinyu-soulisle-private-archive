# 心屿 SoulIsle · 公开路线图

> 依据：`交付物/对标分析报告-2026-09-24.md`（首轮，对标 LobeChat / Open-LLM-VTuber / SillyTavern）
> 与 `交付物/对标分析报告-2026-09-24-v2.md`（第二轮，14 仓 gh api 实测指标 + 同体量垂类项目横向对账）。
>
> 立此文件的原因（对标教训）：**Open-LLM-VTuber 13.9k★ 也近 4 个月零提交**——热度不等于可持续。
> 参赛项目赛后最容易死在"静默"上，所以路线与**不做什么**都要写成公开承诺，而不是散在聊天记录里。

最后更新：2026-09-25（对标轮 r26；r20→r26 每轮增量都在下方「已完成」各节，含被更正的历史结论）

---

## ✅ 已完成（2026-09-24 对标轮第二轮，全部当场实测）

| 项 | 对标差距来源 | 落地证据 |
|---|---|---|
| **逐字流式输出（SSE）** | LobeChat `fetch-sse` / OLV WebSocket，心屿原为整包返回 | `_test/stream_contract.py`：A 非流式契约不破 / B 32 帧中 30 帧含 `delta.content` / C 前端出现逐字气泡且不可达时不冒充在线 |
| **共情策略表 SSOT** | 三家均无可配置策略层；心屿原硬编码 `chat-agent.js` | `src/data/emotion-strategy.js` + `_test/strategy_check.py`（含 `--selftest` 注入分叉证非恒真） |
| **多模型 provider 适配层** | LobeChat 全家桶、OLV 可插拔后端 | `LLM_BASE/LLM_MODEL/LLM_KEY`（`DEEPSEEK_*` 兼容）+ 设置面板 5 家预设 |
| **回复朗读（TTS）** | OLV 多引擎 TTS、LobeChat 自研 TTS 库；陪伴产品不出声是硬短板 | `speechSynthesis`（zh-CN，零依赖）+ `_test/ux_guards_check.py` U1（构造计数实测，含"关得掉"） |
| **对话列表窗口化** | LobeChat `react-virtuoso` | 60 条 DOM 上界 + 配额制折叠展开；U2 实测 `getHistory`/`MemoryStore` 不受窗口化影响 |
| **响应式三档 + 粒子降档** | 心屿原先只有 1 条 640px 媒体查询 | 480/768/1024 + 900/1200/2600 三档；U3 实测无横向溢出且桌面档恒 2600（不破 `browser_check` 标定） |
| **词表一致性红线机器化** | 此前这条铁律**只写在 `memory/AGENTS.md` 靠人记** | CI `java-build` job 起无密钥 fat jar 跑 `engine_consistency_check.py` |
| **密钥零入库扫描进 CI** | 对标项目普遍靠 gitleaks；心屿原先只有本地 `public_check` | CI 对照组（拼接生成 canary，防自伤命中）+ 只扫 `git ls-files` |
| **浏览器回归进 CI** | 三家都有托管 CI | CI `browser-regression` job（runner 无 GPU → 强制 SwiftShader，本机已用同参数复跑 PASS） |

---

## ✅ 已完成（对标轮 r20，2026-09-25，全部当场实测）

| 项 | 对标差距来源 | 落地证据 |
|---|---|---|
| **情绪识别后端化（消除"两份真相"）** | 14 参照仓里 8 家已有向量/语义化记忆与后端化能力；心屿 J3 已做出 Java 引擎却**没被前端用上**（= 两份真相 + 卖点空转） | `src/js/emotion-remote.js`（三层开关与 J4 同口径）+ `_test/emotion_wiring_check.py` **9 项 PASS**：W4 实测 `stats.ok=1` 且气泡标「情绪:后端」/ W5 拦掉 `/api/emotion` 即熔断且**不冒充** / W3b 危机短路 `attempted=0` 未经后端 / W6 词典层双端同句同结论 |
⚠️ 更正见下方 r21 表「依赖自动更新」行 | `_test/vendor-manifest.json`（唯一声明源）+ `vendor_freshness_check.py`：V1 sha256 完整性；V2 从文件内容解析版本对账（正则零命中即红，禁"没测到=通过"）；V3 新库漏登记即红；V4 `--check-upstream` 报落后（`--strict` 才判红）；`--selftest` 4 类篡改全抓到
| **gsap + ScrollTrigger 3.12.5 → 3.15.0 成对升级** | 上游 greensock/GSAP tag 3.15.0（实测 releases/latest 404 ⇒ 该仓只发 tag，探测已按此实现） | 前端实际用到的 API 面**仅 5 处**（`gsap.to/timeline/registerPlugin`、`ScrollTrigger.refresh`、`window.gsap`）；升级后 `browser_check` / `lightshow_check` / `pixel_dual_check` **三套件 rc=0**；体积 +713B/+1,195B，关键路径 819,767/858,752 仍在预算内 |
| **体积预算表覆盖判据（补一个真实存在的洞）** | 上一轮刚建的 `size_budget_check` 靠手工列表 ⇒ **"加文件"这条最常见的退化路径恰好绕过门禁** | 实测抓到 2 处：漏登记 `src/data/emotion-strategy.js`（4,720B）与本轮新增的 `emotion-remote.js`；新增 coverage 判据 + `--selftest` 同时证两条判据非恒真 |
| **对标源数据机器化台账** | 前两轮报告的星数/停更日期来自一次性手工 curl，**下一轮无法机器复核**（度量可信度 M1「数字来自历史快照」风险源） | `_test/benchmark_metrics.py` → `交付物/对标数据/benchmark-metrics.json`：14 仓 ★/pushed/release/CI wf/文档/**递归整树能力矩阵** + 本项目 self 指标，每次运行输出**与上次快照的逐字段漂移**；`--selftest` 合成 2 处改动全抓到、全等对照零误报 |


## ✅ 已完成（对标轮 r21，2026-09-25 同日第二轮）

| 项 | 来源 | 落地证据 |
|---|---|---|
| **接口契约唯一声明源 + 三方对账** | **自我登记的可维护性债**（诚实口径：实测 16 参照仓 `api_spec` 命中仅 **1/16**，不是被同类甩开的差距；但本项目契约此前分散在 `j2_chat_contract.py`/`chat-agent.js` 常量/部署文档三处，改一端忘两端全靠人记） | `docs/openapi.yaml`（11 条，实读控制器与 `LlmProxy` 取得）+ `_test/api_contract_check.py` C1 缺文档即红 / C2 幽灵路径即红 / C3 前端偷调即红 / C4 真实打 8 端点状态码与必需键一致 / C5 `--selftest` 四类合成篡改全抓 |
| **依赖自动更新（可自动化的一半）** | r20 我把这件事整体判为"做不了"，**属错误归因**（见下条更正） | `.github/dependabot.yml`：`maven`@`/server` + `github-actions`@`/`，weekly 08:00 CST，PR 上限 3/2；self 能力位 `deps_autoupdate` 由 0→1（台账机器可见） |
| **测量装置自纠两处** | 第二次实采立刻暴露自己的洞 | ① 漂移原先只比 4 个数字字段 ⇒ `sapphire` 掉 `container` 却零报告，现 `caps`/`docs` 纳入比对（selftest 加样本）② self "回归套件数"原先 glob=19 与报告"24 套件"**两个分母混用** ⇒ 改取 `run_all_suites.py` 条目数为唯一真相源（现 26），解析失败即报错不回退 glob |
| **账面文档齐备度补到 9/9** | 对标 §4.6 唯一缺项 | `docs/README.md` + `docs/openapi.yaml`；self `docs=9/9`，`api_spec` 位 0→1 |

## ✅ 已完成（对标轮 r22，2026-09-25 同日第三轮：差距全部来自复审自己上一轮的交付物）

> 本轮 16 个参照仓指标**零漂移**（与上一轮逐字段相同）⇒ 没有新的外部差距可抄，
> 于是把镜头转向自己上一轮写的守卫，当场抓到两处真缺陷（都已修 + 配反例）。

| 项 | 抓到的问题 | 落地证据 |
|---|---|---|
| **契约探测从"够数就行"改成精确对账** | 上一轮 C4 写的是 `done >= 8`，而 spec 真实操作有 **11** 条 ⇒ 3 条接口既不探测也不解释，判据却绿（阈值低于总量即掩盖） | `docs/openapi.yaml` 补齐 3 条 `x-live-check`，探测 **8 → 11 全覆盖**；新增 C6 `探测 + 豁免 == 操作总数`、C6b 要求**零豁免**；`--selftest` 加第 5 类篡改（抹标注必被抓） |
| **第三方授权边界精确到文件**（自审第三条） | 仓库整体标 **MIT**，但 `src/vendor/gsap.min.js`/`ScrollTrigger.min.js` 文件头自证是 **GreenSock Standard License**（非 MIT、非 OSI），只有 three.js 是 MIT ⇒ 公网分发参赛作品的可挑出合规瑕疵 | 新增 `docs/THIRD-PARTY-NOTICES.md`（逐文件：库/版本/授权/上游/再分发注意 + 本项目适用口径）；README 中英改为「MIT 仅覆盖自研代码」并指向清单；判据 **G6**（vendor 每个 .js 必须在清单点名）+ **G7**（README 必须引用清单，防改回"整仓 MIT"），`--selftest` 两类新反例（抹 gsap 行 / 抹 README 引用行）均被抓到 |
| **仓库配置自洽守卫** | dependabot「配了」≠「生效」：GitHub 只读默认分支、ecosystem/目录拼错时**静默不跑**；且文档数字断言无机器责任 | `_test/repo_config_check.py` G1 schema+目录含 manifest / G2 CI job 数==README 声称 / G3 契约被索引引用 / G4 电池条目数==README 声称 / G5 `--online` 默认分支可见（实测 PASS）/ G6+G7 授权边界。`--selftest` 六类篡改全抓 |跑**；且项目文档里"26 套件 / 四条门禁"这类数字断言无机器责任 | `_test/repo_config_check.py` G1 schema+目录可达 / G2 CI job 数==README 声称 / G3 契约被索引引用 / G4 电池条目数==README 声称 / G5 `--online` 默认分支可见。实测 **G5 PASS**（`...-private-archive` 默认分支可见） |
| **守卫上线即抓到一个真实脱节（红→绿留证）** | 往电池加 2 条后 README 仍写"26 套件" | G4 当场报 `FAIL 实测 28、声称 26` → 改文档 → 转绿。此过程即该判据的判别力证明 |

### 🔧 一条自我更正（r20 → r21）
r20 的"vendor 供给链守卫"一行里我写了「心屿零构建 ⇒ 无 lockfile、**无 dependabot**」，并据此把依赖自动化整块判为不可做。
**这把"npm 生态不适用"扩大成了"整个项目不适用"**：dependabot 的 `maven` ecosystem 对着 `server/pom.xml` 就能挂，
`github-actions` ecosystem 连包管理器都不需要。r21 已配置并在 `memory/06-constraints.md` 原条目下加更正注（不删历史）。
⇒ 真正的盲区只剩 `src/vendor/` 三个手工 vendored 的 JS 库，由 manifest 守卫承担。

## ✅ 已完成（对标轮 r24，2026-09-25 第五轮）

| 项 | 内容 | 证据 |
|---|---|---|
| **`app.js` 模块化第一刀（连续两轮登记的「下一件」，本轮做完）** | 语音（TTS 朗读 + ASR 输入）与编排零耦合，且行为面已被两条专门判据盯住 ⇒ 适合先摘；外提为 `src/js/voice.js`，`window.Voice = {init, speak, isSpeaking}` | `app.js` 471 → 403 行；`ux_guards` U1 六项 + `voice_check` A1-A6 + `browser_check` 全断言 rc=0；电池 `--slice 0 14` 14/14、`--slice 14 28` 14/14 ⇒ **28/28** |
| 交付链完整性 | 切分不能只改 `src/` | `index.html` 引入顺序实测（voice.js 6813 < app.js 6849）；`DEPLOY-SYNC-PASS`；`size_budget` 登记 4,148B/预算 4,355B，关键路径 821,901 / 858,752；公网 `41dea397` 后 `live_sync`/`public_check`/`online_check` 全 rc=0 |

> 剩余切分（同法，每刀单独一轮）：情绪曲线 `drawChart()` → 对话窗口化（`RENDER_MAX` / `trimmedBuf` / 配额）→ 设置面板。
> ⚠️ 排产自省：这项在 r22、r23 都被写成「下一件」却没做。**登记两次而未执行 = 排产缺陷，不是待办**；
> 今后凡 07 里连续两轮未推进的条目，下一轮**必须优先做它**或显式写明"为何本轮仍不能做"，禁止第三次登记。

## ✅ 已完成（对标轮 r25，2026-09-25 第六轮）

| 项 | 内容 | 证据 |
|---|---|---|
| **切分第二刀：情绪曲线外提** | `src/js/chart.js`（`window.Chart={render,init}`），`app.js` 403 → **351 行**；约束随迁（HiDPI 逻辑绘制 / resize 防抖且无数据跳过），补"缺画布静默返回" | `browser_check` 曲线两态断言 + `ALL-ASSERT-PASS`；电池 `--slice 0 14` 14/14、`--slice 14 28` 14/14 ⇒ **28/28 rc=0**；`DEPLOY-SYNC-PASS` + `size_budget` 17 文件在限内 + 公网 `0c90a2d9` 后 `live_sync`/`public_check`/`online_check` rc=0 |

> **一条机制性教训（连续三轮复发的同族坑）**：r23 判据阈值 `done >= 8` 掺水、r24 `2>/dev/null` 吞掉 cp 报错、
> r25 `str.replace` 锚点不匹配却打印"已登记" —— 三者同一根因：**把"命令没报错"当成"事情生效了"**。
> 本轮起统一加两道 assert（替换前锚点存在、替换后内容变化），并登记待办：做 `_test/patch_apply.py`
> 让"改文件"这件事本身有判据，而不是靠每轮记得住。（r26 更正：该族实为**四轮四形态**，
> 首轮是 r20 的"构建失败却因旧进程回 200 成假健康"，r25 台账把它漏记了；r26 又复发第五次 —— 见下。）

## ✅ 已完成（对标轮 r28，2026-09-25 第九轮）

| 项 | 内容 | 证据 |
|---|---|---|
| **只读离线壳（对标反读出的差异化）** | `pwa_offline=0/16` 已证真零 ⇒ 16 个同类都没做；补 `src/sw.js`（HTML network-first / vendor cache-first 指纹钉名 / `/api/**` 永不缓存 / 密钥件永不落缓存） | `_test/offline_shell_check.py` **14 项 + 13 类注入反例全绿**；**R9：公网真断网仍可演**；公网 `54fb9778` |
| **判据挂上真发布路径** | CI job 从只跑 1 条改为整跑电池（无密钥豁免两条、点名、恒等式）；新增 **G10** 常驻盯覆盖分母 | `repo_config` G1–G10 全 PASS；`--exclude-llm` 本地实测 **31/31 rc=0**；全量 **33/33** |
| **少写代码也是产出** | 实测发现 Java `CacheHeaderFilter` 被 Spring 资源处理器的 `no-store` 覆盖 = 死代码 ⇒ 删除；Pages 侧只钉真正缺头的两条 | R6a/R6b 两端头实测（认"再验证"语义：no-cache/no-store/must-revalidate） |

## ✅ 已完成（对标轮 r27，2026-09-25 第八轮）

| 项 | 内容 | 证据 |
|---|---|---|
| **判据先行 + 切分第四刀** | 先补 `_test/settings_panel_check.py`（S1–S8，五类注入反例），再外提 `src/js/settings.js`；`app.js` 241 行（复算命令见 `memory/05`） | 旧代码基线 9/9 PASS → 外提后 9/9 PASS；selftest 五类反例全抓；电池 **31/31 rc=0**；公网 `4f8cd81b` 等字节复验 |
| **全零要有分母证明** | `coverage_hits` 把树截断/取数失败的仓踢出分母并点名原因，恒等式不成立即 rc=1；实测核对 lobehub 树 20,740 对象 `truncated=false` ⇒ `pwa_offline=0/16` 为真零 | `--selftest` 合成盲区 1 有效 / 2 点名；负控制（换回旧写法）实测 rc=1 |

## ✅ 已完成（对标轮 r26，2026-09-25 第七轮）

| 项 | 内容 | 证据 |
|---|---|---|
| **切分第三刀：对话窗口化外提** | `src/js/chat-window.js`（`window.ChatWindow={init,push,update,setTag,toBottom}`），`app.js` 351 → **268 行**；行为零改动，`quota`/`trimmedBuf`/折叠提示条全部关进模块。与前两刀的差别：这块**被对话主流程调用**，所以接口设计是"关住 DOM 细节"而不是"搬出状态" | `ux_guards_check.py` **U2a–U2f 行为判据**（连发 90 条 → `.msg ≤60` / 提示条标折叠数 / `getHistory` 仍 40 / 展开真放回且顺序在前 / 新消息后收回上界 / 零 JS 异常）合计 21 项全绿；`stream_contract` + `browser_check` + `voice` + `emotion_wiring` 同绿；全量电池 **29/29 rc=0** |
| **预算反向棘轮** | 切分后把 `app.js` 预算从 23,979 **收紧到 14,777**（实测 14,073 +5%），新件登记 5,845 ⇒ "切分"不会只减文件不减约束 | `size_budget_check.py` 18 文件 `BUDGET-PASS`（824,777 / 858,752）+ `--selftest` 逐项报红 |
| **漂移台账分档** | `classify_drift`：★±1 入"抖动档"（本轮 6 处漂移中 4 处，含 lobehub 82,808→82,807 **倒退**），`pushed_at`/`release`/`caps`/`docs` 入"实质档"（2 处，均在 sapphire：v2.5.0→v2.13.1） | `--selftest` 两侧都验：分档正确（实质 3 / 抖动 1）+ **纯抖动场景必须 0 实质**（否则分类器只是换个名字再报一遍）；破判据的负控制实测 rc=1 |
| **G9：判据脚本必须 import-safe** | 第五次同族坑——给分档判据做负控制时 `import` 触发 16 仓联网采集后 `exit 0`，**反例没执行却看起来像通过**；全仓扫出 3 个无守卫脚本（含聚合 runner，import 一次 = 29 套件全量重跑），全部补 `__main__` 守卫并加常驻判据 | `repo_config_check.py` G9「29 个脚本已扫，零违规」；`--selftest` 十一类（含"有守卫不得报红""函数体内 sys.exit 不算违规"两条反向样本） |

## 🔜 计划（赛后 1–2 周，按投入产出排序）

1. **three.js r128 → r186 升级**（对标轮 r20 新登记的**头号技术债**）——
   实测：`src/vendor/three.min.js` 内 `REVISION` 值为 **128**（2021 年发布），上游 `mrdoob/three.js` 当时最新
   **r186**（2026-09-24 发布），跨 **58 个大版本**。登记为 `_test/vendor-manifest.json` +
   `python _test/vendor_freshness_check.py --check-upstream --strict`（现在就能机器复现"我们落后多少"）。
   **不在截止前动的理由**（不是拖延，是风险）：r152 起默认色彩管理改写（`outputColorSpace` 取代
   `useLegacyLights`/`sRGBEncoding`）、`Geometry` 全面移除、自定义 `ShaderMaterial` 的 uniform 约定变更
   ⇒ 星雾"暗星 0.05 / 点亮 0.26"与**双色像素级标定**（`pixel_dual_check` 判据 0.25/0.10 双条件）需整体重定，
   等于在答辩素材冻结期重做可视化。升级须独立成阶段并带视觉基线对照。
2. **对话列表真正虚拟化（窗口外节点回收 + 滚动位置保持）**——当前是"上界 + 分批展开"，长会话（>500 条）还需滚动锚定。
3. **结构化记忆升级（persona 维度）**——对标 SillyTavern 世界书：`emotion_record` 加偏好标签，从"记得历史"进化到"记得你的偏好"。
4. **危机干预链路可审计化**——危机命中事件的服务端留痕与导出（**不留对话原文**，只留时间戳与类别），配合《应用方案》里的伦理章节。
5. **i18n 框架化**——低优先（面向国内高校），但 `README.en.md` 已是第一步。

### ⚠️ 本轮（r20）从计划里**撤下**的两项，附实测理由

- **「PWA / service worker 离线缓存」→ 撤销，不做**（原计划第 1 位）。
  依据：`_test/benchmark_metrics.py` 递归整树探测 14 个参照仓，**`pwa_offline`（sw.js/service-worker.js）命中 0/14**
  ——包括 LobeChat/SillyTavern/OLV 三家头部项目。即"同类优质项目都靠 SW 做离线"这个前提**不成立**，
  它是首轮报告未经核实的推断。且心屿三个第三方库本就随源码分发（`src/vendor/`），资源层已是本地化；
  在截止前给评委用的地址加 SW，只会引入"线上改版但旧 SW 继续投喂旧页面"这一类难复现的缓存故障
  （本项目已有一次 jar 进程内缓存导致的假象教训）。**替代动作**：`manifest.webmanifest` 保留（r17 已上线），
  新鲜度改由 `_test/live_sync_check.py` 机器守（线上 == 权威源逐字节）。
  > **⚠️ 更正注（r28，2026-09-25，同日第九轮）——本项已被现实推翻，撤销口径作废，原文按纪律保留不删。**
  > 推翻它的不是新数据，而是**把同一条数据反着读**：`pwa_offline=0/16` 当时被我读成"没人做，所以不必做"，
  > r27 又先证明了这个全零是真零（两条独立观测通道，见 `交付物/对标分析报告-2026-09-25.md` §15.3/§18），
  > 于是它从"不必做"的理由翻成"唯一低成本的差异化能力"。落地形态是**只读离线壳**而非通用缓存层：
  > HTML/JS/CSS 走 network-first（不存在"旧 SW 投喂旧页面"这一类故障，`live_sync` 仍逐字节守），
  > `vendor/`+`assets/` cache-first 且缓存名由 vendor 内容指纹钉死，`/api/**` 与非 GET **完全不碰缓存**，
  > 含密钥的 `js/demo-config.js` 既不预缓存也不写缓存。判据：`_test/offline_shell_check.py`（A1–A10 静态审计
  > + R1–R9 运行时，含**公网真断网仍可演**）与 13 类注入反例；线上 deployment `54fb9778`。
  > 本节上方"已完成"表第 94 行才是当前事实，此处历史判断仅留痕。
- **「`/api/emotion` 前端接线」→ 已完成，移入下方已完成表**（r20，2026-09-25）。

## 🚫 明确不做（附理由，避免被"对标"裹挟）

| 项 | 为什么不做的硬理由 |
|---|---|
| 插件市场 / 扩展 SDK | 参赛作品不需要生态，需要的是"加一类情绪只改一处"——已由策略表 SSOT 达成同等可维护性，成本 1/50 |
| 角色卡 / persona 商店 | 偏离"情绪陪伴垂类"定位，与差异化卖点（双路识别 + 危机拦截 + 可复现评测）无叠加收益 |
| 改用 React/Next + 构建器 | 选型决策 #1/#2 已记录：零构建换来"评委免环境直开"，直读 `src/` 换来零副本同步点。架构维度不与 React 系对齐是**有意取舍** |
| 引入 Spring Security + JWT | 决策 #4：单体演示应用只需私有部署护栏；需要账号体系时再评估 |
| 多用户 / 团队协作 | 同上，且与"隐私本地化"卖点冲突 |

---

## 版本节奏

- 语义化版本 + `CHANGELOG.md`（Keep a Changelog）。当前版本：**v1.4.0**。
  这条断言有机器责任方：`_test/repo_config_check.py` **G12** 拿三个源对账（`git tag --sort=-v:refname` 最大值
  == `server/pom.xml` `<version>` == 本行与 README 里写死的版本号），任一不符即红
  （r35 实测本行停在 `v1.3.0` 而实际已发 `v1.4.0` —— 与"文档数字脱节"同族，此处首次封成常驻判据）。
  每个「可验证关卡」（一组改动 + 全绿判据）即一次小版本；iCAN 提交件冻结点单独打 `ican-2026-submit` 轻量标签，便于赛后回溯。
- 每季度末复核一次本文件：完成项移上、明确不做项如被现实推翻须写「更正注」而非删除（决策留痕）。
