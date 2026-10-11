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


def docs_peers_val(path, payload):
    """第 7 维 peers 格。取数面＝`_test/peer_docs_probe.py` 的一次 git tree 快照。

    改前每轮写「本件不重采 ⇒ 引用 NA」——那是**没有分母**，不是"对手文档差"。
    四类位＝API 规范 / 使用教程 / 贡献指南 / 独立文档区（老大原话里的三项 + 文档区），
    另带 self 的同尺读数（self 与 peers 共用 classify_docs，口径不分开）。"""
    if path is None or not isinstance(payload, dict) or not payload.get("rows"):
        return ("NA-DECLARED：缺 peer-docs 台账 ⇒ 文档维无分母；"
                "补法 python _test/peer_docs_probe.py --json 交付物/对标数据/peer-docs-<date>.json")
    if payload.get("__unreadable__"):
        return "NA-DECLARED：peer-docs 台账读不动（%s）⇒ 不折算成结论" % payload["__unreadable__"]
    # 逐位在册数**在本格现算**（台账里没存聚合位）：聚合由行导出，
    # 存两份就等于同一事实两把尺——台账重采而聚合字段没跟上时，格会抄着旧聚合说谎。
    rows = payload.get("rows") or []
    peer_rows = [r for r in rows if not str(r.get("repo", "")).startswith("self")]
    bits = {k: sum(1 for r in peer_rows if r.get(k))
            for k in ("api_spec", "guide", "contributing", "docs_site")}
    dist = payload.get("class_dist") or {}
    self_row = next((r for r in rows if str(r.get("repo", "")).startswith("self")), None)
    blind = len(payload.get("blind_or_na") or [])
    return ("四类位在册（分母 %s 仓）：API 规范 %s、教程 %s、贡献指南 %s、独立文档区 %s；"
            "形态 %s；失明/未验 %d 仓｜self 同尺=%s（缺项＝独立 quickstart 文件，本仓入门写在 docs/README.md 里）"
            % (payload.get("denominator"), bits.get("api_spec", "NA"), bits.get("guide", "NA"),
               bits.get("contributing", "NA"), bits.get("docs_site", "NA"),
               " ".join("%s=%d" % kv for kv in sorted(dist.items())), blind,
               (self_row or {}).get("class", "NA")))


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
        cell("self 零构建", "zero_build=%s｜（套件数／Java 用例数见第 3 维：同一事实只许一处判，"
             "本格改前抄台账的 152，而第 3 维现算已是 155 ⇒ 同一张表两张嘴）" % (
                 sc.get("zero_build", "?")),
             stamp(roll_p, roll) if roll_p else "NA-DECLARED：缺 benchmark-rollup，补法 python _test/bench_rollup.py"),
        cell("词表单源", "src/data/emotion-lexicon.js（JS/Java 各加载同一文件）",
             "HEAD 面 git show + memory/AGENTS.md 词表一致性红线"),
        cell("peers 生态", "deps_autoupdate=%d/%d（有包清单才可挂）" % (dist.get("deps_autoupdate", 0), denom), m_src),
    ]})

    suites = count_suites()
    jt_files, jt_cases = java_tests()
    qg = jacoco_from_pom()
    dims.append({"dim": DIM_ORDER[2], "cells": [
        cell("self 电池套件数", "%d（工作树面）" % suites if suites is not None else "NA(runner 取不到)",
             "_test/run_all_suites.py --list 自报（r121 更正：旧标「HEAD 面」与实现不符——"
             "归口的 bench_rollup.suites_total() 跑的是工作树脚本，不是 git show HEAD）"),
        cell("self Java 用例", "%d 件 / %d 例｜门 LINE/BRANCH ≥ %s" % (
            jt_files, jt_cases, qg) if jt_files is not None else "NA", "git ls-tree HEAD + server/pom.xml"),
        cell("peers 有测试结构 / CI unit 步", "%d/%d ＋ %d/%d（coverage_gate 与 mutation_gate 均 0/%d）" % (
            (da.get("peers_quality_tooling") or {}).get("have_test_struct", -1), denom,
            (da.get("peers_quality_tooling") or {}).get("ci_unit_step", -1), denom, denom)
            if da.get("peers_quality_tooling") else "NA-DECLARED：缺 peers_quality_tooling 块，补法 python _test/peer_quality_tooling_probe.py --json …",
        sref("peer-quality-tooling-*.json")),
    ]})

    pp_p, pp = ledger("peer-perf-*.json")
    if pp and isinstance(pp, dict) and pp.get("rows"):
        shapes = {}
        for r in pp["rows"]:
            shapes[str(r.get("class"))] = shapes.get(str(r.get("class")), 0) + 1
        blind_rows = sum(1 for r in pp["rows"] if r.get("blind"))
        cell4 = cell("peers bench 在册数",
                     "measured*=%s/%s 仓｜形态 %s｜失明 %d 仓｜三通道 A 基准件 / B CI 真跑 / C 结果件，"
                     "A 单独不算在册能力（r121 首取，改 NA 为有分母）" % (
                         pp.get("measured"), pp.get("denominator"),
                         " ".join("%s=%d" % kv for kv in sorted(shapes.items())), blind_rows),
                     stamp(pp_p, pp) + "（python _test/peer_perf_probe.py）")
    else:
        cell4 = cell("peers bench 在册数",
                     "NA-DECLARED：台账未取到 peers 的 bench 在册数 ⇒ 不做无据横比；"
                     "补法 python _test/peer_perf_probe.py --json 交付物/对标数据/peer-perf-<date>.json",
                     sref("peer-perf-*.json"))
    dims.append({"dim": DIM_ORDER[3], "cells": [
        cell("self 首屏预算", json.dumps((da or {}).get("self", {}).get("first_screen_budget"), ensure_ascii=False),
             stamp(roll_p, roll) if roll_p else "—"),
        cell4,
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

    dc_p, dc = ledger("peer-docs-*.json")          # r122：第 7 维的 peers 分母第一次有数
    n_docs, api_paths, api_ends = docs_self()
    dims.append({"dim": DIM_ORDER[6], "cells": [
        cell("self 文档件数 / openapi⇄端点", "%d 件｜openapi %d paths ⇄ Java %d 映射（差 %d）｜"
             "同尺四类位=%s（HEAD 面取数，与 peers 同一条 classify_docs）" % (
            n_docs, api_paths, api_ends, api_paths - api_ends,
            (next((r for r in (dc or {}).get("rows") or []
                   if str(r.get("repo", "")).startswith("self")), {}) or {}).get("class", "NA")),
             "HEAD 面 git ls-tree + docs/openapi.yaml + 控制器注记；四类位＝_test/peer_docs_probe.py self_only()"),
        cell("peers docs 面", docs_peers_val(dc_p, dc), "本件不重采 ⇒ 引用 NA；补法 python _test/benchmark_metrics.py（docs 字段在 runs[-1].repos[].docs）"),
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
    """归口 bench_rollup.suites_total()：**工作树面** SUITES 条数的唯一算家（它跑 runner 的 --list 自报）。"""
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


def round_key(tag):
    """轮次按**数字**排序，不按字典序：字典序会把 `r99` 排到 `r100` 之后 ⇒ 比对的成了两份旧台账。"""
    m = re.search(r"(\d+)", tag or "")
    return (int(m.group(1)) if m else -1, tag or "")


def ledgers(limit=2):
    """最近 N 份 eight-dims 台账，返回由新到旧的 [(轮次, Path)]。
    排序键取**文件名轮次**而非 mtime —— checkout／搬卷会把 mtime 整体刷新（`ledger_age` 实测踩过）。"""
    fs = []
    for p in glob.glob(str(DATA / "eight-dims-*.json")):
        if "_partial" + os.sep in p or "_superseded" + os.sep in p:
            continue
        m = re.search(r"eight-dims-(.+)\.json$", p)
        if m:
            fs.append((m.group(1), Path(p)))
    fs.sort(key=lambda x: round_key(x[0]))
    return fs[-limit:][::-1]


def cell_map(payload):
    out = {}
    for d in (payload or {}).get("dims") or []:
        for c in d.get("cells") or []:
            out[(d.get("dim"), c.get("label"))] = c
    return out


def drift(prev, cur, tol=3):
    """跨轮漂移纯函数：返回 (红因, 变化点名)。

    口径故意不对称（与 `perf_ramp_delta` 同族）：
      · **只把可追溯性退化判红**——维度数缩水／格数缩水超容差／某格 source 由有变无／
        实测过的格退成 NA。这些是"尺变短了"，放行就等于下一轮看不见差距。
      · **值变化只点名不判红**——变好、换取证口径、台账重采都会改值；把改值当回归判红
        会造出"每次正常演进都红一次"的永红判据（本仓在册教训）。
    """
    if not prev or not cur:
        return [], []
    pm, cm = cell_map(prev), cell_map(cur)
    bad, chg = [], []
    if len({k[0] for k in cm}) < len({k[0] for k in pm}):
        bad.append("维度数缩水：%d → %d" % (len({k[0] for k in pm}), len({k[0] for k in cm})))
    if len(cm) - len(pm) < -tol:
        bad.append("格数缩水 %d → %d（容差 %d）⇒ 有人在悄悄缩短分母" % (len(pm), len(cm), tol))
    for k, c in cm.items():
        p = pm.get(k)
        if p is None:
            chg.append("新增格 %s/%s" % (k[0], k[1]))
            continue
        if (p.get("source") or "").strip() and not (c.get("source") or "").strip():
            bad.append("来源退化（有源→无源）：%s/%s" % (k[0], k[1]))
        pv, cv = str(p.get("value", "")), str(c.get("value", ""))
        if cv.startswith("NA") and not pv.startswith("NA"):
            bad.append("实测退成 NA：%s/%s" % (k[0], k[1]))
        if pv != cv:
            chg.append("值变 %s/%s：%s → %s" % (k[0], k[1], pv[:30], cv[:30]))
    for k in pm:
        if k not in cm:
            chg.append("格消失 %s/%s" % (k[0], k[1]))
    return bad, chg


DRIFT_STUBS = [
    ("两轮齐且无退化（值变）⇒ 不红",
     {"dims": [{"dim": "功能模块覆盖", "cells": [{"label": "a", "value": "1", "source": "x"}]}]},
     {"dims": [{"dim": "功能模块覆盖", "cells": [{"label": "a", "value": "2", "source": "x"}]}]}, 0),
    ("来源由有变无 ⇒ 红",
     {"dims": [{"dim": "功能模块覆盖", "cells": [{"label": "a", "value": "1", "source": "x"}]}]},
     {"dims": [{"dim": "功能模块覆盖", "cells": [{"label": "a", "value": "1", "source": ""}]}]}, 1),
    ("实测退成 NA ⇒ 红",
     {"dims": [{"dim": "性能表现", "cells": [{"label": "a", "value": "25.1s", "source": "x"}]}]},
     {"dims": [{"dim": "性能表现", "cells": [{"label": "a", "value": "NA-DECLARED", "source": "x"}]}]}, 1),
    ("格数小抖动（容差内）⇒ 不红",
     {"dims": [{"dim": "功能模块覆盖", "cells": [
         {"label": str(i), "value": "v", "source": "x"} for i in range(10)]}]},
     {"dims": [{"dim": "功能模块覆盖", "cells": [
         {"label": str(i), "value": "v", "source": "x"} for i in range(8)]}]}, 0),
    ("格数大幅缩水 ⇒ 红",
     {"dims": [{"dim": "功能模块覆盖", "cells": [
         {"label": str(i), "value": "v", "source": "x"} for i in range(25)]}]},
     {"dims": [{"dim": "功能模块覆盖", "cells": [
         {"label": str(i), "value": "v", "source": "x"} for i in range(8)]}]}, 1),
    ("维度数缩水 ⇒ 红",
     {"dims": [{"dim": d, "cells": [{"label": "a", "value": "v", "source": "x"}]} for d in DIM_ORDER]},
     {"dims": [{"dim": DIM_ORDER[0], "cells": [{"label": "a", "value": "v", "source": "x"}]}]}, 1),
]


def drift_selftest():
    bad = []
    for name, prev, cur, want in DRIFT_STUBS:
        got = 1 if drift(prev, cur)[0] else 0
        if got != want:
            bad.append("漂移桩「%s」：期望红=%d 实得 %d（%s）" % (name, want, got, drift(prev, cur)[0][:1]))
    if round_key("r99") >= round_key("r100"):
        bad.append("轮次排序退回字典序 ⇒ 会比错两份旧台账")
    if drift(None, {"dims": []})[0]:
        bad.append("缺第二份时判了红（应为未验：不判红也不判绿）")
    return bad


REMEDY_RX = re.compile(r"python\s+(?:\S*/)?_test/([A-Za-z0-9_.\-]+\.py)")


def remedy_audit(dims, head_files, on_disk):
    """NA-DECLARED 格里的「补法 python _test/x.py」必须是**真能跑的脚本**。

    为什么装这条腿：NA 是这张表唯一"诚实的出口"，而出口本身没人验。
    死链的 NA 长得像"照这句跑一下就补上了"，实际跑起来 file not found ⇒ 下一轮继续抄 NA，
    而且抄得更心安理得（毕竟"补法"写在那儿）。r122 装这条腿的直接动因：本轮把第 4 维
    的 NA 换成实测后，剩余 NA 格里点的脚本名成了唯一还没被机器核过的东西。

    两侧分别判（承 r120「同一判据量两面」）：
      · 工作树也没有 ⇒ **死链**，判红（补法指向一个不存在的出口）；
      · 工作树有、HEAD 没有 ⇒ **未入库**，点名而不判红（那是别人/本轮的在途中间态，
        红会砸到不该砸的人身上；归属轮提交后自然消失）。
    只判 NA 格，不判普通格的引用——普通格的 source 里常有历史描述（"改前写的是…"），
    拿这条腿打死会让判据变成拦正常改表的闸门（爆炸半径＝断言范围）。
    """
    red, pending = [], []
    for d in dims:
        for c in d.get("cells") or []:
            if not str(c.get("value", "")).startswith("NA"):
                continue
            text = str(c.get("value", "")) + " " + str(c.get("source", ""))
            names = set(REMEDY_RX.findall(text))
            if not names and "补法" in text:
                # 写了"补法"却没点到具体脚本（如 `python _test/<对应 probe>.py`）⇒ 出口是占位符。
                # 点名不判红：它不是坏链，是"还没接"；判红会把老实认 NA 的格一起打死。
                pending.append("%s/%s ⇒ 补法是占位符（没点到具体脚本）" % (d["dim"], c.get("label")))
            for name in names:
                rel = "_test/" + name
                if rel not in head_files and rel not in on_disk:
                    red.append("NA 补法死链：%s/%s ⇒ %s 既不在 HEAD 面也不在盘上" % (
                        d["dim"], c.get("label"), rel))
                elif rel not in head_files:
                    pending.append("%s/%s ⇒ %s 在盘未入库" % (d["dim"], c.get("label"), rel))
    return red, pending


def remedy_selftest():
    """补法腿自己也要有反例：死链必须红、活链必须绿、未入库只点名。"""
    bad = []
    hf = {"_test/alive_probe.py"}
    disk = {"_test/alive_probe.py", "_test/inflight_probe.py"}
    ok = [{"dim": DIM_ORDER[3], "cells": [
        cell("a", "NA-DECLARED：无台账；补法 python _test/alive_probe.py --json x", "s")]}]
    r1, p1 = remedy_audit(ok, hf, disk)
    if r1 or p1:
        bad.append("活补法被判红/点名：%s %s" % (r1, p1))
    dead = [{"dim": DIM_ORDER[3], "cells": [
        cell("a", "NA-DECLARED：无台账；补法 python _test/gone_probe.py --json x", "s")]}]
    r2, _ = remedy_audit(dead, hf, disk)
    if not any("死链" in x for x in r2):
        bad.append("死链补法没判红 ⇒ 出口是假的也没人管（这条腿恒绿）")
    infl = [{"dim": DIM_ORDER[3], "cells": [
        cell("a", "NA-DECLARED：无台账；补法 python _test/inflight_probe.py --json x", "s")]}]
    r3, p3 = remedy_audit(infl, hf, disk)
    if r3 or len(p3) != 1:
        bad.append("在盘未入库被当成死链（红=%s）或没点名（pending=%s）⇒ 面别混了" % (r3, p3))
    noref = [{"dim": DIM_ORDER[3], "cells": [cell("a", "NA-DECLARED：本件不重采", "s")]}]
    r4, p4 = remedy_audit(noref, hf, disk)
    if r4 or p4:
        bad.append("没写补法的 NA 被这条腿判红/点名 ⇒ 会拦住所有老实认 NA 的格（爆炸半径>断言范围）")
    placeholder = [{"dim": DIM_ORDER[3], "cells": [
        cell("a", "NA-DECLARED：缺 X，补法 python _test/<对应 probe>.py --json …", "s")]}]
    r5, p5 = remedy_audit(placeholder, hf, disk)
    if r5 or len(p5) != 1:
        bad.append("占位符补法没被点名（红=%s 点名=%s）⇒ 假出口仍可以蒙过这条腿" % (r5, p5))
    return bad


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
    bad += drift_selftest()      # r121：跨轮漂移腿（只生成不比对＝表绿着漂）
    bad += remedy_selftest()
    print("EIGHT-DIMS-SELFTEST-%s（%d 类结构桩 + %d 类漂移桩 + 基线自证 + 恒绿守卫 + NA 计数"
          " + 补法死链 5 向：活链绿/死链红/未入库点名/无补法不拦/占位符点名）"
          % ("PASS" if not bad else "FAIL: " + "; ".join(bad), len(STUBS), len(DRIFT_STUBS)))
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
    # r122：NA 的"补法出口"自证——死链判红，在盘未入库/占位符只点名（不拦正常人改表）
    remedy_red, remedy_pending = [], []
    try:
        head_files = set(BR.ls_files()) if BR is not None else set()
        on_disk = {"_test/" + x.name for x in (ROOT / "_test").glob("*.py")}
        remedy_red, remedy_pending = remedy_audit(dims, head_files, on_disk)
    except Exception as e:                                  # noqa: BLE001
        remedy_red = ["补法腿未跑成（%s: %s）⇒ 未验不判绿" % (type(e).__name__, str(e)[:60])]
    bad += remedy_red
    payload = {"generated_by": "_test/bench_eight_dims_check.py", "round": a.round,
               "written_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
               "dims": dims, "na_cells": na, "cells": ncells}
    out = DATA / ("eight-dims-%s.json" % a.round)
    if not a.no_write:
        DATA.mkdir(parents=True, exist_ok=True)
        dump_bytes(out, json.dumps(payload, ensure_ascii=False, indent=1) + "\n")
    dbad, dchg, prev_round = [], [], None
    pair = [x for x in ledgers() if x[0] != a.round]        # 排除本轮自己那份
    if pair:
        prev_round = pair[0][0]
        try:
            dbad, dchg = drift(json.loads(pair[0][1].read_text("utf-8")), payload)
        except (OSError, ValueError) as e:
            dbad = ["上一份台账读不动（%s）⇒ 漂移腿未验，不判绿" % type(e).__name__]
        bad += dbad
        note = "漂移=比对 %s｜退化红 %d｜变化 %d" % (prev_round, len(dbad), len(dchg))
    else:
        note = "漂移=未验(只有一份台账，不判红也不判绿)"
    line = ("EIGHT-DIMS-PASS 维 %d/8｜格 %d｜NA声明 %d｜补法死链 %d｜补法待接 %d｜%s｜产物 %s" % (
        ndims, ncells, len(na), len(remedy_red), len(remedy_pending), note,
        out.name if not a.no_write else "未落盘(--no-write)"))
    if a.json:
        print(json.dumps({"verdict": line, "red": bad, "na": na, "cells": ncells,
                          "drift_prev": prev_round, "drift_changed": dchg[:12]}, ensure_ascii=False))
    if bad:
        print("EIGHT-DIMS-FAIL 维 %d/8｜格 %d｜缺源/退化 %d 项" % (ndims, ncells, len(bad)))
        for x in bad[:8]:
            print("  - " + x)
        return 1
    if dchg and not a.quiet:
        print("  跨轮变化（点名不判红；把进步也判红会造出永红判据）：")
        for x in dchg[:8]:
            print("   · " + x)
    md = to_markdown(dims)
    if not a.no_write:
        dump_bytes(DATA / ("eight-dims-%s.md" % a.round), md)
    print(line)
    if not a.quiet:
        print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
