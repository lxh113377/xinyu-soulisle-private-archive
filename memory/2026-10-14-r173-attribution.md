# 2026-10-14 · r173 归因线（轮台账）

第 15/16/17 次重发 ⇒ 同一轮续跑（不重复产出 r172 已有件）。HEAD 起点 `f6a47c9`。
本轮的选题不是"再找新功能"，而是**拿上两轮刚立的规矩审上两轮刚写的尺**，抓到 1 条判据把自己的红因写错。

## 1. 四项改造（按优先级）

| # | 项 | 排序依据（盘面红因，非主观） | 落点 | 验收读数 |
|---|---|---|---|---|
| S1（高） | 耦合尺**三态归因** + 两处定长等待换完成态等待 | `timing_coupling` rc=1：C1=21>基线 20 且"评审账对不上" | `_test/timing_coupling_check.py`、`_test/asr_replay_check.py`、`_test/quote_eval.py` | rc=0：`C1=19(电池19) 基线20`、`覆盖 19/19`、`moot=1｜face_check.py→NEXT_NO_READ`；桩 49→**52/52**；`asr_replay` 真跑 `ASR-REPLAY-PASS 样本=24` rc=0 |
| S2（高） | 兜底棘轮 111→108（补装 4 台） | `blindred_guard` rc=1 且电池里唯一那条 BLIND-RED 就是 `mysql_degradation` | `mysql_degradation_check.py`／`perf_api_check.py`／`asr_replay_check.py`／`mysql_backup_drill.py` | `BLINDRED-HOOK-PASS 顶层脚本=122 已兜底=14 未兜底=108｜基线=108`；四台各自 selftest rc=0（7/7、19/19、12 腿、11/11）；`blindred_guard --selftest` 七向变异仍成立 |
| S3（中） | 同步尺每条红目带**归属位** | r172 为搞清"这条能不能由我修"人工跑了 3 条命令 | `_test/deploy_sync_check.py`（`side_state`／`attribute_owner`） | rc=1 三条分叉各自印 `｜归属=他方在途(不代提交他人 WIP)`；`--selftest` rc=0（提交面腿 8 + **归属腿 5** + 函数面 6 类 + 真面分母 36） |
| S4（中） | 文档登记 + 本报告 + 台账 | 判据没写进受理面 = 半成品 | `docs/quality-gates.md` 2 条 | 与 S1/S2/S3 同批提交；`deploy_sync`/`blindred_guard`/`timing_coupling` 三条 selftest 复跑全 rc=0 |

## 2. 本轮抓到的一条判据缺陷（重点，别压成"已修复"）

`timing_coupling` 报 `face_check.py::page.wait_for_timeout(400)（账里有，现读无此形状 ⇒ 锚点陈旧或该件已被改掉）`。
**盘面复核否证了这句归因**：`face_check.py:317 pg.wait_for_timeout(400)` 与 `:328 page.wait_for_timeout(400)` 都在，
只是采集器把它们分进 `NEXT_NO_READ`（等待之后那条语句不取数），而评审账的键只从 `C1_HARD` 桶构造
⇒ "形状仍在、桶变了"被说成"读不到"。
危害不是措辞而是**引导错误动作**：照字面理解会去改 `face_check.py`，或者把台账那行删掉求绿，两条都破坏被审对象。
修法：三态拆开（真消失／换桶要红并印桶名／声明 moot 则免检但**必须自印**）＋矛盾腿（moot 却回到 C1 ⇒ 当场红）。
**这是 r172 "红里只能有它（②-e）/红因必须点名（②）"那条规约第一次在本仓被判据自身踩中并被自家腿抓住。**

## 3. 失败面（与成功面同条，禁只写交付）

1. **兜底补丁把文件写坏一次**：`mysql_backup_drill.py` 的 `sys.exit(main())` 在 `if __name__` **块外**（模块级），
   我按块内缩进插进去 ⇒ `IndentationError: line 325`，`py_compile` 当场拦下。
   同因第二次：另一台的 `raise SystemExit(main())` 收尾形状不同，脚本里 `SKIP-SHAPE` 分支把它放过了 ⇒
   **"装上"的证据必须是编译 + 该件自己的 selftest，不能是补丁应用成功**。
2. **变异腿第一次跑在仓外 ⇒ 两条都 rc=2 未验**：副本放 `%TEMP%`，`ROOT = parents[1]` 指不到仓，
   判据老实报 `真面取不到 HEAD（git 128）`——对照组与变异组同形，等于什么都没测。
   正解＝副本建在仓内 gitignored 面（`_temp/`，`.gitignore:97`）＋未变异对照组 rc=0。
   （②-b"反例的输入面必须落在被保护分支上"的第四次实发，载体维度从"路径权限"扩到"仓根解析"。）
3. **`quote_eval` 改造只验了一半**：`timeout 280` 的调用方天花板先撞上，真跑到 8/60 用例，
   末行 `QUOTE-EVAL-UNVERIFIED: Page.evaluate: Target page, context or browser has been closed` 是**被杀副作用**，
   不是判定失败；能确认的只有"页面装载那一半由新等待放行"。完整真跑记 R173-04 未验。
4. **`rc` 从管道读**这条老坑本轮又踩了一次（`... | tail` 后 `$?` 是 `tail` 的），已按 r172 立的载体改走重定向/`run_logged`。

## 4. 未闭环（带可复算前提）

- **R173-01 三条提交面分叉**：`deploy_sync` 三条均自印 `归属=他方在途` ⇒ 本轮不代提交。
  `前提=git rev-parse HEAD:src/<rel> HEAD:deploy/xinyu/<rel>` 两侧同号，且 `python _test/deploy_sync_check.py` rc=0。
  分叉计数 **1→3**（`emotion-lexicon.js`/`index.html`/`js/app.js`）：并行会话在 r172 后又落了 `5218164 fix(deploy): app.js …`，
  这条新维度上线两天内又抓到 2 条同类缺陷 ⇒ 收益不是理论值。
- **R172-02 / R173-07 perf 关闸配置的远端回执**：仍无（本地独有 216 ⇄ 远端独有 18，禁 force-push ⇒ 推送顺序需人工对齐）。
- **R173-04 `quote_eval` 完整真跑**：本轮未取到结论行。
- **整跑电池**：本轮未重跑全量（S1/S2/S3 各自 selftest + 定向真跑已覆盖改动面）；
  上轮收据 `BATTERY: 172/199 rc=1`（01:07 落地）仍是最近一次全量读数，**不得当作本轮验收**。

## 5. 机器资源

本轮未起任何服务实例（复用并行会话持有的 8123 做只读浏览器验证），无归还动作。
`_temp/` 下我本轮创建的 3 份变异副本已删除；`_temp/` 内其余文件是他人产物，未动。
