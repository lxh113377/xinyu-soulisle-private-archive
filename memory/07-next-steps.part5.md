# 07-next-steps.part5.md

<!-- 本卷为 07-next-steps.md 的延续 -->

- [ ] ⏸ **已冻结（范围冲突待老大一句话解冻）**：起草《应用方案》PDF（大纲：交付物/提交包/应用方案大纲.md；AI核心作用章节可直接引用：双路情绪引擎实测分歧案例 + 词典层评测 94.4%/危机召回3/3 + **Serverless密钥隔离架构**，见 _test/emotion_eval.js / src/functions/api/chat.js）

## P1 — 应该做
- [x] WF-r97-voice退出态 voice 退出态真缺陷修复 + v1.8.1 切版（r94/r95/r96 三轮挂账项）（由 flow 登记；状态: done）
- [ ] VOL-CC6BC 体量治理[L5 自动化链] _trash/ 回收区超龄 — 人工核后清空该面 `_trash`（`handoff.py recycle --list <锚点>` 逐项看）；治理链不自作清历史 —— 里面混着人工裁决过的件（由 flow 登记；状态: todo）
- [x] WF-r96-对标轮 r96 八维对标 + 四项改造（issue响应尺/并发口径封口/龄期尺+探针接线/引擎面归因+交付卫生）（由 flow 登记；状态: done）
- [x] WF-r95-契约自身结构门 契约会被后人改坏（同名/空清单/成本虚报/列了没人跑）⇒ 需常驻门（由 flow 登记；状态: done）
- [x] WF-r95-对标轮 r95 八维对标 + 五项改进（CI 契约入库/契约结构门/30 天提交率尺/台账 SNAP 刷新/电池 120）（由 flow 登记；状态: done）
- [x] WF-r94-收口 r94 收口：五轮电池取最终绿 + 门禁面复核 + 提交推送 + CI 回执（由 flow 登记；状态: done）
- [x] WF-r93-对标轮 r93 八维对标 + 四项改进（loc 门 / rollup 两新增维度 / corpus 归档 / peers 全量重采落工作区）（由 flow 登记；状态: done）
- [x] WF-r73-接入CI契约 陪聊当前未接入 CI 全绿契约（.ci/contract.json 缺失），而 ciwatch 实扫到 1 份 workflow / run 执行面 89 行 ⇒ 未接入 ≠ 没有 CI，这 89 行里没有一条是被契约点名的 blocking 判据。一致接入四步（本引擎 wflow.adapters.sevenstep 对位）：① 生成 .ci/contract.json（把 mvn verify / 关键门禁逐条列 blocking）；② 在 .github/workflows/ci.yml 里为每条加 run step 并 --sweep 复扫到 matched==declared；③ pre-push 接线 greencheck；④ 保留本项目特性（Java/Maven 档位与 8123 回归口不并入引擎）。前提可复算命令：cd 本仓 && python D:/global_skills/A-project-handoff/scripts/handoff.py flow . --status（由 flow 登记；状态: todo）
- [ ] VOL-AGG-20260928 体量治理[L1 记忆卷] 体量余量聚合（6 项） — 另有 6 项待判断，合计 139169 B——按字节降序只单列前 6 条，余量逐条见 memory/sessions/volume-snapshots.jsonl（由 flow 登记；状态: todo）

- 本卷尾部三个条目（2026-09-23 已完成项：评测集扩条 / NEG·DEG 覆盖缺陷（含其验收续行）/ 语音输入真机验证；共四行）已迁 `07-next-steps.part122.md`
  —— 动因：`flow --sync` 把 P1 镜像写回本卷后达 4,609B，越过 R199.2 单卷 4KB 硬限；savepoint 判 `single_block` 拒自动拆 ⇒ 人工拆卷，原句一字未改。
