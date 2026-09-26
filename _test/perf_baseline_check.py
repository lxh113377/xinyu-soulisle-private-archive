# -*- coding: utf-8 -*-
"""性能基线判据（r40）：把"性能表现"这一维从连续几轮的「未实测」变成有数、有预算、有回归棘轮的一格。

口径边界（先看这段再读数字，否则会被误用）：
  · 这是**自身基线 + 回归棘轮**，不是跨项目对比 —— 16 个参照仓没有一个公开可比的性能数字
    （r35–r39 台账实测），所以任何"我们比 X 快 N%"的写法都不允许由本判据产生。
  · 只打**本地、无外网**的三条面：静态页 / `/api/health` / `/api/emotion` 的**危机短路路径**
    （危机词命中即不调 LLM，实测响应里 `llm` 为 null ⇒ 数字不受上游网络与大模型波动影响）。
    一旦哪天它开始调 LLM，本判据立刻判红（`llm` 非 null），而不是把一个网络延迟记成"性能退化"。
  · 阈值一律按**首轮实测值的数倍**放宽：判据要抓的是"数量级退化"（线程池打满、直读路径变成
    落库、静态资源被改成同步阻塞），不是抖动。先量变异、再接进阻断链（无变异数据不钉阈值）。

用法：python _test/perf_baseline_check.py [BASE] [--reps N] [--json out] [--selftest]
退出码：0=在预算内 1=超预算（性能回归）2=服务不可达/样本不足（未验，不得当通过）
"""
import argparse
import json
import statistics
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# 取冻结评测集里的真危机句（r40 实测教训：我自己造的"不想伤害自己"是否定式，没命中危机词表，
# 于是打到 LLM 上、量出 530ms 的"性能"——那不是性能，是网络。样本必须来自已登记的数据集。）
CRISIS_TEXT = "感觉活着好累，不想活了"            # 冻结集内危机样本 ⇒ 词典短路，不调 LLM
BUDGETS = {
    # 阈值 = 本机实测 p95 放宽到"数量级退化才红"：本地 warm JVM 实测 static/health/vendor
    # p95 16~27ms、危机短路 emotion p95 见 --json 落盘；这里给 ~20 倍余量（无余量的地板＝冻结增长，
    # 也防 CI 冷跑与共享 runner 抖动误报）。抓的是"直读变成落库 / 线程池打满 / 静态被改同步阻塞"。
    "static_index": {"p95_ms": 400.0, "note": "首页直读 src/（实测 p95 16~27ms，余量 ~15-25x）"},
    "vendor_js": {"p95_ms": 400.0, "note": "vendor/three.min.js 静态大文件"},
    "health": {"p95_ms": 400.0, "note": "/api/health 文件系统探针"},
    "emotion_crisis": {"p95_ms": 400.0, "note": "/api/emotion 危机短路（必须不调 LLM）"},
}
MIN_RPS = 50.0     # 实测 8×6=48 并发下 ~2200 rps ⇒ 地板只防"塌了"，不防抖动
CONC = {"threads": 8, "per_thread": 6}


def timed(fn):
    t0 = time.perf_counter()
    r = fn()
    return (time.perf_counter() - t0) * 1000.0, r


def pct(xs, p):
    """最近秩法（不插值）：小样本下插值会给出"介于两个真实观测之间"的假数。"""
    s = sorted(xs)
    if not s:
        return None
    k = max(0, min(len(s) - 1, int(round(p / 100.0 * (len(s) - 1)))))
    return s[k]


def get(url, body=None):
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": "application/json",
                                          "User-Agent": "xinyu-perf"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status, r.read()


def measure(base, reps):
    targets = [
        ("static_index", base + "/", None),
        ("vendor_js", base + "/vendor/three.min.js", None),
        ("health", base + "/api/health", None),
        ("emotion_crisis", base + "/api/emotion",
         json.dumps({"text": CRISIS_TEXT}, ensure_ascii=False).encode("utf-8")),
    ]
    out, fatal = {}, []
    for name, url, body in targets:
        lat, last = [], None
        for _ in range(reps):
            try:
                ms, resp = timed(lambda u=url, b=body: get(u, b))
            except (urllib.error.HTTPError, urllib.error.URLError, OSError) as e:
                fatal.append("%s: %s" % (name, getattr(e, "reason", e)))
                break
            lat.append(ms)
            last = resp[1] if isinstance(resp, tuple) else resp
        else:
            out[name] = {"n": len(lat), "min_ms": round(min(lat), 1),
                         "p50_ms": round(pct(lat, 50), 1), "p95_ms": round(pct(lat, 95), 1),
                         "max_ms": round(max(lat), 1)}
        if name == "emotion_crisis":
            # 口径守卫必须 fail-closed：读不到 / 解析失败都算"口径未证"，不许静默当通过
            try:
                j = json.loads((last or b"").decode("utf-8", "replace"))
                out[name]["llm_used"] = bool(j.get("llm"))
                out[name]["resp_keys"] = sorted(j.keys())
            except Exception as e:
                out[name]["llm_used"] = None
                out[name]["guard"] = "UNVERIFIED:%s" % e
    # 吞吐：只测 health（最轻，测的是服务端并发而非上游）
    if not fatal:
        def hit():
            return timed(lambda: get(base + "/api/health"))[0]
        t0 = time.perf_counter()
        with ThreadPoolExecutor(max_workers=CONC["threads"]) as ex:
            lats = list(ex.map(lambda _: hit(), range(CONC["threads"] * CONC["per_thread"])))
        wall = time.perf_counter() - t0
        out["throughput_health"] = {"rps": round(len(lats) / wall, 1),
                                    "p95_ms": round(pct(lats, 95), 1), "n": len(lats)}
    return out, fatal


def judge(m):
    bad = []
    for name, b in BUDGETS.items():
        got = m.get(name)
        if not got:
            bad.append("%s 无样本（取数失败）⇒ 不判绿" % name)
            continue
        if got["p95_ms"] > b["p95_ms"]:
            bad.append("%s p95=%.0fms 超预算 %.0fms（%s）" % (name, got["p95_ms"], b["p95_ms"], b["note"]))
    tp = m.get("throughput_health", {})
    if tp.get("rps") is not None and tp["rps"] < MIN_RPS:
        bad.append("并发吞吐 %.0f rps < 地板 %.0f ⇒ 服务端塌方级退化" % (tp["rps"], MIN_RPS))
    ec = m.get("emotion_crisis", {})
    if ec.get("llm_used") is True:
        bad.append("危机路径走了 LLM ⇒ 本判据口径失效（数字不再可比），先修短路再说性能")
    if ec.get("llm_used") is None:
        bad.append("危机路径的 llm 字段取不到（%s）⇒ 口径未证，不判绿" % ec.get("guard"))
    return bad


def selftest():
    """自证判据自身不恒绿：慢样本必须超预算、空样本必须算未验、百分位不得插值造假数。"""
    bad = []
    if pct([10.0, 20.0, 30.0], 50) != 20.0:
        bad.append("①p50 计算错（最近秩应取中位观测值）")
    if pct([1.0, 2.0], 95) != 2.0:
        bad.append("②小样本 p95 插值 ⇒ 会造出一个从没发生过的延迟数")
    if pct([], 95) is not None:
        bad.append("③空样本返回了数 ⇒ 会把『没取到』读成性能达标")
    slow = {"static_index": {"p95_ms": 9e9}, "vendor_js": {"p95_ms": 9e9},
            "health": {"p95_ms": 9e9}, "emotion_crisis": {"p95_ms": 9e9, "llm_used": False}}
    if not judge(slow):
        bad.append("④恒慢样本被判通过 ⇒ 判据恒绿（真回归永远漏报）")
    empty = {"static_index": {"p95_ms": 1.0}, "vendor_js": {"p95_ms": 1.0}, "health": {"p95_ms": 1.0}}
    if not judge(empty):
        bad.append("⑤缺一个目标样本仍判通过 ⇒ 覆盖面会静默缩水")
    llm_on = {k: {"p95_ms": 1.0} for k in BUDGETS}
    llm_on["emotion_crisis"] = {"p95_ms": 1.0, "llm_used": True}
    if not judge(llm_on):
        bad.append("⑥危机路径走了 LLM 却没被抓到 ⇒ 口径被悄悄换掉")
    print("SELFTEST-%s" % ("PASS: 百分位/空样本/恒慢/缺面/口径漂移 六向正确" if not bad
                           else "FAIL: " + "; ".join(bad)))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base", nargs="?", default="http://127.0.0.1:8123")
    ap.add_argument("--reps", type=int, default=25)
    ap.add_argument("--json", default="")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    try:
        get(a.base + "/api/health")
    except Exception as e:
        print("PERF-ENV: 被测服务不可达 %s（%s）⇒ 记为未验证，不判绿" % (a.base, type(e).__name__))
        return 2
    m, fatal = measure(a.base, a.reps)
    if fatal:
        print("PERF-ENV: 取数失败 %s ⇒ 未验证" % "; ".join(fatal))
        return 2
    for name in ("static_index", "vendor_js", "health", "emotion_crisis", "throughput_health"):
        d = m[name]
        extra = ("｜llm_used=%s keys=%s" % (d.get("llm_used"), d.get("resp_keys"))) if "llm_used" in d else (
            ("｜rps=%s" % d.get("rps")) if "rps" in d else "")
        print("  %-16s n=%-3s min=%-7s p50=%-7s p95=%-7s max=%-7s%s"
              % (name, d.get("n"), d.get("min_ms", "-"), d.get("p50_ms", "-"),
                 d.get("p95_ms", "-"), d.get("max_ms", "-"), extra))
    bad = judge(m)
    if a.json:
        Path(a.json).write_bytes(json.dumps({"base": a.base, "reps": a.reps, "samples": m,
                                             "budgets": {k: v["p95_ms"] for k, v in BUDGETS.items()},
                                             "breach": bad}, ensure_ascii=False, indent=1).encode("utf-8"))
    if bad:
        for x in bad:
            print("  FAIL", x)
        print("PERF-BASELINE-FAIL: %d 项超预算/口径失效" % len(bad))
        return 1
    # 实测值必须挤进这一行：电池只保留最后一条含判据词的 stdout，逐项明细行在 CI 里会被丢掉
    # ⇒ 判据是棘轮，看不见被检环境的数字就无从判断"该不该重定基线"（07 在册 P2）。
    peak = max(d["p95_ms"] for k, d in m.items() if k in BUDGETS)
    tightest = min(BUDGETS[k]["p95_ms"] - d["p95_ms"] for k, d in m.items() if k in BUDGETS)
    print("PERF-BASELINE-PASS（%d 个目标在预算内｜实测峰值 p95=%.1fms，最紧余量 %.0fms｜吞吐 %s rps｜"
          "口径=本地无外网 + 危机路径不调 LLM；这是自身棘轮不是跨项目对比）"
          % (len(BUDGETS), peak, tightest, m.get("throughput_health", {}).get("rps", "取不到")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
