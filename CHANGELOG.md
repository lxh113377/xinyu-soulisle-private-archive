# Changelog

本项目所有值得注意的变更都记录在此。
格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

> 对标 r25（2026-09-25 第六轮）：切分第二刀 —— 情绪曲线外提；外部漂移 3 处（★ lobehub 82,808 / ST 33,745 / OLV 13,903），
> 能力矩阵与 release/pushed 无变化 ⇒ 七维无翻牌，本轮差距继续来自自身结构。

### Changed
- **`src/js/chart.js` 外提**（`app.js` 403 → **351** 行，行为零改动）：`window.Chart = { render(), init() }`；
  原约束随迁（HiDPI `setTransform` 逻辑绘制 / resize 200ms 防抖且无数据跳过），新增缺画布时静默返回。
  `#btn-clear` 处理器留在编排内（它还管星图熄灭，不属于曲线）。
- 交付链同步完成：`index.html` 引入顺序 voice→chart→app（实测 6813 / 6845 / 6885）、`DEPLOY-SYNC-PASS`、
  `size_budget` 登记（17 文件，关键路径 822,936 / 858,752）、公网重部署 `0c90a2d9`、三判据 rc=0。

### Fixed
- 两处「工具没报错 ≠ 生效了」（同族坑连续第三轮）：
  ① 给 `size_budget` 打补丁时锚点写成 `4_355`（文件实为 `4355`），`str.replace` 未命中却照常打印"已登记"数字
    ⇒ 由 coverage 判据报「未登记预算的文件 ['src/js/chart.js']」暴露；补丁脚本改为**替换前 assert 锚点存在、替换后 assert 内容变化**。
  ② 抽曲线的脚本锚点条件过窄（依赖 `measureText` 前一行）⇒ `StopIteration` 半路死；
    改用 `#btn-clear` / resize 注释等**语义锚点**并 assert 边界行内容后再删段。
- `memory/07-next-steps.md` 的 P0 自驱条目在 r24 savepoint 时被迁进分卷未回补 ⇒ 壳内一度只剩"等老大"的两条，
  违反「P0 必须有一条可执行指令」的精神；已补回第三、四刀条目（含每刀的固定动作序列）。


> 对标 r24（2026-09-25 第五轮）：**结构性还债第一刀**，外部漂移 4 处（lobehub ★82,807 / pushed 09-25 等）。

### Changed
- **`src/js/app.js` 语音模块外提为 `src/js/voice.js`**（471 → 403 行，行为零改动）：
  `window.Voice = { init(), speak(), isSpeaking() }`，保留原三条约束（不支持即隐藏按钮 / 异常一律吞掉绝不带崩主链路 /
  开关走独立键 `peiliao.speak.v1` 不进 `cfg`，避免被 `setCfg` 清历史牵连）。
  这是 r22、r23 连续登记为「下一件」却两次推迟的项 —— 本轮作为唯一改动开工，**归因干净，不再登记第三次**。
- 交付链同步完成：`index.html` 引入顺序、`deploy/xinyu` 副本、`size_budget` 登记（4,148B / 预算 4,355B，
  关键路径 821,901 / 858,752），公网重部署 `41dea397`，`live_sync` / `public_check` / `online_check` 三判据 rc=0。

### Fixed
- 本轮自己造的一处噪声并留痕：同步命令把 `src/index.html` 误复制进 `deploy/xinyu/js/`，且 `2>/dev/null` 吞掉了本该提醒的报错
  ⇒ `deploy_sync` 报 EXTRA 一项。核实该副本未被 Git 跟踪且与源字节相同后删除、复跑归零。
  （同族坑：R212 明令降级检索禁配 `2>/dev/null`；上一轮刚写进报告，本轮自己又踩。）
- 又一条文档数字脱节：`memory/06-constraints.md` 写「`app.js` 469 行」，实测 471 行 ⇒ 已在该条更正注里点明
  **G2/G4 只覆盖 README 与 CI，未覆盖 06/05 的正文数字**（是否扩大覆盖面待拍板，见 ROADMAP）。


> 对标 r22（2026-09-25 同日第三轮）：本轮对标数据**零漂移**（16 仓与上一轮逐字段相同），
> 因此差距全部来自**对上一轮交付物自身的复审** —— 结果抓到两处真缺陷，都已修并配反例。

### Added
- **契约探测覆盖判据 C6/C6b**（`_test/api_contract_check.py`）：每条 OpenAPI 操作必须"被真实打"或"显式
  `x-live-skip` + 理由"，且本项目当前要求**零豁免**。`docs/openapi.yaml` 补齐 3 条漏标操作
  （`/api/memory/emotions`、`/api/memory/messages`、`/api/memory/message` POST）⇒ 探测数 **8 → 11 全覆盖**；
  `--selftest` 增第 5 类篡改样本（抹掉一条标注必须被 C6 抓到）
- **仓库配置自洽守卫** `_test/repo_config_check.py`（G1–G5 + selftest）：
  G1 dependabot schema（ecosystem 在支持清单内 / `directory` 真实存在且含对应 manifest / interval 合法）
  G2 CI job 数 == README 声称的门禁数 G3 `docs/openapi.yaml` 存在且被 `docs/README.md` 引用（不留孤文件）
  G4 电池条目数 == README 声称的套件数 G5（`--online`）GitHub 默认分支上 dependabot 文件可见
- 两条判据入全量电池（26 → **28** 套件）与 CI

### Added（r23 追加：R196 强制项从未落地）
- **评测集来源登记判据 G8**：实测 `memory/06-constraints.md` 的「测试专用文件清单」至今是 **init 模板占位符**
  （`（如 eval/testset_provenance.json / blindset / frozen）`）⇒ R196「新增评测数据先登记 provenance」这条红线**从未真正落地**，
  而评测集 accuracy（73 条 / 98.6%）是要写进《应用方案》与答辩材料的数字。
  - 06 该节填实为登记表：文件 / 条数 / 谁在裁决时读它 / provenance（人工撰写、**不用模型生成样本**）/ 冻结状态，
    并写明"真实对话走 `chat_message` 表、与评测集物理分离，禁止回流刷分"（同源 PII 风险）
  - 判据化 `repo_config_check.py` **G8**：① 不得残留模板原句（锚定 `清单：（如 `，不用泛指括号示例 —— 第一版因此把已填实的表判成假红）
    ② 登记的文件必须真实存在（R240）③ **声称条数 == JSON 实际 items 数**（改数据不改台账即红）
    ④ 只对裁决用数据核条数，不对配置声明件核（第一版把 `vendor-manifest.json` 的"3 条"当成 3 个样本 ⇒ 分母混用假红）
  - `--selftest` 扩到 **十类**合成篡改全抓（新增：抹评测集行 / 条数改小 / 删整节 / 表退回模板原句）

### Fixed（授权口径 —— 自审第三条发现）
- **整仓标 MIT 是不准确的声明**：`LICENSE` + README 中英双语均挂 MIT，但 `src/vendor/gsap.min.js`、
  `ScrollTrigger.min.js` 文件头自证为 **GreenSock Standard License**（非 MIT、非 OSI），只有 `three.min.js` 是 MIT。
  对公网分发的参赛作品属可被挑出的合规瑕疵。
  - 新增 `docs/THIRD-PARTY-NOTICES.md`：逐文件列 库/版本/授权/上游/再分发注意，并写明适用口径
    （高校参赛演示、不用 GSAP 构建竞争性动画产品 ⇒ 落在 Standard License 免费使用范围）
  - README 中英授权段改为「MIT **仅覆盖自研代码**」+ 指向该清单
  - 判据化：**G6** `src/vendor/*.js` 每个文件必须在清单中被点名（漏登记即红）、**G7** README 必须含指向清单的口径行
    （防改回"整仓 MIT"）；`--selftest` 两类新反例（抹 `gsap.min.js` 行、抹 README 引用行）均被抓到
- **本轮新加的 `--slice` 开关第一稿是死代码**（先滤掉 `--` 参数再判 `args[0] == "--slice"`，永不命中，
  于是 `--slice 0 14` 把 28 条全跑还报全绿）：改为按 `sys.argv` 原样解析 + `--list` 打印过滤后条数 +
  **过滤后零套件直接 rc=1**（禁止把 0/0 当通过）。实证 `--slice 3 3` → FAIL rc=1、`--only repo_config` → 2 条
- 撤回并在复跑后重写一条**先于证据**的结论（`28/28` 曾在两次后台运行输出 0 字节时被写进报告）
  ⇒ 记录为报告 §10.6：**后台任务 `exit 0` 不等于产物存在**

### Fixed
- **C4 原先的 `done >= 8` 是"阈值低于总量即掩盖"**：真实操作 11 条，只探测 8 条也判绿。现改精确对账
  `探测 + 豁免 == 操作总数` 且要求零豁免 —— 这是我自己上一轮留下的洞，本轮复审抓到
- **文档数字断言与实值脱节**（守卫上线当场抓到）：往电池加 2 条后 README 仍写"26 套件"，
  G4 立刻报红 `实测 28 | 声称 26`；已改并保留该红→绿过程作为反例证据（"文档写过的数字"从此有机器责任）
- dependabot 由"配了就算"升级为"配了且被受理"：G5 实测默认分支可见
  （`lxh113377/xinyu-soulisle-private-archive`），GitHub 只读默认分支 ⇒ 未 push 到默认分支的配置等于没配


> 本轮（对标 r21，2026-09-25）只动文档 / CI / 判据，**未改服务端与前端运行代码** ⇒ 版本号暂留 1.4.0，
> 下次含代码变更的轮次一并 bump（避免在截止前制造"版本号与产物不一致"的新债）。

### Added
- **接口契约唯一声明源** `docs/openapi.yaml`（11 条接口，含错误码与 SSE 语义）+
  守卫 `_test/api_contract_check.py`：C1 不缺文档 / C2 不虚文档（幽灵路径）/ C3 前端不得偷调未文档化端点 /
  C4 运行态状态码与必需键一致（真实打 `/api/chat`、`/api/emotion`，探测会话 `contract-probe` 结尾 DELETE 自清）/
  C5 `--selftest` 四类合成篡改全抓到。已入全量电池（24 → **26** 套件）与 CI `java-build`
- **依赖自动更新** `.github/dependabot.yml`：`maven`（`/server`，即 `server/pom.xml`）+ `github-actions`（`/`）
  两个 ecosystem，每周二 08:00 Asia/Shanghai，PR 上限 3 / 2

### Fixed
- **纠正 r20 自己写下的错误归因**：上一轮技术债记"零构建 ⇒ 挂不上 dependabot（没有 package.json）"，
  把"npm 生态挂不上"扩大成"整个项目挂不上"，据此放弃了本可自动化的两半。实测更正见
  `memory/06-constraints.md` 该条的**更正注**：真正无包管理器可托管的只有 `src/vendor/` 三个手工 vendored 的 JS 库
- **对标测量装置两处自纠**（本轮第二次采集立刻抓到问题，说明守卫有效但也确有洞）：
  ① 漂移比对只比 4 个数字字段 ⇒ `sapphire` 的 `container` 能力从清单消失却**零漂移报告**，现 `caps`/`docs` 纳入比对
  （`--selftest` 加两键样本）；② self 的"回归套件数"此前用文件名 glob（19）与报告口径（24 套件）**两个分母混用**，
  现唯一真相源改为 `run_all_suites.py` 的 SUITES 条目数，解析失败即报错、绝不回退 glob
- 参照池由 14 扩到 **16 仓**（本轮 `search/repositories?sort=updated` 实跑新捞
  `zeroa234/ryza-ai-revive` 190★/JS/09-22 活跃、`Bwcx-songyu/MoodChat` Java 同栈），漂移输出 `repo_added` 正常报告
- 能力探测新增 `api_spec`（机器可读 API 规范）：**实测 1/16** ⇒ 据此把 `docs/openapi.yaml` 在报告里
  登记为**自我改进**而非对标差距，不冒充竞品压力


## [1.4.0] - 2026-09-25 — 对标轮 r20：把"已经建好却没接上"的能力接上

### Added
- **情绪识别后端化接线** `src/js/emotion-remote.js`：共情链路的分类在后端 `/api/emotion`
  可用时以后端为准，**消除 J3 遗留的 JS/Java 两份真相**。开关口径与 J4 完全一致（三层）：
  代码层 `cfg.emotionRemote === true` 默认关闭 → 本地演示（fat jar）开启 → **公网版刻意不开**
  （Pages Function 没有 `/api/emotion`）。危机词在本地词典先判、**绝不为网络等待**；
  404/超时/响应形状不合法即熔断并回落本地引擎；气泡元信息如实标注「情绪:后端」，禁伪装
- **vendor 供给链守卫** `_test/vendor-manifest.json` + `_test/vendor_freshness_check.py`：
  三个首屏第三方库的**完整性哈希 + 版本声明对账 + 上游漂移探测**（零构建项目没有 lockfile，
  此前第三方库漂移是纯盲区）。V2 判据从文件内容解析版本，**正则零命中即判红**（不把"没测到"当"通过"）
- **对标源数据台账** `_test/benchmark_metrics.py` → `交付物/对标数据/benchmark-metrics.json`：
  14 个参照仓的 ★/最近推送/最新 release/CI workflow 数/文档齐备度/**递归整树能力矩阵**
  与本项目 self 指标同一份产物，每次运行输出**与上次快照的逐字段漂移**（治"数字来自历史快照"）
- 新判据入电池（19 → 24 套件）：`emotion_wiring_check`（9 项 + `--selftest` 3 类篡改全抓到）、
  `vendor_freshness_check`（+ `--selftest` 4 类篡改全抓到）、`benchmark_metrics --selftest`；
  CI `frontend-checks` 同步增 3 步

### Changed
- **gsap + ScrollTrigger 3.12.5 → 3.15.0（成对升级）**：前端实际用到的 API 面仅 5 处，
  升级后 `browser_check` / `lightshow_check` / `pixel_dual_check` 三套件全绿；
  首屏关键路径 819,767 B（预算 858,752 B 内）
- **体积预算表加"必须全覆盖"判据**：实测抓到原 13 文件表漏登记 `src/data/emotion-strategy.js`，
  且新增文件本会静默绕过体积门禁 —— 现在漏登记即红

### Removed
- 从 ROADMAP 计划里**撤下**「PWA / service worker 离线缓存」：本轮机器实测 14 个参照仓
  `pwa_offline` 命中 **0/14**（含 LobeChat / SillyTavern / Open-LLM-VTuber），
  即"同类优质项目都靠 SW 做离线"是首轮未经核实的推断；撤销理由与替代动作（`live_sync_check`
  机器守新鲜度）已写入 ROADMAP「本轮撤下的两项」

### Known issues（登记不隐瞒）
- `src/vendor/three.min.js` 实测为 **r128（2021）**，上游 **r186（2026-09-24）**，落后 58 个大版本。
  截止前不升级的理由与迁移风险（色彩管理默认变更 / `Geometry` 移除 / 自定义着色器约定 /
  星雾双色像素级标定需整体重定）已写入 ROADMAP 计划第 1 项，可用
  `python _test/vendor_freshness_check.py --check-upstream --strict` 机器复现


## [1.3.0] - 2026-09-24 — 对标轮第二轮：把"赛后再做"直接落地

### Added
- 工程化七件套（本轮前一并入 1.3.0 发版）：GitHub Actions CI、`.env.example`、`SECURITY.md`、
  Issue & PR 模板、英文 README、首轮对标分析报告
- **逐字流式输出（SSE）**：`/api/chat` 认 `stream:true`；Pages Function 与 Java 侧 SSE 直通，
  前端 `onDelta` 逐字渲染；代理不支持流式时按 `content-type` 自动回落整包，不留半成品气泡
- **共情策略表 SSOT** `src/data/emotion-strategy.js`：persona / rules / 分类器提示 / 危机话术 /
  每种情绪的共情要点·离线模板·采样参数集中一处，新增情绪类别代码零改动
- **多模型 provider 适配层**：`LLM_BASE/LLM_MODEL/LLM_KEY`（`DEEPSEEK_*` 保留兼容别名）
  + 设置面板 5 家快捷预设（DeepSeek / OpenAI / 通义 / Kimi / 本地 Ollama）
- **回复朗读**：`speechSynthesis`（zh-CN）开关，零依赖；浏览器不支持即隐藏按钮
- **对话列表窗口化**：DOM 上界 60 条 + 配额制「展开较早」；模型上下文与情绪记忆不受影响
- **响应式三档**（480/768/1024）+ **星雾粒子按视口降档**（900/1200/2600）
- 新判据三条：`_test/strategy_check.py`（含 `--selftest` 防恒真）、`_test/stream_contract.py`
  （A 非流式不破 / B 含内容帧≥2 / C 前端逐字且回落不冒充）、`_test/ux_guards_check.py`（21 项逐项判定）
- CI 增两条门禁 job：`java-build` 起**无密钥** fat jar 跑词表一致性红线（此前只写在 `memory/AGENTS.md` 靠人记）、
  `browser-regression` 跑浏览器回归（runner 无 GPU，强制 ANGLE/SwiftShader）；密钥扫描带拼接生成的对照组
- `ROADMAP.md`：对标差距 → 已完成 / 计划 / **明确不做（附理由）**

### Changed
- 红线从 4 条增至 5 条（新增「策略表成对红线」），`CONTRIBUTING.md` 同步
- CloudBase 云函数按 HTTP 请求-响应模型**刻意不做流式**（注释写明属设计内回落，非缺陷）

### Fixed
- CI 密钥扫描自伤：写死在 workflow 里的对照密钥会命中自身扫描 → 改拼接生成（本机实跑抓出）
- 「展开较早记录」原先放回即被同一上限裁回（等于没展开）→ 改配额制，新消息才收回上界

## [1.2.0] - 2026-09-24 — 提交包产出

### Added
- 《应用方案》PDF（18 页，含 8 图）+ 作品简介（259 字）+ 盲审遗留处置
- `_test/screenshots_resubmit.py` 重渲染链路（临时文件 → 校验 → 原子替换）
### Fixed
- Edge 打印页脚泄露本机文件路径（`--no-pdf-header-footer` + 全页复扫）
- `render-pdf.ps1` 先毁后坏缺陷

## [1.1.0] - 2026-09-23 — 体验与部署收口

### Added
- Docker 镜像真构建真运行实测（482MB，重启持久化、镜像内密钥扫描对照）
- `deploy/jar/` fat jar 部署包（start.ps1 / start.sh，JDK≥17 探测）
- `deploy_sync_check.py`（src→deploy SHA256 三类归零守卫）、`docker_image_sim_check.py`
- 评测集 36→73 条；语音输入实测
### Changed
- 全栈体验与健壮性优化 16 处；pixel 双色判据破除相位抖动（双条件判据 + 单色对照）
### Fixed
- Dockerfile 红线缺陷：`COPY src/` 会把含 Key 的 demo-config 打进镜像 → 改 `COPY deploy/xinyu/` + `.dockerignore` 纵深防御

## [1.0.0] - 2026-09-22 — Java 全栈主线贯通（J1–J5）

### Added
- Spring Boot 3.2.5 服务端：`/api/health`、`/api/chat`（与 v1 契约 1:1）、`/api/emotion`（+ `/eval` 双端逐项一致）、`/api/memory/**`（H2 file / MySQL 可切）
- 轻量 token 鉴权过滤器（`XINYU_API_TOKEN`，留空放行）
- 两端一致性守卫 `engine_consistency_check.py`；选型决策记录落盘（五条）
### Changed
- 静态页直读 `src/` 权威源（零副本策略）；评测集服务端直读不复制进 jar

## [0.x] - 2026-09-19 ~ 09-21 — v1 原型与基线

- 五幕 3D 情绪叙事页（Three.js + GSAP，零构建）；双路情绪引擎 + 危机优先拦截；
- Cloudflare Pages Function + CloudBase 云函数双线在线；localStorage 持久化与离线降级；
- 版本控制基线建立（2026-09-21）；MIT 协议与对外 README（2026-09-24 随词表 SSOT 化补入）

> 更早明细见 `git log`；本文件自 2026-09-24 起维护。
