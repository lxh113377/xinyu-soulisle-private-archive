# -*- coding: utf-8 -*-
"""F17 - 表情**遮挡**尺（r184 新增；目标#1 点名的「口罩/帽子/眼镜」场景）

为什么单开一条尺：口罩/眼镜/帽子是需求里**点名**的失败场景，而它此前**零测试覆盖** ——
  mouth-flat（口罩）机制 r113 就有，但没有任何常驻判据钉住它；
  眼镜/帽子（眼区/眉区遮挡）则连机制都没有。
  实测（20 张真照 AU 向量做单变量遮挡）：
    原帧            笃定 9 ｜ 质量门命中 0
    口罩(口部归零)   笃定 9→0（mouth-flat 命中 20/20）
    墨镜(眼区归零)   笃定 9→**14**（！遮挡反而更笃定 —— 眼区证据归零后被当成"平静"）
    帽子(眉区归零)   笃定 9（
  第三行就是缺口：**看不见眼睛 ⇒ 引擎更笃定**。r184 补 occluded-eye / occluded-brow 两个区域
  平坦信号（与 mouth-flat 同构），把三行都压到 0。

四条常驻断言：
  A1 口罩机制回归腿：口部归零 ⇒ mouth-flat 必须命中、confident 必须全 false、微笑三态必须 none
  A2 无眼证据不许声称真笑：眼区归零后，真笑三态必须从 duchenne 降级为 social，subs.duchenne 必须 false
  A3 阈值保守性（假阳性闸门）：现有 20 张**真照**上 occluded-eye/occluded-brow 命中数必须 = 0
     （阈值 0.03 取在观测最小值之下：眼区 0.1978 / 眉区 0.0599。首版 0.06 时眉区当场假阳性 1 帧）
  A4 遮挡必须降笃定：眼区或眉区归零后，笃定帧数必须 = 0（新信号真的接上了，不是摆设）

用法：
  python _test/face_occlusion_check.py            # 复算 + 四断言 + 分变体打印
  python _test/face_occlusion_check.py --selftest # 变异演习：阈值抬高 / 判定行拆掉，必翻红
退出码：0=PASS 1=断言红 2=未验（node/语料缺失 ⇒ 绝不判绿）
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
const FE = ctx.window.FaceEngine, R = ctx.window.__XINYU_FACE_RULES__;
const Q = R.quality;
const EYE = ["eyeBlinkLeft","eyeBlinkRight","eyeSquintLeft","eyeSquintRight","eyeWideLeft","eyeWideRight",
  "eyeLookUpLeft","eyeLookUpRight","eyeLookDownLeft","eyeLookDownRight",
  "eyeLookInLeft","eyeLookInRight","eyeLookOutLeft","eyeLookOutRight","cheekSquintLeft","cheekSquintRight"];
const BROW = ["browDownLeft","browDownRight","browInnerUp","browOuterUpLeft","browOuterUpRight"];
const MOUTH = ["mouthSmileLeft","mouthSmileRight","mouthPucker","mouthFunnel","jawOpen",
  "mouthPressLeft","mouthPressRight","mouthFrownLeft","mouthFrownRight"];
const dir = ROOT + "/_test/face-au";
const rows = readdirSync(dir).filter(f => f.endsWith(".json")).map(f =>
  JSON.parse(readFileSync(dir + "/" + f, "utf8")));
const zero = (bs, keys) => { const o = Object.assign({}, bs); for (const k of keys) if (k in o) o[k] = 0; return o; };
const flat = (bs, keys) => { for (const k of keys) if ((bs[k] || 0) >= Q.flatMin) return false; return true; };
/* 与运行时 frame() 同构：区域平坦 → 连续样本数 → assessQuality → applyQuality */
const assess = (bs) => {
  const v = FE.read(bs);
  const q = FE.assessQuality({
    mouthFlatSamples: flat(bs, MOUTH) ? Q.mouthFlatSamples : 0,
    eyeFlatSamples: flat(bs, EYE) ? Q.flatSamples : 0,
    browFlatSamples: flat(bs, BROW) ? Q.flatSamples : 0
  });
  FE.applyQuality(v, q);
  return {v: v, q: q};
};
const variants = {
  "原帧": r => r.bs,
  "口罩": r => zero(r.bs, MOUTH),
  "墨镜": r => zero(r.bs, EYE),
  "帽子": r => zero(r.bs, BROW)
};
const out = {};
for (const name in variants) {
  let confident = 0, flagged = 0, duchenne = 0, social = 0, none = 0, occ = 0;
  const reasons = {};
  for (const r of rows) {
    const a = assess(variants[name](r));
    if (a.v.confident) confident++;
    if (!a.q.ok) { flagged++; for (const k of a.q.reasons) reasons[k] = (reasons[k] || 0) + 1; }
    const kind = a.v.smile ? a.v.smile.kind : "none";
    if (kind === "duchenne") duchenne++; else if (kind === "social") social++; else none++;
    if (a.v.smile && a.v.smile.occluded) occ++;
  }
  out[name] = {confident, flagged, reasons, duchenne, social, none, occluded: occ};
}
/* A2 专项：真笑 4 张在眼区归零后的三态 + subs.duchenne */
const smiles = rows.filter(r => r.want === "joy");
const a2 = smiles.map(r => {
  const a = assess(zero(r.bs, EYE));
  return {file: r.file, kindBefore: FE.read(r.bs).smile ? FE.read(r.bs).smile.kind : "none",
          kindAfter: a.v.smile ? a.v.smile.kind : "none", duchenneAfter: !!a.v.subs.duchenne};
});
/* A3 专项：原帧上的区域平坦误命中数（假阳性闸门） */
let fp = 0;
for (const r of rows) { const a = assess(r.bs); for (const k of a.q.reasons)
  if (k === "occluded-eye" || k === "occluded-brow") fp++; }
console.log(JSON.stringify({n: rows.length, out, a2, fp, flatMin: Q.flatMin,
  flatSamples: Q.flatSamples, mouthFlatSamples: Q.mouthFlatSamples}));
"""


def run_node(root, code=None):
    with tempfile.TemporaryDirectory() as td:
        script = os.path.join(td, "f14_probe.cjs")
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if not AU_DIR.is_dir() or not list(AU_DIR.glob("*.json")):
        print("F17-UNVERIFIED 语料缺失（_test/face-au 为空）⇒ 没有样本就没有遮挡准确率，禁判绿")
        return 2
    data, err = run_node(ROOT)
    if data is None:
        print("F17-UNVERIFIED %s" % err)
        return 2
    bad = []
    o = data["out"]
    # A1 口罩机制
    mask = o["口罩"]
    if mask["flagged"] != data["n"] or "mouth-flat" not in mask["reasons"]:
        bad.append("A1 口罩变体未被 mouth-flat 拦下（命中 %d/%d，理由 %s）"
                   % (mask["flagged"], data["n"], mask["reasons"]))
    if mask["confident"] != 0:
        bad.append("A1 口罩变体仍有 %d 帧笃定" % mask["confident"])
    if mask["duchenne"] or mask["social"]:
        bad.append("A1 口罩变体仍在声称微笑（duchenne=%d social=%d）" % (mask["duchenne"], mask["social"]))
    # A2 无眼证据不许声称真笑
    for r in data["a2"]:
        if r["kindAfter"] == "duchenne" or r["duchenneAfter"]:
            bad.append("A2 眼区归零后仍声称真笑：%s（前 %s 后 %s）"
                       % (r["file"], r["kindBefore"], r["kindAfter"]))
    # A3 假阳性闸门
    if data["fp"]:
        bad.append("A3 现有真照上区域平坦信号误命中 %d 次（阈值 %.3f 不够保守）"
                   % (data["fp"], data["flatMin"]))
    # A4 遮挡必须降笃定
    for name in ("墨镜", "帽子"):
        if o[name]["confident"]:
            bad.append("A4 %s 变体仍有 %d 帧笃定 ⇒ 遮挡信号没接上" % (name, o[name]["confident"]))

    print("遮挡尺（F17）：语料 %d 张｜阈值 flatMin=%.3f flatSamples=%d"
          % (data["n"], data["flatMin"], data["flatSamples"]))
    for name in ("原帧", "口罩", "墨镜", "帽子"):
        v = o[name]
        print("  %-5s 笃定=%2d 被门拦下=%2d 真笑=%d 社交笑=%d 无笑=%d 理由=%s"
              % (name, v["confident"], v["flagged"], v["duchenne"], v["social"], v["none"],
                 json.dumps(v["reasons"], ensure_ascii=False)))
    if bad:
        print("F17-FAIL %d 项" % len(bad))
        for b in bad:
            print("  " + b)
        return 1
    if a.selftest:
        return selftest()
    print("F17-PASS 四断言(A1/A2/A3/A4)全过｜语料 %d 张" % data["n"])
    return 0


def selftest():
    """两条变异腿：① 阈值抬高 ⇒ 假阳性必被 A3 抓到；② 拆掉 occluded 判定 ⇒ A4 必红。"""
    msgs, red_any = [], 0
    with tempfile.TemporaryDirectory() as td:
        for f in ("src/data/emotion-lexicon.js", "src/data/face-smile-rules.js",
                  "src/js/emotion-engine.js", "src/js/face-engine.js"):
            os.makedirs(os.path.join(td, *os.path.dirname(f).split("/")), exist_ok=True)
            shutil.copy(ROOT / f, os.path.join(td, f))
        for f in AU_DIR.glob("*.json"):
            os.makedirs(os.path.join(td, "_test/face-au"), exist_ok=True)
            shutil.copy(f, os.path.join(td, "_test/face-au", f.name))
        rp = os.path.join(td, "src/data/face-smile-rules.js")
        orig = open(rp, encoding="utf-8").read()
        # 腿1：flatMin 抬到 0.30（远高于眼区观测最小 0.1978）⇒ 真照大面积误判遮挡 ⇒ A3 必红
        open(rp, "w", encoding="utf-8").write(orig.replace("flatMin: 0.03", "flatMin: 0.30"))
        d1, e1 = run_node(Path(td))
        ok1 = bool(d1) and d1["fp"] > 0
        msgs.append("腿1 flatMin 抬到 0.30 ⇒ %s（误命中 %s）"
                    % ("真照被判遮挡，尺抓到了" if ok1 else "仍 0（尺无牙：%s）" % e1,
                       d1["fp"] if d1 else "?"))
        red_any |= 0 if ok1 else 1
        open(rp, "w", encoding="utf-8").write(orig)
        # 腿2：拆掉 assessQuality 的 occluded 判定 ⇒ 墨镜/帽子变体重新笃定 ⇒ A4 必红
        ep = os.path.join(td, "src/js/face-engine.js")
        eng = open(ep, encoding="utf-8").read()
        mut = eng.replace('reasons.push("occluded-eye")', "0").replace('reasons.push("occluded-brow")', "0")
        open(ep, "w", encoding="utf-8").write(mut)
        d2, e2 = run_node(Path(td))
        ok2 = bool(d2) and (d2["out"]["墨镜"]["confident"] > 0 or d2["out"]["帽子"]["confident"] > 0)
        msgs.append("腿2 拆掉 occluded 判定 ⇒ %s（墨镜笃定 %s）"
                    % ("遮挡重新变得笃定，尺抓到了" if ok2 else "仍 0（尺无牙：%s）" % e2,
                       d2["out"]["墨镜"]["confident"] if d2 else "?"))
        red_any |= 0 if ok2 else 1
    for m in msgs:
        print("  " + m)
    if red_any:
        print("F17-SELFTEST-FAIL 变异腿没全部被抓到 ⇒ 判据无牙")
        return 1
    print("F17-SELFTEST-PASS 两条变异腿都被抓到")
    return 0


if __name__ == "__main__":
    sys.exit(main())
