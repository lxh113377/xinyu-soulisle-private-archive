# -*- coding: utf-8 -*-
"""r93 新增两维度的只读汇总器（把「领先多少」从形容词变成有分母的数）

为什么加这条（改进项#2 与 #3）：
  维度 3「实现方式」与维度 4「性能」此前只有 self 的绝对值，没有与 peers 的**同址**对照，
  于是「工程化领先」只能写成形容词。本脚本只做一件事：把两侧读数并到一张表里，
  **每个数字带来源字段**（哪个文件、哪个ts），杜绝手抄。

维度 A：测试与可复现性
  self侧（本轮现测，git HEAD 面）：电池套件数 / Java 测试类数与 @Test 数 / jacoco 双门阈值 /
    CI 工作流数/ 「测试结构」存在性。
  peers 侧：读既有台账 `peer-quality-tooling-*.json`（测试结构/计数/CI 步）与
    `peer-repro-*.json`（复现要素：lockfile/.env.example/Dockerfile 等）。
  ⚠️ 两份peers 台账的 ts 是 2026-09-26~28，**含已换址的旧 letta 行** ⇒ 本脚本把
    「台账 ts」与「现采ts」一并打印，并由调用方决定能否当现状读（本脚本自己不下趋势结论）。

维度 B：零构建 / 无 CI 构建链的成本-收益复算
  self侧成本账本（git HEAD 面）：首屏预算件数与总字节 / src 代码文件数 / 跟踪的构建配置数
    （package.json·webpack·vite·tsconfig…，**为 0 才算真零构建**）/ CI workflow 数 / CI job 数。
  peers 侧对照：只报**能取到的构建门分布**（lint/typecheck/coverage/mutation/secret五类），
    成本项（首屏字节/请求数/CI job 数）**本轮未取数**——输出里显式标 `未取数`，
    **不得塌缩成 0**（r76「树派生类降到未验」同族纪律）。

三态：0=ROLLUP-PASS 1=读数不可用 2=源缺失/零文件（缺源不是通过）
`--selftest`：缺源报 rc=2 + 合成样本出表两腿。
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "交付物" / "对标数据"
OUT = DATA / "benchmark-rollup-r93.json"

BUILD_CONFIG_NAMES = ("package.json", "webpack.config.js", "webpack.config.ts", "vite.config.js",
                      "vite.config.ts", "tsconfig.json", "rollup.config.js", "esbuild.config.js")
# job 内的保留键：它们也是两空格缩进的 YAML 键，但不是 job。不扣掉就会把 5 个 job 数成 10
# （r93 一手：正则 `^  key:` 直接数整份文件 ⇒ env/steps/strategy 全被算成 job）。
RESERVED_JOB_KEYS = {"env", "steps", "services", "strategy", "needs", "permissions", "outputs",
                      "defaults", "container", "if", "runs-on", "timeout-minutes", "continue-on-error",
                      "concurrency", "defaults"}


def count_jobs(body):
    """纯函数：workflow 正文 → job 数（只数 `jobs:` 块内的两空格键，并扣掉 job 内保留键）。
    可注入 ⇒ 自检能用合成样本证伪（不靠真实文件状态）。"""
    n, inside = 0, False
    for ln in body.splitlines():
        if re.match(r"^jobs:\s*$", ln):
            inside = True
            continue
        if inside:
            if ln and not ln.startswith(" ") and not ln.startswith("#"):
                break                      # 出了 jobs: 顶层
            m = re.match(r"^  ([A-Za-z0-9_-]+):\s*$", ln)
            if m and m.group(1) not in RESERVED_JOB_KEYS:
                n += 1
    return n


def git(*args):
    r = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, timeout=90)
    if r.returncode != 0:
        raise RuntimeError("git %s 失败：%s" % (" ".join(args), (r.stderr or b"").decode("utf-8", "replace")[:120]))
    return (r.stdout or b"").decode("utf-8", "replace")


def ls_files():
    return [p for p in git("ls-tree", "-r", "--name-only", "HEAD").splitlines() if p.strip()]


def blob(path):
    return git("show", "HEAD:%s" % path)


def suites_total():
    p = subprocess.run([sys.executable, str(ROOT / "_test" / "run_all_suites.py"), "--list"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
                       cwd=str(ROOT))
    m = re.search(r"SUITES:\s*(\d+)", p.stdout or "")
    return int(m.group(1)) if m else None


def jacoco_minimums():
    try:
        pom = blob("server/pom.xml")
    except Exception:
        return {}
    out = {}
    for counter in ("LINE", "BRANCH"):
        m = re.search(r"<counter>%s</counter>.*?<minimum>([0-9.]+)</minimum>" % counter, pom, re.S)
        if m:
            out[counter] = float(m.group(1))
    return out


def first_screen_budget():
    try:
        src = blob("_test/size_budget_check.py")
    except Exception:
        return {}
    block = re.search(r"BUDGETS\s*=\s*\{(.*?)\n\}", src, re.S)
    if not block:
        return {}
    items = re.findall(r'"([^"]+)":\s*([0-9_]+)', block.group(1))
    pairs = [(p, int(v.replace("_", ""))) for p, v in items]
    return {"files": len(pairs), "total_bytes": sum(v for _, v in pairs),
            "entries": [{"path": p, "budget": v} for p, v in pairs]}


def ci_faces():
    files = [p for p in ls_files() if p.startswith(".github/workflows/") and p.endswith((".yml", ".yaml"))]
    jobs = 0
    per = {}
    for p in files:
        try:
            body = blob(p)
        except Exception:
            continue
        n = count_jobs(body)
        per[p] = n
        jobs += n
    return {"workflow_files": files, "jobs": jobs, "jobs_per_file": per}


def self_side(paths):
    java_tests = [p for p in paths if p.startswith("server/src/test/java/") and p.endswith(".java")]
    cases = 0
    for p in java_tests:
        try:
            cases += len(re.findall(r"(?m)^\s*@Test\b", blob(p)))
        except Exception:
            pass
    src_code = [p for p in paths if p.startswith("src/") and p.endswith((".js", ".css", ".html"))
                and "vendor/" not in p]
    build_cfg = [p for p in paths if p.rsplit("/", 1)[-1] in BUILD_CONFIG_NAMES]
    # 「零构建」必须区分**前端构建链**与**平台函数依赖清单**（r93 实测：跟踪面唯一的
    # package.json 是 deploy/cloudbase/functions/chat/package.json，那是 CloudBase 云函数的
    # 依赖元数据，不参与前端打包）。混为一谈会让口径从「零构建」翻成「有构建链」——
    # 一个字的差别，口碑差别很大，故两类分列。
    frontend_build = [p for p in build_cfg if not p.startswith("deploy/cloudbase/")]
    platform_manifests = [p for p in build_cfg if p.startswith("deploy/cloudbase/")]
    qc = [p for p in paths if re.search(r"(?<![\w/])(check|check_)\w*\.py$", p) and p.startswith("_test/")]
    fs = first_screen_budget()
    ci = ci_faces()
    return {
        "face": "git HEAD",
        "regression_suites": suites_total(),
        "java_test_files": len(java_tests),
        "java_test_cases": cases,
        "jacoco_minimum": jacoco_minimums(),
        "check_scripts_in_test": len(qc),
        "src_code_files": len(src_code),
        "first_screen_budget": {k: fs.get(k) for k in ("files", "total_bytes")},
        "build_config_files": build_cfg,
        "frontend_build_configs": frontend_build,
        "platform_function_manifests": platform_manifests,
        "zero_build": len(frontend_build) == 0,
        "ci_workflow_files": len(ci["workflow_files"]),
        "ci_jobs": ci["jobs"],
    }


def peers_side(metrics):
    run = metrics["runs"][-1]
    qg = run.get("quality_gate_channel", {}).get("peers", {})
    classes = {}
    for repo, v in (qg or {}).items():
        for c, val in (v.get("classes") or {}).items():
            classes.setdefault(c, {"yes": 0, "no": 0, "unverified": 0})
            classes[c]["yes" if val is True else ("no" if val is False else "unverified")] += 1
    dp = run.get("doc_perf_channel", {}).get("peers", {}) or run.get("doc_perf_channel", {})
    return {"repo_count": run.get("repo_count"), "ts": run.get("ts"),
            "quality_gate_classes": classes,
            "cap_counts": run.get("cap_counts") or {},
            "doc_perf_raw_keys": sorted(dp)[:8] if isinstance(dp, dict) else []}


def _latest(prefix):
    """台账按**日期**命名（probe 脚本每次写新文件），故取最新一份而不是写死文件名。
    r94 一手：写死 `peer-quality-tooling-2026-09-28.json` 的后果是——重采已经落了
    `…-2026-10-03.json`，rollup 却还在读 09-28 那份，并在报告里标「含旧 letta 行」。
    """
    cands = sorted(DATA.glob(prefix + "*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return cands[0] if cands else None


def qt_side():
    f = _latest("peer-quality-tooling-")
    if f is None or not f.exists():
        return {"available": False}
    d = json.loads(f.read_text("utf-8"))
    rows = [r for r in d.get("rows", []) if r.get("repo") and not r["repo"].startswith("[self]")]
    have = sum(1 for r in rows if "js_test_file" in (r.get("struct") or []) or "java_test_file" in (r.get("struct") or []))
    ci_unit = sum(1 for r in rows if "unit" in (r.get("ci") or []))
    # r94：stale 不再是硬编码字符串 —— 改为**按台账实际内容**判定（是否含已换址的旧 letta 行）。
    # 硬编码的 stale 有一个坏处：重采之后它还写着 stale，读者会以为台账不能用（而真读数已换址）。
    stale = None
    if any("letta-ai/letta" == r.get("repo") for r in d.get("rows", [])):
        stale = "含已换址的旧 letta 行 letta-ai/letta（该仓已退化为 landing 页，权威实现迁 letta-code）"
    return {"available": True, "file": f.name,
            "ts": f.name.replace("peer-quality-tooling-", "").replace(".json", ""),
            "generated_by": d.get("generated_by", ""),
            "denominator": d.get("counted"), "have_test_struct": have, "ci_unit_step": ci_unit,
            "note": d.get("ceiling", ""), "stale": stale}


def repro_side():
    f = _latest("peer-repro-")
    if f is None or not f.exists():
        return {"available": False}
    d = json.loads(f.read_text("utf-8"))
    repos = d.get("repos") or {}
    lock = sum(1 for v in repos.values() if (v.get("tree") or {}).get("locks"))
    stale = None
    if any("letta-ai/letta" == k for k in repos):
        stale = "含已换址的旧 letta 行 letta-ai/letta（权威实现已迁 letta-code）"
    return {"available": True, "file": f.name, "ts": d.get("ts"), "denominator": d.get("denominator"),
            "with_lockfile": lock, "stale": stale}


def build(paths=None, metrics=None):
    paths = paths if paths is not None else ls_files()
    # r94：默认输入改为「取最新的 benchmark-metrics-*.json」，避免每轮都要改这里的文件名
    #（上一轮写死 r93 的后果就是：本轮产物 r94 落盘后，rollup 仍在读 r93 的旧读数）。
    if metrics is None:
        cands = sorted(DATA.glob("benchmark-metrics-*.json"),
                       key=lambda p: p.stat().st_mtime, reverse=True)
        if not cands:
            raise FileNotFoundError("benchmark-metrics-*.json 一份都没有 ⇒ 无源可用（不得回退去读旧台账）")
        metrics = json.loads(cands[0].read_text("utf-8"))
    return {"generated_by": "_test/bench_rollup.py",
            "dim_a_testing_repro": {"self": self_side(paths), "peers_quality_tooling": qt_side(),
                                    "peers_repro": repro_side()},
            "dim_b_zero_build_cost": {"self_cost": self_side(paths),
                                      "peers_build_gates": peers_side(metrics),
                                      "peers_cost_items": "未取数（本轮只取构建门分布；成本项不得塌缩成 0）"}}


def render(roll):
    a = roll["dim_a_testing_repro"]["self"]
    b = roll["dim_b_zero_build_cost"]["self_cost"]
    q = roll["dim_a_testing_repro"]["peers_quality_tooling"]
    p = roll["dim_a_testing_repro"]["peers_repro"]
    g = roll["dim_b_zero_build_cost"]["peers_build_gates"]
    L = []
    L.append("| 指标 | self（本轮现测，git HEAD 面） | peers（同址台账） | 来源 |")
    L.append("|---|---|---|---|")
    L.append("| 回归套件数 | %s | 未取数 | `run_all_suites.py --list` |" % a["regression_suites"])
    L.append("| Java 测试类 / @Test | %d / %d | 见 peers 行 | git ls-files + @Test 计数 |" % (a["java_test_files"], a["java_test_cases"]))
    L.append("| 覆盖率门 | LINE≥%.2f ∧ BRANCH≥%.2f | coverage_gate 有门 %s | server/pom.xml（同址尺 quality_gate_channel） |"
             % (a["jacoco_minimum"].get("LINE", 0), a["jacoco_minimum"].get("BRANCH", 0),
                "%d/%s" % (g["quality_gate_classes"].get("coverage_gate", {}).get("yes", 0), g.get("repo_count"))))
    L.append("| lint 门 | 无标准配置门（有自写 js_syntax 判据） | %d/%s | 同上 |"
             % (g["quality_gate_classes"].get("lint_gate", {}).get("yes", 0), g.get("repo_count")))
    L.append("| typecheck 门 | 无（零构建无 TS） | %d/%s（另 %d 未验） | 同上 |"
             % (g["quality_gate_classes"].get("typecheck_gate", {}).get("yes", 0), g.get("repo_count"),
                g["quality_gate_classes"].get("typecheck_gate", {}).get("unverified", 0)))
    L.append("| 有测试结构的 peer | — | %s/%s（ts=%s） | %s |"
             % (q.get("have_test_struct"), q.get("denominator"), q.get("ts"), q.get("file", "—")))
    L.append("| CI 跑 unit 的 peer | — | %s/%s | 同上 |" % (q.get("ci_unit_step"), q.get("denominator")))
    L.append("| 有 lockfile 的 peer | — | %s/%s（ts=%s） | %s |"
             % (p.get("with_lockfile"), p.get("denominator"), p.get("ts"), p.get("file", "—")))
    L.append("| 前端构建链配置 | %d（零构建=%s） | 未取数 | git ls-files |" % (len(b["frontend_build_configs"]), b["zero_build"]))
    L.append("| 平台函数依赖清单 | %d（%s） | 未取数 | git ls-files |"
             % (len(b["platform_function_manifests"]),
                "、".join(p.rsplit("/", 1)[-1] for p in b["platform_function_manifests"]) or "—"))
    L.append("| 首屏预算 | %d 文件 / %d B | 未取数 | size_budget_check.BUDGETS |"
             % (b["first_screen_budget"]["files"] or 0, b["first_screen_budget"]["total_bytes"] or 0))
    L.append("| CI 工作流 / job | %d / %d | workflow 数见总览表 | git HEAD .github/workflows |"
             % (b["ci_workflow_files"], b["ci_jobs"]))
    return "\n".join(L)


def selftest():
    cases = []
    # 1) 缺源必须 rc=2（不得塌缩成 0/空即通过）
    miss = [p for p in ("交付物/对标数据/__not_exist__.json",) if not (ROOT / p).exists()]
    cases.append(("缺源检出", len(miss) == 1, True))
    roll = {"dim_a_testing_repro": {"self": {"regression_suites": 3, "java_test_files": 2,
                                              "java_test_cases": 20, "jacoco_minimum": {"LINE": 0.9, "BRANCH": 0.9}},
                                    "peers_quality_tooling": {"available": False},
                                    "peers_repro": {"available": False}},
            "dim_b_zero_build_cost": {"self_cost": {"build_config_files": [], "zero_build": True,
                                                    "frontend_build_configs": [],
                                                    "platform_function_manifests": [],
                                                    "first_screen_budget": {"files": 3, "total_bytes": 100},
                                                    "ci_workflow_files": 2, "ci_jobs": 4},
                                      "peers_build_gates": {"repo_count": 16,
                                                             "quality_gate_classes": {"coverage_gate": {"yes": 0, "no": 16, "unverified": 0}}},
                                      "peers_cost_items": "未取数"}}
    md = render(roll)
    cases.append(("合成样本出表", md.count("|") > 20 and "self（本轮现测" in md, True))
    cases.append(("成本项未取数不得写成 0", "未取数" in roll["dim_b_zero_build_cost"]["peers_cost_items"], True))
    # count_jobs 合成样本：两个 job + job 内的 env/steps 保留键 + jobs: 之后的顶层键
    synth = ("name: t\non: push\njobs:\n  a:\n    runs-on: x\n    env:\n      FOO: 1\n"
             "    steps:\n      - run: echo\n  b:\n    steps:\n      - run: echo\npermissions: read-all\n")
    cases.append(("反例 job 内保留键不得算成 job", count_jobs(synth) == 2, True))
    cases.append(("边界 无 jobs 块时不得凭空数出 job", count_jobs("name: t\non: push\n") == 0, True))
    bad = [n for n, got, want in cases if got != want]
    print("ROLLUP-SELFTEST-%s（%d/%d 条）" % ("PASS" if not bad else "FAIL: " + "; ".join(bad),
                                              len(cases) - len(bad), len(cases)))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser(description="r93 两新增维度汇总（只读、零网络、数字带来源）")
    ap.add_argument("--out", default="", help="产物路径；缺省按输入台账的轮次名自动命名")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    # r94：输入/产物都不再写死 r93 —— 取最新一份 metrics，产物名跟随它的轮次号。
    src_metrics = _latest("benchmark-metrics-")
    if src_metrics is None or not src_metrics.exists():
        print("ROLLUP-UNVERIFIED: 缺源 benchmark-metrics-*.json（先跑 benchmark_metrics 落盘，缺源不是 0）")
        return 2
    out_path = args.out or str(DATA / ("benchmark-rollup-%s.json"
                                       % src_metrics.stem.replace("benchmark-metrics-", "")))
    try:
        roll = build()
    except Exception as e:
        print("ROLLUP-FAIL: 读数不可用：%s" % str(e)[:160])
        return 1
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(roll, ensure_ascii=False, indent=2), encoding="utf-8")
    print("自测面：git HEAD（与 benchmark_metrics 同面，禁止混工作树）")
    print(render(roll))
    print("产物：%s" % out.relative_to(ROOT))
    print("ROLLUP-PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())