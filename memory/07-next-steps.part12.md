# 07-next-steps.part12.md

<!-- 本卷为 07-next-steps.part11.md 的延续 -->

- [x] ✅ **对标轮第二轮 M1–M8 全部落地（2026-09-24）**：流式 SSE / 共情策略表 SSOT / provider 别名 / TTS 朗读 / 对话窗口化 / 响应式+粒子降档 / CI 三门禁 / ROADMAP+`v1.3.0` 标签。
      判据全绿：`stream_contract` A/B/C、`strategy_check`（+`--selftest` 防恒真）、`ux_guards_check` 21/21、`browser_check` ALL-ASSERT-PASS、`engine_consistency` 98.6%/6-6 双端全等、`deploy_sync` 三类归零。
      详表见 `05-feature-status.md`「对标轮第二轮」，架构取舍见 `03-tech-stack.md` 决策 #6–#9，对标数据见 `交付物/对标分析报告-2026-09-24-v2.md`

- [x] ~~⏸ PDF 起草（2026-09-23 老大明确维持冻结）~~ → **2026-09-24 解冻并已产出**：18 页 PDF + 盲审遗留处置 + 路径泄露修复（9d7442c 与当日日志），本项关闭

- [x] 🔴 ~~**P0（新）· 公网部署未跟进本轮改动**~~ → **2026-09-24 r17 已上线并复核关闭**：`wrangler pages deploy` 执行成功（deployment `09641d44`）。线上复核：`xinyu-soulisle.pages.dev/` 已含 `btn-theme` + `manifest.webmanifest`（manifest 200）；`online_check.py` rc=0（离线徽章正常）、`public_check.py` rc=0（`● 在线 AI` 徽章 / 体验条 True / **KEY_LEAK: False** / CONSOLE_ERRORS: 0）。⚠️ 复核坑记：Pages 对 `/index.html` 返回**空 body**，须按 `/` 抓页面，否则 grep 恒 0 误判"未上线"。**r18 补机器守卫**：`_test/live_sync_check.py`（线上 `/` 与 `deploy/xinyu/index.html` 逐字节比对，rc 0/1/2 分离漂移与环境，反例 example.com→rc=1 证非恒真）已入 17 套件电池 + CI `live-sync` job

- [x] 🔴 ~~**J3/J4 变现第①件：前端切 `/api/emotion`（消除情绪引擎"两份真相"）~~ → **2026-09-25 对标轮 r20 已落地并配判据**：
      新增 `src/js/emotion-remote.js`（三层开关与 J4 完全同口径：代码层 `cfg.emotionRemote === true` 默认关闭 /
      本地演示 `src/js/demo-config.js` 置 true / **公网 `deploy/xinyu/js/demo-config.js` 刻意不含**——Pages Function 无 `/api/emotion`）。
      **危机词在函数体内先本地短路，绝不为网络等待**；404/超时/响应形状不合法即熔断回落本地引擎；气泡如实标注「情绪:后端」。
      判据 `_test/emotion_wiring_check.py` **9 项 PASS**（W1 接线顺序 / W2 公网零开关 / W2b 副本一致 /
      W3 危机短路顺序 + W3b 实测 `attempted=0` 未经后端 / W4 后端路径生效且如实标注 / W5 不可达熔断不伪装 /
      W6 词典层双端同句同结论 / W7 零 pageerror）+ `--selftest` 3 类篡改全抓到（证判据非恒真）。
      本地那份 JS 引擎**按设计保留为离线降级**，未删。详见 `交付物/对标分析报告-2026-09-25.md`

- [x] **对标轮 r21（2026-09-25 同日第二轮）已落地**：① 接口契约唯一声明源 `docs/openapi.yaml`（11 条）+ 三方对账守卫
      `_test/api_contract_check.py`（C1 不缺文档 / C2 不虚文档 / C3 前端偷调即红 / C4 运行态状态码与必需键 / C5 自证）
      ② `.github/dependabot.yml`（maven@/server + github-actions@/）③ 测量装置自纠（漂移纳入 caps/docs；
      self 套件数改取 `run_all_suites.py` 条目数为唯一分母）④ 参照池 14→16。电池 **26 套件**。
      **同时勾销一处 r20 错误归因**："零构建挂不上 dependabot"→ 实测 Maven 与 Actions 两个 ecosystem 可直接挂，
      更正注在 `06-constraints.md`（原条目保留，不删改历史）。
