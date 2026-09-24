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

- [x] **情绪识别后端化接线**（07 P0「J3/J4 变现」第①件，自 J3 落地起挂账 3 天）
      `src/js/emotion-remote.js`：后端 `/api/emotion` 可用时以后端为准 ⇒ **消除 JS/Java 两份真相**；
      三层开关与 J4 同口径（默认关 / 本地演示开 / **公网刻意不开**）；**危机先本地短路不为网络等待**；
      404·超时·形状不合法即熔断回落本地；界面如实标注「情绪:后端」
      判据 `_test/emotion_wiring_check.py` 9 项 PASS（含 W3b 实测 `attempted=0` 未经后端、W5 熔断不伪装、
      W6 同句双端词典结论相同）+ `--selftest` 3 类篡改全抓到
- [x] **vendor 供给链守卫** `_test/vendor-manifest.json` + `_test/vendor_freshness_check.py`
      （零构建项目没有 lockfile/dependabot ⇒ 第三方库漂移此前是**纯盲区**）：
      V1 sha256 完整性 V2 从文件内容解析版本对账（正则零命中即红，不把"没测到"当"通过"）
      V3 新库漏登记即红 V4 `--check-upstream` 报落后（`--strict` 才判红）；`--selftest` 4 类篡改全抓到
- [x] **gsap + ScrollTrigger 3.12.5 → 3.15.0 成对升级**：前端实到 API 面仅 5 处；
      `browser_check`/`lightshow_check`/`pixel_dual_check` 三套件 rc=0；体积 +1,908B 仍在预算内
- [x] **体积预算表加"必须全覆盖"判据**：实测抓到原 13 文件表漏登记 `src/data/emotion-strategy.js`（4,720B），
      且新增文件会静默绕过体积门禁 ⇒ 现漏登记即红
- [x] **`_test/benchmark_metrics.py` 对标源数据机器化**：14/14 仓采集成功、能力探测改**递归整树**
      （根目录一层探测无判别力：14 仓 sw/locales 全在子目录，只看根会一律报"无" = 把"没测到"当"没有"）
- [x] **公网跟进**：deployment `208e1743`（Cloudflare Pages），`live_sync`/`public_check`/`online_check` 三判据 rc=0
- [x] 版本推进 **v1.4.0**（`server/pom.xml` 1.3.0→1.4.0，JDK 17 构建 fat jar 29,419,279 B）+ CHANGELOG + 标签
- [ ] ❌ **本轮撤销一项对标结论**：v2/ROADMAP 把「PWA / service worker」列赛后排第一位，
      实测 14 参照仓 `pwa_offline` 命中 **0/14**（含 LobeChat/SillyTavern/OLV）⇒ 前提未经核实，已从计划撤销（理由留痕在 ROADMAP）
- [ ] **仍存差距（已登记）**：three.js r128 vs 上游 r186（`06-constraints` 技术债首条）、
      语义/persona 记忆（8/14 家有向量同族能力）、`app.js` 单体、`docs/` 站、真机帧率未测


## 分卷目录
- **卷1** `05-feature-status.part1.md` — 05-feature-status 分卷（R199 自动拆卷）
- **卷2** `05-feature-status.part2.md` — 05-feature-status 分卷（R199 自动拆卷）

