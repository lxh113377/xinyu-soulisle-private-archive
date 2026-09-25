# 07-next-steps.part14.md

<!-- 本卷为 07-next-steps.part13.md 的延续 -->

- [x] 🔴 ~~**J3/J4 变现第①件：前端切 `/api/emotion`（消除情绪引擎"两份真相"）~~ → **2026-09-25 对标轮 r20 已落地并配判据**：
      新增 `src/js/emotion-remote.js`（三层开关与 J4 完全同口径：代码层 `cfg.emotionRemote === true` 默认关闭 /
      本地演示 `src/js/demo-config.js` 置 true / **公网 `deploy/xinyu/js/demo-config.js` 刻意不含**——Pages Function 无 `/api/emotion`）。
      **危机词在函数体内先本地短路，绝不为网络等待**；404/超时/响应形状不合法即熔断回落本地引擎；气泡如实标注「情绪:后端」。
      判据 `_test/emotion_wiring_check.py` **9 项 PASS**（W1 接线顺序 / W2 公网零开关 / W2b 副本一致 /
      W3 危机短路顺序 + W3b 实测 `attempted=0` 未经后端 / W4 后端路径生效且如实标注 / W5 不可达熔断不伪装 /
      W6 词典层双端同句同结论 / W7 零 pageerror）+ `--selftest` 3 类篡改全抓到（证判据非恒真）。
      本地那份 JS 引擎**按设计保留为离线降级**，未删。详见 `交付物/对标分析报告-2026-09-25.md`
