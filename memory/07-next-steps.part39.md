# 卷39 — r45 发布治理面（上）：受理面二次红的完整链条 + 新维度实数（2026-09-27）

> 承主壳 P0。下卷见 `part40`（两条闸的落地、v1.5.0 切版与未闭环序）。
## 1. 受理面二次红的完整链条（508ab3c）

- CI 结论：`gh run view 36285271427 --json jobs` → `failure`，四个 job 里 `浏览器回归` 红；
  末段 `BATTERY: 62/64 rc=0 RED: offline_shell,offline_shell_selftest`。
- 真因：r45 为修 `size_budget` 把数据权利 UI 外提成 `src/js/data-rights.js`，改了 `index.html` 的
  `<script>` 却没改 `src/sw.js` 的 `PRECACHE`。`offline_shell` 的 A10（页面引用必须被壳覆盖）当场判红。
- **我跳过了本地全量电池就推** —— 这条是根因的行为面：判据一条都没坏，坏的是"跑不跑"。
- 比清单更重的一层：同轮 R7 报出公网断网重载时
  `TypeError: Cannot read properties of undefined (reading 'init') at js/app.js:208`，
  R9a 报 `公网壳 17/18 缺=['/js/data-rights.js']`。**公网用户当时是真的打不开离线态**，
  不是"少缓存一个文件"那么轻。我一度把它记成瞬时抖动，用 curl + Playwright 复验才确认稳定复现。
- 处置顺序（本轮按此执行）：补 PRECACHE → 同步 `deploy/xinyu/sw.js`（`DEPLOY-SYNC-PASS`）→
  重部署公网壳（deployment `84148f11`）→ `offline_shell_check` 17 项全过、R8 复算入缓存 18/18 → 才提交推送。

## 2. r45 新维度：发布与版本治理（16 仓 + self）

取数 `python _test/peer_release_probe.py --json 交付物/对标数据/peer-release-2026-09-27.json`
（ts=2026-09-27T01:25:31Z，usable 16 / BLIND 0 / 恒等式 OK）：

- 有公开 release **11/16**；tag 合 semver **11/16**；带 CHANGELOG 类件**只有 4/16**；
  有 release 的 11 家里 **4 家滞后 >30 天**（min 0｜中位 9｜max 261.94）。
- 滞后 TOP4：`Open-LLM-VTuber 261.94` / `MER-Factory 165.2` / `letta 119.03` / `opensoul 94.24`。
- 无 release 的五家全在 tier C（MASCOT / Loyal-Elephie / Rogendo-MHC / succhia / MoodChat）
  ⇒ 这一维的分层信号比 stars 更硬：它量的是"项目方自己决定要不要把东西交出去"。

## 3. 自家被量出的两处事实与账面背离

1. `lag=0.56 天`（11 家里有 release 的里**真实第三**：leemo 推送后 107 秒即发布、ryza 同秒 —— 原始字段核验过，不是时区污染；我第一版写的"全池第一"与第二版写的"时区残差"**两条都已撤回**，见报告 §1 附注）与 **`v1.4.3..HEAD = 44 commit / 11 feat 未切版`** 同时为真。
   滞后指标只取两端时间，中间增量看不见。
2. `[Unreleased]` 有 20 条 bullet 看起来很勤，实际全是 r39/r40*；
   **r41 / r42 / r43 三轮 feat 级提交零登记**，r44 只在"修 r44 造成的红"里被顺带提过。
   ⇒ 计数型判据会被存量 bullet 掩盖成通过（本轮 R2a 的第一号缺陷）。

