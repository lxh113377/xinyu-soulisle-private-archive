# 07-next-steps 卷72 — r71（台账取数面换到 git + 吞标题升成阻断判据 R6）

> 取号 `volume_alloc.py`（O_EXCL）｜报告 `交付物/对标分析报告-2026-09-28-r71.md`｜入场基线 `1068a9e`

## 一、两条一手事实

1. **self 与 peers 取数面不同构**：`self_metrics()` 用 `rglob` 扫工作树，参照仓的 `file_count`/树来自 GitHub 仓库树
   ⇒ 把按红线 gitignore 的本机密钥件 `src/js/demo-config.js` 算进了横向统计（`comm` 实测唯一差集就是它）。
   历史报告「src(除 vendor)=2,516 行 / 20 文件」里的 20 含一个本机文件；HEAD 面真值 **2,488 / 19**。
2. **台账把在途态写成现状**：`regression_suites` 当日两次采集都记 **101**，HEAD 实数 **99**
   （多出 2 条＝并行会话未入库的 `suite_census`）⇒ 换机器/CI 干净克隆必然复算不出。

## 二、修了什么

- `_test/benchmark_metrics.py`：self 行整行改取 `git ls-tree -r HEAD` + `git show HEAD:<path>`；
  取不到面 ⇒ `self_face=取数失败`，**禁止静默退回工作树**；新增 `self_face`/`regression_suites_face`/
  `worktree_extra_untracked`/`worktree_only_src_files`（差值只印不计数）。
- `_test/release_governance_check.py`：新增 **R6**（CHANGELOG `### ` 标题集只增不减），
  双基准 `HEAD`（未提交的吞行）＋`HEAD~1`（已提交的吞行；CI 里 worktree==HEAD，只看 HEAD 恒等即失明），
  两基准都取不到 ⇒ `R6(未验)` 不判绿。动因＝r70 我自己拿条目行当锚点没回写，吞掉 `### Fixed（r69 · …）`。

## 三、回执

- `benchmark_metrics.py --selftest` 尾部含「r71 self 行取数面 = git HEAD」；三向控制＝加一件 +1／减一件 -1／零人口不判绿
- `release_governance_check.py --selftest` **17/17→21/21**（边界 I/J/K/L）
- 验真①真实历史两笔：`20f0da6→ea8a0b3` 判红且点名；`→6ac8722` 转绿
- 验真②变异只打副本（A-get-memory ⑰-b）：摘 R6 判红 ⇒ 边界J 翻红 `20/21`；真实源 sha `4071ebb9ce58` 前后相等
- 台账末次 run（当日第 3 次采集）：self=19 文件 / 2,488 行 / 99 套件 / peers 矩阵与 13:09 一致（实质漂移 0）

## 四、一条新纪律 + 一条设计缺陷（待裁决）

- **采集器自己的源码也是被测面**：当日第 2 次采集跑在我改 `benchmark_metrics.py` 的当口 ⇒ 作废重跑。
  与 r70 `eol_parity` 瞬时红同族 ⇒ **整跑/采集期间本会话不改仓内文件**。
- ⚠️ **R1 与切版规矩互相咬死（自我锁死）**：`release_governance` R1 现判红（**7 个 feat＞上限 5**，本轮自己的 feat 又把计数推一格）且是阻断项，
  而在册切版链条要求「push → **CI 绿** → `gh release create`」；CI 绿又要求 R1 不红 ⇒
  **唯一开环仍是发布授权**（消 `live_sync`）或把 R1 降为 advisory。本轮**两条都不擅自做**，交裁决。

## 五、未闭合（不折叠）

R1 红着（同上）｜`live_sync`/`ci_status` 待发布授权｜R70-01（补 SUITES 两条）仍被并行会话在途 hunk 挡
（HEAD 99 vs 工作树 101）｜真机复跑未做｜flake 对标缺原文｜`i18n_locale` 3/16 是唯一真实产品差距（09-24 已排赛后）
