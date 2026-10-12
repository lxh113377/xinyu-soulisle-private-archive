# -*- coding: utf-8 -*-
"""双核心能力基线复算器（r111 立；用户 2026-10-11 立规的机器面）

立规原文（用户）：「将『表情识别』和『语意理解』确立为项目多轮迭代优化的核心优先级，并在每一轮
优化中明确设定相关目标、评估指标和验证标准 …… 作为反复优化的第一要务进行跟踪与落实。」
⇒ 本脚本把"第一要务"变成**每轮可复算的一条命令**：复算两张能力的基线读数，与
`_test/core-capability-baseline.json` 对账，任何回退即判红（棘轮：只降不升）。

复算面（全部离线、零服务依赖；口径与产物命令一一对应）：
  N1 语意理解 · 情绪评测集   `node _test/emotion_eval.js`            → 条数 / 准确率 / 危机召回
  N2 表情识别 · 引擎单测     `node --test _test/js/face-engine.unit.test.mjs` → tests/pass/fail
  F1 表情识别 · vendor 完整性 `python _test/vendor_freshness_check.py` 的离线腿（V1–V3）→ rc
  N3 双端一致 · 可选腿        `python _test/engine_consistency_check.py`（需 8123 有服务才跑，
                             否则记 SKIP 且**不计入判定**，绝不把"没跑"写成绿）

用法：
  python _test/core_capability_baseline_check.py            # 复算 + 与基线对账（棘轮）
  python _test/core_capability_baseline_check.py --update   # 把更优读数写回基线（只升不降）
  python _test/core_capability_baseline_check.py --selftest # 反例自证：每条规则应红的红、应绿的绿
  python _test/core_capability_baseline_check.py --json     # 机器可读输出（供聚合器）

退出码：0=全过且无回退 1=回退/判红 2=环境未验（node 不可用等 ⇒ 不许判绿）

N1 的回退定义（r127 改判，一手 2×2 实测否证旧口径）：
  旧口径「准确率百分比不得下降」把两个不同的量当同一个比 —— 评测集 85→105 条时，
  99%/105 与 100%/85 不是同一个分母，「题目变难」会被读成「能力回退」，于是每轮扩集必假红，
  而假红的唯一出路就是逼人改数据凑绿。⇒ 现口径 = **基线在册题（pass_cases 指纹集）零回归**；
  分母相等时才允许比百分比；分母变更只点名不判红，新题读数记为「新观察」不进棘轮。
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_FILE = ROOT / "_test" / "core-capability-baseline.json"


def run(cmd, timeout=240):
    """跑子进程：返回 (rc, 合并输出)。rc=124 专用于超时（与电池口径一致）。"""
    try:
        p = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except FileNotFoundError:
        return 127, "COMMAND-NOT-FOUND: %s" % cmd[0]
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT after %ss" % timeout


def parse_nlu(out):
    """从 emotion_eval.js 的 stdout 里取 JSON（它只印一个 JSON 对象）。"""
    i = out.find("{")
    if i < 0:
        return None
    try:
        d = json.loads(out[i:])
    except Exception:
        return None
    cr = str(d.get("crisis_recall", ""))
    m = re.match(r"(\d+)\s*/\s*(\d+)", cr)
    d["crisis_hit"], d["crisis_n"] = (int(m.group(1)), int(m.group(2))) if m else (None, None)
    d["acc_num"] = float(str(d.get("accuracy", "0")).rstrip("%") or 0)
    ms = d.get("misses")
    d["miss_list_ok"] = isinstance(ms, list)
    d["miss_fp"] = sorted({fp(x.get("text", "")) for x in ms}) if d["miss_list_ok"] else []
    return d


def fp(text):
    """题面指纹：与评测器回显的 misses[].text 同源（去首尾空白后取 sha1 前 12 位）。"""
    return hashlib.sha1(str(text).strip().encode("utf-8")).hexdigest()[:12]


def dataset_case_fps(path=None):
    """评测集全部题面指纹 = 分母的可复算来源（禁由聚合数字代填）。"""
    p = Path(path) if path else ROOT / "_test" / "emotion-eval-dataset.json"
    ds = json.loads(p.read_text(encoding="utf-8"))
    for v in ([ds] if isinstance(ds, list) else list(ds.values())):
        if isinstance(v, list) and v and isinstance(v[0], dict) and "text" in v[0]:
            return [fp(c["text"]) for c in v]
    raise ValueError("评测集里找不到带 text 的用例数组（结构变更 ⇒ 不得当成零题）")


def parse_node_test(out):
    """解析 `node --test` 的汇总行（ℹ tests/pass/fail N）。"""
    g = lambda k: (int(re.search(r"ℹ %s (\d+)" % k, out).group(1))
                   if re.search(r"ℹ %s (\d+)" % k, out) else None)
    return {"tests": g("tests"), "pass": g("pass"), "fail": g("fail")}


def measure():
    """复算四个面，返回 (读数 dict, 未验列表)。未验不折算成 0，单独列出。"""
    data, unverified = {}, []

    rc, out = run(["node", "_test/emotion_eval.js"])
    nlu = parse_nlu(out) if rc == 0 else None
    if nlu is None:
        unverified.append("N1 语意理解（node 不可用或评测脚本异常 rc=%s）" % rc)
    else:
        data["nlu"] = {"total": nlu["total"], "accuracy": nlu["accuracy"],
                       "acc_num": nlu["acc_num"], "crisis_hit": nlu["crisis_hit"],
                       "crisis_n": nlu["crisis_n"], "per_class": nlu.get("per_class", {}),
                       "miss_list_ok": nlu["miss_list_ok"], "miss_fp": nlu["miss_fp"]}
        if not nlu["miss_list_ok"]:
            unverified.append("N1 同分母回归对账（评测器未回 misses 清单 ⇒ 无法证明基线题仍过）")

    rc, out = run(["node", "--test", "_test/js/face-engine.unit.test.mjs"])
    nt = parse_node_test(out)
    if nt["tests"] is None:
        unverified.append("N2 表情识别单测（node --test 无汇总行 rc=%s）" % rc)
    else:
        data["face_unit"] = nt

    rc, out = run([sys.executable, "_test/vendor_freshness_check.py"])
    data["vendor"] = {"rc": rc}
    if rc not in (0, 1):
        unverified.append("F1 vendor 完整性（脚本未跑到判定 rc=%s）" % rc)

    # N3 可选腿：有服务才跑；没服务记 SKIP（不计入判定，也不记绿）
    rc, _ = run([sys.executable, "_test/engine_consistency_check.py"], timeout=120)
    data["dual_engine"] = {"rc": rc, "state": "ran" if rc in (0, 1) else "skip"}

    return data, unverified


def ratchet(cur, base):
    """棘轮比对：返回 (回退项, 说明项, 未验项)。规则只降不升，新增面不计降。

    N1 的「回退」= 基线在册题里有任一题现在不过（同分母子集对账）。分母不等时**禁止**拿
    百分比直接横比，只点名；分母相等时旧的准确率规则照旧生效。
    """
    bad, notes, unver = [], [], []
    b, c = base.get("nlu") or {}, cur.get("nlu") or {}
    if b and c:
        bfp, cm = set(b.get("pass_cases") or []), set(c.get("miss_fp") or [])
        if c.get("miss_list_ok") is not True:
            unver.append("N1 同分母对账（评测器未回 misses 清单 ⇒ 空 miss 集不得读成零回归）")
        elif not bfp:
            unver.append("N1 同分母对账（基线无 pass_cases ⇒ 由 --update 补齐后才谈得上零回归）")
        elif len(bfp) != int(b.get("denominator_at_baseline") or -1):
            bad.append("N1 基线自相矛盾：pass_cases %d 道 ⇄ denominator_at_baseline %s"
                       % (len(bfp), b.get("denominator_at_baseline")))
        else:
            reg = sorted(bfp & cm)
            notes.append("N1 基线在册题 %d 道中回归 %d 道" % (len(bfp), len(reg)))
            if reg:
                bad.append("N1 基线在册题回归 %d/%d 道（指纹 %s）"
                           % (len(reg), len(bfp), ",".join(reg[:3])))
            if c["total"] == b["total"]:
                if c["acc_num"] < b["acc_num"]:
                    bad.append("N1 准确率回退 %s → %s（同分母 %d 条）"
                               % (b["accuracy"], c["accuracy"], c["total"]))
            else:
                notes.append("分母变更 %d→%d ⇒ 准确率不横比；新增题 miss %d 条只作新观察、不进棘轮"
                             % (b["total"], c["total"], len(cm - bfp)))
        if c["crisis_hit"] is not None and b["crisis_hit"] is not None:
            if (c["crisis_hit"], -c["crisis_n"]) < (b["crisis_hit"], -b["crisis_n"]):
                bad.append("N1 危机召回回退 %d/%d → %d/%d" % (b["crisis_hit"], b["crisis_n"],
                                                          c["crisis_hit"], c["crisis_n"]))
        if c["total"] < b["total"]:
            bad.append("N1 评测集缩水 %d → %d 条（数据集只增不减）" % (b["total"], c["total"]))
    b, c = base.get("face_unit") or {}, cur.get("face_unit") or {}
    if b and c:
        if (c["fail"] or 0) > 0:
            bad.append("N2 表情引擎单测 fail=%d" % c["fail"])
        if (c["pass"] or 0) < (b["pass"] or 0):
            bad.append("N2 通过数回退 %s → %s" % (b["pass"], c["pass"]))
    if (base.get("vendor") or {}).get("rc") == 0 and (cur.get("vendor") or {}).get("rc") == 1:
        bad.append("F1 vendor 完整性由 PASS 变 FAIL")
    return bad, notes, unver


def verdict_tail(cur, base):
    """收口行携带数值：电池只留末条含判据词的行，数值留在别处等于没量到。"""
    b, c = base.get("nlu") or {}, cur.get("nlu") or {}
    f = cur.get("face_unit") or {}
    bfp, cm = set(b.get("pass_cases") or []), set(c.get("miss_fp") or [])
    sub = "基线无题集" if not bfp else "回归 %d/%d" % (len(bfp & cm), len(bfp))
    return ("N1 %s→%s 条｜%s｜新题 miss %d｜N2 %s/%s fail=%s｜F1 rc=%s" % (
        b.get("total"), c.get("total"), sub, len(cm - bfp),
        f.get("pass"), f.get("tests"), f.get("fail"), (cur.get("vendor") or {}).get("rc")))


def fmt(cur, base):
    n, bn = cur.get("nlu") or {}, base.get("nlu") or {}
    f, bf = cur.get("face_unit") or {}, base.get("face_unit") or {}
    lines = [
        "N1 语意理解 · 评测集  %s 条 / %s / 危机 %s-%s   基线 %s / %s / %s-%s" % (
            n.get("total"), n.get("accuracy"), n.get("crisis_hit"), n.get("crisis_n"),
            bn.get("total"), bn.get("accuracy"), bn.get("crisis_hit"), bn.get("crisis_n")),
        "N2 表情识别 · 引擎单测 %s/%s pass, fail=%s        基线 %s/%s" % (
            f.get("pass"), f.get("tests"), f.get("fail"), bf.get("pass"), bf.get("tests")),
        "F1 表情识别 · vendor   rc=%s（V1 完整性离线腿）     基线 rc=%s" % (
            (cur.get("vendor") or {}).get("rc"), (base.get("vendor") or {}).get("rc")),
        "N3 双端一致 · 可选腿   %s" % (cur.get("dual_engine") or {}).get("state"),
    ]
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--update", action="store_true", help="把更优读数写回基线（只升不降）")
    ap.add_argument("--force", action="store_true", help="允许 --update 覆盖为更低值（需说明理由）")
    ap.add_argument("--selftest", action="store_true", help="反例自证：每条规则应红的红、应绿的绿")
    ap.add_argument("--json", action="store_true", help="机器可读输出")
    a = ap.parse_args()

    base = json.loads(BASE_FILE.read_text(encoding="utf-8"))
    cur, unverified = measure()

    if a.selftest:
        return selftest(base, cur)

    bad, notes, un2 = ratchet(cur, base)
    unverified = unverified + un2
    if not a.json:
        for ln in fmt(cur, base):
            print("  " + ln)
        for n in notes:
            print("  NOTE  " + n)
        for u in unverified:
            print("  UNVERIFIED  " + u)

    if a.update and cur.get("nlu") and cur.get("face_unit"):
        if bad and not a.force:
            print("CORE-CAP-UPDATE-REFUSED：存在回退项，棘轮不允许写低（%s）" % "; ".join(bad[:2]))
            return 1
        if not cur["nlu"].get("miss_list_ok"):
            print("CORE-CAP-UPDATE-REFUSED：评测器未回 misses 清单 ⇒ 写不出可信的 pass_cases，不写基线")
            return 2
        try:
            allfp = dataset_case_fps()
        except Exception as e:
            print("CORE-CAP-UPDATE-REFUSED：评测集题面取数失败（%s）⇒ 不写基线" % e)
            return 2
        nlu = dict(cur["nlu"])
        nlu["pass_cases"] = sorted(set(allfp) - set(nlu.get("miss_fp") or []))
        nlu["denominator_at_baseline"] = len(allfp)
        base.update({"nlu": nlu, "face_unit": cur["face_unit"],
                     "vendor": cur["vendor"],
                     "updated": datetime.date.today().isoformat()})
        BASE_FILE.write_text(json.dumps(base, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("CORE-CAP-BASELINE-UPDATED -> %s（pass_cases %d 道 / 全集 %d 道）"
              % (BASE_FILE.name, len(nlu["pass_cases"]), len(allfp)))

    tail = verdict_tail(cur, base)
    if a.json:
        print(json.dumps({"cur": cur, "bad": bad, "notes": notes,
                          "unverified": unverified}, ensure_ascii=False))
    if bad:
        print("CORE-CAP-BASELINE-FAIL 回退 %d 项：%s ‖ %s" % (len(bad), "; ".join(bad[:3]), tail))
        return 1
    if unverified:
        print("CORE-CAP-BASELINE-UNVERIFIED %d 面未验（不得当绿）：%s ‖ %s"
              % (len(unverified), "; ".join(unverified[:2]), tail))
        return 2
    print("CORE-CAP-BASELINE-PASS 双能力无回退（基线 %s）‖ %s" % (base.get("updated"), tail))
    return 0


def selftest(base, cur):
    """反例自证：每条规则各有应红/应绿两腿，红因点名到题。

    全部用合成输入（不碰真基线文件、不跑子进程），期望形状由 ratchet 返回值现取。
    """
    A, B, C, NEW = fp("基线题A"), fp("基线题B"), fp("基线题C"), fp("扩容新增题")
    CASES = [A, B, C]

    def nlu(total, acc, miss, cases=CASES, crisis=(6, 6), ok_list=True):
        d = {"total": total, "accuracy": "%s%%" % acc, "acc_num": float(acc),
             "crisis_hit": crisis[0], "crisis_n": crisis[1], "per_class": {},
             "miss_list_ok": ok_list, "miss_fp": sorted(miss), "pass_cases": sorted(cases)}
        return d

    def b_of(n, den=None):
        """基线整包（与 ratchet 的入参形状一致；只给 nlu 子字典会让判据整段不进 ⇒ 假绿腿）"""
        d = json.loads(json.dumps(n))
        d["denominator_at_baseline"] = len(d["pass_cases"]) if den is None else den
        return {"nlu": d, "face_unit": {"tests": 31, "pass": 31, "fail": 0},
                "vendor": {"rc": 0}}

    def pack(n, fu=None, ven=None):
        return {"nlu": n, "face_unit": fu or {"tests": 31, "pass": 31, "fail": 0},
                "vendor": ven or {"rc": 0}}

    OK_BASE = b_of(nlu(3, 100.0, []))
    legs = [
        ("同分母+准确率降 ⇒ 红（同分母下必同时是基线题回归）", pack(nlu(3, 66.7, [C])),
         OK_BASE, ["N1 准确率回退", "N1 基线在册题回归"], []),
        ("同分母+全过 ⇒ 绿（对照腿）", pack(nlu(3, 100.0, [])), OK_BASE, [], []),
        ("分母增长+仅新题 miss ⇒ 绿（r127 假红治点）", pack(nlu(4, 75.0, [NEW])),
         OK_BASE, [], ["note:分母变更"]),
        ("分母增长+基线题回归 ⇒ 红并点名", pack(nlu(4, 75.0, [NEW, C])), OK_BASE,
         ["N1 基线在册题回归"], []),
        ("基线无 pass_cases ⇒ 未验不判绿", pack(nlu(3, 66.7, [C], cases=[])),
         b_of(nlu(3, 100.0, [], cases=[])), [], ["unver:同分母对账"]),
        ("评测器不回 misses 清单 ⇒ 未验（空集不得读成零回归）",
         pack(nlu(3, 100.0, [], ok_list=False)), OK_BASE, [], ["unver:同分母对账"]),
        ("分母缩水 ⇒ 红", pack(nlu(2, 100.0, [], cases=[A, B])),
         b_of(nlu(3, 100.0, [])), ["N1 评测集缩水"], []),
        ("危机召回降 ⇒ 红", pack(nlu(3, 100.0, [], crisis=(5, 6))), OK_BASE,
         ["N1 危机召回回退"], []),
        ("N2 fail ⇒ 红", pack(nlu(3, 100.0, []), fu={"tests": 31, "pass": 30, "fail": 1}),
         OK_BASE, ["N2 表情引擎单测", "N2 通过数回退"], []),
        ("F1 vendor 由 0 变 1 ⇒ 红", pack(nlu(3, 100.0, []), ven={"rc": 1}), OK_BASE,
         ["F1 vendor"], []),
        ("基线自相矛盾（题集数⇄登记分母不等） ⇒ 红",
         pack(nlu(3, 100.0, [])), b_of(nlu(3, 100.0, []), den=99), ["基线自相矛盾"], []),
        ("真面原样对账 ⇒ 零回退", cur, base, [], []),
    ]

    ok, detail = True, []
    for name, c, b, want_bad, want_see in legs:
        bad, notes, unver = ratchet(c, b)
        chan = {"note": " | ".join(notes), "unver": " | ".join(unver)}
        miss_bad = [k for k in want_bad if k not in " | ".join(bad)]
        miss_see = [w for w in want_see
                    if w.split(":", 1)[1] not in chan.get(w.split(":", 1)[0], "\x00")]
        stray = [x for x in bad if want_bad and not any(w in x for w in want_bad)]
        wrong = bool(miss_bad or miss_see or stray) or (not want_bad and bool(bad))
        if wrong:
            ok = False
        detail.append("%s%s（红%d/未验%d/说明%d）" % ("✗" if wrong else "✓", name,
                                                     len(bad), len(unver), len(notes)))

    n_ok = sum(1 for d in detail if d.startswith("✓"))
    for d in detail:
        print("  " + d)
    print("CORE-CAP-SELFTEST-%s %d/%d 腿（应红的红、应绿的绿，红因点名到题）"
          % ("PASS" if ok else "FAIL", n_ok, len(legs)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
