# 07 分卷 · 卷85 — r78（2026-09-29 · 两把尺各修一半）

> 报告全文 `交付物/对标分析报告-2026-09-29-r78.md`；本轮入场基线 `489a4d7`，收口提交见 `git log` 的 r78 段。

## 已完成（成功面）

- [x] ✅ **撤掉一条假缺口**：质量门同址尺对执行型三类第一句是 `if not files: out=False`，`files` 只认
      **标准工具文件名**（`.gitleaks.toml`/`eslint.config.*`/`mypy.ini`）⇒ 本仓 CI 每步真跑
      `python _test/tracked_secret_scan.py` 却被判 `self=❌无`，r77 总览表照抄了这条**我方并不存在的缺口**。
      更糟：r75 把该天花板固化成断言（"没有标准配置却判出 secret_scan_gate ⇒ FAIL"）⇒ 错误口径锁进回归网，谁修对谁红。
      修＝新增 `qg_invoked_line()` 第二路由（只认执行行；步骤名/注释不升格），两侧同一函数保持同法；
      真面读数 `secret_scan_gate self=✅有 ∧ 证据点名那一行`。
- [x] ✅ **覆盖率读数接进阻断链 + 具名缺口清单（r77 §3 建议 7 落地）**：`java_test_guard` 新增 T8——
      LINE/BRANCH/METHOD 三路现算下限各 0.90（实测 97.75% / 96.28% / **96.43%**），
      并打印"还带缺口的类"：`LlmProxy(分支漏3/36·行漏4)`、`MemoryController(3/30·行漏2)`、`ChatController(2/30)`。
      两条口径同时钉死：分母只取 `<report>` 直属 counter（`TRAP_JACOCO` 夹具锁死 r77"逐类求和"假 drift）；
      取不到或**产物比源码旧** ⇒ 整条 `rc=2 UNVERIFIED`（旧行为压根不看读数就印 PASS）。
- [x] ✅ 自证：`java_test_guard --selftest` **33/33**（本轮 +11 腿：T8 正反例/盲区/陈旧/具名/口径锁/变异/两条硬化边界）；
      `benchmark_metrics --selftest` PASS（+4 腿：自写门禁正例、描述性文字反例、未取全 None、摘路由即翻判）。

## 失败面（同条登记）

- **拒绝式校验把真产物判成非法（已知坑第二次实发）**：T8 第一版硬化写成"拒 `<!DOCTYPE` + 拒 `<!ENTITY`"，
  而真件首行实测就是 `<?xml …?><!DOCTYPE report PUBLIC "-//JACOCO//DTD Report 1.1//EN" "report.dtd">`
  ⇒ 守卫把**真读数**判成未验、`java_test_guard` 整条 `rc=2`。修＝只拒 `<!ENTITY`，
  并把"真件形状必须读得动"升成夹具正例腿（边界①）＋"含 ENTITY 必须抛"反例（边界②）。
  对照：修前 `REAL-RC=2` 值串印"含 DTD/实体声明 ⇒ 拒解析"；修后 `REAL-RC=0` 印三路读数与缺口名单。
  对应规则：[[gate-shape-must-admit-the-honest-value]]（已知、规则在案未执行）。
- **一次期望值算错**：`Small` 夹具 BRANCH missed=4 covered=40，我按"总数 40"写死期望 ⇒ 自证当场抓出
  （`want …漏4/40… got …漏4/44…`）。是**我的期望错**不是代码错，改期望前先手算了分母构成。
- **`record_lessons_usage.py` 双根深查不存在**（`find D:/global_skills D:/global_memory -name "record_lessons_usage*"` 零命中）
  ⇒ A-get-memory Step 1.5「注入改善度自评」无执行体，本轮只能口头记 ⇒ 属**技能条文引用不存在的工具**（自觉型欠账，
  已登记 r79：要么补脚本，要么把 Step 1.5 改成可执行的替代留痕）。

## 挂账（承接 + 新增）

- [ ] 🔴 **R78-01 方法级名单**（r79 第一刀）：T8 现在点到类，4 个未触达**方法**仍无名 ⇒ `top_gaps(level="method")`。
- [ ] 🔴 **R78-02 字段级 None→值 仍落实质档**：与 r77 §4.3 同一条余债（`ci_workflows: None -> 0` 这类）。
- [ ] 🔴 R76-03 去单点（连续两轮阻塞在他方 r70 在途件）、R76-01 两面抄来的数字、R77-01 自觉型未机器化 —— 原文在 `part82`/`part83`/`part84`。
- [ ] 待老大：R1 发布裁决（`feats=12/5 unreleased=111`）、iCAN 报名 PII（**截止 2026-09-30**）。
