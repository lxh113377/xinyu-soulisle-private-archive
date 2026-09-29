# 07-next-steps.part97.md

<!-- 本卷为 07-next-steps.part91.md 的延续 -->

## ③ 本轮最值钱的一条：管 CSP 的闸，自己也对 CSP 全盲

最后一次改这些件的是 `ebf0736`（09-25 20:42，成片 r34 再录）；HEAD 提交时刻 15:02，zip 时刻 15:50，
两次 `git rev-parse HEAD` 同值 ⇒ 删除发生在**最后一次提交之后**，且当时无并发写。

处置：`git checkout HEAD -- <7 条逐路径>`（**不用 `git checkout .`**，会连别人在途 hunk 一起冲），
逐件 `git hash-object` 前后同值（`fe77beaa…` 等），`git status --short 交付物/提交包/` 只剩 3 条 `??`。

**为什么判据只抓到 2/7**：`deliverable_inventory_check`（r59 立）三条分母全来自「清单声明」
⇒ 没写进清单的入库件消失了**永远不会红**（本轮只报 `render-pdf.ps1` 与成片）。
新腿（第 4 条取数面）分母 = `git ls-tree -r -l HEAD -- 交付物`（89 条，被检对象写不进去的量），
逐条验在位性与 0 B；git 取不到 ⇒ `UNVERIFIED` 不判绿。演习（删一件未声明的入库件）⇒
`rc=1 · 入库件从工作树消失: …（HEAD blob 37194 B 在，磁盘没有 ⇒ 无人声明也丢）`，随后按字节还原。

**下一刀（本轮未做）**：这条腿现在只在电池/CI 里跑，而本轮 7 件是**会话开场**才看见的
⇒ 真正的出口是把「入库件在位」接到 `pre-commit` 或 `A-memory-start` 的开场实测里。
另一条未闭合：**肇事者没找到** —— 修判据不等于修根因，下轮若再现需按时刻对齐 `提交包.zip` 的生成方。

## ② G2（r81 建议 4）CSP 内联样式本体：修完 + 两面同步 + 预算登记

7 处 markup 内联样式（src 与 deploy 共 14 个整行指纹）改为：静态进类
（`src/css/style.css` 的 `.crisis-chip` / `.crisis-chip .dot` / `.readout-line` / `.readout-lead`）、
动态走 `data-fg`/`data-bg`/`data-w` 由 `src/js/app.js` 新增的 `paint()` 一趟 CSSOM 落属性。
**没有放宽 `deploy/xinyu/_headers` 的 `style-src 'self'`**（那是缺陷本体不是约束；H3 棘轮仍咬 `'unsafe-inline'`）。

字节代价（如实记，不静默）：`style.css` 13,813→14,081（超原预算 13,888）⇒ `size_budget_check` 登记 14,785，
理由写在 BUDGETS 注释里（登记前先把 CSS 注释从 106 B 压到 60 B，解释移进判据注释）；
`app.js` 17,036→17,405，仍在 17,524 内；TOTAL 848,879 / 858,752 未动。
回归：`inline_style_check` `扫描=30｜命中=0｜新增=0`（基线清空 ⇒ 转纯网，任何新写内联样式当场红）；
`deploy_sync_check` rc=0（missing/diff/extra 三类归零）；`browser_check` **ALL-ASSERT-PASS**
且 `LIT: init=0 after1=5 after2=17 reload=17 clear=0` 与既有基线逐字相同（证明没改坏点亮链路）。

## ③ 本轮最值钱的一条：管 CSP 的闸，自己也对 CSP 全盲

把 HEAD 未修版（7 处内联样式）放回 `deploy/xinyu/js/app.js` 跑 `headers_csp_check` ⇒
**`HEADSEC-PASS … CSP 下应用可用（五幕=5 对话=True 异常=0）`**。即 r81 那句「本地判据全盲」
不止说中 `browser_check`（Java 服务不发 CSP 头），也说中了这道 r54 就在的、**本该**管 CSP 的闸。
两条根因：① `probe["app"]` 只带 `errors`（pageerror），从不读收集 console violation 的 `vios`
—— 内联样式被拦**只写 violation、不抛 pageerror**；② H2 探针只加载页面 + 发一句话，不驱动第二幕读数/危机条。

补 **H6**（夹具 `--selftest` 8→13 腿，`expected` 由 `ok+len(fail)==expected` 双向钉）：
- 驱动普通轮 + **危机轮**，词面必须取自 `src/data/emotion-lexicon.js` 的 crisis 表（实测「跳楼」**不在表内**，
  它是 `SafetyGuard` 的输出高危词 —— 拿输出词当输入探针会让这条腿永远打不到分支，本轮第一版就是这么写的）；
