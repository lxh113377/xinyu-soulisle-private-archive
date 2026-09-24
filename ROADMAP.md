# 心屿 SoulIsle · 公开路线图

> 依据：`交付物/对标分析报告-2026-09-24.md`（首轮，对标 LobeChat / Open-LLM-VTuber / SillyTavern）
> 与 `交付物/对标分析报告-2026-09-24-v2.md`（第二轮，14 仓 gh api 实测指标 + 同体量垂类项目横向对账）。
>
> 立此文件的原因（对标教训）：**Open-LLM-VTuber 13.9k★ 也近 4 个月零提交**——热度不等于可持续。
> 参赛项目赛后最容易死在"静默"上，所以路线与**不做什么**都要写成公开承诺，而不是散在聊天记录里。

最后更新：2026-09-25（对标轮 r20）

---

## ✅ 已完成（2026-09-24 对标轮第二轮，全部当场实测）

| 项 | 对标差距来源 | 落地证据 |
|---|---|---|
| **逐字流式输出（SSE）** | LobeChat `fetch-sse` / OLV WebSocket，心屿原为整包返回 | `_test/stream_contract.py`：A 非流式契约不破 / B 32 帧中 30 帧含 `delta.content` / C 前端出现逐字气泡且不可达时不冒充在线 |
| **共情策略表 SSOT** | 三家均无可配置策略层；心屿原硬编码 `chat-agent.js` | `src/data/emotion-strategy.js` + `_test/strategy_check.py`（含 `--selftest` 注入分叉证非恒真） |
| **多模型 provider 适配层** | LobeChat 全家桶、OLV 可插拔后端 | `LLM_BASE/LLM_MODEL/LLM_KEY`（`DEEPSEEK_*` 兼容）+ 设置面板 5 家预设 |
| **回复朗读（TTS）** | OLV 多引擎 TTS、LobeChat 自研 TTS 库；陪伴产品不出声是硬短板 | `speechSynthesis`（zh-CN，零依赖）+ `_test/ux_guards_check.py` U1（构造计数实测，含"关得掉"） |
| **对话列表窗口化** | LobeChat `react-virtuoso` | 60 条 DOM 上界 + 配额制折叠展开；U2 实测 `getHistory`/`MemoryStore` 不受窗口化影响 |
| **响应式三档 + 粒子降档** | 心屿原先只有 1 条 640px 媒体查询 | 480/768/1024 + 900/1200/2600 三档；U3 实测无横向溢出且桌面档恒 2600（不破 `browser_check` 标定） |
| **词表一致性红线机器化** | 此前这条铁律**只写在 `memory/AGENTS.md` 靠人记** | CI `java-build` job 起无密钥 fat jar 跑 `engine_consistency_check.py` |
| **密钥零入库扫描进 CI** | 对标项目普遍靠 gitleaks；心屿原先只有本地 `public_check` | CI 对照组（拼接生成 canary，防自伤命中）+ 只扫 `git ls-files` |
| **浏览器回归进 CI** | 三家都有托管 CI | CI `browser-regression` job（runner 无 GPU → 强制 SwiftShader，本机已用同参数复跑 PASS） |

---

## ✅ 已完成（对标轮 r20，2026-09-25，全部当场实测）

| 项 | 对标差距来源 | 落地证据 |
|---|---|---|
| **情绪识别后端化（消除"两份真相"）** | 14 参照仓里 8 家已有向量/语义化记忆与后端化能力；心屿 J3 已做出 Java 引擎却**没被前端用上**（= 两份真相 + 卖点空转） | `src/js/emotion-remote.js`（三层开关与 J4 同口径）+ `_test/emotion_wiring_check.py` **9 项 PASS**：W4 实测 `stats.ok=1` 且气泡标「情绪:后端」/ W5 拦掉 `/api/emotion` 即熔断且**不冒充** / W3b 危机短路 `attempted=0` 未经后端 / W6 词典层双端同句同结论 |
| **vendor 供给链守卫（完整性 + 版本对账 + 上游漂移）** | 心屿零构建 ⇒ 无 lockfile、无 dependabot，第三方库漂移**此前是纯盲区**（14 家里仅 2 家有自动更新，且它们都有 package.json 可挂） | `_test/vendor-manifest.json`（唯一声明源）+ `vendor_freshness_check.py`：V1 sha256 完整性 V2 从文件内容解析版本对账（正则零命中即红）V3 新库漏登记即红 V4 `--check-upstream` 报落后；`--selftest` 4 类篡改全抓到 |
| **gsap + ScrollTrigger 3.12.5 → 3.15.0 成对升级** | 上游 greensock/GSAP tag 3.15.0（实测 releases/latest 404 ⇒ 该仓只发 tag，探测已按此实现） | 前端实际用到的 API 面**仅 5 处**（`gsap.to/timeline/registerPlugin`、`ScrollTrigger.refresh`、`window.gsap`）；升级后 `browser_check` / `lightshow_check` / `pixel_dual_check` **三套件 rc=0**；体积 +713B/+1,195B，关键路径 819,767/858,752 仍在预算内 |
| **体积预算表覆盖判据（补一个真实存在的洞）** | 上一轮刚建的 `size_budget_check` 靠手工列表 ⇒ **"加文件"这条最常见的退化路径恰好绕过门禁** | 实测抓到 2 处：漏登记 `src/data/emotion-strategy.js`（4,720B）与本轮新增的 `emotion-remote.js`；新增 coverage 判据 + `--selftest` 同时证两条判据非恒真 |
| **对标源数据机器化台账** | 前两轮报告的星数/停更日期来自一次性手工 curl，**下一轮无法机器复核**（度量可信度 M1「数字来自历史快照」风险源） | `_test/benchmark_metrics.py` → `交付物/对标数据/benchmark-metrics.json`：14 仓 ★/pushed/release/CI wf/文档/**递归整树能力矩阵** + 本项目 self 指标，每次运行输出**与上次快照的逐字段漂移**；`--selftest` 合成 2 处改动全抓到、全等对照零误报 |


## 🔜 计划（赛后 1–2 周，按投入产出排序）

1. **three.js r128 → r186 升级**（对标轮 r20 新登记的**头号技术债**）——
   实测：`src/vendor/three.min.js` 内 `REVISION` 值为 **128**（2021 年发布），上游 `mrdoob/three.js` 当时最新
   **r186**（2026-09-24 发布），跨 **58 个大版本**。登记为 `_test/vendor-manifest.json` +
   `python _test/vendor_freshness_check.py --check-upstream --strict`（现在就能机器复现"我们落后多少"）。
   **不在截止前动的理由**（不是拖延，是风险）：r152 起默认色彩管理改写（`outputColorSpace` 取代
   `useLegacyLights`/`sRGBEncoding`）、`Geometry` 全面移除、自定义 `ShaderMaterial` 的 uniform 约定变更
   ⇒ 星雾"暗星 0.05 / 点亮 0.26"与**双色像素级标定**（`pixel_dual_check` 判据 0.25/0.10 双条件）需整体重定，
   等于在答辩素材冻结期重做可视化。升级须独立成阶段并带视觉基线对照。
2. **对话列表真正虚拟化（窗口外节点回收 + 滚动位置保持）**——当前是"上界 + 分批展开"，长会话（>500 条）还需滚动锚定。
3. **结构化记忆升级（persona 维度）**——对标 SillyTavern 世界书：`emotion_record` 加偏好标签，从"记得历史"进化到"记得你的偏好"。
4. **危机干预链路可审计化**——危机命中事件的服务端留痕与导出（**不留对话原文**，只留时间戳与类别），配合《应用方案》里的伦理章节。
5. **i18n 框架化**——低优先（面向国内高校），但 `README.en.md` 已是第一步。

### ⚠️ 本轮（r20）从计划里**撤下**的两项，附实测理由

- **「PWA / service worker 离线缓存」→ 撤销，不做**（原计划第 1 位）。
  依据：`_test/benchmark_metrics.py` 递归整树探测 14 个参照仓，**`pwa_offline`（sw.js/service-worker.js）命中 0/14**
  ——包括 LobeChat/SillyTavern/OLV 三家头部项目。即"同类优质项目都靠 SW 做离线"这个前提**不成立**，
  它是首轮报告未经核实的推断。且心屿三个第三方库本就随源码分发（`src/vendor/`），资源层已是本地化；
  在截止前给评委用的地址加 SW，只会引入"线上改版但旧 SW 继续投喂旧页面"这一类难复现的缓存故障
  （本项目已有一次 jar 进程内缓存导致的假象教训）。**替代动作**：`manifest.webmanifest` 保留（r17 已上线），
  新鲜度改由 `_test/live_sync_check.py` 机器守（线上 == 权威源逐字节）。
- **「`/api/emotion` 前端接线」→ 已完成，移入下方已完成表**（r20，2026-09-25）。

## 🚫 明确不做（附理由，避免被"对标"裹挟）

| 项 | 为什么不做的硬理由 |
|---|---|
| 插件市场 / 扩展 SDK | 参赛作品不需要生态，需要的是"加一类情绪只改一处"——已由策略表 SSOT 达成同等可维护性，成本 1/50 |
| 角色卡 / persona 商店 | 偏离"情绪陪伴垂类"定位，与差异化卖点（双路识别 + 危机拦截 + 可复现评测）无叠加收益 |
| 改用 React/Next + 构建器 | 选型决策 #1/#2 已记录：零构建换来"评委免环境直开"，直读 `src/` 换来零副本同步点。架构维度不与 React 系对齐是**有意取舍** |
| 引入 Spring Security + JWT | 决策 #4：单体演示应用只需私有部署护栏；需要账号体系时再评估 |
| 多用户 / 团队协作 | 同上，且与"隐私本地化"卖点冲突 |

---

## 版本节奏

- 语义化版本 + `CHANGELOG.md`（Keep a Changelog）。当前版本：**v1.3.0**（2026-09-24 对标轮第二轮，已打标签）。
  每个「可验证关卡」（一组改动 + 全绿判据）即一次小版本；iCAN 提交件冻结点单独打 `ican-2026-submit` 轻量标签，便于赛后回溯。
- 每季度末复核一次本文件：完成项移上、明确不做项如被现实推翻须写「更正注」而非删除（决策留痕）。
