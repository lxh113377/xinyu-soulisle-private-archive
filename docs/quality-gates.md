# 判据体系明细（从 README 迁出，r39 体量体检）

> README 是每轮注入件，超 16,384B 预算即算**每轮重复付费**；本节明细改放这里，README 留指针。
> 内容逐字迁自 README「## ✅ 验证」一节，未改写（取证见当日会话日志）。


```powershell
python _test/run_all_suites.py           # ★ 全量电池（套件条数以 `--list` 实算为准，本文件不抄数；逐条直取 rc，聚合不掩盖单项失败）
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
python _test/clean_clone_check.py         # r43 干净克隆可跑性：从 HEAD 克隆到临时目录再跑，未知报错即红（已登记缺口须计数命中，0 命中要销账）
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
python _test/ux_guards_check.py          # TTS 朗读 / 对话窗口化 / 响应式与粒子降档（逐项 21 判据）
python _test/size_budget_check.py        # 首屏体积预算 + 「新文件必须登记」覆盖判据（漏登记即红）
python _test/vendor_freshness_check.py   # vendor 完整性哈希 + 版本对账；--check-upstream 报上游漂移
python _test/benchmark_metrics.py        # 对标源数据台账（16 仓指标 + 与上次快照逐字段漂移）；联网采集，人工轮次跑
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
python _test/perf_baseline_check.py      # 性能基线判据（r40）：把"性能表现"这一维从连续几轮的「未实测」变成有数、有预算、有回归棘轮的一格
python _test/disclaimer_forensics_lint.py --all  # 边界声明取证判据（M5⑫ 执行器）：免责声明不得顶替一整维的测量（r57 由 CI 判红实证它在管）
python _test/plan_pdf_coverage_check.py  # 应用方案 PDF 的九项覆盖判据（iCAN 硬截止前的交付面自证）
python _test/settings_panel_check.py     # 设置面板行为守卫（r27，第四刀的前置判据）
python _test/offline_shell_check.py      # 只读离线壳（sw.js）+ 缓存头策略判据（r28）
python _test/pdf_leak_scan.py            # PDF 文本层泄露复扫（R242：二进制产物须抽文本后再扫）
python _test/tracked_secret_scan.py      # 跟踪文件密钥形态扫描（r35）—— 与 CI 密钥门禁同一把尺，且本地也跑
python _test/remote_tree_audit.py        # 远端树洁净度审计（r37）：评委看得见的是远端 main 的文件树，不是本机工作树
python _test/mobile_check.py             # 移动端与触屏可达性判据（r47）—— 量真实几何，不量"有没有写 @media"
python _test/release_governance_check.py # 发布治理判据（r45，双通道同尺）—— 盯「版本在动、内容没切版」这一族
python _test/j2_chat_contract.py         # J2 契约验收：POST /api/chat 与 v1 1:1，前端零代码改动即可切到 Spring Boot
python _test/j4_memory_check.py          # J4 持久化验验收：记忆从 localStorage 迁到服务端数据库（并保留本地降级）
python _test/j4_remote_down_check.py     # J4 熔断对照：服务端没有 /api/memory 时，远端记忆必须"试一次就闭嘴"
python _test/online_check.py             # 在线模式全链路回归：徽章 + 双路情绪探针 + 在线对话 + 危机拦截 + console 0 报错
python _test/public_check.py             # 公网版验收：评委打开即在线AI（走服务端代理），密钥零暴露，console 0
node _test/emotion_eval.js               # 情绪引擎评测：词典层准确率（技术实现维度的可复现数字）
# ↓ 同批第二刀：G16 首跑又抓到 10 条（r35–r50 落地的判据/探针/通道件，同样从未进本文明细）
python _test/ci_watch.py                 # push 后的 CI 回执看守（把"看 CI"从人记得住，变成一条命令必跑）
python _test/lightshow_check.py          # 一键点亮验收：清屏（UI 让位）+ 六色各自可见 + 铺得够满够散 + 播完不自动跳回
python _test/pixel_dual_check.py         # 星雾「是不是真的变彩色了」——像素级回归（判断据不看内部数组）
python _test/server_preflight.py         # 被测服务前置探针（r35）—— 把"服务没起"与"代码有缺陷"分开报
python _test/voice_check.py              # 语音输入（Web Speech API）实测：只认真实发生过的事实（API 在否/start 真被调用/监听态出现过/能恢复）
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
```

> 前置：多数判据需 fat jar 起在 8123（`java -jar server/target/soulisle-server.jar --server.port=8123`，
> 工作目录 = 项目根，`DEEPSEEK_KEY` 走进程环境）。⚠️ 改 `src/` 后**必须重启 jar** 再验（进程内静态资源有缓存）。

GitHub Actions 四条门禁（`.github/workflows/ci.yml`）：同步守卫+评测+策略表+体积+**vendor 供给链**+密钥扫描、Java 构建+**词表一致性红线**（此前只写在 `memory/AGENTS.md` 靠人记，现已机器化）、浏览器回归（runner 无 GPU，强制 SwiftShader）、公网新鲜度。
四条 job 都挂在 `main` push 上真跑；浏览器 job 首轮就抓到本机看不到的真实缺陷：`src/js/demo-config.js` 被 gitignore，全新 clone 下 `<script>` 静态引它 → 首屏 3 个 404 打破「console 0 报错」。修法＝CI 自动用公网零密钥 stub 补占位（本地按 `CONTRIBUTING.md` 第一步手工补一次）。

**受理面状态以远端为准，不在本文件写死**：`python _test/ci_status_check.py`（HEAD 最近一次 run 三态分类：PASS / CODE_FAIL / ENV_BLOCKED）。r35（2026-09-26）实测到一次"本机 37 条全绿、CI 两条 job 真红"的分叉，三条根因与修法见 `交付物/对标分析报告-2026-09-26.md` §2；同类分叉已封成常驻判据（密钥扫描两侧同源 + `voice_selftest` + settings 落盘完成态等待）。

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
