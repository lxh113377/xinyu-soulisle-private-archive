# 07-next-steps 卷60 — r59（交付物清单面 + 函数出口面）

> 取号：`volume_alloc.py`（O_EXCL 独占）｜报告 `交付物/对标分析报告-2026-09-28-r59.md`

## 起点：开工 26 分钟前本仓静默丢了要交出去的东西

- 00:19 实测 `交付物/提交包/` 下 **7 个被跟踪交付件从工作树消失**（唯一参赛成片 mp4、`render-pdf.ps1`、
  `提交清单与验收状态.md` 本体、`演示视频脚本.md`、`演示视频-录制执行清单.md`、`subtitle.ass`、`timeline.json`）。
- 归因三步（先证非迁移再动手）：`archive/` 空 → `find` 全盘零副本 → `_trash/recycle_manifest.jsonl`
  无当日条目 ⇒ 不是受治 recycle/归档 ⇒ 按「工作树丢失、blob 仍在 HEAD」处置。
- 结构性证据：`grep -rn "演示视频\|demo_video_out\|提交清单\|render-pdf" _test/run_all_suites.py
  _test/repo_config_check.py .github/workflows/*.yml` → **0 命中** ⇒ 交付物面在 91 套件里**没有主人**。
- 恢复：`git checkout HEAD -- <7 条显式 pathspec>`（不用目录级，不碰他人在途件）。
  验收不看退出码看被恢复对象本身：成片 `sha256=04a7f7bf…0888ec7e` 与清单登记值逐字节等（22,954,501 B）。

## 本轮落地的两条判据

- `_test/deliverable_inventory_check.py`：提交包「清单声明 ⇄ 磁盘 ⇄ 口径」三方对账。
  分母从清单表格行**现读** `交付物/...` token；官方硬约束同行现读（`≤20页`／`≤5分钟`）；
  成片 `sha256=<64hex>` 在册即对账。真面 `声明 3｜受检 3｜品牌在册比对 1｜未登记 1｜未验 0`。
  反向腿：9 纯函数夹具 + 9 端到端（Ⓑ 声明件消失→红＝本轮真实事故形；Ⓗ 未登记件入库→红；Ⓘ 未跟踪草稿不判红）。
- `_test/api_egress_headers_check.py`：node 假 fetch 驱动**真** `chat.js`，6 条 return 出口逐条断
  5 类头 + 状态码 + 错误体形状 + 部署副本逐字节等。选离线不选 `--live`：pages.dev 按时通时不通，
  挂进阻断链＝给 CI 发彩票；且线上根本取不到 3 条出口的样本。

## 判据自己被抓两次（都靠反向腿，不靠正向）

- SSE 腿没发 `stream: true` ⇒ `wantStream` 为假，测的其实是整包 JSON 分支（症状：该出口回 `no-store`）。
- `evaluate()` 声明了 `tracked` 注入缝，调用点却直写 `tracked_by_git(rel)` ⇒ 注入不生效，Ⓗ 腿首版假绿。
- 第三条：成片时长不得依赖 ffprobe（本机 `which ffprobe`=None，而清单验收列写的就是 ffprobe 读数）。
  改零依赖解 `moov>mvhd`；首版只扫头 1 MB 取不到盒 —— 实测 `moov@22,888,322 / size 22,954,501`
  （非 faststart，盒在尾部）⇒ 改「头 1 MB→尾 1 MB」两段 seek，读数 218.48s 与登记值同尺。

## 台账

- 电池 91 → **95**（4 条：两判据 ± 自测）；README 的「95 套件」由 G4 钉住；G16 已登记两条新判据。
- 上一轮未提交尾件收口：`deploy_sync_check` 的 `src/functions ⇄ deploy/functions` 面随 `9f6c2a9` 入库
  （`DEPLOYSYNC-SELFTEST-PASS` 6 类夹具 + 真面分母 1）。
- ⚠️ **未闭合（新）**：`交付物/提交包/心屿MindIsle_参赛方案.pptx`（未跟踪，09-26 17:06）文本层
  `MindIsle` 12 处 ⇄ 在册权威源 `SoulIsle` ⇒ 品牌口径分叉。判据先计数不判红，`git add` 即拦。
  统一命名属对外裁决（与报名 PII 同档），本轮只做到「机器可见」。
- ⚠️ 重录链路 `demo_video_pipeline.py` 依赖 `ffmpeg/ffprobe`，当前环境缺 ⇒ 该主张不可复算，未修只登记。
