# -*- coding: utf-8 -*-
r"""perf_ramp_delta_check.py — 阶梯并发读数的「漂移尺」（r98 立）。

为什么现在才立（一手代价，不是假想需求）
------------------------------------------------
r96 立了阶梯并发（`perf_baseline_check.py --ramp 8,16,32,64`），跑出
2368.0 / 2041.8 / 2609.9 / 2630.6 rps @ 并发 8/16/32/64（health 面，p95 4.8→16.1ms），
并在报告里写下「8→64 路无塌方点」。**但那条曲线当时只有一个点。**
「无塌方点」是对**这一轮**的形状陈述 —— 它没有上一轮可比，因此：
  ① 「漂移」这个词在 r96 之后**无人量过**（`grep 漂移` 只在报告散文里，不在判据里）；
  ② 地板（`rps ≥ 50`、`p95 ≤ 400ms`）只防塌方，**不防悄悄劣化** ——
     rps 从 2368 掉到 900 仍然全在地板之上，判据一声不响。
这与本仓 `ledger_age` 立的理由同族：**记了读数却从不问它相对上一轮变了什么**，
于是「上一轮的绿」被继承成「这一轮的绿」。

这把尺说什么、不说什么
------------------------------------------------
它只比**同一档位**的相邻两份台账，算相对变化并对照一个允许漂移的阈值。
它**不**重跑性能测试（取数面是两份落盘 JSON，零网络零浏览器）；
它**不**判断「这个 rps 好不好」（绝对地板归 `perf_baseline_check`）——
两把尺各管一面，同一事实只许一处判。

为什么「档位不同就不比」是硬要求
------------------------------------------------
r96 的 8 档与本轮若用了别的档位集，逐档配对会拿 8 比 16。
那不是漂移，那是换了尺。⇒ 档集不同 ⇒ 逐档记 `NA(tier-missing)`，
**不缩档、不补插、不取平均**，且 NA 会印在门面行上。

为什么不许由「上一份 = 目录里最新的那份」决定
------------------------------------------------
那正是 `ledger_age` 实测踩过的：mtime 与文件名日期能不一致，取数源一换红绿翻面。
本件按**文件名里的日期**取「上一轮」，取不到 ⇒ rc=2 UNVERIFIED，**不判绿也不判红**。

用法
------------------------------------------------
    python _test/perf_ramp_delta_check.py                       # 默认比「上一份 vs 本份」
    python _test/perf_ramp_delta_check.py --json <落盘路径>      # 本轮读数落盘
    python _test/perf_ramp_delta_check.py --tol-pct 30          # 演习口：收紧阈值必须判红
    python _test/perf_ramp_delta_check.py --selftest            # 正例/反例/变异/NA/恒等式/盲区
退出码：0=各腿绿  1=漂移超阈值  2=UNVERIFIED（取不到两份可比台账 / 档集无可比档）
"""
import argparse
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "交付物" / "对标数据"
SELF_NAMES = {"perf_ramp_delta_check.py"}
DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
FACES = ("health", "emotion")          # perf_baseline 的 ramp 面就这两条
# 相对漂移上限。**r99 由 40% 改 50%，并把理由换成当轮实测**：
# 原理由（"r96 实测同机同档波动 2368→2041.8 = −13.8%"）量错了对象 —— 那两个数是**同一次**
# 运行的 8 档与 16 档，本尺只比同一档位，永远不会拿 8 比 16，所以它不是"档内噪声"的读数。
# r99 同机静置实测（work=4 连测 5 轮）档内带宽 13.5%~255.8% ⇒ 40% 阈值在仪器噪声带**里面**，
# 天天会被自己踩穿（同日两份 30 分钟间隔实测最坏 −40.1%，当场判红一次）。
# 同轮把采集口径提到 work=32 后带宽收到 ≤38.4% ⇒ 50% 有 11.6 个百分点余量。
# 检测限请如实读：**本尺只能检出 ≥50% 的档内回退**，30% 量级的回退检不出；
# 想让它看得更细，正解是继续提仪器精度（每档重复取中位数），不是把阈值调小假装看得见。
DEFAULT_TOL_PCT = 50.0
FOLD_LIMIT = 110


def is_ramp_ledger(p):
    """这个 `perf-ramp-*.json` 到底是不是阶梯台账：**有 `ramp` 键且它是个非空 dict** 才算。

    一手代价（r100）：本轮把噪声汇总件命名成 `perf-ramp-noise-2026-10-08.json`，正好撞上这个 glob
    ⇒ `ledgers()` 把它当成"最新一份台账"，本尺当场 `rc=2 UNVERIFIED`——**一件新写的产物变成了另一把尺
    的分母**（在册同族：清理通道自己造分母 / 台账里带引号的路径被形状取数读成缺失）。
    修法不是把产物改名就完事（下次还会有人撞），而是**让尺自己认得出不是台账**：
      · `ramp` 键存在且是 dict ⇒ 是台账（哪怕解析不出读数，那是坏件，必须走 UNVERIFIED，不许静默跳过）；
      · 读不动 / 不是 dict ⇒ 也**算台账**（fail-closed，交给解析侧报未验）；
      · 有 `ramp` 键但值是 null（生产者明写"这一轮没跑阶梯"）⇒ 不是阶梯台账，点名跳过，不占分母。
    """
    try:
        d = json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:                                      # noqa: BLE001
        return True
    return isinstance(d, dict) and isinstance(d.get("ramp"), dict) and bool(d.get("ramp"))


def foreign_files(data_dir=None):
    """同名前缀、但不是阶梯台账的件（**出声点名**，禁静默吞）。"""
    base = Path(data_dir) if data_dir else DATA
    return [p.name for p in sorted(base.glob("perf-ramp-*.json"))
            if p.name not in SELF_NAMES and not is_ramp_ledger(p)]


def ledgers(data_dir=None):
    """全部 ramp 台账（按**文件名日期**排序）。刻意不按 mtime —— 见文件头。

    `data_dir` 只给验牙用：变异注入必须打在临时副本上，不许动权威台账
    （r98 一手代价 = 变异脚本改了 `perf-ramp-2026-10-05.json` 的 mtime，字节虽还原，
    而那一刻「还原是否真发生」只能靠另取的基准字节证明）。
    r100：非台账的同前缀件在此摘出去（判定与点名各一处，见 `is_ramp_ledger` / `foreign_files`）。
    """
    base = Path(data_dir) if data_dir else DATA
    out = []
    for p in sorted(base.glob("perf-ramp-*.json")):
        if p.name in SELF_NAMES or not is_ramp_ledger(p):
            continue
        m = DATE_RE.search(p.stem)
        out.append((m.group(1) if m else "", p))
    out.sort(key=lambda x: (x[0], x[1].name))
    return out


def parse_ramp(d):
    """台账 dict → {tier: {face: {rps, p95_ms, llm_used}}} 或 None（不可用）。

    纯函数且**唯一实现**：第一版让 `load_ramp(路径)` 与 `load_ramp_of(dict)` 各抄一份，
    selftest 走的是后者、普查走的是前者 ⇒ 改一份另一份不动 = 装饰腿的近亲。"""
    res = (d.get("ramp") or {}).get("result")
    if not isinstance(res, dict) or not res:
        return None
    tiers = {}
    for tk, tv in res.items():
        try:
            tier = int(tk)
        except (TypeError, ValueError):
            continue
        row = {}
        for face in FACES:
            fv = tv.get(face) if isinstance(tv, dict) else None
            if not isinstance(fv, dict):
                continue
            rps, p95 = fv.get("rps"), fv.get("p95_ms")
            if not isinstance(rps, (int, float)) or isinstance(rps, bool) \
                    or not isinstance(p95, (int, float)) or isinstance(p95, bool):
                continue
            # llm_used 只在该面声明了才记；缺字段不等于 False（那是「没测」不是「没用到」）
            row[face] = {"rps": float(rps), "p95_ms": float(p95), "llm_used": fv.get("llm_used"),
                         # r100：仪器自报的本轮档内带宽（5 次 reps 的 max/min）。缺键 ⇒ None，
                         # 不得折成 0.0（那会把"没记"读成"很安静"）。
                         "band_rps": (float(fv["band_rps"])
                                      if isinstance(fv.get("band_rps"), (int, float))
                                      and not isinstance(fv.get("band_rps"), bool) else None)}
        if row:
            tiers[tier] = row
    return tiers or None


def load_ramp(p):
    """单份台账文件 → 解析结果或 None（读不到/格式不对都不折 0）。"""
    try:
        return parse_ramp(json.loads(p.read_text(encoding="utf-8")))
    except Exception:                                      # noqa: BLE001
        return None


def meta_of(d):
    """台账口径：每线程请求数 + 档集 + 每档重复次数/丢弃的冷启次数。
    r99 起前两项决定「有没有可比读数」；r100 起后两项同理——单次读数与中位数读数不是同一个量
    （后者已经把档内长尾折掉了），拿 1 次去比 5 次会造出既有读数又判红的**假证据**。
    旧台账没有这两个键 ⇒ 读出 None ⇒ 判口径差，不冒充"没差"。"""
    ramp = d.get("ramp") or {}
    return {"work": ramp.get("work_per_thread"), "tiers": ramp.get("tiers") or [],
            "reps": ramp.get("reps_per_tier"), "warmup": ramp.get("warmup_per_tier")}


def load_meta(p):
    try:
        return meta_of(json.loads(p.read_text(encoding="utf-8")))
    except Exception:                                      # noqa: BLE001
        return {"work": None, "tiers": [], "reps": None, "warmup": None}


def caliber_gaps(pm, cm):
    """口径差清单：空 = 可比。

    为什么必须有这条（r99）：`RAMP_WORK` 从 4 提到 32 之后，目录里必然同时存在
    两种口径的台账。档集相同但每线程请求数不同 ⇒ 两份 rps 不是同一个量，
    拿它们算"漂移"会造出一个既有读数又判了红的**假证据**。
    r100 再加两维（reps / warmup）：中位数口径与单次口径、丢冷启与不丢，都会改变同一格的含义。
    """
    out = []
    if pm.get("work") != cm.get("work"):
        out.append("work_per_thread %s→%s" % (pm.get("work"), cm.get("work")))
    if sorted(pm.get("tiers") or []) != sorted(cm.get("tiers") or []):
        out.append("tiers %s→%s" % (pm.get("tiers"), cm.get("tiers")))
    if pm.get("reps") != cm.get("reps"):
        out.append("reps_per_tier %s→%s" % (pm.get("reps"), cm.get("reps")))
    if pm.get("warmup") != cm.get("warmup"):
        out.append("warmup_per_tier %s→%s" % (pm.get("warmup"), cm.get("warmup")))
    return out


def compare(prev_tiers, cur_tiers, tol_pct):
    """逐档逐面算相对漂移。返回 (读数行, 红因列表, NA 列表)。纯函数，selftest 直接调。"""
    rows, red, nas = [], [], []
    for tier in sorted(set(prev_tiers) | set(cur_tiers)):
        if tier not in prev_tiers or tier not in cur_tiers:
            nas.append("tier%d" % tier)
            continue
        for face in FACES:
            if face not in prev_tiers[tier] or face not in cur_tiers[tier]:
                nas.append("t%d/%s" % (tier, face))
                continue
            a, b = prev_tiers[tier][face], cur_tiers[tier][face]
            base = a["rps"] or 1e-9
            dpct = (b["rps"] - a["rps"]) / base * 100.0
            ppct = (b["p95_ms"] - a["p95_ms"]) / (a["p95_ms"] or 1e-9) * 100.0
            rows.append({"tier": tier, "face": face, "prev_rps": a["rps"], "cur_rps": b["rps"],
                         "prev_p95": a["p95_ms"], "cur_p95": b["p95_ms"],
                         "rps_dpct": round(dpct, 1), "p95_dpct": round(ppct, 1),
                         "prev_llm": a.get("llm_used"), "cur_llm": b.get("llm_used"),
                         "band": b.get("band_rps")})
            # rps 掉超过阈值 = 劣化；p95 涨超过阈值 = 劣化。**只劣化判红**，改善不判红
            # （否则一台更快的机器会让这把尺天天红 —— 与「指标变好」无关的判红是噪声源）。
            if dpct < -tol_pct:
                red.append("t%d/%s rps %+.1f%% < -%.0f%%" % (tier, face, dpct, tol_pct))
            if ppct > tol_pct:
                red.append("t%d/%s p95 %+.1f%% > +%.0f%%" % (tier, face, ppct, tol_pct))
    return rows, red, nas


def noise_floor(rows, tol_pct):
    """仪器自报的「这一档今天分辨不出来」清单：本轮档内带宽 ≥ 阈值的档面。

    立据（r100 静置 5 轮、每轮 30s 间隔实测）：t8/t16 跨轮带宽 50.6%~68.1%，t32/t64 只有
    8.0%~16.6%；而**每档跑 5 次取中位数并没有把跨轮噪声压下来**——同一轮里的 5 次共享同一台
    机器的状态，相关性压不掉，压得掉的只有采样次数。⇒ 检测限现在还是 ±50%，不能宣称下压。
    处置按在册规矩「两侧区间重叠 ⇒ 改机制不改参数」：阈值一字不动，红也照判（不 loosening），
    但把这些档面**点名成噪声底**，好让下一轮不会拿一档的单次红去当"回归已证"。
    `band` 缺失（旧台账 / 未记带宽）⇒ 不计入，也不得折成 0 冒充安静。
    """
    return [("t%d/%s" % (r["tier"], r["face"]), r["band"]) for r in rows
            if isinstance(r.get("band"), (int, float)) and r["band"] >= tol_pct]


def face_line(prev_name, cur_name, rows, red, nas, tol):
    """门面行（≤110 字符）。棘轮数 = 参与比较的档×面数，必须印出来：
    否则「0 红」与「一档都没比成」在受理面上无法区分 —— 空比较恒绿是本仓在册最贵的一族。

    台账名只取**日期段**（`perf-ramp-2026-10-05.json` → `10-05`）：全名 22 字符会把
    门面行顶到 112 > 截断线 110 ⇒ 受理面上「最差档」正好被切掉。日期已足够定位，
    全名在 `--json` 落盘件与明细行里都在。"""
    def brief(n):
        m = DATE_RE.search(n or "")
        return m.group(1)[5:] if m else "?"
    line = ("PERF-RAMP-DELTA-%s: %s→%s 比%d档面 阈值±%.0f%% 红%d"
            % ("FAIL" if red else "PASS", brief(prev_name), brief(cur_name),
               len(rows), tol, len(red)))
    if nas:
        line += " NA%d" % len(nas)
    nf = noise_floor(rows, tol)
    if nf:
        line += " 噪声档=%d" % len(nf)
    if rows:
        worst = min(rows, key=lambda r: r["rps_dpct"])
        line += " 最差t%d/%s rps%+.0f%%" % (worst["tier"], worst["face"], worst["rps_dpct"])
    return line


def _st_noise_floor(expect):
    """r100 噪声底桩（抽成模块级只为过 LOC 门 ≤150 行/函数，纯搬家）。
    仪器自报「这档今天量不出来」这件事必须双向自证：该点名的点名、不该计入的不许造。"""
    def rrow(t, f, band):
        return {"tier": t, "face": f, "band": band, "rps_dpct": -99.0}
    rr = [rrow(8, "health", 60.0), rrow(8, "emotion", 10.0), rrow(16, "health", None),
          rrow(16, "emotion", 50.0), rrow(32, "health", 49.9)]
    nf = noise_floor(rr, 50.0)
    expect("噪声底：band 60% ≥ tol ⇒ 必须点名", ("t8/health", 60.0) in nf)
    expect("噪声底：band 恰好等于 tol ⇒ 按 ≥ 计入（边界不放过）", ("t16/emotion", 50.0) in nf)
    expect("噪声底：band 49.9% < tol ⇒ 不得计入（不得把安静档说成量不出）",
           all(n != "t32/health" for n, _ in nf))
    expect("噪声底：band=None（旧台账没记带宽）⇒ 不计入也不折成 0 冒充安静",
           all(n != "t16/health" for n, _ in nf))
    expect("噪声底：门面行印 噪声档=N（聚合面只留一行，计数必须挤进同一行）",
           "噪声档=2" in face_line("perf-ramp-2026-10-08e.json", "perf-ramp-2026-10-08f.json",
                                   rr, [], [], 50.0))
    expect("噪声底：不改变判红语义（红照判，rc 不因它而放宽）",
           len(face_line("a.json", "b.json", rr, ["t8/health rps -60.0% < -50%"], [], 50.0)
                   .split("红")[1][:1]) == 1)
    expect("接线：parse_ramp 认台账里的 band_rps 键（不是靠 compare 现造）",
           parse_ramp({"ramp": {"result": {"8": {"health": {"rps": 100.0, "p95_ms": 5.0,
                                                     "band_rps": 61.5}}}}})[8]["health"]["band_rps"] == 61.5)


def _st_denominator(expect):
    """r100 分母自卫桩（同前缀但不是阶梯台账的件）：抽出去必须**出声点名**，坏件必须 fail-closed。"""
    tmpd = Path(tempfile.mkdtemp(prefix="xinyu_ramp_face_"))
    try:
        good = {"reps_per_tier": 5, "ramp": {"tiers": [8], "work_per_thread": 32,
                                            "result": {"8": {"state": "ok"}}}}
        (tmpd / "perf-ramp-2026-10-08-a.json").write_text(json.dumps(good), encoding="utf-8")
        (tmpd / "perf-ramp-2026-10-08-b.json").write_text(json.dumps(good), encoding="utf-8")
        (tmpd / "perf-ramp-noise-2026-10-08.json").write_text(
            json.dumps({"schema": "xinyu-ramp-noise-v1", "rows": [1, 2]}), encoding="utf-8")
        (tmpd / "perf-ramp-2026-10-08-n.json").write_text(
            json.dumps({"base": "x", "ramp": None}), encoding="utf-8")
        (tmpd / "perf-ramp-2026-10-08-bad.json").write_text("{not json", encoding="utf-8")
        (tmpd / "unrelated-2026-10-08.json").write_text(json.dumps({"x": 1}), encoding="utf-8")
        names = [p.name for _, p in ledgers(tmpd)]
        expect("分母自卫：分母 = 2 份真台账 + 1 份坏件（坏件不算『没这个文件』）",
               names == ["perf-ramp-2026-10-08-a.json", "perf-ramp-2026-10-08-b.json",
                         "perf-ramp-2026-10-08-bad.json"])
        expect("分母自卫：噪声汇总件（无 ramp 键）不算台账",
               "perf-ramp-noise-2026-10-08.json" not in names)
        expect("分母自卫：ramp=null（生产者明写没跑阶梯）不算台账",
               "perf-ramp-2026-10-08-n.json" not in names)
        expect("分母自卫：坏 JSON **仍算台账**（fail-closed，不许静默跳过坏件）",
               "perf-ramp-2026-10-08-bad.json" in names)
        expect("分母自卫：被摘出去的件必须出声点名（foreign_files 列前缀同族非台账件）",
               foreign_files(tmpd) == ["perf-ramp-2026-10-08-n.json",
                                       "perf-ramp-noise-2026-10-08.json"])
        expect("分母自卫：不同前缀的件根本不进视野（glob 没匹配 ≠ 我判过它不是台账）",
               "unrelated-2026-10-08.json" not in foreign_files(tmpd))
    finally:
        shutil.rmtree(str(tmpd), ignore_errors=True)


def selftest():
    """正例 / 三种「不得判绿也不得判红」反例 / 变异 / NA / 空比较 / 门面行封口。"""
    bad, n = [], 0

    def expect(label, cond):
        nonlocal n
        n += 1
        if not cond:
            bad.append(label)

    prev = {8: {"health": {"rps": 2368.0, "p95_ms": 4.8}},
            64: {"health": {"rps": 2630.6, "p95_ms": 16.1}}}
    # 夹具数字必须**真的**落在声称的区间里：r96 实测同档重复测量的波动本身就有 ±2%，
    # 所以正例取 +1.9% / −1.9%（不是随手写的 2481 与 2630）。
    cur = {8: {"health": {"rps": 2413.0, "p95_ms": 4.9}},
           64: {"health": {"rps": 2580.0, "p95_ms": 16.4}}}

    r0, red0, nas0 = compare(prev, cur, 40.0)
    # 夹具只填了 health 面 ⇒ emotion 面记 NA 是**正确**行为（缺面不等于 0，也不等于漂移）。
    # 所以正例的判据是「零红 + 每档比成 1 面 + NA 数 == 缺的面数」，不是「零 NA」。
    expect("正例 同一档 ±2%% 内 ⇒ 零红", not red0)
    expect("正例 两档漂移绝对值都 <2%%（否则下面三条反例在打不成立的靶子）",
           all(abs(x["rps_dpct"]) < 2.0 for x in r0))
    expect("正例 缺面记 NA 而非折 0（NA 数 == 档数×缺面数）",
           len(nas0) == 2 and all(x.endswith("/emotion") for x in nas0))

    # 反例 A：rps 掉一半 ⇒ 必须判红（这是本尺存在的理由：地板管不住悄悄劣化）
    _r, redA, _n = compare(prev, {8: {"health": {"rps": 1000.0, "p95_ms": 5.0}},
                                  64: cur[64]}, 40.0)
    expect("反例 rps 掉 57%% ⇒ 必须判红并点名 t8/health", bool(redA)
           and any("t8/health" in x for x in redA))
    # 反例 B：p95 涨一倍 ⇒ 必须判红（吞吐没掉但延迟劣化，同样是劣化）
    _r, redB, _n = compare(prev, {8: {"health": {"rps": 2368.0, "p95_ms": 20.0}},
                                  64: cur[64]}, 40.0)
    expect("反例 p95 涨 317%% ⇒ 必须判红", bool(redB)
           and any("p95" in x for x in redB))
    # 反例 C：**档集不同** ⇒ 逐档 NA，不缩档不补插更不判红
    _r, redC, nasC = compare(prev, {16: {"health": {"rps": 2041.8, "p95_ms": 10.0}}}, 40.0)
    expect("反例 档集完全不相交 ⇒ 零红 + 三个 NA（不得拿 8 比 16）",
           not redC and len(nasC) == 3)
    # 反例 D：空比较（两份都没可比档）⇒ 门面行必须暴露「比了 0 档面」
    empty = face_line("a", "b", [], [], [], 40.0)
    expect("反例 空比较 ⇒ 门面行明写「比0档面」（空比较恒绿是本仓在册最贵的一族）",
           "比0档面" in empty)

    # 设计腿（不是变异腿）：**改善不判红**是本尺的显式设计 —— 一台更快的机器
    # 不该让这把尺变红（与「指标变好」无关的判红是噪声源）。
    # 这里把它钉住，防止后人手滑写成「绝对值超阈值就红」。
    better = {8: {"health": {"rps": 2368.0 * 1.9, "p95_ms": 4.8}},
              64: {"health": {"rps": 2630.6, "p95_ms": 16.1}}}
    _r, redD, _n = compare(prev, better, 40.0)
    expect("设计腿 rps 涨 90%% 属改善 ⇒ 必须**不**判红（绝对值判红是噪声源）", not redD)
    # 变异腿：阈值从 40% 收紧到 1% ⇒ 同一个 **−1.9%**（t64）必须翻红，证明阈值真在参与判定。
    # 拿 +90% 那侧当变异腿是打错靶：改善在任何阈值下都不判红（上一条腿刚把它钉住）。
    _r, red0b, _n = compare(prev, cur, 40.0)
    _r, redE, _n = compare(prev, cur, 1.0)
    expect("对照 阈值 40% 时 t64 的 −1.9%% 不判红（否则变异腿无输入）", not red0b)
    expect("变异体 阈值收紧到 1% ⇒ t64 的 −1.9%% 必须翻红（阈值不是摆设）",
           any("t64/health rps" in x for x in redE))

    # 恒等式：rps_dpct 的量级必须与实算一致（不靠打印断言）
    row = [r for r in r0 if r["tier"] == 8][0]
    expect("恒等式 dpct = (cur-prev)/prev×100（取整误差 ≤0.1）",
           abs(row["rps_dpct"] - (2413.0 - 2368.0) / 2368.0 * 100.0) <= 0.1)

    # 不可测面：台账缺该面 / rps 非数值 ⇒ 该档面记 NA 而不是当 0（折 0 会造出假劣化）
    junk = load_ramp_of({"ramp": {"result": {"8": {"health": {"rps": "n/a", "p95_ms": 5.0}}}}})
    expect("盲区腿 rps 非数值 ⇒ 该档面不可用（返回 None ⇒ UNVERIFIED，不得折 0）",
           junk is None)

    line = face_line("perf-ramp-2026-10-05.json", "perf-ramp-2026-10-12.json", r0, red0, nas0, 40.0)
    expect("门面行样例 %d 字符 ≤ 截断线 %d" % (len(line), FOLD_LIMIT), len(line) <= FOLD_LIMIT)
    expect("门面行必须自带阈值与棘轮数", ("阈值" in line) and ("比%d档面" % len(r0)) in line)

    # 取数目录腿（r99 加 --dir 的接线回执）：验牙必须在临时副本上打，禁动权威台账。
    # 同日期两条（`-10-07.json` 与 `-10-07b.json`）按名序排，b 落最后一位 = 本份，
    # 这是同日噪底测量（两份间隔 ≥30min）能被本尺读成「相邻两份」的前提。
    tmp = tempfile.mkdtemp(prefix="r99-ramp-")
    try:
        for nm in ("perf-ramp-2026-10-07.json", "perf-ramp-2026-10-07b.json"):
            Path(tmp, nm).write_text(json.dumps(
                {"ramp": {"result": {"8": {"health": {"rps": 100.0, "p95_ms": 1.0}}}}}),
                encoding="utf-8")
        books = ledgers(tmp)
        expect("--dir 真改变取数面 ⇒ 临时目录两份都读到", len(books) == 2)
        expect("--dir 下同日期按名序，b 那份是「本份」",
               len(books) == 2 and books[-1][1].name.endswith("07b.json"))
        expect("不传 --dir 时取数面仍是权威目录（临时件不得混进默认面）",
               all("r99-ramp" not in str(p) for _d, p in ledgers()))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # 口径腿（r99）：work 或档集不同 ⇒ 不可比。禁止把两份不同口径的 rps 算成"漂移"，
    # 那会产出一条**既有读数又判了红的假证据**（比 UNVERIFIED 更坏）。
    m4 = {"work": 4, "tiers": [8, 16, 32, 64]}
    m32 = {"work": 32, "tiers": [8, 16, 32, 64]}
    expect("口径 同 work 同档 ⇒ 零差（可比）", caliber_gaps(m4, dict(m4)) == [])
    expect("口径 work 4 vs 32 ⇒ 必须报差（旧件与新件不得互比）", bool(caliber_gaps(m4, m32)))
    expect("口径 档集不同 ⇒ 必须报差", bool(caliber_gaps(m4, {"work": 4, "tiers": [8, 16]})))
    expect("口径 work 取不到（None）vs 32 ⇒ 报差，不得把缺字段当相等",
           bool(caliber_gaps({"work": None, "tiers": []}, m32)))
    expect("口径 meta_of 认台账里的 work_per_thread 键（不是猜默认值）",
           meta_of({"ramp": {"work_per_thread": 32, "tiers": [8]}})["work"] == 32)
    # r100 两维新口径：单次 vs 中位数、丢不丢冷启，都改变同一格的含义 ⇒ 必须拒比。
    m5 = {"work": 32, "tiers": [8, 16, 32, 64], "reps": 5, "warmup": 1}
    expect("口径 reps 同为 5 ⇒ 零差（同口径可比）", caliber_gaps(m5, dict(m5)) == [])
    expect("口径 旧台账无 reps 键（读出 None）vs 新台账 5 ⇒ 必须报差",
           any("reps_per_tier" in x for x in caliber_gaps(
               {"work": 32, "tiers": [8, 16, 32, 64], "reps": None, "warmup": None}, m5)))
    expect("口径 warmup 1 vs 0 ⇒ 必须报差（丢过冷启的读数与没丢的不是同一个量）",
           any("warmup_per_tier" in x for x in caliber_gaps(
               dict(m5, warmup=0), m5)))
    expect("口径 meta_of 真从台账里读 reps_per_tier/warmup_per_tier（不是默认值兜底）",
           meta_of({"ramp": {"work_per_thread": 32, "tiers": [8],
                             "reps_per_tier": 5, "warmup_per_tier": 1}})["reps"] == 5
           and meta_of({"ramp": {"reps_per_tier": 5, "warmup_per_tier": 1}})["warmup"] == 1)
    expect("口径 load_meta 读坏件 ⇒ 四键全空而非静默可比",
           load_meta(Path(__file__)) == {"work": None, "tiers": [], "reps": None, "warmup": None})
    _st_noise_floor(expect)
    _st_denominator(expect)

    for x in bad:
        print("  不符: " + x)
    print("PERF-RAMP-DELTA-SELFTEST-%s（%d/%d 条）" % ("FAIL" if bad else "PASS", n - len(bad), n))
    return 1 if bad else 0


def load_ramp_of(d):
    """把一段 dict 当台账走一遍校验（selftest 用，避免造临时文件）。"""
    return parse_ramp(d)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tol-pct", type=float, default=DEFAULT_TOL_PCT)
    ap.add_argument("--dir", default="",
                    help="台账目录（默认 交付物/对标数据）。验牙/噪底测量指临时副本，禁打权威台账")
    ap.add_argument("--json", default="", help="本轮读数落盘路径（由 perf_baseline_check --ramp 写）")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()

    if a.json:
        Path(a.json).write_bytes(Path(a.json).read_bytes())   # 幂等落盘校验：路径必须可读
    books = ledgers(a.dir or None)
    foreign = foreign_files(a.dir or None)
    if foreign:
        print("  - 同前缀非台账（已摘出分母，不静默吞）：%s" % ",".join(foreign[:4]))
    if len(books) < 2:
        print("PERF-RAMP-DELTA-UNVERIFIED: 可比台账 %d 份（需 ≥2：上一份 vs 本份）"
              "⇒ 没有「上一轮」就没有漂移可言，既不判绿也不判红" % len(books))
        return 2
    (pd_, prev_p), (cd_, cur_p) = books[-2], books[-1]
    prev, cur = load_ramp(prev_p), load_ramp(cur_p)
    if prev is None or cur is None:
        print("PERF-RAMP-DELTA-UNVERIFIED: %s 不可用（%s）"
              % ("上一份" if prev is None else "本份", prev_p.name if prev is None else cur_p.name))
        return 2
    gaps = caliber_gaps(load_meta(prev_p), load_meta(cur_p))
    if gaps:
        print("PERF-RAMP-DELTA-UNVERIFIED: 两份台账口径不同（%s）⇒ 不缩档不补插不折算，"
              "整尺既不判绿也不判红（r99 把采集口径 work 从 4 提到 32，旧件与新件天然不可比）"
              % "；".join(gaps))
        return 2
    rows, red, nas = compare(prev, cur, a.tol_pct)
    if not rows:
        print("PERF-RAMP-DELTA-UNVERIFIED: 两份台账无可比档面（NA=%s）"
              "⇒ 档集不相交是「没比成」不是「没漂移」" % ",".join(nas))
        return 2
    line = face_line(prev_p.name, cur_p.name, rows, red, nas, a.tol_pct)
    if len(line) > FOLD_LIMIT:
        print("PERF-RAMP-DELTA-NOTE: 门面行 %d 字符 > 截断线 %d ⇒ 尾部读数在受理面上不存在"
              % (len(line), FOLD_LIMIT))
    print(line)
    for r in rows:
        print("  - t%d/%s rps %.1f→%.1f（%+.1f%%）p95 %.1f→%.1f（%+.1f%%）"
              % (r["tier"], r["face"], r["prev_rps"], r["cur_rps"], r["rps_dpct"],
                 r["prev_p95"], r["cur_p95"], r["p95_dpct"]))
    # r100 噪声底：仪器自报「本轮这一档的档内带宽 ≥ 阈值」⇒ 该档的单次红不足以证明回归。
    # 红照判、rc 一字不改（不 loosening）；只是把"哪几档今天量不出来"变成机器可见的读数，
    # 免得下一轮拿 t8 的一次 −60% 当成"吞吐塌了"去改没坏的产品代码。
    for name, band in noise_floor(rows, a.tol_pct):
        print("  - 噪声底 %s 本轮档内带宽 %.1f%% ≥ 阈值 %.0f%% ⇒ 该档漂移不具因果判定力（须复跑）"
              % (name, band, a.tol_pct))
    # llm_used 是这套读数的诚实性前提：r96 的每档都断言了它为 False。
    # 哪一档它变成 True，下一轮的 rps 就掺了上游延迟，这份漂移读数对该档不可用。
    tainted = ["t%d/%s" % (r["tier"], r["face"]) for r in rows if r.get("cur_llm") is True]
    if tainted:
        print("  - 注意 本轮 llm_used=True 于 " + ",".join(tainted) + " ⇒ 该档 rps 混入上游延迟，漂移读数仅作参考")
    for x in red:
        print("  - 红因=" + x)
    if nas:
        print("  - NA(不可比档面，不缩档不补插)=" + ",".join(nas))
    return 1 if red else 0


if __name__ == "__main__":
    sys.exit(main())
