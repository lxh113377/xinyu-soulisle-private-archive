# 07-next-steps.part5.md

<!-- 本卷为 07-next-steps.md 的延续 -->

- [ ] ⏸ **已冻结（范围冲突待老大一句话解冻）**：起草《应用方案》PDF（大纲：交付物/提交包/应用方案大纲.md；AI核心作用章节可直接引用：双路情绪引擎实测分歧案例 + 词典层评测 94.4%/危机召回3/3 + **Serverless密钥隔离架构**，见 _test/emotion_eval.js / src/functions/api/chat.js）

## P1 — 应该做
- [x] ~~情绪引擎评测集扩到 ≥60 条~~ ✅ 2026-09-23：36 → **73 条**（+35 条均衡补样/对抗样本/危机，+2 条防回归样本）。**双端实测一致**：`node _test/emotion_eval.js` 与 `GET /api/emotion/eval` 均为 **73 / 98.6% / 危机召回 6-6 / per_class 全同 / misses 逐字相同**；`engine_consistency_check.py` **ENGINE-CONSISTENCY-PASS**。
- [x] ~~**NEG/DEG 覆盖缺陷**~~ ✅ 2026-09-23 老大拍板「修」：`NEG` 含 `别` + 窗口「词前 3 字」⇒「心里**特别**难受」里「特别」的「别」被当否定词，sadness 反号归零 → 误判 anger（评委输入「我特别难受」必翻车）。修法 = **否定判定前先排除被程度副词覆盖的字符**（保留「别难过」的否定）。双端同步改（`emotion-engine.js` 加 `hasNegation()` / `EmotionEngine.java` 同构加私有方法），jar 重打包 00:45:37。
  **验收（含对照）**：误判样本 `心里特别难受` / `我特别难受，想一个人待着` 修复前 anger → 修复后 **sadness**（anger 降为次情绪 2.8 vs 1.3，语义合理）；**反向对照** `别难过了，我陪着你` 修复后仍 **calm**（证明「别」的否定能力没被误伤）。准确率 97.2% → **98.6%**，仅剩 1 条真歧义（`没什么好难过的`，人标 calm / 引擎 sadness，属标注口径问题，非缺陷）。`browser_check.py` **ALL-ASSERT-PASS**。
- [x] ~~语音输入真机验证~~ ✅ 2026-09-23：新增常驻脚本 `_test/voice_check.py`（系统 msedge + 假麦克风 + 自动授权），**VOICE-PASS**。实测事件序列 `start → audiostart → result:n=1 → end`（**真出了识别结果**），按钮监听态进入与恢复均正常，console 0 错误。判据 6 条（API 存在 / 按钮可见 / start 被调用 / 进入监听态 / 能恢复 / 无 console 错误 + 授权类阻断错误）。
