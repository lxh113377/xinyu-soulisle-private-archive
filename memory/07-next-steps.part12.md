# 07-next-steps.part12.md

<!-- 本卷为 07-next-steps.part11.md 的延续 -->

- [x] ✅ **对标轮第二轮 M1–M8 全部落地（2026-09-24）**：流式 SSE / 共情策略表 SSOT / provider 别名 / TTS 朗读 / 对话窗口化 / 响应式+粒子降档 / CI 三门禁 / ROADMAP+`v1.3.0` 标签。
      判据全绿：`stream_contract` A/B/C、`strategy_check`（+`--selftest` 防恒真）、`ux_guards_check` 21/21、`browser_check` ALL-ASSERT-PASS、`engine_consistency` 98.6%/6-6 双端全等、`deploy_sync` 三类归零。
      详表见 `05-feature-status.md`「对标轮第二轮」，架构取舍见 `03-tech-stack.md` 决策 #6–#9，对标数据见 `交付物/对标分析报告-2026-09-24-v2.md`

- [x] ~~⏸ PDF 起草（2026-09-23 老大明确维持冻结）~~ → **2026-09-24 解冻并已产出**：18 页 PDF + 盲审遗留处置 + 路径泄露修复（9d7442c 与当日日志），本项关闭

- [x] 🔴 ~~**P0（新）· 公网部署未跟进本轮改动**~~ → **2026-09-24 r17 已上线并复核关闭**：`wrangler pages deploy` 执行成功（deployment `09641d44`）。线上复核：`xinyu-soulisle.pages.dev/` 已含 `btn-theme` + `manifest.webmanifest`（manifest 200）；`online_check.py` rc=0（离线徽章正常）、`public_check.py` rc=0（`● 在线 AI` 徽章 / 体验条 True / **KEY_LEAK: False** / CONSOLE_ERRORS: 0）。⚠️ 复核坑记：Pages 对 `/index.html` 返回**空 body**，须按 `/` 抓页面，否则 grep 恒 0 误判"未上线"
