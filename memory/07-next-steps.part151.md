# 07-next-steps 分卷 — r129 心理学知识库轮收尾与第 6 轮队列（2026-10-12）

## 已落地（回执见 `memory/2026-10-12.md` r129 段）
提交面缺件补齐 `373f608`｜构建器 selftest + 源⇄件判据入电池/CI `4b274d5` `e0e01d1`｜
新判据 `psych_kb_integrity_check`（三面 + 17 腿 + `--backlog`）`f29745a` `b5bd7c8`｜
新判据 `kb_wiring_check`（注入链路 K1-K7 真面全过）+ 篇章 17/19/20 共 18 条 `95e552c` `de45ac9`。

## 未落地（不带记忆也能照此执行）
1. **篇章 18 失恋与被拒（RJ 001~006）**：产品情绪枚举里 love/sadness 的空白面；
   与 PSY-AT-*（依恋孤独）、PSY-GR-*（哀伤）划分工。复算 `grep -rc "PSY-RJ" 交付物/心理学知识库/`。
2. **README 升 v1.4 与构建器版本必须同批做**（别半程 bump）：README 版本行 + §4 四域码（NG/RJ/HK/PR）
   + §5 篇章 17-20 四行；`_test/psych_kb_build.py` 的 `KB_VERSION="v1.4"`、`BUILT_TAG` 改本轮号；
   随后重建 → 同步 deploy 副本 → `--check` / integrity / size_budget（实测 +5% 重登记；
   TOTAL 只在实测总量真被顶起时才抬，r129 已连调三批单项而 TOTAL 未动）。
3. **KB 新内容未上线**（deploy 副本已一致，公网未部署）。本轮故意没部署：语音轮在
   `src/js/app.js`、`chat-agent.js`、`voice-call.js` 有未入库改动，此刻部署会把别人半成品推上线。
   上线前置：那三面入库 → `deploy_sync_check` 三类归零 → 整跑电池 `run_all_suites.py --exclude-llm` 全绿 →
   `live_sync_check` + `public_check`。
4. **src 侧「引用可视化」未做**（目标里证据溯源的用户可见面）：现在只有提示词要求〔依据:编号·级〕，
   `kb_wiring_check` K6 仅保证约束词在位，不校验模型真标了什么。要做回复后处理：
   回复里出现的 〔依据:PSY-XX-NNN·级〕 与本轮实际注入编号集合比对，命中才渲染依据标记，
   未命中标「未查证」（不删文本）。落点 `src/js/chat-agent.js`（`kbBlockFor` 需把 used ids 随回复带出）
   + 一条把 K2 反用到回复面的新判据。前提：等 chat-agent.js 的并行改动入库。
5. **同族另一件（非 KB 面，登记不代处置）**：`_test/wit_quotes_build.py` 与 psych_kb_build 同族，
   同样无 `--selftest`、不在电池。做法照抄 `4b274d5`（先补 selftest 再接线，工作树面与提交面各测一次）。
6. **第 6 轮选题队列（机器给，不翻卡片）**：`python _test/psych_kb_integrity_check.py --backlog`
   现读 116 卡 / 未闭合 332 项；最重面 06 多模态 38、14 哀伤 26、20 拖延 25、10 对话支持 24、07 情绪调节 24。
   README §6 第①步「优先补 E 级缺口」自 r123 起失去输入（E=0），待验证点即其接替者。
