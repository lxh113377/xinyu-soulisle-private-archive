# -*- coding: utf-8 -*-
"""全量回归电池：逐套件直取 rc，聚合零掩盖（audit-runner-safe-agents 范式：每项独立记录，不看 any）

版本: V1.41.0（2026-09-27 r41）——两条新机制都在本版落地：
  · `fold_detail()`：判据 rc≠0 时除"含判据词的行"外，还带出其后的 `-` 续行与 stderr 末两行
    （实证动因：`voice` 判红时收口面只剩一行 `VOICE-FAIL`，原因行没有 token 就被折叠掉）；
  · 整跑并发锁（`acquire_lock`/`lock_state`，TTL 1800s）：电池不可重入，并跑的第二条一律
    `rc=2 未验`——不给绿，也不产出一条无法归因的红。两者均由 `--selftest` 双向自证（11 类桩）。
"""
import subprocess, sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8123"
# 判定行形状：各套件统一以 <NAME>-PASS / -FAIL / -CLEAN / UNVERIFIED 收尾
VERDICT_RE = re.compile(r"(?:PASS|FAIL|CLEAN|UNVERIFIED|OK)\b")

# 并发锁 TTL（秒）：整跑一遍实测约 10 分钟，留 3 倍余量；被 kill 掉的运行靠它自愈。
LOCK_TTL = 1800

SUITES = [
    # 前置探针放第一条：r35 实测 jar 中途掉线一次报 5 条红，逐条归因花了三轮命令。
    ("preflight", [sys.executable, "_test/server_preflight.py"]),
    # r40：性能面从"未实测"变成有数有棘轮。阈值按本机三轮实测 p95 放宽 ~16-25 倍，
    # 只防塌方级退化（直读变落库 / 线程池打满 / 危机路径开始打 LLM），不防抖动 ⇒ 才有资格进阻断链。
    ("perf_baseline", [sys.executable, "_test/perf_baseline_check.py", BASE]),
    ("perf_baseline_selftest", [sys.executable, "_test/perf_baseline_check.py", "--selftest"]),
    # r40c：报告里的「不可比 / 受限于 / 仅保证」类边界结论必须自带取证口径（M5⑫ 的执行器）。
    # 首跑就在自己的报告里点名一处 r35 遗留（无可比口径 无取证），修文案后才转绿 ⇒ 判据非装饰。
    ("disclaimer_forensics", [sys.executable, "_test/disclaimer_forensics_lint.py", "--all"]),  # r41: 分母改从目录现读
    ("disclaimer_forensics_selftest", [sys.executable, "_test/disclaimer_forensics_lint.py", "--selftest"]),
    # r40c：push 后的 CI 看守。只把**纯判定桩**接进阻断链（真跑要联网查 gh，不属回归面）。
    ("ci_watch_selftest", [sys.executable, "_test/ci_watch.py", "--selftest"]),
    # r41：整跑不可重入（并跑互踩出无法归因的红，本轮实测两次）⇒ 锁的判定桩入链
    ("battery_lock_selftest", [sys.executable, "_test/run_all_suites.py", "--selftest"]),
    # r40d：交付物 PDF 的「官方九项齐全」从人眼对照升级为机器断言（分母取自大纲，不手抄）。
    ("plan_pdf_coverage", [sys.executable, "_test/plan_pdf_coverage_check.py"]),
    ("plan_pdf_coverage_selftest", [sys.executable, "_test/plan_pdf_coverage_check.py", "--selftest"]),
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
    # r41：对标测试资产面量出 in-build 单测 0/16 vs peers 9/16；探针本体不入电池（16 仓 API 不划算，
    # 承 r37 口径），但它的**匹配器自证**纯本地零网络，进阻断链盯住"把依赖目录当用例"这类灌水。
    ("testasset_selftest", [sys.executable, "_test/peer_test_asset_probe.py", "--selftest"]),
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
    # r41：in-build 门禁的守卫。T4 专门盯"CI 构建步有没有被加上 -DskipTests"——
    # 加了的话 java-build 照样全绿，而构建期单测已经静默不存在（本地看永远是"CI 通过"）。
    ("java_test_guard", [sys.executable, "_test/java_test_guard.py"]),
    ("java_test_guard_selftest", [sys.executable, "_test/java_test_guard.py", "--selftest"]),
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
  --selftest         只验并发锁判定桩（零网络、零套件）
  -h, --help         本说明
未知开关一律拒（rc=2）：开关打错字若被静默忽略，会把"子集全绿"印成"全量全绿"。
整跑不可重入：并发的第二条一律 rc=2 未验（r41 实测并跑会互踩出无法归因的红）。"""

KNOWN_FLAGS = {"--list", "--exclude-llm", "--only", "--slice", "--selftest", "--help", "-h"}


def lock_state(data, now, ttl, mypid):
    """纯函数：判定这把锁该不该拦。返回 (可继续?, 原因)。

    判据（宁可放行也不误拦，但**读到别人的活锁必须拒绝**）：
      · 空/不可解析          → 放行（旧版本写的锁或半截写，不能因此卡死回归）
      · pid == 自己         → 放行并接管（同进程重入，或上次没清干净）
      · now - start > ttl   → 放行（陈旧锁：被 kill 掉的运行不会自己删）
      · 别人的、且没过期     → 拒绝
    """
    try:
        pid_s, start_s = data.strip().split("\t")
        pid, start = int(pid_s), float(start_s)
    except Exception:
        return True, "锁内容不可解析 ⇒ 放行（但会在收口行点名）"
    if pid == mypid:
        return True, "自己的锁 ⇒ 接管"
    if now - start > ttl:
        return True, "锁已过期 %ds ⇒ 视为陈旧" % int(now - start)
    return False, "另一台进程(pid=%d)起于 %ds 前，未到 TTL %ds" % (pid, int(now - start), ttl)


def lock_selftest():
    """双向自证：该拦的要拦住，不该拦的（自己的/陈旧的/半截的）绝不拦。"""
    cases = [
        ("正例 空文件放行", lock_state("", 1000.0, LOCK_TTL, 7)[0], True),
        ("正例 自己的锁放行", lock_state("7\t999.0", 1000.0, LOCK_TTL, 7)[0], True),
        ("正例 陈旧锁放行", lock_state("8" + chr(9) + "1.0", 10000.0, LOCK_TTL, 7)[0], True),
        ("反例 别人的活锁必须拦", lock_state("8\t999.5", 1000.0, LOCK_TTL, 7)[0], False),
        ("边界 半截内容不得判拦", lock_state("garbage", 1000.0, LOCK_TTL, 7)[0], True),
        ("边界 零输入不得判绿成脏", lock_state("\t", 1000.0, LOCK_TTL, 7)[0], True),
    ]
    bad = [n for n, got, want in cases if got != want]
    print("LOCK-SELFTEST-%s（%d/%d 类桩）"
          % ("PASS" if not bad else "FAIL: " + "; ".join(bad), len(cases) - len(bad), len(cases)))
    return 1 if bad else 0


HIT_KEYS = ("FAIL", "🔴", "Error", "error:", "Traceback", "SKIP")


def fold_detail(out_lines, err_text, rc):
    """rc≠0 时该把哪些证据带进收口行。纯函数，可自证。

    三条都是被真实红逼出来的（r41 实测 `voice` 只剩一行 `VOICE-FAIL`，原因在下一行的
    `  - A4 ...` 里）：
      ① 含判据词的行本身；
      ② 紧跟其后的 `-` 续行 —— 很多判据是「标题行带 FAIL，原因逐条列在下面」的形状，
         只挑①就恰好把**最有用的那几行**丢掉（与 r40b「被折叠掉的观测面」同族）；
      ③ stderr 末两行 —— 判据崩在异常里时 stdout 可能一个 token 都没有，
         原先 stdout 非空就完全不读 stderr ⇒「崩了」被读成「没原因」。
    """
    if rc == 0:
        return []
    hits = []
    for i, x in enumerate(out_lines):
        if any(k in x for k in HIT_KEYS):
            hits.append(x.strip()[:170])
            for y in out_lines[i + 1:i + 6]:
                if y.strip().startswith("-"):
                    hits.append(y.strip()[:170])
                else:
                    break
    if not hits:
        hits = [x.strip()[:170] for x in out_lines[-6:]]
    if err_text:
        tail_err = [x.strip()[:170] for x in err_text.strip().splitlines() if x.strip()][-2:]
        hits += ["stderr: " + x for x in tail_err]
    return hits


def fold_selftest():
    """双向自证：续行要带出来、零续行不得乱带、rc=0 一律不印、崩溃必须露 stderr。"""
    out = ["VOICE-FAIL", "  - A4 未观察到监听态", "  - A7 无音频设备", "SOME-OTHER rc=0",
           "  - 不该被带出的邻居"]
    cases = [
        ("续行被带出", len([x for x in fold_detail(out, "", 1) if "A4" in x]), 1),
        ("邻居不越界", any("邻居" in x for x in fold_detail(out, "", 1)), False),
        ("rc=0 一律不印", fold_detail(out, "boom", 0), []),
        ("崩溃露 stderr", any(x.startswith("stderr: boom") for x in
                            fold_detail(["无 token 的一行"], "boom\nsecond", 1)), True),
        ("无 token 退化为末六行", fold_detail(["a", "b"], "", 1)[-1], "b"),
    ]
    bad = ["%s got=%r want=%r" % (n, g, w) for n, g, w in cases if g != w]
    print("FOLD-SELFTEST-%s（%d/%d 类桩）"
          % ("PASS" if not bad else "FAIL: " + "; ".join(bad), len(cases) - len(bad), len(cases)))
    return 1 if bad else 0


def acquire_lock():
    """整跑电池不是可重入的：两条链同时打同一个 jar + 同一个上游会互相踩出假红
    （r41 实测两次：`emotion_wiring` 与 `live_sync` 在并发窗口里判红，单独复跑均 PASS）。
    所以并发时**拒绝第二次**，而不是让它产出一条无法归因的红。"""
    import hashlib
    import os
    import time
    key = hashlib.sha1(str(ROOT).encode("utf-8")).hexdigest()[:12]
    path = Path(os.environ.get("TEMP") or "/tmp") / ("xinyu_battery_%s.lock" % key)
    now = time.time()
    if path.exists():
        try:
            data = path.read_text("utf-8", errors="replace")
        except Exception as e:
            data = ""
        ok, why = lock_state(data, now, LOCK_TTL, os.getpid())
        if not ok:
            return path, "BATTERY-UNVERIFIED(并发): " + why + " ｜ 要并跑请改目录或用 --only 子集"
    path.write_bytes(("%d\t%.3f" % (os.getpid(), now)).encode("utf-8"))
    return path, None


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
    if "--selftest" in argv:
        rc1 = lock_selftest()
        rc2 = fold_selftest()
        print("BATTERY-SELFTEST-%s（锁 %s ＋ 折叠 %s）"
              % ("PASS" if not (rc1 | rc2) else "FAIL", "ok" if not rc1 else "红",
                 "ok" if not rc2 else "红"))
        return 1 if (rc1 | rc2) else 0
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

    lock, why = acquire_lock()
    if why:
        # 2 = 未验，不是 1：并发不是"代码坏了"，但也绝不是一块没跑完的绿
        print(why)
        return 2

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
            detail = fold_detail(tail, p.stderr, p.returncode)
        elif p.returncode != 0:
            detail = fold_detail([], p.stderr, p.returncode)
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
    try:
        lock.unlink()
    except Exception:
        pass
    return 1 if bad else 0


if __name__ == "__main__":
    # 守卫必须有：r26 前本文件是**顶层直跑**，任何 `import run_all_suites` 都会把 29 条套件重跑一遍
    # （聚合 runner 最该 import-safe，因为别的判据会拿它的 SUITES 做对账）。
    sys.exit(main())
