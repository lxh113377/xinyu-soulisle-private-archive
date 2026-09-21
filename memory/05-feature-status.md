# 05 - 功能状态

> 本文件记录各功能的实现状态。
> 归档类型：增量（✅ 已实现的项移入归档）

## ✅ 已实现
- [x] 3D 情绪星雾 — Three.js 粒子星云，滚动驱动镜头；WebGL 不可用降级 CSS 渐变

## ✅ 已实现（v2 / J3-J4 变现，2026-09-22）

- [x] **J3 两端一致性常驻守卫**：`_test/engine_consistency_check.py`（+ `engine_lexicon_dump.js`，Java 侧加 `/api/emotion/lexicon` 与 `eval?detail=1`）
  - 三层判据：**A 词表结构**（含**重复项与顺序**，重复词会被重复计分）/ **B 逐条预测 36 条**（只比汇总会漏"两条错误互相抵消"）/ **C 汇总指标**
  - **判据非恒真已证**：`--selftest` 注入分叉报出 2 问题；**端到端对照**（真改 JS 词表 → FAIL 并精确指出 `仅JS=['考上了X'] 仅Java=['考上了']`；还原 → PASS 且文件 SHA 不变）
  - 设计取舍：**不删本地词典**（离线降级是红线）→ 目标从"消灭重复"改为"让重复不可能**静默**分叉"
- [x] **J4 本地演示开启服务端持久化**：`src/js/demo-config.js` 预置 `remote: true` → **"跨设备、清缓存都不丢"成立**
  - 配套**熔断**（`memory-store.js`）：探测遇 404 / 网络失败即 `remoteDown`，本会话不再重试
  - **公网版刻意不开**：Pages/CloudBase 只有 `/api/chat`、无 `/api/memory`，默认开会给评委看 404 且打破 `public_check` 的 `CONSOLE_ERRORS: 0`
  - 常驻对照组 `_test/j4_remote_down_check.py` **J4-FUSE-PASS**（3 句对话仅 2 请求 = 上界；本地存储照常；熔断后 `isRemote()` False）
- [ ] ⏳ 仅剩：fat jar 部署到国内可达机器（摆脱 CloudBase 首访中间页）

## 分卷目录
- **卷1** `05-feature-status.part1.md` — 05-feature-status 分卷（R199 自动拆卷）

