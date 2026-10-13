# -*- coding: utf-8 -*-
"""F15 · 细分子维度判据尺（r173 新建）

为什么要单建一把（而不是把断言塞进 face_discrim）：
  r173 新增的 8 个子维度（neutral/duchenne/social/masked/worry/tense/micro/asymmetric）
  **不参与身份类 argmax**，所以 F11 那套"主情绪判对没有"的腿一条都碰不到它们。
  它们一旦悄悄退化（阈值被改、prev 帧被忘传、worry 与 sadness 的判别被抹平），
  现有电池**全绿依旧** —— 又是一个"没被考到 = 考了全对"的坑。
  本尺只问一件事：**每个维度在该亮的时候亮、该灭的时候灭**。

三条最要紧的腿（防"亮得太容易"的假阳性）：
  ②b worry vs sadness：browInnerUp 高 + 无口部向下 ⇒ worry 亮、sadness 灭。
      这两者在 r103 起就是已知**判据上不可分**的一对，本尺把它们的分界钉住 ——
      分界没了，"担忧被读成低落"这件事就从显式退回到暗处。
  ③ micro 必须有 prev 帧才可能亮：无 prev ⇒ micro 恒 false 且标 microAvailable=false。
      防的是"把没传上一帧也说成能看微表情"（= 用算法伪造能力）。

退出码：0=PASS（含反例腿有牙）｜1=FAIL｜2=环境不可用（node 跑不起来 ⇒ 未验，禁判绿）
"""
import argparse
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_DIR = ROOT / "_test"

# (用例名, 向量, prev向量或None, 期望为 true 的维度, 期望为 false 的维度)
CASES = [
    ("neutral", {}, {}, ["neutral"], ["duchenne", "social", "worry", "tense", "asymmetric"]),
    ("duchenne", {"mouthSmileLeft": .8, "mouthSmileRight": .8,
                  "cheekSquintLeft": .5, "cheekSquintRight": .5}, None,
     ["duchenne"], ["social", "neutral", "worry", "tense"]),
    ("social", {"mouthSmileLeft": .7, "mouthSmileRight": .7,
                "cheekSquintLeft": .02, "cheekSquintRight": .02}, None,
     ["social"], ["duchenne", "neutral"]),
    # ②b 判别腿：担忧 vs 低落。同一根 browInnerUp，差别全在"口部是否向下"
    ("worry", {"browInnerUp": .6}, None, ["worry"], ["duchenne", "social", "neutral"]),
    ("sad", {"browInnerUp": .9, "mouthFrownLeft": .5, "mouthFrownRight": .5}, None,
     [], ["worry", "neutral"]),
    ("tense", {"mouthPressLeft": .5, "mouthPressRight": .5,
               "browDownLeft": .4, "browDownRight": .4, "jawOpen": 0}, None,
     ["tense"], ["neutral", "duchenne", "social", "worry"]),
    ("asym", {"mouthSmileLeft": .85, "mouthSmileRight": .10,
              "mouthDimpleLeft": .9, "mouthDimpleRight": .10}, None,
     ["asymmetric"], ["duchenne", "neutral"]),
    # ③ 微表情可用性腿：无 prev ⇒ 不许亮，且必须如实标不可用
    ("micro_noprev", {"jawOpen": .2}, None, [], ["micro"]),
    ("micro_withprev", {"jawOpen": .2}, {"jawOpen": 0}, ["microAvailable"], []),
]

PROBE = r"""
import {readFileSync} from 'fs';
import {createContext, runInContext} from 'vm';
const ROOT = process.argv[2];
const S = (p) => readFileSync(ROOT + '/' + p, 'utf8');
const ctx = createContext({window: {}, console});
for (const f of ['src/data/emotion-lexicon.js', 'src/js/emotion-engine.js',
                 'src/data/face-smile-rules.js', 'src/js/face-engine.js']) runInContext(S(f), ctx);
const FE = ctx.window.FaceEngine;
const out = [];
for (const c of CASES) {
  const [name, vec, prev, on, off] = c;   // Python 侧是元组 ⇒ 落到 JS 是数组
  const v = FE.read(vec || {}, prev || null);
  const s = v.subs || {};
  out.push({name: name, on: on, off: off, subs: s, emotion: v.emotion});
}
console.log(JSON.stringify(out));
"""


def run_probe(cases, rules_text=None):
    """rules_text 非空 ⇒ 在临时副本里跑（变异腿用），不碰仓库里的判据。"""
    with tempfile.TemporaryDirectory() as td:
        root = ROOT
        if rules_text is not None:
            root = Path(td)
            for sub in ("src/data", "src/js"):
                (root / sub).mkdir(parents=True, exist_ok=True)
            import shutil
            for rel in ("src/data/emotion-lexicon.js", "src/js/emotion-engine.js",
                        "src/js/face-engine.js"):
                shutil.copy(ROOT / rel, root / rel)
            (root / "src/data/face-smile-rules.js").write_text(rules_text, encoding="utf-8")
        script = os.path.join(td, "f15_probe.mjs")
        with open(script, "w", encoding="utf-8") as fh:
            fh.write("const CASES = " + json.dumps(cases, ensure_ascii=False) + ";\n")
            fh.write(PROBE)
        try:
            p = subprocess.run(["node", script, str(root)], capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=120)
        except FileNotFoundError:
            raise SystemExit("F15 node 不可用 ⇒ 未验（禁判绿）")
        except subprocess.TimeoutExpired:
            raise SystemExit("F15 探针超时 ⇒ 未验")
    if p.returncode != 0 or not (p.stdout or "").strip():
        raise SystemExit("F15 探针失败 rc=%s：%s" % (p.returncode, (p.stderr or "")[:300]))
    return json.loads(p.stdout.strip().splitlines()[-1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="", help="机器件落盘路径")
    args = ap.parse_args()

    try:
        rows = run_probe(CASES)
    except SystemExit as e:
        print("FACE-SUBS-UNVERIFIED %s" % e)
        return 2

    bad = []
    print("F15 · 细分子维度判据（r173）")
    for r in rows:
        s = r["subs"]
        for k in r["on"]:
            if not s.get(k):
                bad.append("%s：%s 应亮而未亮（subs=%s）" % (r["name"], k, json.dumps(s, ensure_ascii=False)))
        for k in r["off"]:
            if s.get(k):
                bad.append("%s：%s 应灭而亮了 ⇒ 假阳性" % (r["name"], k))
        on = [k for k in s if s[k]]
        print("  %-16s 身份=%-9s 亮=%s" % (r["name"], r["emotion"], ",".join(on) or "（无）"))

    # ── 反例腿：针对性变异，每条都必须让对应维度熄火 ──────────────────────
    # ⚠️ 第一版用的是「把 rules.subs 整块抽掉」，**实测无效**：subsOf 对 R.subs 有硬编码
    #    兜底（`S.worry || {…默认…}`），抽掉整块行为一字不变 ⇒ 腿恒绿，等于没牙。
    #    这正是"判据自证"最容易骗人的地方：变异体看起来更狠，实际没打到任何一条路径。
    #    改成按维度逐条打（下表每条都指明它该让哪个用例的哪个维度熄火）：
    #    ⚠️ 第二轮又错的三处，记下来防再犯：
    #      ① weak.on 抬到 1.0 **不会**让 neutral 熄火 —— neutral 的判据是 `topNC < on`，
    #         on 越大越容易亮；正确方向是 on→0.0。
    #      ② smile.ratioOn 归零后该盯的是 **social 熄没熄**（它会翻成 duchenne），
    #         盯 duchenne 恒亮 ⇒ 腿恒绿。
    #      ③ tense 是 `press≥x || browDown≥y` 的 OR：只抬 press 门槛，browDown 那条路
    #         仍然通 ⇒ 要抬的是 browDown 那条（或两条一起抬）。
    MUTATIONS = [
        ("weak.on 归零 ⇒ neutral 永不可能亮", "on: 0.10, off: 0.26", "on: 0.0, off: 0.26",
         "neutral", "neutral"),
        ("smile.ratioOn 归零 ⇒ 社交笑被误判成真笑", "ratioOn: 0.20", "ratioOn: 0.0",
         "social", "social"),
        ("worry.browInnerUp 抬到 1.5 ⇒ 担忧永不亮", "browInnerUp: 0.35", "browInnerUp: 1.5",
         "worry", "worry"),
        ("tense 两路口径同时抬到 0.9 ⇒ 紧绷永不亮", "mouthPress: 0.30, browDown: 0.30",
         "mouthPress: 0.9, browDown: 0.9", "tense", "tense"),
        ("asym.min 抬到 0.9 ⇒ 不对称永不亮", "min: 0.25", "min: 0.9",
         "asymmetric", "asymmetric"),
    ]
    rules = (ROOT / "src/data/face-smile-rules.js").read_text(encoding="utf-8")
    ran = 0
    for tag, old, new, case_name, dim in MUTATIONS:
        if old not in rules:
            bad.append("变异腿「%s」构造失败：片段 %r 未命中（判据文件已改？先更新本尺）"
                       % (tag, old))
            continue
        mutant = rules.replace(old, new, 1)
        try:
            mrows = run_probe(CASES, rules_text=mutant)
        except SystemExit as e:
            bad.append("变异腿「%s」没跑起来：%s" % (tag, e))
            continue
        ran += 1
        row = next((r for r in mrows if r["name"] == case_name), None)
        still_on = bool(row and (row["subs"] or {}).get(dim))
        print("  反例：%s ⇒ %s：%s" % (tag, dim, "❌ 仍亮着，判据无牙" if still_on else "✅ 熄火"))
        if still_on:
            bad.append("变异「%s」后 %s 仍亮 ⇒ 本尺没在盯它" % (tag, dim))
    if ran == 0:
        bad.append("变异腿一条都没跑起来 ⇒ 自证面为空，不得判 PASS")

    dst = Path(args.json) if args.json else (
        TEST_DIR / ("face-subs-%s.json" % _stamp()))
    dst.write_text(json.dumps({"cases": rows, "bad": bad}, ensure_ascii=False, indent=1),
                   encoding="utf-8")

    if bad:
        print("\nFACE-SUBS-FAIL " + "；".join(bad[:6]))
        return 1
    print("\nFACE-SUBS-PASS %d 用例 × 亮/灭双向断言 + 反例腿有牙（机器件 %s）"
          % (len(rows), dst.relative_to(ROOT)))
    return 0


def _stamp():
    from datetime import datetime
    return datetime.now().strftime("%Y%m%d-%H%M%S")


if __name__ == "__main__":
    sys.exit(main())
