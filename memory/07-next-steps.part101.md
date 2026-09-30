# 07-next-steps 分卷 · part101 —— r85 全记录（2026-09-30，提交当日）

> 壳（`07-next-steps.md`）只有 4058/4096 B ⇒ 长段落一律落这儿。入场基线 `a5b6552`（r84 收口），出场 `f1d5a0a` + 本卷这一笔。

## ① 本轮四件事（按做的顺序）

| # | 事 | 结果 | 一手回执 |
|---|---|---|---|
| 1 | 公网重部署（R82-02） | ✅ 转绿 | deployment `a07fee7f`（回滚锚点 `0c272d75`）；`LIVE-SYNC-PASS`（index 9366==9366、21 项逐字节等）+ `PUBLIC-ONLINE-ALL-PASS`（`CONSOLE_ERRORS: 0`，旧版内联样式触发的 CSP 报错已清） |
| 2 | CI「浏览器回归」作业判红口径对齐 | ✅ | `.github/workflows/ci.yml` 只对电池 `rc=2`（ENV-UNVERIFIED）放行并 `::notice` 喊名单；`rc=1` 与其它非零照旧判红。**验牙**：stub rc=0/1/2/3 ⇒ 步骤退出码 0/1/0/3 |
| 3 | 提交定版包入库 + 品牌分叉隔离 | ✅ | `交付物/心屿SoulIsle-作品提交-20260930.zip`（24.77 MB）内 PDF/MP4 与仓内**逐字节相等**（`7ed80c3d…` / `04a7f7bf…`）；两份 `心屿MindIsle_参赛方案`（pdf/pptx）**移出** `提交包/` → `_参考资料-非提交/MindIsle-品牌分叉-待裁决/`（未删、未 add） |
| 4 | `hook_wiring` 的「解释器吃哪种路径形态」坑 | ✅ 修完 | 见 §② |

## ② hook_wiring 那条红：同族第四例（本轮最该记的）

- **现场**：`python _test/run_all_suites.py --exclude-llm`（`run_logged` 包装，尾行 `BATTERY_R85_FINAL_RC=1`）
  `BATTERY: 102/104 rc=1 RED(判红，必须修): hook_wiring,hook_wiring_selftest`。
- **红因原文**：`W1 钩子源解析不过（sh -n rc=127）：/bin/bash: C:Users37533Desktopworkspace项目陪聊_testhookspre-commit: No such file or directory`。
