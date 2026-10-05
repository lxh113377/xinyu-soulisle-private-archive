# -*- coding: utf-8 -*-
"""r94：报告 §5 追加「voice A5 偶发」与「loc 门实证」两条如实登记。"""
from pathlib import Path

P = Path("交付物/对标分析报告-2026-10-03-r94.md")
src = P.read_text(encoding="utf-8")
ANCHOR = "- **r94 漂移「首次运行，无历史可比」**"
ADD = (
    "- **`voice` A5 在电池里偶发红（本轮未改任何 `src/js`，属环境时序而非代码回归）**：\n"
    "  首跑 A5 判「卡在监听态，8s 内 `class=recording` 未移除」。该腿是**时序轮询**"
    "（80 × 100ms = 最多 8s），电池同时压着浏览器与服务端时可能踩不满预算。\n"
    "  证据链：① 本轮 `src/`、`server/` 零改动；② 用正确 URL 单独复跑 2 次均 `VOICE-PASS`（rc=0）；\n"
    "  ③ 单独复跑时若沿用脚本默认的 `8125` 端口会导航失败——那是**用法错**（电池传的是 `BASE`=8123），\n"
    "  不是判据红。**处置：不放宽 8s 预算**（放宽等于为绿而松尺，与本仓 coverage 门同宗纪律），\n"
    "  改用重跑取最终回执，并把本条如实登记为 flaky 待观察。\n"
    "- **loc 门转 enforce 后第一次对真实回归亮红（门有牙的实证）**：给 `offline_shell._run_checks`\n"
    "  补 `return results` 时 accompanying 的 5 行注释把该函数顶到 155 行 ⇒ `loc_guard` 当场\n"
    "  `LOC-FAIL`（rc=1）⇒ 压缩注释后恢复 `LOC-PASS`。此前这条门只印读数、从不拦人。\n"
)
if ANCHOR in src and "voice` A5 在电池里偶发红" not in src:
    src = src.replace(ANCHOR, ADD + ANCHOR, 1)
    P.write_text(src, encoding="utf-8")
    print("已插入 §5 两条")
else:
    print("锚点未命中或已插入")
