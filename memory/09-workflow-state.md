# 09 - 动态工作流任务状态（状态唯一源）

> schema: fenjue-workflow-state-v1 | 本文件是**动态工作流引擎读取的任务状态表**（引擎侧唯一取数面）。
> 与 `07-next-steps.md` 的关系（按实现写，不写愿望）：`flow --sync` **只把 09 的 done/todo 勾选同步到 07**
> ——匹配到同一条目则改勾选位，匹配不到则在对应章节**追加**一行；若 07 已标完成而 09 不是 done，
> 它打印冲突并交人工裁决，**不覆盖 07**。任务表为空时 `--sync` 直接返回，此时 07 完全由人工维护。
> 因此：07 仍是项目台账的权威叙述面（可手工写）；09 只是引擎的任务视图，二者靠 sync 对齐勾选位。
> 状态枚举：`todo` / `doing` / `done` / `blocked`；批次：`P0` / `P1` / `P2`（`--next` **只在当前批次内取**：本批全 done 才进下一批；本批有 doing/blocked 而无可启动 todo 时**不跨批**，只列未完结项）。
> 用法：`handoff.py flow <项目路径> --status | --next | --start --id X | --done --id X [--evidence P] | --block --id X --reason R | --sync | --check | --add ...`

## 任务表

<!--
字段约定（机器解析，**勿改列名与列序**）：
| id | 批次 | 标题 | 状态 | 依赖 | 阻塞 | 更新于 | 证据 |
- id      唯一标识，建议 `<批次>-<序号>`；重复 = 解析报错
- 批次    P0 / P1 / P2；`--next` 依此顺序取批，本批全 done 才进下一批
- 标题    简短描述（不含 `|` 字符）
- 状态    todo / doing / done / blocked；其他值 = 解析报错
- 依赖    任务 id 逗号分隔；`-` 表示无依赖。依赖未 done 时 `--start` 拒绝
- 阻塞    `blocked` 状态必填原因；其余状态写 `-`
- 更新于  `YYYY-MM-DD HH:MM`（由 flow 自动写入）
- 证据    `done` 时填验收证据路径；其余写 `-`

示例行（在本注释内，不参与解析）：
| P0-1 | P0 | 示例任务 | todo | - | - | 2026-09-23 07:00 | - |
-->

| id | 批次 | 标题 | 状态 | 依赖 | 阻塞 | 更新于 | 证据 |
|----|----|----|----|----|----|----|----|
| VOL-04237 | P2 | 体量治理[L3 产物] <整仓> — 整仓瘦身：归档历史轮次产物 + recycle 备份残留 | todo | - | - | 2026-09-27 17:44 | - |
| VOL-FC486 | P2 | 体量治理[L3 产物] 交付物/ — 目录内逐类治理：产物拆分/归档，备份残留走 recycle | done | - | - | 2026-10-02 01:44 | b649a92 交付物 184.8→129.5MB；corpus 43 份是 disclaimer_lint --all 分母⇒不搬（详见 r90 报告 §2） |
| VOL-725F6 | P2 | 体量治理[L3 产物] server/ — 目录内逐类治理：产物拆分/归档，备份残留走 recycle | todo | - | - | 2026-09-27 17:44 | - |
| VOL-C85CA | P2 | 体量治理[L3 产物] 交付物/提交包/demo_video_out/心屿SoulIsle-演示视频.mp4 — 拆分或归档（禁直删） | todo | - | - | 2026-09-27 17:44 | - |
| VOL-04585 | P2 | 体量治理[L3 产物] _test/ — 目录内逐类治理：产物拆分/归档，备份残留走 recycle | todo | - | - | 2026-09-27 17:44 | - |
| VOL-EEB5B | P2 | 体量治理[L3 产物] 交付物/提交包/心屿SoulIsle-应用方案.pdf — 拆分或归档（禁直删） | todo | - | - | 2026-09-27 17:44 | - |
| VOL-0580C | P2 | 体量治理[L3 产物] 交付物/提交包/心屿MindIsle_参赛方案.pptx — 拆分或归档（禁直删） | todo | - | - | 2026-09-28 01:14 | - |
| VOL-AGG-20260928 | P1 | 体量治理[L1 记忆卷] 体量余量聚合（6 项） — 另有 6 项待判断，合计 139169 B——按字节降序只单列前 6 条，余量逐条见 memory/sessions/volume-snapshots.jsonl | todo | - | - | 2026-09-28 01:14 | - |
| WF-r73-接入CI契约 | P1 | 陪聊当前未接入 CI 全绿契约（.ci/contract.json 缺失），而 ciwatch 实扫到 1 份 workflow / run 执行面 89 行 ⇒ 未接入 ≠ 没有 CI，这 89 行里没有一条是被契约点名的 blocking 判据。一致接入四步（本引擎 wflow.adapters.sevenstep 对位）：① 生成 .ci/contract.json（把 mvn verify / 关键门禁逐条列 blocking）；② 在 .github/workflows/ci.yml 里为每条加 run step 并 --sweep 复扫到 matched==declared；③ pre-push 接线 greencheck；④ 保留本项目特性（Java/Maven 档位与 8123 回归口不并入引擎）。前提可复算命令：cd 本仓 && python D:/global_skills/A-project-handoff/scripts/handoff.py flow . --status | todo | - | - | 2026-09-28 02:10 | - |
| VOL-A5B8F | P2 | 体量治理[L3 产物] 交付物/提交包 (2).zip — 拆分或归档（禁直删） | done | - | - | 2026-10-02 01:44 | commit b649a92: git mv → archive/交付物-历史轮次/，判据认搬卷 rc=0 且 HOOK-DRILL-PASS |
| VOL-39DAB | P2 | 体量治理[L3 产物] 交付物/提交包.zip — 拆分或归档（禁直删） | done | - | - | 2026-10-02 01:44 | commit b649a92: git mv → archive/交付物-历史轮次/，判据认搬卷 rc=0 且 HOOK-DRILL-PASS |
| VOL-AGG-20260930 | P2 | 体量治理[L3 产物] 体量余量聚合（10 项） — 另有 10 项待判断，合计 26545458 B——按字节降序只单列前 6 条，余量逐条见 memory/sessions/volume-snapshots.jsonl | todo | - | - | 2026-09-30 02:16 | - |
| VOL-8EF30 | P2 | 体量治理[L3 产物] 交付物/提交包/demo_video_out/心屿MindIsle-演示视频.mp4 — 拆分或归档（禁直删） | todo | - | - | 2026-10-01 03:57 | - |
| VOL-CF954 | P2 | 体量治理[L3 产物] 交付物/心屿SoulIsle-作品提交-20260930.zip — 拆分或归档（禁直删） | todo | - | - | 2026-10-01 03:57 | - |
| VOL-AGG-20261001 | P2 | 体量治理[L3 产物] 体量余量聚合（15 项） — 另有 15 项待判断，合计 103704007 B——按字节降序只单列前 6 条，余量逐条见 memory/sessions/volume-snapshots.jsonl | todo | - | - | 2026-10-01 03:57 | - |
| WF-r90-sync状态词滞留 | P2 | flow --sync 只翻勾选位、不改登记行的「状态: todo」尾注 ⇒ 同一行 [x] 与 todo 自相矛盾（r90 实测 07.part62 VOL-FC486） | todo | - | - | 2026-10-02 01:45 | - |
| WF-r93-对标轮 | P1 | r93 八维对标 + 四项改进（loc 门 / rollup 两新增维度 / corpus 归档 / peers 全量重采落工作区） | done | - | - | 2026-10-02 23:10 | 报告 交付物/对标分析报告-2026-10-02-r93.md（提交 1846cf3/7ae33b9）；BENCHMARK-METRICS-PASS；DISCLAIMER-CLEAN 46 份(0+46)；搬卷 45/未验 0；REPO-CONFIG-PASS 17 项；BATTERY 116/116；CI run 37023508041/37027916208 绿 |
| WF-r93-loc超限治理 | P2 | loc 门 22/156 文件超限（最大 benchmark_metrics.py 1913 行/最长函数 628 行）⇒ 清零后切 --enforce 并加 CI 接线判据 | done | WF-r93-对标轮 | - | 2026-10-03 01:40 | r94：先修尺（22→8，14 项为类/IIFE 误判）→ 拆 10 个真超限函数 → **超限 0（LOC-PASS）** → 切 enforce + 接线自证 wiring_report()；selftest 9→17 条 |
| WF-r93-辅助台账重采 | P2 | peer-quality-tooling / peer-repro 两份台账分母 16 仍含已换址的旧 letta 行 ⇒ rollup 已标 stale，需重采 | done | - | - | 2026-10-03 01:40 | 两份 …-2026-10-03.json 在盘；有 lockfile 10→11/16、有测试结构 6→7/16；bench_rollup 改取最新+stale 按内容判定+产物名跟随 |
| WF-r93-cijob双读数 | P2 | ci_job数两个读数并存（benchmark_metrics ci_workflows=4 文件数 vs bench_rollup ci_jobs=5 job 条数）⇒ 统一口径或写清定义域 | done | - | - | 2026-10-03 01:40 | r94 已统一：实为**同名不同义**（self 侧 ci_workflows 实为 ci.yml job 条数，与 peers 的 GitHub API workflow 总数不同源）⇒ self 分列 ci_jobs_in_ci_yml/ci_workflow_files + 定义域 + 不变式断言 |
| WF-r93-loc超限治理 | P2 | loc 门 22/156 文件超限（最大 benchmark_metrics.py 1913 行/最长函数 628 行）⇒ 清零后切 --enforce 并加 CI 接线判据 | done | WF-r93-对标轮 | - | 2026-10-03 01:40 | r94：先修尺（22→8，14 项为类/IIFE 误判）→ 拆 10 个真超限函数 → **超限 0（LOC-PASS）** → 切 enforce + 接线自证 wiring_report()；selftest 9→17 条 |
| WF-r93-辅助台账重采 | P2 | peer-quality-tooling / peer-repro 两份台账分母 16 仍含已换址的旧 letta 行 ⇒ rollup 已标 stale，需重采 | done | - | - | 2026-10-03 01:40 | 两份 …-2026-10-03.json 在盘；有 lockfile 10→11/16、有测试结构 6→7/16；bench_rollup 改取最新+stale 按内容判定+产物名跟随 |
| WF-r94-probe落盘验证 | P2 | 8 个 peer_*_probe 的 `date -u` 已修（Windows 无此命令，致「跑完不写盘」），但只实跑验证了 repro 一个 | todo | - | - | 2026-10-03 01:40 | 编译全过；`peer_repro_probe --self-only --json` 实跑落盘已验；其余 7 个待用到时实跑 |

## 推进记录

<!-- append-only，最新在下；由 flow --start / --done / --block 自动追加 -->

- [2026-09-27 17:44] 体量体检登记 7 项（待判断项转任务，id 前缀 VOL-）
- [2026-09-28 01:14] 体量体检登记 2 项（待判断项转任务，id 前缀 VOL-）
- [2026-09-28 02:10] WF-r73-接入CI契约 新增（P1，todo）
- [2026-09-30 02:16] 体量体检登记 3 项（待判断项转任务，id 前缀 VOL-）
- [2026-10-01 03:57] 体量体检登记 3 项（待判断项转任务，id 前缀 VOL-）
- [2026-10-02 01:44] VOL-39DAB todo → doing
- [2026-10-02 01:44] VOL-39DAB doing → done
- [2026-10-02 01:44] VOL-A5B8F todo → doing
- [2026-10-02 01:44] VOL-A5B8F doing → done
- [2026-10-02 01:44] VOL-FC486 todo → doing
- [2026-10-02 01:44] VOL-FC486 doing → done
- [2026-10-02 01:45] WF-r90-sync状态词滞留 新增（P2，todo）
- [2026-10-02 22:10] WF-r93-对标轮 新增（P1，doing）＋ WF-r93-loc超限治理 / WF-r93-辅助台账重采 / WF-r93-cijob双读数 新增（P2，todo）

## 分卷目录

<!-- 本文件超 4KB 时由 flow 自动调用拆卷能力，分卷索引写于此节（R199 体量治理） -->
