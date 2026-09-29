# 07 分卷 · 卷86 — r79（2026-09-29 · 把修好的尺接上受理面）

> 报告全文 `交付物/对标分析报告-2026-09-29-r79.md`；入场基线 `fbf86dd`。

## 已完成（成功面）

- [x] ✅ **R78-04 闭合（T8 在受理面被强制）**：`ci.yml` 的 java-build 作业在 `mvn verify` 之后新增一步
      `python _test/java_test_guard.py`。CI 回执（run 36519011939，job 109247586676 **success**）日志原文：
      `T8 覆盖率读数 + 具名缺口 OK LINE=97.75% BRANCH=96.28% METHOD=96.43%｜下限 90%/90%/90%｜带缺口的类：LlmProxy(分支漏3/36·行漏4)…`
      ＋ `JAVA-TEST-GUARD-PASS（… 覆盖率门 在位｜LINE 0.90 / BRANCH 0.90｜链上 是）`。
      插入用"计数 +1"与"剥掉新增块必须逐字等于原文"两条断言把门（22→23 步）。
      **反面写法先排掉**：没有用 `continue-on-error`、没有改成"跳过"——那会把"没测"伪装成"不需要测"。
- [x] ✅ **R78-01 方法级名单**：`top_gaps(level="method")` 现读真面 4 个未触达方法
      （`SafetyGuard$Named.<init>`、`SoulIsleApplication.<init>`、`SoulIsleApplication.main`、`ChatMessage.getSessionId`）
      与漏指令 top（`LlmProxy.openStream 8`、`LlmProxy.call 6`、`LlmProxy.buildPayload 3`…）。
      口径写进注释：**jacoco 的 `<method>` 只有 INSTRUCTION/LINE/COMPLEXITY/METHOD，不含 BRANCH** ⇒ 方法级按
      "未触达 + 漏指令数"排，不假造方法级分支数；`<method>` 缺失时显式标注并回落类级（空名单会被读成"没有缺口"）。
- [x] ✅ **R78-03 余半**：`fault_injection_check.py` 复用同一分档口径（`upstream_state()` / `recover_disposition()` 两个纯函数，
      **故意不 import** safety_guard 的同名件——它在 import 期读 `sys.argv`，跨模块 import 会串开关）。
      F5「恢复方向」在上游 502／欠费／无密钥时记**未验**；上游可达却仍不翻徽章 ⇒ 继续判红（真缺陷不许被环境档洗白）。
      PASS 行改为"如实降级"并带 `（F5 记未验：…）` 尾巴，不再写"6 类全部"。
- [x] ✅ 自证：`java_test_guard --selftest` **38/38**（+5 方法级腿）；`fault_injection --selftest` **26/26**（+13 条：
      探活五形、处置六形、反向自证）；真面 `FAULT-PASS`（hang 兜底 21.3s ≤ 25s）与 `JAVA-TEST-GUARD-PASS` 双双复跑通过。

## 失败面 / 不对称（禁只写"已交付"）

- **F5 的未验分支在真面未被触发**：收口时上游可达（探活 `ok`），所以现场只验到"pass 路径没被改坏"，
  未验路径**只有夹具两侧**。不冒充现场对照；真要现场证据需等下一次上游抖动，已并入 R76-03（去单点/环境档）观察。
- **本卷写作时 `README.md` / `docs/quality-gates.md` / `_test/run_all_suites.py` 仍是 `M`**：他方 r70 在途连续三轮未出库
  ⇒ R76-01（抄来的读数）与"把 java_test_guard 也从电池挪走"这类要做在 runner 里的事，全部排队等待。

## 挂账（承接 + 新增）

- [ ] 🔴 **R79-01 用方法级名单补测试**：把 `SafetyGuard$Named.<init>`、`ChatMessage.getSessionId` 这类"可补"的先补掉；
      `SoulIsleApplication.main`/`.init` 属启动入口，按 r78 原则**不为凑数写反射**，在报告里说明保留理由。
- [ ] 🔴 **R76-03 / R77-01 合并观察**：电池仍由人工起的 `jar@8123` 与上游可达性共同决定；等 r70 普查件出库后一并做分桶 + 探活。
- [ ] 🔴 **R76-01**、**R76-04（`wflow.toml` 噪声）**、**R78-02（字段级 `None -> 值` 仍落实质档）**：原文在 `part83`/`part84`/`part85`。
- [ ] 待老大：R1 发布裁决、iCAN 报名 PII（**截止 2026-09-30**）。
