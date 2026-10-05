# -*- coding: utf-8 -*-
"""全量回归电池：逐套件直取 rc，聚合零掩盖（audit-runner-safe-agents 范式：每项独立记录，不看 any）

版本: V1.41.0（2026-09-27 r41）——两条新机制都在本版落地：
  · `fold_detail()`：判据 rc≠0 时除"含判据词的行"外，还带出其后的 `-` 续行与 stderr 末两行
    （实证动因：`voice` 判红时收口面只剩一行 `VOICE-FAIL`，原因行没有 token 就被折叠掉）；
  · 整跑并发锁（`acquire_lock`/`lock_state`，TTL 1800s）：电池不可重入，并跑的第二条一律
    `rc=2 未验`——不给绿，也不产出一条无法归因的红。两者均由 `--selftest` 双向自证（11 类桩）。
"""
import os
import subprocess, sys, io, re, time, json, shutil, atexit
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8123"
# 判定行形状：各套件统一以 <NAME>-PASS / -FAIL / -CLEAN / UNVERIFIED 收尾
VERDICT_RE = re.compile(r"(?:PASS|FAIL|CLEAN|UNVERIFIED|OK)\b")

# 并发锁 TTL（秒）：整跑一遍实测约 10 分钟，留 3 倍余量；被 kill 掉的运行靠它自愈。
LOCK_TTL = 1800

# r70：每套件耗时的**全量**台账。动因是 r69 自己踩的形状 —— 它记了耗时却只把 top5 印到收口行，
# 一轮结束就只剩"mobile=123.5 / 合计 549s"两个数，「该按什么分桶并行」这个问题依旧没有读数。
TIMING_LEDGER = ROOT / "交付物" / "对标数据" / "battery-timing.json"

SUITES = [
    # 前置探针放第一条：r35 实测 jar 中途掉线一次报 5 条红，逐条归因花了三轮命令。
    ("preflight", [sys.executable, "_test/server_preflight.py"]),
    # r40：性能面从"未实测"变成有数有棘轮。阈值按本机三轮实测 p95 放宽 ~16-25 倍，
    # 只防塌方级退化（直读变落库 / 线程池打满 / 危机路径开始打 LLM），不防抖动 ⇒ 才有资格进阻断链。
    ("perf_baseline", [sys.executable, "_test/perf_baseline_check.py", BASE]),
    ("perf_baseline_selftest", [sys.executable, "_test/perf_baseline_check.py", "--selftest"]),
    # r40c：报告里的「不可比 / 受限于 / 仅保证」类边界结论必须自带取证口径（M5⑫ 的执行器）。
    # 首跑就在自己的报告里点名一处 r35 遗留（无可比口径 无取证），修文案后才转绿 ⇒ 判据非装饰。
    ("disclaimer_forensics", [sys.executable, "_test/disclaimer_forensics_lint.py", "--all"]),  # r41: 分母改从目录现读
    ("disclaimer_forensics_selftest", [sys.executable, "_test/disclaimer_forensics_lint.py", "--selftest"]),
    # r40c：push 后的 CI 看守。只把**纯判定桩**接进阻断链（真跑要联网查 gh，不属回归面）。
    ("ci_watch_selftest", [sys.executable, "_test/ci_watch.py", "--selftest"]),
    # r41：整跑不可重入（并跑互踩出无法归因的红，本轮实测两次）⇒ 锁的判定桩入链
    ("battery_lock_selftest", [sys.executable, "_test/run_all_suites.py", "--selftest"]),
    # r40d：交付物 PDF 的「官方九项齐全」从人眼对照升级为机器断言（分母取自大纲，不手抄）。
    ("plan_pdf_coverage", [sys.executable, "_test/plan_pdf_coverage_check.py"]),
    ("plan_pdf_coverage_selftest", [sys.executable, "_test/plan_pdf_coverage_check.py", "--selftest"]),
    ("deploy_sync", [sys.executable, "_test/deploy_sync_check.py"]),
    # r36：行尾确定性 —— 让「逐字节 / SHA256 / 字节预算」类主张在他人 clone 上也成立
    ("eol_parity", [sys.executable, "_test/eol_parity_check.py"]),
    ("eol_parity_selftest", [sys.executable, "_test/eol_parity_check.py", "--selftest"]),
    ("size_budget", [sys.executable, "_test/size_budget_check.py"]),
    ("size_budget_selftest", [sys.executable, "_test/size_budget_check.py", "--selftest"]),
    ("emotion_wiring", [sys.executable, "_test/emotion_wiring_check.py"]),
    ("emotion_wiring_selftest", [sys.executable, "_test/emotion_wiring_check.py", "--selftest"]),
    ("vendor_freshness", [sys.executable, "_test/vendor_freshness_check.py"]),
    ("vendor_freshness_selftest", [sys.executable, "_test/vendor_freshness_check.py", "--selftest"]),
    ("benchmark_selftest", [sys.executable, "_test/benchmark_metrics.py", "--selftest"]),
    # r82 建议5（取数入口前置自证）：peers 尺全集必须「解析得动 + 归属清楚」，
    # 否则 r81 那一形（坏尺起不来 ⇒ 拿尺的人先撞到 SyntaxError 而不是「红在谁身上」）会复发。
    ("measure_entry", [sys.executable, "_test/measure_entry.py"]),
    ("measure_entry_selftest", [sys.executable, "_test/measure_entry.py", "--selftest"]),
    # r41：对标测试资产面量出 in-build 单测 0/16 vs peers 9/16；探针本体不入电池（16 仓 API 不划算，
    # 承 r37 口径），但它的**匹配器自证**纯本地零网络，进阻断链盯住"把依赖目录当用例"这类灌水。
    ("testasset_selftest", [sys.executable, "_test/peer_test_asset_probe.py", "--selftest"]),
    # r42：无障碍面（对标探针不入链——16 仓 × 4 次 API，承 r37 探针不入电池口径；只入其判定桩）
    ("a11y_probe_selftest", [sys.executable, "_test/peer_a11y_probe.py", "--selftest"]),
    # r43：可复现面（16 仓 × ~4 次 API 的探针不入链，承 r37 口径；只入判定桩）
    ("repro_probe_selftest", [sys.executable, "_test/peer_repro_probe.py", "--selftest"]),
    ("api_contract", [sys.executable, "_test/api_contract_check.py"]),
    ("api_contract_selftest", [sys.executable, "_test/api_contract_check.py", "--selftest"]),
    ("patch_apply_selftest", [sys.executable, "_test/patch_apply.py", "--selftest"]),
    ("settings_panel", [sys.executable, "_test/settings_panel_check.py"]),
    ("settings_panel_selftest", [sys.executable, "_test/settings_panel_check.py", "--selftest"]),
    ("offline_shell", [sys.executable, "_test/offline_shell_check.py"]),
    ("offline_shell_selftest", [sys.executable, "_test/offline_shell_check.py", "--selftest"]),
    ("pdf_leak_scan", [sys.executable, "_test/pdf_leak_scan.py"]),
    ("pdf_leak_selftest", [sys.executable, "_test/pdf_leak_scan.py", "--selftest"]),
    # r35：CI 的密钥门禁原先内联在 ci.yml，本地扫不到 ⇒ "被跟踪文件含密钥形态"只有 CI 红。
    # 现在两侧共用这一条判据（正则只实现一处），本地也进电池。
    ("tracked_secret", [sys.executable, "_test/tracked_secret_scan.py"]),
    ("tracked_secret_selftest", [sys.executable, "_test/tracked_secret_scan.py", "--selftest"]),
    # r37：本机 `git ls-files` 干净 ≠ **远端树**干净（.gitignore 不撤销已推送的东西，
    # 而评委看到的是远端）⇒ 另起一条扫 origin 默认分支的文件树
    ("remote_tree", [sys.executable, "_test/remote_tree_audit.py"]),
    ("remote_tree_selftest", [sys.executable, "_test/remote_tree_audit.py", "--selftest"]),
    ("ci_status", [sys.executable, "_test/ci_status_check.py"]),
    ("ci_status_selftest", [sys.executable, "_test/ci_status_check.py", "--selftest"]),
    ("repo_config", [sys.executable, "_test/repo_config_check.py"]),
    ("repo_config_selftest", [sys.executable, "_test/repo_config_check.py", "--selftest"]),
    ("engine_consistency", [sys.executable, "_test/engine_consistency_check.py"]),
    # r41：in-build 门禁的守卫。T4 专门盯"CI 构建步有没有被加上 -DskipTests"——
    # 加了的话 java-build 照样全绿，而构建期单测已经静默不存在（本地看永远是"CI 通过"）。
    ("java_test_guard", [sys.executable, "_test/java_test_guard.py"]),
    ("java_test_guard_selftest", [sys.executable, "_test/java_test_guard.py", "--selftest"]),
    ("strategy", [sys.executable, "_test/strategy_check.py"]),
    ("strategy_selftest", [sys.executable, "_test/strategy_check.py", "--selftest"]),
    ("ux_guards", [sys.executable, "_test/ux_guards_check.py"]),
    # r42：无障碍从「没人量过」变成常驻阻断面。12 个审计单元=6 状态 x 2 主题，
    # 规则集必须含 experimental（默认集看不见 label-content-name-mismatch，首跑即被这一点骗过）。
    ("a11y", [sys.executable, "_test/a11y_check.py"]),
    ("a11y_selftest", [sys.executable, "_test/a11y_check.py", "--selftest"]),
    # r44：数据主体权利（披露随模式翻转 / 删除有回执并复核归零 / 导出两份与计数对齐）
    ("data_rights", [sys.executable, "_test/data_rights_check.py"]),
    ("data_rights_selftest", [sys.executable, "_test/data_rights_check.py", "--selftest"]),
    ("data_rights_probe_selftest", [sys.executable, "_test/peer_data_rights_probe.py", "--selftest"]),
    # r47：移动端与触屏可达性。测的是**真实几何**（视口溢出 / 触控目标尺寸 / 输入字号 / 禁缩放），
    # 不是"有没有写 @media"。⚠️ 必须 has_touch=True，否则 (pointer:coarse) 不匹配 = 空跑一轮。
    ("mobile", [sys.executable, "_test/mobile_check.py"]),
    ("mobile_selftest", [sys.executable, "_test/mobile_check.py", "--selftest"]),
    ("mobile_peer_selftest", [sys.executable, "_test/peer_mobile_probe.py", "--selftest"]),
    # r50：协作治理与健康度探针的判据自证。核心形状是"声明面 ≠ 行为面"——
    # 实测教训：org 级 dependabot 配置对仓内 tree 不可见（lobehub 开 30 PR 却无 dependabot.yml），
    # 而 search 端点受 secondary rate limit 影响会把 NA 塌缩成"0 家真跑过"的假结论（17/17 里含该反例）。
    ("community_probe_selftest", [sys.executable, "_test/peer_community_probe.py", "--selftest"]),
    # r51：故障注入。把上游打挂（500/非JSON/断连/黑洞挂起）看界面说不说真话。
    # 修前实测：徽章在四类故障下仍写「● 在线 AI」（气泡却写"大模型暂不可用"）；挂起型 60.6s 才兜底。
    ("fault_injection", [sys.executable, "_test/fault_injection_check.py"]),
    ("fault_injection_selftest", [sys.executable, "_test/fault_injection_check.py", "--selftest"]),
    # r51：故障可见性对标的探针自证。边界写死在判据里——故障注入无法对他人站点实施，
    # 所以这一面只取「结构 + 声明」两类证据（监控集成/错误页/排障文档），恒等式含 NA 与 out_of_scope。
    ("fault_peer_selftest", [sys.executable, "_test/peer_fault_probe.py", "--selftest"]),
    # r52：长期记忆召回。十三份对标把「记忆系统」记成存在性 ✅（有表、写得进去），
    # 从没量过"落库的记忆有没有回到发给模型的那条 messages"。实测导出面零召回项 ⇒ 只写不读。
    # 判据取数面 = 拦 /api/chat 读 request.post_data（真流量出口），R4 是反向腿（清库后必须消失），
    # 缺反向腿的判据可以靠"永远注入一段常量"骗绿——所以 selftest 里专门放了这条反例。
    ("memory_recall", [sys.executable, "_test/memory_recall_check.py"]),
    ("memory_recall_selftest", [sys.executable, "_test/memory_recall_check.py", "--selftest"]),
    # r52：记忆/上下文面对标探针的判据自证。三通道里"引用边"只认正向回执，
    # none-in-sample / NA 两态都不构成"该仓没做回灌"；歧义形状（storage 含 rag、
    # React createContext、memory-leak 测试件、GPU memory）各配一条反例。
    ("memory_peer_selftest", [sys.executable, "_test/peer_memory_probe.py", "--selftest"]),
    # r52：README「出错了怎么办」段 ⇄ 代码状态标签**双向**对账。补文档不等于补上——
    # 首跑就以 T2 抓到我自己写了一个代码里不存在的徽章文案（`● 已离线`），以 T1 逼出
    # 一个真实但没被文档化的第四态（`● 网络不可用（配置为在线）`）。
    ("readme_troubleshooting", [sys.executable, "_test/readme_troubleshooting_check.py"]),
    ("readme_troubleshooting_selftest", [sys.executable, "_test/readme_troubleshooting_check.py", "--selftest"]),
    # r53：上下文窗口预算与截断损失。十四份报告从没量过"本机攒下的对话模型这一轮真看到了多少"，
    # 实测 14 轮里 16 条消息对模型永久不可见且无任何补偿 ⇒ 概要注意送达 + 条数按判据独立算法对账
    # （不让产品报给自己的数字自比）。修前该套件以 X2 判红，是真拦住过东西的判据。
    ("context_budget", [sys.executable, "_test/context_budget_check.py"]),
    ("context_budget_selftest", [sys.executable, "_test/context_budget_check.py", "--selftest"]),
    # r54：安全响应头/CSP。取数面是「把同一份 _headers 在本地按 Pages 语义回放，再拿响应回来对账」
    # —— 线上一份声明是否真生效，只有在真施加过头的服务器上才测得出来；H5 那条拦截探针负责证明
    # "夹具真的在拦"，否则整套绿色都来自没生效的 CSP（同族：判具坏了长得像产品好了）。
    ("headers_csp", [sys.executable, "_test/headers_csp_check.py", "--local"]),
    ("headers_csp_selftest", [sys.executable, "_test/headers_csp_check.py", "--selftest"]),
    # r54：安全响应头对标探针的判据自证。核心陷阱是裸子串：`csp` 是 .csproj 的子串、
    # `helmet` 在散文里满地都是 ⇒ 路径与依赖两条通道都必须锚定（反例②③各盯一条）。
    ("sec_headers_peer_selftest", [sys.executable, "_test/peer_sec_headers_probe.py", "--selftest"]),
    # r45：发布/版本治理对标探针的判据自证（semver 合流 / 发布滞后 / CHANGELOG 三段，含小数天反例）
    ("release_probe_selftest", [sys.executable, "_test/peer_release_probe.py", "--selftest"]),
    # r46：许可与供给链对标探针的判据自证（LICENSE 类件 / 归属类件 / vendored 目录三个分类器，
    # 含"任意后缀会把 notice.html 当成归属件"这条被反例④当场抓到的宽匹配）
    ("license_probe_selftest", [sys.executable, "_test/peer_license_probe.py", "--selftest"]),
    # r45：发布治理常驻判据。R1 盯「距上次切版的 feat 增量」，R2 把 CHANGELOG ⇄ git 增量做成双向对账
    # （首跑就以 feats=11/上限 5 判红，并抓出 r41/r42/r43 三轮漏记 —— 旧轮次的 bullet 会掩盖计数型判据）。
    ("release_governance", [sys.executable, "_test/release_governance_check.py"]),
    ("release_governance_selftest", [sys.executable, "_test/release_governance_check.py", "--selftest"]),
    # r43：干净克隆可跑性——从 **HEAD** 克隆到临时目录再跑，证明"交出去的那份"能跑，
    # 而不是"我这台机器上恰好有一份 .gitignore 掉的文件"那一版能跑。
    ("clean_clone", [sys.executable, "_test/clean_clone_check.py"]),
    ("clean_clone_selftest", [sys.executable, "_test/clean_clone_check.py", "--selftest"]),
    ("j2_chat_contract", [sys.executable, "_test/j2_chat_contract.py"]),
    ("j4_memory", [sys.executable, "_test/j4_memory_check.py"]),
    ("j4_remote_down", [sys.executable, "_test/j4_remote_down_check.py"]),
    ("stream_contract", [sys.executable, "_test/stream_contract.py"]),
    # r38：输入侧护栏必须"真的在拦"（注入 6 例点名 + 正常 6 例不误伤，含 2 例近似误伤）
    ("safety_guard", [sys.executable, "_test/safety_guard_check.py", BASE]),
    ("safety_guard_selftest", [sys.executable, "_test/safety_guard_check.py", "--selftest"]),
    ("voice", [sys.executable, "_test/voice_check.py", BASE]),
    # r35：voice 的"CI 无麦克风 ⇒ SKIP"降级必须是纯函数且带边界反例，否则降级会吞掉真缺陷
    ("voice_selftest", [sys.executable, "_test/voice_check.py", "--selftest"]),
    ("browser_check", [sys.executable, "_test/browser_check.py"]),
    ("pixel_dual", [sys.executable, "_test/pixel_dual_check.py"]),
    ("lightshow", [sys.executable, "_test/lightshow_check.py"]),
    ("online_check", [sys.executable, "_test/online_check.py"]),
    ("public_check", [sys.executable, "_test/public_check.py"]),
    ("live_sync", [sys.executable, "_test/live_sync_check.py"]),
    # r84（R83-01 闭环）：备用线 `/xinyu/` 也要有人看着。r83 那次是**人眼 curl** 发现根 index.html
    # 被同环境另一项目覆盖掉（200、样式还在、只有标题换人）⇒ 单盯 pages.dev 等于把备用线交给运气。
    # 复用同一条尺（BASE 由 argv[1] 传入），不另写第二份对账逻辑。
    ("live_sync_alt", [sys.executable, "_test/live_sync_check.py",
                       "https://qwer-d4gf2r76o8829463b-1458054906.tcloudbaseapp.com/xinyu/"]),
    # r86：备用线从「如实标注的离线降级」改判**真实在线**（前端跨域调 pages.dev 函数，
    # 函数侧 CORS 白名单只放行自家来源）。这条尺真开浏览器发一条消息，标签含
    # 「在线大模型生成」才算过——防止 stub 被改回已死的 service 域名而无人知晓。
    ("backup_online", [sys.executable, "_test/backup_online_check.py"]),
    ("emotion_eval_js", ["node", "_test/emotion_eval.js"]),
    # r58 质量工程面：JS 侧从"0 个单元测试"变成有常驻执行位（node --test + 跨 realm 归一）
    ("js_unit", [sys.executable, "_test/js_unit_check.py"]),
    ("js_unit_selftest", [sys.executable, "_test/js_unit_check.py", "--selftest"]),
    ("quality_peer_selftest", [sys.executable, "_test/peer_quality_tooling_probe.py", "--selftest"]),
    # r59 交付物清单面：提交包是「要交出去的东西」，此前 91 套件里没有任何一条判据引用过成片、
    # 清单本体、渲染脚本 —— 09-28 00:19 实测 7 个被跟踪交付件从工作树消失且零告警。
    ("deliverable_inventory", [sys.executable, "_test/deliverable_inventory_check.py"]),
    ("deliverable_inventory_selftest", [sys.executable, "_test/deliverable_inventory_check.py", "--selftest"]),
    # r59 函数出口面：r57 用一次手工 curl 证的「四条出口都回头」，本轮换成 node 假 fetch 驱动
    # 真函数模块 —— 6 条出口（含 stream=true 但上游报错的折返腿）离线可重跑，摘头即翻红。
    ("api_egress_headers", [sys.executable, "_test/api_egress_headers_check.py"]),
    ("api_egress_headers_selftest", [sys.executable, "_test/api_egress_headers_check.py", "--selftest"]),
    # r60 持久层异常面：memory-store 8 处 try/catch 从没被走过一遍（47 条判据零覆盖）。
    # 五种存储故障 × 四条断言，F4 那条当场抓出"清除后界面计数不刷新"的真缺陷。
    # r67：JS 语法面从"没人量"变成有守卫。加它不是因为 peers 有 lint（实测仅 2/16），
    # 而是因为此前 src/js 的 parse 错只能被浏览器判据间接发现，报出来是"断言超时"而不是文件名。
    ("js_syntax", [sys.executable, "_test/js_syntax_check.py"]),
    ("js_syntax_selftest", [sys.executable, "_test/js_syntax_check.py", "--selftest"]),
    ("storage_resilience", [sys.executable, "_test/storage_resilience_check.py"]),
    ("storage_resilience_selftest", [sys.executable, "_test/storage_resilience_check.py", "--selftest"]),
    # r70 资源普查：把"该按什么分桶并行"从报告里的一句话变成有分母有恒等式的在册读数。
    # 分类按目标脚本**源码证据**判（碰 8123 / 自绑端口 / 起浏览器 / 出公网），不维护名字登记表，
    # 否则新加一条套件忘了登记就会被判成"可并行"——那比没有普查更坏。
    ("suite_census", [sys.executable, "_test/suite_resource_census.py"]),
    ("suite_census_selftest", [sys.executable, "_test/suite_resource_census.py", "--selftest"]),
    # r83：交付面在位闸的接线回执。入库件在位那条腿 r82 就补上了，但它只在电池/CI 跑，
    # 而丢失发生在两次提交之间 ⇒ 本轮把 `_test/hooks/pre-commit` 装上，本件盯「装没装、装的是不是源」。
    ("hook_wiring", [sys.executable, "_test/hook_wiring_check.py"]),
    ("hook_wiring_selftest", [sys.executable, "_test/hook_wiring_check.py", "--selftest"]),
    # r89 作品名门面：r86 声称"全线改名 MindIsle"，而本轮实测 16 处显示名仍挂旧名（README/docs/LICENSE…）。
    # 改名是**决定**而不是**一次性动作** ⇒ 要有尺盯着门面，否则下一轮 sync/手写又把旧名抄回来。
    ("brand_consistency", [sys.executable, "_test/brand_consistency_check.py"]),
    ("brand_consistency_selftest", [sys.executable, "_test/brand_consistency_check.py", "--selftest"]),
    # r84（R77-01 包装器侧）：后台测量的真退出码必须由**被包对象自己**写进日志尾行，
    # 调度层的 `completed (exit code 0)` 不算数（r82/r83 两次一手代价）。本腿自证它会转发非零。
    ("run_logged_selftest", [sys.executable, "_test/run_logged.py", "--selftest"]),
    # r91 性能接线：对标尺 doc_perf 的 ci_perf_step / published_numbers 两格全池 0/16，r91 把性能判据
    # 接进 .github/workflows/perf-baseline.yml、把实测数字写进 README 让两格翻真。翻真即开始漂移：
    # workflow 可以空、可以起了 jar 不等 health（恒未验的假门）、README 数字可以手写 ⇒ 五条接线常驻。
    ("ci_perf_wiring", [sys.executable, "_test/ci_perf_wiring_check.py"]),
    ("ci_perf_wiring_selftest", [sys.executable, "_test/ci_perf_wiring_check.py", "--selftest"]),
    # r93 对标轮改进项 #4：对标 opensoul 的 `pnpm check:loc`（文件 ≤2000 行 / 函数 ≤150 行）。
    # 本项目已有更严的既有约束（size_budget 逐文件字节预算、行为 Core P0.8 函数 ≤50 行），
    # 故本门**只登记读数不阻断**（report-only）：先把「行数/函数长」变成在册数字，
    # 等超限清零再切 --enforce 并挂 CI 步。若现在就阻断，等于用一把更松的尺去卡已经在位的纪律。
    ("loc_guard", [sys.executable, "_test/loc_guard_check.py", "--enforce"]),
    ("loc_guard_selftest", [sys.executable, "_test/loc_guard_check.py", "--selftest"]),
    # r94 类扫发现、r95 接线：「印 FAIL 门面行却无非零退出路径」这一族已发生两次（r93 j2、r94 j4）。
    # 修例不修类 ⇒ 常驻判据。静态零网络零浏览器，可进任意档；电池按 rc 记账，本件正是给 rc 记账本身兜底。
    ("verdict_exit_parity", [sys.executable, "_test/verdict_exit_parity_check.py"]),
    ("verdict_exit_parity_selftest", [sys.executable, "_test/verdict_exit_parity_check.py", "--selftest"]),
    # r95：「CI 全绿契约」的**结构性**门。它必须同时进电池和契约自身 blocking ——
    #   契约第一条就是「契约是否入库」，那正是 greencheck/pre-push 能不能生效的前提，
    #   门必须站在门里面；只放电池里则 pre-push 恒放行时无人知情。
    #   静态零网络零浏览器。注意本件**不调用 greencheck run**（那会递归）。
    ("ci_contract", [sys.executable, "_test/ci_contract_check.py"]),
    ("ci_contract_selftest", [sys.executable, "_test/ci_contract_check.py", "--selftest"]),
    # r93 改进项 #2/#3：把「测试与可复现性」「零构建成本-收益」两个新增维度变成可复算读数
    # （只读本地台账 + git HEAD 面，零网络；缺源判 rc=2 不塌缩成 0）。
    ("bench_rollup", [sys.executable, "_test/bench_rollup.py"]),
    ("bench_rollup_selftest", [sys.executable, "_test/bench_rollup.py", "--selftest"]),
    # r96：对标台账的**龄期**尺。立因是一手实测——r95 报告 §1 维度 1/5 写着「16 仓同址尺」，
    #   而底层 peer 台账按文件名日期有 12/15 族已 8–9 天没重采（契约自己声明 refresh_days=7）。
    #   此前没有任何一把尺盯台账的龄，所以「现测」二字没人能对账。静态零网络，进契约 blocking。
    ("ledger_age", [sys.executable, "_test/ledger_age_check.py"]),
    ("ledger_age_selftest", [sys.executable, "_test/ledger_age_check.py", "--selftest"]),
    # r96：三个探针的离线桩入链。r95 报告 §2.1 批评契约「列了但没人跑」，而本仓自己就有三个
    #   探针**零接线**（SUITES 引用数 0）——含 r95 新立的那把尺。桩是纯本地的，网络面承 r37 口径仍不入电池。
    ("hygiene_probe_selftest", [sys.executable, "_test/peer_hygiene_probe.py", "--selftest"]),
    ("capsafe_probe_selftest", [sys.executable, "_test/peer_capability_safety_probe.py", "--selftest"]),
    ("maintenance_probe_selftest", [sys.executable, "_test/peer_maintenance_probe.py", "--selftest"]),
    # r96：浏览器面的「声明 ⇄ 实际用了哪台引擎」门。立因是实测：本机受管 chromium 版本不匹配
    #   （playwright 1.60.0 要 1223，缓存只有 1228/1243），32 个套件各自回退系统 Edge，
    #   而**没有任何一处打印过它用了什么** ⇒ "本地浏览器套件全绿"不可归因（CI 面是另一台浏览器）。
    #   静态档零网络零浏览器进电池；`--machine` 档挂 CI 的 browser-regression job（那里拿到受管
    #   chromium，两侧读数变成两行可对账）。E2 是棘轮：未接入统一入口数只降不升。
    ("browser_engine_declare", [sys.executable, "_test/browser_engine_declare_check.py"]),
    ("browser_engine_declare_selftest",
     [sys.executable, "_test/browser_engine_declare_check.py", "--selftest"]),
]

# 需要真实上游密钥的套件：本地默认跑（回归环境契约要求 DEEPSEEK_KEY 在进程环境里），
# CI runner 上没有密钥 ⇒ 只能显式豁免，且豁免必须被 G10 复核（见 repo_config_check.py）
# 需要真实上游密钥的三条：本地默认跑（回归环境契约要求 DEEPSEEK_KEY 在进程环境里），
# CI runner 上没有密钥 ⇒ 只能显式豁免，且豁免必须被 G10 复核。
# online_check 也在其中：它断言的就是「对话走了在线模型」，无密钥时该断言必然红 ——
# 放宽它等于把这条判据作废（r28 CI 等效复现实测：它在无密钥环境报 6 条 500，
# 那 500 是契约内响应，但"必须出现 在线大模型生成"这一条本就不可能在无密钥环境成立）。
LLM_SUITES = {"j2_chat_contract", "stream_contract", "online_check"}

# r22 加：`--only <子串>` / `--slice <起> <止>` 分段取数。
# ⚠️ 本版第一稿是**死代码**（先滤掉 "--" 开头的参数再判 args[0] == "--slice"，永不命中），
#    跑 "--slice 0 14" 却把 28 条全跑了个遍 —— "配了开关但开关没生效"正是本轮 repo_config 判据要防的那类事，
#    结果自己又踩了一次。故此处直接按 sys.argv 原样解析，并由 --list 提供可复核的"过滤后到底剩几条"。
USAGE = """run_all_suites.py — 全量回归电池（SUITES 是条数唯一真相源）
  --list             只打印套件总数（供别的判据对账）
  --exclude-llm      跳过需要真实上游密钥的套件（CI 用；豁免条数由恒等式自证）
  --only <子串>      只跑名字含该子串的套件
  --slice <起> <止>  按下标分段取数（长电池分段跑，避免撞调用方超时）
  --selftest         只验并发锁判定桩（零网络、零套件）
  -h, --help         本说明
未知开关一律拒（rc=2）：开关打错字若被静默忽略，会把"子集全绿"印成"全量全绿"。
整跑不可重入：并发的第二条一律 rc=2 未验（r41 实测并跑会互踩出无法归因的红）。
自管服务（r82）：8123 没人起时自己起 fat jar、等到 /api/health=UP 再跑，退出经 atexit 收掉；
  已有健康服务则**复用且不停它**（CI 就是这样，它在 job 里自己起了 jar）；jar 非 fat 或没有 JDK17
  则如实 SELF-HOST: skip 并交 preflight 判未验——宁可未验，也不拿一个来路不明的进程当被测对象。
  解释器顺序：XINYU_JAVA → PATH 的 java → 本机实测 JDK17 → JAVA_HOME（本机 JAVA_HOME 是 **JDK 8**，
  必须过 java_major>=17 这一关，否则会拿 8 去起 Spring Boot 3）。"""

KNOWN_FLAGS = {"--list", "--exclude-llm", "--only", "--slice", "--selftest", "--help", "-h"}


def pid_alive(pid):
    """锁属主是否还活着。r69 实测：NameError 崩掉的运行不会删锁，
    而 `lock_state` 原来只看 TTL ⇒ 一个**已经不存在的 pid** 能挡整跑 30 分钟
    （本轮 pid=18600 存活=0 仍被拦，且它给的绕行提示 `--only` 同样被拦）。
    探测失败一律按"活着"处理 ⇒ 宁可维持原有的误拦，也不借这条改动放宽锁。
    """
    try:
        if os.name == "nt":
            import ctypes
            h = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(pid))
            if not h:
                return False
            ctypes.windll.kernel32.CloseHandle(h)
            return True
        os.kill(int(pid), 0)
        return True
    except Exception:
        return True


def lock_state(data, now, ttl, mypid, alive=pid_alive):
    """纯函数：判定这把锁该不该拦。返回 (可继续?, 原因)。

    判据（宁可放行也不误拦，但**读到别人的活锁必须拒绝**）：
      · 空/不可解析          → 放行（旧版本写的锁或半截写，不能因此卡死回归）
      · pid == 自己         → 放行并接管（同进程重入，或上次没清干净）
      · now - start > ttl   → 放行（陈旧锁：被 kill 掉的运行不会自己删）
      · 属主 pid 已不存在     → 放行（r69：崩溃残留不该挡后面每一轮）
      · 别人的、且没过期     → 拒绝
    """
    try:
        pid_s, start_s = data.strip().split("\t")
        pid, start = int(pid_s), float(start_s)
    except Exception:
        return True, "锁内容不可解析 ⇒ 放行（但会在收口行点名）"
    if pid == mypid:
        return True, "自己的锁 ⇒ 接管"
    if now - start > ttl:
        return True, "锁已过期 %ds ⇒ 视为陈旧" % int(now - start)
    if not alive(pid):
        return True, "锁属主 pid=%d 已不存在 ⇒ 崩溃残留，放行" % pid
    return False, "另一台进程(pid=%d)起于 %ds 前，未到 TTL %ds" % (pid, int(now - start), ttl)


def lock_selftest():
    """双向自证：该拦的要拦住，不该拦的（自己的/陈旧的/半截的）绝不拦。"""
    cases = [
        ("正例 空文件放行", lock_state("", 1000.0, LOCK_TTL, 7)[0], True),
        ("正例 自己的锁放行", lock_state("7\t999.0", 1000.0, LOCK_TTL, 7)[0], True),
        ("正例 陈旧锁放行", lock_state("8" + chr(9) + "1.0", 10000.0, LOCK_TTL, 7)[0], True),
        ("反例 别人的活锁必须拦", lock_state("8\t999.5", 1000.0, LOCK_TTL, 7, alive=lambda pid: True)[0], False),
        # r69：既有反例原本**读本机 pid 8 是否存活**，加了判活后它会随机器状态翻面
        #（夹具读机器状态＝一条可能在别人机器上永远绿/永远红的用例）⇒ 两边都注入。
        ("r69 正例 属主已死的锁必须放行", lock_state("8\t999.5", 1000.0, LOCK_TTL, 7, alive=lambda pid: False)[0], True),
        ("边界 半截内容不得判拦", lock_state("garbage", 1000.0, LOCK_TTL, 7)[0], True),
        ("边界 零输入不得判绿成脏", lock_state("\t", 1000.0, LOCK_TTL, 7)[0], True),
    ]
    bad = [n for n, got, want in cases if got != want]
    print("LOCK-SELFTEST-%s（%d/%d 类桩）"
          % ("PASS" if not bad else "FAIL: " + "; ".join(bad), len(cases) - len(bad), len(cases)))
    return 1 if bad else 0


HIT_KEYS = ("FAIL", "🔴", "Error", "error:", "Traceback", "SKIP")


# ── 上游配额签名的分档（r54）────────────────────────────────────────
# 动因（一手）：本轮全量跑出 3 条红（api_contract / safety_guard / public_check），逐条读原文
# 发现响应体都是 Insufficient Balance + HTTP 402 —— 即**上游账号余额耗尽**，不是本仓代码坏了。
# r35 的在册教训是「账单阻塞与代码失败必须分开印」；这里补同一族的下半场：
# **判据不许把上游计费故障留在「RED(必须修)」里** —— 那会诱导下一轮去「修」一段没坏的产品代码。
# 严格性不降：这一档仍是**非零退出**（rc=2 未验），且只有命中上游自己写的计费文案才归此档；
# 真契约违反（无此文案）照旧留 RED。匹配对象是套件 rc!=0 时带出的**响应体原文**，
# 不是套件名白名单（按名字判等于把结论写进登记表，换个名字就漏）。
QUOTA_SIG = re.compile("Insufficient Balance|insufficient quota|account balance", re.I)


def split_quota(hard_names, blurbs):
    """纯函数：从判红名单里分出「上游计费未验」与「真判红」；两侧都由 selftest 双向验。"""
    quota = [n for n in hard_names if QUOTA_SIG.search(blurbs.get(n) or "")]
    return [n for n in hard_names if n not in quota], quota


def fold_detail(out_lines, err_text, rc):
    """rc≠0 时该把哪些证据带进收口行。纯函数，可自证。

    三条都是被真实红逼出来的（r41 实测 `voice` 只剩一行 `VOICE-FAIL`，原因在下一行的
    `  - A4 ...` 里）：
      ① 含判据词的行本身；
      ② 紧跟其后的 `-` 续行 —— 很多判据是「标题行带 FAIL，原因逐条列在下面」的形状，
         只挑①就恰好把**最有用的那几行**丢掉（与 r40b「被折叠掉的观测面」同族）；
      ③ stderr 末两行 —— 判据崩在异常里时 stdout 可能一个 token 都没有，
         原先 stdout 非空就完全不读 stderr ⇒「崩了」被读成「没原因」。
    """
    if rc == 0:
        return []
    hits = []
    for i, x in enumerate(out_lines):
        if any(k in x for k in HIT_KEYS):
            hits.append(x.strip()[:170])
            for y in out_lines[i + 1:i + 6]:
                if y.strip().startswith("-"):
                    hits.append(y.strip()[:170])
                else:
                    break
    if not hits:
        hits = [x.strip()[:170] for x in out_lines[-6:]]
    if err_text:
        tail_err = [x.strip()[:170] for x in err_text.strip().splitlines() if x.strip()][-2:]
        hits += ["stderr: " + x for x in tail_err]
    return hits


def fold_selftest():
    """双向自证：续行要带出来、零续行不得乱带、rc=0 一律不印、崩溃必须露 stderr。"""
    out = ["VOICE-FAIL", "  - A4 未观察到监听态", "  - A7 无音频设备", "SOME-OTHER rc=0",
           "  - 不该被带出的邻居"]
    cases = [
        ("续行被带出", len([x for x in fold_detail(out, "", 1) if "A4" in x]), 1),
        ("邻居不越界", any("邻居" in x for x in fold_detail(out, "", 1)), False),
        ("rc=0 一律不印", fold_detail(out, "boom", 0), []),
        ("崩溃露 stderr", any(x.startswith("stderr: boom") for x in
                            fold_detail(["无 token 的一行"], "boom\nsecond", 1)), True),
        ("无 token 退化为末六行", fold_detail(["a", "b"], "", 1)[-1], "b"),
    ]
    bad = ["%s got=%r want=%r" % (n, g, w) for n, g, w in cases if g != w]
    print("FOLD-SELFTEST-%s（%d/%d 类桩）"
          % ("PASS" if not bad else "FAIL: " + "; ".join(bad), len(cases) - len(bad), len(cases)))
    return 1 if bad else 0


def quota_selftest():
    """双向自证：计费签名要能摘出未验，**无签名的真红一律不许被摘**（否则这一档就成了逃生门）。"""
    b = {"api_contract": 'C4 -> 402 body={"error":{"message":"Insufficient Balance (request_id x)"}}',
         "safety_guard": "FAIL 注入样本 override-en 返回 http=402（期望 200）",
         "browser_check": "AssertionError: 对话未走在线（proxy）",
         "empty_blurb": ""}
    cases = [
        ("签名命中→摘为未验", split_quota(["api_contract"], b)[1], ["api_contract"]),
        ("无签名→留 RED（402 本身不是证据）", split_quota(["safety_guard"], b)[0], ["safety_guard"]),
        ("真断言失败绝不被摘", split_quota(["browser_check"], b)[1], []),
        ("明细为空不误判", split_quota(["empty_blurb"], b)[0], ["empty_blurb"]),
        ("两侧之和==输入(不漏不重)",
         sorted(split_quota(list(b), b)[0] + split_quota(list(b), b)[1]) == sorted(b), True),
    ]
    bad = ["%s got=%r want=%r" % (n, g, w) for n, g, w in cases if g != w]
    print("QUOTA-SELFTEST-%s（%d/%d 类桩）"
          % ("PASS" if not bad else "FAIL: " + "; ".join(bad), len(cases) - len(bad), len(cases)))
    return 1 if bad else 0


def ledger_should_write(n_suites, total_suites, rc_hist):
    """纯函数：这一次运行有没有资格改写耗时台账。返回 (写?, 覆盖率标签, 原因)。

    只有**跑满了 SUITES** 的运行才算全量读数。`--only`／`--slice` 跑出来的子集若也落盘，
    下一轮就会拿"3 条的分布"当 99 条的现状做并行决策 —— 那正是 r69 要治的错（读数缺失）
    的反面：读数存在但**是子集冒充全量**，比缺失更坏。
    rc_hist 里没有 -1 之外的含义：本函数只看条数，不看红绿（红运行的耗时照样是真耗时）。
    """
    if total_suites <= 0:
        return False, "none", "零套件 ⇒ 无分母，不写台账"
    if n_suites < total_suites:
        return False, "subset", "实跑 %d/%d ⇒ 子集读数不得覆盖全量台账（会被下一轮当成现状）" % (n_suites, total_suites)
    return True, "full", "实跑==总数 ⇒ 全量分布"


def timing_selftest():
    """台账写入门的双向自证：全量必须写、子集/零分母绝不写。"""
    cases = [
        ("正例 全量运行该写", ledger_should_write(99, 99, 0)[0], True),
        ("反例 --only 子集不该写", ledger_should_write(3, 99, 0)[0], False),
        ("反例 slice 子集不该写", ledger_should_write(98, 99, 0)[0], False),
        ("边界 零分母不该写", ledger_should_write(0, 0, 0)[0], False),
        ("边界 覆盖率标签须与判定同向",
         all((ledger_should_write(a, b, 0)[1] == "full") == (a >= b and b > 0) for a, b in
             [(99, 99), (3, 99), (0, 0), (95, 95)]), True),
    ]
    bad = ["%s got=%r want=%r" % (n, g, w) for n, g, w in cases if g != w]
    print("TIMING-SELFTEST-%s（%d/%d 类桩）"
          % ("PASS" if not bad else "FAIL: " + "; ".join(bad), len(cases) - len(bad), len(cases)))
    return 1 if bad else 0


def write_timing_ledger(times, results, coverage):
    """把本轮**全量**耗时分布落盘并按字节自证读回（r66 立的规矩：写了不算，要证明是这个字节）。

    为什么带 rc：只有耗时没有红绿的台账会被下一轮读成"这些套件都是绿的、花这么多时间"，
    而红套件（尤其长期挂红的 ci_status/live_sync）的时间是**白花的时间**，必须能区分。
    """
    import hashlib
    import json
    from datetime import datetime
    payload = {"generated_by": "_test/run_all_suites.py",
               "written_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
               "coverage": coverage, "suites": len(times),
               "total_s": round(sum(times.values()), 1),
               "rows": [{"suite": n, "seconds": times[n], "rc": rc} for n, rc, _ in results]}
    blob = json.dumps(payload, ensure_ascii=False, indent=1).encode("utf-8")
    TIMING_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    tmp = TIMING_LEDGER.with_suffix(".json.tmp")
    # write_bytes：文本模式在 Windows 会把 \n 翻成 \r\n，带 CRLF 的台账别人 clone 上复算不出 SHA
    tmp.write_bytes(blob)
    os.replace(tmp, TIMING_LEDGER)
    back = TIMING_LEDGER.read_bytes()
    if back != blob:
        return "LEDGER-FAIL: 台账读回字节与写入不一致（被别的运行改了？）"
    return "LEDGER-OK %s ｜ 台账 %s ｜ 指纹 sha256=%s bytes=%d" % (
        coverage, TIMING_LEDGER.relative_to(ROOT).as_posix(),
        hashlib.sha256(back).hexdigest()[:16], len(back))


def serve_plan(up, jar_ok, java_ok):
    """纯决策：已有健康服务→复用；否则 jar 是 fat 且找得到 JDK17→自管起；都不成立→如实报不自管。

    为什么 21 条套件过去只能靠人工起进程（r81 G4）：`server_preflight` 会把「服务没起」如实判成
    rc=2 未验（对，它不该假装绿），但**没人负责把它起来** ⇒ 每一轮都得先手工 `java -jar`，
    忘了就是 21 格成排未验。本函数把「起不起、归谁」收到一处，纯函数因此可离线自证（见 serve_selftest）。
    """
    if up:
        return ("reuse", "8123 已有健康服务 ⇒ 复用，**不会**停掉不是我起的进程")
    if not jar_ok:
        return ("skip", "jar 非 fat 或比源码旧 ⇒ 不自管（先跑 python _test/build_jar.py 或用 mvn）")
    if not java_ok:
        return ("skip", "找不到 JDK17 的 java ⇒ 不自管（设 XINYU_JAVA 指向 java.exe 可覆盖）")
    return ("start", "自管起 jar@8123，跑完由本进程收掉")


def http_health(base=BASE, budget=2.0):
    """探 `/api/health` 且要求 `status=UP`——只看 200 不够（旧 jar 也会回 200）。"""
    import urllib.error
    import urllib.request
    try:
        with urllib.request.urlopen(base.rstrip("/") + "/api/health", timeout=budget) as r:
            if r.status != 200:
                return False
            return json.loads(r.read().decode("utf-8", "replace")).get("status") == "UP"
    except Exception:
        return False


def java_exe(env=None, which=shutil.which, exists=Path.exists):
    """按 XINYU_JAVA → PATH 的 java → 本机实测 JDK17 路径 → JAVA_HOME 的顺序找一个可用解释器。

    ⚠️ 本机 `JAVA_HOME` 默认指向 **JDK 8**（AGENTS.md 工具链表实测），而 Spring Boot 3.2.5 要 17；
    直接拿 `java` 或 `$JAVA_HOME/bin/java` 会起不来或以晦涩错误收口，所以顺序里必须带版本核验。
    """
    env = os.environ if env is None else env
    cand = []
    if env.get("XINYU_JAVA"):
        cand.append(env["XINYU_JAVA"])
    w = which("java")
    if w:
        cand.append(w)
    cand.append(r"C:\Program Files\Eclipse Adoptium\jdk-17.0.20.101-hotspot\bin\java.exe")
    if env.get("JAVA_HOME"):
        cand.append(str(Path(env["JAVA_HOME"]) / "bin" / ("java.exe" if os.name == "nt" else "java")))
    for c in cand:
        if c and exists(Path(c)):
            return c
    return None


def java_major(exe, run=subprocess.run):
    """`java -version` 取主版本号；JDK 8 报 `1.8.0_504` ⇒ 主版本按 8 算，不写成 1。"""
    try:
        p = run([exe, "-version"], capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=25)
    except Exception:
        return None
    text = (p.stderr or "") + (p.stdout or "")
    m = re.search(r'version "(\d+)(?:\.(\d+))?', text)
    if not m:
        return None
    first = int(m.group(1))
    return 8 if first == 1 and m.group(2) else first


def jar_is_fat_and_fresh():
    """复用 `jar_shape_check.inspect` 的判定，不在这里另写一套 fat 标准（derive, not duplicate）。"""
    sys.path.insert(0, str(ROOT / "_test"))
    try:
        import jar_shape_check as J
        newest, ts = J.newest_source()
        r = J.inspect(J.JAR, ts, newest)
        return r["verdict"] == "PASS", "%s｜%s" % (r["verdict"], r.get("reason") or newest)
    except Exception as exc:
        return False, "jar_shape_check 不可调用（%s）" % type(exc).__name__
    finally:
        while str(ROOT / "_test") in sys.path:
            sys.path.remove(str(ROOT / "_test"))


def ensure_server():
    """返回 (状态词, 说明)。状态：reuse / start / skip。

    自管子进程的收口靠 `atexit`（电池全程是 `sys.exit(main())` 正常退出，异常退出也会触发），
    不在 main() 里为它套一层 try/finally —— 那要把 25 行循环整体重缩进，改动面比收益大。
    """
    up = http_health()
    jar_ok, jar_why = (False, "未取数") if up else jar_is_fat_and_fresh()
    exe = None if up else java_exe()
    java_ok = bool(exe) and (java_major(exe) or 0) >= 17
    act, why = serve_plan(up, jar_ok, java_ok)
    if act != "start":
        return ("reuse" if act == "reuse" else "skip"), "%s｜jar=%s" % (why, jar_why)
    log = (Path(os.environ.get("TEMP") or "/tmp") / "xinyu-selfhost-8123.log")
    handle = log.open("wb")
    try:
        p = subprocess.Popen([exe, "-jar", str(ROOT / "server" / "target" / "soulisle-server.jar"),
                              "--server.port=8123"], cwd=str(ROOT), stdout=handle,
                             stderr=subprocess.STDOUT)
    except Exception as exc:
        handle.close()
        return "skip", "Popen 失败（%s）｜日志=%s" % (type(exc).__name__, log)
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        if p.poll() is not None:
            handle.close()
            tail = ""
            try:
                tail = log.read_text("utf-8", errors="replace").strip().splitlines()[-3:]
            except Exception:
                pass
            return "skip", "子进程 rc=%s 已退出｜日志尾=%s" % (p.returncode, " / ".join(tail))
        if http_health():
            atexit.register(stop_server, p, handle)
            return "start", "已起并等到 status=UP｜日志=%s" % log
        time.sleep(1.0)
    stop_server(p, handle)
    return "skip", "120s 内 /api/health 没到 UP ⇒ 已收掉自管子进程（不留孤儿）"


def stop_server(p, handle):
    """只收自己起的那个；terminate 后必须 wait，否则 JVM 还在退就把端口让给下一轮。"""
    try:
        if p.poll() is None:
            p.terminate()
            p.wait(timeout=25)
    except Exception:
        try:
            p.kill()
            p.wait(timeout=10)
        except Exception:
            pass
    try:
        handle.close()
    except Exception:
        pass


def serve_selftest():
    """决策表离线自证（不起真进程）：四形各判其所，含「复用优先于自管」这一条。"""
    fails = []
    cases = (
        ((True, False, False), "reuse", "外部服务健康时必须复用，哪怕 jar 是坏的也不许起第二个"),
        ((False, True, True), "start", "无服务+fat jar+JDK17 ⇒ 自管"),
        ((False, False, True), "skip", "jar 不是 fat ⇒ 不许自管（宁可交未验）"),
        ((False, True, False), "skip", "没有 JDK17 ⇒ 不许自管"),
    )
    for args, want, why in cases:
        got = serve_plan(*args)[0]
        if got != want:
            fails.append("serve_plan%s 应=%s 实=%s（%s）" % (args, want, got, why))
    # JDK 8 的 `-version` 串必须算成 8（本机 JAVA_HOME 实测指向 8，算成 1 会把它当可用解释器）
    class _P:
        def __init__(self, s):
            self.stderr, self.stdout = s, ""
    got8 = java_major("x", run=lambda *a, **k: _P('openjdk version "1.8.0_504"'))
    if got8 != 8:
        fails.append("JDK8 版本串应解析成主版本 8，实=%r" % (got8,))
    got17 = java_major("x", run=lambda *a, **k: _P('openjdk version "17.0.20.1"'))
    if got17 != 17:
        fails.append("JDK17 版本串应解析成 17，实=%r" % (got17,))
    gotbad = java_major("x", run=lambda *a, **k: (_ for _ in ()).throw(OSError("boom")))
    if gotbad is not None:
        fails.append("java 不可调用时必须返回 None（交 skip），实=%r" % (gotbad,))
    return 1 if fails else 0, fails


def acquire_lock():
    """整跑电池不是可重入的：两条链同时打同一个 jar + 同一个上游会互相踩出假红
    （r41 实测两次：`emotion_wiring` 与 `live_sync` 在并发窗口里判红，单独复跑均 PASS）。
    所以并发时**拒绝第二次**，而不是让它产出一条无法归因的红。"""
    import hashlib
    import os
    import time
    key = hashlib.sha1(str(ROOT).encode("utf-8")).hexdigest()[:12]
    path = Path(os.environ.get("TEMP") or "/tmp") / ("xinyu_battery_%s.lock" % key)
    now = time.time()
    if path.exists():
        try:
            data = path.read_text("utf-8", errors="replace")
        except Exception as e:
            data = ""
        ok, why = lock_state(data, now, LOCK_TTL, os.getpid())
        if not ok:
            return path, "BATTERY-UNVERIFIED(并发): " + why + " ｜ 属主若已死会被自动放行；仍活着请等 TTL 或换目录跑（`--only` 同样受此锁约束）"
    path.write_bytes(("%d\t%.3f" % (os.getpid(), now)).encode("utf-8"))
    return path, None


def main():
    global SUITES
    argv = sys.argv[1:]
    total_suites = len(SUITES)   # r70：过滤前的分母，台账靠它区分"全量分布"与"子集冒充全量"
    if "--help" in argv or "-h" in argv:
        print(USAGE)
        return 0
    # 未知开关 fail-closed：r36 实测 `--help` 被静默忽略 ⇒ 直接把 43 条全跑了一遍，
    # 而 `--onl selftest` 这类打错字的过滤同样会跑成全量并打印 ALL-GREEN。
    unknown = [a for a in argv if a.startswith("-") and a not in KNOWN_FLAGS]
    if unknown:
        print("BATTERY-FAIL: 未知开关 %s（可用：--list/--exclude-llm/--only/--slice/--help）"
              % " ".join(unknown))
        return 2
    if "--selftest" in argv:
        rc1 = lock_selftest()
        rc2 = fold_selftest()
        rc3 = quota_selftest()
        rc4 = timing_selftest()
        rc5, serve_fails = serve_selftest()
        print("BATTERY-SELFTEST-%s（锁 %s ＋ 折叠 %s ＋ 计费分档 %s ＋ 台账写入 %s ＋ 自管决策 %s）"
              % ("PASS" if not (rc1 | rc2 | rc3 | rc4 | rc5) else "FAIL",
                 "ok" if not rc1 else "红", "ok" if not rc2 else "红",
                 "ok" if not rc3 else "红", "ok" if not rc4 else "红",
                 "ok" if not rc5 else "红"))
        for f in serve_fails:
            print("  · SELF-HOST-FAIL " + f)
        return 1 if (rc1 | rc2 | rc3 | rc4 | rc5) else 0
    if "--list" in argv:
        print("SUITES:", len(SUITES))
        return 0
    if "--exclude-llm" in argv:
        # CI runner 没有真实上游密钥（密钥不落仓，见 CONTRIBUTING），这两条必须走在线链路才能判绿。
        # 关键约束：**踢掉谁必须点名 + 恒等式**，否则"CI 全绿"会被读成"33 条都跑过了"（同行踩过：装了等于没装）。
        drop = [s for s in SUITES if s[0] in LLM_SUITES]
        SUITES = [s for s in SUITES if s[0] not in LLM_SUITES]
        print(f"(--exclude-llm → 实跑 {len(SUITES)} + 豁免 {len(drop)} == 总数 {len(SUITES) + len(drop)}；"
              f"豁免={[s[0] for s in drop]}，原因=runner 无上游密钥)")
        if not drop:
            print("BATTERY-FAIL: --exclude-llm 却零豁免 ⇒ 豁免名单与实际套件漂移，判据失效")
            return 1
    if "--only" in argv:
        i = argv.index("--only")
        if i + 1 >= len(argv):
            print("BATTERY-FAIL: --only 缺子串操作数")
            return 2
        key = argv[i + 1]
        SUITES = [s for s in SUITES if key in s[0]]
        print(f"(--only {key!r} → {len(SUITES)} 条)")
    if "--slice" in argv:
        i = argv.index("--slice")
        if i + 2 >= len(argv):
            print("BATTERY-FAIL: --slice 需要两个下标（起 止）")
            return 2
        total = len(SUITES)
        lo, hi = int(argv[i + 1]), int(argv[i + 2])
        # 越界下标在 Python 里是静默截断（`--slice 99 120` → 空集），必须点名：
        # 分段跑时"这一条都没跑"不能被印成"这段全绿"
        if not (0 <= lo < hi <= total):
            print(f"BATTERY-FAIL: --slice {lo}:{hi} 越界（套件总数 {total}）")
            return 2
        SUITES = SUITES[lo:hi]
        print(f"(--slice {lo}:{hi} → {len(SUITES)} 条)")
    if not SUITES:
        print("BATTERY-FAIL: 过滤后零套件（空跑出来的全绿没有意义，禁止把 0/0 当通过）")
        return 1

    lock, why = acquire_lock()
    if why:
        # 2 = 未验，不是 1：并发不是"代码坏了"，但也绝不是一块没跑完的绿
        print(why)
        return 2

    # r82 去单点：8123 没人起时自己起、跑完自己收；已有健康服务则**复用且绝不停它**
    srv_state, srv_note = ensure_server()
    print("SELF-HOST: %s ｜ %s" % (srv_state, srv_note))

    results = []
    blurbs = {}
    times = {}   # r69：此前不记每套件耗时 ⇒ "先出耗时分布再谈并行"根本取不到读数
    for name, cmd in SUITES:
        t0 = time.monotonic()
        p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=600)
        times[name] = round(time.monotonic() - t0, 1)
        tail = (p.stdout or "").strip().splitlines()
        # 聚合器只留最后一行 ⇒ 判据说 FAIL 却答不出"哪一条 FAIL"，等于没判（r28 CI 实测踩到）。
        # 现在：rc≠0 时把该套件的 FAIL/🔴/异常行原样带出来；成功仍是一行，不制造噪声。
        # 摘要行改取"最后一条判定行"而非"最后一行"：r36 实测 strategy_selftest 在 PASS 后
        # 还打印注入反例清单，摘要于是显示 `· 热线清单需 ≥3 条，实际 []` —— rc=0 却像报错。
        detail = []
        if p.returncode != 0 and tail:
            detail = fold_detail(tail, p.stderr, p.returncode)
        elif p.returncode != 0:
            detail = fold_detail([], p.stderr, p.returncode)
        line = next((x for x in reversed(tail) if VERDICT_RE.search(x)),
                    tail[-1] if tail else "")
        blurbs[name] = line + " " + " ".join(detail) + " " + (p.stderr or "")
        results.append((name, p.returncode, (line[:110] if tail else (p.stderr or "").strip()[:110])))
        print(f"{name:22s} rc={p.returncode} {times[name]:>5.1f}s | {results[-1][2]}")
        for d in detail:
            print(" " * 25 + "· " + d)

    bad = [r for r in results if r[1] != 0]
    # 收口行必须把"判红"与"环境未验（rc=2）"分开印：r35 实证 ci_status 长期挂红，
    # 起因是账单阻塞（rc=2），计费恢复后变成代码级失败（rc=1）——**原因换了，行没换**，
    # 于是连续 5 次 push 带着真红出门，而电池摘要看上去和上周一样。
    # ⚠️ 三类而不是两类：本轮第一版把"非 1 即环境"写死，随即被自己的输出证伪 ——
    #    voice 两条套件硬崩（rc=0xC0000409、stdout 全空）被判成"环境未验"，等于给崩溃发了通行证。
    hard = [b[0] for b in bad if b[1] == 1]
    hard, quota = split_quota(hard, blurbs)
    soft = [b[0] for b in bad if b[1] == 2]
    crash = [(b[0], b[1]) for b in bad if b[1] not in (1, 2)]
    parts = []
    if hard:
        parts.append("RED(判红，必须修): " + ",".join(hard))
    if soft:
        parts.append("ENV-UNVERIFIED(不是判红，但不得声称已验): " + ",".join(soft))
    if crash:
        parts.append("CRASH(判据自身崩溃，既不是判红也不是环境，必须查): "
                     + ",".join("%s=0x%08x" % (n, c & 0xFFFFFFFF) for n, c in crash))
    if quota:
        parts.append("ENV-QUOTA(上游余额/计费阻塞：响应体自证，非本仓缺陷，但仍不得记为已验): "
                     + ",".join(quota))
    tail_msg = "ALL-GREEN" if not parts else "  |  ".join(parts)
    print("=" * 60)
    ok, coverage, why = ledger_should_write(len(SUITES), total_suites, 0)
    ledger_line = write_timing_ledger(times, results, coverage) if ok else "LEDGER-SKIP: " + why
    print(ledger_line)
    top = sorted(times.items(), key=lambda kv: -kv[1])[:5]
    print("耗时 top5(秒): %s ｜ 合计 %.0fs ｜ 全量分布在台账里（%d 条，并行方案只能在这个读数存在之后才提）"
          % (", ".join("%s=%s" % (k, v) for k, v in top), sum(times.values()), len(times)))
    # rc 必须由真退出码算出来再印：**本行此前长期硬印 `rc=0`**（r74 两面实测：本地整跑 rc=1、
    # 同 SHA 的 CI job 也判 failure，而摘要行照旧印 "rc=0"）——这条摘要是人和机器共同的收口读数，
    # 印错等于伪造回执（台账里"94/98 rc=0"那类句子全部来自它）。
    bat_rc = 1 if (hard or crash) else (2 if (soft or quota) else 0)
    print(f"BATTERY: {len(results) - len(bad)}/{len(results)} rc={bat_rc}", tail_msg)
    try:
        lock.unlink()
    except Exception:
        pass
    # 计费未验与软未验同档（非零、不给绿）；只有真判红/崩溃才是 rc=1
    return bat_rc


if __name__ == "__main__":
    # 守卫必须有：r26 前本文件是**顶层直跑**，任何 `import run_all_suites` 都会把 29 条套件重跑一遍
    # （聚合 runner 最该 import-safe，因为别的判据会拿它的 SUITES 做对账）。
    sys.exit(main())
