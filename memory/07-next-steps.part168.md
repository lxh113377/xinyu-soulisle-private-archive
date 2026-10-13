# 07-next-steps.part168.md

<!-- 本卷为 07-next-steps.part32.md 的延续 -->

## P2｜`08-ac-obs.md` 的 AC id 存量重编号（7 个 id 各挂两条命题）

- [ ] VOL-AGG-f12a8a 体量治理[L3 产物] 体量余量聚合（61 项） — 另有 61 项待判断，合计 188575995 B——按字节降序只单列前 6 条，余量逐条见 memory/sessions/volume-snapshots.jsonl（由 flow 登记；状态: todo）
- [ ] VOL-AGG-6d668c 体量治理[L3 产物] 体量余量聚合（57 项） — 另有 57 项待判断，合计 193735506 B——按字节降序只单列前 6 条，余量逐条见 memory/sessions/volume-snapshots.jsonl（由 flow 登记；状态: todo）
- [ ] VOL-AGG-b5d07b 体量治理[L3 产物] 体量余量聚合（56 项） — 另有 56 项待判断，合计 192780973 B——按字节降序只单列前 6 条，余量逐条见 memory/sessions/volume-snapshots.jsonl（由 flow 登记；状态: todo）
- [ ] VOL-AGG-0c2511 体量治理[L3 产物] 体量余量聚合（42 项） — 另有 42 项待判断，合计 192208085 B——按字节降序只单列前 6 条，余量逐条见 memory/sessions/volume-snapshots.jsonl（由 flow 登记；状态: todo）
- [ ] VOL-AGG-db2ad9 体量治理[L3 产物] 体量余量聚合（41 项） — 另有 41 项待判断，合计 216450694 B——按字节降序只单列前 6 条，余量逐条见 memory/sessions/volume-snapshots.jsonl（由 flow 登记；状态: todo）
- [ ] VOL-F443C 体量治理[L3 产物] _temp/ 缓存簇 — 超上限但无超龄项（TTL 14 天内）⇒ 本轮不处置（由 flow 登记；状态: todo）
- [ ] VOL-AGG-3237c7 体量治理[L3 产物] 体量余量聚合（53 项） — 另有 53 项待判断，合计 362326616 B——按字节降序只单列前 6 条，余量逐条见 memory/sessions/volume-snapshots.jsonl（由 flow 登记；状态: todo）
- [ ] VOL-13B40 体量治理[L3 产物] _temp/pristine/archive/交付物-历史轮次/提交包 (2).zip — 可再生缓存目录内文件：gitignore 命中未证实 ⇒ 本轮只可见不处置（在 git 仓里会走 TTL + recycle）（由 flow 登记；状态: todo）
- [ ] VOL-9E7EB 体量治理[L3 产物] _temp/ — 目录内逐类治理：产物拆分/归档，备份残留走 recycle（由 flow 登记；状态: todo）

- **实测（22:1x，`python` 解析定义行）**：08 共 **30 条 AC 定义、只用掉 23 个 id**；
  `AC-OBS-13 / 14 / 15 / 16 / 17 / 18 / 19` **每个出现 2 次**，且两次是**互不相干的命题**：
  - `AC-OBS-19` = 「首屏第三方库可溯源」（r20）**又**=「容器镜像真构建真运行」（2026-09-23）
  - `AC-OBS-18` = 「危机拦截不因后端化而延迟」（r20）**又**=「Dockerfile 镜像内容物可证」（2026-09-23）
  - （13/14/15/16/17 同形，均为"旧命题 + 9-23 新命题"共用一号）
- **危害不是难看**：`handoff.py flow . --verify-ac` 按 id 汇报，实测回显里同一 id 两行并存、
  整套被它数成 **24 条 AC**（定义数 30、唯一 id 23 ⇒ 三个数互不相等，说明它的计数口径也不可信）。
  追溯键重复 ⇒ 一条判红不知道该勾哪一行、07/CHANGELOG 里"见 AC-OBS-18"这种引用**指不到唯一对象**。
- **为什么本轮不直接重编号**：18/19/13 等号在 `README.md`、`05-feature-status`、多份 07 分卷、
  CHANGELOG 里被交叉引用，改号会一次性制造十几处死链（属跨文档结构改动，不是顺手活）。
- **本轮已做的（防增量）**：`_test/repo_config_check.py` 新增 **G15** 棘轮——
  额外重复数 > 基线 7 即判红（存量放行、新造重复当场红），三条合成篡改断言在册
  （真文件放行 / 多造一条重复须红 / 零定义须红，`--selftest` 42 条全过）。
- **下轮做法建议**：以"新增命题一律取新号（下一个空号 = 24 之后）"为过渡纪律，
  再挑一次干净窗口按 9-23 那批整体重编号并同步全部交叉引用（G15 基线随之下调到 0）。
