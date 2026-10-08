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
| WF-r73-接入CI契约 | P1 | 陪聊当前未接入 CI 全绿契约（.ci/contract.json 缺失），而 ciwatch 实扫到 1 份 workflow / run 执行面 89 行 ⇒ 未接入 ≠ 没有 CI，这 89 行里没有一条是被契约点名的 blocking 判据。一致接入四步（本引擎 wflow.adapters.sevenstep 对位）：① 生成 .ci/contract.json（把 mvn verify / 关键门禁逐条列 blocking）；② 在 .github/workflows/ci.yml 里为每条加 run step 并 --sweep 复扫到 matched==declared；③ pre-push 接线 greencheck；④ 保留本项目特性（Java/Maven 档位与 8123 回归口不并入引擎）。前提可复算命令：cd 本仓 && python D:/global_skills/A-project-handoff/scripts/handoff.py flow . --status | done | - | - | 2026-10-05 03:05 | **r95 落地**：① bootstrap 实测 checks=[] ⇒ 改手写 blocking 14 条（实测合计 10021ms/20s 预算）；② 契约**已入库**（r90~r94 四轮只生成未入库 ⇒ greencheck 恒 UNKNOWN ⇒ pre-push 恒放行，实测坐实）；③ pre-push 钩子早就在位（greencheck 通用模板 2378B）。回执 `[greencheck] GREEN` 14 条全绿 rc=0 10.1s。**注：②里的"加 run step 并 --sweep 复扫"在本仓不成立**——greencheck 无 --sweep 子命令，改由 _test/ci_contract_check.py 的接线腿替代（每条 blocking 的脚本必须在 CI 或电池里有执行位）。见 r95 报告 §2.1 |
| VOL-A5B8F | P2 | 体量治理[L3 产物] 交付物/提交包 (2).zip — 拆分或归档（禁直删） | done | - | - | 2026-10-02 01:44 | commit b649a92: git mv → archive/交付物-历史轮次/，判据认搬卷 rc=0 且 HOOK-DRILL-PASS |
| VOL-39DAB | P2 | 体量治理[L3 产物] 交付物/提交包.zip — 拆分或归档（禁直删） | done | - | - | 2026-10-02 01:44 | commit b649a92: git mv → archive/交付物-历史轮次/，判据认搬卷 rc=0 且 HOOK-DRILL-PASS |
| VOL-AGG-20260930 | P2 | 体量治理[L3 产物] 体量余量聚合（10 项） — 另有 10 项待判断，合计 26545458 B——按字节降序只单列前 6 条，余量逐条见 memory/sessions/volume-snapshots.jsonl | todo | - | - | 2026-09-30 02:16 | - |
| VOL-8EF30 | P2 | 体量治理[L3 产物] 交付物/提交包/demo_video_out/心屿MindIsle-演示视频.mp4 — 拆分或归档（禁直删） | todo | - | - | 2026-10-01 03:57 | - |
| VOL-CF954 | P2 | 体量治理[L3 产物] 交付物/心屿SoulIsle-作品提交-20260930.zip — 拆分或归档（禁直删） | todo | - | - | 2026-10-01 03:57 | - |
| VOL-AGG-20261001 | P2 | 体量治理[L3 产物] 体量余量聚合（15 项） — 另有 15 项待判断，合计 103704007 B——按字节降序只单列前 6 条，余量逐条见 memory/sessions/volume-snapshots.jsonl | todo | - | - | 2026-10-01 03:57 | - |
| WF-r90-sync状态词滞留 | P2 | flow --sync 只翻勾选位、不改登记行的「状态: todo」尾注 ⇒ 同一行 [x] 与 todo 自相矛盾（r90 实测 07.part62 VOL-FC486） | blocked | - | 责任面在受管根 global_skills/A-project-handoff，本仓无执行位 | 2026-10-05 12:56 | - |
| WF-r93-对标轮 | P1 | r93 八维对标 + 四项改进（loc 门 / rollup 两新增维度 / corpus 归档 / peers 全量重采落工作区） | done | - | - | 2026-10-02 23:10 | 报告 交付物/对标分析报告-2026-10-02-r93.md（提交 1846cf3/7ae33b9）；BENCHMARK-METRICS-PASS；DISCLAIMER-CLEAN 46 份(0+46)；搬卷 45/未验 0；REPO-CONFIG-PASS 17 项；BATTERY 116/116；CI run 37023508041/37027916208 绿 |
| WF-r93-loc超限治理 | P2 | loc 门 22/156 文件超限（最大 benchmark_metrics.py 1913 行/最长函数 628 行）⇒ 清零后切 --enforce 并加 CI 接线判据 | done | WF-r93-对标轮 | - | 2026-10-03 01:40 | r94：先修尺（22→8，14 项为类/IIFE 误判）→ 拆 10 个真超限函数 → **超限 0（LOC-PASS）** → 切 enforce + 接线自证 wiring_report()；selftest 9→17 条 |
| WF-r94-收口 | P1 | r94 收口：五轮电池取最终绿 + 门禁面复核 + 提交推送 + CI 回执 | done | - | - | 2026-10-03 02:40 | BATTERY 第5轮 116/116 ALL-GREEN（919s）｜LOC/eol/repo_config/inventory/disclaimer/brand 六门全绿｜提交 1de2a9a 已推 |
| WF-r93-辅助台账重采 | P2 | peer-quality-tooling / peer-repro 两份台账分母 16 仍含已换址的旧 letta 行 ⇒ rollup 已标 stale，需重采 | done | - | - | 2026-10-03 01:40 | 两份 …-2026-10-03.json 在盘；有 lockfile 10→11/16、有测试结构 6→7/16；bench_rollup 改取最新+stale 按内容判定+产物名跟随 |
| WF-r93-cijob双读数 | P2 | ci_job数两个读数并存（benchmark_metrics ci_workflows=4 文件数 vs bench_rollup ci_jobs=5 job 条数）⇒ 统一口径或写清定义域 | done | - | - | 2026-10-03 01:40 | r94 已统一：实为**同名不同义**（self 侧 ci_workflows 实为 ci.yml job 条数，与 peers 的 GitHub API workflow 总数不同源）⇒ self 分列 ci_jobs_in_ci_yml/ci_workflow_files + 定义域 + 不变式断言 |
| WF-r94-probe落盘验证 | P2 | 8 个 peer_*_probe 的 `date -u` 已修（Windows 无此命令，致「跑完不写盘」），但只实跑验证了 repro 一个 | done | - | - | 2026-10-05 12:56 | 15 份写盘回执见 bench-r96-*.log；结论在 r96 报告 §0/§2.4 |
| WF-r95-对标轮 | P1 | r95 八维对标 + 五项改进（CI 契约入库/契约结构门/30 天提交率尺/台账 SNAP 刷新/电池 120） | done | - | - | 2026-10-05 12:56 | 报告 r95.md；提交 5bd5bc3/6fe3d58/fb7c6e7；CI-WATCH-GREEN 两次 |
| WF-r95-契约入库 | P0 | `.ci/contract.json` 未入库 ⇒ greencheck 恒 UNKNOWN ⇒ pre-push 钩子恒放行（r90 登记 5 轮未动） | done | WF-r73-接入CI契约 | - | 2026-10-05 03:05 | 5bd5bc3：契约手写重做（blocking 14 条 / 实测 10021ms / name 唯一 / 总预算可复算 / deferred 逐条写明承接面）并入库；`[greencheck] GREEN` rc=0 |
| WF-r95-契约自身结构门 | P1 | 契约会被后人改坏（同名/空清单/成本虚报/列了没人跑）⇒ 需常驻门 | done | WF-r95-契约入库 | - | 2026-10-05 03:05 | `_test/ci_contract_check.py` 9 腿 + 自检 15 条；同时进电池与契约 blocking 自身；套件 116→120。自检抓到本件自身 bug：`any(s in x for x in (集合,集合))` 对容器做成员判定恒 False ⇒ 14 条合法 blocking 全被误报 |
| WF-r95-提交率尺 | P2 | 「维护状态」维只有状态快照（★/pushed/release），无 30 天同口径窗口；★ 与维护度反向已实测 | done | - | - | 2026-10-05 03:05 | `_test/peer_maintenance_probe.py`（两腿交叉验证 + 印历史跨度 + `--self-only`/`--selftest` 14 条）；台账 `peer-maintenance-2026-10-05.json` 在盘；MoodChat 两腿差 1 ⇒ 判不可用不取平均 |
| WF-r95-台账SNAP刷新 | P2 | 权威 `benchmark-metrics.json` 自 10-02 停滞，G17 报「台账记 112 / HEAD 现算 116」 | done | - | - | 2026-10-05 03:05 | 本轮重采 16/16；G17 差值 −4 → 0；README 电池数 118→120（G4 抓红后改，不是事后凑绿） |
| WF-r95-落后格触发条件 | P2 | lint 门（peers 3/16）/ vector 记忆（7/16）/ i18n（3/16）/ mutation 门（0/16）—— 全部维持不执行，但把触发条件写死 | todo | - | - | 2026-10-05 03:05 | 触发条件见 r95 报告 §3 #7/#8：lint = 引入前端构建链或 size_budget 预算容得下 node_modules；vector = ①跨会话语义召回需求 ②接受双运行时（决策 #1 重评）；mutation = 覆盖率门连续两轮无新增缺口 |
| WF-r96-对标轮 | P1 | r96 八维对标 + 四项改造（issue响应尺/并发口径封口/龄期尺+探针接线/引擎面归因+交付卫生） | done | - | - | 2026-10-05 17:58 | 报告 r96.md；tag v1.8.0+Release；CI-WATCH-GREEN 3991069c；电池 124/125 唯一红=voice 真缺陷 |
| VOL-CC6BC | P1 | 体量治理[L5 自动化链] _trash/ 回收区超龄 — 人工核后清空该面 `_trash`（`handoff.py recycle --list <锚点>` 逐项看）；治理链不自作清历史 —— 里面混着人工裁决过的件 | todo | - | - | 2026-10-05 22:57 | - |
| VOL-AGG-11523b | P2 | 体量治理[L3 产物] 体量余量聚合（14 项） — 另有 14 项待判断，合计 87869470 B——按字节降序只单列前 6 条，余量逐条见 memory/sessions/volume-snapshots.jsonl | todo | - | - | 2026-10-05 22:57 | - |
| WF-r97-voice退出态 | P1 | voice 退出态真缺陷修复 + v1.8.1 切版（r94/r95/r96 三轮挂账项） | done | - | - | 2026-10-06 04:50 | src/js/voice.js 幂等 leaveListening + start() try；桩腿 A8/A9/A10 先验红后验绿，带 base 11 轮全 rc=0 |
| WF-r97-v1.8.1发布链 | P0 | 推 main+tag v1.8.1+CI 回执+Release（Pages 面未发布，CI 电池不豁免 live 面） | blocked | - | 本机无 CF 凭据（env 全 unset / ~/.wrangler 不存在 / gh secret 空 / 全局 wrangler 崩），pages.dev 无法更新 ⇒ live_sync 判红未解，推送链 held。前提=npx wrangler pages deploy xinyu --project-name=xinyu-soulisle --commit-dirty=true | 2026-10-06 04:50 | - |
| VOL-AGG-da9b83 | P2 | 体量治理[L3 产物] 体量余量聚合（14 项） — 另有 14 项待判断，合计 87861530 B——按字节降序只单列前 6 条，余量逐条见 memory/sessions/volume-snapshots.jsonl | todo | - | - | 2026-10-06 04:57 | - |
| WF-r100-对标轮 | P1 | r100 八维对标 + 四项改造（判据三态纪律/性能中位数口径/__pendingTurns 完成态/peers 错峰重采） | done | - | - | 2026-10-08 06:11 | 报告 r100.md；四项回执见 07.part129/part130（②为负面结论） |

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
- [2026-10-05 12:56] WF-r94-probe落盘验证 todo → done
- [2026-10-05 12:56] WF-r95-对标轮 doing → done
- [2026-10-05 12:56] WF-r90-sync状态词滞留 todo → blocked（责任面在受管根 global_skills/A-project-handoff，本仓无执行位）
- [2026-10-05 12:57] WF-r96-对标轮 新增（P1，todo）
- [2026-10-05 12:57] WF-r96-对标轮 todo → doing
- [2026-10-05 17:58] WF-r96-对标轮 doing → done
- [2026-10-05 22:57] 体量体检登记 2 项（待判断项转任务，id 前缀 VOL-）
- [2026-10-06 04:12] WF-r97-voice退出态 新增（P1，doing）
- [2026-10-06 04:50] WF-r97-voice退出态 doing → done
- [2026-10-06 04:50] WF-r97-v1.8.1发布链 新增（P0，todo）
- [2026-10-06 04:50] WF-r97-v1.8.1发布链 todo → blocked（本机无 CF 凭据（env 全 unset / ~/.wrangler 不存在 / gh secret 空 / 全局 wrangler 崩），pages.dev 无法更新 ⇒ live_sync 判红未解，推送链 held。前提=npx wrangler pages deploy xinyu --project-name=xinyu-soulisle --commit-dirty=true）
- [2026-10-06 04:57] 体量体检登记 1 项（待判断项转任务，id 前缀 VOL-）
- [2026-10-08 06:10] WF-r100-对标轮 新增（P1，todo）
- [2026-10-08 06:11] WF-r100-对标轮 todo → done

## 分卷目录

<!-- 本文件超 4KB 时由 flow 自动调用拆卷能力，分卷索引写于此节（R199 体量治理） -->
