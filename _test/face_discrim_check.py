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
    ("anger", {"browDownLeft": .85, "browDownRight": .85,
               "noseSneerLeft": .6, "noseSneerRight": .6}, "anger"),
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
    # ── 负样本：这些**不是情绪**，判错就是假阳性（r102 的核心诉求）──
    ("concentrating", {"browDownLeft": .4, "browDownRight": .4}, "calm"),
    ("speaking_frown", {"jawOpen": .4, "browDownLeft": .3, "browDownRight": .3}, "calm"),
    ("speaking", {"jawOpen": .5, "mouthFunnel": .3}, "calm"),
    ("blinking", {"eyeBlinkLeft": .9, "eyeBlinkRight": .9}, "calm"),
    ("looking_down", {"eyeLookDownLeft": .8, "eyeLookDownRight": .8}, "calm"),
    ("lips_pressed", {"mouthPressLeft": .4, "mouthPressRight": .4}, "calm"),
]

# 强度扫描档位（测单调性 / 饱和）
SWEEP = [.25, .40, .55, .70, .85, 1.00]
# sweep 只跑「本身就以某情绪为标签」的向量。排除两类，理由写在这里防后人"顺手补回去"：
#   - 负样本（concentrating 等）：它们追踪的类是 calm，而 calm 是**残余量**，
#     按定义随 top 单调反向，用它判"某情绪分数单调"是判错了对象。
#   - joy_weak：它的标签是 calm，同上。
POSITIVE = [c for c in CASES if c[0] not in (
    "concentrating", "speaking_frown", "speaking", "blinking", "looking_down",
    "lips_pressed", "joy_weak")]
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

    # ② 负样本假阳性必须为 0（"专注被读成愤怒"这类是本尺存在的理由）
    negs = [c for c in cases if c["want"] == "calm" and c["name"] != "neutral"]
    fp = [c for c in negs if c["got"] != "calm"]
    if fp:
        bad.append("F11 负样本假阳性 %d/%d：%s"
                   % (len(fp), len(negs), ", ".join(c["name"] + "→" + c["got"] for c in fp)))

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
    报数与实跑脱节，正是本仓在册的「计数靠手写就会漂」那类错，故改成自动数。"""
    import copy
    import tempfile
    bad = []
    ran = 0
    real_rules = open(os.path.join(ROOT, "src/data/face-smile-rules.js"), encoding="utf-8").read()
    ran = 0

    def probe_with(patch_text, tag):
        """把改坏的 rules 临时落到一个副本工程里，跑同一探针，看 F11 是否红。"""
        nonlocal ran
        ran += 1
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

    # 反例 1：把 disgust 的口鼻证据抽掉（模拟 r102 的旧权重：disgust 判不出来）
    m = real_rules.replace("noseSneerLeft: 1.0, noseSneerRight: 1.0,\n      mouthUpperUpLeft: 0.8, mouthUpperUpRight: 0.8,\n      mouthLowerDownLeft: 0.5, mouthLowerDownRight: 0.5,\n      mouthShrugUpper: 0.3,",
                           "mouthShrugUpper: 0.3,")
    if m == real_rules:
        bad.append("selftest 反例1 构造失败：disgust 权重串没匹配上（规则文件已改？先更新本测试）")
    else:
        red, msg = probe_with(m, "反例1 disgust 证据被抽掉")
        print("  " + msg)
        if not red:
            bad.append(msg)

    # 反例 2：把 disgust 与 surprise 从声明的类别里去掉（模拟 r102 的旧版：
    #   这两类根本不在词表里，于是 disgust 判成 anger、surprise 判成 fear）
    m2 = real_rules.replace(
        '"surprise", "disgust", "contempt", "calm"', '"calm"')
    if m2 == real_rules:
        bad.append("selftest 反例2 构造失败：emotions 串没匹配上")
    else:
        red, msg = probe_with(m2, "反例2 删掉 surprise/disgust/contempt 三类（模拟旧版）")
        print("  " + msg)
        if not red:
            bad.append(msg)

    # 反例 2b：把 fear 与 surprise 的分水岭拆掉（browDown 一正一负那一对）——
    #   模拟 r102 修的第二个真实缺陷：fear 永远被 surprise 抢走。
    m2b = real_rules.replace("      browDownLeft: 0.4, browDownRight: 0.4,\n      jawOpen: 0.25,", "      jawOpen: 0.25,")
    m2b = m2b.replace("      browDownLeft: -0.6, browDownRight: -0.6,\n      mouthPressLeft: -0.4, mouthPressRight: -0.4", "      mouthPressLeft: -0.4, mouthPressRight: -0.4")
    if m2b == real_rules:
        bad.append("selftest 反例2b 构造失败：browDown 分水岭串没匹配上")
    else:
        red, msg = probe_with(m2b, "反例2b 拆掉 fear/surprise 的 browDown 分水岭")
        print("  " + msg)
        if not red:
            bad.append(msg)

    # 反例 3：peak 调到极小（模拟旧版饱和：所有非平静分都顶满 1.0）
    m3 = real_rules.replace("peak: 0.60,", "peak: 0.05,")
    if m3 == real_rules:
        bad.append("selftest 反例3 构造失败：peak 串没匹配上")
    else:
        red, msg = probe_with(m3, "反例3 peak 调到 0.05（制造饱和）")
        print("  " + msg)
        if not red:
            bad.append(msg)

    # 反例 4：confidence 阈值压到 0（恒 confident ⇒ 该字段退化成装饰）
    m4 = real_rules.replace("confidence: { on: 0.15, lowLabel:", "confidence: { on: -1, lowLabel:")
    if m4 == real_rules:
        bad.append("selftest 反例4 构造失败：confidence 串没匹配上")
    else:
        red, msg = probe_with(m4, "反例4 confidence 阈值压到 -1（恒 confident）")
        print("  " + msg)
        if not red:
            bad.append(msg)

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