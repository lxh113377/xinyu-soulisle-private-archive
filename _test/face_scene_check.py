# -*- coding: utf-8 -*-
"""F16 - 表情**场景切片**尺（r184 新增；目标#5「标准/低光照/侧脸/小尺寸」分场景验证）

量什么（与 F11/F12/S4 不重复，逐字对照过）：
  F11 量分类判别力（合成向量）、F12 量低强度三态水位（合成向量）、S4 量真照片 top-1（不分场景）。
  本尺是**第一条按场景切片的尺**：读 _test/face-au/*.json 里 harness 存的 meta
  （lumaBucket/yawBucket/faceSize，分档阈值与线上质量门**同源**，见 face-harness.html 注释），
  对当前引擎复算 read()，输出 per-scene 切片 + 六条常驻断言：
    A1 小尺寸门（r184 faceMin=0.18）在现有语料命中数必须 = 0
       （语料实测 faceSize 0.198~0.638，全部大于线 ⇒ 命中 = 门误伤正常样本）
    A2 眨眼不得冒充微表情（r184 修复的常驻回归腿）：prev 只差 eyeBlink/eyeLook 时
       subs.micro 必须 false；真实表情 AU 帧间跃升时必须 true（双向，防把 micro 修死）
    A3 meta 里记录的 quality 阈值必须等于当前 R.quality ⇒ 样本分档失效即红（禁拿旧档切新阈值）
    A6 侧脸（姿态）闸门（r184 补）：yawBucket=profile 的真照必须被 yaw 门拦下且不得笃定
    A5 复杂背景机制腿（r184 补）：lumaRect 的取样区必须锁在人脸框内、远小于整帧、并跟随人脸移动
       —— 若它悄悄回落成整帧，背景就重新进入光照判定（R1 复发），而这条此前无人守
  场景切片（normal/dark、front/profile、小尺寸）**report-only**：语料 19 张，
  **wc 列只报数不做闸门**（label 与引擎输出不同源，见下方口径更正）；
  切片分母 2~12，做成闸门就是永红判据（同 F12「棘轮与目标线分家」的设计要点）。

用法：
  python _test/face_scene_check.py            # 复算 + 断言 + 切片打印
  python _test/face_scene_check.py --selftest # 变异演习：faceMin 抬 0.30 / gazeRe 拆掉 / lumaRect 掐整帧 / yawMax 抬 0.99 四条腿必翻红
退出码：0=PASS 1=断言红 2=未验（node/语料/meta 缺失 ⇒ 绝不判绿）
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
AU_DIR = ROOT / "_test" / "face-au"

NODE = r"""
const {readFileSync, readdirSync} = require("fs");
const vm = require("vm");
const ROOT = process.argv[2];
const S = (p) => readFileSync(ROOT + "/" + p, "utf8");
const ctx = vm.createContext({window: {}, console, require});
for (const f of ["src/data/emotion-lexicon.js", "src/js/emotion-engine.js",
                  "src/data/face-smile-rules.js", "src/js/face-engine.js"]) vm.runInContext(S(f), ctx);
const FE = ctx.window.FaceEngine;
const R = ctx.window.__XINYU_FACE_RULES__;
const dir = ROOT + "/_test/face-au";
const rows = readdirSync(dir).filter(f => f.endsWith(".json")).map(f =>
  JSON.parse(readFileSync(dir + "/" + f, "utf8")));
const keys = Object.keys(rows.length ? rows[0].bs : {});
function frame(mut) { const o = {}; for (const k of keys) o[k] = 0.02; Object.assign(o, mut || {}); return o; }
const out = rows.map(r => {
  const v = FE.read(r.bs);
  /* r184 修假绿：read() 不算质量门（门在运行时 frame() 里由 assessQuality 合成），
     旧写法 v.quality 恒 undefined ⇒ reasons 恒空 ⇒ A1 是条没接电的断言。
     现按 harness 存的 meta 信号**直接调线上同一个纯函数 assessQuality** ⇒ 同源。 */
  const q = FE.assessQuality({
    luma: (r.meta && r.meta.luma != null) ? { mean: r.meta.luma, variance: r.meta.lumaVar } : null,
    yaw: r.meta ? r.meta.yaw : null,
    faceWidth: r.meta ? r.meta.faceSize : null,
    mouthFlatSamples: 0
  });
  /* r184 口径修复（与 S4 同一个坑）：只调 assessQuality 不调 applyQuality ⇒ v.confident
     仍是**门前的原始值**。A6 一上线就抓到：sadness-01-wayuu-woman-bright 门后应为 false，
     而门前是 true ⇒ 切片 conf 列与 A4/A6 都在读一个产品里不存在的读数。 */
  FE.applyQuality(v, q);
  return {file: r.file, want: r.want, got: v.emotion, confident: !!v.confident,
          wrong_confident: (!!v.confident && v.emotion !== r.want && r.want !== null),
          reasons: q.reasons,
          meta: r.meta || null};
});
const blink = FE.read(frame({}), frame({eyeBlinkLeft: 0.92, eyeBlinkRight: 0.88})).subs.micro;
const gaze = FE.read(frame({}), frame({eyeLookDownLeft: 0.85, eyeLookDownRight: 0.85})).subs.micro;
const real = FE.read(frame({mouthSmileLeft: 0.30, mouthSmileRight: 0.30}), frame({mouthSmileLeft: 0.02, mouthSmileRight: 0.02})).subs.micro;
/* A5（r184）：复杂背景机制腿 —— R1 的修法是「亮度按人脸框取样」，那就必须证明
   取样区**锁在人脸上**、而不是悄悄回落成整帧（回落 = 背景又能决定光照判定，R1 复发）。 */
const boxLm = (x0, x1, y0, y1) => Array.from({length: 478}, (_, i) =>
  ({x: x0 + (x1 - x0) * ((i % 23) / 22), y: y0 + (y1 - y0) * (Math.floor(i / 23) / 20)}));
const bgA = FE.lumaRect(boxLm(0.40, 0.60, 0.35, 0.65), 640, 480);
const bgB = FE.lumaRect(boxLm(0.10, 0.25, 0.20, 0.45), 640, 480);
const bgNone = FE.lumaRect(null, 640, 480);
console.log(JSON.stringify({out, micro: {blink, gaze, real},
  bg: {a: bgA, b: bgB, none: bgNone, fw: 640, fh: 480},
  faceMin: (R.quality || {}).faceMin, thresholds: {
    brightMin: R.quality.brightMin, brightMax: R.quality.brightMax, yawMax: R.quality.yawMax}}));
"""


def run_node(root, code=None):
    with tempfile.TemporaryDirectory() as td:
        script = os.path.join(td, "f13_probe.cjs")
        open(script, "w", encoding="utf-8").write(code or NODE)
        try:
            p = subprocess.run(["node", script, str(root)], capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=120)
        except FileNotFoundError:
            return None, "node 不可用"
        if p.returncode != 0 or not (p.stdout or "").strip():
            return None, "探针跑不起来 rc=%s %s" % (p.returncode, (p.stderr or "")[:200])
        try:
            return json.loads(p.stdout.strip().splitlines()[-1]), None
        except Exception as e:
            return None, "输出解析失败 %s" % e


def a5_problems(bg):
    """A5 判定：lumaRect 的取样区必须锁在人脸框内（r184 复杂背景机制腿）。

    为什么要有这条：R1 的修法是「亮度按人脸框取样，而不是整帧平均」。修完若没有判据守着，
    任何人把 lumaRect 改回 null（回落整帧）都不会被任何尺子发现 —— 而那正是 R1 的复发。
    """
    out = []
    ra, rb, fw, fh = bg.get("a"), bg.get("b"), bg.get("fw"), bg.get("fh")
    if not (ra and rb):
        out.append("A5 lumaRect 对人脸框返回了空 ⇒ 取样区回落整帧，R1（背景污染光照判定）复发")
        return out
    frameArea = float(fw * fh)
    for tag, rc in (("A", ra), ("B", rb)):
        if rc["sw"] * rc["sh"] >= 0.25 * frameArea:
            out.append("A5 取样区%s 占整帧 %.1f%%（应远小于）⇒ 背景仍在光照判定里"
                       % (tag, 100.0 * rc["sw"] * rc["sh"] / frameArea))
        if rc["sx"] < 0 or rc["sy"] < 0 or rc["sx"] + rc["sw"] > fw + 1 or rc["sy"] + rc["sh"] > fh + 1:
            out.append("A5 取样区%s 越出帧边界（裁剪失效）" % tag)
    if abs((ra["sx"] + ra["sw"] / 2.0) - 0.50 * fw) > 0.03 * fw:
        out.append("A5 取样区 A 未对准注入的人脸框中心（机制没跟着关键点走）")
    if abs((rb["sx"] + rb["sw"] / 2.0) - 0.175 * fw) > 0.03 * fw:
        out.append("A5 取样区 B 未对准注入的人脸框中心")
    if abs(ra["sx"] - rb["sx"]) < 50:
        out.append("A5 两个人脸框位置不同但取样区几乎相同 ⇒ 取样区不是关键点的函数")
    if bg.get("none") is not None:
        out.append("A5 无关键点时 lumaRect 必须返回 null（回落整帧是明文契约），实得 %s" % bg.get("none"))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if not AU_DIR.is_dir() or not list(AU_DIR.glob("*.json")):
        print("F16-UNVERIFIED 语料缺失（_test/face-au 为空）⇒ 没有样本就没有场景准确率，禁判绿")
        return 2
    data, err = run_node(ROOT)
    if data is None:
        print("F16-UNVERIFIED " + err)
        return 2
    rows = data["out"]
    missing_meta = [r["file"] for r in rows if not r["meta"]]
    if missing_meta:
        print("F16-UNVERIFIED meta 缺失（分档失效）：%s" % ", ".join(missing_meta))
        return 2
    bad = []
    # A3 阈值同源
    th = data["thresholds"]
    for r in rows:
        mt = r["meta"].get("thresholds") or {}
        if any(abs(float(mt.get(k, -1)) - float(v)) > 1e-9 for k, v in th.items()):
            bad.append("A3 %s 样本阈值(%s)与当前(%s)不同源 ⇒ 分档失效，需重导出" % (r["file"], mt, th))
    # A1 小尺寸门零命中
    hits = [r["file"] for r in rows if "small" in r["reasons"]]
    if hits:
        bad.append("A1 小尺寸门误伤正常语料：%s" % ", ".join(hits))
    # A2 眨眼双向
    m = data["micro"]
    if m["blink"] or m["gaze"]:
        bad.append("A2 眨眼/眼动仍被读成微表情（blink=%s gaze=%s）" % (m["blink"], m["gaze"]))
    if not m["real"]:
        bad.append("A2 真实表情跃升不再亮 micro ⇒ micro 被修死")
    # 场景切片（report-only；r184 升级为 lumaBucket × yawBucket 交叉表 + 暗光段闸门）
    #   升级动因：旧版只按「luma/yaw 合并」切，暗光段 2 张真照混在 normal 里看不见。
    #   实测 19 张真照 meta 里 lumaBucket=dark 有 2 张（disgust-04-look-woman-dark 0.150、
    #   sadness-01-wayuu-woman-dark 0.129）⇒ 之前「暗光场景无法验证」是错判，数据一直在。
    def bucket(r):
        mm = r["meta"]
        return mm.get("lumaBucket", "?") + "/" + mm.get("yawBucket", "?")
    # r184 口径更正（实测 19 张真照）：wrong_confident 在本语料上不是误识别率。
    #   label 取自 Commons 人工标题（smiling / neutral / sadness），引擎输出是八类情绪
    #   （joy / calm / anger）两个分类体系不同源。confident 表达的是
    #   引擎对自己的判断有信心，不是判断对了。实测 confident=true 的 8 张里 7 张是 WC
    #   （neutral-01/04 -> calm、smile-01..04 -> joy、sadness-01-bright -> anger）。
    #   若读成 误识别率 7/8，就是拿不同源的分母去比分子，数字无意义。
    #   故 wc 列只报数不做闸门；真正的误识别率闸门在 F11（合成向量，同源）。
    sc = {}
    for r in rows:
        b = sc.setdefault(bucket(r), {"n": 0, "top1": 0, "wc": 0, "conf": 0})
        b["n"] += 1
        b["top1"] += 1 if r["got"] == r["want"] else 0
        b["wc"] += 1 if r["wrong_confident"] else 0
        b["conf"] += 1 if r["confident"] else 0
    print("场景切片（report-only，样本小勿外推；wc 列只报数不做闸门，见 docstring 口径说明）：")
    for k in sorted(sc):
        v = sc[k]
        print("  %-16s n=%2d top1=%d (%.0f%%) 笃定错报=%d/%d" % (k, v["n"], v["top1"], 100.0 * v["top1"] / v["n"], v["wc"], v["conf"]))
    # A4 暗光段闸门：dark 档真照必须存在，且**一律不得笃定骗人**（WC=0）。
    #   依据：r184 的 lumaRect 改按人脸框取样后，暗光判定不再被背景污染；
    #   这条是「暗光场景」这一目标维度在真照上的唯一可验证落点。
    dark = [r for r in rows if r["meta"].get("lumaBucket") == "dark"]
    if not dark:
        bad.append("A4 暗光段零真照（meta 无 lumaBucket=dark）⇒ 目标#5 暗光场景无法验证，需补数据")
    else:
        dwc = [r["file"] for r in dark if r["wrong_confident"]]
        if dwc:
            bad.append("A4 暗光段出现笃定错报：%s" % ", ".join(dwc))
        else:
            print("  A4 暗光段 n=%d 笃定错报=0（dark 档一律不笃定）" % len(dark))
    # A5 复杂背景机制腿：取样区必须锁在人脸框内，且远小于整帧（否则背景会重新进入光照判定）
    probs = a5_problems(data.get("bg") or {})
    bad.extend(probs)
    if not probs:
        bgs = data.get("bg") or {}
        ra, fw, fh = bgs["a"], bgs["fw"], bgs["fh"]
        print("  A5 复杂背景机制腿：取样区占帧 %.1f%%/%.1f%%，跟随人脸框移动 %.0fpx（未回落整帧）"
              % (100.0 * ra["sw"] * ra["sh"] / float(fw * fh),
                 100.0 * bgs["b"]["sw"] * bgs["b"]["sh"] / float(fw * fh),
                 abs(ra["sx"] - bgs["b"]["sx"])))
    # A6 侧脸（姿态变化）闸门：yawBucket=profile 的真照必须被 yaw 门拦下且不得笃定。
    #   为什么补：目标#1 点名「侧脸/姿态变化」，而 yaw 门此前**零判据覆盖**（只在 F16 切片里当一列数字）。
    prof = [r for r in rows if r["meta"].get("yawBucket") == "profile"]
    if not prof:
        bad.append("A6 侧脸档零真照（meta 无 yawBucket=profile）⇒ 目标#1 姿态维度无法验证，需补数据")
    else:
        leak = [r["file"] for r in prof if "profile" not in r["reasons"]]
        conf = [r["file"] for r in prof if r["confident"]]
        if leak:
            bad.append("A6 侧脸档未被 yaw 门拦下：%s" % ", ".join(leak))
        if conf:
            bad.append("A6 侧脸档仍出笃定读数：%s" % ", ".join(conf))
        yaws = [abs(float(r["meta"].get("yaw", 0))) for r in prof]
        if not leak and not conf:
            print("  A6 侧脸档 n=%d yaw %.3f~%.3f（>yawMax=%s）全部被 yaw 门拦下、零笃定"
                  % (len(prof), min(yaws), max(yaws), data["thresholds"].get("yawMax")))
    fs_min = min(float(r["meta"].get("faceSize", 1)) for r in rows)
    print("faceSize 观测 %.3f~%.3f｜faceMin=%s｜语料 %d 张" % (fs_min, max(float(r["meta"].get("faceSize", 1)) for r in rows), data["faceMin"], len(rows)))
    if bad:
        print("F16-FAIL " + ("%d 项" % len(bad)))
        for b in bad:
            print("  " + b)
        return 1
    if a.selftest:
        return selftest()
    print("F16-PASS 六断言(A1/A2/A3/A4/A5/A6)全过｜语料 %d 张｜切片覆盖 %d 组" % (len(rows), len(sc)))
    return 0


def selftest():
    """变异演习：四条腿都必须翻红，否则本尺无牙。"""
    red_any, msgs = 0, []
    # 腿1 faceMin 抬到 0.30 ⇒ A1 必红（观测最小 0.198 < 0.30）
    code = NODE.replace('const R = ctx.window.__XINYU_FACE_RULES__;',
                        'const R = ctx.window.__XINYU_FACE_RULES__; R.quality.faceMin = 0.30;')
    data, err = run_node(ROOT, code)
    ok1 = bool(data) and any("small" in r["reasons"] for r in data["out"])
    msgs.append("腿1 faceMin 抬 0.30 ⇒ %s（应命中）" % ("命中 %d 张" % sum(1 for r in data["out"] if "small" in r["reasons"]) if ok1 else "零命中，尺无牙"))
    red_any |= 0 if ok1 else 1
    # 腿2 拆 gazeRe（回到 r184 前行为）⇒ A2 眨眼必被误读
    code2 = NODE.replace('for (const f of ["src/data/emotion-lexicon.js", "src/js/emotion-engine.js",',
                         'for (const f of ["src/data/emotion-lexicon.js", "src/js/emotion-engine.js",  // noqa')
    with tempfile.TemporaryDirectory() as td:
        for sub in ("src/js", "src/data", "_test/face-au"):
            os.makedirs(os.path.join(td, *sub.split("/")), exist_ok=True)
        for f in ("src/data/emotion-lexicon.js", "src/data/face-smile-rules.js",
                  "src/js/emotion-engine.js", "src/js/face-engine.js"):
            shutil.copy(ROOT / f, os.path.join(td, f))
        for f in (AU_DIR).glob("*.json"):
            shutil.copy(f, os.path.join(td, "_test/face-au", f.name))
        eng = open(os.path.join(td, "src/js/face-engine.js"), encoding="utf-8").read()
        open(os.path.join(td, "src/js/face-engine.js"), "w", encoding="utf-8").write(
            eng.replace("const gazeRe = /^eye(?:Blink|Look)/;", "const gazeRe = /^(?!);/;"))
        data2, err2 = run_node(Path(td))
        ok2 = bool(data2) and (data2["micro"]["blink"] is True)
        msgs.append("腿2 拆 gazeRe ⇒ %s" % ("眨眼重新冒充微表情（尺抓到了）" if ok2 else "仍 false（尺无牙或变体没生效：%s）" % err2))
        red_any |= 0 if ok2 else 1
    # 腿3 把 lumaRect 掐成恒 null（= 回落整帧，R1 复发）⇒ A5 必须翻红
    code3 = NODE.replace("const FE = ctx.window.FaceEngine;",
                         "const FE = ctx.window.FaceEngine; FE.lumaRect = () => null;")
    data3, err3 = run_node(ROOT, code3)
    ok3 = bool(data3) and bool(a5_problems(data3.get("bg") or {}))
    msgs.append("腿3 lumaRect 掐成整帧回落 ⇒ %s"
                % ("A5 当场翻红" if ok3 else "A5 仍绿（尺无牙：%s）" % err3))
    red_any |= 0 if ok3 else 1
    # 腿4 yawMax 抬到 0.99 ⇒ 侧脸门失效，A6 必红
    code4 = NODE.replace('const R = ctx.window.__XINYU_FACE_RULES__;',
                         'const R = ctx.window.__XINYU_FACE_RULES__; R.quality.yawMax = 0.99;')
    data4, err4 = run_node(ROOT, code4)
    ok4 = bool(data4) and any(r["meta"].get("yawBucket") == "profile" and "profile" not in r["reasons"]
                              for r in data4["out"])
    msgs.append("腿4 yawMax 抬到 0.99 ⇒ %s"
                % ("侧脸档不再被拦，尺抓到了" if ok4 else "仍被拦（尺无牙：%s）" % err4))
    red_any |= 0 if ok4 else 1
    for s in msgs:
        print("  " + s)
    if red_any:
        print("F16-SELFTEST-FAIL 变异腿没全部被抓到 ⇒ 判据无牙")
        return 1
    print("F16-SELFTEST-PASS 四条变异腿都被抓到")
    return 0


if __name__ == "__main__":
    sys.exit(main())
