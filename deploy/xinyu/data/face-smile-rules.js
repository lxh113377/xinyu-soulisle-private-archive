/* 心屿 · 面部表情判据（单一真相源）
 *
 * 映射对象：MediaPipe FaceLandmarker 的 52 维 blendshape（近似 FACS 的 AU）。
 * 判据的**标定依据与踩坑记录**在 memory/05-feature-status r102 段与 memory/07-next-steps，
 * 本文件只留**判据值 + 一行为何**；改阈值前先读那两处，别凭直觉调。
 *
 * 红线：crisis 恒 false —— 表情既不判危机，也不解除危机（危机只由文本决定）。
 */
window.__XINYU_FACE_RULES__ = {
  version: "2.0",
  generated: "2026-10-10",

  /* 可输出的表情（8 类）。顺序即平分时的兜底顺序。 */
  emotions: ["joy", "sadness", "anger", "fear", "surprise", "disgust", "contempt", "calm"],
  /* 不可由表情判定的情绪：界面必须如实说明，不能靠表情猜 */
  undetectable: ["love"],

  /* 界面文案。文本六类的名字仍走 EmotionEngine.labelOf（那边是双端 SSOT），
     这里只给**表情侧独有**的三类补名字 —— 放这里而不是 emotion-lexicon.js，
     就是为了不把只用于表情的词条灌进 JS/Java 共用的词表。 */
  labels: { surprise: "惊讶", disgust: "厌恶", contempt: "轻蔑" },

  /* 与文本六情绪的语义归属：分歧标注据此对齐，避免"表情说 contempt、文字无此类"变成噪声。
     只做映射，不新增文本情绪 —— emotion-lexicon.js 是 JS/Java 双端 SSOT，不在本文件动。
     表情侧 8 类 ≠ 文本侧 6 类是刻意的：可辨识上限由 blendshape 决定，r102 实测
     disgust/surprise 不新增类就会被判成 anger/fear。 */
  family: {
    joy: "joy", sadness: "sadness", anger: "anger", fear: "fear", calm: "calm",
    surprise: "fear", disgust: "anger", contempt: "anger"
  },

  /* 表情侧独有三类的自持色（文本六类仍走 EmotionEngine.colorOf，避免两份色值漂移）。
     色相避开既有六色（≥40°），同色相段靠明度/饱和度拉开。 */
  colors: {
    surprise: [0.30, 0.92, 1.00],
    disgust:  [0.72, 0.80, 0.25],
    contempt: [0.74, 0.47, 0.78]
  },

  /* 峰值基准：满强度时该情绪的平均正权 AU 激活度。
   * ⚠️ 语义在 r102 变过：旧版是 `norm: 0.45`（除以它就是饱和点，实测 25% 的帧顶满 1.0，
   *   "笑得很大"与"笑到极致"读数一样）。现改为除以 peak，强度随真实表情线性铺开。
   * peak=0.60 由 F11 实测标定：饱和 0%、17/17 分类命中。⚠️ 社交笑 margin 很薄，
   * 改 peak 前先跑 `python _test/face_discrim_check.py`。 */
  peak: 0.60,

  /* 各情绪的 blendshape 权重。负权 = 反向证据。r102 重标三处易混对：
   *   ① disgust/anger 靠 **上唇上提**分（disgust +0.8 / anger −0.5）；
   *   ② surprise/fear 靠 **下颌方向**分（竖直张口 vs 横向拉唇），并用 browDown 一正一负：
   *      恐惧皱眉(AU1+2+4)、惊讶平滑上抬(AU1+2) —— 这是 fear 能判出来的唯一分水岭；
   *   ③ contempt/joy 靠**眼周是否参与**分（见下方 asym）。 */
  weights: {
    joy: {
      mouthSmileLeft: 1.0, mouthSmileRight: 1.0,
      cheekSquintLeft: 0.5, cheekSquintRight: 0.5,
      mouthDimpleLeft: 0.3, mouthDimpleRight: 0.3,
      mouthUpperUpLeft: 0.2, mouthUpperUpRight: 0.2,
      mouthFrownLeft: -0.6, mouthFrownRight: -0.6,
      mouthPressLeft: -0.5, mouthPressRight: -0.5
    },
    sadness: {
      /* r103 重标：主证据从 mouthFrown 换成 browInnerUp，并新增「张嘴即非悲伤」反向证据。
       * 一手实测（Commons 目检后的真悲伤照，走真 MediaPipe）：
       *   真悲伤#1  browInnerUp .85  browOuterUp .60/.34  mouthFrown .13/.09  jawOpen **0**
       *   真悲伤#2  browInnerUp .98  browOuterUp .88/.85  mouthFrown .27/.20  jawOpen **0**
       * 旧权重把 mouthFrown 当 1.0 主证据 => 真悲伤只得 0.18/0.52，被 surprise 抢走
       * (surprise 0.47/0.69) => sadness 2/2 全错（与 anger 同构的漏判）。
       * ⚠️ 这里有一个**我自己的错误记录，按实测更正**：本注释首版写「分水岭是 jawOpen（真惊讶
       *   .82/.83、真悲伤 .00）⇒ 把张嘴=惊讶写进权重」，并赋了 jawOpen:-1.9。但逐项拆开实测
       *   （_test 侧 sad_which 同手法）：把 jawOpen 整行**删掉**或**归零**，两组真悲伤的
       *   sad/surprise 分一字不变（0.629/0.468、0.781/0.691）⇒ **它不是分水岭，是摆设**。
       *   真正 load-bearing 的是 browInnerUp:1.2（降回 0.7 立刻漏判真悲伤#2）。
       *   jawOpen:-1.9 的真实作用（**代价面实测后补全**，上一轮这段只写了一半）：
       *   主判上它确实不是分水岭（见上一段）；但在**代价面**上它是 ——
       *   browInnerUp 逐档扫「担忧/专注」形态：.40 → calm ✓ / .55 / .70 / .80 → sadness ✗；
       *   而「担忧+说话」(innerUp .55 + jawOpen .40) → **calm** ✓、
       *   「担忧+抿唇」(innerUp .55 + press .40) → **sadness** ✗。
       *   ⇒ 说话时 jawOpen 被顶起来，把读数拉回平静：**jawOpen 管的是代价面，不是主判**。
       * ⚠️ 代价面现状（**未经老大拍板，别当已解决**）：担忧轻 innerUp .40 不误报；
       *   **担忧中/重/很重（innerUp .55–0.80）会误报成低落**。与 anger 那次同构，
       *   但 anger 是老大拍板的取舍、sadness 这次没拍板 ⇒ 未改判据，登记在 07-next-steps。
       * ⚠️ 参数是扫出来的，但**不是窄峰拟合**：jawOpen∈[-2.1,-1.7] 与 browInnerUp∈[1.5,0.9]
       *    各 6/6 档位全 10/10（train 4 张真照 + holdout 6 条合成/混合样本）=> 结构支撑。
       *    取区间中值 jawOpen=-1.9 / browInnerUp=1.2。
       * ⚠️ 与 anger 的区别：anger 是老大拍板的取舍，**sadness 这次未经拍板** ——
       *    更弱的输入会不会误报低落尚未实测。上线前先补「专注/担忧」标注样本，见 07-next-steps。 */
      browInnerUp: 1.2,
      mouthFrownLeft: 0.4, mouthFrownRight: 0.4,
      mouthLowerDownLeft: 0.3, mouthLowerDownRight: 0.3,
      eyeSquintLeft: 0.3, eyeSquintRight: 0.3,
      jawOpen: -1.9,
      mouthSmileLeft: -0.7, mouthSmileRight: -0.7,
      cheekSquintLeft: -0.2, cheekSquintRight: -0.2
    },
    anger: {
      /* r103：browDown 1.0 → 1.4，鼻翼 0.55 → 0.35、抿唇 0.5 → 0.3、下颌前推 0.4 → 0.3。
       * 理由：真人发怒实测**只有压眉**（其余 AU 全 0），原先 noseSneer/press 权重高，
       * 那些维度不激活就把分摊母数撑大、真实分数被压到 calm 之下。抬高主证据、压低
       * 辅助证据的母数，等于让"只有压眉"这一种真实形态也能拿到足够分数。 */
      browDownLeft: 1.4, browDownRight: 1.4,
      noseSneerLeft: 0.35, noseSneerRight: 0.35,
      mouthPressLeft: 0.3, mouthPressRight: 0.3,
      jawForward: 0.3,
      jawOpen: 0.15,
      mouthUpperUpLeft: -0.5, mouthUpperUpRight: -0.5,
      mouthSmileLeft: -0.6, mouthSmileRight: -0.6
    },
    fear: {
      eyeWideLeft: 1.0, eyeWideRight: 1.0,
      mouthStretchLeft: 0.7, mouthStretchRight: 0.7,
      browInnerUp: 0.5,
      browDownLeft: 0.4, browDownRight: 0.4,
      jawOpen: 0.25,
      mouthPressLeft: 0.3, mouthPressRight: 0.3
    },
    surprise: {
      browInnerUp: 1.0,
      browOuterUpLeft: 0.8, browOuterUpRight: 0.8,
      eyeWideLeft: 0.8, eyeWideRight: 0.8,
      jawOpen: 0.7,
      mouthStretchLeft: 0.3, mouthStretchRight: 0.3,
      mouthFunnel: 0.2,
      browDownLeft: -0.6, browDownRight: -0.6,
      mouthPressLeft: -0.4, mouthPressRight: -0.4
    },
    disgust: {
      noseSneerLeft: 1.0, noseSneerRight: 1.0,
      mouthUpperUpLeft: 0.8, mouthUpperUpRight: 0.8,
      mouthLowerDownLeft: 0.5, mouthLowerDownRight: 0.5,
      mouthShrugUpper: 0.3,
      mouthSmileLeft: -0.8, mouthSmileRight: -0.8,
      browDownLeft: -0.5, browDownRight: -0.5
    },
    contempt: {
      mouthDimpleLeft: 1.0, mouthDimpleRight: 1.0,
      mouthSmileLeft: 0.4, mouthSmileRight: 0.4,
      jawOpen: 0.2,
      cheekSquintLeft: -0.6, cheekSquintRight: -0.6,
      mouthFrownLeft: -0.5, mouthFrownRight: -0.5
    }
    /* calm 不进 weights：它是"其余都不高"的残余量，见 calm.baseline */
  },

  /* 多线索佐证：一类情绪须由 ≥need 个**独立区域**同时作证，单区则按 penalty 打折。
   * 修的是「专注时压眉(AU4)被读成愤怒」这个假阳性 —— 加权求和本身不要求区域佐证。
   * ⚠️ 默认是 1（不打折），只有下方 need 点名的三类强制多区。曾把默认值写成 2，
   *   结果 joy 也被要求两区，而"社交性微笑按定义就是只有口部参与"⇒ 强颜欢笑被判成 calm。
   *   别只让 joy 过一关就以为对了：social smile 的 Duchenne 三态另有判据兜着。 */
  cues: {
    brow: ["browDownLeft", "browDownRight", "browInnerUp", "browOuterUpLeft", "browOuterUpRight"],
    eye:  ["eyeWideLeft", "eyeWideRight", "eyeSquintLeft", "eyeSquintRight",
           "eyeBlinkLeft", "eyeBlinkRight", "cheekSquintLeft", "cheekSquintRight"],
    nose: ["noseSneerLeft", "noseSneerRight"],
    mouth:["mouthSmileLeft", "mouthSmileRight", "mouthFrownLeft", "mouthFrownRight",
           "mouthPressLeft", "mouthPressRight", "mouthUpperUpLeft", "mouthUpperUpRight",
           "mouthLowerDownLeft", "mouthLowerDownRight", "mouthDimpleLeft", "mouthDimpleRight",
           "mouthFunnel", "mouthPucker", "mouthStretchLeft", "mouthStretchRight",
           "mouthShrugLower", "mouthShrugUpper", "mouthRollLower", "mouthRollUpper",
           "mouthClose", "jawOpen", "jawForward"]
  },
  cue: { min: 0.18, penalty: 0.5 },
  /* 需要多区佐证的情绪。**anger 已移出**（r103 老大选定「乙」）：
   *   原先 anger 在此，是因为压眉(AU4) 是"专注思考"的常态表情，单眉区就判愤怒是假阳性。
   *   但 r103 用 face-api.js 的**真实愤怒照**实测发现：真人发怒的 AU 分布是
   *   **browDown 0.64/0.59 而其余全 0**（无鼻翼/抿唇/张口/眼睁大）——
   *   也就是说「真愤怒」与「专注轻皱(0.40)」在 blendshape 空间里**结构完全相同，只有幅度差**。
   *   要求第二区 ⇒ 真愤怒永远判不出来（F12 实测 anger 0/2）。
   *   ⇒ 老大拍板走「保真怒」：anger 不再要求多区，代价是**专注/说话时可能闪一下烦躁**。
   *   实测代价面（合成负样本）：专注轻皱 .40 → anger 0.41、说话+微皱 .30 → anger 0.33、
   *   更轻的皱 .25 → calm（不误报）。fear/sadness 仍保留多区要求（它们吃 browInnerUp，
   *   而惊讶/担忧也吃 browInnerUp，误报面比 anger 大得多）。
   *   ⚠️ 若日后拿到「专注/中性」的**标注照片**，应回来复标这条 —— 现在它靠的是定性论证。 */
  need: { fear: 2 },

  /* 轻蔑靠**左右不对称**识别，加权和表达不了（对称项两侧同权，单/双侧笑在权重空间同点）。
     不达标时 contempt 直接归零 —— 否则对称笑会被 contempt 抢走。 */
  asym: { mouthSmile: ["mouthSmileLeft", "mouthSmileRight"], min: 0.25 },

  /* 强度增益：残余量 calm 天生接近 1，压到 0.6 免得"面无表情"被读成强烈平静 */
  gain: { joy: 1.0, sadness: 1.0, anger: 1.0, fear: 1.0, calm: 0.6,
          surprise: 1.0, disgust: 1.0, contempt: 1.0 },

  /* calm 基线：最强非平静分量达到 0.35 时，平静分归零 */
  calm: { baseline: 0.35 },

  /* 次情绪采纳线：与 EmotionEngine.secondaryOf 同口径（≥ 主情绪 40% 且自身够强） */
  secondary: { ratio: 0.4, floor: 0.12 },

  /* 置信度 = 主分 − 次分（margin）。r102 加：旧版每帧都硬给一个情绪、没有"看不出来"
   * 的出口（实测强度 p25 仅 0.47 ⇒ 一半帧本就不确定却输出确定结论，表现为读数乱跳）。 */
  confidence: { on: 0.15, lowLabel: "读数不稳" },

  /* ── 质量门（r113「表情识别更抗造」）：画面本身靠不住时，读数只能当参考 ──────────
   * 四条信号全部来自本机已有的帧数据，零新增依赖（算术在 face-engine.js 的 assessQuality）：
   *   lighting=整帧平均亮度出窗（过暗/过曝，24×24 缩样）｜blur=缩样灰度方差过低（画面糊）
   *   profile=鼻尖偏离面部中线的比例过大（侧脸）｜mouth-flat=嘴部 blendshape 连续 N 样本趋零
   *   （口罩/捂嘴嫌疑 ⇒ 嘴部判据停用，微笑三态给「看不清」）
   * ⚠️ 标定债：阈值是首版保守值，未按标注照复标（与 ratioOn 的 4 张样本同族债务）；
   *   命中质量门只降置信+改文案，不参与任何确定性结论。 */
  quality: { brightMin: 0.16, brightMax: 0.94, blurVarMin: 0.0045,
             yawMax: 0.36, mouthFlat: 0.02, mouthFlatSamples: 10 },

  /* ── 强颜欢笑判据（Duchenne）───────────────────────────────────────
   * 老师提的验证难题：「表情大笑，怎么知道是真开心还是强颜欢笑」。
   * 心理学口径：真笑（Duchenne）= 口部 AU12（颧大肌）**且**眼周参与 AU6/AU7；
   * 社交性微笑只有口部。于是判据不是"笑得多大"，而是"眼周参与 / 口部微笑"的比值。
   * ⚠️ ratioOn=0.20 是**实测标出来的**：首版 0.45 被 4 张真笑照当场证伪（实测比值
   *   0.269~0.326，会把真笑全判成强颜欢笑）。样本量仅 4，扩样本必须复标。
   * 阈值全在本块，`_test/face_check.py` 拿标注样本集复跑同一条链；阈值若不参与计算会判红。 */
  smile: { smileOn: 0.35, ratioOn: 0.20, tensionOn: 0.30 },

  /* 时序：EMA 平滑（α=0.3）防读数抖动；实时采样 8fps（不每帧推理，省电省热） */
  smooth: { alpha: 0.3 },
  sample: { fps: 8, minSamples: 3 },

  /* 表情读数有效期：超过这个时长没新读数，就当没有表情（不拿旧脸去标新话） */
  freshMs: 3000
};