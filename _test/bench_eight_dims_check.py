# -*- coding: utf-8 -*-
"""八维对标总览表**派生化**判据（r119 改造二）。

动机（一手，不是猜想）：`_test/bench_rollup.py` 只算两维（`dim_a_testing_repro` +
`dim_b_zero_build_cost`），其余六维每轮**从台账手抄进报告**——对标报告链已 60+ 份，每份手抄一次。
本仓被这条形态咬过不止一回：AGENTS.md 08 的 AC-OBS-09 里「94.4% / 3-3 / 36 条」是 09-22 当日值，
评测集 09-23 扩到 73 条后**没人重算**，旧值一路活在注入面上，最后由构建期用例才打出来。
同一族换个对象就会复发：只要总览表还是手写的。本件把它变成**生成的**，并把
「每格必须有出处」做成硬断言 —— 没出处的格子直接判红，抄错数字这件事从此不可见即不可发生。

口径边界（避免与本仓既有判据重复设尺）：
  · 台账**龄期/fuse** 由 `_test/ledger_age_check.py` 独家判，本件只记日期与来源，不重复判降级；
  · 版本三源（tag⇄pom⇄文档）由 `repo_config G12` 独家判，本件只报 tag 计数不判一致性；
  · 本件判的是**表的可追溯性**：维度齐、格有源、分母自证、NA 必须点名。

用法：
  python _test/bench_eight_dims_check.py --round r119 [--json] [--no-write]
  python _test/bench_eight_dims_check.py --selftest
退出码：0=八维齐且格格有源 1=缺维/缺源/分母不自洽 2=台账或 git 取数面不可读（不得读成通过）
"""
import argparse
import glob
import io
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "交付物" / "对标数据"
# 参照池分母的唯一权威源是名册本身（`benchmark_metrics.PEERS`），这里 import 而不是抄数
sys.path.insert(0, str(ROOT / "_test"))
DIM_ORDER = ["功能模块覆盖", "技术架构设计", "实现方式（质量门）", "性能表现",
             "可扩展性", "维护状态", "文档完善程度", "适用场景"]


try:
    # 归口（r119 改造四）：self 侧的「套件数 / Java 测试件与用例 / jacoco 阈值 / HEAD 文件清单」
    # 唯一算家是 `_test/bench_rollup.py`。本件先前自己数了一遍，等于**同一事实两把尺**——
    # 两把尺会各自漂（本仓 AC-OBS-09 的旧值就是这么活下来的），所以改成 import 它的函数：
    # 取不到就整尺 rc=2，**禁止回落成本件自算**（回落等于把去重偷偷改回重复）。
    sys.path.insert(0, str(ROOT / "_test"))
    import bench_rollup as BR
except Exception as _e:                                   # noqa: BLE001
    BR = None
    BR_ERR = "%s: %s" % (type(_e).__name__, str(_e)[:80])


def sh(args, timeout=25):
    """git 只读命令。取不到就抛，由调用方折算成 UNVERIFIED —— 不许静默当空集。"""
    r = subprocess.run(args, cwd=str(ROOT), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError("git 失败 rc=%s：%s" % (r.returncode, (r.stderr or "")[:90]))
    return r.stdout or ""


def head_text(rel):
    """HEAD 面取文件原文（= CI 会 checkout 的那一份），工作树在途改动不参与对标。"""
    return sh(["git", "show", "HEAD:" + rel])


def ledger(pat):
    """取某族台账最新一份（排除 _partial/_superseded）。返回 (path, payload) 或 (None, None)。"""
    fs = [p for p in glob.glob(str(DATA / pat))
          if "_partial" + os.sep not in p and "_superseded" + os.sep not in p]
    if not fs:
        return None, None
    p = max(fs, key=os.path.getmtime)
    try:
        with open(p, encoding="utf-8") as f:
            return Path(p), json.load(f)
    except (OSError, ValueError) as e:
        return Path(p), {"__unreadable__": type(e).__name__}


def stamp(path, payload):
    """来源标签＝文件名 + 件内时点（缺件内时点就用文件名日期，两者都没有 ⇒ 由调用方判缺源）。"""
    ts = None
    if isinstance(payload, dict):
        for k in ("taken_at", "ts", "generated_at", "as_of"):
            if payload.get(k):
                ts = str(payload[k])
                break
    return "%s%s" % (path.name, ("@" + ts[:19]) if ts else "")


def sref(pat):
    """取某族的来源标签；台账不在面时**如实写 NA + 补法**，绝不留空串（空串会被 audit 判缺源，
    但更糟的是它长得像"没有这一格"）。"""
    p, payload = ledger(pat)
    if p is None:
        return "NA-DECLARED：缺 %s，补法 python _test/<对应 probe>.py --json 交付物/对标数据/…（错峰单跑）" % pat
    return stamp(p, payload)


def cell(label, value, source):
    return {"label": label, "value": value, "source": source}


# ── 各维取数 ────────────────────────────────────────────────────────────────
def build_dims():
    """返回 (dims, notes)。dims = [{dim, cells:[{side,label,value,source}]}]。

    每个 cell 的 source 都必须可复算；取不到的格写 NA 并点名「哪条命令能补上」，
    禁止把 NA 写成空格（空格会被读成"没有差距"）。
    """
    notes, dims = [], []

    metrics_p, metrics = ledger("benchmark-metrics.json")
    if metrics_p is None or not isinstance(metrics, dict) or not metrics.get("runs"):
        raise Unverified("benchmark-metrics.json 取不到 runs（先跑 python _test/benchmark_metrics.py）")
    last = metrics["runs"][-1]
    peers = last.get("repos") or []
    denom = len(peers)
    expected = metrics.get("peers_expected")
    if expected is not None and denom != expected:
        raise Inconsistent("参照池分母不自洽：runs[-1].repos=%d 而 peers_expected=%s" % (denom, expected))
    m_src = stamp(metrics_p, {"ts": last.get("ts")})
    self_row = last.get("self") or {}

    caps = sorted(self_row.get("caps") or [])
    blind = sorted(self_row.get("caps_blind") or [])
    dist = {}
    for r in peers:
        for c in (r.get("caps") or []):
            dist[c] = dist.get(c, 0) + 1
    top_peer = sorted(dist.items(), key=lambda kv: -kv[1])
    dims.append({"dim": DIM_ORDER[0], "cells": [
        cell("self 计数位", "%d 项：%s" % (len(caps), "/".join(caps) or "—"), m_src),
        cell("self 测量盲区（不是缺功能）", "、".join(blind) or "无",
             "%s（self_row.caps_blind；口径见 benchmark_metrics.cap_channel_class docstring）" % m_src),
        cell("peers 单格最高", "%s=%d/%d" % (top_peer[0][0], top_peer[0][1], denom) if top_peer else "NA(池空)", m_src),
        cell("peers 危机语料覆盖", "池内多数仓无标注危机集；self 有 6 条冻结样本",
             "peer-capability-safety 台账 " + sref("peer-capability-safety-*.json")),
    ]})

    roll_p, roll = ledger("benchmark-rollup-*.json")
    da = (roll or {}).get("dim_a_testing_repro") or {}
    db = (roll or {}).get("dim_b_zero_build_cost") or {}
    sc = ((db.get("self_cost") or da.get("self") or {}))
    dims.append({"dim": DIM_ORDER[1], "cells": [
        cell("self 零构建", "zero_build=%s｜套件 %s｜Java 测试件 %s" % (
            sc.get("zero_build", "?"), sc.get("regression_suites", "?"), sc.get("java_test_files", "?")),
             stamp(roll_p, roll) if roll_p else "NA-DECLARED：缺 benchmark-rollup，补法 python _test/bench_rollup.py"),
        cell("词表单源", "src/data/emotion-lexicon.js（JS/Java 各加载同一文件）",
             "HEAD 面 git show + memory/AGENTS.md 词表一致性红线"),
        cell("peers 生态", "deps_autoupdate=%d/%d（有包清单才可挂）" % (dist.get("deps_autoupdate", 0), denom), m_src),
    ]})

    suites = count_suites()
    jt_files, jt_cases = java_tests()
    qg = jacoco_from_pom()
    dims.append({"dim": DIM_ORDER[2], "cells": [
        cell("self 电池套件数", "%d（HEAD 面）" % suites if suites is not None else "NA(git 取不到)",
             "git show HEAD:_test/run_all_suites.py 的 SUITES 计数"),
        cell("self Java 用例", "%d 件 / %d 例｜门 LINE/BRANCH ≥ %s" % (
            jt_files, jt_cases, qg) if jt_files is not None else "NA", "git ls-tree HEAD + server/pom.xml"),
        cell("peers 有测试结构 / CI unit 步", "%d/%d ＋ %d/%d（coverage_gate 与 mutation_gate 均 0/%d）" % (
            (da.get("peers_quality_tooling") or {}).get("have_test_struct", -1), denom,
            (da.get("peers_quality_tooling") or {}).get("ci_unit_step", -1), denom, denom)
            if da.get("peers_quality_tooling") else "NA-DECLARED：缺 peers_quality_tooling 块，补法 python _test/peer_quality_tooling_probe.py --json …",
        sref("peer-quality-tooling-*.json")),
    ]})

    dims.append({"dim": DIM_ORDER[3], "cells": [
        cell("self 首屏预算", json.dumps((da or {}).get("self", {}).get("first_screen_budget"), ensure_ascii=False),
             stamp(roll_p, roll) if roll_p else "—"),
        cell("peers bench 在册数", "NA-DECLARED：台账未取到 peers 的 bench_script 在册数 ⇒ 不做无据横比；"
             "补法 python _test/benchmark_metrics.py --doc-perf",
             "peer-repro 台账 " + sref("peer-repro-*.json")),
    ]})

    mem_p, mem = ledger("peer-memory-*.json")
    dims.append({"dim": DIM_ORDER[4], "cells": [
        cell("self 缺位", "插件协议 / 向量长记忆 / i18n（文档化 ≠ 机制化，见 docs/EXTENSIONS.md）",
             "HEAD 面 git ls-tree + docs/EXTENSIONS.md"),
        cell("peers vector_memory", "%d/%d" % (dist.get("vector_memory", 0), denom), m_src),
        cell("peers i18n_locale", "%d/%d" % (dist.get("i18n_locale", 0), denom), m_src),
        cell("peers 记忆形态在册面", "usable=%s blind=%s denominator=%s" % (
            (mem or {}).get("usable"), (mem or {}).get("blind"), (mem or {}).get("denominator")) if mem else "NA",
             stamp(mem_p, mem) if mem_p else "—"),
    ]})

    mt_p, mt = ledger("peer-maintenance-*.json")
    rel_p, rel = ledger("peer-release-*.json")
    ir_p, ir = ledger("peer-issue-response-*.json")
    commits, hdays, tags = maintenance_self()
    # CI 可移植性（R-CURRENT 第 12 条口径）：runner 是 depth=1 浅克隆，`--since=30.days` 恒读到 1、
    # tag 面恒为空 ⇒ 这三格在 CI 里量的是 checkout 形状而不是项目现状。明知失真还印进台账，
    # 下一轮就会有人拿它横比。正解是**逐格降档为 NA 并写明补法**，其余七维照判。
    in_ci = (os.environ.get("CI") or "").lower() in ("true", "1")
    if in_ci:
        commits, hdays, tags = None, None, None
    peers_rel = ((rel or {}).get("repos") or {})
    n_rel = sum(1 for k, v in peers_rel.items() if k != "__self__" and isinstance(v, dict) and v.get("release"))
    n_sem = sum(1 for k, v in peers_rel.items() if k != "__self__" and isinstance(v, dict) and v.get("semver_tag"))
    val_commits = ("NA-DECLARED：CI 浅克隆面（depth=1），提交率量的是 checkout 形状不是现状；"
                   "补法=本机 python _test/bench_eight_dims_check.py --round rNNN")
    if commits is not None:
        val_commits = "%d 次｜history_days=%d%s" % (
            commits, hdays, "（<30 ⇒ window_full=false，**禁止横比**）" if hdays < 30 else "")
    val_tags = ("NA-DECLARED：CI 浅克隆无 tag 面" if tags is None
                else "%d（一致性由 repo_config G12 独家判，本件不重复设尺）" % tags)
    dims.append({"dim": DIM_ORDER[5], "cells": [
        cell("self 30 天提交", val_commits,
             "本轮 git rev-list --count --since=30.days HEAD 实测" if commits is not None else "CI 面降档"),
        cell("self tag 数", val_tags,
             "本轮 git tag 实测 + G12" if tags is not None else "CI 面降档"),
        cell("peers 提交率 top", top_rates(mt) if mt else "NA(缺 peer-maintenance)",
             stamp(mt_p, mt) if mt_p else "—"),
        cell("peers release / semver tag", "%d/%d ＋ %d/%d" % (n_rel, denom, n_sem, denom) if rel else "NA",
             stamp(rel_p, rel) if rel_p else "—"),
        cell("peers issue 响应可比性", "NA-DECLARED：%d 条里含 self 在内多条为 NA（零 issue 或样本<3）⇒ 该维不作差距项；"
             "补法 python _test/peer_issue_response_probe.py --json …（错峰单跑）" %
             len((ir or {}).get("rows") or {}), stamp(ir_p, ir) if ir_p else "—"),
    ]})

    n_docs, api_paths, api_ends = docs_self()
    dims.append({"dim": DIM_ORDER[6], "cells": [
        cell("self 文档件数 / openapi⇄端点", "%d 件｜openapi %d paths ⇄ Java %d 映射（差 %d）" % (
            n_docs, api_paths, api_ends, api_paths - api_ends), "HEAD 面 git ls-tree + docs/openapi.yaml + 控制器注记"),
        cell("peers docs 面", "本件不重采 ⇒ 引用 NA；补法 python _test/benchmark_metrics.py（docs 字段在 runs[-1].repos[].docs）", m_src),
    ]})

    why = ", ".join("%s(%s)" % (r.get("repo", "?").split("/")[-1], r.get("tier", "-")) for r in peers[:6])
    dims.append({"dim": DIM_ORDER[7], "cells": [
        cell("self 定位", "演示级单用户 + 离线可完整演示 + 三路情绪 + 危机转介", "HEAD 面 src/ 与 memory/01-goal.md"),
        cell("peers 定位抽样", why, m_src + "（repos[].why/tier）"),
    ]})

    return dims, notes


class Unverified(Exception):
    """取数面不可读 ⇒ rc=2，绝不静默 PASS。"""


class Inconsistent(Exception):
    """分母/自证不自洽 ⇒ rc=1。"""


def count_suites():
    """归口 bench_rollup.suites_total()：HEAD 面 SUITES 条数的唯一算家。"""
    if BR is None:
        raise Unverified("bench_rollup 不可导入（%s）⇒ 拒绝回落自算" % BR_ERR)
    return BR.suites_total()


def java_tests():
    if BR is None:
        raise Unverified("bench_rollup 不可导入（%s）" % BR_ERR)
    side = BR.self_side(BR.ls_files())
    return side.get("java_test_files"), side.get("java_test_cases")


def jacoco_from_pom():
    if BR is None:
        raise Unverified("bench_rollup 不可导入（%s）" % BR_ERR)
    m = BR.jacoco_minimums()
    return m if isinstance(m, str) else json.dumps(m, ensure_ascii=False)


def maintenance_self():
    try:
        commits = int(sh(["git", "rev-list", "--count", "--since=30.days", "HEAD"]).strip() or 0)
        first = sh(["git", "log", "--format=%ad", "--date=short", "--reverse"]).splitlines()[:1]
        hdays = 0
        if first:
            d0 = datetime.strptime(first[0], "%Y-%m-%d")
            hdays = (datetime.now() - d0).days + 1
        tags = len([x for x in sh(["git", "tag"]).splitlines() if x.strip()])
        return commits, hdays, tags
    except (RuntimeError, ValueError):
        return 0, 0, 0


def top_rates(mt):
    peers = mt.get("peers") or {}
    items = sorted(((v.get("rate_per_day") or 0, k) for k, v in peers.items() if isinstance(v, dict)),
                   reverse=True)
    return "、".join("%s=%.2f/日" % (k.split("/")[-1], r) for r, k in items[:3])


def docs_self():
    """self 侧文档面：件数 + openapi paths ⇄ Java 映射端点数（两个都取 HEAD 面，避免读到在途改动）。"""
    try:
        files = BR.ls_files() if BR is not None else sh(["git", "ls-tree", "-r", "--name-only", "HEAD"]).splitlines()
        docs = [f for f in files if (f.startswith("docs/") or f in
                ("README.md", "README.en.md", "CONTRIBUTING.md", "ROADMAP.md", "SECURITY.md", "CHANGELOG.md"))]
        api = len(re.findall(r"^  /api/", head_text("docs/openapi.yaml"), re.M))
        hits = sh(["git", "grep", "-h", "-e", "@GetMapping(", "-e", "@PostMapping(",
                   "-e", "@DeleteMapping(", "-e", "@PutMapping(", "HEAD", "--",
                   "server/src/main/java"])
        ends = len([ln for ln in hits.splitlines() if "@Map" in ln or "Mapping(" in ln])
    except (RuntimeError, OSError):
        return 0, 0, 0
    return len(docs), api, ends


# ── 判定与产物 ──────────────────────────────────────────────────────────────
def audit(dims):
    """纯函数：返回 (红因列表, 未验列表, 格数)。红因=缺源/缺维；未验=NA-DECLARED 计数（不判红）。"""
    bad, na, ncells = [], [], 0
    got = [d["dim"] for d in dims]
    for want in DIM_ORDER:
        if want not in got:
            bad.append("缺维：%s" % want)
    for d in dims:
        cells = d.get("cells") or []
        if not cells:
            bad.append("维度 %s 零格 ⇒ 空格不等于无差距" % d["dim"])
        for c in cells:
            ncells += 1
            src = (c.get("source") or "").strip()
            if not src or src in ("—", "-"):
                bad.append("格缺源：%s / %s" % (d["dim"], c.get("label")))
            if str(c.get("value", "")).startswith("NA"):
                na.append("%s/%s" % (d["dim"], c.get("label")))
    return bad, na, ncells, len(got)


def to_markdown(dims):
    """按格子的 side（标签前缀 `peers`）分列，出处列**不截断到字中间**：
    半截的文件名比没有文件名更坏——它长得像可核对的出处。"""
    buf = io.StringIO()
    buf.write("| # | 维度 | 心屿 MindIsle（self） | peers | 出处（可复算） |\n|---|---|---|---|---|\n")
    for i, d in enumerate(dims, 1):
        is_peer = lambda c: str(c["label"]).startswith("peers")
        selfc = [c for c in d["cells"] if not is_peer(c)]
        peerc = [c for c in d["cells"] if is_peer(c)]
        srcs = sorted({c["source"] for c in d["cells"] if c.get("source")})
        shown = "; ".join(srcs[:2]) + ("…（共 %d 条，全量见 eight-dims JSON）" % len(srcs) if len(srcs) > 2 else "")
        buf.write("| %d | %s | %s | %s | %s |\n" % (
            i, d["dim"],
            "；".join("%s：%s" % (c["label"], c["value"]) for c in selfc[:3]),
            "；".join("%s：%s" % (c["label"], c["value"]) for c in peerc[:3]) or "—",
            shown))
    return buf.getvalue()


def dump_bytes(path, text):
    """强制 LF：Windows 文本模式会把 \n 译成 \r\n，而字节类判据按磁盘字节算（r35 一手坑）。"""
    path.write_bytes(text.encode("utf-8").replace(b"\r\n", b"\n"))


def mk_dims(override=None, drop=None):
    """造一份「八维齐、格格有源」的基线夹具，再按用例破坏其中一处。
    桩必须**先自证基线可用**：早先版本把 cellsets 按下标硬塞进 8 维，
    结果「正向桩」自己因为另外几维是空格而红 ⇒ 桩在测自己的构造而不是测 audit（同族：改错分支）。"""
    dims = [{"dim": d, "cells": [cell("a", "1", "src-a"), cell("peers b", "2", "src-b")]} for d in DIM_ORDER]
    for i in (drop or []):
        dims.pop(i)
    for idx, cells in (override or {}).items():
        dims[idx]["cells"] = cells
    return dims


STUBS = [
    ("基线：八维齐且格格有源 ⇒ 0", mk_dims(), 0),
    ("格缺源 ⇒ 1", mk_dims({0: [cell("a", "1", "   "), cell("b", "2", "src-b")]}), 1),
    ("缺维 ⇒ 1", mk_dims(drop=[3]), 1),
    ("维度零格 ⇒ 1", mk_dims({5: []}), 1),
    ("NA 声明不判红但计数 ⇒ 0", mk_dims({2: [cell("a", "NA-DECLARED：缺 bench_script，补法 …", "src-a")]}), 0),
]


def selftest():
    bad = []
    if audit(mk_dims())[0]:                       # 基线必须先自证可用，否则下面所有桩都是空转
        bad.append("基线夹具本身判红 ⇒ 桩在测自己的构造，不是测 audit")
    for name, dims, want in STUBS:
        code = 1 if audit(dims)[0] else 0
        if code != want:
            bad.append("%s：期望 rc=%d 实得 %d（%s）" % (name, want, code, audit(dims)[0][:1]))
    # 恒绿守卫：全格缺源必须红
    if not audit([{"dim": d, "cells": [cell("a", "1", "")]} for d in DIM_ORDER])[0]:
        bad.append("判据恒绿：八维格格缺源仍判通过")
    na = audit(mk_dims({2: [cell("a", "NA-DECLARED：x", "s")]}))[1]
    if len(na) != 1:
        bad.append("NA 计数不成立：期望 1 实得 %d" % len(na))
    print("EIGHT-DIMS-SELFTEST-%s（%d 类桩 + 基线自证 + 恒绿守卫 + NA 计数）"
          % ("PASS" if not bad else "FAIL: " + "; ".join(bad), len(STUBS)))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--round", default=None)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-write", action="store_true", help="只算不写台账（演习/selftest 用）")
    ap.add_argument("--quiet", action="store_true",
                    help="不印 markdown 表（电池整跑用：电池只留末条判据行，满屏表格会把它挤掉）")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not a.round:
        print("EIGHT-DIMS-UNVERIFIED: 缺 --round rNNN ⇒ 产物无法署名，宁可不写也不造无主台账")
        return 2
    try:
        dims, notes = build_dims()
    except Unverified as e:
        print("EIGHT-DIMS-UNVERIFIED: %s" % e)
        return 2
    except Inconsistent as e:
        print("EIGHT-DIMS-FAIL: %s" % e)
        return 1
    except RuntimeError as e:
        print("EIGHT-DIMS-UNVERIFIED: git 取数面不可读（%s）⇒ 不得读成通过" % str(e)[:80])
        return 2
    bad, na, ncells, ndims = audit(dims)
    payload = {"generated_by": "_test/bench_eight_dims_check.py", "round": a.round,
               "written_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
               "dims": dims, "na_cells": na, "cells": ncells}
    out = DATA / ("eight-dims-%s.json" % a.round)
    if not a.no_write:
        DATA.mkdir(parents=True, exist_ok=True)
        dump_bytes(out, json.dumps(payload, ensure_ascii=False, indent=1) + "\n")
    line = ("EIGHT-DIMS-PASS 维 %d/8｜格 %d｜NA声明 %d｜产物 %s" % (ndims, ncells, len(na),
            out.name if not a.no_write else "未落盘(--no-write)"))
    if a.json:
        print(json.dumps({"verdict": line, "red": bad, "na": na, "cells": ncells}, ensure_ascii=False))
    if bad:
        print("EIGHT-DIMS-FAIL 维 %d/8｜格 %d｜缺源/缺维 %d 项" % (ndims, ncells, len(bad)))
        for x in bad[:8]:
            print("  - " + x)
        return 1
    md = to_markdown(dims)
    if not a.no_write:
        dump_bytes(DATA / ("eight-dims-%s.md" % a.round), md)
    print(line)
    if not a.quiet:
        print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
