## 改动概述

<!-- 一件事一个 PR。type(范围): 中文描述 -->

## 红线自查（逐项打勾）

- [ ] 密钥零落前端、零入库、零进镜像（`python _test/public_check.py` → `KEY_LEAK: False`）
- [ ] 若改了 `src/`：已同步 `deploy/xinyu/` 且 `python _test/deploy_sync_check.py` → `DEPLOY-SYNC-PASS`
- [ ] 若改了任一端情绪词表：两端同步且 `python _test/engine_consistency_check.py` 通过
- [ ] 若改了 `/api/chat` 契约：`_test/j2_chat_contract.py` → `J2-CONTRACT-PASS`
- [ ] `node _test/emotion_eval.js` 指标不回退（accuracy ≥ 95%、危机召回全命中）

## 验证证据

<!-- 粘贴关键判据输出行（DEPLOY-SYNC-PASS / ALL-ASSERT-PASS / 评测 JSON 等），只写结论行不算过 -->

## 影响面与回滚

<!-- 波及哪些文件/页面/接口；回滚方式（revert 本 PR 即可 / 需要额外动作） -->
