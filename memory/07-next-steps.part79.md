
> 接续卷78。切卷理由（数字实测）：07 主壳 4,080 B / 封顶 4,096 B ⇒ r76 新账落本卷、壳内只留指针；
> 「推荐下一步」与「从壳迁来的条目」两块因本卷仍超 4,096 B 硬限，另起卷80。
- [x] ✅ **r76 构建期测试面（R75-02 闭合）**：四个 0% 类补齐（Emotion/Memory/Chat Controller + MemoryService，
      四者占缺口 69%），另把 HealthController 与 ApiTokenFilter（AC-OBS-12 此前构建期 0 用例）也钉住。现测测试类 **10** 件 / `@Test` **62** 个（复算：`find server/src/test/java`、
      `grep -rho @Test`）；jacoco LINE **268/669=40.06% → 615/669=91.93%**，
      0% 类 **10 → 1**（只剩 SoulIsleApplication 的 3 行 main）。`<minimum>` **0.35 → 0.85**
      （91.93 距 0.90 只剩 1.93 点＝零余量地板，按 r75 那把尺的算法不取）；
      验牙＝临时改 0.99 ⇒ `rc=1` 红因 `lines covered ratio is 0.91`，按字节还原（sha256 `626fe300…` 前后相等）⇒ `rc=0`。
- [x] ✅ **R75-05 产物新鲜度真红闭合**（复算=`python _test/server_preflight.py`）：开场实测 8123 **无监听者**
      （他人 08:36 起的那个 java 进程已退出）⇒ r75「不代停」的前提消失，`python _test/build_jar.py --restart`
      重打 jar 并起服务 ⇒ `PREFLIGHT-PASS: jar=fat(bytes=28447811 libs=46,新于源码) 夹具=5/5｜服务 status=UP`。
- [x] ✅ **AC-OBS-09 的过期引用值已纠（R76-01 的一部分）**：新锁第一次真跑就把文档判红——AGENTS.md 的 AC-OBS-09
      与 J3 行仍写 `36 条 / 94.4% / crisis 3-3 / misses 两条`，磁盘与 JS/Java 双端现值都是
      `73 条 / 98.6% / 6-6 / misses 1 条`（评测集 09-23 由 36 扩至 73；`memory/03`·`06` 早就对，**只有注入面没人重算**）。
      处置＝按实测纠判据的引用值 + AGENTS.md 四处加更正注（原文当日为真保留）+ `engine_consistency_check.py` B 层说明；
      不反过来改数据凑绿。
- [x] ✅ **同址尺的另一半塌缩已修**（`_test/benchmark_metrics.py`）：chibi 那次 tree 取数失败而 README 取成功，
      旧写法把 `docs_site/changelog_root` 直接判 False ⇒ 同一条尺 6 小时内 9/16→8/16、3/16→2/16，漂移行不点名这类翻转。
      修法＝纯函数 `doc_perf_downgrade`（整棵 tree 没取到 ⇒ 树派生类降 **None=未验**，文本派生类不受牵连）
      + `doc_perf_counts`（有/无/未验三档分列）+ 打印行拒写「N 仓无 X」；`--selftest` 加 4 条腿（含摘掉名单即翻判的变异体）。
- [ ] 🔴 **R76-01 剩余面**：本轮只纠了评测数字。「文档里的数字是抄来的、没有判据回读」这一类还有别的出口——
      已具名：`docs/quality-gates.md` 与 README 的覆盖率门读数（阈值 0.35→0.85、LINE 40.06%→91.93% 都变了），
      而这两件**此刻正被他方在途修改** ⇒ 不抢改。`前提=git status --short docs/quality-gates.md README.md`（M 消失后再动）。
- [ ] 🟠 **R76-03 回归链挂在 8123 这个单点上**（本轮一手测得）：8123 一退，整跑电池从 **93/98 掉到 73/98**
      （13 判红 + 11 环境未验 ＝ 21 个套件挂在一个人工/半自动起的进程上）；起回来同样的代码回到 93/98。
      方向＝runner 自起自停或按端口分桶，验收＝拔一次进程再整跑，红名单不得因「服务不在」膨胀。
      ⚠️ 与 R71-03（并行第一刀只并非共享 8123 桶）同源，别重复立项。
- [ ] 🟡 **R75-03 仍在**：`--quality-gates` 的 workflow 上限 12 ⇒ lobehub 的 lint/typecheck 两格永远记未验。
- [ ] ⏳ iCAN 报名 PII（截止 **2026-09-30**，**剩 1 天**）与发布裁决（R1 `feats=11/5 unreleased=98`，
      本轮 feat 提交后实测；一次性清 `live_sync`/`ci_status`/R1 三条红）——两件事都在老大侧。
- [ ] ⏳ 真机复跑、flake 对标原文、`mvn verify` 的 CI 实跑回执（推送后读 java-build 日志的 `jacoco:check` 行）。

