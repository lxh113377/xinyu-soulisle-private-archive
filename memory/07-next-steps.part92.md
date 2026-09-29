# 07-next-steps.part92 — r83 轮完整记录（2026-09-30）

> 从 07 壳迁出的长段落全文。壳只留一行摘要 + 本卷指针。

## ① 交付面在位这条腿「建好了，但站在没人经过的出口」（R82-01 的下一刀，本轮闭环）

r82 补的第 4 条取数面（分母 = `git ls-tree -r -l HEAD -- 交付物`，本轮 90 条）方向对，但它只在电池/CI 跑，
而 09-28 与 09-29 两次事故都发生在**两次提交之间** ⇒ r82 那一轮仍要靠会话开场才看见 7 条 ` D`。

本轮落点（两件，都被跟踪、都可复算）：
- `_test/hooks/pre-commit`（源，2,347 B）：只拦「已入库交付件从工作树消失」；
  **fail-open 是设计** —— 判据 rc=2（取不到数）或找不到 python ⇒ 放行并报警；
  rc 不在 {0,1,2} 一律按 CRASH 报警但不拦（r82 把硬崩判成「环境未验」= 通行证，这条不再犯）。
  逃生门 `XINYU_SKIP_DELIV_HOOK=1` **带计量**：每次跳过往 `.git/xinyu-hook-skip.log` 追加一行并打印累计次数。
  **不动 `core.hooksPath`** —— 本仓 `.git/hooks/` 里已有 `post-checkout`/`post-commit`（Mimosa 占位），
  改 hooksPath 会让它们静默失效，那是拿别人的工具链换我的闸。
- `_test/hook_wiring_check.py`（新判据，接入电池两条 ⇒ 套件 103→**105**）：
  W1 源在位且 `sh -n` 解析得动；W2 `.git/hooks/pre-commit` **按字节 == 源**（改源没重装就红）；
  W3 被拦判据的三态（pass/block/unverified）与 `tracked_missing_check`/`committed_blobs`/`parse_ls_tree` 仍在位。
  `--install` 唯一装法：异版先备份 `pre-commit.bak-<sha>`，写后**读回**断言等值。
  `--selftest` **12 腿**，反向方向含：副本漂**一个字节**必须红、CI 面（新克隆）**不得**判红、
  源被截成一行必须红、零输入绝不 ok、硬崩 rc 不并入未验；
  **端到端腿**在 `tempfile` 里建一个真 git 仓、装真源、真删一件入库件 ⇒ 钩子真回 rc=1 且点名。
  真面演习（本轮实测）：靶 = `交付物/提交包/demo_video_out/timeline.json`（354 B，**未写进声明面**），
  删 ⇒ `rc=1 且点名`，按字节复原（sha `c277581073f9`）⇒ `rc=0`。
  靶子取数直接 `import deliverable_inventory_check` 复用 `committed_blobs()` —— 本仓另写一份 `ls-tree` 解析
  第一次就把 CJK 路径读成 `"\344\272\244..."` 那种**根本不是路径**的串（0 候选 ⇒ 判未验，没蒙绿）。

## ② 在册的国内备用链接已经不是心屿的页面（一手取证 + 加法修复）

`tcb hosting list --json` 现场读数：该环境静态托管**根目录由三个项目共用**
（24 个 `NN_*.html` 是 iCAN 门店快照集，`zhengwen-api` 是医项目的云函数，`__auth/`、`cloud-admin/` 是平台件）。
心屿那批 `js/*`、`css/style.css` 停在 **09-19 18:54**；根上 `index.html` 的 `lastModified = 2026-09-24 21:01:07`，
**与 iCAN 那 24 件同一批次**；现场 `curl` 取到 `<title>iCAN 演示快照集</title>`，
而本地 `deploy/xinyu/index.html` 是 `<title>心屿 · AI 情感陪伴 — 滚轮驱动的 3D 情绪叙事</title>`。
