# 05-feature-status.part6.md

<!-- 本卷为 05-feature-status.part5.md 的延续 -->

## 📋 计划中

- [x] **判据化**：`repo_config_check.py` 新增 **G8**（模板原句残留 / 登记文件不存在 R240 / 声称条数≠实际 items 数 /
      未登记的裁决数据文件），`--selftest` 扩到 **十类**合成篡改全抓；判据自身两次假红已修并写进注释：
      ① 用"段里出现（如 "当占位符 → 已填实的表被误判 ② 对所有登记文件比 items 长度 → 把
      `vendor-manifest.json` 的「3 条」当成 3 个样本 ⇒ 分母混用。教训同族：**判据错、不是数据错，先修判据**

- [x] 回归：`repo_config --online` 7 项全 PASS、`--selftest` 十类全抓；全量电池 `--slice 0 14` 14/14 + `--slice 14 28` 14/14 ⇒ **28/28 rc=0**

- [x] **`src/js/voice.js` 外提**（`app.js` 471 → 403 行，语音 99 行独立模块）：
      `window.Voice = { init(), speak(), isSpeaking() }`；保留原三条约束注释（不支持即隐藏 / 异常一律吞掉不带崩主链路 /
      开关走独立键 `peiliao.speak.v1` 不进 `cfg`）。选它当第一刀的理由是**与编排零耦合 + 判据最密**
      （`ux_guards` U1 实测 utterance 构造计数与开关、`voice_check` A1-A6 盯 ASR 与按钮）

- [x] 接线与交付链完整：`index.html` 在 `app.js` 前引入（实测 6813 < 6849）→ `deploy/xinyu` 同步（`DEPLOY-SYNC-PASS`）
      → `size_budget` 登记新文件（4,148B / 预算 4,355B，关键路径 821,901 / 858,752）→ 公网重部署 `41dea397`
      → `live_sync` / `public_check` / `online_check` 三判据 rc=0

- [x] 回归：`--slice 0 14` 14/14 + `--slice 14 28` 14/14 ⇒ **28/28 rc=0 ALL-GREEN**；`node --check` 双文件通过

- ⚠️ **本轮自伤（留痕）**：同步时把 `src/index.html` 误 `cp` 进 `deploy/xinyu/js/` 且用 `2>/dev/null` 吞掉报错
      ⇒ `deploy_sync` 报 EXTRA 一项；核实该副本未被跟踪且与源字节相同后删除。**我自己上一轮才把这条记进 lessons，本轮又踩**。

- [x] **`src/js/chart.js` 外提**（情绪曲线 Canvas 2D + resize 防抖）：`app.js` **403 → 351 行**，行为零改动；
      两条原约束随迁（HiDPI `setTransform` 逻辑绘制 / resize 200ms 防抖且无数据跳过），并补一处健壮性：
      缺 `#mood-chart` 时静默返回不抛错。判据=`browser_check` 曲线计数两态（「本机已记录 1 条情绪」/清除后「还没有记录」）实测通过

- [x] 交付链全跑：`index.html` 顺序 voice→chart→app（实测 6813/6845/6885）→ `DEPLOY-SYNC-PASS`
      → `size_budget` 登记（17 文件，关键路径 822,936 / 858,752）→ 公网重部署 `0c90a2d9` → 三判据 rc=0
      → 电池 `--slice 0 14` 14/14、`--slice 14 28` 14/14 ⇒ **28/28 rc=0**

- [x] 外部漂移 3 处（lobehub 82,808 / ST 33,745 / OLV 13,903，能力矩阵无变化）⇒ 七维无翻牌，本轮不编造差距

- ⚠️ **本轮两处自伤**：① 打 `size_budget` 补丁时锚点写成 `4_355`（实为 `4355`），`replace` 未命中却照常打印"已登记"
      ⇒ 被 coverage 判据当场报「未登记文件」；已改成替换前后各加 assert。② 抽曲线的脚本锚点条件过窄（依赖 `measureText` 前一行）
      ⇒ `StopIteration` 死在半路；改用 `#btn-clear`/resize 注释这类语义锚点 + 边界行 assert。
      两条同族：**工具"没报错"不等于"生效了"**（与 r23 的 `done >= 8`、r24 的 `2>/dev/null` 同族，已连续三轮复发）。
