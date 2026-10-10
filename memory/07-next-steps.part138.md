- **卷42** `07-next-steps.part138.md` — **r105 追加段（老大在收尾询问后选定「先只做代价实测」＋「优先修整跑挂起那一档」）**：
  ⑤ **执行器改造**：终验第一次没跑完（停 #59 之后 >18 分钟零输出，r104 立的 600s 硬顶**一次没触发**）。
  根因＝调用形态：`subprocess.run(capture_output=True, timeout=600)` 超时那刻是「kill 直接子进程 → `communicate()` 读空管道」，
  而判据起的 chrome/edge/java **孙**进程继承同一对 stdout/stderr 句柄且没死 ⇒ EOF 永不到来 ⇒ communicate 无限等 ⇒ TimeoutExpired 递不上来。
  修法＝输出**不走管道**（临时文件，读文件不需 EOF）＋到点 `taskkill /T` 杀整棵进程树（PID 本次 Popen 创建 ⇒ 归属确定）。
  三腿 `EXEC-SELFTEST-PASS`（正例 rc 透传／挂起夹具 cap 附近返回＋部分输出可读／**旧机制对照拿不到结论**）；`BATTERY-SELFTEST-PASS（8 档）`。
  **换后终验跑完** ⇒ `BATTERY: 131/143 rc=1`，红 22→**11**、BLIND-RED 6→**1**（剩 lightshow 是并行会话自己的对照组真信号），TIMEOUT 桶照常点名 face_check=600s 且继续跑完。
  仪器故障在册三档：**崩**（BLIND-RED）／**挂**（既不红也不退，本轮新收）／**超时**（cap 有效）。
  ⑥ **改判一条被当不变量的一次性取证**（我自己踩出来的）：①的迁移让 `browser_engine_declare --selftest` 翻红 ——
  该腿断言「AST 面 ⇄ 旧子串面对称差为空」，而我在 docstring 照抄旧写法登记代价 ⇒ 子串面多认一件；它**下一腿自己就证明**子串会虚增分母
  ⇒「对称差为空」是 r98 换尺那一刻的一次性取证被误当永久不变量，留着＝**逼后人删证据**。改判＝`AST ⊆ 子串` ＋ 差集逐个实测「调用点=0 且文本命中>0」
  ＋ 构造 `launch (` 换行证反方向可造 ⇒ `SELFTEST-PASS（45/45）`、真面 `余量 21`。
  自曝：该改动一度把 `selftest` 顶到 168 行越过 ≤150 行门（loc_guard 多报一件），抽成 `_st_face_equivalence()` 后回 133 行、门恢复 4 件（全属并行会话）。
  **第二次终验（追加段修完，05:49）跑完**：`BATTERY: 135/145 rc=1`，RED 22→**9**、BLIND-RED 6→**1**、TIMEOUT 桶照常拦下 face_check=600s 并继续跑完；
  `repo_config` 红只剩 G12（G4 在 SUITES 146→148 时又咬一次并同步 README ⇒ 那条纠漏改的尺确认还在工作）；九条红逐条归属见报告 §6.1b，**本轮责任面内零红**。
  ⑦ **分叉三条路代价实测（只读，未动正式仓）**：merge ＝ `git merge-tree --write-tree` 现读**冲突 9 个文件**（CHANGELOG/README/docs/quality-gates/public_check/run_all_suites/timing_coupling/ledger_age/clean_clone/07 主壳，
  其中 4 件正是本轮我改过的 ⇒ 合并轮必须逐件复验）；force ＝ 作废面实测仅 `v1.8.2` 一枚 tag（`git tag --contains e8462ca` 唯一命中），
  `git branch -a --contains` 只有远端自己、`git worktree list` 只有一个 ⇒ 无他人基于它；挂账 ＝ 对外写 v1.8.2 的地方**只有 3 个文件且全是本轮自己的记录**，
  README/ROADMAP/提交包 PDF 从未写过该版本号 ⇒「改口径」几乎零对外代价。**待老大据此选路。**
