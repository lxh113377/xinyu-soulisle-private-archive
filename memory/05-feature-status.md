# 05 - 功能状态

> 本文件记录各功能的实现状态。
> 归档类型：增量（✅ 已实现的项移入归档）

## ✅ 已实现
## ✅ 已实现（v2 / J3-J4 变现，2026-09-22）

- [ ] ⏳ 仅剩：fat jar 部署到国内可达机器（摆脱 CloudBase 首访中间页）

## ✅ 已实现（对标轮第二轮 2026-09-24：把首轮"赛后再做"直接落地）

> 详见 `交付物/对标分析报告-2026-09-24-v2.md`（14 仓 gh api 实测指标）与 `03-tech-stack.md` 决策 #6–#9。

- [ ] **仍存差距（已登记 ROADMAP 中优先）**：`/api/emotion` 前端接线（消除两份真相最后一环）· PWA · persona 偏好记忆 · `app.js` 模块化拆分 · 真机 iOS/Android 帧率与布局未测（❌）

## ✅ 已实现（对标轮 r20，2026-09-25：把"早就建好却没接上"的接上 + 第三方库漂移变机器可见）

> 详见 `交付物/对标分析报告-2026-09-25.md`。对标源数据自本轮起进台账 `交付物/对标数据/benchmark-metrics.json`
> （14 仓指标 + 本项目 self 指标 + 与上次快照的逐字段漂移），报告与台账同一份源。

- [ ] ❌ **本轮撤销一项对标结论**：v2/ROADMAP 把「PWA / service worker」列赛后排第一位，
      实测 14 参照仓 `pwa_offline` 命中 **0/14**（含 LobeChat/SillyTavern/OLV）⇒ 前提未经核实，已从计划撤销（理由留痕在 ROADMAP）
- [ ] **仍存差距（已登记）**：three.js r128 vs 上游 r186（`06-constraints` 技术债首条）、
      语义/persona 记忆（8/14 家有向量同族能力）、`app.js` 单体、`docs/` 站、真机帧率未测


## ✅ 已实现（对标轮 r21，2026-09-25 同日第二轮：接口契约 + 依赖自动更新 + 测量装置自纠）

> 详见 `交付物/对标分析报告-2026-09-25.md` §9。命令重发 = 完整重执行（刷新数据 → 执行 → 配判据 → 回归 → 回写）。

- [ ] 下一件（不依赖外部信号）：`src/js/app.js` 469 行按 voice/chart/window/编排 纯切分（⚠️ 动前先看 8123 端口归属，本轮观测到并行会话重启过 jar）

## ✅ 已实现（对标轮 r22，2026-09-25 同日第三轮）

- [ ] 下一件不变：`app.js` 469 行纯切分（⚠️ 并行会话在活动，动前先测 8123 端口归属）

## ✅ 已实现（对标轮 r23，2026-09-25 第四轮：把从没落地的 R196 强制项做成判据）

- [ ] 下一件仍是 `app.js` 469 行切分（本轮未做，见 07）

## ✅ 已实现（对标轮 r24，2026-09-25 第五轮：把连续两轮推迟的「下一件」真正做掉）

> 本轮外部数据**有漂移**（4 处：lobehub ★82,805→82,807 且 pushed 09-24→09-25、SillyTavern 33,743→33,744、OLV 13,901→13,902），
> 但主要产出是**结构性还债**：`app.js` 切分第一刀。

- [x] **`src/js/voice.js` 外提**（`app.js` 471 → 403 行，语音 99 行独立模块）：
      `window.Voice = { init(), speak(), isSpeaking() }`；保留原三条约束注释（不支持即隐藏 / 异常一律吞掉不带崩主链路 /
      开关走独立键 `peiliao.speak.v1` 不进 `cfg`）。选它当第一刀的理由是**与编排零耦合 + 判据最密**
      （`ux_guards` U1 实测 utterance 构造计数与开关、`voice_check` A1-A6 盯 ASR 与按钮）
- [x] 接线与交付链完整：`index.html` 在 `app.js` 前引入（实测 6813 < 6849）→ `deploy/xinyu` 同步（`DEPLOY-SYNC-PASS`）
      → `size_budget` 登记新文件（4,148B / 预算 4,355B，关键路径 821,901 / 858,752）→ 公网重部署 `41dea397`
      → `live_sync` / `public_check` / `online_check` 三判据 rc=0
- [x] 回归：`--slice 0 14` 14/14 + `--slice 14 28` 14/14 ⇒ **28/28 rc=0 ALL-GREEN**；`node --check` 双文件通过
- [ ] **切分未完成**：`app.js` 仍 403 行，剩余可摘模块 = 情绪曲线 `drawChart()`、对话窗口化（`RENDER_MAX`/`trimmedBuf`/配额）、
      设置面板；每一刀都须沿用同一套动作（外提 → index.html 顺序 → deploy 同步 → size_budget 登记 → 电池全绿 → 重部署）
- ⚠️ **本轮自伤（留痕）**：同步时把 `src/index.html` 误 `cp` 进 `deploy/xinyu/js/` 且用 `2>/dev/null` 吞掉报错
      ⇒ `deploy_sync` 报 EXTRA 一项；核实该副本未被跟踪且与源字节相同后删除。**我自己上一轮才把这条记进 lessons，本轮又踩**。

## 分卷目录
- **卷1** `05-feature-status.part1.md` — 05-feature-status 分卷（R199 自动拆卷）
- **卷2** `05-feature-status.part2.md` — 05-feature-status 分卷（R199 自动拆卷）
- **卷3** `05-feature-status.part3.md` — 05-feature-status 分卷（R199 自动拆卷）
- **卷4** `05-feature-status.part4.md` — 05-feature-status 分卷（R199 自动拆卷）

