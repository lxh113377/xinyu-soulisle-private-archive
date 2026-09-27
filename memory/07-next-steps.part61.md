# 07-next-steps 卷61 — r60（持久层异常面：四类存储故障 + 一条真缺陷）

> 取号：`volume_alloc.py`（O_EXCL 独占）｜报告 `交付物/对标分析报告-2026-09-28-r60.md`

## 起点：try/catch 有 8 处，走一遍的判据 0 条

- `src/js/memory-store.js` 对 localStorage 的读写**全部包了 try/catch**（实测 8 处）。
- 而 `grep -rn "QuotaExceeded\|SecurityError" _test/*.py` → **0 命中**（2026-09-28 01:35）
  ⇒ 47 条判据没有一条把这条路径走过。已有测试只做「写进去再读出来」的正向。
- 真实触发条件不是假想：无痕模式（Safari 直接抛 SecurityError）、企业策略禁用站点数据、
  配额写满（本仓把整段历史写进一个 key）、旧版本写坏一半的 JSON。

## 新判据 `_test/storage_resilience_check.py`

- 四类故障（禁用 / 损坏 / 写满 / 删不掉）+ 一个对照组，每条断四件：
  零未捕获异常、`#chat-dock` 可用、**`#mem-count` == `MemoryStore.count()`**、说一句情绪话后星雾仍点亮。
- 真面回执：`STORAGE-RESILIENCE-PASS: 4 种存储故障下…（用例 5 条）`；F4 行印
  `ui=0 src=0 回执=「本机清除失败 ｜ 服务端已删 3 条，复核为 0」`。
- 反向腿 10 条：合规正例不假红 + 六形必红 + **真浏览器驱动一个无 try/catch 的坏页必须冒未捕获异常** + 零读数不判绿。

## 抓到的一条真缺陷（修完）

- 现象：点「清除我的数据」→ `beforeClear` 里那次 `syncStars()` 量到的是**清除前**的条数，
  `clear()` 完成后只写回执，计数槽再没人刷 ⇒ 界面挂旧数字（实测 界面 1 ⇄ 数据源 0）。
- 修法：`DataRights.init` 增 `afterClear` 钩子，`.then` 内补一次 `syncStars()`；
  同步 `deploy/xinyu/js/`（`DEPLOY-SYNC-PASS`）并重部 Pages（`LIVE-SYNC-PASS` 21/21 逐字节等）。
- ⚠️ 差点引入的第二处：`afterClear` 里顺手加的 `Chart.render()` 会把回执槽 `#chart-count`
  覆成「还没有记录」—— 该槽**双主人**（曲线条数 + 清除回执），F4 腿当场拦下。风险已写进源码注释。

## 判据自己的三处失效（都是反向腿/复跑抓的）

- 反例 needle 与红因文案不一致（我写「注错自身」，文案是「自身抛错」）⇒ 腿自己假绿。
- harness 的 `TimeoutError` 被塞进 `pageerrors` ⇒ 会把"取数失败"报成"应用崩了"；现分两栏、各有专属红因。
- **flake 一次**：单跑 rc=0、接进电池后同一条 F4 翻红。真因＝固定等待（2600ms/1500ms），
  并发下 `DELETE → /stats` 更慢，回执还停在「正在清除…」。改 `settle()` 有界轮询完成信号（≤15s），
  超时记 `harness_error` 而非判绿/误判红。修后 2 次单跑 + 1 次电池内全绿；
  ⚠️ 只宣称"再 flake 时红因会点名"，不宣称"永不再 flake"。

## 挂账（现象在册、未归因）

- `#btn-clear` 真点击在 Playwright 默认 actionability 下超时，`force=True` 可点；
  已排除"元素在动"：5 次采样 `top/left` 恒定 330.5/369、`document.getAnimations()` 零 active。
- `grep -c btn-clear _test/entry_reach_check.py` → **0** ⇒ 该数据权利入口的可达性**没有判据管**。
  本轮只登记现象与排除项，**未**写成缺陷（未归因不得下结论）。

## 台账

- 电池 95 → **97**（`storage_resilience` ± 自测）；`REPO-CONFIG-PASS 14/14`（G16 已登记）、
  `EOL-PARITY-PASS`、`DEPLOY-SYNC-PASS`、`LIVE-SYNC-PASS`、`browser_check ALL-ASSERT-PASS`、`data_rights 3/3`。
