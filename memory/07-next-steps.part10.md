# 07-next-steps.part10.md

<!-- 本卷为 07-next-steps.part5.md 的延续 -->

- [x] ~~DeepSeek Key 轮换~~ ✅ 2026-09-22 已完成（见 `part9`）。**本条属台账漂移**：`part5` 一直挂着未勾，2026-09-23 盘点时确认为重复条目，已关闭。

## P2 — 可以做
- [ ] VOL-AGG-11523b 体量治理[L3 产物] 体量余量聚合（14 项） — 另有 14 项待判断，合计 87869470 B——按字节降序只单列前 6 条，余量逐条见 memory/sessions/volume-snapshots.jsonl（由 flow 登记；状态: todo）
- [ ] WF-r95-落后格触发条件 lint 门（peers 3/16）/ vector 记忆（7/16）/ i18n（3/16）/ mutation 门（0/16）—— 全部维持不执行，但把触发条件写死（由 flow 登记；状态: todo）
- [x] WF-r95-台账SNAP刷新 权威 `benchmark-metrics.json` 自 10-02 停滞，G17 报「台账记 112 / HEAD 现算 116」（由 flow 登记；状态: done）
- [x] WF-r95-提交率尺 「维护状态」维只有状态快照（★/pushed/release），无 30 天同口径窗口；★ 与维护度反向已实测（由 flow 登记；状态: done）
- [x] WF-r94-probe落盘验证 8 个 peer_*_probe 的 `date -u` 已修（Windows 无此命令，致「跑完不写盘」），但只实跑验证了 repro 一个（由 flow 登记；状态: done）
- [x] WF-r93-cijob双读数 ci_job数两个读数并存（benchmark_metrics ci_workflows=4 文件数 vs bench_rollup ci_jobs=5 job 条数）⇒ 统一口径或写清定义域（由 flow 登记；状态: done）
- [x] WF-r93-辅助台账重采 peer-quality-tooling / peer-repro 两份台账分母 16 仍含已换址的旧 letta 行 ⇒ rollup 已标 stale，需重采（由 flow 登记；状态: done）
- [x] WF-r93-loc超限治理 loc 门 22/156 文件超限（最大 benchmark_metrics.py 1913 行/最长函数 628 行）⇒ 清零后切 --enforce 并加 CI 接线判据（由 flow 登记；状态: done）
- [ ] WF-r90-sync状态词滞留 flow --sync 只翻勾选位、不改登记行的「状态: todo」尾注 ⇒ 同一行 [x] 与 todo 自相矛盾（r90 实测 07.part62 VOL-FC486）（由 flow 登记；状态: blocked）
- [ ] VOL-AGG-20261001 体量治理[L3 产物] 体量余量聚合（15 项） — 另有 15 项待判断，合计 103704007 B——按字节降序只单列前 6 条，余量逐条见 memory/sessions/volume-snapshots.jsonl（由 flow 登记；状态: todo）
- [ ] VOL-CF954 体量治理[L3 产物] 交付物/心屿SoulIsle-作品提交-20260930.zip — 拆分或归档（禁直删）（由 flow 登记；状态: todo）
- [ ] VOL-8EF30 体量治理[L3 产物] 交付物/提交包/demo_video_out/心屿MindIsle-演示视频.mp4 — 拆分或归档（禁直删）（由 flow 登记；状态: todo）
- [ ] VOL-AGG-20260930 体量治理[L3 产物] 体量余量聚合（10 项） — 另有 10 项待判断，合计 26545458 B——按字节降序只单列前 6 条，余量逐条见 memory/sessions/volume-snapshots.jsonl（由 flow 登记；状态: todo）
- [x] VOL-39DAB 体量治理[L3 产物] 交付物/提交包.zip — 拆分或归档（禁直删）（由 flow 登记；状态: done）
- [x] VOL-A5B8F 体量治理[L3 产物] 交付物/提交包 (2).zip — 拆分或归档（禁直删）（由 flow 登记；状态: done）
- [ ] VOL-0580C 体量治理[L3 产物] 交付物/提交包/心屿MindIsle_参赛方案.pptx — 拆分或归档（禁直删）（由 flow 登记；状态: todo）
- [ ] VOL-EEB5B 体量治理[L3 产物] 交付物/提交包/心屿SoulIsle-应用方案.pdf — 拆分或归档（禁直删）（由 flow 登记；状态: todo）
- [ ] VOL-04585 体量治理[L3 产物] _test/ — 目录内逐类治理：产物拆分/归档，备份残留走 recycle（由 flow 登记；状态: todo）
- [ ] VOL-C85CA 体量治理[L3 产物] 交付物/提交包/demo_video_out/心屿SoulIsle-演示视频.mp4 — 拆分或归档（禁直删）（由 flow 登记；状态: todo）
