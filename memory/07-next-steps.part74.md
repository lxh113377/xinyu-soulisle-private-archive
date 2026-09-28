# 07-next-steps 卷74 — r72（G17 把取数面钉成闸 + 技能侧闭环补欠）

> 取号 `volume_alloc.py`（O_EXCL）｜报告 `交付物/对标分析报告-2026-09-28-r72.md`｜入场基线 `0509595`

## 一、本轮做了两件"把上轮结论变成机器不许违反"的事

1. **G17 新判据（`repo_config_check.py`，销 R71-01）**：对标台账末次 run 的 self 行必须显式
   `self_face="HEAD"`、`regression_suites` 为正整数、`self_face_errors` 为空，否则判红；
   整个 self 行读不到也算红（无对象不得判绿）。**台账套件数与 HEAD 现算值的差只印不拦**——
   CI 里没法重跑联网采集刷新台账，拦它就是造一条不可自愈的红（进阻断链前三问）。
   判据数 14→15；`--selftest` 合成篡改 **56→64 条**（㉒a 真台账不误伤／㉒b 抹面声明／㉒c 降级 worktree／
   ㉒d 面报错仍落账／㉒e suites=0／㉒f 整行缺失）。**端到端另走读取器**（真台账 + 两份临时副本三态）。
2. **技能侧欠账清零（A-skill-manager 收尾硬门禁）**：r70/r71 我两次改 `A-get-memory/SKILL.md` 权威源
   却没跑镜像同步与派生件重建 ⇒ 七端实际读到的还是旧版（"改了等于没改"）。本轮实测链条：
   `check-skill-mirror.ps1` 先报 `missing=4 mismatch=16`（**含 `A-get-memory\SKILL.md`**，归属实测）
   → `-Fix` → 复检 `[GATE:mirror-pass] missing=0 mismatch=0（extra=15 警告级）`；
   `build_indexes.py --apply` 守恒 PASS 166 条；`verify_truth_consistency.py` **34 PASS/0 FAIL/0 SKIP**；
   `disk_registry_diff.py` 漏注册 0／回滚 0／幽灵 0；派生件**不提交**（铁律 5）。

## 二、Step 0 盘点里新发现的两条（都不代改）

- `handoff.py noise` 共 **36 条 VIOL**，其中**焚诀根目录 5 个 0 字节句子片段散件**
  （`⚠️`、`处置：…`、`成因：…`、`归属：…`、`影响：…`），mtime 全为 09-28 **08:34**，
  早于本会话第一条写入（12:4x）⇒ **非我所有**；形态正是"未加引号 heredoc 被命令替换后把正文当文件名"。
  该仓 `porcelain=242`、`staged=175` ⇒ 入场三闸 **G-b 命中** ⇒ 禁 `git add`/禁清理他人半成品，只登记。
  复算：`cd 焚诀 && python <handoff> noise`。
- 8123 上仍是 **08:36 起的旧 jar 进程**：`jar_shape` 只保证**产物**是 fat 且不旧，**不保证进程是新的**
  ⇒ 回归前必须 `python _test/build_jar.py`（它先停占用者再构建再验货）。

## 三、仍被同一前提挡住的三条（复算命令在括号内）

`R70-01` 补 SUITES 两条＋README 计数、`R70-02` 分桶并行第一刀（`HEAD SUITES=99` vs `--list=101`，他方未入库）；
`R71-02` 切版（`python _test/release_governance_check.py` → `feats=7/5`，r71 我自己的 feat 又推一格）；
`live_sync`/`ci_status`（受 09-24 冻结裁决约束）。**R1 与"切版须 CI 绿"互为前置 ⇒ 自我锁死，只由老大开环。**

## 四、未闭合（不折叠）

R1↔切版锁死｜发布授权｜SUITES 两条目（等他笔入库）｜并行第一刀｜真机复跑｜flake 原文｜
焚诀根 5 个散件（他人现场）｜`i18n_locale` 按裁决排后
