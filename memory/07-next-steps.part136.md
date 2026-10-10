## r106 入口（按优先级）
1. 🔴 **G12 + 分叉收口方向须老大选定（本轮实测：`origin/main` 与本地 main 已分叉，不是只差 tag）**：
   `git ls-remote origin refs/heads/main` = **e8462ca**（远端 main 正停在那笔「只改版本号三处」的 v1.8.2 发版提交上），
   `git rev-list --left-right --count origin/main...HEAD` = **18 / 41**（远端 18 条本地没有 = r100/r101 原文；
   本地 41 条远端没有 = r101 的 cherry-pick 重放 + r102…r105 全部成果）。⇒ 普通 push 必被拒（non-fast-forward），
   只有三条路：**(a) merge** 把远端旧线并进来（先在副本测冲突数；本地已含同内容的 cherry-pick 版 ⇒ 可能重复/冲突）；
   **(b) force-push** 用本地线覆盖远端（**重写已发布历史**，远端 18 条 SHA 引用与 `v1.8.2` tag 一起失效 ⇒ 须先 `git bundle` 备份远端并确认无他人基于 e8462ca 工作）；
   **(c) 现状挂账**并把对外口径改成「v1.8.2 未生效，下一版从 v1.8.3 起」。
   本仓 post-commit 钩子里**零 `git push`**（`grep -c` = 0）⇒ 自动推送经验不适用，未推是决策不是遗漏。
   前提命令：`git ls-remote origin refs/heads/main` + `git rev-list --left-right --count origin/main...HEAD`。
2. 🟠 **BLIND-RED 余下 4 条崩溃面**：`j4_memory_check` 死于未捕获 `playwright TimeoutError: wait_for_function 15000ms`（③ 同族第二形态：超时必须落「未验/点名红」而非抛栈）；`lightshow_check` 死于自己的对照组（`判据失效：未点亮时也判出这些颜色: ['低落','平静']`，指向在途调色板，**归其作者判**）；`browser_check / pixel_dual` 待定位。前提：`python _test/lightshow_check.py`。
3. 🟠 **E2 继续降数**：现 21/基线 23（起点 31 已接 10）。最便宜的一件 = `_test/mobile_check.py`（单一 `launch()` 出口，形状同本轮三件）。每接一件跑 AST 清点（裸 `chromium.launch(`==0）。
4. 🟠 **face_check 7 处 debt-open 结转**：前提 = 该件作者提交 + `timing_coupling_check --only face_check`；入场 TIMEOUT=630s 先解决（仪器没跑完时任何「结转成功」都不可信）。
5. 🟡 **rollup 派生件重生**：`交付物/对标数据/benchmark-rollup-r95.json` 的 `regression_suites` 仍 144（现 146）；该件被并行会话改着（8/8 diff）⇒ 等干净窗口跑 `python _test/bench_rollup.py`，**派生件最后写**。
6. 🟡 **peers 未重采族**：`peers_build_gates` 时点 10-04（fuse 内已 7 天）、maintenance/repro/memory 多为 10-08 ⇒ 到点**错峰单族**重采，禁 burst（撞限流）。
7. 🟡 **共享交付面纪律**：本轮 29 个文件带真实 diff（非幽灵脏件），本轮 pathspec 与其零交集；下一轮动手前仍先 `git diff --name-only` 复测在途面再定能碰什么。
8. 🟠 **仪器挂起第三档（r105 终验一手）**：整跑停在第 117 行（`clean_clone_selftest` 之后）>18 分钟零输出，
   而 r104 立的 `TIMEOUT(>600s 硬顶)` **没有触发** —— 同轮 `face_check=630s` 确实被拦下过，所以不是 cap 没用，
   是**存在 cap 管不到的挂起形态**（假设：直接子进程已退、孙子进程仍持有管道 ⇒ `communicate()` 无限等）。
   这与 `BLIND-RED(仪器崩了)` 并列成第三档：**既不红也不退**。
   前提命令：`python _test/run_all_suites.py --only <挂起点附近>` 复现 + 读 `run_all_suites.timeout_row()` 与 `run_suites()` 的等待面；
   修法方向＝给等待加**墙钟上限**（不等管道 EOF），且该上限必须与 600s 分档口径一致，不许另立一套。
