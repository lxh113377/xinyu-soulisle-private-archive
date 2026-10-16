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
退出码：0=在预算内 1=超预算（性能回归）2=服务不可达/样本不足/并发档被限流闸吞掉（未验，不得当通过）
r172 三态口径（一手实测，落盘件可复算）：吞吐相按**状态码分桶**，非 2xx 一律不进 rps/p95。被测面开着
  ApiGuardFilter（默认 burst=20）时，单点档 8×6=48 发必被拦一部分（--reps 5 在 spare 8148 实跑 ⇒
  `2xx=18/48，429=30`；--reps 25 时延迟面先撞顶 ⇒ 落 `<json>.partial` 的 PERF-UNREACHABLE），
  此时并发这一半**没有读数**⇒ 印 `PERF-BASELINE-UNVERIFIED` 并 rc=2，台账落 `<json>.partial` 不覆盖基线。
  修前形态（HEAD 那份脚本原样跑在同一台带闸 spare 上）：--reps 25 ⇒ rc=2 只报「取数失败 emotion_crisis:
  HTTP 429」（等 22s 重试仍是 429）；--reps 5 --no-settle ⇒ rc=1 `仪器异常 HTTPError 429`（BLIND-RED，
  r170 的兜底虽有仪器异常行，但仍无结论、无台账）。**勘误**：这里原写「假绿/账面像合规通过」，盘面否证——
  旧版从没判过绿；真缺陷是**红因不可归因**：「闸把测量拦住了」被报成「服务/判据坏了」，
  且没有任何一条面能自证当时闸开没开。
"""
import argparse
import glob
import json
import os
import platform
import re
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]   # 只用于读**声明面**配置（见 declared_burst）

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
# r121：词典引擎路径的并发地板。推导依据＝私有 spare 服务（复制 jar 到 %TEMP%，端口 8147，
# 独立 H2 库，不碰并行会话正服务的 8123）连测 3 轮 emotion_crisis 吞吐 = 1951.1 / 1980.9 / 1978.9 rps
# （p95 4.4~5.0ms），比 health 档（1690~2158）还稳。取与 health 同一条"塌方级"口径：50 rps ≈ 实测的 1/39。
# 为什么不按实测的 90% 设阈：本轮同机噪声一手在册（ramp 档内带宽 9.2%~38.4%），
# 贴着读数设地板＝给下一轮埋一条会自己踩穿的红。
MIN_RPS_EMOTION = 50.0
# r122：资源占用率两条上限。对标维度 4 原文是「响应时间、资源占用率及并发处理能力」三块，
# 本判据此前只有时延（p95）+ 并发（rps）两块，**资源这块从来没有读数**——不是量了达标，是没量。
# 一手实测（jar sha256=a145cbd5、pid 由 8147 端口反查、独立 H2）连跑 4 轮：
#   工作集 240.8 / 259.0 / 262.2 / 272.6 / 286.0 MB，峰值工作集恒 333.8 MB；
#   单请求 CPU 2278.1 / 3092.7 / 2115.6 / 2278.1 / 651.0 µs（窗口 CPU 增量 ÷ 96 请求）。
# ⚠️ 那个 µs/请求**不是纯业务耗时**：窗口里 JVM 的 JIT、GC、H2 后台线程都算在内，
#    所以它天然比时延维脏（五轮 651.0~3092.7，跨 4.7 倍）。据此只设"数量级退化才红"的两条上限，
#    贴着读数设阈值＝给下一轮埋一条会自己踩穿的红（同 r96/r100 的噪声一手在册）。
MAX_RSS_MB = 1200.0            # ≈观测峰值 333.8MB 的 3.6x ⇒ 抓泄漏/无界缓存，不抓抖动
MAX_US_CPU_PER_REQ = 12000.0   # ≈观测最坏 3092.7µs 的 3.9x ⇒ 抓每请求计算量的数量级退化
IDLE_WINDOW_S = 1.0        # r123 空载窗口长度（秒）：与负载窗口按 CPU 速率归一，不要求等长
# r171：令牌桶回满等待。推导写死在这儿，别让人去猜这个数从哪来 ——
# ApiGuardFilter 默认 burst=20、补充速率 1 token/s ⇒ 空桶到满需 20s，留 2s 余量取 22s。
# 与 `perf_api_check` 的 settle 常量同口径（两处若不一致，改的那处必须同时改另一处）。
GUARD_SETTLE_S = 22
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


def resolve_pid(base):
    """按**被测端口**反查服务进程（不是"随便挑一个 java"）。取不到 ⇒ (None, 通道, 原因)，
    由调用方把这一子项记成未验——禁止折算成 0 或"没有占用"。"""
    try:
        port = int(str(base).rstrip("/").rsplit(":", 1)[-1])
    except (ValueError, IndexError):
        return None, "base", "base 里解析不出端口（%s）" % str(base)[:40]
    if platform.system() == "Windows":
        cmd = ("$c=Get-NetTCPConnection -LocalPort %d -State Listen -ErrorAction SilentlyContinue;"
               "$p=@($c.OwningProcess | Sort-Object -Unique);if($p.Count -gt 0){$p[0]}else{'NONE'}" % port)
        try:
            r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True,
                               text=True, encoding="utf-8", errors="replace", timeout=25)
        except Exception as e:
            return None, "powershell", "%s: %s" % (type(e).__name__, str(e)[:60])
        txt = (r.stdout or "").strip()
        if r.returncode != 0 or not txt or txt == "NONE":
            return None, "powershell", ((r.stderr or "").strip()[:60] or "该端口无监听进程")[:60]
        try:
            return int(txt.splitlines()[0]), "powershell:Get-NetTCPConnection", ""
        except ValueError:
            return None, "powershell", "pid 解析失败：%s" % txt[:30]
    for f in glob.glob("/proc/[0-9]*/cmdline"):          # Linux（CI 里 jar 与判据同容器）
        try:
            cl = open(f, "rb").read().replace(bytes([0]), b" ").decode("utf-8", "replace")
        except OSError:
            continue
        if "soulisle-server.jar" in cl:
            try:
                return int(f.split("/")[2]), "proc:cmdline", ""
            except ValueError:
                continue
    return None, "proc", "/proc 里没有 soulisle-server.jar 进程"


def proc_read(pid):
    """读进程自己的资源量：工作集 / 峰值工作集 / 累计 CPU 毫秒。取不到 ⇒ None（记未验）。"""
    if pid is None:
        return None
    if platform.system() == "Windows":
        cmd = ("$p=Get-Process -Id %d -ErrorAction SilentlyContinue;"
               "if($p){[pscustomobject]@{ws=$p.WorkingSet64;peak=$p.PeakWorkingSet64;"
               "cpu=[math]::Round($p.TotalProcessorTime.TotalMilliseconds,1)}|ConvertTo-Json -Compress}"
               "else{'NONE'}" % pid)
        try:
            r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True,
                               text=True, encoding="utf-8", errors="replace", timeout=25)
            d = json.loads((r.stdout or "").strip())
        except Exception:
            return None
        if not isinstance(d, dict) or "ws" not in d:
            return None
        return {"rss_mb": float(d["ws"]) / 1048576.0, "rss_peak_mb": float(d.get("peak") or 0) / 1048576.0,
                "cpu_ms": float(d.get("cpu") or 0)}
    try:
        st = open("/proc/%d/status" % pid, encoding="utf-8", errors="replace").read()
        raw = open("/proc/%d/stat" % pid, encoding="utf-8", errors="replace").read()
    except OSError:
        return None
    rss = hwm = None
    for ln in st.splitlines():
        if ln.startswith("VmRSS:"):
            rss = float(ln.split()[1]) / 1024.0
        elif ln.startswith("VmHWM:"):
            hwm = float(ln.split()[1]) / 1024.0
    try:
        fields = raw[raw.rindex(")") + 2:].split()      # comm 可含空格 ⇒ 从最后一个 ) 之后切
        hz = os.sysconf("SC_CLK_TCK")
        cpu_ms = (int(fields[11]) + int(fields[12])) * 1000.0 / hz   # utime + stime
    except (ValueError, IndexError):
        return None
    return {"rss_mb": rss, "rss_peak_mb": hwm if hwm is not None else rss, "cpu_ms": cpu_ms}


def resource_net(load_cpu_ms, load_wall, idle_cpu_ms, idle_wall, n_req):
    """**净**单请求 CPU（µs）＝(负载窗口 CPU − 同速率空载 CPU) ÷ 请求数。

    为什么要这一格：r122 的 `us_cpu_per_req` 把 JVM 的 JIT/GC/H2 后台线程一并算进窗口，
    五轮 651.0~3092.7µs 跨 4.7 倍 —— 那不是业务耗时，是"这台机器此刻在忙什么"。
    补一段**同长度的空载窗口**按速率折算后相减，才知道地板该往哪收紧。
    任一读数缺 ⇒ None（未验，禁止用 0 顶替）；结果为负 ⇒ 照实返回，
    由 `resource_state` 侧标 noise-dominated（负号本身就是结论：负载 CPU 与空载同速率之差被噪声吃掉）。
    """
    vals = (load_cpu_ms, load_wall, idle_cpu_ms, idle_wall, n_req)
    if any(v is None for v in vals) or load_wall <= 0 or idle_wall <= 0 or n_req <= 0:
        return None
    net_ms = load_cpu_ms - idle_cpu_ms * (load_wall / idle_wall)
    return round(net_ms * 1000.0 / n_req, 1)


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


def declared_burst():
    """读**声明面**的令牌桶容量：`application.yml` 的 `xinyu.guard.burst` 默认值（环境可覆盖）。

    为什么判据需要它：r172 一手实测「延迟面在带闸实例上结构性不可达」——`--reps 25 > 桶 20`，
    等令牌桶回满也救不了（回满就停在 20），所以 r171 那条 22s settle 重试对这一形态**永远白等**。
    要把「白等」和「值得等」分开，就得有个不靠运行时假设的容量数；读 yml 而不是在判据里写死 20，
    是因为 20 属于被测面的配置（改了配置判据跟着变），写死会变成"判据自己造事实"。
    读不到 ⇒ None：只降级成"不做这个判定"，不猜值、不放宽、不据此判绿。
    """
    yml = ROOT / "server" / "src" / "main" / "resources" / "application.yml"
    try:
        txt = yml.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    m = re.search(r"^\s*burst:\s*\$\{XINYU_GUARD_BURST:(\d+)\}", txt, re.M)
    return int(m.group(1)) if m else None


def latency_reach(reps, cap):
    """串行样本数与令牌桶上限的关系。返回 None=可达（settle 重试有意义），否则返回点名理由。
    `cap is None` ⇒ 声明面读不到，**不判定**（禁止猜一个桶容量来放行或拦人）。"""
    if cap is None or reps <= cap:
        return None
    return ("--reps=%d > 声明桶 %d ⇒ 等回满也只回到 %d，第 %d 发必 429（重试是白等）"
            % (reps, cap, cap, cap + 1))


def required_burst(reps):
    """跑完整一轮对**受闸路径**（`/api/emotion`）的总需求 + 余量。

    r172 一手纠正：结论行原先建议 `--xinyu.guard.burst=reps+16`，实测 burst=64 时这一轮仍被拦
    5/48——因为延迟相先吃掉 25 发，吞吐相再打 48 发，同一条受闸路径共需 **73** 发。
    建议值必须由**本轮自己的请求算术**得出，不能只按触发那条消息的相位算（否则建议本身就是错的）。
    `/api/health` 与静态页不在受闸面（`ApiGuardFilter.OPEN_PATH`，实测桶排空时 health 仍 48/48 通过），
    所以只计 emotion 的两相。余量 16 覆盖同机其他会话打到本实例的请求。
    """
    return reps + CONC["threads"] * CONC["per_thread"] + 16


def partial_receipt(path, d):
    """把「这一轮为什么没有读数」落到台账位旁的 `.partial`，下一轮才分得清"没跑"与"跑了但不可达"。

    立因：r171 起性能基线断更的真实形态是**一个文件都不留**——判据 rc=2 直接退出，
    `交付物/对标数据/` 里只剩旧日期的台账，于是"最近一次测量"读起来像"最近没测过"，
    而实际测过、且每次都被同一个配额硬顶拦回来。留一条带理由的 .partial 才是可归因的缺席。
    写失败只改变**这条留痕**，不改判据结论（rc 由测量本身决定），但必须出声（stderr）。
    """
    if not path:
        return
    try:
        Path(path + ".partial").write_bytes(
            json.dumps(d, ensure_ascii=False, indent=1).encode("utf-8"))
    except OSError as e:
        print("  留痕未写入 %s.partial：%s" % (path, e), file=sys.stderr)


def measured_hdr(e):
    """从 429 响应头取被测面自己报的配额读数（有则点名，无则不编）。"""
    try:
        h = e.headers or {}
        rem, ra = h.get("X-RateLimit-Remaining"), h.get("Retry-After")
    except AttributeError:
        return ""
    if rem is None and ra is None:
        return ""
    return "｜配额头 Remaining=%s Retry-After=%s" % (rem, ra)


def counted(fn):
    """跑一次探针，把**状态码**一起带回来。

    r172 一手：`/api/emotion` 的 429 原先走异常路径 ⇒ 在吞吐这一段直接掀掉整轮
    （`ex.map` 把 HTTPError 抛回主线程，`measure()` 的吞吐块没有 try），判据连结论行都印不出来，
    兜底钩子只能报「仪器异常」。被闸拦下的那一发是**读数**，不是崩溃。
    """
    try:
        ms, resp = timed(fn)
        return ms, (resp[0] if isinstance(resp, tuple) else 200)
    except urllib.error.HTTPError as e:
        return None, e.code


def phase_verdict(res, wall, budget, face):
    """把一批并发探针折成读数。**非 2xx 一律不进 rps/p95** —— 被限流闸拒掉的那些量的是闸，不是服务端。

    立此函数的算术（r172 实测，spare 实例 8147、闸按默认配）：等令牌桶回满 22s 后打 48 并发
    `/api/emotion` ⇒ `status={200:20, 429:28}`；紧接着再打一次 ⇒ `{429:48}`，而那一趟的
    表观 rps 反而从 446 涨到 573（拒得越快显得越"吞吐高"）。所以既不能把 429 当延迟，
    也不能把它算进吞吐，只能如实记「这一档没有读数」并给出口径。
    """
    served = [ms for ms, code in res if ms is not None and 200 <= code < 300]
    rejected = sum(1 for _, code in res if code == 429)
    other = sum(1 for _, code in res
                if code is not None and code != 429 and not (200 <= code < 300))
    d = {"n": len(res), "budget": budget, "served": len(served),
         "rejected_429": rejected, "other_status": other, "face": face}
    if rejected or other or len(served) < budget:
        d["measurable"] = False
        d["why"] = ("限流闸吞掉 %d/%d 发（有效桶 < 并发预算 %d）⇒ %s 这一档的 rps/p95 无读数"
                   % (rejected + other, budget, budget, face))
        return d
    d["measurable"] = True
    d["rps"] = round(len(served) / wall, 1)
    d["p95_ms"] = round(pct(served, 95), 1)
    return d


def guard_state_from_headers(headers, code):
    """把「被测面这一发带回什么限流头」折成口径位。返回 (state, detail)。

    为什么要这一格：r172 发现 CI 与本机的**被测配置可以不同**（perf workflow 起 jar 时没设
    `XINYU_GUARD_*` ⇒ 默认 burst=20；私有 spare 可设 96），而台账里的 rps 从来不写它是**在不在闸后**
    量出来的 —— 于是两份台账长得一样、量的却是两个对象。闸态由被测面自报（`ApiGuardFilter` 只在
    放行路径与 `enabled=false` 时**不设** `X-RateLimit-*`），所以这不是猜，是读。
    state：`guarded`=该发带限流头（闸开且这条路径受闸）／`unguarded`=2xx 且无该头（闸关或路径豁免）
           ／`unknown`=这一发本身没取到（未验，不折算成前两种）。
    """
    if headers is None:
        return "unknown", "探测发未取到响应头"
    lim = headers.get("X-RateLimit-Limit")
    if lim is not None:
        return "guarded", "X-RateLimit-Limit=%s Remaining=%s" % (lim, headers.get("X-RateLimit-Remaining"))
    if code is not None and 200 <= code < 300:
        return "unguarded", "2xx 且无限流头（闸关或路径豁免）"
    return "unknown", "无 headers 也无 2xx（code=%s）" % code


def get(url, body=None):
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": "application/json",
                                          "User-Agent": "xinyu-perf"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status, r.read()


def probe_guard(base):
    """打一发 `/api/emotion` **只为了读闸态**：不计入任何延迟/吞吐样本，成本 = 1 个令牌。
    取不到 ⇒ `unknown`（不默认成 unguarded —— 那会把"没探到"读成"闸关着"，正是要防的假口径）。"""
    body = json.dumps({"text": CRISIS_TEXT}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(base + "/api/emotion", data=body,
                                 headers={"Content-Type": "application/json",
                                          "User-Agent": "xinyu-perf-guardprobe"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return guard_state_from_headers(r.headers, r.status)
    except urllib.error.HTTPError as e:
        return guard_state_from_headers(e.headers, e.code)
    except Exception as e:
        return "unknown", "%s: %s" % (type(e).__name__, str(e)[:60])


def attach_crisis_guard(out, name, last):
    """把「危机短路未调 LLM」这条口径守卫挂到读数上。

    r171 修一手崩溃：原实现直接 `out[name]["llm_used"] = ...`，而 `out[name]` **只在整轮没出
    fatal 时才存在**（`for/else` 的 else 分支才赋值）。于是只要 `/api/emotion` 打不通
    （服务没起、5xx、连接被拒），这里就 `KeyError: 'emotion_crisis'` —— 判据**当场崩掉**，
    电池记成 BLIND-RED，而 perf 基线自那次起**一直在静默断更**（崩在写台账之前 ⇒ 没有新读数）。
    关键差别：崩之前它看起来像"性能有问题"，实际是"仪器自己坏了"。
    现在：键不存在 ⇒ 不写、返回 False，让 fatal 分支正常把这一面报成未验（rc=2）。
    """
    if name not in out:
        return False
    try:
        j = json.loads((last or b"").decode("utf-8", "replace"))
        out[name]["llm_used"] = bool(j.get("llm"))
        out[name]["resp_keys"] = sorted(j.keys())
    except Exception as e:
        out[name]["llm_used"] = None
        out[name]["guard"] = "UNVERIFIED:%s" % e
    return True


def measure(base, reps):
    targets = [
        ("static_index", base + "/", None),
        ("vendor_js", base + "/vendor/three.min.js", None),
        ("health", base + "/api/health", None),
        ("emotion_crisis", base + "/api/emotion",
         json.dumps({"text": CRISIS_TEXT}, ensure_ascii=False).encode("utf-8")),
    ]
    out, fatal = {}, []
    g_state, g_detail = probe_guard(base)
    out["guard_probe"] = {"state": g_state, "detail": g_detail}
    for name, url, body in targets:
        lat, last = [], None
        for _ in range(reps):
            try:
                ms, resp = timed(lambda u=url, b=body: get(u, b))
            except (urllib.error.HTTPError, urllib.error.URLError, OSError) as e:
                # r171：HTTPError 的 `.reason` 可能是空串 ⇒ 原写法印出「取数失败 emotion_crisis: 」
                # 后面什么都没有，等于又造了一条"点名但不可归因"的红。带上类型与状态码才算点名。
                detail = getattr(e, "reason", None) or getattr(e, "strerror", None) \
                    or getattr(e, "msg", None) or "%s: %s" % (type(e).__name__, e)
                if isinstance(e, urllib.error.HTTPError):
                    detail = "HTTP %s (%s)｜%s%s" % (e.code, e.reason or "-", detail, measured_hdr(e))
                fatal.append("%s: %s" % (name, str(detail)[:170]))
                break
            lat.append(ms)
            last = resp[1] if isinstance(resp, tuple) else resp
        else:
            out[name] = {"n": len(lat), "min_ms": round(min(lat), 1),
                         "p50_ms": round(pct(lat, 50), 1), "p95_ms": round(pct(lat, 95), 1),
                         "max_ms": round(max(lat), 1)}
        if name == "emotion_crisis":
            # 口径守卫必须 fail-closed：读不到 / 解析失败都算"口径未证"，不许静默当通过；
            # 而**整轮失败时不得凭空造读数**（r171 一手：那时键根本不存在，原写法直接 KeyError 崩）
            attach_crisis_guard(out, name, last)
    # 吞吐：只测 health（最轻，测的是服务端并发而非上游）
    if not fatal:
        # r122：资源占用率读数 ⇒ 窗口前后各读一次**被测进程自己**的计数器
        # r123：再补一段**空载窗口**（同法前后各读一次），用于把 JIT/GC/后台线程的那份 CPU 扣掉
        pid, pid_how, pid_note = resolve_pid(base)
        r0 = proc_read(pid)
        idle_wall = IDLE_WINDOW_S
        idle_cpu = None
        if r0 is not None:
            time.sleep(idle_wall)
            _ri = proc_read(pid)
            if _ri is not None:
                idle_cpu = max(0.0, _ri["cpu_ms"] - r0["cpu_ms"])
                r0 = _ri                      # 空载窗口之后才是负载窗口的起点
        budget = CONC["threads"] * CONC["per_thread"]

        def hit():
            return counted(lambda: get(base + "/api/health"))
        t0 = time.perf_counter()
        with ThreadPoolExecutor(max_workers=CONC["threads"]) as ex:
            res1 = list(ex.map(lambda _: hit(), range(budget)))
        wall = time.perf_counter() - t0
        out["throughput_health"] = phase_verdict(res1, wall, budget, "/api/health")
        # r121：并发维补**真实计算路径**。立因是对标维度 4 问的是"并发处理能力"，
        # 而这里只有 /api/health 的吞吐 —— health 只做一次文件系统探针，
        # 量到的是"JVM 还活着"，不是"词典引擎在并发下扛不扛得住"。
        # 用同一条危机短路请求（`llm_used=False` 已在延迟维自证，不打上游、不出网）。
        body = json.dumps({"text": CRISIS_TEXT}, ensure_ascii=False).encode("utf-8")

        def hit_emotion():
            return counted(lambda: get(base + "/api/emotion", body))
        t1 = time.perf_counter()
        with ThreadPoolExecutor(max_workers=CONC["threads"]) as ex:
            res2 = list(ex.map(lambda _: hit_emotion(), range(budget)))
        wall2 = time.perf_counter() - t1
        out["throughput_emotion"] = phase_verdict(res2, wall2, budget, "/api/emotion")
        r1 = proc_read(pid)
        if r0 and r1:
            n_req = 2 * budget     # health 与 emotion 两轮闭环
            cpu_ms = max(0.0, r1["cpu_ms"] - r0["cpu_ms"])
            out["resource"] = {"pid": pid, "pid_how": pid_how,
                               "rss_mb": round(r1["rss_mb"], 1),
                               "rss_peak_mb": round(r1["rss_peak_mb"] or r1["rss_mb"], 1),
                               "cpu_ms_window": round(cpu_ms, 1), "requests": n_req,
                               "us_cpu_per_req": round(cpu_ms * 1000.0 / n_req, 1),
                               "idle_cpu_ms": None if idle_cpu is None else round(idle_cpu, 1),
                               "idle_window_s": idle_wall,
                               "us_cpu_per_req_net": resource_net(cpu_ms, wall + wall2,
                                                                  idle_cpu, idle_wall, n_req)}
        else:
            out["resource"] = None
            out["resource_na"] = pid_note or ("进程计数器读不到（pid=%s，通道 %s）" % (pid, pid_how))
    return out, fatal


def resource_state(m):
    """资源子项的状态：ok / na(带原因)。**取不到 ≠「没有占用」**，也不是红——它是一条未验通道。
    main 与 --selftest 共用这一把尺（同一事实只许一处判）。"""
    r = m.get("resource")
    if not r:
        return "na", m.get("resource_na") or "未尝试取数"
    if r.get("rss_mb") is None or r.get("us_cpu_per_req") is None:
        return "na", "读数缺字段（%s）" % ",".join(
            k for k in ("rss_mb", "us_cpu_per_req") if r.get(k) is None)
    return "ok", ""


def judge(m):
    bad = []
    for name, b in BUDGETS.items():
        got = m.get(name)
        if not got:
            bad.append("%s 无样本（取数失败）⇒ 不判绿" % name)
            continue
        if got["p95_ms"] > b["p95_ms"]:
            bad.append("%s p95=%.0fms 超预算 %.0fms（%s）" % (name, got["p95_ms"], b["p95_ms"], b["note"]))
    # 吞吐两面的三态必须可分：`measurable is False` = 被限流闸拦住、**这一档没有读数**（走 main 的
    # UNVERIFIED 分支，rc=2）；缺键/缺 rps = 仪器没跑到那一块（判红，r121 口径）；有 rps 才比地板。
    # 把"闸吞掉了"记成红是虚报缺陷，记成绿是虚报能力——两头都不许。
    tp = m.get("throughput_health") or {}
    if tp.get("measurable") is not False and tp.get("rps") is not None and tp["rps"] < MIN_RPS:
        bad.append("并发吞吐(health) %.0f rps < 地板 %.0f ⇒ 服务端塌方级退化" % (tp["rps"], MIN_RPS))
    te = m.get("throughput_emotion") or {}
    # r121：真实计算路径的并发读数。缺样本一律判红不判绿——"没量到"与"量到但塌了"必须可分。
    if te.get("measurable") is False:
        pass
    elif not te or te.get("rps") is None:
        bad.append("throughput_emotion 无样本 ⇒ 并发维（词典引擎路径）未验，不判绿")
    elif te["rps"] < MIN_RPS_EMOTION:
        bad.append("并发吞吐(emotion) %.0f rps < 地板 %.0f ⇒ 词典引擎在并发下塌方"
                   % (te["rps"], MIN_RPS_EMOTION))
    res = m.get("resource")
    if res:
        if res["rss_mb"] > MAX_RSS_MB:
            bad.append("资源占用 工作集 %.0fMB > 上限 %.0fMB ⇒ 数量级膨胀（泄漏/无界缓存），"
                       "峰值 %sMB" % (res["rss_mb"], MAX_RSS_MB, res["rss_peak_mb"]))
        if res["us_cpu_per_req"] > MAX_US_CPU_PER_REQ:
            bad.append("单请求 CPU %.0fµs > 上限 %.0fµs ⇒ 每请求计算量数量级退化（窗口 %sms / %d 请求）"
                       % (res["us_cpu_per_req"], MAX_US_CPU_PER_REQ, res["cpu_ms_window"], res["requests"]))
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


def _selftest_block4(bad):
    """selftest 的连续区间 651-667（mid_split 原样搬运；判定/阈值/注释未改一字）。"""
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

def _selftest_block3(bad):
    """selftest 的连续区间 670-692（mid_split 原样搬运；判定/阈值/注释未改一字）。"""
    _ok = {k: {"p95_ms": 1.0} for k in BUDGETS}
    for k in BUDGETS:
        _ok[k] = dict(_ok[k], llm_used=False) if k == "emotion_crisis" else _ok[k]
    _ok["throughput_health"] = {"rps": 900.0}
    # （⑥b 首跑就是被这条判红的——我构造的"正常样本"里漏了 emotion 吞吐，新腿当场咬住我自己的桩 ⇒ 腿有牙齿，桩先补全）
    _ok["throughput_emotion"] = {"rps": 800.0}
    if judge(dict(_ok)):
        bad.append("⑥b 正常样本被新增的 emotion 地板误判红 ⇒ 新腿在造永红")
    if not judge(dict(_ok, throughput_emotion={"rps": 12.0})):
        bad.append("⑥c 词典引擎吞吐 12 rps（远低于地板）仍判通过 ⇒ 有地板没咬")
    if not judge(dict(_ok, throughput_emotion=None)) and not judge(_ok):
        bad.append("⑥d emotion 吞吐缺样本却没判红 ⇒ 把「没量到」读成达标")
    # r122 资源占用率四腿（形状取自本轮 spare 实测：rss 294.4MB／峰值 333.8MB／单请求 3580.2µs）
    _res = {"rss_mb": 294.4, "rss_peak_mb": 333.8, "cpu_ms_window": 343.8,
            "requests": 96, "us_cpu_per_req": 3580.2, "pid": 3560}
    if judge(dict(_ok, resource=_res)):
        bad.append("⑦a 正常资源读数被误判红 ⇒ 阈值贴着噪声，下一轮必自己踩穿")
    if not judge(dict(_ok, resource=dict(_res, rss_mb=MAX_RSS_MB + 1))):
        bad.append("⑦b 工作集超上限仍判通过 ⇒ 上限是装饰（泄漏类退化漏报）")
    if not judge(dict(_ok, resource=dict(_res, us_cpu_per_req=MAX_US_CPU_PER_REQ + 1))):
        bad.append("⑦c 单请求 CPU 超上限仍判通过 ⇒ 每请求计算量退化无人管")
    if judge(dict(_ok, resource=None)) or resource_state({"resource": None})[0] != "na":
        bad.append("⑦d 资源取不到却走绿、或没被识别成未验 ⇒「没量到」会被读成达标")
    return _ok, _res

def _selftest_block2(_res, bad):
    """selftest 的连续区间 697-707（mid_split 原样搬运；判定/阈值/注释未改一字）。"""
    if resource_net(300.0, 1.5, 120.0, 1.0, 96) != 1250.0:
        bad.append("⑧净 CPU 算错：%s（算式 (300−120×1.5)×1000÷96 应得 1250.0）"
                   % resource_net(300.0, 1.5, 120.0, 1.0, 96))
    if resource_net(300.0, 1.5, None, 1.0, 96) is not None:
        bad.append("⑧b 空载读数缺却给了数 ⇒ 把「没扣」写成「扣过了」")
    if resource_net(300.0, 0.0, 120.0, 1.0, 96) is not None or resource_net(300.0, 1.5, 120.0, 1.0, 0) is not None:
        bad.append("⑧c 窗口长度或请求数为 0 时没拒算 ⇒ 除零会造出天文数字读数")
    if resource_net(100.0, 1.0, 200.0, 1.0, 96) >= 0:
        bad.append("⑧d 空载比负载还忙时没把负号带出来 ⇒ 噪声主导被抹平成 0，读起来像「几乎不耗 CPU」")
    if resource_state({"resource": _res})[0] != "ok":
        bad.append("⑦e 有读数时 resource_state 没判 ok ⇒ main 会把量到的资源误报成未验")

def _selftest_block1(bad):
    """selftest 的连续区间 710-737（mid_split 原样搬运；判定/阈值/注释未改一字）。"""
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
    return tiers


def selftest():
    """自证判据自身不恒绿：慢样本必须超预算、空样本必须算未验、百分位不得插值造假数。"""
    bad = []
    _selftest_block4(bad)

    # r121：并发维（词典引擎路径）的三条腿——缺样本 / 塌方 / 正常，三态必须可分。
    _ok, _res = _selftest_block3(bad)
    # r123 净 CPU 四腿：正常／任一读数缺⇒None／除零⇒None／负值照实带出（噪声主导本身就是结论）
    # 期望由被测函数自报后再核对算式：(300 − 120×(1.5/1.0))ms ×1000 ÷96 = 1250.0µs
    # （第一版我把期望写成 1125.0 —— 手算错，被测对象反倒报 1250.0；按算式复核后是**我错**，
    #   故改期望而不是改实现。这类"期望凭直觉写"的坑在册：变异/桩的期望必须被测对象自报或算式复核。）
    _selftest_block2(_res, bad)

    # ── r96 阶梯三腿（正例 / 变异 / 边界）：judge_ramp 是新写的，没自证就是没接线 ──
    tiers = _selftest_block1(bad)
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
    # ㉑ r171 一手崩溃的回归腿：`/api/emotion` 打不通时 `out` 里**根本没有这个键**，
    #    原写法在那儿直接 `KeyError: 'emotion_crisis'` ⇒ 判据崩在写台账之前，
    #    电池只记到 BLIND-RED，而性能基线自那次起**静默断更**（没读数 ≠ 读数慢）。
    crashed = {}
    try:
        wrote = attach_crisis_guard(crashed, "emotion_crisis", b"")
    except KeyError as e:
        bad.append("㉑失败面仍凭空写读数（KeyError:%s）⇒ 整跑会崩而不是报未验" % e)
        wrote = None
    if wrote is not False or crashed:
        bad.append("㉑失败面被凭空造出读数：wrote=%r 面=%s" % (wrote, crashed))
    # ㉒ 反向腿：键在场时守卫必须真的挂上 —— 防"整块改成 no-op"把口径守卫静默关掉
    filled = {"emotion_crisis": {}}
    if attach_crisis_guard(filled, "emotion_crisis", b'{"llm":null,"final":{}}') is not True \
            or filled["emotion_crisis"].get("llm_used") is not False:
        bad.append("㉒键在时守卫没挂上（llm_used 未落）⇒ 口径漂移重新隐身")
    # ── r172 吞吐相的三态腿（20 发 2xx + 28 发 429 是本仓一手实测形状）────────────────
    # 立因：原实现把 429 当异常往上抛，吞吐段整跑崩掉（BLIND-RED），而吞吐台账自那次起断更。
    # 修好之后必须有腿盯着新语义：拒掉的发数**既不算延迟也不算吞吐**，且这一档必须落到"未验"。
    def _boom():
        raise urllib.error.HTTPError("http://x/api/emotion", 429, "Too Many Requests", {}, None)
    try:
        b_ms, b_code = counted(_boom)
        b_raised = None
    except Exception as e:
        b_ms, b_code, b_raised = None, None, type(e).__name__
    if b_raised or b_code != 429 or b_ms is not None:
        bad.append("㉓a counted 没把 429 收成读数（raised=%s code=%s ms=%s）⇒ 吞吐段仍会被闸掀掉"
                   % (b_raised, b_code, b_ms))
    full = phase_verdict([(5.0, 200)] * 48, 0.024, 48, "/api/health")
    if not full.get("measurable") or abs(full.get("rps", 0) - 2000.0) > 1.0 or full.get("p95_ms") != 5.0:
        bad.append("㉓正向腿失效：48 发全 200 应得 rps=2000/p95=5.0，实得 %s ⇒ 有闸的面上连合规读数都给不出"
                   % {k: full.get(k) for k in ("measurable", "rps", "p95_ms")})
    mixed = phase_verdict([(5.0, 200)] * 20 + [(0.5, 429)] * 28, 0.02, 48, "/api/emotion")
    if mixed.get("measurable") or "rps" in mixed or mixed.get("rejected_429") != 28:
        bad.append("㉔变异体失效：28 发 429 仍被折进 rps ⇒ 拒得越快显得吞吐越高（本轮实测 446→573）")
    all_no = phase_verdict([(0.5, 429)] * 48, 0.01, 48, "/api/emotion")
    if all_no.get("measurable") or "rps" in all_no or all_no.get("served") != 0:
        bad.append("㉕全拒档被判可测 ⇒ 台账会出现「没有 2xx 却有 rps」的自相矛盾行")
    other = phase_verdict([(5.0, 200)] * 47 + [(9.0, 500)], 0.024, 48, "/api/emotion")
    if other.get("measurable") or other.get("other_status") != 1:
        bad.append("㉖非 429 的 5xx 被当成合规样本 ⇒ 服务端错误的延迟会进 p95、错误率隐身")
    # 三态分得开：可测→比地板；无读数→交给 main 记未验（判红会造永红，判绿是虚报能力）
    _thr = dict(full, measurable=False, served=20, rejected_429=28, face="/api/emotion")
    _thr.pop("rps", None)
    _thr.pop("p95_ms", None)
    if judge(dict(_ok, throughput_emotion=_thr)):
        bad.append("㉗限流导致的无读数被判红 ⇒ 环境状态冒充性能缺陷（同 r131 settle 的口径）")
    if not judge(dict(_ok, throughput_health={"rps": 12.0, "measurable": True})):
        bad.append("㉘health 面加了 measurable 分支后地板失效 ⇒ 服务端塌方漏报")
    if not judge(dict(_ok, throughput_emotion={"measurable": None})):
        bad.append("㉙measurable 缺失（旧形状/崩在半路）被判通过 ⇒ 未验被读成达标")
    # ── r172 声明面容量 + 白等判定 + 配额头取证 三条腿 ──
    cap = declared_burst()
    if not isinstance(cap, int) or cap <= 0:
        bad.append("㉚application.yml 的 xinyu.guard.burst 读不出正整数（实得 %r）⇒ "
                   "「样本数 vs 桶容量」这格静默失效，下一轮又会白等 22s" % cap)
    if not latency_reach(25, 20) or "25" not in latency_reach(25, 20) or "20" not in latency_reach(25, 20):
        bad.append("㉛白等判定没点名算术（25 vs 20）⇒ 结论行读起来像环境坏了，不是配额硬顶")
    if latency_reach(20, 20) is not None or latency_reach(25, None) is not None:
        bad.append("㉜等号档或读不到容量时被判定拦下 ⇒ 声明面缺失时判据开始替被测面猜数")
    _h = urllib.error.HTTPError("u", 429, "Too Many Requests",
                                {"X-RateLimit-Remaining": "0", "Retry-After": "1"}, None)
    if "Remaining=0" not in measured_hdr(_h) or "Retry-After=1" not in measured_hdr(_h):
        bad.append("㉝被测面报的配额头没进结论（实得 %r）⇒ 归因少一格实证" % measured_hdr(_h))
    if measured_hdr(urllib.error.HTTPError("u", 429, "x", {}, None)) != "":
        bad.append("㉞无头时编出了读数 ⇒ 假配额头比没有更坏")
    need = required_burst(25)
    if need < 25 + CONC["threads"] * CONC["per_thread"]:
        bad.append("㉟建议桶容量只覆盖触发那条消息的相位（实得 %d，本轮共需 ≥%d）⇒ 建议本身是错的"
                   "（r172 一手：burst=64 时仍被拦 5/48）" % (need, 25 + 48))
    if required_burst(26) != required_burst(25) + 1:
        bad.append("㊱建议值不跟 --reps 走（写成常数了）⇒ 改了样本数没人改建议")
    # ── r172 闸态口径位四腿：读数必须带上"量的是闸前还是闸后"，探不到不许当探到 ──
    gs1, _ = guard_state_from_headers({"X-RateLimit-Limit": "60", "X-RateLimit-Remaining": "0"}, 429)
    gs2, _ = guard_state_from_headers({}, 200)
    gs3, _ = guard_state_from_headers(None, 200)
    gs4, _ = guard_state_from_headers({}, 500)
    if (gs1, gs2, gs3, gs4) != ("guarded", "unguarded", "unknown", "unknown"):
        bad.append("㊲闸态四态折错（实得 %s）⇒ 台账会把「闸后」与「闸前」的 rps 混成同一格"
                   % (gs1, gs2, gs3, gs4))

    print("SELFTEST-%s" % ("PASS: 百分位/空样本/恒慢/缺面/口径漂移 + 阶梯 正例/双地板/LLM偷换/NA不冒充绿"
                           " + 中位数 取中/带宽/LLM从严/冷启不掺/空样本/接线双证"
                           " + 资源 正常/超工作集/超单请求CPU/缺数不判绿/有数不误未验 + 净CPU 正常/缺读数/除零/负值不抹平"
                           " + 吞吐三态 全2xx有数/掺429无读数/全429无读数/5xx不入合规/无读数不判红也不判绿/地板仍在位"
                           " + 限流归因 声明桶读出/白等点名算术/等号与缺容量不猜/配额头取证/无头不编/建议桶随样本数走"
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


def _main_block2(a, throttled):
    """main 的连续区间 943-963（mid_split 原样搬运；判定/阈值/注释未改一字）。"""
    if throttled and not a.no_settle:
        cap = declared_burst()
        # 结构性不可达：串行样本数 > 令牌桶上限时，等回满也没用（回满就停在 cap，第 cap+1 发必 429）。
        # 这时再睡 22s 重跑一遍同样的形状是**白等**（r171 那条 settle 是为"上一判据的余温"设计的，
        # 覆盖不了"本轮样本数本身就超配额"这一类），所以直接点名算术并退出，不装作重试过。
        why = latency_reach(a.reps, cap)
        if why:
            partial_receipt(a.json, {"kind": "PERF-UNREACHABLE", "base": a.base, "reps": a.reps,
                                     "declared_burst": cap, "why": why, "measured": throttled,
                                     "machine": machine_state()})
            print("PERF-ENV: 延迟面在带闸实例上结构性不可达 —— %s；实测面 %s"
                  "。两条出路：空闲副本加 `--xinyu.guard.burst=%d`（整轮对 /api/emotion 共需 %d 发）起服务复跑，"
                  "或把 --reps 收到 ≤%s（收样本档时结论行必须印档）%s"
                  % (why, throttled[0][:80], required_burst(a.reps), required_burst(a.reps) - 16, cap,
                     "；缺席理由已写 %s.partial" % a.json if a.json else ""))
            return 2
        print("   限流重试：检出 %d 条 429 ⇒ 等 %ds 让令牌桶回满后重打一次（复算：--no-settle 可关）"
              % (len(throttled), GUARD_SETTLE_S))
        time.sleep(GUARD_SETTLE_S)
        retried = 1
        m, fatal = measure(a.base, a.reps)
    return fatal, m, retried

def _main_block1(a, bad, m, no_read, ramp, ramp_bad, tiers, worst_band):
    """main 的连续区间 1006-1024（mid_split 原样搬运；判定/阈值/注释未改一字）。"""
    if a.json:
        Path(a.json + (".partial" if no_read else "")).write_bytes(
            json.dumps({"base": a.base, "reps": a.reps, "samples": m,
                                             "machine": machine_state(),
                                             "budgets": {k: v["p95_ms"] for k, v in BUDGETS.items()},
                                             "concurrency": {"single_point_threads": CONC["threads"],
                                                             "single_point_requests": CONC["threads"] * CONC["per_thread"],
                                                             "throttled_faces": sorted(no_read),
                                                             "guard_settle_s": GUARD_SETTLE_S},
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base", nargs="?", default="http://127.0.0.1:8123")
    ap.add_argument("--reps", type=int, default=25)
    ap.add_argument("--no-settle", action="store_true",
                    help="关掉 r171 的限流自愈重试，专门用于复现「上一个判据的余温把基线打成 429」")
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
    # r171：撞**自家限流闸**（429）不是性能退化，也不是被测面坏了 —— 是上一个判据的余温。
    # r131 已给 `perf_api_check` 定过同一处置：等令牌桶回满再打一次，且**必须点名重试了几次**，
    # 不许静默。推导：ApiGuardFilter 默认 burst=20、1 token/s ⇒ 满桶需 20s，取 22s 留 2s 余量。
    # 只重试一次（不是循环放宽）：真被限流打断时第二次仍会 429，那时如实报未验。
    throttled = [f for f in fatal if "429" in f]
    retried = 0
    fatal, m, retried = _main_block2(a, throttled)
    if fatal:
        partial_receipt(a.json, {"kind": "PERF-FETCH-FAILED", "base": a.base, "reps": a.reps,
                                 "fatal": fatal, "retried": retried, "machine": machine_state()})
        print("PERF-ENV: 取数失败 %s ⇒ 未验证（限流重试次数=%d）%s"
              % ("; ".join(fatal), retried,
                 ("；缺席理由已写 %s.partial" % a.json) if a.json else ""))
        return 2
    for name in ("static_index", "vendor_js", "health", "emotion_crisis",
                 "throughput_health", "throughput_emotion"):
        d = m[name]
        extra = ("｜llm_used=%s keys=%s" % (d.get("llm_used"), d.get("resp_keys"))) if "llm_used" in d else (
            ("｜rps=%s" % d.get("rps")) if "rps" in d else
            ("｜无读数：%s" % d.get("why")[:70] if d.get("measurable") is False else ""))
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
    # r172：**降级读数不得覆盖基线**（同 r101 的 .partial 口径）。被限流闸吞掉的那一档没有 rps，
    # 这一轮的台账只能是 `.partial`——把"没量到"写回基线，下一轮就再也分不清是环境坏了还是服务退了。
    no_read = {k: d for k, d in m.items()
               if k.startswith("throughput_") and isinstance(d, dict) and d.get("measurable") is False}
    _main_block1(a, bad, m, no_read, ramp, ramp_bad, tiers, worst_band)
    allbad = bad + ramp_bad
    if allbad:
        for x in allbad:
            print("  FAIL", x)
        print("PERF-BASELINE-FAIL: %d 项超预算/口径失效" % len(allbad))
        return 1
    if no_read:
        for k in sorted(no_read):
            d = no_read[k]
            print("  无读数 %-20s %s（2xx=%d/%d，429=%d，其他非 2xx=%d）"
                  % (k, d.get("why"), d["served"], d["budget"],
                     d["rejected_429"], d["other_status"]))
        budget = CONC["threads"] * CONC["per_thread"]
        print("PERF-BASELINE-UNVERIFIED: 并发维在带限流闸的被测面上无读数——单点档 %d 线程×%d=%d 发，"
              "实测各面放行 %s ⇒ 有效桶容量小于并发预算，rps/p95 记未验；台账写 %s%s。"
              "要拿容量真值：在**空闲副本**上加 `--xinyu.guard.burst=%d` 起服务后复跑"
              "（整轮对 /api/emotion 共需 %d 发=延迟 %d + 吞吐 %d；正解是给被测面配够桶，"
              "不是把并发预算调到桶以下去迎合闸）"
              % (CONC["threads"], CONC["per_thread"], budget,
                 " ".join("%s=%d/%d" % (no_read[k]["face"], no_read[k]["served"], no_read[k]["budget"])
                          for k in sorted(no_read)),
                 a.json or "(未指定 --json)", ".partial" if a.json else "",
                 required_burst(a.reps), required_burst(a.reps) - 16, a.reps, budget))
        return 2
    if ramp_na:
        print("PERF-RAMP-UNVERIFIED: 未跑全的档=%s ⇒ 阶梯这一半记未验（取数不全不得判绿）"
              % "; ".join(ramp_na))
        return 2
    if resource_state(m)[0] == "na":
        print("PERF-RESOURCE-UNVERIFIED: 资源占用这一子项无读数（%s）⇒ 维度 4 的资源那一半未验，不得记为通过"
              % m.get("resource_na", "未尝试取数"))
        return 2
    # 实测值必须挤进这一行：电池只保留最后一条含判据词的 stdout，逐项明细行在 CI 里会被丢掉
    # ⇒ 判据是棘轮，看不见被检环境的数字就无从判断"该不该重定基线"（07 在册 P2）。
    # r96：吞吐数**必须同行带并发档**（r95 那条矛盾就是这么产生的）。
    peak = max(d["p95_ms"] for k, d in m.items() if k in BUDGETS)
    tightest = min(BUDGETS[k]["p95_ms"] - d["p95_ms"] for k, d in m.items() if k in BUDGETS)
    tp = m.get("throughput_health", {})
    te = m.get("throughput_emotion", {})
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
    rs = m.get("resource") or {}
    res_note = ("资源 工作集=%sMB 峰值=%sMB 单请求CPU=%sµs（扣空载后净=%sµs，空载 %sms/%ss）"
                "（pid %s 由端口反查）"
                % (rs.get("rss_mb", "NA"), rs.get("rss_peak_mb", "NA"),
                   rs.get("us_cpu_per_req", "NA"), rs.get("us_cpu_per_req_net", "NA"),
                   rs.get("idle_cpu_ms", "NA"), rs.get("idle_window_s", "NA"), rs.get("pid", "NA"))) if rs else "资源 未验"
    print("PERF-BASELINE-PASS（%d 个目标在预算内｜实测峰值 p95=%.1fms，最紧余量 %.0fms｜"
          "吞吐 并发%d线程×%d请求：health=%s rps／emotion=%s rps（词典引擎真实路径%s）｜%s｜"
          "闸态=%s（%s）｜"
          "口径=本地无外网 + 危机路径不调 LLM；这是自身棘轮不是跨项目对比）"
          % (len(BUDGETS), peak, tightest, CONC["threads"], CONC["threads"] * CONC["per_thread"],
             tp.get("rps", "取不到"), te.get("rps", "取不到"), tier_note, res_note,
             (m.get("guard_probe") or {}).get("state", "unknown"),
             (m.get("guard_probe") or {}).get("detail", "未探测")))
    return 0


if __name__ == "__main__":
    # r171：本件 750 行、此前**没有任何未捕获异常兜底** ⇒ 2026-10-13 那次 `KeyError: 'emotion_crisis'`
    # 崩在结论行之前，电池只记到 BLIND-RED（有 rc、零读数），而性能基线因此静默断更。
    # 兜底词汇唯一在 `check_instrument.verdict_for`（服务不可达→UNVERIFIED rc=2／仪器 bug→RED rc=1），
    # 本处不另写一份归因逻辑。
    from check_instrument import install_excepthook
    install_excepthook("PERF-BASELINE")
    sys.exit(main())
