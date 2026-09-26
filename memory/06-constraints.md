# 06 - 已知约束

> 本文件记录已知问题、技术债和约束。
> 归档类型：增量（已解决的问题移入归档）

## 已知 Bug
<!-- 格式：- [BUG] 描述 — 影响范围 | 状态：未修复/修复中 -->
<!-- 解决后标记 - [x]，归档时自动移入 archive -->

## 技术债
<!-- 格式：- [DEBT] 描述 — 建议的还债方式 -->
<!-- 还清后标记 - [x] -->

- [DEBT] **`src/vendor/three.min.js` = r128（2021 年），上游已 r186（2026-09-24 实测）— 落后 58 个大版本**
  — 还债方式：iCAN 截止后独立阶段升级，**必须带视觉基线对照**（r152 起默认色彩管理改写、`Geometry` 移除、
  自定义 `ShaderMaterial` uniform 约定变更 ⇒ 星雾"暗星 0.05/点亮 0.26"与 `pixel_dual_check` 的双色像素级标定需整体重定）。
  截止前不动的理由 = 素材冻结期重做可视化不划算，不是拖延。
  **本条机器可见**：`python _test/vendor_freshness_check.py --check-upstream --strict`（现返回 rc=1，即"落后"不再可隐藏）。
- [DEBT] **`src/vendor/` 三个前端第三方库无包管理器可托管**（r21 更正本条范围，原写"零构建=挂不上 dependabot"是**错误归因**）
  — 已用 `_test/vendor-manifest.json`（版本 + sha256 唯一声明源）+ `vendor_freshness_check.py`（V1 完整性 /
  V2 从文件内容解析版本对账 / V3 新库漏登记即红）承担同等职责。**代价**：这三个库的上游发新版不会自动通知，须人工跑 `--check-upstream`。
  - ⚠️ **更正注（r21，2026-09-25）**：上一轮把"npm 生态挂不上 dependabot"扩大成"整个项目挂不上"，据此放弃了本可自动化的两半。
    实测更正：**Maven（`server/pom.xml`）与 GitHub Actions（`.github/workflows`）两个 ecosystem 与 npm 无关，可以直接挂**
    ⇒ 已加 `.github/dependabot.yml`（maven@/server + github-actions@/，每周二 08:00 Asia/Shanghai，PR 上限 3/2）。
    本条剩余真实盲区只有 `src/vendor/` 那三个手工 vendored 的 JS 库，由上面的 manifest 守卫承担。
- [DEBT] `src/js/app.js` 单体编排 —— **r24 已切第一刀**：语音（TTS+ASR）外提为 `src/js/voice.js`，471 → 403 行；剩余 曲线 / 窗口化 / 设置面板 三块待切（同法：外提 → index.html 顺序 → deploy 同步 → `size_budget` 登记 → 电池全绿 → 重部署）。⚠️ 原条目写 469 行系 r23 手测值，实际当时已 471 行 —— 数字断言再次与实值脱节（G4/G2 只覆盖 README 与 CI，未覆盖 06）。
- [DEBT] `tick()` 每帧遍历全部粒子做 CPU 侧着色（桌面档 2600 次/帧）；**真机帧率 ❌未实测** → 不进任何"性能领先"结论。
- [DEBT] 情绪引擎仍是**两份实现**（JS 离线降级用 + Java 后端权威）。本轮已把前端接到后端，但**词表仍须两端同步改**
  （红线不变，判据 `engine_consistency_check.py`）；`emotion_wiring_check.py` W6 另加一条"同句双端词典结论必须相同"。
  彻底消除两份 = 需要"JS 侧只保留极简危机词表"的重构，未排期。

- [x] [DEBT] 情绪引擎「两份真相」（`src/js/emotion-engine.js` + `server/.../EmotionLexicon.java`）—— 已由 J3 两端一致性常驻守卫 `_test/engine_consistency_check.py` 消除静默分叉风险（三层判据 + 端到端对照）；本地词典保留为离线降级（红线，不删）
- [ ] [DEBT] fat jar 尚未部署到国内可达机器（当前依赖 CloudBase 中间页）—— 见 `07-next-steps.md` P0 ③

## 红线（不能改）
<!-- 绝对不能修改的模块/约定 -->
- **密钥红线**：密钥零落前端、零入库；`src/js/demo-config.js`（含 Key）已 ignore，`deploy/xinyu/js/demo-config.js`（零密钥代理版）禁被 src 版覆盖
- **同步红线**：改 `src/` 必须同步 `deploy/xinyu/` 并做 SHA256 双向比对（MISSING/DIFF/EXTRA 三类归零）
- **静态页托管红线**：服务端直读 `src/`（`static-locations=file:${XINYU_WEB_ROOT:./src/}`），禁把前端复制进 `resources/static/`（第三处副本）
- **评测集红线**：`/api/emotion/eval` 直读 `_test/emotion-eval-dataset.json`，禁复制进 jar
- **词表一致性红线**：改 JS/Java 任一端词表须两端同步 + 跑 `_test/engine_consistency_check.py`
- **行尾红线（r36）**：文本一律 `eol=lf`（`.gitattributes` 钉死），落仓库的文本**禁用 `Path.write_text` 文本模式**
  （Windows 实测把 `\n` 翻成 `\r\n`，一次写入即毁掉归一）⇒ 改 `write_bytes`；复验也要按字节读
  （`read_text` 的 universal newlines 会把 CR 读成 `\n`，正好掩盖该缺陷）。判据 `_test/eol_parity_check.py`
- **性能口径红线（r40）**：性能数字只允许来自 `python _test/perf_baseline_check.py`（本地无外网、危机短路路径、阈值含 ~16–25 倍余量）。**禁止**「比某参照仓快 N%」式横向对比——16 仓实测无一家公开可比延迟/吞吐数值（报告 §14.1）；headless 或真机 FPS 未实测即写 ❌，不得充当性能结论。
- **远端可见面红线（r37）**：评委与公网看到的是**远端 main 文件树 + Release 资产 + 线上站点**；
  本机 `.gitignore` 只挡「以后再 add」，**不会把已推上去的东西从远端拿掉** ⇒ 本机工件
  （含 Key 的 `src/js/demo-config.js`、`_test/cors_probe.py`、`server/data/*.mv.db`、`*.jar`）
  出现在远端树即事故。判据 `_test/remote_tree_audit.py`（扫 origin 默认分支，实测 230 blob 零命中；
  空树或 `truncated=true` 判未验不判绿）。⚠️ 本仓名带 `private-archive` 而 visibility 实测为
  **PUBLIC** ⇒ 禁止按「私有」假设放松上传。
- **二进制红线（r36）**：png/jpg/mp4/pdf/jar/db 等按 `.gitattributes` 显式 `binary` 声明，
  新增二进制扩展名须先登记 —— r36 首轮归一曾剥掉 20 个二进制里的 `0D0A`（PNG/MP4 少 1–2 字节），
  由 `git show HEAD:` 全量还原；该形状现由判据 E3 盯住

## 性能/兼容性约束
<!-- 性能要求、浏览器兼容性、系统兼容性等 -->
- 

## 环境隔离（R196，init 必填）
<!-- 声明当前运行环境模式；dev 禁连 prod 库/密钥；production 操作前必须有近期备份 -->
- env_mode: development（枚举：development / staging / production）
- 红线：dev/staging 禁止连接 production 数据库与 API key
- production 操作前检查：近期备份存在（archive/ 或 DR 快照 ≤7 天）+ 密钥不复用
- 保护文件 .env.prod / .env.production 禁止入库（.gitignore 已含规则）

## 评测集隔离（R196）
<!-- 标注测试专用文件，禁止把训练数据写入测试集；新增评测数据先登记 provenance -->
- 测试专用文件清单（r23 填实，此前长期是 init 模板占位符 ⇒ 判据 `repo_config_check.py` G8 现在会盯这张表）：
  | 文件 | 条数 | 用途（谁在裁决时读它） | 来源 / provenance | 冻结状态 |
  |---|---|---|---|---|
  | `_test/emotion-eval-dataset.json` | **73 条** | `node _test/emotion_eval.js`（JS 侧）、`GET /api/emotion/eval`（Java 侧直读，决策 #5 不复制进 jar）、`engine_consistency_check.py` 双端逐条对账 | 团队自建：按 7 类情绪（joy/sadness/anger/fear/calm/love/crisis）人工撰写，**不来自任何模型输出或线上对话日志**；2026-09-23 由 36 条扩至 73 条（扩充部分同样人工写，含 6 条危机样本） | 结构冻结：新增只允许"人工写 + 双端复跑全绿"，禁止用 LLM 批量生成 |
  | `_test/vendor-manifest.json` | 3 条 | `vendor_freshness_check.py` 的完整性/版本对账声明源 | 本项目自维护（r21 建），非评测数据，列此仅为明确它**不属于**裁决用评测集 | 随 vendor 变更同步（`--refresh` 后人工核对 diff） |
- 红线：训练/生产数据禁止写入测试专用文件；新增评测数据先登记来源（provenance）
  - **为什么本项目特别要盯这条**：情绪评测集的准确率会被写进《应用方案》PDF 与答辩材料（当前 98.6% / 危机 6-6），
    一旦把"模型自己生成的样本"或"用户真实对话"混进测试集，这个数字就从"可复现的能力度量"退化成"自证循环"，
    而且双端对账（JS ↔ Java）会同时被污染 —— 两边都错也照样"全等"。
  - 真实对话落库走的是**另一张表**（`chat_message` / `emotion_record`，服务端持久化），与本清单物理分离，
    禁止把库里的用户文本直接回填评测集（既是污染，也是 PII 风险，见 iCAN 待办「③ PII 挂账」同源问题）。
- 机器责任：`python _test/repo_config_check.py` 的 **G8** 断言 ①本章节非占位符 ②清单里的文件真实存在
  ③`声称条数 == 文件实际 items 数`（改条数不改这里即红）。`--selftest` 用三类反例自证（抹登记行 / 改小条数 / 删章节）

## 红线补充（r26 新增，机器可判）

- **判据脚本必须 import-safe**：`_test/*.py` 的顶层入口调用（`sys.exit(main())` / `main()` / `raise SystemExit`）
  必须落在 `if __name__ == "__main__":` 守卫之后。原因不是风格：判据脚本会被互相 import（`--only` 自查、
  聚合 runner 对账、CI 复用），**无守卫 = 一 import 就跑全套或跑网络，而且退出码还是 0**。
  r26 实测：`run_all_suites.py` 若无守卫，import 一次等于把 29 条套件全量重跑。
  复算：`python _test/repo_config_check.py`（G9，逐脚本扫）+ `python _test/repo_config_check.py --selftest`（十一类）。
- **对标漂移必须分档**：★ 数单点差值（含倒退，如 lobehub 82,808→82,807 系平台清虚假账号）属**抖动**，
  不得与 `pushed_at` / `latest_release` / `caps` / `docs` 这类**实质**变化混在一张表里报，
  否则台账失去指方向能力（r26 实测：6 处漂移里只有 2 处可行动）。
  复算：`python _test/benchmark_metrics.py`（输出首行即"实质 N / 抖动 M"）。
- **06 正文禁手抄数字**（r25 立规、r28 再犯再修）：只写"判据可复算的事实 + 复算命令"，数字由 `_test/` 脚本现读。
  r28 实证这条连判据自己都不豁免：`repo_config --selftest` 的"十一类/十五类"两处手抄都与实际断言数不符，现改为
  `Path(__file__).read_text().count('bad.append("篡改')` 从代码里数。
- **密钥件永不进缓存**（r28 新增）：`js/demo-config.js`（本机含真实 Key）必须同时在 SW 的 `NO_STORE` 里，
  既不预缓存也不写缓存 —— 否则密钥会落进浏览器 Cache Storage（判据 A4 + R8 双盯）。
- **判据必须挂在真会走的路径上**（r28 新增，G10 机器化）：新写判据若只进本地脚本、不进 CI 步骤，
  等同于"没写"。豁免必须点名 + 恒等式（`实跑 + 豁免 == 总数`），幽灵豁免（豁免了不存在的套件）判红。
- **模式标签必须来自真实来源，禁硬编码"在线"**（r32 新增，R10a/R10b/R10c 机器化）：徽章看
  `ChatAgent.isOnline()` **且** `navigator.onLine`（配置在线 + 浏览器报断网 ⇒ 显示「网络不可用（配置为在线）」）；
  逐条回复标签按 `r.mode` 映射（model/fallback/offline/guard）；开场白标签固定为「本机开场白 · 未经大模型」
  （它从不经过模型）。`navigator.onLine` **只用于降级、不用于宣称在线**。
  复算：`python _test/offline_shell_check.py`（R10a 联网态须仍显「在线 AI」＝反向防写反；
  R10b 断网态须显「网络不可用」；R10c 开场白标签不得含「在线」）+ `python _test/rescan_shots_check.py`。
- **全零/差异结论须两条独立观测通道**（r31 新增）：任何形如"对手 N 家全都没有 X"的卖点句，必须由
  **两条互不依赖的通道**同时支撑（本项目 = 文件名法 `CAP_RULES` + 内容法 `offline_signal_class`），
  且逐仓归因语境（"offline" 可能是**离线训练**而非离线可用）、取数失败的仓必须记 `unverified` 并点名，
  `unverified != 0` 时**禁止**打印全零结论。措辞纪律：可以说"没人用浏览器 app-shell 做离线"，
  不可以说"没人做离线"（Open-LLM-VTuber 有本地模型完全离线，形态不同）。
  复算：`python _test/benchmark_metrics.py --offline-audit`（末行给两法对照）
  + `python _test/benchmark_metrics.py --selftest`（四类样本 + 两条反向 + 两个变异体）。
- **对标台账禁手动加能力位**（r30 新增）：`CAP_RULES` 是**双方同一把尺**（只读文件路径）。本项目的能力若因
  文件名而看不见，只能由 `blind_spot_caps()` 单列「盲区点名」，**不得写进 `caps`** —— 给参照仓"读内容"这条
  通道就是双标（r21 同族自纠）。复算：`python _test/benchmark_metrics.py`（self 行末尾即盲区点名，
  横向计数不受影响）+ `python _test/benchmark_metrics.py --selftest`（三向 + 三变异体）。

## 分卷目录
- **卷1** `06-constraints.part1.md` — 已完成条目归档（R224 主壳自愈）
  - **r25 第二刀已完成**：情绪曲线（Canvas 2D）+ resize 防抖外提为 `src/js/chart.js`，`app.js` 403 → **351 行**；剩余待切 = 对话窗口化（`RENDER_MAX`/`trimmedBuf`/配额）与设置面板两块。**但本条目实测行数已连续三次与实值不同**（06 曾写 469，r24 实测 471，r25 实测 403→351）⇒ 结论：**06 正文里的数字断言不该再手写**，改为「只写判据可复算的事实 + 附复算命令」，数字由 `_test/` 脚本产出（是否把 G 系列扩到全仓文档数字，仍待老大拍板）。
