# Changelog

本项目所有值得注意的变更都记录在此。
格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### Fixed（r33 收尾）
- **对标 r33 footer 落错卷**：GM 端 footer 被写进「明天」的卷且 ts 手写 ⇒ 对零参数默认门禁不可见。
  已在当天卷重落，并给门禁加未来日卷阻断（判据升级落在 skill 侧，本仓只留痕）。
- `memory/07-next-steps.part17.md`：fat jar / 容器部署待办补齐「三件套」（执行目录 / 日志必见证据 / 回滚锚）。

> 对标 r33（2026-09-25 第十四轮）：**公网重部署追平本地** —— r32 改的降级徽章与诚实标签此前只在本地，
> 公网仍是旧版；本轮上线并四项复验。外部漂移 **0 处**（首次连 ★ 都没动，但两次采集只差 22 分钟，
> 不能读成"对手停止演进"）。

### Changed
- **公网部署**：deployment `b5f46ecf`（回滚锚 `ec881aaa`）。部署前发现一个会让线上挂掉的坑：
  `deploy/xinyu/` 里**没有** `functions/` 目录，Functions 源在 `deploy/functions/`，
  wrangler 的 Functions 目录是**按 cwd 解析**的 ⇒ 必须 `cd deploy` 再 `npx wrangler pages deploy xinyu ...`；
  部署日志须出现 **`Uploading Functions bundle`**，否则 `/api/chat` 会在新 deployment 里消失（404）。
- 复验四项全绿：`live_sync_check`（线上 `/` 与本地 `index.html` 逐字节等 9,463B）、
  `public_check`（浏览器级：标签实测「在线大模型生成 · 逐字流式 · 词典+LLM 分歧 → 采信 LLM · 2184ms」、
  危机 True、CONSOLE_ERRORS 0、KEY_LEAK False）、`POST /api/chat` 200、
  公网 `app.js` 含「网络不可用」×3 / `chat-window.js` 含「本机开场白」×1（证明 r32 两处修复**在线上生效**）。
- 提交清单第 3 行的验收判据改为**带部署命令与 Functions 守卫**的可复算式，并记下 deployment id。

### Fixed
- **自抓一条"拿旧数当本轮结论"**：本轮第一次读快照算漂移时，误把 r31→r32 的差当成 r33 的（快照末条 ts
  是上一轮的），核对 ts 后重采两次（11:12 / 11:13 UTC）才取到本轮真值 0 处。
  教训：`与上一次快照比对` 必须先证明"上一次"确实是上一轮，而不是"文件里最后一条"。

### 下一件（已登记 07）
- 成片（217.6s）录在 r32 徽章/开场白修复**之前**，画面里仍是「在线 AI · 共情模式」旧标签
  ⇒ 按刚落地的 consulting-analysis M6「材料须追上构建」，下一件重录成片。

> 对标 r32（2026-09-25 第十三轮）：**交付物回扫（R242）** —— 方案正文对三项已建成能力 0 命中，
> 顺手抓出两处"伪装在线"出口并机器化封死。外部漂移 4 处 = 实质 1（`my-neuro` 今日推送：移除 PyQt 桌面 UI、
> 转 Web UI + 插件广场）+ 抖动 3 ⇒ 对手正往"浏览器化 + 扩展生态"收敛，印证可扩展性维度的既有差距，
> 但 5 天内不可行动（登记为赛后项）。

### Added
- **方案新增 6.7「离线可用：浏览器应用壳」+ 7.8「评委自助：设置面板与模式自证」+ 实拍图 8/9**，
  7.3 补 SSE 逐字流式一句；6.6 耗时行由单次样本改为**两次独立实测区间**（965 ms / 1,378 ms）。
  动因是 grep 实测：`sw.js`/`Service Worker`/`PWA`/`逐字`/`流式`/`设置面板` 在 `application-plan.html` **0 命中**，
  而"离线"那 21 处全部指**离线降级模板**（§7.6），不是 r28 交付的应用壳。
- **`_test/pdf_leak_scan.py`（新常驻判据，电池 35 → 37 套件）**：解 FlateDecode 流抽 PDF 可见文本，
  扫 `file://` / Windows 家目录 / `sk-` 密钥 / 邮箱 / 手机号；**零输入不得判 CLEAN**（可抽文本 <2000B 即 UNVERIFIED）。
  自测三侧：正例含字体噪声串不误报、五类真敏感全抓、`12356` 与 `%@P`/`c-@g.Bk` 不被误抓。
  落地过程中两轮误报（字体子集名被判成邮箱）都是**先改判据再下结论**，没有放宽判据求绿。
- **`_test/rescan_shots_check.py`**：出图前机器断言（预缓存 ≥17 项才允许断网、断网后五幕结构在、
  零 `XINYU-SHELL-MISS`、Key 框 `value` 为空且 `type=password`、截图面零密钥串），先落 `_shots/` 目检后才进交付物。
- **`render-pdf.ps1` 期望图数改为从 HTML 现读 `<figure>`**（原手抄"预期 8 张"，加图后必成假告警），
  并加"数不到 figure 即判不可信"的空输入守卫。

### Fixed
- **两处"伪装在线"出口（红线级，同类出口已枚举全仓确认只剩这两处）**：
  ① 引擎徽章只看配置不看网络 ⇒ 断网重开仍显示「● 在线 AI」（截图当场抓到）；改为
  配置在线 + `navigator.onLine === false` 时显示「● 网络不可用（配置为在线）」并注册 online/offline 事件回灌，
  `navigator.onLine` **只用于降级、不用于宣称在线**；② 开场白标签硬编码「在线 AI · 共情模式」，
  而该句从不经过模型 ⇒ 改为「本机开场白 · 未经大模型」。判据 `offline_shell_check` 新增 **R10a/R10b/R10c**
  （R10a 是反向断言：联网态仍须显示「在线 AI」，防我把分支写反造成恒绿）。
  变异体双侧实测：摘掉网络分支 → R10b 翻红；标签改回伪装文案 → R10c 翻红；还原后全绿。
- **G9 当场拦下我自己新写的脚本**（`rescan_shots_check.py` 顶层执行 + 无 `__main__` 守卫）——
  r26 那族第五次复发形态由判据自动抓住，已包成 `main()` + 守卫。
- 图序缺陷：新加的「图 8」原本落在 §6.7，排在旧图 1–7 之前（文档顺序倒置）⇒ 移到 §7.8 之前，
  正文改交叉引用「实拍见图 8」；判据改为按 `<figcaption>` 断言图注单调递增。
- `README.md` 三处状态性数字按本轮实测更新（35→37 套件、r20–r27→r20–r32、首屏 819,767→832,373 B）。
- `src/js/app.js` 体积预算按既有口径（实测基线 ×1.05）由 13,780 上调至 **14,390**，理由写进表内注释与本版；
  徽章修复使 app.js 13,123→13,698B（余量仅 82B 会让下一轮任何一行改动都撞墙，故按算法重设而非凭手感抬）。

### 交付物
- PDF 重渲染：**20 页 / 9 图 / 2,022 KB**，满足 ≤20 页硬约束但**已贴上限**（再加内容必须先精简）；
  文本层泄露复扫 `PDF-LEAK-CLEAN`（输入非空已证）。旧 PDF 18 页 / 8 图。
- ⚠️ **公网副本落后本地**（`app.js`/`chat-window.js` 已改、PDF 已重做）：部署属线上动作，本轮未执行 ⇒
  已登记 07 P0 为下一件，且**不在文档里声称两端一致**。

### Known issue（待老大，非代码）
- GitHub Actions 账户账单/配额未解 ⇒ HEAD 最近 run 仍判 `ENV_BLOCKED`，r28 的 CI 覆盖面修复**至今无法在受理面验证**
  （复算 `python _test/ci_status_check.py`；本轮电池那条红仍是设计如此，不放宽）。
- iCAN 报名名单 PII（五人学号/手机号/邮箱 + 指导教师 ≤2 非成员 + 官网填报登录态）只有老大能给；
  PDF 署名页需在 PII 齐后重渲染。
- 公网部署需凭据与线上确认：本轮改了 `app.js`/`chat-window.js` 与 PDF，**公网仍是旧版**，故不声称两端一致。

> 对标 r29–r30（2026-09-25 第十、十一轮）：**受理面优先** —— 查 CI 真结论，查出"CI 全红"其实是
> GitHub 账户账单导致 runner 从未启动；同时清掉我自己写进聚合器的 3.12-only 语法。外部漂移全为 ★ 抖动。

### Added
- **离线能力的「第二条观测通道」（r31）**：`pwa_offline=0/16` 原本只靠**文件名法**
  （`sw.js|service-worker.js|serviceworker.js|sw.ts`）—— 而 r30 刚证明文件名法会假阴性，对自己如此，对参照仓亦然。
  新增 `offline_signal_class()`（纯函数，读 description+README）把 "offline" 分四类
  `app_shell / local_models_offline / ml_training_offline / none`，**先归因再计数**；台账 `--offline-audit` 跑，
  结果只写快照 `runs[-1].offline_audit` 与复核行，**不参与 `caps` 计数**。实测 16 仓：
  `app_shell=0`、`local_models_offline=1`（Open-LLM-VTuber「run completely offline using local models」，
  桌面自托管形态而非网页壳）、`ml_training_offline=1`（hello-diana/MASCOT 的 **offline DPO 训练** = 误报源）、
  `unverified=0` ⇒ 差异结论从"单观测法 + 手工抽查 1 仓"升级为"双独立通道 + 逐仓点名"。
  判据自证：四类各一合成样本 + 两条反向（训练语境不得判成离线壳 / 真 SW 语境必须判成离线壳）+ 零输入判 `none`；
  两个变异体（恒判 app_shell、恒判 none）实测 `SELFTEST-FAIL rc=1`，还原后 rc=0。
  复算：`python _test/benchmark_metrics.py --selftest` + `python _test/benchmark_metrics.py --offline-audit`
- **`_test/ci_status_check.py`（K1–K4，电池 33 → 35 套件）**：把"CI 红"分成 `CODE_FAIL` / `ENV_BLOCKED` / `PASS`
  三态。ENV 判据 = 全部 job 在 15s 内失败 **且** run 的 ANNOTATIONS 命中账单/配额类措辞 ⇒ rc=2，
  并明写「本轮不得声称 CI 已验」。结论只取 HEAD 那次 run（历史红只作上下文）；在 CI 内部自动 SKIP（自指）。
  自证含两条反向断言：去掉账单措辞必须翻判 CODE；不 SKIP 就 selftest 红。实测三态均正确。
- 离线壳能力的台账自证：`benchmark_metrics.py` 的 self 行现已报 `caps=...,pwa_offline`
  ⇒ "16 个同类都没做的能力我们有"这句话由台账复算，而不是写在报告里自说（r28 的 claim 至此闭环）。
- **`benchmark_metrics.py` 的「盲区点名」（r30）**：能力匹配器只看文件路径，对我们有两类是**假阴性**
  （SSE 写在 `chat.js`/`ChatController.java` 里、文件名不含 sse；浏览器端到端在 `_test/*.py` 里用
  playwright、路径不含 e2e）。新增 `blind_spot_caps()` **读内容取证据**，在 self 行打印
  `盲区点名：e2e_browser,streaming`，但**不计入 `caps`** —— 横向对比仍用同一把尺，给参照仓"读内容"就是双标。
  自证三侧（有证据→点名 / 无证据→空 / 已看见→不重复计数）；三个变异体（恒空 / 恒报 / 不去重）实测都被抓住。
  复算：`python _test/benchmark_metrics.py --selftest` + `python _test/benchmark_metrics.py`

### Fixed
- **演示成片重录（交付物变更，r30）**：旧片画面仍是**情绪后端化之前**的，而"后端引擎 + 同源代理在线"才是最有
  说服力的两点差异 ⇒ 按 07 P0 登记的那件自驱项重录。8 幕 `RECORD-PASS`、`ffprobe` **217.56s**、
  成片 `sha256=fc810f65…`（替换旧 `50e060d1…`）；S3 画面标签实测
  `在线大模型生成 · 逐字流式 · 情绪双路：词典+LLM 一致 → LLM · 情绪:后端 · 1378ms`。
  含一次**真实失败**：第一次把代理写成绝对 URL `http://127.0.0.1:8123/api/chat`，页面在 `localhost:8123`
  ⇒ 跨源且 `/api/chat` 无 CORS 头（curl 带 `Origin` 实测），S3 落进「离线共情模板」被断言拦下 rc=1；
  改**同源相对** `/api/chat` 后通过。教训："同源代理"的同源是 **URL 形状**的属性，不是端口的属性。
  录制环境的切换/还原按 sha256 机器核验（`2521954c…` 前后一致），录后 `public_check`/`live_sync`/`deploy_sync` 全 PASS。
- **聚合器自己是 3.12-only 语法**：r28 给失败明细写的 `print(f"{" " * 25}· {d}")` 依赖 PEP 701，
  本机 3.12 全绿、CI pin 3.11 直接 SyntaxError（30 条判据一条没跑）。改字符串拼接；
  另全仓扫两类 3.11 雷（嵌套同引号 f-string 1 处已修、f-string 花括号内反斜杠 0 处），
  并在 CI 最早一步加 `python -m compileall -q _test`（版本兼容差要以最小失败面暴露）。
- 交付物 `G4`/`G10` 数字随套件数同步（README 声称 35 == 实测 35；CI 恒等式 实跑 32 + 豁免 3 == 35）。

### Known issue（待老大，非代码）
- GitHub Actions 连续 3 次 run 判 `ENV_BLOCKED`：annotations 原文
  "The job was not started because recent account payments have failed or your spending limit needs to be increased."
  ⇒ r28 的 CI 覆盖面修复**至今无法在受理面验证**；本轮不声称已验。

> 对标 r28（2026-09-25 第九轮）：**把对标的"全零"读成机会** —— 只读离线壳 `sw.js` 上线（判据先行），
> 并把判据挂上 CI 真发布路径。外部漂移 3 处全为 ★ 抖动（实质 0）。

### Added
- **只读离线壳 `src/sw.js`**：HTML/JS/CSS network-first、`vendor/`+`assets/` cache-first（缓存名由 vendor 内容指纹钉）、
  `/api/**` 与非 GET 完全不碰缓存、`js/demo-config.js`（本地含密钥）既不预缓存也不写缓存。
- **`_test/offline_shell_check.py`**：A1–A10 静态审计（13 类注入反例）+ R1–R9 运行时，共 14 项；
  其中 **R9 在公网上真断网重载**（"现场 WiFi 挂了还能演五幕"是唯一验收口径）。入电池 ⇒ 31 → **33 套件**。
- **`deploy/xinyu/_headers`**：只钉实测真正缺头的两条（`/index.html` 原本无 Cache-Control 且 308 到 `/`；`/sw.js` 显式 no-cache）。
- **常驻判据 G10**（`repo_config_check.py`）：CI 必须整跑电池且声明豁免，豁免项必须是真实套件（幽灵豁免判红）。

### Changed
- **CI browser-regression job**：由"只跑 `browser_check.py` 一条"改为 `python _test/run_all_suites.py --exclude-llm`
  （runner 无上游密钥 ⇒ 显式豁免 `j2_chat_contract` / `stream_contract` 并点名，恒等式 `实跑+豁免==总数` 自证）。
- `size_budget` 覆盖域扩到 `src` 根目录（`sw.js` 入册 4,814）；`index.html` 预算因注册块上调 9,191→9,936（理由写在该文件行内注释）。

### Fixed
- **删掉一处自己刚写的死代码**：原打算用 Java `CacheHeaderFilter` 统一头策略，实测发现
  `spring.web.resources.cache.period=0` 已对所有静态件给 `no-store`（filter 被资源处理器覆盖）⇒ 过滤器删除，
  也没顺手把 vendor 改长缓存（那是性能主张，不是离线壳前提，做了只会让两端策略分叉）。
- 判据自证三处：① `transferSize` 对被 SW 拦截的请求恒为 0 ⇒ 无判别力，改由 SW 自报 `x-xinyu-src`；
  ② `c.add().catch(()=>{})` 吞掉预缓存失败 ⇒ 留痕 + 新增"清单必须真入缓存 / 页面引用必须在壳里"两条分母断言；
  ③ 间歇红根因是**判据自己的脚手架**（单线程 TCPServer 扛不住 SW 安装期并发）：换 ThreadingHTTPServer 后 3/3 绿，
  再把变量翻回单线程复现 2/3 红，A/B 钉死因果后才敢收工。
- `repo_config --selftest` 的反例条数从手抄（"十一类/十五类"两版都错）改为从代码里数。

### Deployment
- 公网 `54fb9778`（wrangler 回执含 `Uploading _headers`）：`sw.js` 线上 200 / 4,773B / `no-cache`；
  本地 `--exclude-llm` 31/31 rc=0，全量含密钥 **33/33 rc=0**。

> 对标 r27（2026-09-25 第八轮）：判据先行 —— 先给设置面板立行为判据，再切第四刀；外部漂移 2 处全为 ★ 抖动（实质 0）。

### Added
- **`_test/settings_panel_check.py`**（S1–S8 + 五类注入反例）：设置面板此前**没有任何行为判据**，而它是唯一直接碰
  密钥输入框的模块。断言：Key 恒不回显 / 留空保存不洗掉已存 Key / 填了新 Key 则写入 / 流式勾选落盘 /
  取消一字不改 / 徽章随 Key 有无如实翻转 / 全程零 JS 异常。入电池 ⇒ 29 → **31 套件**（含其自证）。
- **能力覆盖率分母证明**（`benchmark_metrics.py::coverage_hits`）：树截断或取数失败的仓**踢出分母并逐条点名原因**，
  首行改打「有效分母 N/16」，恒等式 `usable + blind == 总数` 不成立即 rc=1。起因：`pwa_offline=0/16` 的全零
  需先证"不是没数到"（实测 lobehub 树 `truncated=false` / 20,740 对象 / `sw.js|service-worker.js|sw.ts` 零命中）。

### Changed
- **`src/js/settings.js` 外提**（第四刀，`app.js` 268 → 241 行；复算见 `memory/05`）：三条密钥语义原样随迁，
  徽章刷新改用 `init({onSaved})` 注入，模块不反向依赖编排层。预算同步收紧：app.js 14,777→13,780、新件 3,000。
- 公网重部署 `4f8cd81b`：线上 `settings.js` 与磁盘等字节（2,857B），`LIVE-SYNC-PASS`。

### Fixed
- 校正注：第四刀提交信息写「239 行」，复算实为 **241 行**（把工具回执当文件真值 = 又一次手抄数字）。
  历史不改写，改在正文只写复算命令。

> 对标 r26（2026-09-25 第七轮）：切分第三刀 —— 对话窗口化外提；外部 6 处漂移经分档后**实质仅 2 处**
> （均在 sapphire：pushed 09-25 + release v2.5.0→v2.13.1），其余 4 处是 ★±1 抖动（lobehub 甚至倒退）。
> 能力矩阵/CI/docs 无变化 ⇒ 七维无翻牌。本轮另一条主线是**把"验证动作本身"纳入判据**。

### Changed
- **`src/js/chat-window.js` 外提**（`app.js` 351 → 268 行，行为零改动）：对外只留 `init/push/update/setTag/toBottom`，
  `quota` 临时抬高、`trimmedBuf` 缓存、`.log-fold` 提示条等原实现约束留在模块内。与前两刀不同，
  这块**被对话主流程调用**（提交 / 流式覆写 / 历史恢复），所以接口目标是"关住 DOM 细节"而非"搬出状态"。
  判据 = `ux_guards_check.py` U2a–U2f（浏览器实跑）21 项全绿。
- 预算**收紧**而非放宽：`app.js` 23,979 → 14,777（实测 +5%），新件登记 5,845；`size_budget` 17 → 18 文件。
- 漂移台账分档：`benchmark_metrics.py` 新增 `classify_drift`，★ 数入"抖动档"（单点差值含倒退不作趋势证据），
  `pushed_at`/`latest_release`/`caps`/`docs`/CI 全算"实质档"（可行动）。selftest 两侧都验。

### Fixed
- **同族坑第五次复发，这次骗的是验证动作本身**：给上面那条分档判据做负控制时 `import benchmark_metrics`
  = 先跑一遍 16 仓联网采集再 `exit 0` ⇒ **反例根本没执行却看起来像通过**。根因是裸 `sys.exit(main())`
  缺 `if __name__ == "__main__":` 守卫；全仓扫出 3 个（`benchmark_metrics` / `live_sync_check` /
  `run_all_suites`，后者 import 一次等于 29 套件全量重跑），三个全补守卫。
- 新增常驻判据 **G9**（`repo_config_check.py`）：`_test/*.py` 必须 import-safe；`--selftest` 扩到**十一类**，
  含两条反向样本（"有守卫不得报红"、"函数体内缩进的 sys.exit 不算违规"）防判据恒假。
- 公网重部署 `61ec115b`：`chat-window.js` 线上 200 且与磁盘等字节，`LIVE-SYNC-PASS` / `PUBLIC-ONLINE-ALL-PASS`。
- 首次 `wrangler pages deploy` 报 `fetch failed`（未静默跳过，重试第二次成功）；线上主域名响应曾达 15.7s，
  已记为环境抖动而非代码结论。

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
