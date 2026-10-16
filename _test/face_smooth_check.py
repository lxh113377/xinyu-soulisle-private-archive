# -*- coding: utf-8 -*-
"""F18 - 表情**噪声过滤（EMA 平滑）**尺（r184 新增；目标#2 的「噪声过滤」）

为什么单开一条尺：需求#2 点名「噪声过滤」，而 EMA 是系统里**唯一的**噪声过滤环节，
  却长期零覆盖 —— 它藏在有状态的 smooth() 里，判据够不着。
  r184 把单步内核拆成纯函数 emaStep(prev, bs, a) 并挂出来（同 regionFlat/yawRatio 的范式），
  本尺才有得量。

量什么：**平滑度与响应延迟的权衡**（同 F12「棘轮与目标线分家」的思路，给曲线不给单一数）。
  交替噪声 ±0.3 打在同一维上，看输出逐帧差降到输入的多少；阶跃 0→1 看多少帧到 90%。
  实测曲线（α=0.3 为现行值）：

    α      抖动占输入   达 90% 帧数（8fps 采样）
    0.05      2.6%        >40（≈5s，跟不动）
    0.10      5.3%         22
    0.20     11.2%         11
    0.30     17.8%          7   ← 现行
    0.50     33.6%          4
    0.70     54.2%          2
    1.00    100.0%          1（等于关掉过滤）

四条常驻断言：
  A1 抖动必须真被压住：现行 α 下输出抖动占输入 ≤ 35%（实测 17.8%，留 2× 余量）
  A2 但不得平滑到跟不动：达 90% 用时 ≤ 12 帧（实测 7；8fps 下 = 1.5s 上限）
  A3 α 必须合法且与 rules 同源：0 < α < 1（=1 是关闭过滤、→0 是冻结画面）
  A4 权衡曲线的形状必须成立：α 单调增 ⇒ 抖动单调不减 **且** 响应帧数单调不增
     （防有人改出一个"两边都要"的假参数）

用法：
  python _test/face_smooth_check.py            # 复算 + 四断言 + 权衡曲线
  python _test/face_smooth_check.py --selftest # 变异演习：关过滤 / 过度平滑 / 内核直通，三腿必翻红
退出码：0=PASS 1=断言红 2=未验（node 不可用 ⇒ 绝不判绿）
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

NODE = r"""
const {readFileSync} = require("fs");
const vm = require("vm");
const ROOT = process.argv[2];
const S = (p) => readFileSync(ROOT + "/" + p, "utf8");
const ctx = vm.createContext({window: {}, console, require});
for (const f of ["src/data/emotion-lexicon.js", "src/js/emotion-engine.js",
                  "src/data/face-smile-rules.js", "src/js/face-engine.js"]) vm.runInContext(S(f), ctx);
const FE = ctx.window.FaceEngine, R = ctx.window.__XINYU_FACE_RULES__;
const KEYS = ["browInnerUp", "mouthSmileLeft", "mouthSmileRight", "jawOpen", "eyeSquintLeft"];
const mk = (v) => { const o = {}; for (const k of KEYS) o[k] = v; return o; };
const run = (a, seq) => { let prev = null; return seq.map((bs) => (prev = FE.emaStep(prev, bs, a))); };
const meanAbsDiff = (xs) => { let s = 0; for (let i = 1; i < xs.length; i++) s += Math.abs(xs[i] - xs[i - 1]); return xs.length > 1 ? s / (xs.length - 1) : 0; };
const noisy = []; for (let i = 0; i < 40; i++) noisy.push(mk(0.5 + (i % 2 ? 0.3 : -0.3)));
const step = []; for (let i = 0; i < 60; i++) step.push(mk(i < 10 ? 0 : 1));
const inJit = meanAbsDiff(noisy.map((b) => b[KEYS[0]]));
const ALPHAS = [0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 1.0];
/* 把**现行 α** 并进曲线：否则有人把 α 改成表外的值，A3 会报"量不到" —— 那是尺子的脆性，
   不是参数的问题。并进来之后任何 α 都能被量到，A1/A2 才有意义。 */
if (!ALPHAS.some((x) => Math.abs(x - R.smooth.alpha) < 1e-9)) ALPHAS.push(R.smooth.alpha);
ALPHAS.sort((x, y) => x - y);
const curve = ALPHAS.map((a) => {
  const out = run(a, noisy).map((o) => o[KEYS[0]]);
  const st = run(a, step).map((o) => o[KEYS[0]]);
  let n90 = -1;
  for (let i = 10; i < st.length; i++) if (st[i] >= 0.9) { n90 = i - 9; break; }
  return {a: a, jitter: meanAbsDiff(out), ratio: meanAbsDiff(out) / inJit, n90: n90};
});
console.log(JSON.stringify({alpha: R.smooth.alpha, inJitter: inJit, curve: curve}));
"""


def run_node(root, code=None):
    with tempfile.TemporaryDirectory() as td:
        script = os.path.join(td, "f18_probe.cjs")
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


def check(data):
    """四断言。返回 (bad, 现行行)。抽成纯函数 ⇒ 变异腿验的是判据本身，不是"数据变了"。"""
    bad = []
    cur = [c for c in data["curve"] if abs(c["a"] - data["alpha"]) < 1e-9]
    if not cur:
        bad.append("A3 现行 α=%s 不在曲线里 ⇒ 本尺量不到实际生效的参数" % data["alpha"])
        return bad, None
    cur = cur[0]
    if not (0 < data["alpha"] < 1):
        bad.append("A3 α=%s 非法：=1 等于关闭过滤、<=0 等于冻结画面" % data["alpha"])
    if cur["ratio"] > 0.35:
        bad.append("A1 抖动没被压住：输出抖动占输入 %.1f%%（线 35%%）" % (100.0 * cur["ratio"]))
    if cur["n90"] < 0 or cur["n90"] > 12:
        bad.append("A2 平滑到跟不动：达 90%% 用时 %s 帧（线 12 帧；-1=窗口内没到）" % cur["n90"])
    for i in range(1, len(data["curve"])):
        p, q = data["curve"][i - 1], data["curve"][i]
        if q["ratio"] < p["ratio"] - 1e-9:
            bad.append("A4 曲线形状破了：α %.2f->%.2f 抖动反而变小" % (p["a"], q["a"]))
        if p["n90"] >= 0 and q["n90"] >= 0 and q["n90"] > p["n90"]:
            bad.append("A4 曲线形状破了：α %.2f->%.2f 响应反而更慢" % (p["a"], q["a"]))
    return bad, cur


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    data, err = run_node(ROOT)
    if data is None:
        print("F18-UNVERIFIED %s" % err)
        return 2
    bad, cur = check(data)
    print("噪声过滤尺（F18）：现行 α=%s｜输入抖动 %.4f（交替噪声 ±0.3）" % (data["alpha"], data["inJitter"]))
    print("  %-6s %-14s %-12s" % ("α", "抖动占输入", "达90%帧数"))
    for c in data["curve"]:
        mark = "  <- 现行" if abs(c["a"] - data["alpha"]) < 1e-9 else ""
        print("  %-6s %-14s %-12s%s" % (c["a"], "%.1f%%" % (100.0 * c["ratio"]), c["n90"], mark))
    if cur:
        print("  A1 抖动压制到 %.1f%%（线 <=35%%）｜A2 响应 %d 帧（线 <=12）" % (100.0 * cur["ratio"], cur["n90"]))
    if bad:
        print("F18-FAIL %d 项" % len(bad))
        for b in bad:
            print("  " + b)
        return 1
    if a.selftest:
        return selftest()
    print("F18-PASS 四断言(A1/A2/A3/A4)全过｜现行 α=%s" % data["alpha"])
    return 0


def selftest():
    """三条变异腿，每条都必须让**判据**翻红（而不是数据变了）。"""
    msgs, red_any = [], 0
    # ⚠️ 锚点必须逐字对齐探针真实的那一行（首版写成带分号的版本 ⇒ 变体没生效 ⇒ 腿1/腿2 假绿）
    inj = "const FE = ctx.window.FaceEngine, R = ctx.window.__XINYU_FACE_RULES__;"
    d1, e1 = run_node(ROOT, NODE.replace(inj, inj + " ctx.window.__XINYU_FACE_RULES__.smooth.alpha = 1.0;"))
    bad1 = check(d1)[0] if d1 else ["探针失败"]
    ok1 = any(x.startswith("A1") for x in bad1)
    msgs.append("腿1 α 掐到 1.0（关闭过滤）⇒ %s" % ("A1 当场翻红" if ok1 else "A1 仍绿（尺无牙：%s）" % (e1 or bad1)))
    red_any |= 0 if ok1 else 1
    d2, e2 = run_node(ROOT, NODE.replace(inj, inj + " ctx.window.__XINYU_FACE_RULES__.smooth.alpha = 0.03;"))
    bad2 = check(d2)[0] if d2 else ["探针失败"]
    ok2 = any(x.startswith("A2") for x in bad2)
    msgs.append("腿2 α 掐到 0.03（过度平滑）⇒ %s" % ("A2 当场翻红" if ok2 else "A2 仍绿（尺无牙：%s）" % (e2 or bad2)))
    red_any |= 0 if ok2 else 1
    with tempfile.TemporaryDirectory() as td:
        for f in ("src/data/emotion-lexicon.js", "src/data/face-smile-rules.js",
                  "src/js/emotion-engine.js", "src/js/face-engine.js"):
            os.makedirs(os.path.join(td, *os.path.dirname(f).split("/")), exist_ok=True)
            shutil.copy(ROOT / f, os.path.join(td, f))
        ep = os.path.join(td, "src/js/face-engine.js")
        eng = open(ep, encoding="utf-8").read()
        anchor = "for (const k in bs) o[k] = prev ? a * bs[k] + (1 - a) * (prev[k] || 0) : bs[k];"
        mut = eng.replace(anchor, "for (const k in bs) o[k] = bs[k];")
        if mut == eng:
            msgs.append("腿3 变体没生效（锚点失配）⇒ 本条未验")
            red_any |= 1
        else:
            open(ep, "w", encoding="utf-8").write(mut)
            d3, e3 = run_node(Path(td))
            bad3 = check(d3)[0] if d3 else ["探针失败"]
            ok3 = any(x.startswith("A1") for x in bad3)
            msgs.append("腿3 EMA 内核改直通 ⇒ %s" % ("A1 当场翻红" if ok3 else "A1 仍绿（尺无牙：%s）" % (e3 or bad3)))
            red_any |= 0 if ok3 else 1
    for s in msgs:
        print("  " + s)
    if red_any:
        print("F18-SELFTEST-FAIL 变异腿没全部被抓到 ⇒ 判据无牙")
        return 1
    print("F18-SELFTEST-PASS 三条变异腿都被抓到")
    return 0


if __name__ == "__main__":
    sys.exit(main())
