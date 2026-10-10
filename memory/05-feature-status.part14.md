### r105（2026-10-11）判据层与工具层四项改造（产品源码零改动，与并行会话在途面 pathspec 零交集）

- [x] **G16 孤儿判据接线** — `_test/dock_auto_check.py`（对话坞滚动收起/三态/演示态，D1-D11）从「在提交面却两头不执行」
      接进电池 SUITES + `docs/quality-gates.md` 同笔登记。**接线前两侧先测**：HEAD 面 11/11 PASS、工作树面 15/15 PASS。
      复算：`python _test/repo_config_check.py`（G16 段现绿）｜`python _test/run_all_suites.py --selftest`
- [x] **E2 唯一实现棘轮降数 24→21**（基线 23，起点 31 ⇒ 已接 10）— `ux_guards_check` / `settings_panel_check` /
      `public_check` 三件的手写 launch 回退收编进 `browser_engine`，**引擎身份折进各自判定行**
      （`… PASS 引擎=msedge(channel)(155.0.4283.45)`）⇒ "本地浏览器判据全绿"这句话第一次可归因。
      复算：`python _test/browser_engine_declare_check.py`
- [x] **仪器崩溃面收口（BLIND-RED 族，2/6）** — `vendor_freshness_check.py` 新增 `field_problems()` 五字段门
      （file/version/sha256/size/detect 的缺失与类型各自点名条目），`detect:null` 升为**一档合法声明**
      （只关 V2 那条腿，V1 照查，参与数折进判定行）。`TypeError` 崩溃 ⇒ 点名判红；`--selftest` 5 类 → 10 类，
      变异体（摘门）当场 `KeyError: 'detect'` 复现旧崩溃。复算：`python _test/vendor_freshness_check.py --selftest`
- [x] **端口 8123 属主协议** — `build_jar.stop_holders()` 由「按端口逐个 `Stop-Process -Force`」改为四档归类
      （`ours / same-artifact / foreign / unknown`，**取不到命令行归 unknown 不升格为可杀**），默认只停本工具起的
      （租约 `%TEMP%/xinyu-port-lease.json`），`--takeover` 才是人授权的接管口，拒绝时 rc=2 不构建。
      真面只读探测 pid 23828 ⇒ `same-artifact`、默认 `kill=[]`；`BUILD-JAR-SELFTEST-PASS（11 条）`，桩已进电池（`build_jar_selftest`）。
- [x] **电池口径 144 → 146**（`README.md` 声称数被自家 G4 当场纠出并同步）
- [x] **唯一入口地图修复** — `交付物/对标总览-合并索引` 轮次表补 r98–r105、「最新」指针 r96→r105；
      r97/r103 两侧实测无报告文件，写清事实不补造。
- ⚠️ **新事实（不改代码，改对外口径）**：远端 `v1.8.2` tag 指向的 e8462ca **不在 main 祖先面上**
      （`git merge-base --is-ancestor e8462ca HEAD` 非零）⇒ G12 是「切了没落地」，收口方向待老大选。
