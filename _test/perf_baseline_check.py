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
import os
import platform
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
# r96：单点并发**必须把档位写进读数本身**。立因是 r95 报告自相矛盾——§1 维度 4 印
# `吞吐 1013.9 rps`，§5 又写「并发维度仍无读数」（依据是 grep k6/locust 全仓 0 命中）。
# 两句话各自都对，错在**数字没带自己的口径**：1013.9 是 8 线程闭环 48 请求这一个点上量出来的，
# 而"没有第三方压测工具"是另一件事。⇒ ① PASS 行现印档位；② 下面这套阶梯把单点变成曲线。
DEFAULT_RAMP = (8, 16, 32, 64)
RAMP_WORK = 32            # 每线程请求数 ⇒ 各档总请求 = 档位 × 32
# 为什么从 4 改到 32（r99 一手实测，不是"多跑点更准"的直觉）：
# 漂移尺 `perf_ramp_delta_check.py` 的阈值要压得住**仪器自身的噪声**。同机静置连测 5 轮：
#   work=4  ⇒ 各档 rps 带宽 13.5% / 42.1% / 43.0% / 69.4% / 117.7% / **255.8%**（首轮冷启 986.6）
#   work=32 ⇒ 带宽 9.2% / 15.6% / 16.9% / 26.0% / 29.6% / 31.9% / 33.9% / **38.4%**
# 每档总请求 档位×4（t8 只有 32 个请求、took_s≈0.01）时，两次读数的差主要来自这台机器此刻
# 在忙什么，不来自被测对象 ⇒ 任何 <70% 的漂移阈值都会被噪声自己踩穿。改 work=32 后 50% 阈值
# 才有 11.6 个百分点的余量。旧台账（work=4）与新台账（work=32）**不可比**，由漂移尺的口径腿
# 逐档记 NA、整体回 rc=2 UNVERIFIED（不判红也不判绿），不是回落成"没漂移"。
RAMP_BUDGET_S = 60         # 整段阶梯的硬上限；到点即停并把未跑档记 NA(budget-exhausted)
# r100：每档**重复取中位数**（入口第②条，"先提仪器精度再谈调小阈值"）。一手依据：work=32 时
# 同机静置 5 轮的档内带宽仍有 9.2%~38.4%，r99 只能把检测限如实写成 50%。单档 took_s≈0.07~0.61s
# （实测见 perf-ramp-2026-10-07d.json），整段阶梯 1.2s ⇒ 5 次重复的代价是秒级，不是分钟级。
RAMP_REPS = 5              # 参与中位数的次数
RAMP_WARMUP = 1            # 每档先丢掉的冷启次数（r99 首轮 986.6 rps 的冷启离群点就是这么来的）


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


def reduce_reps(reps_out, warm=None):
    """把同一档多次跑的结果折成**一个中位数读数**（纯函数，selftest 双向打过）。

    为什么是中位数而不是平均值：r99 实测 work=32 单跑时每档带宽仍达 9.2%~38.4%，这类样本
    是**单侧长尾**（某一次被别的进程抢占就飙高），均值会被长尾拖走，中位数不会。
    口径四条，都是"宁可少声称也不虚报"：
      · rps 取各次的中位数（越大越好），p95/max 取各次的中位数（越小越好）；
      · `llm_used` 必须**每一次**都是 False 才算 False——任何一次 True/None 都往严的方向走
        （一次都没证到的东西不许写进结论）；
      · `warm`（冷启丢弃次）只入库计数，不参与任何统计量；
      · 样本不足时 `band_rps` 照实印、不猜：漂移尺的口径腿会因 reps/warmup 不同拒绝互比。
    """
    warm = warm or []
    ok = [r for r in reps_out if r.get("state") == "ok"]
    if not ok:
        return {"state": "NA(no-rep-succeeded)", "reps": len(reps_out),
                "reps_asked": len(reps_out), "reps_warmup_dropped": len(warm)}
    rps = [r["health"]["rps"] for r in ok if (r.get("health") or {}).get("rps") is not None]
    out = {"state": "ok", "reps": len(ok), "reps_asked": len(reps_out),
           "reps_warmup_dropped": len(warm)}
    for face in ("health", "emotion"):
        vals = [r[face] for r in ok if isinstance(r.get(face), dict) and "rps" in r[face]]
        if not vals:
            out[face] = {"state": "NA(no-sample)"}
            continue
        pr = [v["rps"] for v in vals]
        pp = [v["p95_ms"] for v in vals]
        out[face] = {"rps": round(pct(pr, 50), 1), "p95_ms": round(pct(pp, 50), 1),
                     "max_ms": round(pct([v["max_ms"] for v in vals], 50), 1),
                     "threads": vals[0]["threads"], "n": vals[0]["n"],
                     "band_rps": round((max(pr) - min(pr)) / min(pr) * 100.0, 1) if min(pr) else None,
                     "reps_rps": [round(x, 1) for x in pr]}
        if face == "emotion":
            llms = [v.get("llm_used") for v in vals]
            # 单一真相：llm_used 只放在 emotion 面内（judge_ramp 读的就是这一处），
            # 档级不再另存一份副本，免得两处漂移。
            out[face]["llm_used"] = False if all(x is False for x in llms) else (
                None if any(x is None for x in llms) else True)
            out["reps_llm"] = llms
    return out


def measure_ramp(base, tiers, work, budget_s, reps=1, warmup=0):
    """阶梯并发：每档开 `n` 个线程、每线程 `work` 次闭环请求，打两条面
    （health=纯服务端并发；emotion=危机短路句，仍要求不调 LLM）。
    到 `budget_s` 即**停止加档**，未跑的档记 NA(budget-exhausted)——不缩档数、不降并发、
    不加有界重试（放宽等于为绿而松尺，与本仓 voice 8s 预算 / coverage 门同宗纪律）。

    r100：每档跑 `reps` 次并取**中位数**（`reduce_reps`）。立因是 r99 把检测限如实写成 50%
    ——单跑一次时同机静置的档内带宽就有 9.2%~38.4%，30% 量级的真实回退根本检不出。
    先提仪器精度再谈调小阈值，不拿"看不见"当"没坏"。某档跑到一半超预算 ⇒ 该档用已跑完的次数
    出中位数并如实记 `reps`<`reps_asked`（不冒充满次数，也不整档作废）。
    `warmup` 次冷启跑**不进中位数**：r99 那个 986.6 rps 的首轮离群点就是冷启，丢它是修仪器
    而不是挑数据 —— 已跑次数与丢弃次数一起入库（`reps_warmup_dropped`），漂移尺按同一口径拒比。"""
    out = {}
    deadline = time.perf_counter() + budget_s
    crisis_body = json.dumps({"text": CRISIS_TEXT}, ensure_ascii=False).encode("utf-8")
    for n in tiers:
        if time.perf_counter() > deadline:
            out[n] = {"state": "NA(budget-exhausted)", "reps": 0}
            continue
        t_tier = time.perf_counter()
        reps_out = []
        warm = []          # 冷启次数的原始读数：入库留证，但不参与中位数
        got = 0
        for _ in range(max(1, reps) + max(0, warmup)):
            if time.perf_counter() > deadline:
                break
            rec = {"state": "ok"}
            for face, url, body in (("health", base + "/api/health", None),
                                    ("emotion", base + "/api/emotion", crisis_body)):
                def hit(u=url, b=body):
                    return timed(lambda: get(u, b))
                t0 = time.perf_counter()
                try:
                    with ThreadPoolExecutor(max_workers=n) as ex:
                        res = list(ex.map(lambda _: hit(), range(n * work)))
                except (urllib.error.HTTPError, urllib.error.URLError, OSError) as e:
                    rec[face] = {"state": "NA(fetch-failed:%s)" % getattr(e, "reason", e)[:50]}
                    rec["state"] = "NA(fetch-failed)"
                    continue
                wall = time.perf_counter() - t0
                lats = [x[0] for x in res]
                last = res[-1][1][1] if isinstance(res[-1][1], tuple) else res[-1][1]
                d = {"rps": round(len(lats) / wall, 1) if wall > 0 else None,
                     "p95_ms": round(pct(lats, 95), 1), "max_ms": round(max(lats), 1),
                     "n": len(lats), "threads": n}
                if face == "emotion":
                    try:
                        d["llm_used"] = bool(json.loads((last or b"").decode("utf-8", "replace")).get("llm"))
                    except Exception as e:                          # noqa: BLE001
                        d["llm_used"] = None
                        d["guard"] = "UNVERIFIED:%s" % type(e).__name__
                rec[face] = d
            if rec.get("state") == "ok":
                (warm if got < warmup else reps_out).append(rec)
            got += 1
        merged = reduce_reps(reps_out, warm)
        merged["took_s"] = round(time.perf_counter() - t_tier, 2)
        out[n] = merged
    return out


def judge_ramp(ramp, tiers):
    """每档地板**只加不减**：rps ≥ MIN_RPS、p95 ≤ 400ms（沿用 BUDGETS 现值），
    且每档都要证 `llm_used=False`。64 档若撑不住 ⇒ 是真读数，处置是撤档并在报告里写明
    实测塌方点，**不是抬预算**。"""
    bad, na = [], []
    cap = BUDGETS["health"]["p95_ms"]
    for n in tiers:
        d = ramp.get(n)
        if not d or d.get("state") != "ok":
            na.append("%s:%s" % (n, (d or {}).get("state", "没跑")))
            continue
        for face in ("health", "emotion"):
            f = d.get(face, {})
            if not isinstance(f, dict) or "rps" not in f:
                na.append("%s/%s:%s" % (n, face, f.get("state", "无样本")))
                continue
            if f["rps"] < MIN_RPS:
                bad.append("并发@%d %s 吞吐 %.0f rps < 地板 %.0f" % (n, face, f["rps"], MIN_RPS))
            if f["p95_ms"] > cap:
                bad.append("并发@%d %s p95=%.0fms 超预算 %.0fms" % (n, face, f["p95_ms"], cap))
            if face == "emotion" and f.get("llm_used") is not False:
                bad.append("并发@%d 危机路径 llm_used=%s ⇒ 该档数字不是性能，是网络" % (
                    n, f.get("llm_used")))
    return bad, na


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

    # ── r96 阶梯三腿（正例 / 变异 / 边界）：judge_ramp 是新写的，没自证就是没接线 ──
    def tier(n, rps, p95, llm=False):
        return {"state": "ok",
                "health": {"rps": rps, "p95_ms": p95, "n": n * 4, "threads": n},
                "emotion": {"rps": rps, "p95_ms": p95, "n": n * 4, "threads": n,
                            "llm_used": llm}}
    tiers = (8, 16, 32, 64)
    healthy = {n: tier(n, 900.0, 60.0) for n in tiers}
    b, na = judge_ramp(healthy, tiers)
    if b or na:
        bad.append("⑦阶梯正例被误报（四档 900rps/60ms 应全绿）：%s %s" % (b, na))
    slow_tier = dict(healthy)
    slow_tier[64] = tier(64, 10.0, 9000.0)
    b2, _ = judge_ramp(slow_tier, tiers)
    # 一档塌方 ⇒ health 与 emotion **两个面各报 rps 与 p95 两条**，共 4 条。
    # 期望值按"面数×地板数"算，不是按档数拍脑袋（少一条就是某面的地板没咬）。
    if len(b2) != 4:
        bad.append("⑧变异体失效：64 档两面的吞吐与 p95 共应报 4 条，实得 %d ⇒ 有地板没咬：%s"
                   % (len(b2), b2))
    llm_tier = dict(healthy)
    llm_tier[32] = tier(32, 900.0, 60.0, llm=True)
    b3, _ = judge_ramp(llm_tier, tiers)
    if not any("llm_used" in x for x in b3):
        bad.append("⑨变异体失效：某档走了 LLM 却没被点名 ⇒ 并发面口径可被偷换")
    b4, na4 = judge_ramp({8: tier(8, 900.0, 60.0), 16: {"state": "NA(budget-exhausted)"}}, tiers)
    if b4:
        bad.append("⑩预算耗尽不该算判红（它该走 UNVERIFIED 分支）：%s" % b4)
    if len(na4) != 3:
        bad.append("⑪未跑的档必须逐档点名（期望 3 条 NA，实得 %d）⇒ 缺档会被读成『没有缺档』" % len(na4))
    # ── r100 中位数折叠腿：reduce_reps 是新写的纯函数，没自证就是没接线（R238 的层 a）──
    def rep(rps, p95, llm=False):
        return {"state": "ok",
                "health": {"rps": rps, "p95_ms": p95, "n": 32, "threads": 8, "max_ms": p95 * 2},
                "emotion": {"rps": rps, "p95_ms": p95, "n": 32, "threads": 8, "max_ms": p95 * 2,
                            "llm_used": llm}}
    three = [rep(100.0, 60.0), rep(200.0, 70.0), rep(1000.0, 90.0)]
    mid = reduce_reps(three)
    if abs(mid["health"]["rps"] - 200.0) > 1e-6:
        bad.append("⑫中位数取错：[100,200,1000] 的 rps 应取 200（均值会是 433＝被长尾拖走），实得 %s"
                   % mid["health"]["rps"])
    if abs(mid["health"]["band_rps"] - 900.0) > 1e-6:
        bad.append("⑬档内带宽算法失效：(max-min)/min 应得 900.0%%，实得 %s" % mid["health"]["band_rps"])
    if reduce_reps([rep(900.0, 60.0), rep(900.0, 60.0, llm=True), rep(900.0, 60.0)])["emotion"]["llm_used"] is not True:
        bad.append("⑭口径偷换漏报：三次里有一次走了 LLM，中位数读数却写成 False")
    mixed = reduce_reps([rep(900.0, 60.0), rep(900.0, 60.0, llm=None), rep(900.0, 60.0)])
    if mixed["emotion"]["llm_used"] is not None:
        bad.append("⑮未证到的那次没被如实带出：llm_used=None 应折成 None（不得被两次 False 洗绿）")
    w = reduce_reps([rep(900.0, 60.0), rep(900.0, 60.0)], [rep(50.0, 900.0)])
    if w["reps"] != 2 or w["reps_warmup_dropped"] != 1 or w["health"]["rps"] < 800.0:
        bad.append("⑯冷启次掺进了中位数：reps=%s dropped=%s rps=%s（丢弃次那次 50rps 必须不参与）"
                   % (w["reps"], w["reps_warmup_dropped"], w["health"]["rps"]))
    if reduce_reps([])["state"] != "NA(no-rep-succeeded)" or \
            reduce_reps([{"state": "NA(fetch-failed)", "health": {"state": "NA"}}])["state"] != "NA(no-rep-succeeded)":
        bad.append("⑰空/全失败样本被折成了 ok ⇒ 没取到数会冒充『跑过且绿』")
    # 层 b（接线）：中位数读数必须能被 judge_ramp 直接吃，且严口径仍咬得住。
    healthy_mid = {n: reduce_reps(three) for n in (8, 16, 32, 64)}
    bb, nna = judge_ramp(healthy_mid, tiers)
    if bb or nna:
        bad.append("⑱接线失效：reduce_reps 的产物 judge_ramp 读不动（%s %s）⇒ 中位数进不了判据链"
                   % (bb, nna))
    llm_mid = {n: reduce_reps(three) for n in (8, 16, 32, 64)}
    llm_mid[16] = reduce_reps([rep(900.0, 60.0), rep(900.0, 60.0, llm=None)])
    bb2, _ = judge_ramp(llm_mid, (8, 16, 32, 64))
    if not any("llm_used" in x and "16" in x for x in bb2):
        bad.append("⑲变异体失效：16 档中位数读数里 llm_used=None 没被 judge_ramp 点名 ⇒ 中位数把偷换抹平了")
    print("SELFTEST-%s" % ("PASS: 百分位/空样本/恒慢/缺面/口径漂移 + 阶梯 正例/双地板/LLM偷换/NA不冒充绿"
                           " + 中位数 取中/带宽/LLM从严/冷启不掺/空样本/接线双证"
                           if not bad else "FAIL: " + "; ".join(bad)))
    return 1 if bad else 0


def machine_state():
    """台账的**机器状态凭据**（r101）—— 让下一轮真能把阈值收紧的那块机制。

    为什么本轮要加它：r100 实测「每档取中位数压不掉跨轮噪声」，根因是同一轮 5 次共享这台机器
    此刻的状态；而 r101 现算 11 个相邻对的最坏差时，跨轮/离群对（10-05→10-07 的 t64/emotion
    63.1%）与同日静置对混在一个桶里取 max ⇒ 结论只能是「±50% 已是这份数据能支持的最严值」。
    要把跨轮对与同日对分开算，前提是台账里**有**可比性凭据；没有就只能整桶取 max。
    取不到的项一律记 None（不造默认值 —— 那会把"不知道"读成"相同"），`tag_env_set` 明写标识
    到底有没有给：缺它时漂移尺会照实报「N 份台账无机器标识 ⇒ 跨轮不可归因」。
    只用 stdlib：Windows 上 `getloadavg`/`sched_getaffinity` 不存在 ⇒ 相应项为 None。
    """
    tag = (os.environ.get("XINYU_MACHINE") or "").strip() or None
    try:
        load = list(os.getloadavg())
    except (OSError, AttributeError):
        load = None
    try:
        aff = len(os.sched_getaffinity(os.getpid()))
    except (OSError, AttributeError):
        aff = None
    return {"tag": tag, "tag_env_set": tag is not None,
            "cpu_count": os.cpu_count(), "cpu_affinity": aff,
            "os": "%s %s" % (platform.system(), platform.release()),
            "python": platform.python_version(), "loadavg_1m": (load[0] if load else None),
            "taken_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base", nargs="?", default="http://127.0.0.1:8123")
    ap.add_argument("--reps", type=int, default=25)
    ap.add_argument("--ramp", default="",
                    help="阶梯并发档位，逗号分隔（如 8,16,32,64）；**默认关**——电池不因此变长，"
                         "由 CI 的 perf-baseline 作业与人工轮次显式开启")
    ap.add_argument("--ramp-work", type=int, default=RAMP_WORK)
    ap.add_argument("--ramp-reps", type=int, default=RAMP_REPS,
                    help="每档参与中位数的次数（r100；1=退回单次读数）")
    ap.add_argument("--ramp-warmup", type=int, default=RAMP_WARMUP,
                    help="每档先丢掉几次冷启（r100；不计入中位数，只入库计数）")
    ap.add_argument("--ramp-budget", type=int, default=RAMP_BUDGET_S)
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
    tiers = tuple(int(x) for x in a.ramp.split(",") if x.strip())
    ramp, ramp_bad, ramp_na = None, [], []
    if tiers:
        ramp = measure_ramp(a.base, tiers, a.ramp_work, a.ramp_budget,
                            reps=a.ramp_reps, warmup=a.ramp_warmup)
        ramp_bad, ramp_na = judge_ramp(ramp, tiers)
        for n in tiers:
            d = ramp[n]
            h = d.get("health") or {}
            e = d.get("emotion") or {}
            print("  ramp@%-4s %-18s reps=%s(warm丢%s) health: rps=%-8s p95=%-7s band=%-6s"
                  " ｜ emotion: rps=%-8s p95=%-7s band=%-6s llm_used=%s"
                  % (n, d.get("state"), d.get("reps", "-"), d.get("reps_warmup_dropped", "-"),
                     h.get("rps", "-"), h.get("p95_ms", "-"), h.get("band_rps", "-"),
                     e.get("rps", "-"), e.get("p95_ms", "-"), e.get("band_rps", "-"),
                     e.get("llm_used", "-")))
    # 档内带宽（max-min)/min 的中位数口径 —— 检测限由它推导，不靠"感觉够用"。
    bands = [v.get(f, {}).get("band_rps") for v in (ramp or {}).values()
             for f in ("health", "emotion")
             if isinstance(v.get(f), dict) and v[f].get("band_rps") is not None]
    worst_band = round(max(bands), 1) if bands else None
    if a.json:
        Path(a.json).write_bytes(json.dumps({"base": a.base, "reps": a.reps, "samples": m,
                                             "machine": machine_state(),
                                             "budgets": {k: v["p95_ms"] for k, v in BUDGETS.items()},
                                             "concurrency": {"single_point_threads": CONC["threads"],
                                                             "single_point_requests": CONC["threads"] * CONC["per_thread"]},
                                             "ramp": ({"tiers": list(tiers), "work_per_thread": a.ramp_work,
                                                       "reps_per_tier": a.ramp_reps,
                                                       "warmup_per_tier": a.ramp_warmup,
                                                       "machine_tag": machine_state()["tag"],
                                                       "budget_s": a.ramp_budget,
                                                       "worst_band_pct": worst_band,
                                                       "result": {str(k): v for k, v in (ramp or {}).items()}}
                                                      if ramp else None),
                                             "breach": bad + ramp_bad},
                                            ensure_ascii=False, indent=1).encode("utf-8"))
    allbad = bad + ramp_bad
    if allbad:
        for x in allbad:
            print("  FAIL", x)
        print("PERF-BASELINE-FAIL: %d 项超预算/口径失效" % len(allbad))
        return 1
    if ramp_na:
        print("PERF-RAMP-UNVERIFIED: 未跑全的档=%s ⇒ 阶梯这一半记未验（取数不全不得判绿）"
              % "; ".join(ramp_na))
        return 2
    # 实测值必须挤进这一行：电池只保留最后一条含判据词的 stdout，逐项明细行在 CI 里会被丢掉
    # ⇒ 判据是棘轮，看不见被检环境的数字就无从判断"该不该重定基线"（07 在册 P2）。
    # r96：吞吐数**必须同行带并发档**（r95 那条矛盾就是这么产生的）。
    peak = max(d["p95_ms"] for k, d in m.items() if k in BUDGETS)
    tightest = min(BUDGETS[k]["p95_ms"] - d["p95_ms"] for k, d in m.items() if k in BUDGETS)
    tp = m.get("throughput_health", {})
    tier_note = ""
    if ramp:
        line = "｜".join("rps@%d=%s" % (n, (ramp[n].get("health") or {}).get("rps", "NA"))
                        for n in tiers)
        p95s = [(ramp[n].get("health") or {}).get("p95_ms") for n in tiers
                if (ramp[n].get("health") or {}).get("p95_ms") is not None]
        tier_note = ("｜阶梯 %s｜p95@N 峰值 %sms｜每档中位数取 %d 次（另丢冷启 %d 次）"
                     "｜档内带宽最坏 %s%%" % (line, round(max(p95s), 1) if p95s else "-",
                                             a.ramp_reps, a.ramp_warmup,
                                             worst_band if worst_band is not None else "-"))
    print("PERF-BASELINE-PASS（%d 个目标在预算内｜实测峰值 p95=%.1fms，最紧余量 %.0fms｜"
          "吞吐 并发%d线程×%d请求=%s rps%s｜口径=本地无外网 + 危机路径不调 LLM；"
          "这是自身棘轮不是跨项目对比）"
          % (len(BUDGETS), peak, tightest, CONC["threads"], CONC["threads"] * CONC["per_thread"],
             tp.get("rps", "取不到"), tier_note))
    return 0


if __name__ == "__main__":
    sys.exit(main())
