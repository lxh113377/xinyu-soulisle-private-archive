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

# (相对路径, 预算 bytes)。总预算 = 首屏关键路径：index.html + style.css + 全部 js + vendor
BUDGETS = {
    "src/index.html": 9_143,
    "src/css/style.css": 13_367,
    "src/js/app.js": 23_757,
    "src/js/chat-agent.js": 11_266,
    "src/js/emotion-engine.js": 5_597,
    "src/js/scroll-story.js": 3_756,
    "src/js/three-scene.js": 15_793,
    "src/js/memory-store.js": 4_843,
    "src/js/demo-config.js": 1_411,
    "src/data/emotion-lexicon.js": 4_041,
    "src/vendor/three.min.js": 633_617,
    "src/vendor/gsap.min.js": 75_824,
    "src/vendor/ScrollTrigger.min.js": 45_549,
}
TOTAL_KEY_PATH = 847_969  # 首屏关键路径总预算（含 vendor）


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
    if "--selftest" in sys.argv:
        rc = run(scale=0.90)
        if rc == 1:
            print("✅ SELFTEST-PASS：压缩预算后成功报红 ⇒ 判据非恒真")
            sys.exit(0)
        print("🔴 SELFTEST-FAIL：预算压到 90% 仍未报红，判据恒真")
        sys.exit(1)
    sys.exit(run())
