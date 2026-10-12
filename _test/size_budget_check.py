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
    #    r109 上调 14,172→实测 14,809 +5%：表情感知折叠行+面板入坞的 markup（原侧边 aside 整块删除，
    #    净增约 640B）；摄像头总闸并入设置面板（+1 行 label）。
    # r115 上调 15,550→实测 19,916 +5%：① emoji 字形图标换内联 SVG 精灵（12 个 symbol 定义一次、
    #    各处 <use> 引用，比逐个内联 path 省一半字节）② 表情感知侧边抽屉 markup（拖柄 + 头部 +
    #    关闭/大小两键 + 说明行）③ 坞标题条新增「表情面板」常驻功能键。都是功能与可达性本体。
    "src/index.html": 24_683,   # r117 上调 24,640→实测 23,507 仍在旧限内（净 +43B：wit-quotes 数据件 script 标签一行）；
                                #    本行随 r117 按实测重算 +5% 登记，语义不变。
    # r28 上调：加了离线壳注册块（9,463 实测 +5%），理由记在 CHANGELOG
    #    r116 再上调 20,920→24,640（实测 23,464 +5%）：语音通话入口 #btn-call + 通话浮层 #call-layer
    #    （音色下拉/双工开关/字幕/音量计）。⚠️ 本数含并行轮 r115→r116 表情感知悬浮窗的在途件
    #    （face-pip 块 + 精灵图标），随本轮整批入库并署名一次，以便日后考古不认错轮次。
    #    r87 三度上调（9,936 → 实测 12,605 +5%）：第二幕扫描块 + 对话坞摄像头按钮 + **侧边控制面板**
    #    （头部状态胶囊 + 预览/占位舞台 + 开关控件 + 收起）+ ESM 桥 script 标签。都是功能本体。
    # r104 上调 20,723→实测 27,153 +5%：系统性 UI 优化一次性落地「令牌层 + 组件态」（净 +7.2KB）。
    #    增量全是真规则不是注释：① 令牌（圆角/间距/时长曲线/阴影三级/--ink-2/--ring/--hi）
    #    ② 补齐按钮 active/disabled、输入 focus 双层环、气泡圆角与阴影、弹窗入场与分隔线
    #    ③ 新增件（幕次导航 / 跳转链接 / hover:none / 矮屏 / 减弱动效全量收敛）。
    #    登记前已按本仓口径**先压注释**（新增块初稿 27,764 → 压到 27,153，−611B）；
    #    没有放宽任何判据，也不是"装不下就抬上限"——换掉的是"圆角/间距/时长各写各的"这处不一致。
    #    r108 上调 28,511→实测 30,335 +5%：对话坞「与背景融为一体 + 右上角只留一个按钮」（老大拍板）。
    #    增量全是真规则：① 融合渐变四级令牌（深/浅各一套，顶透底实替代面板底色+blur+描边+投影）
    #    ② 三态样式（常规 / 全屏 .full 铺满视口+日志吃掉余高 / 收起 44px 细条）③ 坞按钮与输入行
    #    两个挪位按钮的窄屏收图标规则。登记前已按本仓口径先压注释（初稿 30,692 → 30,335，−357B），
    #    仍差的部分是规则本体（融合渐变只能写成多行 linear-gradient），不是注释灌水。
    #    r109 上调 31,860→实测 31,463（本轮反而下降 −397B：.face-hud 从 fixed 悬浮改坞内流式块，
    #    删掉了右下角定位/768px grid 重排两套规则，新增的折叠行与全屏隐藏规则少于删掉的）。
    #    r110 上调 31,860→实测 32,361 +5%（两笔真规则：r109 的 hidden 家族修复 5 选择器；
    #    r110 坞底透明度减半 + 文字描边补偿两行）。登记前已压注释（32,602 → 32,361，−241B）。
    # r115 上调 33,980→实测 36,357 +5%（净 +3,367B，登记前已压注释）：① 侧边抽屉本体（桌面右滑出 /
    #    手机底部弹出两套定位 + 拖拽态关过渡）② 画面从写死 height:120px+cover（把 4:3 横切只剩半张脸，
    #    老大实测截图即此）改为 aspect-ratio:4/3 随抽屉缩放 ③ .ico SVG 图标基线 ④ 手机优先字阶
    #    （.msg 14.5→16px、.lead 14.5→15.5px、chat-log 加高）。同时删掉两条零引用死规则
    #    （.face-hud-head/.face-hud-title，grep src/ deploy/ _test/ 三面确认无使用者）。
    # r116 上调 38,180→实测 39,336 +5%：侧边抽屉换成**微信视频通话式悬浮窗**——小窗态（可拖位置/
    #    可拖大小）+ 整屏态（画面铺满视口、标题条与读数浮在上下两层 scrim 上）+ 角落缩略图，
    #    两套定位与 scrim 是真规则不是注释；同时删掉抽屉那套底部弹出与向右让位规则（净 −1 段）。
    "src/css/style.css": 41_310,   # r47 上调：触屏可达性块（13,368→13,502 实测 +134B，含 5% 余量）。
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
    #    r108 上调 35,173→实测 36,842 +5%：对话坞三态状态机（DOCK_NEXT 表 + paintDock/setDock/
    #    setFull + 三态点击派发 + Esc 退出全屏 + 演示态先退全屏）。旧版是 7 行「open/!open」二态，
    #    新版多出的字节换的是「一个按钮管三态且图标/文案/aria 随态翻面」这件本来没有的事。
    #    r109 再上调 38,690→实测 40,112 +5%：表情感知入坞接线（总闸搬设置面板 + setFacePanel 折叠）
    #    与全屏虚拟滚动（wheel/touch→星雾进度 + 退出还镜头，含日志内滚不抢滚动的分流）。
    #    登记前已按本仓口径先压注释（初稿 40,124 → 40,112）。
    # r115 上调 42,120→实测 45,683 +5%：新增 initFaceDrawer()（拖柄 pointer 调大小 + 「大小」三档循环
    #    + 视口变窄重钳 + 尺寸存 peiliao.facedrawer.v1），尺寸只走 CSSOM setProperty（markup 内联 style
    #    撞线上 CSP，_test/inline_style_check.py 新增即判红）；#btn-face-panel 常驻键与抽屉关闭键接线；
    #    主题图标从 emoji textContent 改为换 <use> 的 href 引用。
    "src/js/app.js": 50_770,   # r102 实测 31,590 +5%（r87d 的 30,901 之上 +2.2%）：表情 5 类→8 类的界面接线 ——
                          # faceChipHtml / paintHud 改用 FaceEngine.labelOf（独有三类才有名字）+
                          # 低置信度如实标「读数不稳」（旧版每帧都显示成一个笃定的情绪）。
                          # 注：divergence 仍显示表情原名而不是 family 归并后的名 —— 归并发生在
                          # chat-agent.js 侧判定 disagree/agree 时，界面只负责如实呈现名字。
    #    r116 再上调 47,970→实测 48,352 +5%：把「一句话走完整共情链路」抽成 sendTurn(text, extraDelta)，
    #    文字模式与语音通话共用同一条路（另起一条链路 = 情绪双路/记忆注入/危机短路/点亮要维护两份，
    #    正是本仓刚消掉的「两份真相」红线形态）；并注入 window.VoiceCall.init({send: sendTurn})。
    #    ⚠️ 本数同时覆盖并行轮 r115→r116 的表情感知悬浮窗在途件，随本轮整批入库并署名一次。
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
    "src/js/chat-agent.js": 21_773,   # r117 上调 19,336→实测 20,736 +5%：表达语料库注入 quoteBlockFor()
                          # （老大定的「每轮都给候选」：情绪匹配 Top5 候选 + 引用规则拼接）+ SYSTEM
                          # 预算切分（quote 保底优先、kb 用剩余）。防堆砌靠 quoteRules 硬约束（≤1 句/不契合不引）。
                          # r113 上调 16,842→实测 18,415 +5%：心理学知识库注入 kbBlockFor()
                          # （老大定的「回答更专业有据」）：相关条目注入回复提示词+依据标注。
                          # 体量被 X3（system 1600 字符）双向管住：注入只用剩余量，挤不下不注入。
                          # 注释已按仓规压过（触发条件与预算约束写进一处，不重复展开）。
    #    r52 上调 11,729→13,024：SYSTEM 拼长期记忆摘要 + respond 返回 memory 字段
    #    r87 再上调 15,302→实测 16,040 +5%：表情作**并列第三路**（face/divergence 字段）。
    #    注意它**不改**双路裁决规则（LLM 采信逻辑一字未动）⇒ 文本链路准确率零回归风险。
    #    r53 再上调 13,024→实测 14,573 +5%：新增 summaryOfDropped()（滑出窗口的历史压成一行结构化摘要）
    #    与 droppedCount()。动因是 r53 实测——14 轮对话有 **16 条消息对模型永久不可见**且无任何补偿
    #    （`_test/context_budget_check.py` 拦 /api/chat 取证，修前该套件以 X2 判红）。
    #    同样先压注释（14,747→14,573，省 174B）再登记；X3 另给 system 段 1,600 字符的**成本上限**，
    #    即"注入更多上下文"这件事本身被预算管住，不是无限往上堆。
    "src/js/emotion-engine.js": 9_371,   # r117 在途收尾上调 5,598→实测 8,924 +5%：语意转折主次判定增量（转折标记与主次特征）；本行随 r118 弃置在途件代收口按实测重算登记
    "src/js/emotion-remote.js": 4_679,
    # src/js/voice.js：r97 上调 4,355→实测 4,798 +5%。动因是修「`recognition.stop()` 后浏览器不派发 `end`
    #    ⇒ 语音按钮永久卡在监听态、之后每次点击只是再调 `stop()`（ASR 到刷新前点不回来）」——即 r94/r95/r96
    #    三轮挂账、报告 §3 #9 那处 `src/` 行为码缺陷。判据未放宽：`voice_check.py` A5 的 8s 预算一字未动，
    #    且修复前先在**未修树**上验过新增的 A8/A10 两条桩化腿确实会红（对照腿 A9 同轮绿 ⇒ 不是恒红）。
    #    增量 = 幂等 `leaveListening()` + 两处 try 包裹 + 3 行 WHY 注释；登记前先把自己写的注释从 5,039B
    #    压到 4,798B（−241B，沿用 r47/r51 的「先压注释再登记」口径，不是装不下就抬上限）。
    #    TOTAL 复核 849,529 仍在 858,752 限内；牙未动：`size_budget_selftest` 的「压缩预算逐项报红」腿照在。
    #    r116 上调 5,038→实测 10,624 +5%：voice.js 从「单音色朗读 + 一次性输入」升为**声音能力层**
    #    —— 音色目录（本机 getVoices 独立音色 × 5 档语调，标签如实区分「独立音色/变调」）+ 分句朗读队列
    #    （enqueue/cancelSpeech/queueBusy/preview）。动因：通话层要「边生成边念第一句」，出声调度必须与
    #    音色选择同层，否则两处各建 utterance = 音色口径分叉。原 speak 的单次朗读语义未放宽（U1e 关得掉）。
    # r118 上调 11,160→实测 16,454 +5%：voice.js 长出「本机开源神经引擎」这一层（决策 #11）——
    #    /health 探测、把本机说话人并进同一张音色表、一句话一个 WAV 的发声、以及"播放事件丢了
    #    也不许把队列挂死"的看门狗。动因：浏览器自带中文音色机械感强，老大定「本机引擎优先 +
    #    浏览器兜底 + 字幕终兜」。默认关（cfg.localTts 不为 true 时一次请求都不发，公网面行为未变）。
    "src/js/voice.js": 17_277,
    # r116 新增两件（语音通话）：编排层 + 它自己的样式表。分文件是为守 size_budget 的逐文件口径，
    #    不是绕预算 —— 两者都计入 TOTAL，且都进 sw.js PRECACHE（断网也要能讲）。
    "src/js/voice-call.js": 23_828,   # r118 上调 22,465→实测 22,693 +5%：采集链显式声明（AUDIO_CST 三面旗）
    #    + 能量门 gateOpen（噪声不许把话头吊着不收口）+ 无合成引擎时不把状态翻成「在说」（判据 C12/C13 各盯一条）。
    # r116 首登 21,330（实测 20,312 +5%）→ 收口轮上调 22,465（实测 21,396 +5%）：
    #    收口时补的两处一手修复 —— ① 真机 results 是会话级累计列表，收口后要按条数跳过旧句（baseLen），
    #    否则第二句会把第一句重拼进送模型的文本；② 识别会话生命周期 recAlive（活着不重复 start、
    #    半双工念话期间 end 到了不抢着开麦）。都不是注释膨胀，是行为码。
    "src/css/voice-call.css": 4_690,
    "src/js/chart.js": 3969,
    "src/js/chat-window.js": 5845,
    "src/js/settings.js": 3000,
    "src/sw.js": 6_083,   # r117 上调 5,718→实测 5,793 +5%：PRECACHE 增 wit-quotes 数据件一行 + 两行注释
    #    （断网也要能注入候选；注释按数组内禁引号的既有纪律写）。
    # r87 上调 4,814→实测 5,445 +5%：PRECACHE 增三个面部模块 + 一段"本数组内禁止引号"的注释
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
    "src/js/face-engine.js": 25_317,            # r113 上调 21,216→实测 24,111 +5%：质量门四信号（r113「表情
                                             # 识别更抗造」，老大拍板的功能）——assessQuality 纯函数 +
                                             # lumaStats 24×24 缩样 + yawRatio 标志点几何 + 嘴部平坦计数 +
                                             # applyQuality 降档落点。命中只降置信+改文案，不参与裁决。
                                             # r102 实测 20,204 +5%（r87 的 18,467 之上再上调 14.9%）。
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
    "src/data/face-smile-rules.js": 14_911,      # r113 上调 13,927→实测 14,201 +5%：quality 阈值块（四信号，
                                              # 首版保守值+标定债注释——债务写进注释正是要占预算的内容）。
                                              # r102 实测 8,754 +5%（r87 的 5,479 之上 +59.8%）。表情 5 类→8 类：
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
    "src/data/emotion-lexicon.js": 6_711,   # r117 在途收尾上调 4,042→实测 6,391 +5%：语意转折词表增量；同上代收口按实测重算
    # r117 上调 4,956→实测 5,153 +5%：quoteRules 四条引用适配规则（防硬贴/防堆砌的底线条款；
    #    _test/strategy_check.py 新增 G 判据钉住其存在与关键约束词，缺即判红）。
    "src/data/emotion-strategy.js": 5_411,
    # r113 新增：心理学知识库数据件（老大定的「AI 回答更专业有据」）——由 psych_kb_build.py
    #    从 交付物/心理学知识库 条目卡生成，禁手改；E 级（未查证）条目构建期排除。
    #    数据件随条目扩充增长 ⇒ 每次重建后按实测 +5% 重登记（--check 判据钉住源与产物一致）。
    "src/data/psych-kb.js": 97_040,   # r129-KB 上调 91,660→97,040：第5轮首批（篇章19 求助污名 HK 域 6 条）后实测 92,419B +5%（104 条 A34/B41/C9/D20；r127-KB 前值 91,660 系第4轮 98 条/87,295B +5%）   # r127-KB 上调 66,605→91,660：第4轮扩容+校准升级后实测 87,295B +5%（98 条 A-D 级 A33/B40/C6/D19；r123 落 24 卡、校准员升 12 张 E 级卡）
    # r117 新增：表达语料库数据件（老大定的「表达优化专项」）——由 _test/wit_quotes_build.py
    #    从 交付物/表达语料库 四篇条目卡生成，禁手改；E 级构建期排除。首登实测 63,140 +5%
    #    （101 条 A53/B35/C5/D8）。数据件随条目扩充增长 ⇒ 重建后按实测重登记（--check 钉住源产物一致）；
    #    注入体量另受 X3（system 1600 字符）独立管住，不会随库变大而变大。
    "src/data/wit-quotes.js": 66_297,
    "src/vendor/three.min.js": 633_617,
    "src/vendor/gsap.min.js": 75_825,
    "src/vendor/ScrollTrigger.min.js": 45_549,
}
TOTAL_KEY_PATH = 1_222_765  # r127-KB 同幅上调（psych-kb +25,055：66,605→91,660，第4轮 98 条）  # 首屏关键路径总预算（含 vendor），2026-09-25 实测 817,859B + 5%
#   r117 上调 1,115,591→实测 1,134,541 +5%：表达语料库数据件首登（wit-quotes.js 63,140B）是本轮
#   真实的首屏字节增量（每轮对话注入用的素材底座），其余为 chat-agent/strategy/sw 的功能本体增量。
#   逐文件预算同步登记，没靠"抬总分"掩盖单项超限（coverage 强制新文件必须登记）。
#   r116 上调 1,045,114→实测 1,048,288 +5%：语音通话两件是**真首屏字节**（js/voice-call.js 20,312 +
#   css/voice-call.css 4,463 = 24.5KB），且都进 sw.js PRECACHE（断网也要能讲）。逐文件预算同步登记，
#   没靠"抬总分"掩盖单项超限：sw.js 加两行清单后实测 5,666 仍在 5,718 限内（先把自己的注释压掉）。
#   ⚠️ 该实测面同时含并行轮在途件（r113 psych-kb 48,693、r115/r116 face-pip），随本轮整批入库并署名一次。
#   r114 上调 1,023,000→1,045,114：psych-kb 数据件预算同幅上调（29,602→51,716），随第2轮扩容
#   （+23 条，实测 49,253B）。r113 上调 968,000→1,023,000：心理学知识库数据件首登 + 质量门三件。
#   r116-KB（知识库第3轮）上调 1,100,702→1,115,591：psych-kb 预算同幅 51,716→66,605（实测 63,433B +5%，74 条）。
#   r127-KB（知识库第4轮收口）上调 1,197,710→1,222,765：psych-kb 预算同幅 66,605→91,660（实测 87,295B +5%，98 条）。
#   r129-KB（知识库第5轮首批 6 条）只调单项 91,660→97,040（实测 92,419B +5%，104 条），**TOTAL 未动**：
#     TOTAL 比的是实测总量（现 1,175,634），与单项预算上限无关；本轮实测余量 47,131B，按「不许静默抬限」不把总分一起抬。
#     先前各轮「同幅上调 TOTAL」的写法在单项上调会流进实测总量时才必要（文件真变大才会顶总分），此处不是。
#   ⚠️ 同日两名并行会话同取 r116 号（本知识库轮 vs 语音通话轮）——考古按内容面区分：KB 轮=psych-kb/交付物面，语音轮=voice-call 面。
#   数据件是功能本体（「回答更专业有据」的知识底座），随条目扩充增长，重建后按实测重登记；
#   注入体量另受 X3（system 1600 字符）独立管住，不会随库变大而变大。
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
