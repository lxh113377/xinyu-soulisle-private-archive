# 07-next-steps 卷43 — **r130 收口（八维对标四项改造）**（2026-10-12）

> 全文：`交付物/对标分析报告-2026-10-12-r130.md`。提交 `887e6e9`。
> **轮次号**：入场时 HEAD 已是 `94e623b feat(r129 FE-1)`（并行会话的前端专项）⇒ **r129 已被占用，本轮取 r130**。
> 入场纪律：**开工前先看 HEAD 提交信息里的轮次号**，别沿用上一份报告的号（否则产出两条同名轮次）。

## 一、本轮定位（为什么是这四项）

本仓 `repo_config_check` 入场 **G1–G20 全绿**（v1.8.3 已切版），**没有存量红可借力** ⇒
四项改造的依据全部来自八维对标差距，且刻意各占一个维度：

| 项 | 闭合哪个维度 | 交付 | 回执 |
|---|---|---|---|
| S1 性能可复算尺 | 第 4 维（历轮写「不可测」） | `_test/perf_api_check.py` | selftest 18/18；PERF-API-PASS（health p95 17.49 / emotion 15.69 / 并发 8×32 全成功 rps 1526） |
| S2 成本总量闸 | 第 1 维（r128 只堵突发，总量敞口仍在） | `UsageLedger` + `QuotaFilter` + `/api/usage` | 新增 20 例单测全绿 |
| S3 记忆可携带 | 第 1+5 维（数据权只做了「能删」） | `MemoryPortService` + `MemoryPortController` | 新增 15 例；契约 12→15 路径，运行态 15/15、**C6b 零豁免** |
| S4 文档厚度与防腐烂 | 第 7 维（4 ⇄ lobe 51 篇） | `tutorial-05/06` + `docs_tutorial_check.py` | T1–T4 全绿 + 4 类篡改被抓 + 2 条防误报反向腿 |

补挂：棘轮 `server_hardening_check` **H1–H4 → H1–H6**（六条变异腿逐条打翻、还原后零红）。
接线：电池 **185 → 188**；`suite_count_sync --apply`；`REPO-CONFIG-PASS 18/18`。
测试：JUnit **134 → 169 例**；LINE **95.23%** / BRANCH **90.58%**（门 0.90 双路未红）。
核心能力：**CORE-CAP-BASELINE-PASS**（N1 105 条、回归 0/104；N2 31/31）—— 本轮未碰 `emotion-engine.js` /
`face-engine.js` / 评测集（并行会话在途面）。

## 二、r131 入口（按值排序）

1. **换新 fat jar 后重取性能基线**：当前两份台账一份打 8123（他人旧产物）、一份打 8130（本轮新代码实例）。
   `perf_api_check` 的**指纹不含版本号**（已知缺陷）⇒ 换产物必须重跑 `--calibrate` 并更新 `THRESHOLDS`。
2. **待 8123 换新后把 `api_contract_check` 的 C4 从 `--base 8130` 切回默认**：默认面下 `/api/memory/search` 仍超时（他人产物面）。
3. **判据层体量治理**（7.27:1）：本轮仍**未动**（会碰并行会话在途判据），维持 P-2。
4. `mvn test` 的 2 红（`EmotionControllerTest` 硬编码 85/100%）持续属并行会话在途（评测集 105 条），**非我方**，不修。
5. 向量语义记忆 / 渠道适配 / 插件协议 / i18n —— **需老大拍板**（命中架构决策 #1 重评条件）。

## 四、r131 续做（2026-10-13，接上文「不停工」直接续做，均已提交）

**做了什么**（三条，全部对着自己登记的缺陷/待办动手，不新增面）：

1. **产物身份 `build`**（对应上文 r131 入口第 1 条的**根因**，而不只是现象）：
   `/api/health` 加 `build` = `jar:<名>:<摘要12>:<字节数>` / `classes:<目录>:<mtime>`。
   - 实测取证：**8123（他人进程）的 health 无此字段** ⇒ 实证它跑的是 r131 之前的产物
     （此前只能靠「`/api/memory/search` 超时」去猜）；fat jar 实例回
     `jar:soulisle-server.jar:071a50bf59a4:28486290`。
   - 踩坑：fat jar 下 `getProtectionDomain().getCodeSource()` 是**嵌套 URL**，
     实测退化成 `classes:null:<mtime>`，**恰好丢掉 jar 名与字节数**（那正是区分瘦/fat 的字段）
     ⇒ 改 `ApplicationHome` + `java.class.path` 回退，并补 `resolveSource()` 的 seam 与用例。
   - 覆盖率副作用：`buildIdentity` 整段塞函数里时 BRANCH 掉到 **90.07%**（门 0.90，余量 0.07 点）
     ⇒ 拆 seam 后回到 **90.57%**。
2. **判据间共享服务端状态的自愈**（两个方向都踩到了）：
   - 契约（15 条连打）吃令牌桶 ⇒ 基准 `emotion` 15 次里 **9 次 429**；
   - 反过来先跑基准（62 次）⇒ 契约 `/api/usage`、delete 各吃 429 判红。
   - 修法同构：撞 429 ⇒ 等 **22s**（= burst 20 ÷ 1 token/s，推导写进常量）重打一次；
     收尾打印「限流重试 N 条」，不许静默。`perf_api_check --no-settle` 可关（用于复现）。
3. **契约判据先报产物身份**：C4 开跑前读 `build`，缺失 ⇒ 点名「以下运行态结果不可当新代码证据」
   （**不判红**——换新产物不由判据控制，判红只会把环境问题刷成常驻红项）；严格模式 `--require-build`
   ⇒ 直接 rc=2 未验，而不是给出一堆 404/405 的红。
4. **更正注（诚实记录）**：前两轮把「95,429 B 瘦 jar 冒充 fat jar」写成「无人发现」是**不准确**的 ——
   `jar_shape_check.py` + `server_preflight.py` 的 **P0（r70 立）**一直盯着字节数与 MANIFEST，
   本轮实测它一句话点出真因（`thin jar｜bytes=95429 libs=0`）。真因是**我们撞了 `mvn package`
   却没先跑 preflight**，属「有守卫而我没用」，不是「无守卫」。
   另：`_test/build_jar.py`（r38）本就是「停服务→构建→验货」整套，但其四档归属协议
   （ours/unknown/same-artifact/foreign，`--takeover` 默认关）**不会**停他人进程
   ⇒ 8123 被他人持有时它同样构不成解法，旁路构建仍是必要补位。
   **改写后的教训**：动手前先问「这件事仓里有没有现成的尺」。
5. **`server_preflight.py` 加了两条归因腿**（r131）：P0 FAIL 时也探一次活并报运行实例 `build`，
   把「盘上产物不合格」与「运行实例旧」分开归因（本轮实测两者同时成立，此前必被混成一件事）。

**绕开 jar 锁的旁路构建（可复用）**：`mvn package` 撞在他人持有的 `soulisle-server.jar` 上
（`repackage` 无法 rename 成 `.jar.original`），且 `-Djar.finalName` **无效**。
解法 = 在工作区内复制 `pom.xml` + `src/` 到旁路目录构建（相对路径 `../src` 仍成立），
拿到 **28,486,290 B 真 fat jar**，用完即删（不留 28MB 残渣）。
fat jar 上正式读数：health p95 **16.86ms**、emotion p95 **24.52ms**、并发 8×32 rps **1161**，PERF-API-PASS。

**提交**：`5595278`（build 身份 + 基准自愈）、`f49afa0`（契约报产物身份）、r131 收口一笔。
**JUnit 171 → 172 例**；契约 19/19；教程判据 4/4；性能 selftest 19/19；核心能力 PASS。

## 五、本轮新发现的两条（不在上表内，登记待办）

1. **部署同步当前红 1 项，归属并行会话**：`deploy_sync_check` → `DIFF css/voice-call.css`。
   实测取证：`src/css/voice-call.css` 是 **M（在途）**，工作树 sha `6e8b063a…`，而
   `deploy/xinyu/css/voice-call.css` 与 **HEAD 版相同**（`9a449d64…`）⇒
   是并行会话改了 src 尚未同步 deploy，**不是本轮改动**（本轮未碰任何 css）。
   ⇒ **演示/提交前必须先绿**（用户 2026-09-23 铁律），届时需对方补齐同步；不要代为同步
   （半成品传播到公网比不同步更糟）。
2. **成本闸只覆盖了一半暴露面（新 P1）**：r130 的 S2 按日闸在 **Java 服务端**；而公网 v1 线
   （`pages.dev` → `deploy/functions/api/chat.js`）是**无状态 Pages Function**，既没有令牌桶
   （`ApiGuardFilter` 在 Java 侧）也没有按日累计（要 KV/D1 才能做）。公网面当前只有
   「密钥不落前端」这一层。选项：① Cloudflare KV 计数（要建 namespace + 改 wrangler.toml，
   属对外发布动作，需老大点头）；② 接受平台层限制并写进 `data-and-privacy.md` 的边界声明；
   ③ 公网 /api/chat 加**无状态**的次数上限（按 CF 提供的 `cf-connecting-ip` + 单实例内存，
   重启即失效，只能挡瞬时打爆）。**本轮只登记不动手**。

## 三、一手教训（本轮真踩，全文见报告 §8）

1. **单测全绿 ≠ 能启动**：`MemoryPortService` 漏 `@Service`、`QuotaFilter` 双构造器漏 `@Autowired` ⇒
   `spring-boot:run` 直接失败，而 169 个用例一个没红（JUnit 是手工装配，容器走另一条链）。**新增控制器/服务必须真起一次。**
2. **`spring-boot:run` 的 cwd 不是项目根** ⇒ `./src/`、`./_test/emotion-eval-dataset.json` 全失效（lexicon 500 / eval 404）。
   正解：显式给 `XINYU_WEB_ROOT` / `XINYU_EVAL_DATASET` / `XINYU_LEXICON` 绝对路径。
3. **他人进程持有的 jar 会让 `package` 失败并留下瘦 jar**（93,975 B 冒充 20 MB，本仓第二次）。
   绕行 = `spring-boot:run` 跑 `target/classes` + **独立端口 8130** + **独立内存库**（H2 文件库不支持多进程写）。全程未动 8123。
4. **基准会被自家限流闸打回**：`--rounds 30` > `burst 20` ⇒ 10 次 429。429 须单独计 `rate_limited`，
   成功样本 <60% 判 **rc=2 未验**（不拿残缺样本下结论）；默认 rounds 已改为 15。
5. **变异锚点出现多处时单次替换＝空操作**（r128 同族，但这次正解是**全量替换**，因为语义是「任一处存活＝没删干净」）。
6. **判据自己崩会带走前面所有 PASS**：`api_contract_check` 的 C4 超时未捕获 ⇒ 抛栈，11 条 PASS 与"哪条挂了"一起消失。
   超时必须落成读数（同族于 r105 BLIND-RED）。
7. **C6b 零豁免不许「先豁免以后再验」**：想给 3 条新接口写 `x-live-skip` 会判红 —— 那正是它的作用。
   正解是给判据开 `--base` 换到含新代码的实例真验。
8. **共享文件的提交用 blob 精修**：`run_all_suites.py` 在途（含他人 +3 行）⇒ 以 HEAD 为底只加我的 7 行造 blob
   灌索引（`update-index --cacheinfo`），工作树不动，未吞他人改动。
