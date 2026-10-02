# 07-next-steps 分卷 · r94（2026-10-03）

> 本卷记 r93 遗留三项的执行结果；壳层 `07-next-steps.md` 的 P0/P1 摘要按本卷实况更新。

## ① 本轮状态（r94）

- **loc 门从「只报」变成「会红」**：先修尺（类/IIFE 不计函数长、嵌套函数改为逐层测量），
  再逐个拆分 10 个真超限函数，最后 **超限 0** 并切 `enforce`（已进电池）。
  自检由 9 条扩到 **17 条**（新增 4 条分类腿 + 3 条接线腿）。
- **CI 口径统一**（r92 遗留的「双读数」查清了）：self 侧原有一个叫 `ci_workflows` 的字段，
  实际数的是 **ci.yml 的 job 条数**（连 perf-baseline.yml 都没算），与 peers 侧同名不同义 ⇒
  已分列 `ci_jobs_in_ci_yml` / `ci_workflow_files` 并写死定义域，peers 侧键名不动。
- **两份 peers 台账重采**：`peer-quality-tooling-2026-10-03.json` / `peer-repro-2026-10-03.json`
  均落盘。有 lockfile 10/16 → **11/16**、有测试结构 6/16 → **7/16**（换址的收益第一次在数据上体现）。
- 报告 `交付物/对标分析报告-2026-10-03-r94.md`（留根目录，为最新一轮）。

## ② 顺手修掉的同族坑（可复用）

1. **尺的误判比项目的问题更危险**：loc 门 22 项超限里 **14 项是误判**（Java 类 + JS IIFE 当函数）。
   照单治理会去拆类/拆模块 ⇒ 破坏 `src/` 运行时代码、撞同步红线。**先问「尺在量什么」再问「怎么改」**。
2. **`date -u` 在 Windows 上不存在**：8 个 peers probe 都用它取时间戳 ⇒「跑完统计但产物没落盘」，
   不看 stderr 会误判成功。已全换 `datetime.now(timezone.utc)`。同族判据：`gh` 的 0 字节占位文件。
3. **两把尺互相牵制**：拆分让文件行数顶到 2051（行数门红），压行后补 CI 口径统一又到 2021，再压到 1988。
   修一把尺可能踩另一把 —— 报告里必须两把都写。
4. **验真要比运行结果，不能比源码文本**：比对 `--selftest` 时曾用正则去源码里抓 PASS 行，
   抓到的是 print 语句里的 f-string 源码（13379 字符）⇒ 比对无意义。正解是实跑 HEAD 副本逐字比。

## ②-1 本轮第三个判据盲区（一手，`eol_parity` 只查 HEAD 面）

- **现象**：本轮入库的一批 `_r94_*.py` 在**工作树里是 CRLF**，而提交时 git 归一为 LF 存入 blob
  ⇒ 提交后 `eol_parity` 判红「工作树字节 != blob 字节」。但**提交前跑它是绿的**。
- **根因**：`eol_parity` 的扫描面是 `git ls-tree HEAD`（git HEAD 面）⇒ **未入库的新文件在入库前完全不被检查**。
  同一分钟内我写文件 → 归一 → 提交，顺序上没问题；但**提交后**工作树与 blob 的字节关系变了，门才变红。
- **含义**：这道门有个时间窗——「刚写完、还没入库」的窗口是盲区。**入库后必须再跑一次归一**，
  否则 CI/下一次本地跑就会红，而红因看起来像「我明明归一过了」。
- **处置**：本轮已归一（归一后与 HEAD 零差异，证实**入库 blob 一直是 LF，正确的**），
  并把「写文档/脚本 → 归一 → 提交 → **再归一一次**」固化为流程。
  下轮可考虑给 `eol_parity` 加一条 `--worktree` 面（含未入库文件），或至少在门面行印出
  「本门只查 HEAD 面，未入库文件不在内」。

## ②-2 事故留档：15 个交付物二进制被我改坏（已全部恢复）

`_r94_eol.py` 第二版用 `git check-attr` 判二进制，`subprocess.run(text=True)` 按 locale 解码
git 的 UTF-8 输出 ⇒ 中文路径乱码 ⇒ 二进制判定失效 ⇒ 15 个 PNG/ZIP/PDF/MP4 被当文本 CRLF→LF
改写。`git status` 见 15 个二进制呈 `M` ⇒ 逐个 `git checkout --` 恢复 ⇒ 复检 0。

两条硬规矩（已落进脚本与流程）：
1. **凡「按路径匹配子进程输出」的代码必须显式 `encoding="utf-8"`**（本仓同族坑第三条：
   `gh` 0 字节占位文件 / `date -u` 跨平台 / 本次 locale 乱码）。
2. **破坏性批量操作先 dry-run**：`_r94_eol.py` 现默认 dry-run，`--apply` 才改盘；
   两道闸：只碰文本类扩展名 + 前 8KB 含 NUL 一律跳过。**属性表会漏，字节不会。**

产品面：`eol_parity` 扩为双面（已跟踪/未入库两个分母都印在门面行）+ 自检补 4 条未入库腿。

## ③ 下一轮入口（r95）

1. 8 个 probe 的写盘段只验了 `peer_repro_probe --self-only --json` 真落盘，其余 7 个未实跑 ——
   下轮重采用到哪几个就验哪几个，别拿「同构代码」当已验。
2. loc 阈值 2000/150 是借来的（opensoul `check:loc`，已坐实其命令行）；本仓既有更严约束是
   `size_budget` 字节预算与 Core P0.8 函数 ≤50 行，两把并存，面板已并列打印。
3. 维持不立项项触发条件不变：lint 门（2/16）、向量长记忆（7/16）、i18n（3/16）、插件协议。

## ④ 收口回执

- `loc_guard_check.py` → `LOC-PASS`（超限 0）｜`--selftest` 17/17
- `benchmark_metrics.py --selftest` 与 HEAD 版逐字相同（960 字符，rc=0）
- `BENCHMARK-METRICS-PASS`（16/16 仓，产物 `benchmark-metrics-r94.json`）
- 两份台账落盘 + `ROLLUP-PASS`（产物 `benchmark-rollup-r94.json`，轮次名自动跟随）
- 8 个 probe 的 `date -u` 修复：编译过 + `--self-only --json` 实跑落盘
- **收口全量电池：第 5 轮 `116/116 rc=0 ALL-GREEN`**（`交付物/对标数据/bench-r94-battery5.log`，合计 919s，台账指纹 `sha256=f874b118…`）。前 4 轮各红 1–2 条且**各不相同**，逐条归因见报告 §2.6。
- 门禁面复核（收口时现跑）：`LOC-PASS`（enforce 身份）｜`EOL-PARITY-PASS`（text 461 / binary 28）｜`REPO-CONFIG-PASS` 17 项 18 判据号｜`DELIVERABLE-INVENTORY-PASS`｜`DISCLAIMER-CLEAN` 48 份（交付物 2 + _历史轮次-对标 46）0 缺口｜`BRAND-PASS`。
- **提交 `1de2a9a`**（已推 `origin/main`，本地 == 远端）；CI run 在后台，收口后补回执。
- 唯一未纳入提交的三项（按铁律排除）：`memory/AGENTS.md`（并行会话在途）、`.ci/`（r90 遗留，未做 `--sweep` 复扫到 `matched==declared`，不在未验状态替他入库）、`memory/07-next-steps.part105.md`。
