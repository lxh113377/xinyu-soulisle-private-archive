# 07 分卷 · 卷82 — r77（2026-09-29 · 换尺：分支覆盖 + 门挂第二路）— 已完成与挂账；失败面见卷83

> 取号序卷；正文为 r77 一手读数与挂账，报告全文 `交付物/对标分析报告-2026-09-29-r77.md`。

## 已完成（本轮内收）

- [x] ✅ **r77 分支覆盖内收（r76 §4 第 3 条）**：只量 LINE 的门会放行"三元表达式从没走过另一半"——
      r76 收口时 LINE 91.93% 而 **BRANCH 只有 83.11%**。补 `LlmProxyTest`(9，上游换成 JDK 内置
      `com.sun.net.httpserver.HttpServer`，127.0.0.1 + 端口 0，零新依赖/零公网/零密钥)、
      `EmotionLexicon` 包内 seam（`resolvePath(String,String)`/`readLexicon`/`toStringList`；
      无参入口仍传 `System.getenv` ⇒ 运行时取值路径一字未改，而 fat jar 与 Docker 各自那条回落腿第一次有构建期用例）、
      五个控制器的坏形态补形、否定窗两侧（`太不开心` 0.65 sadness vs `不太开心` 0.25 calm）。
      现测 **11 类 / 82 @Test**；LINE **615/669=91.93% → 651/666=97.75%**；BRANCH **246/296=83.11% → 285/296=96.28%**。
      ⚠️ **分母 669→666 = 删掉 `ChatController` 里实测零调用点的 2 参 `bytes()` 重载**（5 个调用点全走 4 参）
      ⇒ 这是分母缩水，**不得写成覆盖提升**，两侧数字都在这行。
- [x] ✅ **覆盖率门挂上第二路**：pom LINE `0.85 → 0.90`（余量 7.75 点）+ **新挂 BRANCH 0.90**（余量 6.28 点）。
      验牙两形：BRANCH 阈值临时 0.99 ⇒ `rc=1` 且红因点名 `branches covered ratio is 0.96, but expected minimum is 0.99`；
      按字节还原（sha256 前后同为 `d675b7e463c24594…`）⇒ `rc=0`。剩 **11 支未覆盖分支**逐条归类为
      不可达/短路边（`readTree` 永不返回 null 3、`payload == null` 2、`ofString` 永不返回 null 1、
      `harden()` 被上游守卫挡住 1、`||`/`&&` 短路 2、删重载后 `safety != null` false 侧 1、三元组合 1）
      ⇒ **不为凑数写反射或喂假输入**。
- [x] ✅ **`_test/java_test_guard.py` 同源升级（T6 从"随便一个 minimum"改为按 counter 配对解析）**：
      旧写法读第一个 `<minimum>` 就印"LINE 阈值 0.90"，把 BRANCH 那一路删掉照样 PASS ⇒ 门是半个门。
      下限 3 件/24 例 → **8 件/70 例**（现测 11/82，余量 3 件/12 例）；新增反例⑫（LINE-only pom）+
      点名E（共用夹具配合规 pom/CI 必须全绿，否则其余反例的红无法归因）+ 点名F/G（红因必须点名 BRANCH、
      合规回执必须同时带两路阈值），自证 **22/22**。头注里写死的"四件"随维度增长早已失真 ⇒ 改为"条数以本列表为准"。

## 挂账（承接）

- [ ] 🔴 **R76-01 仍未闭**：`README.md` 与 `docs/quality-gates.md` 本轮 02:53 复测仍 `M`（他方 r70 在途：电池 99→101 套件），
      `前提=git status --short README.md docs/quality-gates.md` 为空再改。
- [ ] 🔴 **R76-03 升优先级**：见上「第二形态」。
- [ ] **R77-02 下一刀候选**：`SoulIsleApplication` 是最后一个 0% 类（3 行 main），
      以及 METHOD 覆盖 **108/112=96.43%（4 个方法未触达）**、INSTRUCTION 46 条未覆盖 ——
      本轮按"分母不许自造"原则未逐一定位到方法名，下一轮先出名单再决定补还是删。
- [ ] 待老大：发布裁决（R1，收口时 feats 12/5）、iCAN 报名 PII（**截止 2026-09-30**）。
