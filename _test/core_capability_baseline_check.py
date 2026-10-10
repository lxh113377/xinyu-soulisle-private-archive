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
  python _test/core_capability_baseline_check.py --selftest # 反例自证：抬高基线必须逐项判红
  python _test/core_capability_baseline_check.py --json     # 机器可读输出（供聚合器）

退出码：0=全过且无回退 1=回退/判红 2=环境未验（node 不可用等 ⇒ 不许判绿）
"""
import argparse
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
    return d


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
                       "crisis_n": nlu["crisis_n"], "per_class": nlu.get("per_class", {})}

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
    """棘轮比对：返回回退项列表（空 = 无回退）。规则只降不升，新增面不计降。"""
    bad = []
    b, c = base.get("nlu") or {}, cur.get("nlu") or {}
    if b and c:
        if c["acc_num"] < b["acc_num"]:
            bad.append("N1 准确率回退 %s → %s（基线 %s）" % (b["accuracy"], c["accuracy"], b["accuracy"]))
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
    return bad


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
    ap.add_argument("--selftest", action="store_true", help="反例自证：抬高基线必须逐项判红")
    ap.add_argument("--json", action="store_true", help="机器可读输出")
    a = ap.parse_args()

    base = json.loads(BASE_FILE.read_text(encoding="utf-8"))
    cur, unverified = measure()

    if a.selftest:
        return selftest(base, cur)

    bad = ratchet(cur, base)
    if not a.json:
        for ln in fmt(cur, base):
            print("  " + ln)
        for u in unverified:
            print("  UNVERIFIED  " + u)

    if a.update and cur.get("nlu") and cur.get("face_unit"):
        if bad and not a.force:
            print("CORE-CAP-UPDATE-REFUSED：存在回退项，棘轮不允许写低（%s）" % "; ".join(bad[:2]))
            return 1
        base.update({"nlu": cur["nlu"], "face_unit": cur["face_unit"],
                     "vendor": cur["vendor"],
                     "updated": datetime.date.today().isoformat()})
        BASE_FILE.write_text(json.dumps(base, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("CORE-CAP-BASELINE-UPDATED -> %s" % BASE_FILE.name)

    if a.json:
        print(json.dumps({"cur": cur, "bad": bad, "unverified": unverified}, ensure_ascii=False))
    if bad:
        print("CORE-CAP-BASELINE-FAIL 回退 %d 项：%s" % (len(bad), "; ".join(bad[:3])))
        return 1
    if unverified:
        print("CORE-CAP-BASELINE-UNVERIFIED %d 面未验（不得当绿）：%s" % (len(unverified), "; ".join(unverified[:2])))
        return 2
    print("CORE-CAP-BASELINE-PASS 双能力无回退（基线 %s）" % base.get("updated"))
    return 0


def selftest(base, cur):
    """反例自证：把基线抬到不可能达到的值，ratchet 必须逐项点名判红。"""
    hot = json.loads(json.dumps(base))
    hot["nlu"] = dict(hot.get("nlu") or {}, acc_num=101.0, crisis_hit=99, crisis_n=99, total=99999)
    hot["face_unit"] = dict(hot.get("face_unit") or {}, **{"pass": 9999})   # pass 是关键字，只能字典展开
    hot["vendor"] = {"rc": 0}
    bad = ratchet(cur, hot)
    need = ["N1 准确率回退", "N1 危机召回回退", "N1 评测集缩水", "N2 通过数回退"]
    hit = [k for k in need if any(k in x for x in bad)]
    real = ratchet(cur, base)
    ok = (hit == need) and (not real)
    print("SELFTEST %s：抬高基线抓到 %d/%d 条（%s）；原样基线回退项=%d"
          % ("PASS" if ok else "FAIL", len(hit), len(need), ",".join(hit), len(real)))
    print("CORE-CAP-SELFTEST-%s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
