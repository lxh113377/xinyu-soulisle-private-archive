# -*- coding: utf-8 -*-
"""全量回归电池：逐套件直取 rc，聚合零掩盖（audit-runner-safe-agents 范式：每项独立记录，不看 any）"""
import subprocess, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8123"

SUITES = [
    ("deploy_sync", [sys.executable, "_test/deploy_sync_check.py"]),
    ("size_budget", [sys.executable, "_test/size_budget_check.py"]),
    ("size_budget_selftest", [sys.executable, "_test/size_budget_check.py", "--selftest"]),
    ("emotion_wiring", [sys.executable, "_test/emotion_wiring_check.py"]),
    ("emotion_wiring_selftest", [sys.executable, "_test/emotion_wiring_check.py", "--selftest"]),
    ("vendor_freshness", [sys.executable, "_test/vendor_freshness_check.py"]),
    ("vendor_freshness_selftest", [sys.executable, "_test/vendor_freshness_check.py", "--selftest"]),
    ("benchmark_selftest", [sys.executable, "_test/benchmark_metrics.py", "--selftest"]),
    ("api_contract", [sys.executable, "_test/api_contract_check.py"]),
    ("api_contract_selftest", [sys.executable, "_test/api_contract_check.py", "--selftest"]),
    ("patch_apply_selftest", [sys.executable, "_test/patch_apply.py", "--selftest"]),
    ("repo_config", [sys.executable, "_test/repo_config_check.py"]),
    ("repo_config_selftest", [sys.executable, "_test/repo_config_check.py", "--selftest"]),
    ("engine_consistency", [sys.executable, "_test/engine_consistency_check.py"]),
    ("strategy", [sys.executable, "_test/strategy_check.py"]),
    ("strategy_selftest", [sys.executable, "_test/strategy_check.py", "--selftest"]),
    ("ux_guards", [sys.executable, "_test/ux_guards_check.py"]),
    ("j2_chat_contract", [sys.executable, "_test/j2_chat_contract.py"]),
    ("j4_memory", [sys.executable, "_test/j4_memory_check.py"]),
    ("j4_remote_down", [sys.executable, "_test/j4_remote_down_check.py"]),
    ("stream_contract", [sys.executable, "_test/stream_contract.py"]),
    ("voice", [sys.executable, "_test/voice_check.py", BASE]),
    ("browser_check", [sys.executable, "_test/browser_check.py"]),
    ("pixel_dual", [sys.executable, "_test/pixel_dual_check.py"]),
    ("lightshow", [sys.executable, "_test/lightshow_check.py"]),
    ("online_check", [sys.executable, "_test/online_check.py"]),
    ("public_check", [sys.executable, "_test/public_check.py"]),
    ("live_sync", [sys.executable, "_test/live_sync_check.py"]),
    ("emotion_eval_js", ["node", "_test/emotion_eval.js"]),
]

# r22 加：`--only <子串>` / `--slice <起> <止>` 分段取数。
# ⚠️ 本版第一稿是**死代码**（先滤掉 "--" 开头的参数再判 args[0] == "--slice"，永不命中），
#    跑 "--slice 0 14" 却把 28 条全跑了个遍 —— "配了开关但开关没生效"正是本轮 repo_config 判据要防的那类事，
#    结果自己又踩了一次。故此处直接按 sys.argv 原样解析，并由 --list 提供可复核的"过滤后到底剩几条"。
def main():
    global SUITES
    argv = sys.argv[1:]
    if "--list" in argv:
        print("SUITES:", len(SUITES))
        return 0
    if "--only" in argv:
        key = argv[argv.index("--only") + 1]
        SUITES = [s for s in SUITES if key in s[0]]
        print(f"(--only {key!r} → {len(SUITES)} 条)")
    if "--slice" in argv:
        i = argv.index("--slice")
        lo, hi = int(argv[i + 1]), int(argv[i + 2])
        SUITES = SUITES[lo:hi]
        print(f"(--slice {lo}:{hi} → {len(SUITES)} 条)")
    if not SUITES:
        print("BATTERY-FAIL: 过滤后零套件（空跑出来的全绿没有意义，禁止把 0/0 当通过）")
        return 1

    results = []
    for name, cmd in SUITES:
        p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=600)
        tail = (p.stdout or "").strip().splitlines()
        results.append((name, p.returncode, tail[-1][:110] if tail else (p.stderr or "").strip()[:110]))
        print(f"{name:22s} rc={p.returncode} | {results[-1][2]}")

    bad = [r for r in results if r[1] != 0]
    print("=" * 60)
    print(f"BATTERY: {len(results) - len(bad)}/{len(results)} rc=0", "ALL-GREEN" if not bad else "RED: " + ",".join(b[0] for b in bad))
    return 1 if bad else 0


if __name__ == "__main__":
    # 守卫必须有：r26 前本文件是**顶层直跑**，任何 `import run_all_suites` 都会把 29 条套件重跑一遍
    # （聚合 runner 最该 import-safe，因为别的判据会拿它的 SUITES 做对账）。
    sys.exit(main())
