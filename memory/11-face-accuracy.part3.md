# 11-face-accuracy · part3 — 执行方案（改进项 × 步骤 / 预期 / 资源 / 验收 / 时间）

> 时间锚（假设值，待老大确认）：复赛 ≈10 月下旬 ⇒ 短期 T+7；决赛 ≈11 月 ⇒ 中期 T+28。
> 每项验收都是机器判据（跑得出 rc），禁"看起来好了"。资源单位：轮（一个 agent 会话）。

## S1 低强度动态分母（算法，修 A1+A2）

- **步骤**：① `src/js/face-engine.js scores()`：pos 只累加 `bs[k]≥cue.min` 的正权项；
  ② `face-smile-rules.js` 加 `dynDenom: true` 开关（回滚=置 false，旧路径不动）；
  ③ 症状 13 向量 + face_discrim 全量回归；④ 同步 deploy/xinyu + SHA256 双向比对。
- **预期**：轻微笑 .22 → joy ~0.8（主壳表第 3 行翻 ✓）；抿嘴笑 .40 强度 0.396 → ~0.9。
- **资源**：1 轮。**验收**：face_discrim 全 PASS + 新增低强度用例（0.12~0.45 五档×六类）全 ✓；
  core_capability N2 只升（31/31 起步）。**时间**：T+3 天。

## S2 弱信号档输出（界面，修 A4 体感）

- **步骤**：`read()` 加 `weak` 标记（top∈[0.08,0.26) 且不 confident）；app.js paintHud/faceChipHtml
  出「轻微 X（读数仅供参考）」三态文案。
- **预期**：轻表情有可见反馈；"必须明显表情"体感消除。
- **资源**：1 轮。**验收**：browser_check 全 PASS；三态文案截图留档。**时间**：T+5 天。

## S3 anger 复标 + 专注区分（算法，修 A5/A1）

- **步骤**：anger 加 browInnerUp −0.5（第二 AU 分焦虑/专注与愤怒）；用 S4 首批 20 张照扫
  browDown∈[0.15,0.35] 区间，中点取值。
- **预期**：轻紧锁眉 .20 → anger ✓；专注（browDown .3 + innerUp .3）→ calm ✓。
- **资源**：1 轮（依赖 S4 数据）。**验收**：12 条 anger 低强度/专注对照全 ✓；误报不高于 r103 水位。
  **时间**：T+10 天。

## S4 真照片 AU 批跑尺（工程地基，修 D4/E1）

- **步骤**：① 建 `_test/face_au_replay_check.py`：读 `_test/face-au/*.json`（52 维向量+标注+质量标签）
  → node 复算 `FaceEngine.read()` → 分场景 top-1 统计；② face-harness 在 Chrome 跑首批 20 张标注照
  导出 AU JSON（**只存参数不存图**，守隐私）；③ 接入电池 SUITES。
- **预期**：真实流准确率首次有常驻尺子；先量基线（预估 60~75%）再谈提升。
- **资源**：1 轮 + 20 张照（1~2h 标注）。**验收**：判据 rc=0；基线写回 10-core-capabilities。
  **时间**：T+7（首批）/ T+28（120 张）。

## M1 权重复标 + sadness 拍板（中期主线，修 A6/D2）

- **步骤**：标注集扩 120~200 张 → 逐类扫权重区间（r103 方法：6/6 档全过取中点）→
  sadness 担忧面复标（browInnerUp/jawOpen）→ 老大拍板后落 rules 注释 + 07 台账。
- **预期**：担忧 .55/.80 不再误报低落；八类权重全部有真照支撑。
- **资源**：2 轮 + 标注 4~6h。**验收**：有把握帧 top-1 ≥95%；担忧负样本 ≥8 条全 ✓。
  **时间**：T+28 天。

## M2 质量门复标 + 演示模式（修 E3/E4）

- **步骤**：标注照批跑亮度/方差/yaw 分布 → 重标 bright/blurVar/yaw；`?faceMode=demo` 预设
  （放宽亮度窗 + 文案升档）。
- **验收**：暗光/侧脸下"仅供参考"误命中降 ≥50%（S4 尺前后对账）。**时间**：T+21 天。

## ✅ 轮132 交付（S4 尺 + 延迟埋点）

S4 真照片尺已建：`face_au_export.py`（只存参数不存图）+ `face_au_replay_check.py`（纯 node 进电池）。实测真照片 12 张 top-1 100%、有把握帧 10/12；⚠️**语料全表演级强度、零低强度**，sadness/fear/disgust/contempt 零真照 ⇒ **S1 靶场仍只靠 F12**。

## ✅ r161 交付（S1 = 弱信号诚实化；S2 文案同轮落地）

**路线变更记录（重要，防后人重走弯路）**：part2 原定 S1 = 「动态分母」，r161 执行轮用一次性探针
（`_temp/face_dyndenom_probe.mjs`，已 gitignore）对 7 个候选设计（门 0.18/0.21 × 激活数 ≥1/≥2 ×
按类开关 × 无证据不笃定）在 F11 全量 CASES + F12 45 格上实跑对比，**全军尽没**：

| 候选 | F11 红项 | F12 笃定错报 | 致命伤 |
|---|---|---|---|
| base（不动） | 0 | 8 | — |
| d1 门0.18/≥1（part2 原案） | **13** | 11（更差） | lips_pressed 虚报 anger、joy/disgust 平局抢赢、饱和率 34.6% 击穿 15% 红线、②d 序差归零 |
| d2 门0.21/≥1 | 11 | 11 | 同上 |
| d3 门0.21/≥2 | 8 | 16（更差） | 同上 + speaking 误报 |
| d4 d3+关 fear/surprise | 4 | 11 | disgust→joy、contempt→joy、饱和 23.1% |

**根因**：动态分母把「加权平均激活度」变成「激活 AU 的平均强度」——lips_pressed 只激活
anger 的正权 AU（mouthPress）⇒ anger 虚高；joy 与 disgust 互吃对方正权子集 ⇒ 平局抢赢；
中低强度即顶满 ⇒ 饱和率爆。**方差放大而无信息增益**，不是调参能救的。
⇒ 改走本机制：**scores 一个数不改，只修 read() 的"笃定"语义**（weak 翻转）。
⇒ F11 饱和率/单调性/序差/绝对分全部零影响（实测 sat 10.3% 不变），回归面极小。

**落地清单**（src + deploy 同步，SHA256 三类归零；voice-call.css DIFF 属并行会话半成品，按台账不代同步）：
1. `src/data/face-smile-rules.js`：新增 `weak` 块（on/off/onByEmo/offByEmo + 窄缝标定注释）
2. `src/js/face-engine.js` `read()`：最高非 calm 分量落入 [on,off) ⇒ calm 赢身份时翻该情绪、
   标 weak、强制不笃定；intensity 改用翻转后主情绪的分数
3. `src/js/app.js`：paintHud / faceChipHtml / divergenceHtml 三处出「轻微 X（读数仅供参考）」三态文案
4. `_test/face_discrim_check.py`：selftest 加反例 13（joy.off→0.20 ⇒ joy_weak 必须红）/
   反例 14（surprise.on→0.09 ⇒ speaking 必须红）——weak 参数被回调必被抓

**窄缝标定（扫出来的，非拍脑袋；扫描器 = _temp 探针定线模式）**：
on=0.10（上界 speaking.surprise .12）；onByEmo.surprise=0.13（同 .12，按类抬高，
否则全局 on 接不住 sadness@0.12 .106）；offByEmo.joy=0.15（上界 joy_weak .167）；
offByEmo.sadness=0.22（上界 worry_light_A .25，下界 sadness@0.22 .195）；
offByEmo.surprise=0.20（上界 worry_speak_B1 .243，下界 fear@0.22 格的 surprise .166）；
全局 off=0.26（旧注释"top≥0.26 才翻得出 calm"同源线）。

**验收数（r161 实跑）**：
- F11：分类 25/25、8 类、饱和 2/78（2.6%）、低置信 5 条；selftest 15/15 反例全抓
- F12：笃定错报 **8→1**、有把握帧命中 **78.4%→96.7%**（≥95% 目标线触达）、不确定 33.3%（≤30% 未达，只点名不判红）；基线已 --update 写回
- N2 单测 31/31；N1 无回归；F1 vendor rc=0
- **遗留 1 格**：fear@0.12 笃定错报——fear 的 need:2 多区惩罚把 fear 自分压到 surprise 之下
  ⇒ 该格 wt=surprise .09 < on 不翻。fear 的 need 与低强度段结构冲突，归 S3/M1 复标。
- 未修仪器（登记）：browser_check UNVERIFIED（开场 done 态 15s 超时，scroll-story 路径，
  与 face 零关联，同族 R105-02/159）。
- **A0 仪器已修（r162，commit 778b70b）**：core_capability N2 UNVERIFIED 根因 = node 22/24 在
  非 TTY 子进程捕获下默认输出 TAP reporter（`# tests 31`），而 parse_node_test 旧正则只认
  spec 的 `ℹ tests 31` ⇒ rc=0 全过却解析不到汇总行。修法 = 正则双格式兼容
  `^(?:ℹ|#)\s+tests\s+(\d+)`（re.M 行首锚定，防 TAP 失败 YAML 块缩进注释误匹配）+
  parse_selftest 4 腿反例。验收：CORE-CAP-BASELINE-PASS（N2 31/31 fail=0）+
  PARSE-SELFTEST 4/4 + SELFTEST 12/12。N2 从"下轮修"转为常驻可验尺。
- **nlu 扩集对账 + 判据自洽修复（r163）**：105 条评测集固化进基线——pass_cases 104 道 +
  miss_at_baseline 1 道（「整个人都不好了」→sadness）= 全集 105，三件套自洽（复跑
  CORE-CAP-BASELINE-PASS，回归口径 0/104）。顺带修掉 `--update` 写入端与 ratchet 自洽判据
  的隐藏矛盾：写入端写 `pass=全集−miss`（104）而判据要求 `len(pass)==denom`（105）⇒
  带 miss 的基线一重建就自锁变红（r111 建立时全过 85==85，缺陷潜伏至今，今天首次带 miss
  重建才暴露）。判据改双格式：有 miss_at_baseline ⇒ 校验 `pass∪miss=全集 且互不交`；
  无 ⇒ 旧格式 `pass=分母`。selftest 12→14 腿（新格式绿腿 + 交叠红腿）。miss 题词表修复
  归语意轮（emotion-lexicon.js 在途改动避让）。
- **S3 资料准备（r164）**：渠道全摸底 + 可检出性实测 + 补拍规格定稿。
  - **渠道矩阵（本轮实测）**：①Commons 分类面二次证伪（Category:Anger 32 文件含音频/路线图/
    头盔/画作，真人照个位数；Rage/Snarl 近乎空）；②face-api.js 挖尽（仅 angry×2）；③HF
    `LaurenGurgiolo/9_Facial_Expressions`：anger **350 张**，但 80×80 + Alamy 图库水印 +
    授权链模糊（Roboflow 二次聚合）⇒ 定级**备选**（仅本机标定、绝不入 git）；④JAFFE 镜像
    无完整集，放弃。
  - **MediaPipe 可检出性实测**（探针 `_temp/s3_mediapipe_probe.py`，msedge channel）：
    80×80 候选 **3/3 检出**；browDown 分布 0.094 / 0.286 / 0.5+（有区分度）；引擎判定
    anger 1/3、disgust 2/3——**正好印证 S3 修因**（browDown 强信号被判成 disgust）。
  - **网络通道**：外网请求一律显式走代理 `127.0.0.1:7897`（裸连被吸入本地 56070 死链路
    超时；GitHub 走 api/gh、HF 走 7897 实测通）。
  - **补拍规格书（给老大，全程 10 分钟可拍完）**：目标 anger ≥8 张（低强度 4 + 中强度 4；
    低强度自然版最宝贵——S1 弱信号主题直接需要）；可选加拍 fear/disgust 各 4 张（现零真照）。
    拍法：手机前后置皆可、光线正常、正脸或轻侧（yaw ≤15°）、距 30~50cm、背景随意。
    表情参考：低强度＝想着烦心事、眉微压唇抿紧；中强度＝皱眉瞪眼。隐私：照片放本机
    **不入 git**（T+10 前补 `face_au_export --fixtures-dir` 支持：本机目录独立名册、
    只入库 52 维 JSON）。
- **S3 执行完成（r165，commit 836aff4）**：anger 复标落地 = `weights.anger.browInnerUp:-0.5`
  + `weak.offByEmo.anger:0.23`（窄缝标定：上界=专注负权后 .253、下界=轻锁眉 .205，中点 .229→.23）。
  机制要点（实测推翻两个直觉）：①`scores()` 分母只计**正权重**、负权只减分子——"负权撑大母数
  压低所有正项"的猜测不成立（改前用单点分解验证）；②weak 机制是 S3 的**真正闸口**——专注
  场景 calm 赢身份后，anger 分落 [on,.26) 会被翻回 anger，**单改负权只把"笃定错"降级成
  "不笃定的错"**，必须配套 offByEmo.anger 定线。验收全绿：F11 26/26+selftest 16/16
  （新增反例15：负权被删必抓）；F12 50 格 PASS（旧 45 格账目零变化）+ selftest 6/6；
  N2 31/31；core 基线 PASS；replay 1.0；真照 29 HF 仅 1 张边界图转"含糊不报"、12 夹具零变化。
  附带修 F12 update 自锁（「格数变更须重建」与"重建被 bad 拦死"——与 r163 core 同族缺陷，
  格数项已豁免、其他真回退仍拦）。导出腿 `--fixtures-dir` 扩展亦在此轮实战验证（29/30 检出、
  1 张 SKIPPED 单列）。

## 回滚锚（通用）

规则改动独立 commit（revert 即回滚）；`face-smile-rules.js` 开关默认 false 起步、灰度参数放 src 版；
deploy 三类归零才发布；AU JSON 与照片分离存放（照片只在标注者本机）。
