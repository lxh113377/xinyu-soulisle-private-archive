# -*- coding: utf-8 -*-
"""r94：把 backup_online 的 B2 有界重试这条写进报告 §5 与 CHANGELOG。"""
from pathlib import Path

# ── 报告 §5 ──
P = Path("交付物/对标分析报告-2026-10-03-r94.md")
src = P.read_text(encoding="utf-8")
ANCHOR = "- **r94 漂移「首次运行，无历史可比」**"
ADD = (
    "- **`backup_online` B2 在电池里红 1 次（Playwright 导航竞态，已加有界重试）**：\n"
    "  失败形态是 `Page.evaluate: Execution context was destroyed, most likely because of a navigation`\n"
    "  —— 页面在 evaluate 期间发生导航（腾讯「确定访问」页跳转 / SW 重载）。证据：单独复跑 2 次全绿、\n"
    "  本轮 `src/` 与 `deploy/` 零改动、r93 也观测过同一套件首跑红重跑绿。\n"
    "  处置：给该腿加**有界重试一次**（失败等 1.2s 重读同一份 localStorage，第二次仍红照判）——\n"
    "  这是**修测试基础设施的竞态**，不是放宽判据：真内容缺陷第二次仍会被拦。\n"
)
if ANCHOR in src and "B2 在电池里红 1 次" not in src:
    src = src.replace(ANCHOR, ADD + ANCHOR, 1)
    P.write_text(src, encoding="utf-8")
    print("报告 §5 已补")

# ── CHANGELOG ──
C = Path("CHANGELOG.md")
cs = C.read_text(encoding="utf-8")
OLD = "- **loc 门第一次对真实回归亮红（门有牙的实证）**"
NEW = (
    "- **`backup_online` B2 的 Playwright 导航竞态（Fixed）**：电池里红 1 次，失败形态是\n"
    "  `Page.evaluate: Execution context was destroyed`（页面在 evaluate 期间导航），单独复跑 2 次全绿。\n"
    "  给该腿加**有界重试一次**（1.2s 后重读同一份 localStorage，第二次仍红照判）——修竞态不是放宽判据。\n"
    + OLD
)
if OLD in cs and "导航竞态" not in cs:
    C.write_text(cs.replace(OLD, NEW, 1), encoding="utf-8")
    print("CHANGELOG 已补")
