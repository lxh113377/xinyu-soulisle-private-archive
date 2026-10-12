# -*- coding: utf-8 -*-
"""F12 · 表情**低强度段三态**尺（r127 新增；face-diag 的「先尺后改」地基）

问的问题（与 F11 不重复，逐字对照过）：
  F11 `face_discrim_check.py` 量的是**分类判别力**：跨类混淆、负样本假阳性、
  强度**单调性**、饱和率、margin 可分性。它明确允许「弱 joy 退回 calm」（其 CASES 里
  `joy_weak` 就把 .2 的微笑标成期望 calm），所以 F11 判不出用户投诉的那件事。
  用户 2026-10-12 实测原话：「必须做明显表情（露齿）才判微笑」「愤怒识别不到」——
  机理不是 argmax 翻成 calm，而是**翻成 calm 之后界面仍然笃定显示**（r124 §一：
  轻微笑 .22 → calm 0.381 > joy 0.217，读数面上看不出"我在猜"）。
  ⇒ 本尺量的量 = 低强度段每一帧落在哪个态（**五态**）：
      hit              判对**且**引擎标了置信 ⇒ 计入「有把握帧」
      hit_lean         判对但引擎没标置信 ⇒ 不算有把握（虚高命中率的那一类，单列）
      soft_ok          退回 calm 且未标置信（诚实的"看不出来"，合格）
      uncertain        未标置信但报了非期望情绪（可接受，界面该出"仅供参考"）
      wrong_confident  **标了置信却报错** ⇒ 这才是"笃定地骗人"，用户体感的直接来源
  口径取自老大拍板的目标：有把握帧 top-1 ≥95%、不确定帧 ≤30%（`memory/11-face-accuracy.md`）。

棘轮与目标线分家（这条是设计要点，不是客套）：
  - **判红只看棘轮**：`wrong_confident` 变多、或 confident 子集命中率变低 ⇒ 红。
  - **目标线只点名不判红**：今天低强度段远未达标，若把它做成闸门，这条套件第一次接线
    就是一条"正常提交也变不了绿"的永红判据；届时唯一的绿灯途径就是虚报。
    ⇒ 缺口以「缺口在册」字样常驻判定行，被 `memory/11-face-accuracy.md` 的执行序追踪。

输入是 FACS/AU **合成向量的低强度缩放**，不是真实照片（真照片那一层是 face-diag S4，
需要人工标注，本尺不冒充它，也不替代 F5）。零摄像头、零网络、零密钥。

用法：
  python _test/face_lowintensity_check.py            # 复算 + 与基线棘轮对账
  python _test/face_lowintensity_check.py --update   # 把更优水位写回基线（只升不降）
  python _test/face_lowintensity_check.py --selftest # 六腿反例自证（应红的红、应绿的绿）
  python _test/face_lowintensity_check.py --json     # 机器可读
退出码：0=无回退 1=回退 2=未验（node 不可用/格数对不上 ⇒ 绝不判绿）
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = str(Path(__file__).resolve().parents[1])
BASE_FILE = Path(ROOT) / "_test" / "face-lowintensity-baseline.json"
LEVELS = [0.12, 0.22, 0.30, 0.40, 0.45]

# 基向量取自 F11 的 CASES（同一套 AU 语义，不另造一份形状真相）；
# 每条 = (类名, 基向量)。缩放方式 = 把该向量的最大 AU 压到 LEVELS 的档位值。
SHAPES = [
    ("joy", {"mouthSmileLeft": .8, "mouthSmileRight": .8, "cheekSquintLeft": .6,
             "cheekSquintRight": .6, "eyeSquintLeft": .5, "eyeSquintRight": .5}),
    ("anger", {"browDownLeft": .65, "browDownRight": .65}),
    ("sadness", {"mouthFrownLeft": .8, "mouthFrownRight": .8, "browInnerUp": .6}),
    ("fear", {"browInnerUp": .8, "eyeWideLeft": .6, "eyeWideRight": .6,
              "mouthStretchLeft": .5, "mouthStretchRight": .5}),
    ("surprise", {"jawOpen": .8, "browInnerUp": .8, "browOuterUpLeft": .7,
                  "browOuterUpRight": .7, "eyeWideLeft": .5, "eyeWideRight": .5}),
    ("disgust", {"noseSneerLeft": .7, "noseSneerRight": .7,
                 "mouthUpperUpLeft": .6, "mouthUpperUpRight": .6}),
]
# calm 期望的负样本（低强度段同样不许笃定报错）
NEGATIVES = [("neutral", {}), ("speaking", {"jawOpen": .5, "mouthFunnel": .3}),
             ("lips_pressed", {"mouthPressLeft": .4, "mouthPressRight": .4})]
EXPECT = {"joy": "joy", "anger": "anger", "sadness": "sadness", "fear": "fear",
          "surprise": "surprise", "disgust": "disgust",
          "neutral": "calm", "speaking": "calm", "lips_pressed": "calm"}
TARGET_CONF_ACC = 0.95
TARGET_UNCERTAIN_MAX = 0.30

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
  const v = JSON.parse(JSON.stringify(FE.read(c.vec || {})));
  out.push({name: c.name, level: c.level, want: c.want, got: v.emotion,
            confident: !!v.confident, confidence: v.confidence,
            intensity: v.intensity, top: v.all[0].score,
            second: v.all[1] ? v.all[1].score : 0});
}
console.log(JSON.stringify(out));
"""


def scaled(base, level):
    """把基向量整体缩放，使最大 AU 恰为 level（低强度档的真实形态是"整体弱"而非"只动一个 AU"）。"""
    peak = max(base.values()) if base else 0.0
    if not peak:
        return dict(base)
    return {k: round(v * level / peak, 4) for k, v in base.items()}


def build_cases():
    cases = []
    for name, vec in SHAPES + NEGATIVES:
        for lv in LEVELS:
            cases.append({"name": "%s@%s" % (name, lv), "level": lv,
                          "vec": scaled(vec, lv), "want": EXPECT[name]})
    return cases


def run_probe():
    """在受管根之外落探针并跑 node：仓库不留临时件。"""
    with tempfile.TemporaryDirectory() as td:
        script = os.path.join(td, "f12_probe.mjs")
        with open(script, "w", encoding="utf-8") as fh:
            fh.write("const CASES = " + json.dumps(build_cases(), ensure_ascii=False) + ";\n")
            fh.write(PROBE)
        try:
            p = subprocess.run(["node", script, ROOT], capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=180)
        except FileNotFoundError:
            return None, ["node 不可用（CommandNotFound）⇒ F12 未验"]
        except subprocess.TimeoutExpired:
            return None, ["node 探针超时 180s ⇒ F12 未验"]
        if p.returncode != 0 or not (p.stdout or "").strip():
            return None, ["F12 node 探针跑不起来 rc=%s：%s" % (p.returncode, (p.stderr or "")[:300])]
        try:
            data = json.loads(p.stdout.strip().splitlines()[-1])
        except Exception as e:  # noqa: BLE001
            return None, ["F12 探针输出解析失败：%s" % e]
    want_n = len(SHAPES + NEGATIVES) * len(LEVELS)
    if not isinstance(data, list) or len(data) != want_n:
        return None, ["F12 格数对不上：期望 %d 实得 %s（不得按少下来的格子判绿）"
                      % (want_n, len(data) if isinstance(data, list) else "非列表")]
    return data, []


def classify(rec):
    """五态口径（口径见模块 docstring）。

    判对**且**引擎标了置信才算 `hit`；判对但未标置信记 `hit_lean` —— 它不能进
    「有把握帧」分母，否则老大口径里的 top-1 ≥95% 会被"其实心里没底却猜对"的帧虚高。
    """
    if rec["got"] == rec["want"]:
        return "hit" if rec["confident"] else "hit_lean"
    if not rec["confident"]:
        return "soft_ok" if rec["got"] == "calm" else "uncertain"
    return "wrong_confident"


def tally(data):
    keys = ["hit", "hit_lean", "soft_ok", "uncertain", "wrong_confident"]
    t = dict((k, 0) for k in keys)
    by_level, wrong_names = {}, []
    for rec in data:
        st = classify(rec)
        t[st] += 1
        lv = by_level.setdefault(rec["level"], {"n": 0, "hit": 0, "wrong_confident": 0})
        lv["n"] += 1
        lv["hit"] += 1 if st in ("hit", "hit_lean") else 0
        lv["wrong_confident"] += 1 if st == "wrong_confident" else 0
        if st == "wrong_confident":
            wrong_names.append(rec["name"])
    n = len(data)
    confident = t["hit"] + t["wrong_confident"]
    return {
        "frames": n, "levels": len(LEVELS), "shapes": len(SHAPES + NEGATIVES),
        "hit": t["hit"], "hit_lean": t["hit_lean"], "soft_ok": t["soft_ok"],
        "uncertain": t["uncertain"], "wrong_confident": t["wrong_confident"],
        "wrong_names": wrong_names[:8],
        "by_level": {str(k): v for k, v in sorted(by_level.items())},
        "confident_frames": confident,
        "acc_on_confident": round(t["hit"] / confident, 4) if confident else None,
        "uncertain_rate": round((t["hit_lean"] + t["uncertain"] + t["soft_ok"]) / n, 4),
    }


def ratchet(cur, base):
    """棘轮：笃定错报帧数不得增多、置信子集命中率不得下降（两者同分母 = 格数由夹具定死）。"""
    bad = []
    if not base:
        return ["F12 无基线（先跑 --update 建立水位基线，否则棘轮无参照）"], []
    if cur["frames"] != base.get("frames"):
        bad.append("F12 格数变了 %s → %s（夹具改动须同步重建基线，不许沿用旧水位判绿）"
                   % (base.get("frames"), cur["frames"]))
        return bad, []
    if cur["wrong_confident"] > base.get("wrong_confident", 0):
        bad.append("F12 笃定错报帧增多 %s → %s（新增：%s）"
                   % (base.get("wrong_confident"), cur["wrong_confident"],
                      ",".join(cur["wrong_names"][:3])))
    ca, cb = cur["acc_on_confident"], base.get("acc_on_confident")
    if ca is not None and cb is not None and ca < cb:
        bad.append("F12 置信子集命中率下降 %s → %s" % (cb, ca))
    return bad, []


def verdict(cur, base, bad, notes):
    # 百分号一律走 str 拼接：同一字符串被 % 格式化两次会把 "%" 变成 "%%"（本轮实测踩过）
    acc = "n/a" if cur["acc_on_confident"] is None else "%.1f" % (100 * cur["acc_on_confident"])
    unc = "%.1f" % (100 * cur["uncertain_rate"])
    gap = ("目标 有把握帧 top-1 >=" + str(int(TARGET_CONF_ACC * 100))
           + " / 不确定帧 <=" + str(int(TARGET_UNCERTAIN_MAX * 100))
           + "；现 有把握帧 " + acc + " / 不确定 " + unc + " ⇒ 缺口在册")
    tail = ("格 " + str(cur["frames"]) + "（" + str(cur["levels"]) + " 档 x "
            + str(cur["shapes"]) + " 形态）｜有把握判对 " + str(cur["hit"]) + "｜判对但没底 "
            + str(cur["hit_lean"]) + "｜诚实退calm " + str(cur["soft_ok"]) + "｜没底报错 "
            + str(cur["uncertain"]) + "｜笃定错报 " + str(cur["wrong_confident"]) + "｜" + gap)
    if bad:
        return "FACE-LOWINTENSITY-FAIL " + "; ".join(bad) + " ‖ " + tail, 1
    if notes:
        return "FACE-LOWINTENSITY-UNVERIFIED " + "; ".join(notes) + " ‖ " + tail, 2
    return ("FACE-LOWINTENSITY-PASS 水位无回退（基线 " + str((base or {}).get("updated"))
            + "）‖ " + tail), 0


def selftest(base):
    """六腿反例自证：应红的红并点名、应绿的绿、可单降的项不得连带，取数不全不得判绿。"""
    def rec(name, want, got, confident):
        return {"name": name, "level": LEVELS[0], "want": want, "got": got,
                "confident": confident, "confidence": 0.5, "intensity": 0.3,
                "top": 0.4, "second": 0.2}
    # 基线形态：2 帧有把握判对、1 帧笃定错报、1 帧诚实退回 calm ⇒ 置信子集 3、命中 2
    base_data = [rec("a", "joy", "joy", True), rec("b", "anger", "anger", True),
                 rec("c", "fear", "sadness", True), rec("d", "disgust", "calm", False)]
    b_same = tally(base_data)
    # 只把 b 从「有把握判对」改成「判对但没底」：笃定错报不变，置信子集命中率单降
    acc_only = list(base_data); acc_only[1] = rec("b", "anger", "anger", False)
    # 把 d 从「诚实退回 calm」改成「笃定报错」：笃定错报增多，命中率也降（两条都该点名）
    lie = list(base_data); lie[3] = rec("d", "disgust", "sadness", True)
    red_of = lambda d, b: ratchet(d, b)[0]          # noqa: E731  只取红项，腿形状统一
    legs = [
        ("水位相同 ⇒ 绿", red_of(tally(list(base_data)), b_same), []),
        ("命中率单降（笃定错报未增）⇒ 只点命中率这一条", red_of(tally(acc_only), b_same),
         ["置信子集命中率下降", "!笃定错报帧增多"]),
        ("笃定错报增多 ⇒ 红并点名", red_of(tally(lie), b_same),
         ["笃定错报帧增多", "置信子集命中率下降"]),
        ("无基线 ⇒ 红（新尺不得裸判绿）", red_of(tally(list(base_data)), None), ["无基线"]),
        ("格数变更 ⇒ 红（禁沿用旧水位）",
         red_of({**tally(list(base_data)), "frames": 3}, b_same), ["格数变了"]),
        ("classify 五态口径 ⇒ 逐态对号（顺序敏感）",
         [" | ".join([classify(rec("x", "joy", "joy", False)),
                      classify(rec("y", "joy", "calm", False)),
                      classify(rec("z", "joy", "sadness", True)),
                      classify(rec("w", "joy", "joy", True)),
                      classify(rec("v", "joy", "anger", False))])],
         ["hit_lean | soft_ok | wrong_confident | hit | uncertain"]),
    ]
    ok, detail = True, []
    for name, seen, want in legs:
        joined = " | ".join(seen)
        miss = [k for k in want if not k.startswith("!") and k not in joined]
        leak = [k for k in want if k.startswith("!") and k[1:] in joined]
        wrong = bool(miss or leak) or (not want and bool(seen))
        ok = ok and not wrong
        detail.append("%s%s（项%s%s）" % ("✗" if wrong else "✓", name, len(seen),
                                         "｜连带不该红:" + ",".join(leak) if leak else ""))
    n_ok = sum(1 for d in detail if d.startswith("✓"))
    for d in detail:
        print("  " + d)
    print("F12-SELFTEST-%s %d/%d 腿（应红的红、应绿的绿）" % ("PASS" if ok else "FAIL", n_ok, len(legs)))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--update", action="store_true", help="把更优水位写回基线（只升不降）")
    ap.add_argument("--force", action="store_true", help="允许 --update 写低（须说明理由）")
    ap.add_argument("--selftest", action="store_true", help="六腿反例自证")
    ap.add_argument("--json", action="store_true", help="机器可读输出")
    a = ap.parse_args()

    base = json.loads(BASE_FILE.read_text(encoding="utf-8")) if BASE_FILE.exists() else None
    if a.selftest:
        return selftest(base)

    data, unverified = run_probe()
    if data is None:
        print("FACE-LOWINTENSITY-UNVERIFIED 取数失败 ⇒ 不判绿（格数/命中率/态分布一律未验）‖ %s"
              % "; ".join(unverified))
        return 2
    cur = tally(data)
    bad, notes = ratchet(cur, base)
    if a.update:
        if bad and not a.force and base:
            print("F12-UPDATE-REFUSED 存在回退项，棘轮不允许写低：%s" % "; ".join(bad[:2]))
            return 1
        payload = dict(cur)
        payload["updated"] = __import__("datetime").date.today().isoformat()
        payload["why"] = ("低强度段三态水位基线；口径与判据同文件 docstring，"
                          "目标线（有把握帧 ≥95%／不确定 ≤30%）来自 memory/11-face-accuracy.md")
        BASE_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("F12-BASELINE-UPDATED -> %s（笃定错报 %s 帧 / 置信子集命中 %s）"
              % (BASE_FILE.name, cur["wrong_confident"], cur["acc_on_confident"]))
    if a.json:
        print(json.dumps({"cur": cur, "bad": bad, "unverified": unverified}, ensure_ascii=False))
    line, rc = verdict(cur, base, bad, notes + unverified)
    print(line)
    return rc


if __name__ == "__main__":
    sys.exit(main())
