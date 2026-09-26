# 07 - 下一步 · 卷25（r36 续卷 · 2026-09-26：公网同源 / 电池加固 / 同类写盘口 / 对标补测）

> 由卷24 按 4KB 同尺续拆（R161 零豁免），条目逐字迁移未改写。

3. ✅ **公网字节同源（本轮重部署）**：`cd deploy && npx wrangler pages deploy xinyu
   --project-name=xinyu-soulisle --commit-dirty=true`，日志含 `Uploading Functions bundle`；
   回滚锚点 = 上一版生产部署 `b5f46ecf-d1dd-46ee-b700-10a3d2914e56`，新版预览 `24eb5e2e.xinyu-soulisle.pages.dev`。
   复验：`live_sync_check` 由 `live=9463 local=9288｜仅行尾差异 ⇒ PASS`（靠 `eol_only` 兜底分支放行）
   变为 **`live=9288 local=9288 equal=True`**（不再走兜底分支）；
   `public_check` / `online_check` / `offline_shell_check`（17 项 0 失败）/ `deploy_sync_check` 全绿。
4. ✅ **电池入口 fail-closed（commit `e45ba62`）**：`--help` 原先无实现 ⇒ 被当未知参数**静默忽略并跑全量**；
   同理 `--only`/`--slice` 打错字会跑成全量还打印 `ALL-GREEN`（把"子集全绿"说成"全量全绿"）。
   现：未知开关 rc=2、缺操作数 rc=2、`--slice 99 120` 越界 rc=2（Python 切片会静默截成空集）、补 `-h/--help`。
   另：摘要行由"最后一行"改"最后一条判定行"——`strategy_selftest` 在 PASS 后还打印注入反例，
   rc=0 却显示 `· 热线清单需 ≥3 条，实际 []`，看着像报错。
5. ✅ **同类写盘口归一（commit `c3f8c1a`）**：`Path.write_text` 在 Windows 文本模式把 `\n` 翻成 `\r\n`
   （实测 `b'a\n'` → 落盘 `b'a\r\n'`），**一次写入即把刚归一好的 LF 打回 CRLF**。
   判据 `eol_parity` 在本轮复跑台账时当场抓到一处（`benchmark-metrics.json`）。
   按"修一类不修一例"枚举全部落**被跟踪文本**的写盘口并改 `write_bytes`：
   `benchmark_metrics.py`（台账）、`patch_apply.py`（补丁写盘 + 读回复验改按字节，
   因 `read_text` 的 universal newlines 会把 CR 读成 `\n`，复验步骤自己会掩盖该缺陷）、
   `demo_video_pipeline.py`（`timeline.json` / `subtitle.ass`，两文件均已入库）。
   `patch_apply --selftest` 由六类改**八类**（新增 ⑦LF 输入打完仍 LF / ⑧CRLF 输入被归一）。
6. ✅ **本机 43 套件全量复跑**：`--slice 0 22` ⇒ **22/22 rc=0 ALL-GREEN**、
   `--slice 22 43` ⇒ **21/21 rc=0 ALL-GREEN** ⇒ 合计 43/43。
   台账重采：`BENCHMARK-METRICS-PASS`，`[self] … 电池套件=43(判据脚本文件=26，两口径不同源即登记)`，
   漂移 3 处 = 实质 0 + 抖动 3（★ 单点差值不作趋势证据）。
7. ✅ **对标语义补测（本轮唯一新参照数据）**：16 个参照仓根目录 `.gitattributes` 探测
   （`gh api repos/<r>/contents/.gitattributes`，按 HTTP 状态分 ABSENT/PRESENT，base64 由 Python 解，
   不走 shell `base64 -d`）⇒ **存在 6/16，其中真钉行尾/二进制 4/16**
   （lobehub `eol=lf`×15 + `text=auto` + `binary`×15；leemo 1；opensoul `eol=lf`+`text=auto`；
   MoodChat 钉的是 `eol=crlf`），另 2 个存在但三类关键词计数均为 0。
   ⇒ 结论修正为：**"钉行尾"在同类项目里是少数派（4/16），但头部工程化项目（lobehub）在做**，
   本轮做法与最强者同形，不是自创规矩。
