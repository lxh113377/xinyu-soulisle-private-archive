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
