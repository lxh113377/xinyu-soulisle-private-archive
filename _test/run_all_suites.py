# -*- coding: utf-8 -*-
"""全量回归电池：逐套件直取 rc，聚合零掩盖（audit-runner-safe-agents 范式：每项独立记录，不看 any）"""
import subprocess, sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8123"
# 判定行形状：各套件统一以 <NAME>-PASS / -FAIL / -CLEAN / UNVERIFIED 收尾
VERDICT_RE = re.compile(r"(?:PASS|FAIL|CLEAN|UNVERIFIED|OK)\b")

SUITES = [
    # 前置探针放第一条：r35 实测 jar 中途掉线一次报 5 条红，逐条归因花了三轮命令。
    ("preflight", [sys.executable, "_test/server_preflight.py"]),
    ("deploy_sync", [sys.executable, "_test/deploy_sync_check.py"]),
    # r36：行尾确定性 —— 让「逐字节 / SHA256 / 字节预算」类主张在他人 clone 上也成立
    ("eol_parity", [sys.executable, "_test/eol_parity_check.py"]),
    ("eol_parity_selftest", [sys.executable, "_test/eol_parity_check.py", "--selftest"]),
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
    ("settings_panel", [sys.executable, "_test/settings_panel_check.py"]),
    ("settings_panel_selftest", [sys.executable, "_test/settings_panel_check.py", "--selftest"]),
    ("offline_shell", [sys.executable, "_test/offline_shell_check.py"]),
    ("offline_shell_selftest", [sys.executable, "_test/offline_shell_check.py", "--selftest"]),
    ("pdf_leak_scan", [sys.executable, "_test/pdf_leak_scan.py"]),
    ("pdf_leak_selftest", [sys.executable, "_test/pdf_leak_scan.py", "--selftest"]),
    # r35：CI 的密钥门禁原先内联在 ci.yml，本地扫不到 ⇒ "被跟踪文件含密钥形态"只有 CI 红。
    # 现在两侧共用这一条判据（正则只实现一处），本地也进电池。
    ("tracked_secret", [sys.executable, "_test/tracked_secret_scan.py"]),
    ("tracked_secret_selftest", [sys.executable, "_test/tracked_secret_scan.py", "--selftest"]),
    # r37：本机 `git ls-files` 干净 ≠ **远端树**干净（.gitignore 不撤销已推送的东西，
    # 而评委看到的是远端）⇒ 另起一条扫 origin 默认分支的文件树
    ("remote_tree", [sys.executable, "_test/remote_tree_audit.py"]),
    ("remote_tree_selftest", [sys.executable, "_test/remote_tree_audit.py", "--selftest"]),
    ("ci_status", [sys.executable, "_test/ci_status_check.py"]),
    ("ci_status_selftest", [sys.executable, "_test/ci_status_check.py", "--selftest"]),
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
    # r38：输入侧护栏必须"真的在拦"（注入 6 例点名 + 正常 6 例不误伤，含 2 例近似误伤）
    ("safety_guard", [sys.executable, "_test/safety_guard_check.py", BASE]),
    ("safety_guard_selftest", [sys.executable, "_test/safety_guard_check.py", "--selftest"]),
    ("voice", [sys.executable, "_test/voice_check.py", BASE]),
    # r35：voice 的"CI 无麦克风 ⇒ SKIP"降级必须是纯函数且带边界反例，否则降级会吞掉真缺陷
    ("voice_selftest", [sys.executable, "_test/voice_check.py", "--selftest"]),
    ("browser_check", [sys.executable, "_test/browser_check.py"]),
    ("pixel_dual", [sys.executable, "_test/pixel_dual_check.py"]),
    ("lightshow", [sys.executable, "_test/lightshow_check.py"]),
    ("online_check", [sys.executable, "_test/online_check.py"]),
    ("public_check", [sys.executable, "_test/public_check.py"]),
    ("live_sync", [sys.executable, "_test/live_sync_check.py"]),
    ("emotion_eval_js", ["node", "_test/emotion_eval.js"]),
]

# 需要真实上游密钥的套件：本地默认跑（回归环境契约要求 DEEPSEEK_KEY 在进程环境里），
# CI runner 上没有密钥 ⇒ 只能显式豁免，且豁免必须被 G10 复核（见 repo_config_check.py）
# 需要真实上游密钥的三条：本地默认跑（回归环境契约要求 DEEPSEEK_KEY 在进程环境里），
# CI runner 上没有密钥 ⇒ 只能显式豁免，且豁免必须被 G10 复核。
# online_check 也在其中：它断言的就是「对话走了在线模型」，无密钥时该断言必然红 ——
# 放宽它等于把这条判据作废（r28 CI 等效复现实测：它在无密钥环境报 6 条 500，
# 那 500 是契约内响应，但"必须出现 在线大模型生成"这一条本就不可能在无密钥环境成立）。
LLM_SUITES = {"j2_chat_contract", "stream_contract", "online_check"}

# r22 加：`--only <子串>` / `--slice <起> <止>` 分段取数。
# ⚠️ 本版第一稿是**死代码**（先滤掉 "--" 开头的参数再判 args[0] == "--slice"，永不命中），
#    跑 "--slice 0 14" 却把 28 条全跑了个遍 —— "配了开关但开关没生效"正是本轮 repo_config 判据要防的那类事，
#    结果自己又踩了一次。故此处直接按 sys.argv 原样解析，并由 --list 提供可复核的"过滤后到底剩几条"。
USAGE = """run_all_suites.py — 全量回归电池（SUITES 是条数唯一真相源）
  --list             只打印套件总数（供别的判据对账）
  --exclude-llm      跳过需要真实上游密钥的套件（CI 用；豁免条数由恒等式自证）
  --only <子串>      只跑名字含该子串的套件
  --slice <起> <止>  按下标分段取数（长电池分段跑，避免撞调用方超时）
  -h, --help         本说明
未知开关一律拒（rc=2）：开关打错字若被静默忽略，会把"子集全绿"印成"全量全绿"。"""

KNOWN_FLAGS = {"--list", "--exclude-llm", "--only", "--slice", "--help", "-h"}


def main():
    global SUITES
    argv = sys.argv[1:]
    if "--help" in argv or "-h" in argv:
        print(USAGE)
        return 0
    # 未知开关 fail-closed：r36 实测 `--help` 被静默忽略 ⇒ 直接把 43 条全跑了一遍，
    # 而 `--onl selftest` 这类打错字的过滤同样会跑成全量并打印 ALL-GREEN。
    unknown = [a for a in argv if a.startswith("-") and a not in KNOWN_FLAGS]
    if unknown:
        print("BATTERY-FAIL: 未知开关 %s（可用：--list/--exclude-llm/--only/--slice/--help）"
              % " ".join(unknown))
        return 2
    if "--list" in argv:
        print("SUITES:", len(SUITES))
        return 0
    if "--exclude-llm" in argv:
        # CI runner 没有真实上游密钥（密钥不落仓，见 CONTRIBUTING），这两条必须走在线链路才能判绿。
        # 关键约束：**踢掉谁必须点名 + 恒等式**，否则"CI 全绿"会被读成"33 条都跑过了"（同行踩过：装了等于没装）。
        drop = [s for s in SUITES if s[0] in LLM_SUITES]
        SUITES = [s for s in SUITES if s[0] not in LLM_SUITES]
        print(f"(--exclude-llm → 实跑 {len(SUITES)} + 豁免 {len(drop)} == 总数 {len(SUITES) + len(drop)}；"
              f"豁免={[s[0] for s in drop]}，原因=runner 无上游密钥)")
        if not drop:
            print("BATTERY-FAIL: --exclude-llm 却零豁免 ⇒ 豁免名单与实际套件漂移，判据失效")
            return 1
    if "--only" in argv:
        i = argv.index("--only")
        if i + 1 >= len(argv):
            print("BATTERY-FAIL: --only 缺子串操作数")
            return 2
        key = argv[i + 1]
        SUITES = [s for s in SUITES if key in s[0]]
        print(f"(--only {key!r} → {len(SUITES)} 条)")
    if "--slice" in argv:
        i = argv.index("--slice")
        if i + 2 >= len(argv):
            print("BATTERY-FAIL: --slice 需要两个下标（起 止）")
            return 2
        total = len(SUITES)
        lo, hi = int(argv[i + 1]), int(argv[i + 2])
        # 越界下标在 Python 里是静默截断（`--slice 99 120` → 空集），必须点名：
        # 分段跑时"这一条都没跑"不能被印成"这段全绿"
        if not (0 <= lo < hi <= total):
            print(f"BATTERY-FAIL: --slice {lo}:{hi} 越界（套件总数 {total}）")
            return 2
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
        # 聚合器只留最后一行 ⇒ 判据说 FAIL 却答不出"哪一条 FAIL"，等于没判（r28 CI 实测踩到）。
        # 现在：rc≠0 时把该套件的 FAIL/🔴/异常行原样带出来；成功仍是一行，不制造噪声。
        # 摘要行改取"最后一条判定行"而非"最后一行"：r36 实测 strategy_selftest 在 PASS 后
        # 还打印注入反例清单，摘要于是显示 `· 热线清单需 ≥3 条，实际 []` —— rc=0 却像报错。
        detail = []
        if p.returncode != 0 and tail:
            keys = ("FAIL", "🔴", "Error", "error:", "Traceback", "SKIP")
            hit = [x.strip()[:170] for x in tail if any(k in x for k in keys)]
            detail = hit or tail[-6:]
        line = next((x for x in reversed(tail) if VERDICT_RE.search(x)),
                    tail[-1] if tail else "")
        results.append((name, p.returncode, (line[:110] if tail else (p.stderr or "").strip()[:110])))
        print(f"{name:22s} rc={p.returncode} | {results[-1][2]}")
        for d in detail:
            print(" " * 25 + "· " + d)

    bad = [r for r in results if r[1] != 0]
    # 收口行必须把"判红"与"环境未验（rc=2）"分开印：r35 实证 ci_status 长期挂红，
    # 起因是账单阻塞（rc=2），计费恢复后变成代码级失败（rc=1）——**原因换了，行没换**，
    # 于是连续 5 次 push 带着真红出门，而电池摘要看上去和上周一样。
    # ⚠️ 三类而不是两类：本轮第一版把"非 1 即环境"写死，随即被自己的输出证伪 ——
    #    voice 两条套件硬崩（rc=0xC0000409、stdout 全空）被判成"环境未验"，等于给崩溃发了通行证。
    hard = [b[0] for b in bad if b[1] == 1]
    soft = [b[0] for b in bad if b[1] == 2]
    crash = [(b[0], b[1]) for b in bad if b[1] not in (1, 2)]
    parts = []
    if hard:
        parts.append("RED(判红，必须修): " + ",".join(hard))
    if soft:
        parts.append("ENV-UNVERIFIED(不是判红，但不得声称已验): " + ",".join(soft))
    if crash:
        parts.append("CRASH(判据自身崩溃，既不是判红也不是环境，必须查): "
                     + ",".join("%s=0x%08x" % (n, c & 0xFFFFFFFF) for n, c in crash))
    tail_msg = "ALL-GREEN" if not parts else "  |  ".join(parts)
    print("=" * 60)
    print(f"BATTERY: {len(results) - len(bad)}/{len(results)} rc=0", tail_msg)
    return 1 if bad else 0


if __name__ == "__main__":
    # 守卫必须有：r26 前本文件是**顶层直跑**，任何 `import run_all_suites` 都会把 29 条套件重跑一遍
    # （聚合 runner 最该 import-safe，因为别的判据会拿它的 SUITES 做对账）。
    sys.exit(main())
