# -*- coding: utf-8 -*-
"""F11 · 表情判据**分类判别力**尺（r102 新增）

为什么需要这把尺（不是"补个测试"这么轻）：
  r87 建的表情判据只有 F5 一条腿，而 F5 只验「微笑组 vs 中性组的口部分离」——
  **七类里只碰了 joy 和 calm 两类**，sadness/anger/fear 的权重从没被真实数据校过。
  于是 r102 一上手就实测出三个硬事实：
    ① disgust 与 surprise **根本判不出来**（被判成 anger 0.47 / fear 1.00）；
    ② 「专注时压眉」被判成 anger 0.39，压过平静（假阳性）；
    ③ 强度分布 25% 的帧顶满 1.0 ⇒ 中高强度段没有分辨力。
  三条都不是 F5 能抓的。所以这把尺问的是**分类判别力**：
    - 跨类混淆矩阵（哪些类互相抢）
    - 负样本假阳性率（「专注/说话/眨眼」必须判 calm）
    - 强度单调性（同一类逐步增强，强度必须单调升 —— 治饱和）
    - 置信度可分性（margin 低的帧必须能被标成"读数不稳"）

⚠️ 本尺的**已知局限**（写在文件里，防后人当成准确率）：
  输入是 FACS 动作单元的**合成向量**，不是真实照片。它验的是「判据结构是否有判别力、
  阈值是否参与计算」，**不能**当成真实场景准确率。真实照片那一层由 F5 承担（8 张 Wikimedia
  授权照片，smile/neutral 两类）。要补 anger/sadness/fear 的真实照片，需要人工标注，
  不是本尺能替代的 —— 这个缺口已登记在 memory/07-next-steps。
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ── 标注向量集（FACS AU 语义 → blendshape 名字）────────────────────────────────
# 每条 = (向量, 期望主情绪, 用途)。用途 tag 让失败时能点名是哪一类问题。
CASES = [
    # ── 正样本：七类各自的典型 AU 组合 ──
    ("joy", {"mouthSmileLeft": .8, "mouthSmileRight": .8, "cheekSquintLeft": .6,
             "cheekSquintRight": .6, "eyeSquintLeft": .5, "eyeSquintRight": .5}, "joy"),
    ("social_smile", {"mouthSmileLeft": .6, "mouthSmileRight": .6,
                      "cheekSquintLeft": .05, "cheekSquintRight": .05}, "joy"),
    ("sadness", {"mouthFrownLeft": .8, "mouthFrownRight": .8, "browInnerUp": .6}, "sadness"),
    ("crying", {"mouthFrownLeft": .9, "mouthFrownRight": .9, "browInnerUp": .85,
                "eyeSquintLeft": .6, "eyeSquintRight": .6}, "sadness"),
    # r103 新增：**真脸实测形态**。Commons 目检后的真悲伤照（走真 MediaPipe）：
    #   真悲伤#1 browInnerUp .85 / browOuterUp .60/.34 / mouthFrown .13/.09 / jawOpen **0**
    #   真悲伤#2 browInnerUp .98 / browOuterUp .88/.85 / mouthFrown .27/.20 / jawOpen **0**
    # 合成向量给 sadness 配了 0.8 的 mouthFrown，真实照片里那两维只有 0.1~0.27 ——
    # 正是这个差别让旧权重漏判（被 surprise 抢走）。
    ("sad_real_1", {"browInnerUp": .85, "browOuterUpLeft": .60, "browOuterUpRight": .34,
                    "mouthFrownLeft": .13, "mouthFrownRight": .09,
                    "eyeSquintLeft": .15, "eyeSquintRight": .18}, "sadness"),
    ("sad_real_2", {"browInnerUp": .98, "browOuterUpLeft": .88, "browOuterUpRight": .85,
                    "mouthFrownLeft": .27, "mouthFrownRight": .20,
                    "eyeSquintLeft": .2, "eyeSquintRight": .25}, "sadness"),
    ("anger", {"browDownLeft": .85, "browDownRight": .85,
               "noseSneerLeft": .6, "noseSneerRight": .6}, "anger"),
    # 真愤怒的**实测形态**（r103 从 face-api.js 真照跑出来的 AU，非教科书最大值）：
    # 只有压眉，其余全 0。教科书向量给 anger 配了鼻翼+抿唇，看起来很强，
    # 但真实照片里那两维根本是 0 —— 正是这份差别让旧权重漏判（详见 need 字段注释）。
    ("anger_real", {"browDownLeft": .64, "browDownRight": .59}, "anger"),
    ("fear", {"eyeWideLeft": .8, "eyeWideRight": .8, "jawOpen": .6, "browInnerUp": .5,
              "browDownLeft": .3, "browDownRight": .3}, "fear"),
    ("surprise", {"jawOpen": .8, "browInnerUp": .8, "browOuterUpLeft": .7,
                  "browOuterUpRight": .7, "eyeWideLeft": .5, "eyeWideRight": .5}, "surprise"),
    ("disgust", {"noseSneerLeft": .7, "noseSneerRight": .7,
                 "mouthUpperUpLeft": .6, "mouthUpperUpRight": .6}, "disgust"),
    ("contempt", {"mouthSmileLeft": .85, "mouthSmileRight": .10,
                  "mouthDimpleLeft": .9, "mouthDimpleRight": .10}, "contempt"),
    ("neutral", {}, "calm"),
    # 弱强度回落：同一个 joy 向量压到很弱时，主情绪**理应**退回 calm
    # （"看不出情绪"就该说平静，不是硬报一个弱 joy）。这条不是判 calm 对不对，
    # 而是给下面的 sweep 口径定基准：argmax 身份翻成 calm 是合法的，只有**分数**非单调才是缺陷。
    ("joy_weak", {"mouthSmileLeft": .2, "mouthSmileRight": .2}, "calm"),
    # ── 负样本：这些**不是情绪**，判错就是假阳性 ──
    # ⚠️ r103 的两处改法，理由见下面 POSITIVE 里的 concentrating_note，勿"顺手"改回去：
    #   concentrating / speaking_frown 现在**预期判 anger**（老大拍板「保真怒」的已知代价），
    #   它们不再是"必须判 calm"的负样本。判据仍盯着它们 —— 只是盯的内容从
    #   「不许误报」变成「**不许比真愤怒更凶**」（见 KEEP_BELOW）。
    ("speaking", {"jawOpen": .5, "mouthFunnel": .3}, "calm"),
    ("blinking", {"eyeBlinkLeft": .9, "eyeBlinkRight": .9}, "calm"),
    ("looking_down", {"eyeLookDownLeft": .8, "eyeLookDownRight": .8}, "calm"),
    ("lips_pressed", {"mouthPressLeft": .4, "mouthPressRight": .4}, "calm"),
    # 专注/说话：已知会误报 anger，但强度必须**低于真愤怒**，否则"专注"读数与"真发怒"读数
    # 无法区分，代价就从"闪一下红"升级成"骗人"。
    ("concentrating", {"browDownLeft": .4, "browDownRight": .4}, "anger"),
    ("speaking_frown", {"jawOpen": .4, "browDownLeft": .3, "browDownRight": .3}, "anger"),
    # ── 「乙」取舍的已知代价（r103 老大拍板「保真悲」）──
    # 真悲伤 2/2 换来的代价是「担忧中重误报低落」。这两条是**代价面样本**：
    # 它们现在**预期判 sadness**（不是漏报），但它们的存在让代价在判据里可见，
    # 而不是只活在注释里。真正不许跨的是下面两条边界：轻担忧、边担忧边说话。
    ('worry_mid   r103 代价', {"browInnerUp": .55}, "sadness"),
    ('worry_heavy r103 代价', {"browInnerUp": .70}, "sadness"),
    # 边界 A：**轻担忧不得误报**（实测 innerUp .40 → calm，离 sadness 线有 0.10 余量）
    ("worry_light_A", {"browInnerUp": .40}, "calm"),
    # 边界 B：**边担忧边说话不得误报**（实测 jawOpen .40 把 sad 分全压到 0 ⇒ calm）
    ("worry_speak_B1", {"browInnerUp": .55, "jawOpen": .40}, "calm"),
    ("worry_speak_B2", {"browInnerUp": .70, "jawOpen": .40}, "surprise"),
]

# 真愤怒 vs 专注轻皱的**强度序**：真愤怒必须更凶，否则 anger 这一路分不出"真怒"与"专注"。
KEEP_BELOW = [("concentrating", "speaking_frown", "anger_real")]

# 强度扫描档位（测单调性 / 饱和）
SWEEP = [.25, .40, .55, .70, .85, 1.00]
# sweep 只跑「本身就以某情绪为标签」的向量。排除两类，理由写在这里防后人"顺手补回去"：
#   - 负样本（concentrating 等）：它们追踪的类是 calm，而 calm 是**残余量**，
#     按定义随 top 单调反向，用它判"某情绪分数单调"是判错了对象。
#   - joy_weak：它的标签是 calm，同上。
POSITIVE = [c for c in CASES if c[0] not in (
    "concentrating", "speaking_frown", "speaking", "blinking", "looking_down",
    "lips_pressed", "joy_weak",
    # r103 代价面样本：worry_* 是「乙」取舍的**代价**，不是任何一类的正样本 ——
    # 用它们扫「某类分数随强度递增」是扫错了对象（它们量的类是随输入反向变的）。
    # 它们在 ②c/②d/②e 里各自有专门断言，不参与这项统计。
    "worry_mid   r103 代价", "worry_heavy r103 代价",
    "worry_light_A", "worry_speak_B1", "worry_speak_B2")]
# concentrating / speaking_frown 现在**预期判 anger**（r103 的已知代价），
# 它们的分数要参与 ②b 的「真怒必须更凶」比较，但不该混进"某类分数单调性"统计 ——
# 那项统计问的是"同一情绪随强度递增"，而它们不是 anger 的正样本。
# contempt 走**非对称门**（r102 加的），单侧向量整体缩放时两侧比值不变 ⇒
# 门一旦通过就恒通过，它的分数单调性与其它类不同口径，不参与单调性统计（但仍参与饱和率）。
SKIP_MONO = {"contempt"}
SAT_MAX = 0.15

# 饱和率上限 = 15%。**为什么不是 0%**（这条阈值本身是标出来的，不是拍的）：
#   本尺的 sweep 输入是**教科书最大值**的合成向量（AU 给到 0.8~1.0），
#   而真人脸的 blendshape 在自然表情下很少超过 0.6~0.7（这是 MediaPipe 模型的取值口径）。
#   实测：peak=0.60 时合成向量有 13% 顶满，但真笑照（F5，真实照片）实测 joy 分 0.65±，
#   远未触顶 ⇒ 「顶满」只发生在**比真人更极端**的输入上，不是中段被压平。
#   所以阈值定 15%：容许教科书极端向量触顶，但不允许判据在中段就崩成常量。
#   ⚠️ 若哪天把 sweep 换成真实照片，这个阈值必须重标（会显著变严）。

PROBE = r"""
import {readFileSync} from 'fs';
import {createContext, runInContext} from 'vm';
const ROOT = process.argv[2];
const S = (p) => readFileSync(ROOT + '/' + p, 'utf8');
const ctx = createContext({window: {}, console});
for (const f of ['src/data/emotion-lexicon.js', 'src/js/emotion-engine.js',
                  'src/data/face-smile-rules.js', 'src/js/face-engine.js']) runInContext(S(f), ctx);
const FE = ctx.window.FaceEngine;
const rd = (b) => JSON.parse(JSON.stringify(FE.read(b || {})));
const out = {cases: [], sweep: [], rules: ctx.window.__XINYU_FACE_RULES__.emotions};
for (const [name, vec, want] of CASES) {
  const v = rd(vec);
  /* pairs：全部情绪的分数快照。argmax 判据抓不到"分数关系变了"的缺陷（见 f11_bad ⑤），
     必须在探针里就把这一层取出来，Python 侧才判得了。 */
  const pairs = {};
  for (const x of v.all) pairs[x.emotion] = x.score;
  out.cases.push({name, want, got: v.emotion, intensity: v.intensity, pairs,
                  confidence: v.confidence, confident: v.confident,
                  smile: v.smile.kind, family: v.family});
}
for (const [name, base, want] of POSITIVE) {
  for (const s of SWEEP) {
    const scaled = Object.fromEntries(Object.entries(base).map(([a, b]) => [a, +(b * s).toFixed(4)]));
    const v = rd(scaled);
    /* 记「该类自己的分数」而不是 v.intensity —— 口径见 f11_bad ④ 的注释 */
    const score = (v.all.find((x) => x.emotion === want) || {}).score || 0;
    out.sweep.push({name, s, want, score, intensity: v.intensity, got: v.emotion});
  }
}
console.log(JSON.stringify(out));
"""


def run_probe():
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_f11_probe.mjs")
    with open(script, "w", encoding="utf-8") as fh:
        fh.write("const CASES = " + json.dumps(CASES, ensure_ascii=False) + ";\nconst SWEEP = "
                 + json.dumps(SWEEP, ensure_ascii=False) + ";\nconst POSITIVE = "
                 + json.dumps([[c[0], c[1], c[2]] for c in POSITIVE], ensure_ascii=False) + ";\n")
        fh.write(PROBE)
    try:
        p = subprocess.run(["node", script, ROOT], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=120)
    finally:
        try:
            os.remove(script)
        except OSError:
            pass
    if p.returncode != 0 or not (p.stdout or "").strip():
        return None, ["F11 node 探针跑不起来 rc=%s：%s" % (p.returncode, (p.stderr or "")[:300])]
    try:
        return json.loads(p.stdout.strip().splitlines()[-1]), []
    except Exception as e:  # noqa: BLE001
        return None, ["F11 探针输出解析失败：%s" % e]


def _probe_with(patch_text, tag):
    """把改坏的 rules 临时落到一个副本工程里，跑同一探针，看 F11 是否红。
    返回 (red, msg)：red=True=判据抓到了。（r117 自 selftest 嵌套升模块级：
    嵌套体行数计入 selftest 使其超 loc-guard 函数长门。）"""
    with tempfile.TemporaryDirectory() as td:
        for sub in ("src/data", "src/js"):
            os.makedirs(os.path.join(td, sub), exist_ok=True)
        for rel in ("src/data/emotion-lexicon.js", "src/js/emotion-engine.js",
                    "src/js/face-engine.js"):
            shutil.copy(os.path.join(ROOT, rel), os.path.join(td, rel))
        with open(os.path.join(td, "src/data/face-smile-rules.js"), "w", encoding="utf-8") as fh:
            fh.write(patch_text)
        save = ROOT
        try:
            globals()["ROOT"] = td
            data, errs = run_probe()
            if data is None:
                return False, tag + " 探针没跑起来：" + "; ".join(errs)
            got = f11_bad(data)
            return bool(got), tag + (" ⇒ F11 抓到了" if got else " ⇒ **F11 没抓到，判据无牙**")
        finally:
            globals()["ROOT"] = save


def _rule_case(real_rules, bad, tag, *pairs):
    """反例通用体：按 (旧, 新) 对依次替换规则片段，探针必须红。
    返回 1=探针实跑（selftest 据此累加 ran）/ 0=构造失败未跑（缺口记入 bad）；
    抓没抓到的结论在本函数内 print 并记 bad，收口行 F11-SELFTEST-PASS/FAIL 格式保持原样。"""
    m = real_rules
    for old, new in pairs:
        m = m.replace(old, new)
    if m == real_rules:
        bad.append(tag + " 构造失败：替换片段没匹配上（规则文件已改？先更新本测试）")
        return 0
    red, msg = _probe_with(m, tag)
    print("  " + msg)
    if not red:
        bad.append(msg)
    return 1


def _f11_margin(cases, bad):
    """②b-②e 边际判据（r103 老大拍板「保真怒」+「乙」取舍的三条补偿线，从 f11_bad 外提）：
    真愤怒/真悲伤的绝对分门槛、真悲伤对担忧的序差、常态表情的 sad 分上界、真怒对专注的差距。
    只往 bad 里追加，不改 cases；门槛数字的来历注释随代码迁移，逐字保留。"""
    # ②b **真愤怒的分数必须够高**（r103 老大拍板「保真怒」的补偿判据）。
    # 这条不是可有可无的：anger 去掉多区要求后，专注时确实会判 anger（已知代价）。
    # 门槛量的是**绝对分数**而不是「真怒−专注」的差值 —— 这是试出来的：
    #   把 browDown 从 1.4 压回 1.0（最可能的回退）时，差值仍有 0.191（看着很安全），
    #   但真怒的**绝对分**从 0.631 掉到 0.547 —— 而 calm 残余门槛是 top≥0.35，
    #   一旦真怒掉到 0.35 附近就被 calm 吃掉，anger 重演 0/2（r102 的漏判）。
    #   ⇒ 差值答「排得开吗」（本来就排得开），绝对分才答「够不够压过平静」。
    #   门槛 0.55：当前 0.631 有余量；回退到 1.0 时 0.547 < 0.55 ⇒ 必红。
    _real = next((c for c in cases if c["name"] == "anger_real"), None)
    if _real:
        _rg0 = (_real.get("pairs") or {}).get("anger", 0)
        if _rg0 < 0.55:
            bad.append("F11 真愤怒 anger 分仅 %.3f < 0.55 ⇒ 离 calm 残余门槛(0.35)太近，"
                       "browDown 权重被压回就会重演 anger 0/2（r102 的漏判）" % _rg0)
    # ②c **真悲伤的 sad 分必须够高**（r103「乙」取舍的低端保护，与 anger ②b 同构）。
    #   sad1/sad2 实测 0.629/0.781；取门店 0.55 ⇒ 权重被压低会先在撞 calm 残余线(0.35)前报红。
    _sad = max([c for c in cases if c["name"] in ("sad_real_1", "sad_real_2")],
               key=lambda c: (c.get("pairs") or {}).get("sadness", 0), default=None)
    if _sad:
        _sv = (_sad.get("pairs") or {}).get("sadness", 0)
        if _sv < 0.55:
            bad.append("F11 真悲伤 sad 分仅 %.3f < 0.55 ⇒ 离 calm 残余门槛(0.35)太近，"
                       "browInnerUp 权重被压低就会重演 sadness 0/2" % _sv)
    # ②d **真悲伤必须比最高分担忧更凶**。若序翻负 ⇒ 读到的是担忧不是悲伤。
    _worst = max([c for c in cases if c["name"] == "worry_heavy r103 代价"],
                 key=lambda c: (c.get("pairs") or {}).get("sadness", 0), default=None)
    if _sad and _worst:
        _g = (_sad.get("pairs") or {}).get("sadness", 0)
        _w = (_worst.get("pairs") or {}).get("sadness", 0)
        if _g - _w < 0.08:
            bad.append("F11 真悲伤 sad(%.3f) − 担忧重 sad(%.3f) = %.3f < 0.08 "
                       "⇒ 真悲与担忧读不出区别，代价面就从闪一下变成骗人" % (_g, _w, _g - _w))
    # ②e **两条边界不许跨**（「乙」的代价不是无限放大）：轻担忧、边担忧边说话**不得判 sadness**。
    #   真正的红线是「不把常态表情误报成低落」，不是「必须判 calm」—— 实测
    #   worry_speak_B2（边担忧边说重话）会判 surprise，那是另一回事，不算误报低落。
    #   判据用它自己的 sad 分来断，比读 got 更准（got 会被其它类抢）。
    for _bn in ("worry_light_A", "worry_speak_B1", "worry_speak_B2"):
        _b = next((c for c in cases if c["name"] == _bn), None)
        if _b:
            _bs = (_b.get("pairs") or {}).get("sadness", 0)
            if _bs >= 0.30:
                bad.append("F11 %s 的 sad 分达 %.3f ≥ 0.30 ⇒ 「乙」的代价被放大到常态表情上了"
                           % (_bn, _bs))
    for nm in ("concentrating", "speaking_frown"):
        _c = next((c for c in cases if c["name"] == nm), None)
        if not _real or not _c:
            continue
        rg = (_real.get("pairs") or {}).get("anger", 0)
        cg = (_c.get("pairs") or {}).get("anger", 0)
        gap = rg - cg
        if gap < 0.10:
            bad.append("F11 真愤怒 anger(%.3f) − %s anger(%.3f) = %.3f < 0.10 "
                       "⇒ 真怒与「%s」读数拉不开，专注时会被读成真发火（不只是闪一下红）"
                       % (rg, nm, cg, gap, nm))


def f11_bad(data):
    bad = []
    if data is None:
        return bad
    cases = data.get("cases") or []
    if not cases:
        return ["F11 零条读数 ⇒ 没跑到，不得当绿"]

    # ① 分类命中（含负样本：假阳性直接算失败）
    wrong = [c for c in cases if c["got"] != c["want"]]
    hits = len(cases) - len(wrong)
    if wrong:
        bad.append("F11 分类 %d/%d 命中，错判：%s"
                   % (hits, len(cases),
                      "; ".join("%s 期望%s 实得%s(%.2f)" % (c["name"], c["want"], c["got"], c["intensity"])
                                for c in wrong)))

    # ② 负样本假阳性必须为 0（这些是**不该被读成任何情绪**的常态表情）
    negs = [c for c in cases if c["want"] == "calm" and c["name"] != "neutral"]
    fp = [c for c in negs if c["got"] != "calm"]
    if fp:
        bad.append("F11 负样本假阳性 %d/%d：%s"
                   % (len(fp), len(negs), ", ".join(c["name"] + "→" + c["got"] for c in fp)))

    # ②b-②e 真怒/真悲伤绝对分门槛、序差与边界（r103 取舍的补偿判据，实现见 _f11_margin）
    _f11_margin(cases, bad)

    # ③ 七类必须都出现（"情绪种类单一"的直接反判据）
    rules = set(data.get("rules") or [])
    produced = {c["got"] for c in cases}
    missing = rules - produced
    if missing:
        bad.append("F11 判据声明 %d 类但夹具只触发 %d 类，未覆盖：%s ⇒ 「种类单一」无人拦"
                   % (len(rules), len(produced), ",".join(sorted(missing))))

    # ④ 单调性 + 饱和率
    #   ⚠️ 口径（r102 修正过一次，写在这里防后人再踩）：**只看该类自己的分数**，
    #   不看"当前主情绪"的强度。因为同一个向量压弱后，argmax 会合法地退回 calm，
    #   此时报告的 intensity 是 calm 的分 —— 拿它判 joy 的单调性就是**判错了对象**，
    #   第一次跑本尺就是这样把 8 条全报红的（实测 s=0.25 joy=0.11 calm=0.67）。
    #   真正要验的两件事是：① 该类分数随输入强度单调升 ② 分数不顶满（否则无分辨力）。
    by_name = {}
    for r in data.get("sweep") or []:
        by_name.setdefault(r["name"], []).append(r)
    saturated = 0
    nsat_total = 0
    for name, rows in by_name.items():
        rows.sort(key=lambda r: r["s"])
        vals = [r["score"] for r in rows]
        nsat_total += len(vals)
        saturated += sum(1 for v in vals if v >= 0.99)
        if name in SKIP_MONO:
            continue
        for i in range(1, len(vals)):
            if vals[i] < vals[i - 1] - 1e-6:
                bad.append("F11 %s 的**分数**非单调：sweep %s ⇒ %s 反而比上一档低"
                           % (name, [round(v, 3) for v in vals], round(vals[i], 3)))
                break
    if nsat_total and saturated / nsat_total > SAT_MAX:
        bad.append("F11 分数饱和率 %.0f%%（%d/%d 顶满 ≥0.99）> 上限 %.0f%% ⇒ 高强度段无分辨力，须降 peak"
                   % (100 * saturated / nsat_total, saturated, nsat_total, 100 * SAT_MAX))

    # ⑤ 成对可分性：**argmax 判据抓不到的缺陷，必须靠这一层抓**。
    #   r102 实测踩过：拆掉 fear 的 browDown 正权、或拆掉 contempt 的非对称门之后，
    #   **主情绪判据全绿**（fear 仍第一、contempt 仍低于 joy），只有分数层面的关系变了。
    #   只看 argmax 的判据在这两种破坏下完全无牙 —— 必须显式查分数关系。
    def pair_sep(name, a, b, min_gap, why):
        """同名样本下 a 的分数必须显著高于混淆类 b。"""
        rows = [c for c in cases if c["name"] == name]
        if not rows:
            return
        got = rows[0].get("pairs") or {}
        if a not in got or b not in got:
            bad.append("F11 %s 探针没回传 %s/%s 的分数（判据自身失灵）" % (name, a, b))
            return
        gap = got[a] - got[b]
        if gap < min_gap:
            bad.append("F11 %s：%s(%.3f) − %s(%.3f) = %.3f < %.3f ⇒ %s"
                       % (name, a, got[a], b, got[b], gap, min_gap, why))

    # 恐惧 vs 惊讶：恐惧的眉头是皱的，惊讶是平滑上抬 ⇒ 恐惧样本里 fear 必须压过 surprise。
    #   ⚠️ 门槛 0.10 是**实测定的**，不是拍的：现状 fear−surprise = 0.135；
    #     而"拆掉 fear 的 browDown 正权 + surprise 的 browDown 负权"这一破坏，实测把 gap
    #     压到 **0.059** —— 此时两者主情绪**都仍是 fear**，argmax 判据全绿，只有这一层能区分。
    #     门槛取 0.10 ⇒ 0.059 必红、0.135 必绿，两侧都留余量（不许贴边过）。
    pair_sep("fear", "fear", "surprise", 0.10,
             "fear/surprise 不可分 ⇒ browDown 一正一负那对分水岭被拆掉了")
    # 惊讶样本里 surprise 必须压过 fear（反向，防止把 fear 调得过肥）
    pair_sep("surprise", "surprise", "fear", 0.10,
             "surprise 被 fear 压过 ⇒ 两侧权重失衡")
    # 对称的社交笑：contempt 必须**严格为 0**（非对称门在起作用），否则非对称门被拆了
    rows = [c for c in cases if c["name"] == "social_smile"]
    if rows:
        got = rows[0].get("pairs") or {}
        if "contempt" in got and got["contempt"] > 1e-9:
            bad.append("F11 social_smile（双侧对称）时 contempt=%.3f 应严格为 0 ⇒ 非对称门失效"
                       % got["contempt"])

    # ⑥ 置信度必须真的在判（低 margin 必须被标成不稳，否则这个字段是装饰）
    lows = [c for c in cases if not c.get("confident")]
    if not lows:
        bad.append("F11 没有一条读数被判为「读数不稳」⇒ confidence 可能是恒真的装饰字段")
    for c in cases:
        if c.get("confident") and c.get("confidence", 0) <= 0:
            bad.append("F11 %s confidence=%.3f 却判 confident ⇒ 阈值没参与计算"
                       % (c["name"], c.get("confidence", 0)))

    # ⑥ 反例（可证伪）：抬 peak 必须让分类变差 —— 否则判据对阈值不敏感
    return bad


def selftest():
    """反例组：故意把判据改坏，F11 必须**每次都红**。
    没有这一腿，F11 就是"看着绿"——它可能只是恒真。
    每条反例都对应 r102 真实修过的一个缺陷，不是凭空造的。

    ⚠️ 回执条数**由实际执行数统计**，不写死数字：首版跑了 6 条却印「5 条」——
    报数与实跑脱节，正是本仓在册的「计数靠手写就会漂」那类错，故改成自动数。
    （r117 计数账：probe_with 原嵌套自计数、反例6-12 又显式 ran+=1 双计，报数虚高；
    助手升模块级后改为 _rule_case 返回实跑数、此处累加，一处计数一处累加。）"""
    import copy
    bad = []
    ran = 0
    real_rules = open(os.path.join(ROOT, "src/data/face-smile-rules.js"), encoding="utf-8").read()

    # 反例 1：把 disgust 的口鼻证据抽掉（模拟 r102 的旧权重：disgust 判不出来）
    ran += _rule_case(real_rules, bad, "反例1 disgust 证据被抽掉",
              ("noseSneerLeft: 1.0, noseSneerRight: 1.0,\n      mouthUpperUpLeft: 0.8, mouthUpperUpRight: 0.8,\n"
               "      mouthLowerDownLeft: 0.5, mouthLowerDownRight: 0.5,\n      mouthShrugUpper: 0.3,",
               "mouthShrugUpper: 0.3,"))

    # 反例 2：把 disgust 与 surprise 从声明的类别里去掉（模拟 r102 的旧版：
    #   这两类根本不在词表里，于是 disgust 判成 anger、surprise 判成 fear）
    ran += _rule_case(real_rules, bad, "反例2 删掉 surprise/disgust/contempt 三类（模拟旧版）",
              ('"surprise", "disgust", "contempt", "calm"', '"calm"'))

    # 反例 2b：把 fear 与 surprise 的分水岭拆掉（browDown 一正一负那一对）——
    #   模拟 r102 修的第二个真实缺陷：fear 永远被 surprise 抢走。
    ran += _rule_case(real_rules, bad, "反例2b 拆掉 fear/surprise 的 browDown 分水岭",
              ("      browDownLeft: 0.4, browDownRight: 0.4,\n      jawOpen: 0.25,", "      jawOpen: 0.25,"),
              ("      browDownLeft: -0.6, browDownRight: -0.6,\n      mouthPressLeft: -0.4, mouthPressRight: -0.4",
               "      mouthPressLeft: -0.4, mouthPressRight: -0.4"))

    # 反例 3：peak 调到极小（模拟旧版饱和：所有非平静分都顶满 1.0）
    ran += _rule_case(real_rules, bad, "反例3 peak 调到 0.05（制造饱和）", ("peak: 0.60,", "peak: 0.05,"))

    # 反例 4：confidence 阈值压到 0（恒 confident ⇒ 该字段退化成装饰）
    ran += _rule_case(real_rules, bad, "反例4 confidence 阈值压到 -1（恒 confident）",
              ("confidence: { on: 0.15, lowLabel:", "confidence: { on: -1, lowLabel:"))

    # 反例 5：把非对称门去掉（轻蔑会被 joy 抢走）。
    #   这条门在 **face-engine.js** 里（判据只存阈值），所以改的是引擎不是 rules。
    eng = open(os.path.join(ROOT, "src/js/face-engine.js"), encoding="utf-8").read()
    m5 = eng.replace('if (emo === "contempt" && smileAsymmetry(bs) < R.asym.min) s = 0;', "")
    if m5 == eng:
        bad.append("selftest 反例5 构造失败：非对称门那行没匹配上（face-engine.js 已改？）")
    else:
        red = False
        ran += 1
        with tempfile.TemporaryDirectory() as td:
            for sub in ("src/data", "src/js"):
                os.makedirs(os.path.join(td, sub), exist_ok=True)
            for rel in ("src/data/emotion-lexicon.js", "src/js/emotion-engine.js"):
                shutil.copy(os.path.join(ROOT, rel), os.path.join(td, rel))
            with open(os.path.join(td, "src/data/face-smile-rules.js"), "w", encoding="utf-8") as fh:
                fh.write(real_rules)
            with open(os.path.join(td, "src/js/face-engine.js"), "w", encoding="utf-8") as fh:
                fh.write(m5)
            save = globals()["ROOT"]
            try:
                globals()["ROOT"] = td
                data, errs = run_probe()
                got = f11_bad(data) if data else ["探针没起来: " + "; ".join(errs)]
                red = bool(got)
            finally:
                globals()["ROOT"] = save
        msg = "反例5 拆掉非对称门" + (" ⇒ F11 抓到了" if red else " ⇒ **F11 没抓到，判据无牙**")
        print("  " + msg)
        if not red:
            bad.append(msg)

    # 反例 6：把 anger 的 browDown 权重压回 1.0（=回到 r102 的量级），
    #   真愤怒的分数会掉到与「专注轻皱」拉不开 —— ②b 必须在此时报红。
    #   这条模拟的是"某天有人为了压误报把权重调回去"，是最可能发生的回退。
    ran += _rule_case(real_rules, bad, "反例6 anger 的 browDown 压回 1.0（真怒与专注拉不开）",
              ("browDownLeft: 1.4, browDownRight: 1.4,", "browDownLeft: 1.0, browDownRight: 1.0,"))

    # 反例 7：把 sadness 的 browInnerUp 从 1.2 降回 0.7（= r102 的权重）。
    #   ⚠️ 这条原本写的是「拆掉 jawOpen 反向证据」，跑出来 **F11 没抓到** ——
    #   查证发现 jawOpen:-1.9 在两组真悲伤上**完全不影响分数**（删掉/归零后与有它时一字不差），
    #   它只管「悲伤+惊讶混合」的边界，不管主判。真正的 load-bearing 项是 browInnerUp。
    #   ⇒ 反例改成测真正起作用的那一个。教训：反例没被抓到时，先查它是不是测了个摆设。
    ran += _rule_case(real_rules, bad, "反例7 sadness 的 browInnerUp 降回 0.7（回到 r102 漏判态）",
              ("      browInnerUp: 1.2,", "      browInnerUp: 0.7,"))

    # 反例 8：把 sadness 加回 need:2（r102 旧状态）。多区要求会让只有 brow 证据的真悲伤
    #   被打折一半 ⇒ 同样漏判。这条盯的是「多区要求被加回来」。
    ran += _rule_case(real_rules, bad, "反例8 把 sadness 加回 need:2（回退到漏判态）",
              ("need: { fear: 2 },", "need: { fear: 2, sadness: 2 },"))

    # 反例 9：browInnerUp 压回 r102 的 0.7 ⇒ 真悲伤 sad 分跌破 0.55（②c 必须红）。
    #   【覆盖②c：真悲伤分数低端保护】
    ran += _rule_case(real_rules, bad, "反例9 browInnerUp 压回 0.7（真悲伤跌破 0.55）",
              ("      browInnerUp: 1.2,", "      browInnerUp: 0.7,"))

    # 反例 10：browInnerUp 抬到 3.0 ⇒ 轻担忧 innerUp .40 也被判成 sadness（②e 必须红）。
    #   这是「乙」益价最真实的放大方向：有人为了"不漏真悲"一味抬高主证据。
    ran += _rule_case(real_rules, bad, "反例10 browInnerUp 抬到 3.0（轻担忧误报低落）",
              ("      browInnerUp: 1.2,", "      browInnerUp: 3.0,"))

    # 反例 11：jawOpen 负权从 -1.9 调小到 -0.3 ⇒ 边担忧边说话开始误报 sadness（②e 必须红）。
    #   这条盯的是 jawOpen 在代价面上的作用 —— 上轮误判它是摆设，代价面实测才翻案。
    ran += _rule_case(real_rules, bad, "反例11 jawOpen 负权调小到 -0.3（边担忧边说话误报低落）",
              ("      jawOpen: -1.9,", "      jawOpen: -0.3,"))

    # 反例 12：mouthFrown 从 0.4 抬回 1.0（r102 旧权重）⇒ 合成悲伤全对，
    #   但真悲伤的 sad 分可能被稀释。盯的是「辅证被当成主证」。
    ran += _rule_case(real_rules, bad, "反例12 mouthFrown 抬回 1.0（r102 旧权重回归）",
              ("      mouthFrownLeft: 0.4, mouthFrownRight: 0.4,",
               "      mouthFrownLeft: 1.0, mouthFrownRight: 1.0,"))

    if bad:
        print("F11-SELFTEST-FAIL 实跑 %d 条反例，%d 条没抓到" % (ran, len(bad)))
        for b in bad:
            print("  " + b)
        return 1
    print("F11-SELFTEST-PASS 实跑 %d 条反例，全部被 F11 抓到（判据有牙）" % ran)
    return 0


def main():
    if "--selftest" in sys.argv:
        return selftest()
    data, bad = run_probe()
    bad = f11_bad(data) + bad
    if data and not bad:
        cases = data["cases"]
        hits = sum(1 for c in cases if c["got"] == c["want"])
        sweep = data.get("sweep") or []
        sat = sum(1 for r in sweep if r["intensity"] >= 0.99)
        lows = sum(1 for c in cases if not c.get("confident"))
        print("F11-PASS 分类 %d/%d  类别 %d  饱和 %d/%d  低置信 %d"
              % (hits, len(cases), len(data.get("rules") or []), sat, len(sweep), lows))
        for b in bad:
            print("  " + b)
        return 0
    for b in bad:
        print("F11-FAIL " + b)
    return 1


if __name__ == "__main__":
    sys.exit(main())