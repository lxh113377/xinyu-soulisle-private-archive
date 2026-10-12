#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""心屿 · 服务端性能基准（八维表第 4 维「性能表现」的自我尺子，r130 新增）。

为什么补这一根尺（不是拍脑袋加脚本）：
  八维对标表里第 4 维历轮都写「peers 无基准 ⇒ 不可测」，本仓自己也没有「响应时间/并发」
  的可复算读数 —— 于是「这次改动有没有变慢」这个问题在结构上无法回答。
  本轮（r130）实测 peers 侧基准在册仍是 **0/16**（`peer_perf_probe.py` 三通道全零），
  所以本判据**不给横比结论**，只给 self 侧可复算的自身趋势基线。

三条纪律（同族坑已多次踩过，写在代码里防复发）：
  1. **服务指纹必记**：8123 上跑的可能是他人旧产物（瘦 jar 冒充 fat jar 是本仓实测过的坑）。
     指纹不同 ⇒ 读数不可比，判据显式标 `fingerprint_changed` 而不是假装同一条曲线。
  2. **环境未验 ≠ 绿**：服务不可达时 rc=2，绝不当 0。
  3. **阈值先测后登记**：`--calibrate` 只打数字不判红；阈值按实测 ×1.5 写进 THRESHOLDS，
     禁止先写阈值再拿它去"解释"实测。

用法：
  python _test/perf_api_check.py                      # 打 8123，判红/绿，落台账
  python _test/perf_api_check.py --calibrate          # 只出数字，不判红（登记阈值时用）
  python _test/perf_api_check.py --base http://127.0.0.1:9xxx --rounds 10
  python _test/perf_api_check.py --selftest           # 内置桩自证（含反例腿，零公网零服务依赖）

退出码：0=绿；1=判红（超阈）；2=环境未验（服务不可达）；3=用法/内部错误
"""
import argparse
import json
import os
import statistics
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "交付物" / "对标数据"

# 阈值：先 `--calibrate` 实测再登记，禁止先写阈值再拿它解释实测。
# 首采（2026-10-12，指纹 service=xinyu-soulisle/stage=J5，8123 上的**他人旧产物**）：
#   health p95=16.18ms ｜ emotion p95=15.99ms ｜ 并发 8×32 全成功
# 登记为 ×3（≈50ms）而非 ×1.5：本机与 CI 负载不同，1.5 倍会把正常抖动读成红。
# ⚠️ 换产物（指纹变化）后必须重新 --calibrate 并更新这里，否则是拿旧曲线判新产物。
# 限流污染自愈的等待秒数：ApiGuardFilter 的桶容量 burst=20、补充速率 60/分钟（≈1 token/s）
# ⇒ 22s 足以回满。写死成常量而不是"随便睡一会儿"：睡多久必须能说清推导，否则就是玄学。
SETTLE_SECONDS = 22

THRESHOLDS = {
    "health": {"p95_ms": 50},
    "emotion": {"p95_ms": 50},
}

# 探测面：GET /api/health（无副作用） + POST /api/emotion（真实计算路径，离线词典腿）
PROBES = [
    ("health", "GET", "/api/health", None),
    ("emotion", "POST", "/api/emotion", '{"text":"今天有点烦，说不上来为什么"}'),
]


def percentile(sorted_vals, pct):
    """nearest-rank 百分位：空表返回 None（不是 0 —— 0 会被读成"极快"）。"""
    if not sorted_vals:
        return None
    k = max(1, int(round(pct / 100.0 * len(sorted_vals))))
    return sorted_vals[min(k, len(sorted_vals)) - 1]


def summarize(samples):
    """纯函数：延迟样本(ms) → 五读数。selftest 直接喂它。"""
    ok = [s for s in samples if s is not None]
    ordered = sorted(ok)
    return {
        "n": len(samples),
        "ok": len(ok),
        "fail": len(samples) - len(ok),
        "mean_ms": round(statistics.fmean(ordered), 2) if ordered else None,
        "p50_ms": round(percentile(ordered, 50), 2) if ordered else None,
        "p95_ms": round(percentile(ordered, 95), 2) if ordered else None,
        "max_ms": round(ordered[-1], 2) if ordered else None,
    }


def http_once(base, method, path, body, timeout):
    """单次请求。返回 (耗时毫秒 or None, 状态码)；连不上时状态码为 0。

    <p>429 必须单独认出来：那是限流闸在正常工作（本仓 burst=20，打 30 次必然被打回 10 次），
    既不是「慢」也不是「故障」。混进 fail 里会让「服务被自己的闸挡住」被读成「服务不可用」。
    """
    data = body.encode("utf-8") if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp.read(4096)
            status = resp.status
    except urllib.error.HTTPError as e:
        return None, e.code
    except (urllib.error.URLError, OSError, ValueError):
        return None, 0
    elapsed = (time.perf_counter() - started) * 1000.0
    return (None, status) if status >= 400 else (elapsed, status)


def tally(samples, statuses):
    """纯函数：延迟样本 + 状态码 → 含 rate_limited 的读数（selftest 直接喂它）。"""
    stat = summarize(samples)
    stat["rate_limited"] = sum(1 for s in (statuses or []) if s == 429)
    return stat


def run_serial(base, rounds, timeout):
    out = {}
    for name, method, path, body in PROBES:
        res = [http_once(base, method, path, body, timeout) for _ in range(rounds)]
        out[name] = tally([ms for ms, _ in res], [st for _, st in res])
    return out


def run_concurrent(base, level, requests, timeout, path="/api/health", body=None):
    """并发吞吐腿：用线程池打固定次数，量总耗时与单请求延迟分布。"""
    barrier = threading.Barrier(min(level, requests))

    def once():
        try:
            barrier.wait(timeout=5)
        except Exception:
            pass
        return http_once(base, "GET" if body is None else "POST", path, body, timeout)

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=level) as pool:
        res = list(pool.map(lambda _: once(), range(requests)))
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    stat = tally([ms for ms, _ in res], [st for _, st in res])
    stat["level"] = level
    stat["elapsed_ms"] = round(elapsed_ms, 2)
    stat["rps"] = round(requests / (elapsed_ms / 1000.0), 2) if elapsed_ms > 0 else None
    return stat


def fingerprint(base, timeout):
    """服务指纹：换产物即换曲线。取不到 ⇒ 返回 None（未验，不是"未知产物=可忽略"）。"""
    try:
        with urllib.request.urlopen(base + "/api/health", timeout=timeout) as resp:
            payload = json.loads(resp.read(4096).decode("utf-8", "replace"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    # `build` 是 r131 加的产物身份（jar:<名>:<摘要12>:<字节数> / classes:<目录>:<mtime>）。
    # 没有它，新旧产物在 service/stage/java/webRoot 上**逐字相同** ⇒ 换产物后曲线会被误当连续。
    return {k: payload.get(k) for k in ("service", "stage", "java", "webRoot",
                                        "indexFound", "vendorFound", "build")}


def judge(endpoints, thresholds):
    """纯函数：返回 [(端点, 指标, 实测, 阈值)] 超限清单。"""
    bad = []
    for name, stat in endpoints.items():
        gate = thresholds.get(name)
        if not gate:
            continue
        for metric, limit in gate.items():
            actual = stat.get(metric)
            if actual is None or actual > limit:
                bad.append((name, metric, actual, limit))
    return bad


def write_ledger(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


# --------------------------------------------------------------------------
# selftest：内置 HTTP 桩，零公网、零外部服务依赖
# --------------------------------------------------------------------------

class _StubHandler(BaseHTTPRequestHandler):
    delay_ms = 0

    def _reply(self, payload):
        if _StubHandler.delay_ms:
            time.sleep(_StubHandler.delay_ms / 1000.0)
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        # r131：桩也回传 build。真实服务端自 r131 起带这一格（产物身份），
        # 桩不带的话，指纹腿在 selftest 里测的是「少一格也能过」——那正是要防的退化解。
        self._reply({"status": "UP", "service": "stub", "stage": "SELFTEST", "java": "stub",
                     "build": "jar:stub.jar:abcdef123456:1024"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            self.rfile.read(length)
        self._reply({"lex": {"emotion": "sadness"}, "final": {"emotion": "sadness"}})

    def log_message(self, *args):
        pass


def selftest():
    checks = []

    def check(name, cond, detail=""):
        checks.append((name, bool(cond), detail))

    # 1) 统计口径腿：已知序列的 p95 必须落在可判位置
    stat = summarize([10.0, 20.0, 30.0, 40.0, 50.0])
    check("p95 of 5 samples == max", stat["p95_ms"] == 50.0, str(stat))
    check("mean of [10..50] == 30", stat["mean_ms"] == 30.0, str(stat))
    check("empty samples -> None not 0", summarize([])["p95_ms"] is None)
    check("fail counted", summarize([1.0, None])["fail"] == 1, str(summarize([1.0, None])))

    # 1b) 429 单独计数：限流是闸在正常工作，不得混进 fail 被读成「服务不可用」
    t = tally([10.0] * 15 + [None] * 5, [200] * 15 + [429] * 5)
    check("429 counted separately", t["rate_limited"] == 5 and t["fail"] == 5, str(t))
    check("ok excludes rate-limited", t["ok"] == 15, str(t))
    t2 = tally([10.0] * 5, [200] * 5)
    check("no 429 -> rate_limited 0", t2["rate_limited"] == 0, str(t2))

    # 2) 阈值门真的有牙：正常值放行 / 超阈判红
    good = {"health": {"p95_ms": 10.0}}
    check("gate passes good", judge(good, THRESHOLDS) == [], str(judge(good, THRESHOLDS)))
    bad = {"health": {"p95_ms": 99999.0}}
    check("gate flags breach", len(judge(bad, THRESHOLDS)) == 1, str(judge(bad, THRESHOLDS)))
    check("gate flags None as breach", len(judge({"health": {"p95_ms": None}}, THRESHOLDS)) == 1)

    # 3) 端到端：起桩 → 真打 → 指纹与读数齐全
    server = ThreadingHTTPServer(("127.0.0.1", 0), _StubHandler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = "http://127.0.0.1:%d" % port
    try:
        fp = fingerprint(base, 5)
        check("fingerprint readable", isinstance(fp, dict) and fp.get("service") == "stub", str(fp))
        # r131：产物身份必须进指纹 —— 没有它，换产物后曲线会被误当同一条
        check("fingerprint carries build identity", (fp or {}).get("build") == "jar:stub.jar:abcdef123456:1024",
              str(fp))
        ends = run_serial(base, 3, 5)
        check("both probes ok", ends["health"]["ok"] == 3 and ends["emotion"]["ok"] == 3, str(ends))
        conc = run_concurrent(base, 4, 8, 5)
        check("concurrency ok", conc["ok"] == 8 and (conc["rps"] or 0) > 0, str(conc))

        # 4) 反例腿：把桩调慢 + 阈值压到 0 ⇒ 必须判红（证明门不是恒真）
        _StubHandler.delay_ms = 60
        slow = run_serial(base, 2, 5)
        # 牙在这一条：把阈值压到 0 后，慢桩必须被判红（否则门恒真）
        breach = judge(slow, {"health": {"p95_ms": 0}})
        check("slow stub breaches gate", len(breach) == 1 and breach[0][0] == "health", str(breach))
        # 反向腿：没登记阈值的端点不得被顺手判红（防止 judge 越权）
        check("ungated endpoint not judged", all(b[0] != "emotion" for b in breach), str(breach))
        check("slow stub really slow", (slow["health"]["p95_ms"] or 0) >= 55, str(slow["health"]))
        _StubHandler.delay_ms = 0

        # 5) 环境未验腿：连一个必然不通的端口 ⇒ 全部 fail 且指纹为 None
        dead_base = "http://127.0.0.1:1"
        check("dead service -> fingerprint None", fingerprint(dead_base, 1) is None)
        dead = run_serial(dead_base, 1, 1)
        check("dead service -> all fail", dead["health"]["fail"] == 1, str(dead))
    finally:
        server.shutdown()
        server.server_close()

    failed = [n for n, ok, _ in checks if not ok]
    for name, ok, detail in checks:
        print("  %s %s%s" % ("PASS" if ok else "RED ", name, ("  -> " + detail) if not ok and detail else ""))
    print("PERF-SELFTEST-%s（%d/%d）" % ("PASS" if not failed else "FAIL", len(checks) - len(failed), len(checks)))
    return 0 if not failed else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description="心屿服务端性能基准（self 侧可复算，不横比）")
    parser.add_argument("--base", default=os.environ.get("XINYU_BASE", "http://127.0.0.1:8123"))
    # 默认 15 而不是 30：本仓 ApiGuardFilter 的桶容量 burst=20，打 30 次必然被自己的闸
    # 打回 10 次 ⇒ 样本残缺。基准要量的是「服务有多快」，不是「闸有多严」。
    parser.add_argument("--rounds", type=int, default=15, help="每端点串行次数（默认低于 burst=20，免被自家限流闸污染样本）")
    parser.add_argument("--concurrency", type=int, default=8, help="并发腿的并发数")
    parser.add_argument("--concurrent-requests", type=int, default=32)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--json", default=None, help="台账落盘路径（默认 交付物/对标数据/perf-api-<date>.json）")
    parser.add_argument("--calibrate", action="store_true", help="只出数字不判红（登记阈值用）")
    parser.add_argument("--tag", default="", help="人工标注这轮读数来自哪个实例（如 old-jar-8123 / r130-new）。"
                                                 "服务端回传的 build 只回答『跑的是哪份产物』，"
                                                 "回答不了『这份产物是不是我本轮想测的那份』——"
                                                 "r130 实测：8123 上跑的是他人旧产物，指纹却与新实例逐字相同。")
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--no-settle", action="store_true",
                        help="关闭「检出限流污染后等桶回满再重跑一次」的自愈（默认开）。"
                             "关掉可用于复现『上一个判据吃掉令牌桶 ⇒ 基准被 429 打残』这一现象。")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    fp = fingerprint(args.base, args.timeout)
    if fp is None:
        print("PERF-UNVERIFIED：%s 不可达（rc=2，环境未验不当绿）。先起服务：java -jar server/target/soulisle-server.jar"
              % args.base)
        return 2

    endpoints = run_serial(args.base, args.rounds, args.timeout)

    # r131：**判据之间共享服务端状态**。先跑 `api_contract_check`（15 条接口连打）会吃掉
    # ApiGuardFilter 的令牌桶，紧跟着跑基准就会看到 429=9 的假象（实测踩到）——
    # 那不是"服务慢"，是上一个判据的余温。等桶回满再重跑一次，比把 429 归因给被测服务诚实。
    # 桶容量 burst=20、补充 60/分钟（≈1/s）⇒ 22s 足够回满；`--no-settle` 可关（用于复现该现象）。
    if not args.no_settle:
        starved = {n: s for n, s in endpoints.items() if s["ok"] < max(1, int(s["n"] * 0.6))}
        if starved:
            print("  · 检出限流污染（%s），等待 %ds 让令牌桶回满后重跑一次（--no-settle 可关）"
                  % (", ".join("%s 429=%d" % (n, s.get("rate_limited", 0)) for n, s in starved.items()),
                     SETTLE_SECONDS))
            time.sleep(SETTLE_SECONDS)
            endpoints = run_serial(args.base, args.rounds, args.timeout)
    conc = run_concurrent(args.base, args.concurrency, args.concurrent_requests, args.timeout)

    payload = {
        "generated_by": "_test/perf_api_check.py",
        "collected_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "base_url": args.base,
        "instance_tag": args.tag or None,
        "fingerprint": fp,
        "rounds": args.rounds,
        "endpoints": endpoints,
        "concurrency": conc,
        "thresholds": THRESHOLDS if not args.calibrate else None,
        "comparable": False,  # peers 侧在册 0/16 ⇒ 本读数只作 self 趋势，禁横比
        "comparable_reason": "peers 基准在册 0/16（peer_perf_probe 三通道，2026-10-12 现采）",
    }
    out = Path(args.json) if args.json else OUT_DIR / ("perf-api-%s.json" % time.strftime("%Y-%m-%d"))
    write_ledger(out, payload)

    print("PERF 服务指纹: %s" % json.dumps(fp, ensure_ascii=False))
    for name, stat in endpoints.items():
        print("  %-8s n=%-3d ok=%-3d fail=%-2d 429=%-2d mean=%-8s p50=%-8s p95=%-8s max=%-8s"
              % (name, stat["n"], stat["ok"], stat["fail"], stat.get("rate_limited", 0),
                 stat["mean_ms"], stat["p50_ms"], stat["p95_ms"], stat["max_ms"]))
    print("  并发 level=%d reqs=%d ok=%d 429=%d rps=%s p95=%sms"
          % (conc["level"], conc["n"], conc["ok"], conc.get("rate_limited", 0), conc["rps"], conc["p95_ms"]))
    print("台账 -> %s" % out)

    # 样本充足门：成功样本不足 60% 时「未验」，不拿残缺样本下结论（多数情形是自撞限流闸）
    for name, stat in endpoints.items():
        if stat["ok"] < max(1, int(stat["n"] * 0.6)):
            print("PERF-UNVERIFIED：%s 成功样本 %d/%d 不足（429=%d）⇒ 不下结论（rc=2）。"
                  "多半是自撞了限流闸：调小 --rounds 到 burst(%d) 以下再测。"
                  % (name, stat["ok"], stat["n"], stat.get("rate_limited", 0), 20))
            return 2

    if args.calibrate:
        print("PERF-CALIBRATE：只出数字不判红（阈值按实测 ×1.5 登记进 THRESHOLDS）")
        return 0

    bad = judge(endpoints, THRESHOLDS)
    # 并发腿的失败率不进 THRESHOLDS（机器差异太大，不给绝对门），但**一条都不许失败**
    if conc["fail"] > 0:
        bad.append(("concurrency", "fail", conc["fail"], 0))
    if bad:
        for name, metric, actual, limit in bad:
            print("RED  %s.%s 实测=%s 阈值=%s" % (name, metric, actual, limit))
        print("PERF-API-FAIL（%d 项超阈）" % len(bad))
        return 1
    print("PERF-API-PASS 全部端点在阈内（self 趋势基线，不可横比）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
