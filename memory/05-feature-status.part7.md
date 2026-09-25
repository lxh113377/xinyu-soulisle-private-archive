# 05-feature-status.part7.md

<!-- 本卷为 05-feature-status.part6.md 的延续 -->

## 📋 计划中

- [x] 接线与交付链完整：`index.html` 在 `app.js` 前引入（实测 6813 < 6849）→ `deploy/xinyu` 同步（`DEPLOY-SYNC-PASS`）
      → `size_budget` 登记新文件（4,148B / 预算 4,355B，关键路径 821,901 / 858,752）→ 公网重部署 `41dea397`
      → `live_sync` / `public_check` / `online_check` 三判据 rc=0

- [x] 回归：`--slice 0 14` 14/14 + `--slice 14 28` 14/14 ⇒ **28/28 rc=0 ALL-GREEN**；`node --check` 双文件通过

- ⚠️ **本轮自伤（留痕）**：同步时把 `src/index.html` 误 `cp` 进 `deploy/xinyu/js/` 且用 `2>/dev/null` 吞掉报错
      ⇒ `deploy_sync` 报 EXTRA 一项；核实该副本未被跟踪且与源字节相同后删除。**我自己上一轮才把这条记进 lessons，本轮又踩**。

- [x] **`src/js/chart.js` 外提**（情绪曲线 Canvas 2D + resize 防抖）：`app.js` **403 → 351 行**，行为零改动；
      两条原约束随迁（HiDPI `setTransform` 逻辑绘制 / resize 200ms 防抖且无数据跳过），并补一处健壮性：
      缺 `#mood-chart` 时静默返回不抛错。判据=`browser_check` 曲线计数两态（「本机已记录 1 条情绪」/清除后「还没有记录」）实测通过
