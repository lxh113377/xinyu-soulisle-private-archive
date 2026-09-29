# -*- coding: utf-8 -*-
"""套件资源普查：全量电池里每条套件**实际占哪块资源**，从目标脚本源码证据判出来。

动因（r69 的在册建议 → r70 的读数）：r69 拿到"合计 549s、mobile 一条就 123.5s"之后，
报告里写的下一步是"按是否共享 jar@8123 分桶并行"。那句话当时是**主张**：
没有任何地方在册回答"99 条里几条真碰 8123、这些几条占多少秒"。本件把它变成可复算的普查。

三条设计约束（都是本轮实测踩出来的形状，不是偏好）：
1) 分类按**证据**不按名字登记表：碰 8123 写进判据的登记表，改天有人新加一条套件忘了登记，
   普查就会把"碰共享服务的"印成"可并行的" —— 那比没有普查更坏（在册教训：声明名册 ≠ 行为）。
2) 取不到证据要记 **blind**，绝不折叠成"不碰共享资源"（在册教训：盲区不是零）。
3) `--selftest` 桩与真跑要分轴：同一个文件的桩路径是纯函数，按文件分类会把 ~30 条桩误并进 jar 桶，
   桶就白分了。**但"桩不碰 jar"本件只是按调用参数推断，未实测** ⇒ 见 facet `stub_unproven`，
   要拿它做并行决策前必须先补行为回执（见 --trace-behaviour 一节，本件不谎称已做）。
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "_test"))

TIMING_LEDGER = ROOT / "交付物" / "对标数据" / "battery-timing.json"

# 证据表：(类别, 正则, 是否互斥, 说明)
# 互斥 = 两条套件同跑会互相踩出无法归因的红（r41 实测：emotion_wiring 与 live_sync 并发窗口双红、单跑均绿）
FACETS = [
    ("jar8123", re.compile(r"\b8123\b"), True,
     "共享 Java 服务端：H2 文件库 + 同一份静态页，清除/计数类动作互覆 ⇒ 串行"),
    ("own_server", re.compile(r"TCPServer|HTTPServer|serve_forever"), False,
     "自带临时服务器：实测三处绑 port=0 或 free_port() ⇒ 端口不冲突，可并行"),
    ("browser", re.compile(r"sync_playwright|chromium\.launch"), False,
     "起 Chromium：吃内存但不互斥 ⇒ 是节流维度不是排他维度"),
    ("public_net", re.compile(r"https?://(?!127\.0\.0\.1|localhost)[a-z0-9.-]+", re.I), False,
     "出公网：受上游限流/余额影响（红不一定出自本仓），彼此不互斥"),
    ("build", re.compile(r"\bmvn\b|\bjavac\b|java -jar"), False,
     "调构建/JVM：重但不改共享状态"),
]
# 固定端口绑定是第二类互斥资源（port=0 不是）：必须把端口号本身取出来当键
FIXED_BIND = re.compile(r'(?:TCPServer|HTTPServer|Server)\(\s*\(\s*"[^"]+"\s*,\s*(\d+)\s*\)')
STUB_FLAGS = ("--selftest",)


def classify_src(src):
    """纯函数：源码 → 资源类别集合。空集＝"未检出证据"，由调用方判成 offline 或 blind。

    返回 dict：类别 → 附加信息（固定端口号列表 / 空串）。
    """
    out = {}
    for name, rx, _excl, _why in FACETS:
        if rx.search(src):
            out[name] = ""
    ports = sorted({p for p in FIXED_BIND.findall(src) if p != "0"})
    if ports:
        out["fixed_port"] = ",".join(ports)
    return out


def exclusive_keys(facets):
    """该套件的排他键列表：同键的两条不得同跑。空列表＝与谁都不同时冲突。"""
    k = []
    if "jar8123" in facets:
        k.append("jar8123")
    if "fixed_port" in facets:
        k += ["port:" + p for p in facets["fixed_port"].split(",")]
    return k


def target_of(cmd):
    """从 cmd 里取被检脚本；取不到记 None（→ blind，不得当 offline）。"""
    for c in cmd[1:]:
        s = str(c)
        if s.endswith(".py") or s.endswith(".js"):
            return s
    return None


def mode_of(cmd):
    return "stub" if any(f in [str(c) for c in cmd] for f in STUB_FLAGS) else "real"


def census(suites):
    """→ (rows, blind)。rows 每条含 suite/facets/exclusive/mode/target。blind=取不到证据面的套件名。"""
    rows, blind = [], []
    for name, cmd in suites:
        tgt = target_of(cmd)
        path = ROOT / tgt if tgt else None
        if not path or not path.exists():
            blind.append(name)
            rows.append({"suite": name, "target": tgt, "mode": mode_of(cmd),
                         "facets": {}, "exclusive": [], "state": "blind"})
            continue
        try:
            src = path.read_text("utf-8", errors="replace")
        except Exception:
            blind.append(name)
            rows.append({"suite": name, "target": tgt, "mode": mode_of(cmd),
                         "facets": {}, "exclusive": [], "state": "blind"})
            continue
        f = classify_src(src)
        rows.append({"suite": name, "target": tgt, "mode": mode_of(cmd), "facets": f,
                     "exclusive": exclusive_keys(f), "state": "ok"})
    return rows, blind


def read_ledger():
    """取 r70 落的耗时台账。缺件/不可解析 → (None, 原因)，绝不返回空字典冒充"都没耗时"。"""
    if not TIMING_LEDGER.exists():
        return None, "台账不存在 ⇒ 耗时维度整体未测（先跑一轮全量电池）"
    try:
        data = json.loads(TIMING_LEDGER.read_text("utf-8"))
    except Exception as e:
        return None, "台账不可解析 %s" % e
    if data.get("coverage") != "full":
        return None, "台账 coverage=%r 非 full ⇒ 不得当全量分布用" % data.get("coverage")
    return data, ""


def bucket_plan(rows, ledger):
    """纯函数：按排他键分桶 + （有耗时台账时）算并行天花板。

    桶 = 排他键 或 free；同桶内必须串行，不同桶可同跑。
    天花板口径：makespan 下界 = max(最大桶耗时, ...) —— 这里只报**桶耗时上界**（= 全串行的可省部分），
    不谎称这是实测加速比；实测要真跑一次两桶并发（r70 的回执步）。
    """
    sec = {}
    if ledger:
        sec = {r["suite"]: r.get("seconds", 0.0) for r in ledger.get("rows", [])}
    buckets = {}
    for r in rows:
        # 盲区单独成桶：落进 free 就等于宣布"它可以和任何一条同跑"，而我们对它一无所知
        if r.get("state") == "blind":
            key = "blind"
        else:
            key = "+".join(r["exclusive"]) if r["exclusive"] else "free"
        b = buckets.setdefault(key, {"n": 0, "s": 0.0, "members": []})
        b["n"] += 1
        b["s"] += sec.get(r["suite"], 0.0)
        b["members"].append(r["suite"])
    return buckets, bool(sec)


def selftest():
    """双向自证：该检出的要检出、该分开的要分开、取不到证据的必须是 blind 而不是"自由并行"。

    条数由 CASES 现算 —— 硬编码"N 类桩"会和实际脱钩（同族坑：登记表抄错）。
    """
    rows = [{"suite": "a", "exclusive": ["jar8123"], "state": "ok", "mode": "real", "facets": {}},
            {"suite": "b", "exclusive": ["jar8123"], "state": "ok", "mode": "real", "facets": {}},
            {"suite": "c", "exclusive": [], "state": "ok", "mode": "stub", "facets": {}},
            {"suite": "d", "exclusive": [], "state": "blind", "mode": "real", "facets": {}}]
    led = {"coverage": "full", "rows": [{"suite": "a", "seconds": 10.0},
                                        {"suite": "b", "seconds": 4.0},
                                        {"suite": "c", "seconds": 1.0},
                                        {"suite": "d", "seconds": 99.0}]}
    buckets, have = bucket_plan(rows, led)
    _b2, have2 = bucket_plan(rows, None)
    jar = classify_src('PORT = "http://127.0.0.1:8123/api"\n')
    ephem = classify_src('srv = socketserver.TCPServer(("127.0.0.1", 0), H)\nsrv.serve_forever()\n')
    fixed = classify_src('httpd = socketserver.TCPServer(("127.0.0.1", 18123), Q)\nhttpd.serve_forever()\n')
    cases = [
        ("正例 源码含 8123 判成共享 jar", "jar8123" in jar),
        ("正例 检出即进排他键（否则分桶会把它当可并行）", exclusive_keys(jar) == ["jar8123"]),
        ("恒真守卫 纯函数源码不得判出资源", not classify_src("def f():\n    return 1\n")),
        ("反例 port=0 是临时端口，不构成排他", "fixed_port" not in ephem),
        ("正例 自带服务器要检出（否则漏一类资源）", "own_server" in ephem),
        ("正例 固定端口 18123 必须成为排他键", exclusive_keys(fixed) == ["port:18123"]),
        ("正例 非本机 https 记公网证据",
         "public_net" in classify_src('v = "https://api.deepseek.com/y"\n')),
        ("反例 纯本机回环不得判成公网依赖",
         "public_net" not in classify_src('u = "http://127.0.0.1:8123/x"\n')),
        ("正例 同排他键并桶且耗时累加（14s）",
         sorted(buckets) == ["blind", "free", "jar8123"]
         and buckets["jar8123"]["n"] == 2 and buckets["jar8123"]["s"] == 14.0),
        ("反例 取不到证据的套件不得落进 free 桶（盲区不是零）",
         buckets.get("blind", {}).get("members") == ["d"]
         and "d" not in buckets.get("free", {}).get("members", [])),
        ("有台账才许报已计时", have and not have2),
    ]
    bad = [n for n, ok in cases if not ok]
    print("CENSUS-SELFTEST-%s（%d/%d 类桩）"
          % ("PASS" if not bad else "FAIL: " + "; ".join(bad), len(cases) - len(bad), len(cases)))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--json", default="", help="台账输出路径；传 '-' 不落盘（读数不得据以改判）")
    ap.add_argument("--show-members", action="store_true", help="打印每桶成员名（默认只出计数）")
    a = ap.parse_args()
    if a.selftest:
        return selftest()

    import run_all_suites as R
    rows, blind = census(R.SUITES)
    total = len(R.SUITES)
    ledger, why = read_ledger()
    buckets, have = bucket_plan(rows, ledger)

    by_facet = {}
    for r in rows:
        for f in r["facets"]:
            by_facet[f] = by_facet.get(f, 0) + 1
    print("-" * 100)
    print("普查单位：%d 条套件（分母取自 run_all_suites.SUITES，不手抄）｜ 取到证据面 %d ｜ BLIND %d"
          % (total, total - len(blind), len(blind)))
    for f in sorted(by_facet):
        excl = dict((n, e) for n, _r, e, _w in FACETS).get(f, f == "fixed_port")
        print("  %-11s %3d 条  %s  ｜ %s" % (f, by_facet[f],
                                             "排他(须串行)" if excl else "非排他(可并行)",
                                             dict((n, w) for n, _r, _e, w in FACETS).get(f, "固定端口：两条同绑必互踩")))
    real_jar = [r for r in rows if "jar8123" in r["facets"] and r["mode"] == "real"]
    stub_jar = [r for r in rows if "jar8123" in r["facets"] and r["mode"] == "stub"]
    print("碰 8123 的：真跑腿 %d 条 ｜ 桩腿 %d 条（桩是否真不碰 jar **未实测**，见头注第 3 条）"
          % (len(real_jar), len(stub_jar)))
    print("-" * 100)
    order = sorted(buckets.items(), key=lambda kv: (-kv[1]["n"], kv[0]))
    for key, b in order:
        print("  桶 %-14s %3d 条 ｜ 耗时 %s" % (
            key, b["n"], ("%.1fs" % b["s"]) if have else "未计时"))
        if a.show_members:
            print("        " + ", ".join(b["members"]))
    serial = sum(b["s"] for b in buckets.values())
    if have:
        biggest = max(buckets.items(), key=lambda kv: kv[1]["s"])
        print("全串行 %.1fs ｜ 最大桶 %s=%.1fs ⇒ 该桶**自身**就是并行后的时间下界（除它之外的桶可与它同跑）"
              % (serial, biggest[0], biggest[1]["s"]))
        print("⇒ 天花板读数：省下的上限 %.1fs（%.0f%%）｜这是**算出来的上界**，不是实测加速比"
              % (serial - biggest[1]["s"], 100.0 * (serial - biggest[1]["s"]) / serial if serial else 0))
    else:
        print("CEILING-UNVERIFIED: " + why)
    print("-" * 100)
    idn = sum(b["n"] for b in buckets.values())
    print("恒等式：分桶 %d == 套件 %d ⇒ %s" % (idn, total, "OK" if idn == total else "不成立"))
    if a.json != "-":
        path = Path(a.json) if a.json else (ROOT / "交付物" / "对标数据" / "suite-resource-census.json")
        payload = {"generated_by": "_test/suite_resource_census.py",
                   "ceiling": "只出资源与耗时分桶；最大桶是**算出的时间下界**，不是实测加速比",
                   "suites": total, "blind": blind, "timings_from": TIMING_LEDGER.name if have else None,
                   "buckets": {k: {"n": v["n"], "seconds": round(v["s"], 1), "members": v["members"]}
                               for k, v in buckets.items()},
                   "rows": [{"suite": r["suite"], "target": r["target"], "mode": r["mode"],
                             "facets": sorted(r["facets"]), "exclusive": r["exclusive"]} for r in rows]}
        blob = json.dumps(payload, ensure_ascii=False, indent=1).encode("utf-8")
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_bytes(blob)
        tmp.replace(path)
        back = path.read_bytes()
        print("LEDGER-%s %s ｜ 指纹 sha256=%s bytes=%d" % (
            "OK" if back == blob else "FAIL", path.relative_to(ROOT).as_posix(),
            hashlib.sha256(back).hexdigest()[:16], len(back)))
        if back != blob:
            return 1
    if idn != total:
        print("CENSUS-FAIL: 恒等式不成立（分母可疑）")
        return 1
    if blind:
        print("CENSUS-UNVERIFIED: %d 条取不到证据面 ⇒ 不得据本普查做并行决策：%s"
              % (len(blind), ",".join(blind)))
        return 2
    print("CENSUS-PASS: 证据面 %d/%d 全覆盖，分桶恒等式成立" % (total - len(blind), total))
    return 0


if __name__ == "__main__":
    sys.exit(main())
