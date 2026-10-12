# -*- coding: utf-8 -*-
"""face_au_replay_check.py — 真照片 AU 回放尺（S4 主尺，轮132）

量什么：`_test/face-au/*.json`（由 `face_au_export.py` 从**真实照片**跑 MediaPipe 导出的
52 维 blendshape）→ 在 node 里用**当前** `src/js/face-engine.js` + `src/data/face-smile-rules.js`
复算 `FaceEngine.read(bs)` → 逐类 top-1。**零浏览器、零摄像头、零网络、零密钥。**

为什么要有这把尺（不是"补个测试"这么轻）：
  F11 `face_discrim_check.py` 与 F12 `face_lowintensity_check.py` 的输入都是**合成 AU 向量**，
  两者的 docstring 都写明「不能当成真实场景准确率」；真照片那一层此前只挂在 F5 里
  （12 张、4 类、且 F5/F10 需摄像头，本机实测挂起）。⇒ 真实流此前**没有常驻尺子**，
  「改完到底准不准」只能靠肉眼。本尺把那一层变成可复跑的机器面。

⚠️ **证据等级必须说清（防把本尺读成"真实场景准确率已达标"）**：
  语料 12 张**全是表演级强度**（明摆着的笑/怒/惊/中性），零张 0.1~0.4 低强度样本，
  且只覆盖 joy/calm/anger/surprise 四类 —— fear/sadness/disgust/contempt 零真照。
  ⇒ 本尺当前测的是「**高强度段 + 已覆盖四类**判得对不对」，
  它**测不到**用户投诉的低强度沉底问题（S1 的靶场）。低强度段由 F12 负责，两者互补不重叠。

棘轮与目标线分家（沿用 F12 同款设计，不是客套）：
  - **判红只看棘轮**：`hit`/`acc` 变少 ⇒ 红。
  - **目标线（有把握帧 top-1 ≥95%）只点名不判红**：今天真照片层远未达标，
    把它做成闸门，这条套件第一次接线就是一条「正常提交也变不了绿」的永红判据，
    届时唯一的绿灯途径就是虚报。缺口以「缺口在册」字样常驻判定行。

用法：
  python _test/face_au_replay_check.py              # 复算 + 与基线棘轮对账
  python _test/face_au_replay_check.py --update     # 把更优水位写回基线（只升不降）
  python _test/face_au_replay_check.py --selftest   # 变异演习（尺子必须能翻红）
  python _test/face_au_replay_check.py --json       # 机器可读
退出码：0=无回退 1=回退/名册坏 2=未验（node 不可用 / 语料为空 ⇒ 绝不判绿）
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

from check_instrument import install_excepthook   # r113：失败路径自己不能崩
install_excepthook("FACE-AU-REPLAY")

ROOT = Path(__file__).resolve().parents[1]
AU_DIR = ROOT / "_test" / "face-au"
BASE_FILE = ROOT / "_test" / "face-au-baseline.json"

# 与 face_au_export.py 的 WANT 同表；两处各写一份是刻意的（导出腿与复算腿互不 import，
# 免得复算腿被导出腿的 bug 带着一起错）。改映射必须两处同改。
WANT = {"smiling": "joy", "neutral": "calm", "anger": "anger", "surprise": "surprise"}

NODE_PROBE = r"""
const ROOT = process.argv[2];
const {readFileSync} = require('fs');
const {createContext, runInContext} = require('vm');
const S = (p) => readFileSync(ROOT + '/' + p, 'utf8');
const ctx = createContext({window: {}, console});
for (const f of ['src/data/emotion-lexicon.js', 'src/data/face-smile-rules.js',
                 'src/js/emotion-engine.js', 'src/js/face-engine.js']) {
  runInContext(S(f), ctx, {filename: f});
}
const FE = ctx.window.FaceEngine;
const rows = JSON.parse(readFileSync(process.argv[3], 'utf8'));
const out = rows.map(r => {
  const v = FE.read(r.bs);
  return {file: r.file, label: r.label, want: r.want,
          got: v.emotion, intensity: v.intensity,
          confidence: v.confidence, confident: v.confident,
          stored_emotion: (r.view || {}).emotion || null};
});
console.log(JSON.stringify(out));
"""


def load_corpus():
    """读语料。空目录 / 坏 JSON / 未知 label 一律走"未验或判红"，禁当空集合判绿。"""
    if not AU_DIR.is_dir():
        return None, ["语料目录不存在：%s（先跑 python _test/face_au_export.py）" % AU_DIR]
    files = sorted(AU_DIR.glob("*.json"))
    if not files:
        return None, ["语料为空（_test/face-au/ 下 0 个 JSON）⇒ 没有样本就没有准确率，禁判绿"]
    rows, bad = [], []
    for p in files:
        try:
            d = json.loads(p.read_text("utf-8"))
        except Exception as e:  # noqa: BLE001
            bad.append("%s 不可解析：%s" % (p.name, e))
            continue
        lab = d.get("label")
        if lab not in WANT:
            bad.append("%s 的标注 %r 不在映射表内 ⇒ 显式报错，不静默忽略" % (p.name, lab))
            continue
        bs = d.get("bs")
        if not isinstance(bs, dict) or not bs:
            bad.append("%s 的 bs 缺失或非字典 ⇒ 分母不可信" % p.name)
            continue
        rows.append(d)
    if bad:
        return None, bad
    return rows, []


def classify(rec):
    """五态口径（与 F12 同口径，见 F12 docstring）。

    判对**且**引擎标了置信才算 `hit`；判对但未标置信记 `hit_lean` —— 它不进「有把握帧」
    分母，否则老大口径的 top-1 ≥95% 会被「其实没底却猜对」虚高。
    """
    if rec["got"] == rec["want"]:
        return "hit" if rec["confident"] else "hit_lean"
    if not rec["confident"]:
        return "soft_ok" if rec["got"] == "calm" else "uncertain"
    return "wrong_confident"


def tally(rows):
    keys = ["hit", "hit_lean", "soft_ok", "uncertain", "wrong_confident"]
    t = dict((k, 0) for k in keys)
    by_label, wrong = {}, []
    for r in rows:
        st = classify(r)
        t[st] += 1
        b = by_label.setdefault(r["want"], {"n": 0, "hit": 0, "wrong": 0})
        b["n"] += 1
        b["hit"] += 1 if st in ("hit", "hit_lean") else 0
        if st == "wrong_confident":
            b["wrong"] += 1
            wrong.append("%s(%s→%s)" % (r["file"], r["want"], r["got"]))
    n = len(rows)
    confident_n = t["hit"] + t["wrong_confident"]
    return {
        "n": n, **t,
        "by_label": by_label,
        "top1": round((t["hit"] + t["hit_lean"]) / float(n), 4) if n else 0.0,
        "confident_n": confident_n,
        "acc_on_confident": round(t["hit"] / float(confident_n), 4) if confident_n else 0.0,
        "wrong": wrong,
        "stored_mismatch": [r["file"] for r in rows
                            if r.get("stored_emotion") and r["stored_emotion"] != r["got"]],
    }


def node_rows(rows):
    """在 node 里用当前 src 判据复算。语料与探针都落受管根之外（临时副本），仓内不留临时件。"""
    import tempfile
    payload = [{"file": r["file"], "label": r["label"], "want": WANT[r["label"]],
                "bs": r["bs"], "view": r.get("view")} for r in rows]
    d = tempfile.mkdtemp(prefix="face_au_replay_")
    probe = Path(d) / "probe.js"
    data = Path(d) / "rows.json"
    probe.write_text(NODE_PROBE, encoding="utf-8")
    data.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    try:
        p = subprocess.run(["node", str(probe), str(ROOT), str(data)],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=180)
    except FileNotFoundError:
        return None, ["node 不可用（CommandNotFound）⇒ 本尺未验，禁判绿"]
    except subprocess.TimeoutExpired:
        return None, ["node 探针超时 180s ⇒ 本尺未验，禁判绿"]
    if p.returncode != 0 or not (p.stdout or "").strip():
        return None, ["node 探针跑不起来 rc=%s：%s" % (p.returncode, (p.stderr or "")[:300])]
    try:
        got = json.loads(p.stdout.strip().splitlines()[-1])
    except Exception as e:  # noqa: BLE001
        return None, ["探针输出解析失败：%s" % e]
    if not isinstance(got, list) or len(got) != len(rows):
        return None, ["探针行数对不上：期望 %d 实得 %s" % (len(rows), len(got) if isinstance(got, list) else "非列表")]
    return got, []


def load_base():
    if not BASE_FILE.is_file():
        return None
    try:
        return json.loads(BASE_FILE.read_text("utf-8"))
    except Exception:  # noqa: BLE001
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--update", action="store_true", help="把更优水位写回基线（只升不降）")
    ap.add_argument("--selftest", action="store_true", help="变异演习：尺子必须能翻红")
    ap.add_argument("--json", action="store_true", help="机器可读输出")
    a = ap.parse_args()

    rows, bad = load_corpus()
    if rows is None:
        for m in bad:
            print("  " + m)
        print("FACE-AU-REPLAY-UNVERIFIED: %s" % bad[0][:90])
        return 2
    got, bad = node_rows(rows)
    if got is None:
        for m in bad:
            print("  " + m)
        print("FACE-AU-REPLAY-UNVERIFIED: %s" % bad[0][:90])
        return 2
    s = tally(got)

    if a.selftest:
        # 变异腿：把一条记录的 want 改错，正确实现必须**报红**。
        # 若尺子对"标错也照样 PASS"恒绿，它就是装饰，不配进电池。
        mut = [dict(r) for r in got]
        mut[0] = dict(mut[0], want="__不可能类__")
        ms = tally(mut)
        ok = (ms["top1"] < s["top1"]) and (len(ms["wrong"]) > len(s["wrong"]))
        print("FACE-AU-REPLAY-SELFTEST: %s（原始 top1=%.4f；变异后 top1=%.4f 且 wrong %d→%d）"
              % ("PASS 尺子对错标会翻红" if ok else "FAIL 尺子对错标仍绿=装饰",
                 s["top1"], ms["top1"], len(s["wrong"]), len(ms["wrong"])))
        return 0 if ok else 1

    base = load_base()
    if a.update:
        if base is None or s["acc_on_confident"] > base.get("acc_on_confident", -1):
            BASE_FILE.write_text(json.dumps(s, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            print("AU-BASELINE-UPDATED acc_on_confident=%s" % s["acc_on_confident"])
        else:
            print("AU-BASELINE-KEPT 更优水位已在基线（基线 %s > 本轮 %s，棘轮只升不降）"
                  % (base.get("acc_on_confident"), s["acc_on_confident"]))
        base = load_base() or s

    if a.json:
        print(json.dumps(s, ensure_ascii=False))
    else:
        print("真照片 AU 回放（S4）：样本 %d 张｜top-1 %.1f%%｜有把握帧 %d/%d = %.1f%%"
              % (s["n"], s["top1"] * 100, s["hit"], s["confident_n"], s["acc_on_confident"] * 100))
        print("  五态：hit %d ｜ hit_lean %d（判对但无把握，不进分母）｜ soft_ok %d ｜ uncertain %d ｜ wrong_confident %d"
              % (s["hit"], s["hit_lean"], s["soft_ok"], s["uncertain"], s["wrong_confident"]))
        for lab, b in sorted(s["by_label"].items()):
            print("  %-9s %d/%d" % (lab, b["hit"], b["n"]))
        if s["wrong"]:
            print("  笃定判错：%s" % ", ".join(s["wrong"]))
        if s["stored_mismatch"]:
            print("  ⚠️ 与导出时存下的读数不一致：%s（判据在导出后被改过？）" % ", ".join(s["stored_mismatch"]))
        print("  覆盖面：仅 %s 四类·表演级强度；低强度段由 F12 负责，fear/sadness/disgust/contempt 零真照"
              % "/".join(sorted(set(WANT.values()))))

    if base and s["acc_on_confident"] < base.get("acc_on_confident", 0) - 1e-9:
        print("  ❌ 有把握帧命中率较基线回退（基线 %s → 本轮 %s）" % (base.get("acc_on_confident"), s["acc_on_confident"]))
        print("FACE-AU-REPLAY-FAIL 回退 n=%d" % s["n"])
        return 1
    print("FACE-AU-REPLAY-PASS 无回退 n=%d acc_on_confident=%s 缺口在册（目标≥95%%，本轮不判红）"
          % (s["n"], s["acc_on_confident"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())