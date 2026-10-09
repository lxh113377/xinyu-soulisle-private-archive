# 07 分卷 r101 部署段 — 2026-10-09（QD 端）

> 取号：`volume_alloc.py` 独占建卷（本卷字节由落盘后复量，不写占位数）。

## r102 入口追加（公网站段实测所得，本轮只登记未动）

1. **Pages 直传必带 functions**：`wrangler pages deploy <dir>` 的 Functions 取数面是 **cwd 的 `functions/`**，
   不是被上传目录里的 `functions/`。实测第一次从项目根跑 ⇒ 部署成功但 `/api/chat` 由
   `400 {"error":"bad-json"}` 变 **405**（函数丢了）；改到 staging 目录内跑（`cd` 进去 + `deploy .`）
   ⇒ 输出 `Compiled Worker` + `Uploading Functions bundle`，函数面恢复。
   **落点**：`live_sync_check` 增一条**零配额**函数回执腿（POST 坏 JSON ⇒ 期望 400，禁打真实上游），
   并把「部署后同链跑该腿」写进发布说明；现成兜底只有 `public_check` P6（真发消息，花配额）。
2. **Pages 的 git 连接已停摆**：`pages deployment list` 最近一次 Production 构建源 = `c567ad3`（10-01），
   而 `origin/main` 已到 `8b54af6`（10-07）⇒ 一周的 push 没触发构建。本轮线上内容靠**手工直传**对齐。
   ⇒ 合并任何 PR 前须先核 Pages 的 build output 目录设置，否则一次 git 构建可能把线上打回旧内容。
3. **CloudBase CLI 的 MSYS 路径改写**：`tcb hosting deploy deploy/xinyu/js/x.js /xinyu/js/x.js`
   会把云端路径写成 `C:/Program Files/Git/xinyu/...`（`git bash` 的 PATH 转换），且 rc=0 报成功。
   正解 = `MSYS_NO_PATHCONV=1` + 全 ASCII 本地路径。本轮因此造出 1 个野对象（今日时间戳），
   已 `tcb hosting delete` 清除并复量（今日戳野键 0 条）。
4. **桶内 24 个野键是 09-30 残留**：`C:/Program Files/Git/xinyu/**`（LastModified 2026-09-30 01:45）
   = r83 那次「根 index.html 被同环境另一项目覆盖」事故的同一形态残留，**非本轮所造 ⇒ 未动**。
   待裁决：删（它们是公网可读的野副本，键名含 `js/demo-config.js`——**是否零密钥版未逐件回读，删前先拉回验**）
   或留着当证据。
5. **LFS 与入库字节不一致**：`交付物/提交包/**.mp4` 等 3 件以**裸 blob** 入库，而 `.gitattributes`
   给它们设了 `filter=lfs` ⇒ 任何新 clone / 新 worktree 一检出就报脏（`should have been a pointer,
   but wasn't`），`git rebase` 直接被 "unstaged changes" 拦下。本轮绕行方式 = 临时 clone +
   `cherry-pick`（只 14 个提交，不碰这些路径）。根治要么 `git lfs migrate`，要么把这些路径移出
   lfs 属性——**属他人交付件，本轮未动**。
6. **共享仓库里 `refs/stash` 是全仓共用**：在 linked worktree 内 `git rebase --autostash` 写的
   stash 落进同一个 `refs/stash`（本轮实测：主树 `git stash list` 立刻看得见那条 `autostash`）。
   ⇒ 在册「共享工作树禁裸 stash」再添一手；本轮事后按内容核验（只有那 1 个 mp4）才 drop。
