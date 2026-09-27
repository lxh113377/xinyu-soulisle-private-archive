# 卷44 — r48 窄屏能力入口面（下）：`entry_reach_check` 口径、双向自证与两条未闭环（2026-09-27）

> 上卷 `part43`：实测归因、既有判据为何结构性失明、R245 分诊。

## 4. 新判据 `_test/entry_reach_check.py`（能力入口可见性单调性）

口径：基线档(1280x800)可见的入口，**任一更窄档位必须仍可见，或有替代入口**。
分母结构现读不手抄：`index.html` 带 id 的 `<button>` ∩ 被 `src/js/*.js` 以 `#id` 引用（实测候选 8）。
状态门控型（基线档本就不可见，如演示态才出现的 `#btn-exit-show`）排除但**必须点名打印**。
替代入口按能力符号判：handler 段里的 `window.<模块>.<能力>(`，再看别的 id 是否调用同名能力；
**取不到符号 ⇒ undetermined ⇒ 保守判红**（禁把"没测到"记成通过）。
豁免账 `DECLARED` 与实测 gap 集合**双向相等**：出现未登记的消失判红；
登记项实测已不再消失（账陈旧）同样判红。
视口档：1280x800 基线 + 1024/768/480/479/390/360/320 七档。

## 5. 首跑双向自证（2026-09-27 11:3x 本机，rc 一律直读不走管道）

- `--selftest` ⇒ `cases=11 fails=0 ALL-OK` rc=0。断言含：①未登记消失必红并点名 ②登记后同读数转绿
  ③陈旧豁免必红 ④空候选不得判绿 ⑤状态门控不得进分母 ⑥篡改 `ok` 计数被**门面行现算的恒等式**抓红
  ⑦⑧匹配器正/反例（共享能力符号=有替代 / 无第二处调用=判缺口）⑨能力符号取不到必红
  ⑩隐藏四形态（display/visibility/offsetParent/盒 0）皆判不可见。
  ⚠️ ⑥ 首版是**无效断言**：恒等式由 `assess()` 预先算成布尔，事后篡改 `ok` 无人能抓 ⇒
  改为 `verdict_line()` 现算，属本轮自犯自修（同族第 6 次：反例没打到被检对象）。
- 真跑现网 ⇒ `ENTRY-REACH-PASS 全部消失均已登记豁免: btn-lightshow@<=480px |`
  `visible=7/8 narrow_ok=6 gap=1 undetermined=0 declared=1 stale=0 state_gated_excluded=1[btn-exit-show]` rc=0。
- 端到端变异体（走真浏览器那条，不止纯函数桩）：`src/` 拷到仓外临时目录 →
  注入 `@media(max-width:480px){#btn-dock{display:none}}` → 起 8199 静态服务真跑 ⇒
  `ENTRY-REACH-FAIL 无法证明窄屏仍有入口（能力符号取不到，保守判红）: btn-dock@<=480px` rc=1，
  临时目录已删（`temp gone: True`）。首版 FAIL 行只给计数不点名新缺陷 ⇒ 已补：红行必带 id 与档宽。
- 邻面未破：`size_budget` / `eol_parity` / `tracked_secret` / `deploy_sync` / `release_governance`
  五跑 rc 全 0（feats=2/上限 5；本笔按 `test()` 提交，不计 feat、不占 CHANGELOG 双向对账）。

## 6. 未闭环（两条，均为刻意留下，须回读这卷才看得见）

1. 🔴 **手机端演示入口仍不可达**：按老大裁定进豁免账，样式零改动。
   **撤账条件**：480 档补替代入口（收成 `✨` 图标，或坞菜单加一项）后删
   `DECLARED["btn-lightshow"]`，判据即刻转绿；不删则第 5 条的「陈旧豁免」断言会反过来判红。
   ⚠️ 代价要写明：评委用手机打开就看不到「一键点亮」这一屏，而它正是展示分（10%）的实拍画面。
2. ⚠️ **未接进电池（因并发写者挂起，非遗漏）**：`run_all_suites.py` 现 71 条且**尚不含** r47 的
   `mobile_check` —— 那一轮正在同一文件上接线（`_test/mobile_check.py` mtime 11:25:41、
   `src/css/style.css` 11:21 仍在写）。两条同改一个 SUITES 必互覆盖 ⇒ 本轮不动它。
   留下一轮的命令 = 在 SUITES 末尾追加两行：
   `("entry_reach", [sys.executable, "_test/entry_reach_check.py"]),`
   `("entry_reach_selftest", [sys.executable, "_test/entry_reach_check.py", "--selftest"]),`
   接线后 SUITES 应为 **73**（若同轮并入 mobile 则为 75），并以 `--list` 实取条数为准。
