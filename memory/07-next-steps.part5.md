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
- [x] ~~情绪引擎评测集扩到 ≥60 条~~ ✅ 2026-09-23：36 → **73 条**（+35 条均衡补样/对抗样本/危机，+2 条防回归样本）。**双端实测一致**：`node _test/emotion_eval.js` 与 `GET /api/emotion/eval` 均为 **73 / 98.6% / 危机召回 6-6 / per_class 全同 / misses 逐字相同**；`engine_consistency_check.py` **ENGINE-CONSISTENCY-PASS**。
- [x] ~~**NEG/DEG 覆盖缺陷**~~ ✅ 2026-09-23 老大拍板「修」：`NEG` 含 `别` + 窗口「词前 3 字」⇒「心里**特别**难受」里「特别」的「别」被当否定词，sadness 反号归零 → 误判 anger（评委输入「我特别难受」必翻车）。修法 = **否定判定前先排除被程度副词覆盖的字符**（保留「别难过」的否定）。双端同步改（`emotion-engine.js` 加 `hasNegation()` / `EmotionEngine.java` 同构加私有方法），jar 重打包 00:45:37。
  **验收（含对照）**：误判样本 `心里特别难受` / `我特别难受，想一个人待着` 修复前 anger → 修复后 **sadness**（anger 降为次情绪 2.8 vs 1.3，语义合理）；**反向对照** `别难过了，我陪着你` 修复后仍 **calm**（证明「别」的否定能力没被误伤）。准确率 97.2% → **98.6%**，仅剩 1 条真歧义（`没什么好难过的`，人标 calm / 引擎 sadness，属标注口径问题，非缺陷）。`browser_check.py` **ALL-ASSERT-PASS**。
- [x] ~~语音输入真机验证~~ ✅ 2026-09-23：新增常驻脚本 `_test/voice_check.py`（系统 msedge + 假麦克风 + 自动授权），**VOICE-PASS**。实测事件序列 `start → audiostart → result:n=1 → end`（**真出了识别结果**），按钮监听态进入与恢复均正常，console 0 错误。判据 6 条（API 存在 / 按钮可见 / start 被调用 / 进入监听态 / 能恢复 / 无 console 错误 + 授权类阻断错误）。
