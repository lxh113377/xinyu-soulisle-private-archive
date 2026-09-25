# -*- coding: utf-8 -*-
"""静态资源体积预算守卫（对标 LobeChat CI size-limit 的零依赖版）

动机：心屿首屏优势 = 零构建 + 本地 vendor；这份优势同样脆弱——
往 src 里多加一个大依赖/忘压缩一个文件，首屏就悄悄退化，且没有任何门禁拦得住。
本脚本把「体积不回涨」变成机器红线：逐文件预算 + 关键路径总预算。

预算来源：2026-09-25 实测基线 + 5% 余量（写死在 BUDGETS，改预算必须在 PR/日志说明理由）。
判据三态：0=BUDGET-PASS 1=超限 2=文件缺失（缺文件不是"通过"）。
--selftest：把预算临时压到实际值的 90%，必须**逐项报红**，否则判据恒真（R247 对照组）。
"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]

# (相对路径, 预算 bytes)。总预算 = 首屏关键路径：index.html + style.css + 全部 js + data + vendor
# ⚠️ 本表必须**全覆盖**首屏源文件（下方 coverage() 机器强制）：r20 实测发现原 13 文件表
#    漏登记了 src/data/emotion-strategy.js（4,720B），新增 emotion-remote.js 也不会被自动纳入
#    —— 「逐文件预算」若靠手工维护，加文件这条最常见的退化路径恰好绕过门禁。
BUDGETS = {
    "src/index.html": 9_936,   # r28 上调：加了离线壳注册块（9,463 实测 +5%），理由记在 CHANGELOG
    "src/css/style.css": 13_368,
    "src/js/app.js": 13_780,
    "src/js/chat-agent.js": 11_729,
    "src/js/emotion-engine.js": 5_598,
    "src/js/emotion-remote.js": 4_679,
    "src/js/voice.js": 4355,
    "src/js/chart.js": 3969,
    "src/js/chat-window.js": 5845,
    "src/js/settings.js": 3000,
    "src/sw.js": 4814,
    "src/js/scroll-story.js": 3_757,
    "src/js/three-scene.js": 15_793,
    "src/js/memory-store.js": 4_844,
    "src/js/demo-config.js": 1_828,
    "src/data/emotion-lexicon.js": 4_042,
    "src/data/emotion-strategy.js": 4_956,
    "src/vendor/three.min.js": 633_617,
    "src/vendor/gsap.min.js": 75_825,
    "src/vendor/ScrollTrigger.min.js": 45_549,
}
TOTAL_KEY_PATH = 858_752  # 首屏关键路径总预算（含 vendor），2026-09-25 实测 817,859B + 5%

# 参与覆盖校验的目录（src/functions 是 Pages Function 服务端源码，不在首屏路径）
COVER_DIRS = ("src/js", "src/css", "src/data", "src/vendor")
COVER_ROOT = ("src",)   # r28：src 根目录也有首屏件（sw.js），不纳入就等于给"新增文件绕过预算"留口子


def coverage():
    """返回 (未登记预算的新文件, 表里已不存在的死条目)。"""
    on_disk = set()
    for d in COVER_DIRS:
        for p in (ROOT / d).glob("*"):
            if p.is_file() and p.suffix in (".js", ".css", ".html"):
                on_disk.add(p.relative_to(ROOT).as_posix())
    html = "src/index.html"
    if (ROOT / html).exists():
        on_disk.add(html)
    for d in COVER_ROOT:
        for p in (ROOT / d).glob("*.js"):
            on_disk.add(p.relative_to(ROOT).as_posix())
    # demo-config.js：src 版含本机 Key 且被 .gitignore，两端形态本就不同 ⇒ 两侧都排除，
    # 只做「存在则测预算」，不参与「必须登记」的覆盖对账
    on_disk.discard("src/js/demo-config.js")
    declared = set(BUDGETS) - {"src/js/demo-config.js"}
    unregistered = sorted(on_disk - declared)
    stale = sorted(declared - on_disk)
    return unregistered, stale


def measure():
    rows, total, missing = [], 0, []
    for rel, budget in BUDGETS.items():
        f = ROOT / Path(rel)
        if not f.exists():
            # demo-config.js 被 .gitignore 排除（真身含本机 Key）→ 全新 clone 缺席是常态，
            # 记警告并按"其公网 stub 不会超预算"放行；其余文件缺席 = 环境异常 rc=2。
            if rel == "src/js/demo-config.js":
                print(f"  WARN  {rel} 缺席（gitignore 本机件），本项跳过预算")
            else:
                missing.append(rel)
            continue
        size = f.stat().st_size
        total += size
        rows.append((rel, size, budget))
    return rows, total, missing


def run(scale=1.0):
    rows, total, missing = measure()
    if missing:
        print(f"BUDGET-ENV-FAIL: 缺失文件 {missing}")
        return 2
    red = 0
    for rel, size, budget in sorted(rows, key=lambda r: -r[1]):
        b = int(budget * scale)
        ok = size <= b
        if not ok:
            red += 1
        print(f"  {'OK ' if ok else 'OVER'}  {rel:36s} {size:8,d} / {b:8,d}")
    tb = int(TOTAL_KEY_PATH * scale)
    ok_total = total <= tb
    if not ok_total:
        red += 1
    print(f"  {'OK ' if ok_total else 'OVER'}  {'TOTAL(关键路径)':36s} {total:8,d} / {tb:8,d}")
    if red:
        print(f"BUDGET-FAIL: {red} 项超预算")
        return 1
    print(f"BUDGET-PASS: {len(rows)} 文件 + 总预算全在限内（total={total:,d}）")
    return 0


if __name__ == "__main__":
    unreg, stale = coverage()
    if "--selftest" in sys.argv:
        # 覆盖判据自证：从表里抽掉一个真实存在的文件，coverage 必须抓到（否则恒真）
        probe = "src/js/emotion-remote.js"
        BUDGETS.pop(probe, None)
        caught = probe in coverage()[0]
        rc = run(scale=0.90)
        if rc == 1 and caught:
            print("✅ SELFTEST-PASS：压缩预算逐项报红 + 漏登记文件被 coverage 抓到 ⇒ 两判据非恒真")
            sys.exit(0)
        print(f"🔴 SELFTEST-FAIL：budget_rc={rc} coverage_caught={caught}")
        sys.exit(1)
    if unreg:
        print(f"BUDGET-FAIL: 首屏存在未登记预算的文件 {unreg}（新增文件必须同步进预算表）")
        sys.exit(1)
    if stale:
        print(f"  WARN  预算表含磁盘已无的条目 {stale}（不阻塞，建议清理）")
    sys.exit(run())
