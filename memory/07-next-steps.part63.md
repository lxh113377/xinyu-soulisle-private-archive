# 07-next-steps 卷62 — r61 收口（CI 零判红 + 一条跨轮数据污染嫌疑待归因）

> 取号：`volume_alloc.py`（O_EXCL 独占）｜报告 `交付物/对标分析报告-2026-09-28-r61.md`

## r61 收口面

- CI 受理面 `8aa03f9` run `36340519269`：**`BATTERY: 93/94 rc=0`，判红 0 条**；
  唯一非绿 = `ENV-QUOTA(public_check)`（rc=2，余额，按 r54 设计不得记为已验）⇒ job 仍 `failure`。
  r60 我造成的 `size_budget` 真红已由 `5626460` 消掉。取证读的是看守自己落的全文 log，不采信通知的 exit。
- 公网漂移是我在 r61 中途造成的：缩注释改了 `src/` 却没重部 ⇒ `live_sync` 判红。
  补部（`0c272d75.xinyu-soulisle.pages.dev`，日志含 `Uploading Functions bundle`）后
  `LIVE-SYNC-PASS` 21/21 逐字节等。**教训**：`src/` 任何改动的收尾清单里"重部 + 跑 live_sync"不能省。

## 新挂账（未归因，机制仅列为假设）：`data_rights` 在整跑里红、单跑 3/3 绿

- 实测两侧：干净整跑（重部后启动、期间未改文件）`89/94` 且 `RED: data_rights`；
  随后 `--only data_rights` → `3/3 rc=0`（`DATA-RIGHTS-PASS … 复核归零 …`）。
- 顺序事实：`storage_resilience` 挂在 SUITES **末尾**，`data_rights` 在前 ⇒ 同一轮内不可能由它改数据；
  但 r61 的两次整跑之间它跑过，且真页在 `remote:true` 下会**真写/真删服务端行**。
- 假设（**未证实，禁止当结论抄**）：我的存储判据按自己的 sid 收口，而 `data_rights` 若有跨 sid 的
  全局计数断言，就会被上一轮的残留行影响 ⇒ 属「常驻判据在共享数据面留痕」族。
- 归因路径（r62 第一件）：`python _test/run_all_suites.py --exclude-llm > <全文 log> 2>&1`
  （**不要再 `| tail`** —— 本轮我就因 `tail -3` 把 `data_rights` 的明细截掉了），
  取到红因后按归属分档：若确为我留下的行 ⇒ 我的判据须改为跑完自清或全程用一次性 sid；
  若是 `data_rights` 自身读全局面 ⇒ 它得按 sid 隔离，另开一条反向腿。
- 另记：本轮 `ci_status` 落 `ENV-UNVERIFIED`（自愈型：等远端出现一次全绿 run 即转绿），不是判红。

## 结构事实（给后来人的预算账）

- 07 索引壳现值 **4,082 / 4,096 B（余量 14 B，比 r60 时更紧）** ⇒ 加任何一行前必须先压缩，禁止超限搬运。
- 本仓中文注释按 **3 B/字** 直接消耗逐文件字节预算：解释该进 CHANGELOG/台账，代码里留一行指针。
