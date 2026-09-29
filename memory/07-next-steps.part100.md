## ③ 覆盖率换尺：从「还差几支」到「逐支说明为什么差」

jacoco 逐行 `mb>0` 读数（本轮 11 支 → 修后 8 支）与归类：
- **补测 3 支真分支** ⇒ BRANCH 285→**288 / 296 = 97.30%**（用例 83→88）：
  `MemoryController:48`（`intensity` 键**不存在** 与「给了但不是数字」是两条不同短路）、
  `MemoryController:93`（`ChatMessage.createdAt` 为空 ⇒ 字段在、值为 null，不伪造当前时间）、
  `EmotionLexicon:129`（`e <= s` 为真）。
- **8 支结构不可达，每支给了机器载体**（散文不变量升为用例，红了会被看见）：
  `mapper.readTree("")` 实测返回 **`MissingNode` 而非 null**（对照探针跑的是项目实际依赖 jackson 2.15.4）
  ⇒ `MemoryController:118` / `ChatController:55` / `EmotionController:54` 的 null 侧是死代码，
  本轮写了「`readTree` 永不返回 java null」的断言同时钉住这三处；
  `BodyHandlers.ofString` 对零字节响应给 `""` ⇒ `LlmProxy:103` 的 `body == null` 死；
  `lastUserText` 对非数组先给空串 ⇒ `harden` 在上一道门就 return ⇒ `SafetyGuard:131` 的 `isArray` 支死；
  `LlmProxy:94/125`（`payload == null`）沿用 r82 归因；`ChatController:112` false 侧沿用 r77（`headerValue()` 恒非 null）。
- **两处自纠由新用例当场测出**（不是事后追认）：
  ① 我假设「把 `}` 写在 `{` 前面」能触发定位守卫 ⇒ 用例回「实际静默通过」：`lastIndexOf('}')` 取**全文最后一个**，
  而旧 `unbalanced.js` 夹具 `{"lex":{}` 末尾自带 `}` ⇒ **它一直是被 Jackson 解析异常抓住的，守卫那一支从没被走过**。
  这是「看起来在测这条」的假覆盖。
  ② 桩脚本是**队列**：只 `script` 一条空体时，第二次请求掉进桩的默认响应，断言拿到「兜底」而非 `upstream-nonjson`。
- LINE 97.75 / METHOD 96.43 **未动** ⇒ 不虚报「本轮把覆盖率全面推高」。

## ④ 本轮三次踩同一族（已进 `memory/AGENTS.md` 排障表）

1. **退出码在管道里死掉**（本仓第三次）：删除循环写 `out=$(tcb … 2>&1 | tail -1); rc=$?` ⇒ `rc` 是 `tail` 的，
   25 次失败全被吞，`git`/`tcb hosting list` 复算才发现托管面还是 68 件。
2. **Python 调 npm shim**：`subprocess.run(["tcb", …])` 报 `FileNotFoundError`（WinError 2）——
   `tcb` 是 `D:\npm-global\tcb.cmd`，Windows `CreateProcess` 不走 PATHEXT ⇒ 必须给 `.cmd` 全路径。
3. **MSYS 改写斜杠开头的参数**：`tcb hosting deploy deploy/xinyu /xinyu` 被改写成 `C:/Program Files/Git/xinyu`
   ⇒ 25 件误上传到错误 cloudPath。修法 `MSYS_NO_PATHCONV=1`。误上传已逐件删除并双向对账
   （原始 43 件面 → 现在 43 件面，`新增 0 / 缺失 0`，他人件一根没动）。

- [x] ✅ **R82-01 闭环（r83）**：「入库件在位」腿接成提交面（`_test/hooks/pre-commit` + `hook_wiring_check`
      12 腿含端到端删件真被拦，套件 103→**105**）。**肇事者仍未找到**。`part92` §①

- [x] ✅ **R1 切版 v1.7.0（r83；当轮命令构成授权）**：`feats=17/5` ⇒ `[Unreleased]` 640 行逐字节进 `[1.7.0]`，
      pom/ROADMAP/tag 三源由 G12 对账；未放宽任何阈值。`part92` §⑤

- [x] ✅ **R35-01 改判闭环（r83）**：fake-media 两参实测早在 `_test/voice_check.py:104-105`，降级面已收到
      「CI ∧ 仅 audio-capture」⇒ 这行挂了两次开场都没重跑的 P0 是**过期账**。`part92` §③

- [x] ✅ **覆盖率换尺（r83）**：BRANCH **97.30%**（88 用例），余 8 支逐支归类不可达**并各给断言**。`part92` §③§⑦

- [x] ✅ 历史闭环索引：**R76-01**（`part79`）｜**R76-03 / R81-01**（`part91`）｜**R78-04 / r78 两把尺**（`part85`）
