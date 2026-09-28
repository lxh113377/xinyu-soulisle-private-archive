# 07-next-steps 卷70 — r70（thin jar 成因登记 / 台账一格能力是尺子造的 / 分类腿挂起预算）

> 取号 `volume_alloc.py`（O_EXCL）｜报告 `交付物/对标分析报告-2026-09-28-r70.md`｜入场基线 `5fbc0ad`

## 一、三条一手事实（读代码看不出来）

1. **r65 挂账「thin jar 成因」已登记**：在已有 `java -jar` 占着 8123 的机器上裸跑 `mvn package` ⇒
   jar-plugin 先把 fat 原地覆盖成 thin（实测 56,728 B，无 Main-Class）→ `spring-boot:repackage`
   要改名 `.original` 但文件被运行中 JVM 锁住（`Unable to rename …`）→ BUILD FAILURE，
   **盘上留下一枚"存在但 java -jar 起不来"的产物**。`build_jar.py`（先 stop_holders 再构建）是约定不是闸。
   ⚠️ 我本轮就是绕开它撞上的，并把**别人在跑**的产物覆盖了：已按 sha 回灌复原（28,446,595 B / `6be524dd51e3442a`）。
2. **`CAP_RULES["vector_memory"]` 用裸子串 `"rag" in path`** ⇒ self 那一格由
   `_test/storage_resilience_check.py` + `_test/plan_pdf_coverage_check.py` 两个文件名撑起（真 vector/embedding/独立 rag = 0），
    peers 侧同尺虚高：重采后 **9→7**（chibi、ryza 出局）。修法= `rag` 须独立词元 + `--selftest` 双向控制
   （6 拒 5 收，并**先自证假阳清单在旧规则下确实会命中**）。总览表里被抄了十几轮的"同类标配向量记忆"据此更正。
3. **`/api/emotion` 分类腿复用聊天链路 60s 超时**（`LlmProxy.newRequest` 硬写），上游挂起时占住工作线程
   一分钟才回落词典；前端同链已压到 15s/整轮看门狗。修法=新增带超时的 `call()` 重载 +
   `xinyu.emotion.llm-timeout-ms`（缺省 8s），**`/api/chat` 仍 60s 不动**。

## 二、回执（可复算）

- JUnit `mvn -B -f server/pom.xml test` → **32 tests**（新增：挂起预算、危机不建连）
- 变异对照：`llmTimeout` 写死 60s → `hangingUpstreamDegradesWithinBudget` FAIL「实测 60.057s」（正常 2.5s）
- HTTP 面单变量 A/B（同枚 jar、独立实例 8129/8128、黑洞上游）：3000ms→**3.11s** ／ 60000ms→**60.22s**，
  两次 `path=LLM 精判失败 → 词典兜底`、`accepted=1`（证明测的是挂起而非拒连）
- 新守卫 `_test/jar_shape_check.py`：三态 PASS/FAIL(thin·零依赖·体积下界·比源码旧)/SKIP(不存在＝未验不算通过)，夹具 5/5
- 接线面控制：同一枚 21MB fat **只改 mtime** ⇒ 绿变红；thin ⇒ rc=1 且红因落在前 90 字符
  （`server_preflight` 在探活**之前**跑产物腿——产物坏时服务必连不上，先探活会用 rc=2「环境未验」盖掉真因）

## 三、两条纪律（本轮踩到/学到）

- **聚合器按宽度截断每套件最后一行**：值写在行尾＝没写（r70 实测 `PREFLIGHT-PASS …src（` 处被截，产物腿整个消失）。
  门面行的数字必须落在**前 60 字符**内。
- **变异对照禁在真件上跑 `git checkout`**：我用 `git checkout -- <file>` 还原变异体，结果把**自己本轮**在该文件的
  未入库改动一并吃掉（SHA-MISMATCH 才发现），只能重打。正确做法＝副本上改、或先 `git diff` 存出自己的 hunk。

## 四、未闭合（不折叠）

`jar_shape` 未占独立 SUITES 名额（避让并行会话在途的 101 套件 hunk；HEAD 99 / 工作树 101）｜
`live_sync`+`ci_status` 判红，闭法只有对外发布，**受老大 09-24 裁决「先不办，降级 10 月复赛」约束**｜
真机复跑未做｜flake 对标缺原文｜8123 上仍是 08:36 起的旧 jar 进程（非我起的服务，未动）｜
`i18n_locale` 3/16 是唯一真实产品差距（09-24 已排赛后，不虚报为已做）
