# 07-next-steps 分卷 · r97 语音退出态修复 + v1.8.1 切版（2026-10-06）

## 已完成（本轮实测）

- 🔵 **挂账三轮的 `voice` 退出态缺陷已修**（§3 #9 / `part113`）：`src/js/voice.js` 新增幂等 `leaveListening()`，退出分支改为「`try { rec.stop(); }` 后**本侧立即复位**」，`start()` 包 try、抛错即复位。根因两处同一出口：① `listening` 与 `class="recording"` 只由 `onend`/`onerror` 清除，而浏览器不保证 `stop()` 后派 `end`；② `start()` 未包 try，抛错时同样留在监听态 —— 违反 `voice.js` 约束 2。
- **判据**：`_test/voice_check.py` 加三条桩化腿 A8/A9/A10（整体替换 `window.SpeechRecognition`）+ 各带反例腿 ⇒ 与环境无关，CI 里不许走 SKIP 降级。
  先验 RED（未修树，同一命令）：`A8 卡在监听态（evt=['start'] class='ghost-btn voice-btn recording'）` + `A10 卡在监听态` + `A10 约束2 违背（pageerror ['InvalidStateError: recognition already started']）`，同一轮 `A9/A9b PASS` ⇒ 三条腿不是恒红。
  修后复算（**必须传 base**）`python _test/voice_check.py http://127.0.0.1:8123`：中间形态 run1–6 + 最终树 `voice_final_1..5`，**11 轮全 rc=0**；且 11 轮真机 `hook(final)` 一律是 `ev=['start','audiostart']`、`stopped:1`、**无 `end`** ⇒ 当晚这条路径 11/11 必现（r96 记的是 3 次里 1 次）。A5 的 8s 预算一字未动、未加重试。
  🔴 判据自错一处（已修）：A9 第一版先轮询 class 后读 `evt`，而修好后 class 是同步复位 ⇒ 抢在桩 30ms `end` 定时器前读数，把对照腿误判成红（`rc=1`）。正解＝先等被断言的事实到场再断言（与 `settle_wait` 同族）。
- **体积预算**：`src/js/voice.js` 上限 4,355 → 5,038（实测 4,798 ×1.05，沿用本表「基线 ×1.05」口径），登记前先把自己新写的注释 5,039 → 4,798 B（−241 B）；理由记在 `_test/size_budget_check.py` 表内注释与 `CHANGELOG` 的 r97 段。TOTAL 849,529 / 858,752 仍在限内。
- **v1.8.1 切版三源**：`server/pom.xml` 1.8.0→1.8.1 + `ROADMAP.md`「当前版本：**v1.8.1**」+ `CHANGELOG.md` 新增 `## [1.8.1]`（r96 那段的 `### ` 标题**原位承接**、一字未改）。fat jar 重建 `BUILD-JAR-PASS … 内嵌 version=1.8.1 == pom`，服务已重启 :8123。
- 本轮跑过且绿的面：`DEPLOY-SYNC-PASS missing=0 diff=0 extra=0(白名单外)`、`JS-SYNTAX-PASS 28/28`、`LOC-PASS`、`EOL-PARITY-PASS text=609 binary=28`、`BUDGET-PASS 22 文件`、`DISCLAIMER-CLEAN 报告 50 份 缺取证 0 处`、`CI-CONTRACT-PASS 问题=0`、`VERDICT-EXIT-PARITY-PASS defect=0`。

## 待办（P0 收口 / P1）

- ⬜ **残余（本侧动作界 ≠ 原句的有界时间界）**：`start()` 后若既不派 `end` 也不派 `error`，按钮需用户点一下才复原 —— 从「只能刷新页面」收敛为「一次点击」，未做到零操作（API 在这个形状上不给「还在听 / 已静默结束」的区分信号，固定 timer 会在真在听时谎报未听 ⇒ 不取；取舍详见 `CHANGELOG` r97 段）。

- ⬜ **本轮收口链未完**：整跑电池 → `greencheck` → 推 main + tag `v1.8.1` → `ci_watch` 取 CI 回执 → GitHub Release `v1.8.1`。
  `前提 = python _test/run_all_suites.py --exclude-llm`，且**必须跑在 tag 建好之后的冻结树上** —— tag 未建时 `release_governance`（R2a/R2c 拿 v1.8.0 当基准）与 `repo_config` G12（tag=v1.8.0 而 pom=1.8.1）两格必红，本轮已一手复现过，那不是缺陷是切版中间态。
- ⬜ `A4=SKIP|PASS` 在受理面仍无读数（r96 §2.9 更正注）：本轮新增的三条桩腿让「退出态」有了不依赖 A4 分支的断言，但那把「A4 到底走了哪个分支」的尺还没做。
- ⬜ v1.7.0 从未有 GitHub Release 页（v1.6.1 直跳 v1.8.0，r96 一手查出）⇒ 可选补。
- ⬜ 上一轮挂的体量项继续沿 `part119`：07 卷族体量（需名册许可）、`_trash/` 清理（需老大在场）。
