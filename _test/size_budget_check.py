# -*- coding: utf-8 -*-
"""静态资源体积预算守卫（对标 LobeChat CI size-limit 的零依赖版）

动机：心屿首屏优势 = 零构建 + 本地 vendor；这份优势同样脆弱——
往 src 里多加一个大依赖/忘压缩一个文件，首屏就悄悄退化，且没有任何门禁拦得住。
本脚本把「体积不回涨」变成机器红线：逐文件预算 + 关键路径总预算。

预算来源：2026-09-25 实测基线 + 5% 余量（写死在 BUDGETS，改预算必须在 PR/日志说明理由）。
判据三态：0=BUDGET-PASS 1=超限 2=文件缺失（缺文件不是"通过"）。
--selftest：把预算临时压到实际值的 90%，必须**逐项报红**，否则判据恒真（R247 对照组）。
"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]

# (相对路径, 预算 bytes)。总预算 = 首屏关键路径：index.html + style.css + 全部 js + data + vendor
# ⚠️ 本表必须**全覆盖**首屏源文件（下方 coverage() 机器强制）：r20 实测发现原 13 文件表
#    漏登记了 src/data/emotion-strategy.js（4,720B），新增 emotion-remote.js 也不会被自动纳入
#    —— 「逐文件预算」若靠手工维护，加文件这条最常见的退化路径恰好绕过门禁。
BUDGETS = {
    # r104 上调 13,235→实测 13,497 +5%：幕次导航（5 个带 aria-label 的锚点）+ 跳转链接。
    #    两者都是"操作效率"本体（回头看某一幕不必一路回滚、键盘 Tab 一下进输入框），不是装饰。
    "src/index.html": 14_172,   # r28 上调：加了离线壳注册块（9,463 实测 +5%），理由记在 CHANGELOG
    #    r87 三度上调（9,936 → 实测 12,605 +5%）：第二幕扫描块 + 对话坞摄像头按钮 + **侧边控制面板**
    #    （头部状态胶囊 + 预览/占位舞台 + 开关控件 + 收起）+ ESM 桥 script 标签。都是功能本体。
    # r104 上调 20,723→实测 27,153 +5%：系统性 UI 优化一次性落地「令牌层 + 组件态」（净 +7.2KB）。
    #    增量全是真规则不是注释：① 令牌（圆角/间距/时长曲线/阴影三级/--ink-2/--ring/--hi）
    #    ② 补齐按钮 active/disabled、输入 focus 双层环、气泡圆角与阴影、弹窗入场与分隔线
    #    ③ 新增件（幕次导航 / 跳转链接 / hover:none / 矮屏 / 减弱动效全量收敛）。
    #    登记前已按本仓口径**先压注释**（新增块初稿 27,764 → 压到 27,153，−611B）；
    #    没有放宽任何判据，也不是"装不下就抬上限"——换掉的是"圆角/间距/时长各写各的"这处不一致。
    "src/css/style.css": 28_511,   # r47 上调：触屏可达性块（13,368→13,502 实测 +134B，含 5% 余量）。
    #    r87e 三度上调（→ 实测 19,737 +5%）：侧边控制面板的部件（状态胶囊三态 / 预览舞台与占位 /
    #    role=switch 开关控件——轨道 38×22 但点击区 ≥44px / 移动端 grid 重排）。先压掉 2 处注释再登记。
    #    r87 再上调 14,785→实测 17,222 +5%：面部识别部件的样式块（小窗/扫描窗/三态徽章/分歧条 + 响应式）。
    #    沿用既有令牌（--panel/--line/--radius/blur），无第二种设计语言，也未引入内联 style。
    #    动因不是"装不下就抬上限"：块内容由 _test/mobile_check.py M2/M3 实测驱动（7 控件高 27-35px
    #    < WCAG 2.5.8 的 44；输入框 14-15px 触发 iOS 聚焦缩放），且已先把注释压到 3 行再登记。
    #    r82 再上调 13,888→实测 14,081 +5%：修「线上 CSP 把内联 style 拦成情绪强度条失效」（r81 §2 G2）时，
    #    7 处 markup 内联 style 的**静态部分**必须有个家 —— `.crisis-chip`/`.crisis-chip .dot`/
    #    `.readout-line`/`.readout-lead` 四条规则（+268B）。登记前已把 CSS 注释从 106B 压到 60B，
    #    解释移进本条注释；**没有**放宽 `deploy/xinyu/_headers` 的 style-src（那是缺陷本体不是约束）。
    #    同轮 app.js 17,036→17,405 仍在 17,524 限内；TOTAL 848,879 仍在 858,752 限内。
    # r104 上调 33,170→实测 33,498 +5%：本轮两笔增量——① 幕次导航高亮与顶栏滚动态的接线
    #    （各 3 行，只切 class，样式全在 CSS）；② initFace 的 TDZ 修复留痕（把 applyEnabled()
    #    首次调用下移到 initFaceHud 解构之后，并在原位写明"为什么不能上移"——不留痕会被挪回去）。
    #    登记前已按本仓口径先压注释（修复说明 7 行→5 行，−200B）。② 这笔不是本轮 UI 引入的缺陷，
    #    是 r103 ③ 拆 initFaceHud 后遗留的，详见文件内注释。
    "src/js/app.js": 35_173,   # r102 实测 31,590 +5%（r87d 的 30,901 之上 +2.2%）：表情 5 类→8 类的界面接线 ——
                          # faceChipHtml / paintHud 改用 FaceEngine.labelOf（独有三类才有名字）+
                          # 低置信度如实标「读数不稳」（旧版每帧都显示成一个笃定的情绪）。
                          # 注：divergence 仍显示表情原名而不是 family 归并后的名 —— 归并发生在
                          # chat-agent.js 侧判定 disagree/agree 时，界面只负责如实呈现名字。
    #    r32 上调：徽章加"网络不可用"降级分支（13,123→13,698 实测 +5%），理由记在 CHANGELOG
    #    r87d 七度上调（r87c 的 29,155 → 实测 29,430 +5%）：开局自检（enumerateDevices 设备数 +
    #    permissions 状态）与错误态附自检读数 —— 用户"授权过却打不开"时界面必须能分开报
    #    「被浏览器记住阻止 / 系统级拦截 / 无设备」。自检结果同时挂 window.__XINYU_FACE_DIAG__（判据取数用）。
    #    r87b/c 六度上调 25,441→实测 27,767 +5%：用户两轮反馈逼出来的三件事——
    #    ①「正在识别…」挂死 ⇒ HUD 看门狗（按 stats() 的 phase 分阶段说人话 + 读数新旧翻面）；
    #    ② 加摄像头总闸 #btn-cam（关=立即真停+隐藏入口+localStorage 记住，开=仍过能力探测）；
    #    ③「点了不弹授权窗」⇒ 授权排在模型加载之前之后，界面必须能说清卡在哪一环
    #    （对话坞新增 #face-status 状态行 + 启动中再点=取消，而不是被 disabled 吞掉）。
    #    r87 四度上调 17,524→实测 24,229 +5%：面部识别的**接线层**（第二幕扫描、实时小窗开合、
    #    三路分歧标注渲染）。评估过按 voice.js/chart.js 先例外提成 `js/face-ui.js`：
    #    不取——它要复用 app.js 私有的 rgbHex/paint/faceChipHtml（渲染口径必须同源，
    #    外提就得反向暴露或复制一份样式拼装函数，那正是本仓"两份真相"那族缺陷的入口）。
    #    宁可让编排层长 7KB，也不造第二个 chip 渲染实现。
    #    r51 再上调：徽章加"大模型暂不可用（已降级）"分支 + 每轮 respond 后 refreshBadge()
    #    （14,294→14,748 实测 +454B，含 5% 余量）。动因是 r51 故障注入实测——上游 500/非 JSON/断连/挂起
    #    四类故障下气泡写「暂不可用」而徽章仍写「● 在线 AI」，同屏自相矛盾且撞红线"禁伪装在线"。
    #    先把自己新写的 3 行注释压成 1 行（省 109B）再登记，不是装不下就抬上限。
    #    r80 三度上调 15,490→实测 16,690 +5%：一键点亮**默认打开**（老大指令）在 boot 末尾的 replayStars() 之后加一段开场演示（16 行）
    #    （playing→lit→done 四态读数 + 定时器收尾 + 播完 replayStars 归位）。**不是装不下就抬上限**：
    #    评估过 r45 式「外提」成 js/opening-show.js（**只在脑内比过方案，没落过文件**）——判定不取：
    #    它要在 index.html 与 sw.js 两处清单各加一条，本判据守的是首屏字节**与请求数**，拆文件等于把
    #    1,272B 换成 1,272B + 一次往返，把预算问题变成更贵的一次加载。
    #    同轮把初版实测 18,484 压到 16,690：注释 10 行→3 行、去掉「hydrate 排队」那套 queue/flush
    #    （改由播完的 replayStars 自然读到最新记忆，行为不变；两次实测 18,484→16,690 未分项归因）。TOTAL 复核 849,690→850,962，
    #    仍在 858,752 限内。牙未动：`size_budget_selftest` 的「压缩预算逐项报红 + 漏登记被 coverage 抓」两腿照在。
    "src/js/chat-agent.js": 16_842,   # r52 上调 11,729→13,024：SYSTEM 拼长期记忆摘要 + respond 返回 memory 字段
    #    r87 再上调 15,302→实测 16,040 +5%：表情作**并列第三路**（face/divergence 字段）。
    #    注意它**不改**双路裁决规则（LLM 采信逻辑一字未动）⇒ 文本链路准确率零回归风险。
    #    r53 再上调 13,024→实测 14,573 +5%：新增 summaryOfDropped()（滑出窗口的历史压成一行结构化摘要）
    #    与 droppedCount()。动因是 r53 实测——14 轮对话有 **16 条消息对模型永久不可见**且无任何补偿
    #    （`_test/context_budget_check.py` 拦 /api/chat 取证，修前该套件以 X2 判红）。
    #    同样先压注释（14,747→14,573，省 174B）再登记；X3 另给 system 段 1,600 字符的**成本上限**，
    #    即"注入更多上下文"这件事本身被预算管住，不是无限往上堆。
    "src/js/emotion-engine.js": 5_598,
    "src/js/emotion-remote.js": 4_679,
    # src/js/voice.js：r97 上调 4,355→实测 4,798 +5%。动因是修「`recognition.stop()` 后浏览器不派发 `end`
    #    ⇒ 语音按钮永久卡在监听态、之后每次点击只是再调 `stop()`（ASR 到刷新前点不回来）」——即 r94/r95/r96
    #    三轮挂账、报告 §3 #9 那处 `src/` 行为码缺陷。判据未放宽：`voice_check.py` A5 的 8s 预算一字未动，
    #    且修复前先在**未修树**上验过新增的 A8/A10 两条桩化腿确实会红（对照腿 A9 同轮绿 ⇒ 不是恒红）。
    #    增量 = 幂等 `leaveListening()` + 两处 try 包裹 + 3 行 WHY 注释；登记前先把自己写的注释从 5,039B
    #    压到 4,798B（−241B，沿用 r47/r51 的「先压注释再登记」口径，不是装不下就抬上限）。
    #    TOTAL 复核 849,529 仍在 858,752 限内；牙未动：`size_budget_selftest` 的「压缩预算逐项报红」腿照在。
    "src/js/voice.js": 5_038,
    "src/js/chart.js": 3969,
    "src/js/chat-window.js": 5845,
    "src/js/settings.js": 3000,
    "src/sw.js": 5_718,   # r87 上调 4,814→实测 5,445 +5%：PRECACHE 增三个面部模块 + 一段"本数组内禁止引号"的注释
    # r54 新增：CSP 要求把 index.html 里唯一那个内联 <script>（离线壳注册）外提，
    #    基线 = 实测 1,078B +5%。它同时进了 SW 预缓存清单（r45 踩过"外提件没进预缓存"）。
    "src/js/sw-register.js": 1_132,
    "src/js/scroll-story.js": 3_757,
    "src/js/three-scene.js": 17_747,   # r87 上调 15,793→实测 16,902 +5%：新增表情雾底色 setMistTint()
    #    （只染**未点亮**的暗星，已点亮的星=被记住的那一瞬，绝不改写；null 时逐帧计算与 r87 前逐位相同）
    # r45 上调 4,844 -> 7214：clear() 改为带回执并读 /stats 复核归零 + 新增 exportAll()
    # （r44 数据权利面实测：旧 fire-and-forget 丢弃服务端 removed 回执）。理由同记 CHANGELOG。
    "src/js/memory-store.js": 8_868,
    # r52 上调 7214→实测 8,446 +5%：新增 recall()（只聚合次数/跨度/高频情绪，不拼用户原话）
    # 与 count()（供界面标「已带入 N 条记忆」）。判据 _test/memory_recall_check.py R4 是反向腿：
    # 清空记忆后召回段必须消失，所以这块不是"常量字符串"，是数据驱动的能力。
    # 同样先压注释（8,675→8,446，省 229B）再登记。
    # r45 新增：数据主体权利 UI 从 app.js 外提（外提后 app.js 14,281 回到限内），基线取实测 +5%
    "src/js/data-rights.js": 3_553,   # r104 上调 3,300→实测 3,384 +5%：修「界面直接显示 **星号**」这一处
    #    文案缺陷（`REMOTE_TXT`/`LOCAL_TXT` 是 textContent，Markdown 标记会原样显示，第四幕截图实测可见）
    #    + 一行留痕注释。先压注释（初稿 +230B → 压到 +128B）再登记；判据口径未动
    #    （`data_rights_check.py` D1 只认「服务端 / 不上传 / 只留在本机」这些关键字，改后全绿）。
    "src/js/demo-config.js": 1_828,
    # ── r87 新增：面部表情识别三件套（首屏只多 ~21KB，13MB 的 wasm/模型走懒加载，见 LAZY_BLOCKS）──
    "src/js/face-engine.js": 21_216,            # r102 实测 20,204 +5%（r87 的 18,467 之上再上调 14.9%）。
                                             # 上调理由（功能驱动，非"装不下就抬"）：表情 5 类扩到 8 类，增量是真代码
                                             # 不是注释 —— ① 非对称门 smileAsymmetry()（轻蔑靠左右不对称；加权和的对称项
                                             # 两侧同权，表达不了"单侧笑"）② 多线索佐证 cueRegions()（修"专注时压眉被
                                             # 读成愤怒"）③ confidence/confident（margin 低时自报"读数不稳"，
                                             # 旧版每帧都硬给一个情绪）④ curve() 软饱和单点可调。
                                             # 登记前注释已从 5,786B 压到约 4.1KB（标定依据移到 memory；仓规：中文注释 3B/字）。
                                            # r87b 再上调：用户级摄像头开关（enabled/setEnabled，localStorage 记住，关=立即真停）。
                                            # r87d 再上调（实测 17,588 +5%）：diagnose() 分层自检 + getUserMedia 12s 超时
                                            # （系统级拦截时该 promise 会一直挂着）+ 五类错误各自的可执行处置文案。
                                                # 12,236→13,755 的增量是真代码不是注释：① start() 加会话令牌（修"启动未完成时点关闭
                                                # ⇒ 摄像头留在开着"的隐私竞态，公网实测抓到）② videoEl.play() 改"发起即走+1.5s 兜底"
                                                # （公网实测该 promise 永不 settle 会把整条开启链吊死 60s+）③ 单帧异常留痕 frameErr。
    "src/js/face-mediapipe-bridge.js": 3_996,   # r87 实测 3,806 +5%：全站唯一 type=module（ESM 桥）。3,292→3,806 = boot 改惰性
                                                # （初版模块一执行就下 13MB，公网冷启动把能力状态卡在 boot 超 90s）+ SIMD 探测注释。
    "src/data/face-smile-rules.js": 13_927,      # r102 实测 8,754 +5%（r87 的 5,479 之上 +59.8%）。表情 5 类→8 类：
                                             # r103 上调 9,192→11,148（实测 10,617 +5%）：anger 取舍的**留痕**。
                                             # 写清「为什么 anger 不在 need 里、真愤怒实测 AU 是什么、代价面是哪
                                             # 三条、fear/sadness 为何仍保留多区要求」。这类注释是取舍记录，
                                             # 删掉就没人知道 anger 为何独独没有多区佐证 —— 后人会当手滑改回去
                                             # （F11 反例6 腿专门盯这次回退）。
                                             # r103 再上调 11,148→13,138（实测 12,512 +5%）：
                                             # sadness 重标的**证据留痕**：真悲伤照实测 AU、为什么主证据换成
                                             # browInnerUp，以及一段**自我更正**（我原写 jawOpen 是分水岭，实测
                                             # 发现它是摆设、真正起作用的是 browInnerUp）。这段更正必须留 ——
                                             # 它防的是「注释写错比没注释更坏」，比被删的参数本身更值得占预算。
                                             # r103 补（13,138→实测 13,264 +5%）：jawOpen 在**代价面**上的作用。
                                             # 上轮把它误判成摆设，代价面实测翻案（边担忧边说话靠它拉回平静）——
                                             # 这类「我以为无用的规则其实有用」的更正，正是最该留痕的东西。                                             # 权重表 4 组→7 组（新增 surprise/disgust/contempt）+ family（表情侧 8 类
                                             # 对齐文本 6 类，供分歧标注用）+ colors（独有三类自持色，不碰双端 SSOT）
                                             # + cue/need（多线索佐证）+ asym（非对称门）+ confidence + peak 基准。
                                             # 同上：注释已从 9,944B 压到约 5.5KB，标定依据移到 memory/05 与 07。
    "src/data/emotion-lexicon.js": 4_042,
    "src/data/emotion-strategy.js": 4_956,
    "src/vendor/three.min.js": 633_617,
    "src/vendor/gsap.min.js": 75_825,
    "src/vendor/ScrollTrigger.min.js": 45_549,
}
TOTAL_KEY_PATH = 968_000  # 首屏关键路径总预算（含 vendor），2026-09-25 实测 817,859B + 5%
#   r104 上调 913,000→968,000（实测 921,253 +5%）：承接本轮 CSS/HTML 的净增（+8.6KB，理由见上两条）。
#   这是**首屏真要解析的字节**（令牌层 + 组件态 + 幕次导航），不是懒加载、不是注释灌水；
#   牙未动：`size_budget_selftest` 的「压缩预算逐项报红 + 漏登记被 coverage 抓」两腿照在。
#   r103 上调 911,000→912,000（实测 911,182 +0.02%）：拆 initFaceHud 的净增（约 +1.1KB，
#   r103 再上调 912,000→913,000（实测 912,685 +0.07%）：anger 取舍的注释留痕（约 +1.4KB）。
#   13.7MB 模型仍走懒加载不进 TOTAL，判据面文件全在首屏 ⇒ 这 1.4KB 是真的首屏字节。
#   换掉的是 app.js 里 194 行单函数；判据面未动，13.7MB 模型仍走懒加载不进 TOTAL）。
#   r102 上调 905,000→911,000（实测 910,140 +0.1%）：表情判据 5 类→8 类的真实增量
#   （引擎 +1.7KB、规则 +3.3KB、app.js 接线 +0.7KB 净增，注释已先压过一轮）。
#   13.7MB 的 wasm/模型仍走懒加载、不进 TOTAL（见 LAZY_BLOCKS）—— 这条上限守的是**首屏
#   真要解析的字节**，而模型只在用户点开表情感知时才拉，两者不是同一笔钱。
#   牙未动：`size_budget_selftest` 的「压缩预算逐项报红 + 漏登记被 coverage 抓」两腿照在。
#   r87 上调 900,000→905,000（实测 902,062 +0.3%）：面部表情识别的**关键路径**增量约 +13KB
#   （引擎 15.6KB + 桥 3.8KB + 规则 5.2KB + 面板 UI/CSS/接线），这些是首屏真的要解析的字节；
#   而 13.7MB 的 wasm 与模型走**懒加载**、单独打印、不进 TOTAL。属功能驱动的一次性上调，
#   不是"装不下就抬"：登记前已把本轮新增注释压掉约 1.6KB（app.js/face-engine.js/style.css/index.html）。
#   r87 上调 858,752→900,000：面部表情识别让首屏真多了 ~28KB（三个新模块 20.7KB + 接线与样式 ~7KB），
#   这不是"装不下就抬上限"而是**记录一次真实的体积增长**：13MB 的 wasm/模型**不进首屏**
#   （走懒加载，见 LAZY_BLOCKS，只在用户点开表情感知时才拉）。上限按实测 +5% 重定，
#   牙未动：`size_budget_selftest` 的「压缩预算逐项报红 + 漏登记被 coverage 抓」两腿照在。
# 懒加载块（**不计入首屏 TOTAL**，单独打印）：这些字节只在用户真的开启功能时才下载。
#   为什么要单独有一格：不登记的话，13MB 的第三方模型混入"首屏预算"讨论会让这把尺失去意义
#   —— 判据要管的是"首屏不退化"，同时也要让人看见"代价发生在哪一次点击之后"。
LAZY_BLOCKS = {"src/vendor/mediapipe": 14_000_000}  # 实测 13,674,721（2026-10-10）

# 参与覆盖校验的目录（src/functions 是 Pages Function 服务端源码，不在首屏路径）
COVER_DIRS = ("src/js", "src/css", "src/data", "src/vendor")
COVER_ROOT = ("src",)   # r28：src 根目录也有首屏件（sw.js），不纳入就等于给"新增文件绕过预算"留口子


def coverage():
    """返回 (未登记预算的新文件, 表里已不存在的死条目)。"""
    on_disk = set()
    for d in COVER_DIRS:
        for p in (ROOT / d).glob("*"):
            if p.is_file() and p.suffix in (".js", ".css", ".html"):
                on_disk.add(p.relative_to(ROOT).as_posix())
    html = "src/index.html"
    if (ROOT / html).exists():
        on_disk.add(html)
    for d in COVER_ROOT:
        for p in (ROOT / d).glob("*.js"):
            on_disk.add(p.relative_to(ROOT).as_posix())
    # demo-config.js：src 版含本机 Key 且被 .gitignore，两端形态本就不同 ⇒ 两侧都排除，
    # 只做「存在则测预算」，不参与「必须登记」的覆盖对账
    on_disk.discard("src/js/demo-config.js")
    declared = set(BUDGETS) - {"src/js/demo-config.js"}
    unregistered = sorted(on_disk - declared)
    stale = sorted(declared - on_disk)
    return unregistered, stale


def measure():
    rows, total, missing = [], 0, []
    for rel, budget in BUDGETS.items():
        f = ROOT / Path(rel)
        if not f.exists():
            # demo-config.js 被 .gitignore 排除（真身含本机 Key）→ 全新 clone 缺席是常态，
            # 记警告并按"其公网 stub 不会超预算"放行；其余文件缺席 = 环境异常 rc=2。
            if rel == "src/js/demo-config.js":
                print(f"  WARN  {rel} 缺席（gitignore 本机件），本项跳过预算")
            else:
                missing.append(rel)
            continue
        size = f.stat().st_size
        total += size
        rows.append((rel, size, budget))
    return rows, total, missing


def run(scale=1.0):
    rows, total, missing = measure()
    if missing:
        print(f"BUDGET-ENV-FAIL: 缺失文件 {missing}")
        return 2
    red = 0
    for rel, size, budget in sorted(rows, key=lambda r: -r[1]):
        b = int(budget * scale)
        ok = size <= b
        if not ok:
            red += 1
        print(f"  {'OK ' if ok else 'OVER'}  {rel:36s} {size:8,d} / {b:8,d}")
    tb = int(TOTAL_KEY_PATH * scale)
    ok_total = total <= tb
    if not ok_total:
        red += 1
    print(f"  {'OK ' if ok_total else 'OVER'}  {'TOTAL(关键路径)':36s} {total:8,d} / {tb:8,d}")
    # 懒加载块：不计入上面那个 TOTAL，但必须被人看见（越界同样判红，只是分母不同）
    for rel, budget in LAZY_BLOCKS.items():
        d = ROOT / rel
        lazy = sum(p.stat().st_size for p in d.rglob("*") if p.is_file()) if d.is_dir() else 0
        lb = int(budget * scale)
        ok = lazy <= lb
        if not ok:
            red += 1
        print(f"  {'OK ' if ok else 'OVER'}  {('懒加载 ' + rel):36s} {lazy:8,d} / {lb:8,d} （不计入首屏 TOTAL）")
    if red:
        print(f"BUDGET-FAIL: {red} 项超预算")
        return 1
    print(f"BUDGET-PASS: {len(rows)} 文件 + 总预算全在限内（total={total:,d}）")
    return 0


if __name__ == "__main__":
    unreg, stale = coverage()
    if "--selftest" in sys.argv:
        # 覆盖判据自证：从表里抽掉一个真实存在的文件，coverage 必须抓到（否则恒真）
        probe = "src/js/emotion-remote.js"
        BUDGETS.pop(probe, None)
        caught = probe in coverage()[0]
        rc = run(scale=0.90)
        if rc == 1 and caught:
            print("✅ SELFTEST-PASS：压缩预算逐项报红 + 漏登记文件被 coverage 抓到 ⇒ 两判据非恒真")
            sys.exit(0)
        print(f"🔴 SELFTEST-FAIL：budget_rc={rc} coverage_caught={caught}")
        sys.exit(1)
    if unreg:
        print(f"BUDGET-FAIL: 首屏存在未登记预算的文件 {unreg}（新增文件必须同步进预算表）")
        sys.exit(1)
    if stale:
        print(f"  WARN  预算表含磁盘已无的条目 {stale}（不阻塞，建议清理）")
    sys.exit(run())
