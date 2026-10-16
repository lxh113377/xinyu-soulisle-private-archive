# -*- coding: utf-8 -*-
"""F13 · 表情识别**逐类精确率 / 召回率 / F1** 报告尺（2026-10-13 新建）

为什么非要单建这一把尺（不是给既有三把尺加一行打印）：
  既有三把尺（face_discrim / face_lowintensity / face_au_replay）答的都是
  「这句判断对不对」，输出是**命中率**与**计数**。它们共同缺一样东西：
  **「漏了多少」永远不可见**。举例：fear 的真实照片一张都没有，
  三把尺里 fear 的分数永远是 100%（合成向量 26/26），可它的**召回率其实是 0/0，
  从未被测过** —— 命中率这个口径把「没考过」和「考过了全对」显示成同一个数字。
  要回答「准确率有没有到 90%」，必须换成 P/R/F1 + 混淆矩阵：
    · 精确率（P）：报了 X 的帧里，真有 X 的比例 —— 治「抢别人的类」（需求 3：相似情绪互混）
    · 召回率（R）：真有 X 的帧里，抓出来的比例 —— 治「安静地漏判」（合成尺上看不出的漏判在此现形）
    · F1：两者调和平均 —— 单一指标排序用这个
    · 混淆矩阵：**哪两类互抢**要看这里，P/R 汇总后会把它抹平

三个语料库，认识论地位不同，**禁止混成一个数**（混了就是用合成向量冒充真实准确率）：
  REAL  = 真照片导出的 52 维 AU（`_test/face-au/*.json`）—— 唯一带真实人脸的证据
  SYNTH = FACS 教科书级合成向量（face_discrim_check.CASES）—— 验判据结构，不验真实率
  LOWINT= 低强度网格 5 档 × 10 形态（face_lowintensity_check.build_cases）—— 验低强度段
  ⚠️ 三者都**不是**「随机抽样人群」上的准确率。任何对外表述必须点名语料，见 DISCLAIMER。

本尺**故意不设通过线**（不像其它三把尺有 PASS/FAIL）：
  样本量撑不起阈值 —— REAL 只有 12 张、且 fear/sadness/disgust/contempt 四类零样本。
  在这里挂一个 ≥90% 的门，等于让**没被考过的类自动变绿**
  （这正是「禁自比恒等」那条纪律要防的）：零样本的类既没有 FN 也没有 FP，任何通过线都会放行。
  ⇒ 本尺的门禁职责改为：**反例自证**（§selftest）—— 证明这些数字会坏、会被区分开、
    不会因为少喂样本就变好。真实水位的取舍交给 face_discrim / lowintensity 那两把有牙的尺。

输出：
  控制台人读表 + 机器件 `_test/face-prf-report-<stamp>.json`（**工作区内**，落盘可审计）
"""
import argparse
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_DIR = ROOT / "_test"
AU_DIR = TEST_DIR / "face-au"

DISCLAIMER = (
    "本报告的准确率是「判据在**指定语料**上的表现」，不等于「产品在真实人群上的准确率」。"
    "REAL 语料 12 张真照片仅覆盖 anger/calm/joy/surprise 四类；"
    "fear/sadness/disgust/contempt 四类**零真实样本**（真实召回率未测，不是 100%）。"
    "SYNTH/LOWINT 为合成向量，仅证明判据结构有判别力。"
)

# ── 切片轴：需求要的「不同光照 / 不同人脸角度 / 不同年龄·性别」四轴 ──────────────
# 现状：**只有很少一部分能算**。没标就是没标 —— 本尺对未标注轴输出「不可测」，
# 而不是静默按 0 或按总数补上（补了就是这个数被人当成证据的开始）。
SLICE_AXES = OrderedDict([
    ("lighting", "光照（暗/常/亮）"),
    ("yaw", "人脸角度（正面/侧脸）"),
    ("age_group", "年龄段"),
    ("gender", "性别"),
    ("level", "表情强度档（仅 LOWINT 语料有）"),
])


def _load_mod(name):
    """导入同目录既有脚本，**不复制**它们的样本定义。

    为什么是 import 而不是抄一份 CASES：每多一份真相副本，就多一处「改了这边忘了那边」。
    改样本定义请回源文件；本函数只做取数，导入失败就让自己红，不静默降级用自己的猜测。
    """
    path = TEST_DIR / (name + ".py")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit("F13 依赖缺失：找不到 %s（禁止猜测样本，先修这里）" % path)
    m = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(m)
    except Exception as e:  # noqa: BLE001
        raise SystemExit("F13 导入 %s 失败：%s" % (name, e))
    return m


def build_corpora():
    """返回 OrderedDict(语料名 -> [item...])，item = {name, want, vec, meta}。"""
    corpora = OrderedDict()

    # REAL：真照片 AU。meta 里可能带 lighting/yaw/... —— 老的 12 张导出时还没这套字段，
    # 于是它们在这几根轴上是**未标注**，本报告如实标记。
    real = []
    if AU_DIR.is_dir():
        for fp in sorted(AU_DIR.glob("*.json")):
            try:
                obj = json.loads(fp.read_text(encoding="utf-8"))
            except Exception as e:  # noqa: BLE001
                print("  ⚠️ 跳过无法解析的真照 fixture %s：%s" % (fp.name, e))
                continue
            bs = obj.get("bs")
            want = obj.get("want")
            if not isinstance(bs, dict) or not want:
                print("  ⚠️ 跳过缺 bs/want 的真照 fixture %s" % fp.name)
                continue
            raw = obj.get("meta") or None
            meta = {}
            if isinstance(raw, dict):
                # 轴承接：把导出时的连续量压有限档位，否则每帧一个亮度值 ⇒ 切片全是 n=1 的孤桶。
                # 档位阈值**不在这里重造**：lighting/yaw 的分早由 harness 按 R.quality 算好（lumaBucket/
                # yawBucket），本处只做搬运；这里若再拍一次阈值，就会与样本侧的口径分家。
                for src_k, dst_k in (("lumaBucket", "lighting"), ("yawBucket", "yaw")):
                    if raw.get(src_k) is not None:
                        meta[dst_k] = raw[src_k]
                for k in ("faceSize", "imgW", "imgH"):
                    if raw.get(k) is not None:
                        meta[k] = raw[k]
                # r183b：人口学两轴直接搬运（名册标注 → fixture meta → 切片）。值本身是
                #   人工标注（ethel 旧照=adult、wayuu=elderly 等），不是推断，故不做再分档。
                for k in ("age_group", "gender", "prov", "license"):
                    if raw.get(k) is not None:
                        meta[k] = raw[k]
                meta["source"] = obj.get("source", "")
            real.append({"name": fp.stem, "want": want, "vec": bs, "meta": meta})
    corpora["REAL"] = real

    dm = _load_mod("face_discrim_check")
    cases = getattr(dm, "CASES", None)
    if not cases:
        raise SystemExit("F13 取不到 face_discrim_check.CASES（样本真相源变了？）")
    corpora["SYNTH"] = [{"name": n, "want": w, "vec": v, "meta": {}} for n, v, w in cases]

    lm = _load_mod("face_lowintensity_check")
    if not hasattr(lm, "build_cases"):
        raise SystemExit("F13 取不到 face_lowintensity_check.build_cases")
    corpora["LOWINT"] = [{"name": c["name"], "want": c["want"], "vec": c["vec"],
                          "meta": {"level": c["level"]}} for c in lm.build_cases()]
    return corpora


PROBE = r"""
import {readFileSync} from 'fs';
import {createContext, runInContext} from 'vm';
const ROOT = process.argv[2];
const S = (p) => readFileSync(ROOT + '/' + p, 'utf8');
const ctx = createContext({window: {}, console});
for (const f of ['src/data/emotion-lexicon.js', 'src/js/emotion-engine.js',
                 'src/data/face-smile-rules.js', 'src/js/face-engine.js']) runInContext(S(f), ctx);
const FE = ctx.window.FaceEngine;
const R = ctx.window.__XINYU_FACE_RULES__;
const EEO = ctx.window.EmotionEngine;
const labelOf = (e) => (R.labels && R.labels[e]) ? R.labels[e]
  : (EEO && EEO.labelOf ? EEO.labelOf(e) : e);
const labels = {};
for (const e of R.emotions) labels[e] = labelOf(e);
const out = [];
for (const c of ALL) {
  const t0 = process.hrtime.bigint();
  const v = JSON.parse(JSON.stringify(FE.read(c.vec || {})));
  const t1 = process.hrtime.bigint();
  out.push({name: c.name, want: c.want, got: v.emotion,
            confident: !!v.confident, weak: !!v.weak,
            confidence: v.confidence, intensity: v.intensity,
            second: v.all[1] ? v.all[1].emotion : null, secondary: v.secondary,
            smile: v.smile ? v.smile.kind : null,
            // 单帧 read() 规则层耗时（纳秒→毫秒）：**不含** MediaPipe 取帧与推理
            ms: Number(t1 - t0) / 1e6});
}
console.log(JSON.stringify({preds: out, labels: labels, emotions: R.emotions}));
"""


def run_probe(all_items):
    with tempfile.TemporaryDirectory() as td:
        script = os.path.join(td, "f13_probe.mjs")
        with open(script, "w", encoding="utf-8") as fh:
            fh.write("const ALL = " + json.dumps(all_items, ensure_ascii=False) + ";\n")
            fh.write(PROBE)
        try:
            p = subprocess.run(["node", script, str(ROOT)], capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=180)
        except FileNotFoundError:
            raise SystemExit("F13 node 不可用 ⇒ 报告未生成（不要凭空写数字）")
        except subprocess.TimeoutExpired:
            raise SystemExit("F13 node 探针超时 180s ⇒ 报告未生成")
    if p.returncode != 0 or not (p.stdout or "").strip():
        raise SystemExit("F13 探针失败 rc=%s：%s" % (p.returncode, (p.stderr or "")[:400]))
    try:
        data = json.loads(p.stdout.strip().splitlines()[-1])
    except Exception as e:  # noqa: BLE001
        raise SystemExit("F13 探针输出解析失败：%s" % e)
    if len(data.get("preds", [])) != len(all_items):
        raise SystemExit("F13 探针条数对不上：期望 %d 实得 %d（少下来的样本必须出声，"
                         "不得按少下来的数算准确率）" % (len(all_items), len(data.get("preds", []))))
    return data


def prf(tp, fp, fn):
    prec = tp / (tp + fp) if (tp + fp) else None
    rec = tp / (tp + fn) if (tp + fn) else None
    f1 = (2 * prec * rec / (prec + rec)) if (prec and rec) else 0.0
    return prec, rec, f1


def metrics(rows, emotions, confident_only=False):
    """rows = [{want, got, confident, ...}]。confident_only=True ⇒ 只对「有把握帧」算。

    为什么拆两套口径：本引擎 r161 起**会主动弃权**（confident=false ⇒ 界面说"读数不稳"）。
    只报全帧 P/R ⇒ 弃权帧被算成错（惩罚诚实）；只报置信子集 ⇒ 靠弃权刷高（假装窄也不错）。
    两套一起出，读的人才知道「这个 96.7% 是有把握帧口径，全帧是多少」。
    """
    use = [r for r in rows if (not confident_only or r.get("confident"))]
    classes = [e for e in emotions] + ["__UNKNOWN__"]
    per = OrderedDict((e, {"support": 0, "tp": 0, "fp": 0, "fn": 0, "predicted": 0})
                      for e in classes)
    for r in use:
        w, g = r["want"], r["got"]
        if g not in per:
            g = "__UNKNOWN__"
        per[w]["support"] += 1
        per[g]["predicted"] += 1
        if w == g:
            per[w]["tp"] += 1
        else:
            per[w]["fn"] += 1
            per[g]["fp"] += 1
    for e, d in per.items():
        p, rc, f1 = prf(d["tp"], d["fp"], d["fn"])
        d["precision"] = p
        d["recall"] = rc
        d["f1"] = f1
        d["untested"] = (d["support"] == 0 and d["predicted"] == 0)
    tot_tp = sum(d["tp"] for d in per.values())
    tot_fp = sum(d["fp"] for d in per.values())
    tot_fn = sum(d["fn"] for d in per.values())
    n = len(use)
    micro_p, micro_r, micro_f1 = prf(tot_tp, tot_fp, tot_fn)
    tested = [d for d in per.values() if not d["untested"]]
    macro_f1 = (sum(d["f1"] for d in tested) / len(tested)) if tested else None
    n_conf = sum(1 for r in rows if r.get("confident"))
    return {
        "n": n,
        "n_all": len(rows),
        "abstain_rate": (1 - n_conf / len(rows)) if rows else None,
        "per_class": per,
        "micro": {"precision": micro_p, "recall": micro_r, "f1": micro_f1},
        "macro_f1": macro_f1,
        "accuracy_all_frame": (tot_tp / n) if n else None,
        "classes_tested": len(tested),
        "classes_untested": [e for e, d in per.items() if d["untested"]],
        "confusion": _confusion(use, classes),
    }


def _confusion(use, classes):
    m = OrderedDict()
    for w in classes:
        row = OrderedDict()
        for g in classes:
            row[g] = 0
        m[w] = row
    for r in use:
        w, g = r["want"], r["got"]
        if g not in classes:
            g = "__UNKNOWN__"
        m[w][g] += 1
    return m


def slice_table(rows, axis):
    """按一根轴分层。**未标注单独成组**，不混进已标注组、也不剔除。"""
    buckets = OrderedDict()
    for r in rows:
        key = (r.get("meta") or {}).get(axis)
        key = key if key not in (None, "", "unknown") else None
        k = "__未标注__" if key is None else str(key)
        b = buckets.setdefault(k, {"n": 0, "hit": 0, "hit_confident": 0, "n_confident": 0})
        b["n"] += 1
        if r["want"] == r["got"]:
            b["hit"] += 1
        if r.get("confident"):
            b["n_confident"] += 1
            if r["want"] == r["got"]:
                b["hit_confident"] += 1
    for k, b in buckets.items():
        b["acc_all"] = (b["hit"] / b["n"]) if b["n"] else None
        b["acc_confident"] = (b["hit_confident"] / b["n_confident"]) if b["n_confident"] else None
    return buckets


def _pr(v):
    return "n/a" if v is None else "%.3f" % v


def render(name, m, labels, show_matrix=True):
    print("\n" + "─" * 78)
    print("语料 %s ｜ 样本 %d ｜ 弃权率 %s ｜ 已考类 %d / 未考类 %s"
          % (name, m["n_all"],
             "n/a" if m["abstain_rate"] is None else "%.1f%%" % (100 * m["abstain_rate"]),
             m["classes_tested"], ",".join(m["classes_untested"]) or "无"))
    print("  micro P %s  R %s  F1 %s ｜ macro-F1 %s ｜ 全帧 acc %s"
          % (_pr(m["micro"]["precision"]), _pr(m["micro"]["recall"]), _pr(m["micro"]["f1"]),
             _pr(m["macro_f1"]), _pr(m["accuracy_all_frame"])))
    if len(m) > 1 and show_matrix:
        print("  %-12s %5s %5s %5s %5s %5s %8s %8s %8s" %
              ("类", "支持", "TP", "FP", "FN", "预报", "精确率", "召回率", "F1"))
        for e, d in m["per_class"].items():
            if d["untested"]:
                continue
            tag = "*" if (d["support"] == 0) else " "
            print("  %s%-11s %5d %5d %5d %5d %5d %8s %8s %8s" % (
                tag, labels.get(e, e), d["support"], d["tp"], d["fp"], d["fn"], d["predicted"],
                _pr(d["precision"]), _pr(d["recall"]), _pr(d["f1"])))
        # 一行点名"从未被考过"的类 —— 这是本尺最重要的一行：它防止 n=0 被读成 100%
        un = [labels.get(e, e) for e, d in m["per_class"].items() if d["untested"]]
        if un:
            print("  ⚠️ 以下类在本语料中 support=0 且从未被预测：**召回率未测，不是满分**：%s"
                  % "、".join(un))
    _print_confusion(m, labels)


def _print_confusion(m, labels):
    cm = m["confusion"]
    keys = [k for k in cm if any(cm[k][g] for g in cm) or any(cm[w][k] for w in cm)]
    if len(keys) > 1:
        print("  混淆矩阵（行=真值 列=预报）：")
        print("      " + "".join("%7s" % labels.get(g, g)[:6] for g in keys))
        for w in keys:
            print("  %-5s" % labels.get(w, w)[:5] + "".join("%7d" % cm[w][g] for g in keys))
        worst = []
        for w in keys:
            for g in keys:
                if w != g and cm[w][g]:
                    worst.append((cm[w][g], labels.get(w, w), labels.get(g, g)))
        worst.sort(reverse=True)
        if worst:
            print("  最大互抢对：" + "；".join(
                "%s→%s %d 例" % (a, b, c) for c, a, b in worst[:4]))


def selftest(rows, emotions, labels):
    """反例自证：证明**这些数字会坏**、且不会因为少喂样本就变好。

    不验「本产品好不好」，只验「这把尺本身有没有牙」——没牙的尺子挂在告警链里，
    就是在给后面的假绿灯盖章（呼应 r162 的教训：仪器读数先证自己的解析层）。
    """
    print("\n" + "─" * 78)
    print("反例自证（尺子自身有牙，非产品验收）：")
    bad = []
    ran = 0

    # 腿 1：**全猜一个类** ⇒ macro-F1 必须显著塌陷（若还很高 = P/R 计算里混入了未考类）
    flat = [dict(r, got="joy") for r in rows]
    mf = metrics(flat, emotions)["macro_f1"]
    ran += 1
    ok1 = mf is not None and mf < 0.35
    print("  ① 全猜 joy ⇒ macro-F1=%s（应 <0.35）：%s" % (_pr(mf), "✅" if ok1 else "❌"))
    if not ok1:
        bad.append("全猜一类后 macro-F1 没有塌陷 ⇒ 指标被未考类/分母污染")

    # 腿 2：**完美预测** ⇒ P/R/F1 必须全 1（有一项不到 = 公式写错）
    perfect = [dict(r, got=r["want"]) for r in rows]
    mm = metrics(perfect, emotions)
    ran += 1
    ok2 = all(v is not None and abs(v - 1.0) < 1e-9
              for v in (mm["micro"]["precision"], mm["micro"]["recall"], mm["micro"]["f1"]))
    print("  ② 完美预测 ⇒ micro P/R/F1=%s/%s/%s（应全 1）：%s"
          % (_pr(mm["micro"]["precision"]), _pr(mm["micro"]["recall"]),
             _pr(mm["micro"]["f1"]), "✅" if ok2 else "❌"))
    if not ok2:
        bad.append("完美预测时 micro 指标不为 1 ⇒ 公式层有缺陷")

    # 腿 3：**丢样本** ⇒ 支持数必须跟着变（防「少喂就变好看」的静默作弊）
    half = rows[: max(1, len(rows) // 2)]
    mh, mfull = metrics(half, emotions), metrics(rows, emotions)
    ran += 1
    supports_match = (mh["per_class"] == mfull["per_class"]) or sum(
        d["support"] for d in mh["per_class"].values()) < sum(
        d["support"] for d in mfull["per_class"].values())
    ok3 = bool(supports_match)
    print("  ③ 丢一半样本 ⇒ 总支持数 %d < %d（应严格变小）：%s"
          % (sum(d["support"] for d in mh["per_class"].values()),
             sum(d["support"] for d in mfull["per_class"].values()), "✅" if ok3 else "❌"))
    if not ok3:
        bad.append("丢样本后支持数没变 ⇒ 分母与样本无关，指标不可信")

    # 腿 4：**未考类必须被点名**，不得悄悄按 0 计入 macro-F1
    present = set(r["want"] for r in rows) | set(r["got"] for r in rows)
    unseen = [e for e in emotions if e not in present]
    mf2 = metrics(rows, emotions)
    ran += 1
    ok4 = not set(unseen) - set(mf2["classes_untested"])
    print("  ④ 未考类 %s 必须被标为 untested：%s" % (",".join(unseen) or "无", "✅" if ok4 else "❌"))
    if not ok4:
        bad.append("存在未考类但没被点名 ⇒ n=0 会被读成满分，这是本尺最要命的失效模式")

    print("  " + ("F13-SELFTEST-PASS 反例腿 %d/%d 通过" % (ran - len(bad), ran) if not bad
                  else "F13-SELFTEST-FAIL " + "；".join(bad)))
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="", help="机器件落盘路径（默认 _test/face-prf-report-<stamp>.json）")
    ap.add_argument("--no-selftest", action="store_true")
    args = ap.parse_args()

    corpora = build_corpora()
    flatIndex = []
    for cname, items in corpora.items():
        for it in items:
            it = dict(it)
            it["corpus"] = cname
            flatIndex.append(it)
    if not flatIndex:
        raise SystemExit("F13 三个语料全空 ⇒ 不许出报告（空表比没有表更危险）")

    print("F13 · 表情识别逐类 P/R/F1 报告（%s）" % datetime.now().strftime("%Y-%m-%d %H:%M"))
    print("样本合计 %d ｜ REAL %d ｜ SYNTH %d ｜ LOWINT %d"
          % (len(flatIndex), len(corpora["REAL"]), len(corpora["SYNTH"]), len(corpora["LOWINT"])))

    data = run_probe(flatIndex)
    labels = data["labels"]
    emotions = data["emotions"]
    preds = data["preds"]
    for i, p in enumerate(preds):
        flatIndex[i].update({"got": p["got"], "confident": p["confident"],
                             "weak": p["weak"], "confidence": p["confidence"],
                             "intensity": p["intensity"], "smile": p["smile"],
                             "second": p["second"], "ms": p["ms"]})

    print("\n⚠️ 口径声明：" + DISCLAIMER)

    out = {"generated": datetime.now().isoformat(timespec="seconds"),
           "disclaimer": DISCLAIMER,
           "counts": {k: len(v) for k, v in corpora.items()},
           "corpora": OrderedDict(), "slices": OrderedDict(), "latency_ms": {}}

    for cname in corpora:
        rows = [r for r in flatIndex if r["corpus"] == cname]
        full = metrics(rows, emotions)
        conf = metrics(rows, emotions, confident_only=True)
        render(cname, full, labels)
        print("  【有把握帧口径】micro P %s  R %s  F1 %s ｜macro-F1 %s ｜ n=%d"
              % (_pr(conf["micro"]["precision"]), _pr(conf["micro"]["recall"]),
                 _pr(conf["micro"]["f1"]), _pr(conf["macro_f1"]), conf["n"]))
        out["corpora"][cname] = {"all_frame": full, "confident_only": conf}

    print("\n" + "─" * 78)
    print("分层切片（需求口径：光照 / 角度 / 年龄 / 性别）：")
    for axis, desc in SLICE_AXES.items():
        rows = [r for r in flatIndex if axis in (r.get("meta") or {}) or axis == "level"]
        if not rows:
            out["slices"][axis] = {"measurable": False, "reason": "无任何样本带该轴标注"}
            print("  %-10s %s ⇒ **不可测**（无一竟样本带标注，故不出数字）" % (axis, desc))
            continue
        b = slice_table(rows, axis)
        unlabeled_n = b.get("__未标注__", {}).get("n", 0)
        out["slices"][axis] = {"measurable": True, "buckets": b, "unlabeled": unlabeled_n}
        print("  %-10s %s ｜未标注 %d 条" % (axis, desc, unlabeled_n))
        for k, v in b.items():
            print("      %-12s n=%-4d 全帧acc %-8s 有把握acc %-8s"
                  % (k, v["n"], _pr(v["acc_all"]),
                     _pr(v["acc_confident"]) if v["n_confident"] else "无 confident 帧"))

    ms = sorted(r["ms"] for r in flatIndex if r.get("ms") is not None)
    if ms:
        n = len(ms)
        p50 = ms[int(0.50 * (n - 1))]
        p95 = ms[int(0.95 * (n - 1))]
        out["latency_ms"] = {"n": n, "p50": p50, "p95": p95, "max": ms[-1],
                             "note": "仅 read() 规则层计算耗时，**不含** MediaPipe 拉流与推理"}
        print("\n单帧规则层 compute 延迟：p50 %.4f ms ｜ p95 %.4f ms ｜ max %.4f ms（n=%d）"
              % (p50, p95, ms[-1], n))
        print("  ⚠️ 这是规则层耗时，**不是**单帧端到端延迟：还要叠加摄像头取帧 + MediaPipe 推理"
              "（那一段只有真人开着摄像头才测得出来，详见报告 §延迟）。")

    bad = []
    if not args.no_selftest:
        bad = selftest(flatIndex, emotions, labels)

    dst = Path(args.out) if args.out else (
        TEST_DIR / ("face-prf-report-%s.json" % datetime.now().strftime("%Y%m%d-%H%M%S")))
    dst.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n机器件已落盘：" + str(dst.relative_to(ROOT)))

    if bad:
        print("\nF13-FAIL 尺子自身反例未通过 ⇒ 上述数字不可引用")
        return 1
    print("\nF13-PASS 报告已生成。注意：本尺**不设 90% 通过线** —— "
          "样本不足以支撑该断言时挂门 = 让未考类自动变绿。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
