# 07-next-steps 分卷 · 卷87 — r81 账（一）：CSP 拦掉的那半，修法与前提（2026-09-29）

# 07-next-steps 分卷 · 卷87 — r81 对标轮账（2026-09-29）

> 独占取号建卷（`volume_alloc` O_EXCL），壳内只留判定行，全文在此。
> 本轮入场基线 `3f4eca5`（= origin/main）。报告全文：`交付物/对标分析报告-2026-09-29-r81.md`。

## R81-01（新登记，高）线上情绪强度条被 CSP 拦成失效，而本地 46 道判据全盲

- **一手证据链**：`deploy/xinyu/_headers:28` = `style-src 'self'`（无 `unsafe-inline`）；
  `python _test/public_check.py` rc=1 → **8 条** `Applying inline style violates … 'style-src 'self'`（去重 5 个 sha256）；
  写点 = `src/js/app.js` 的 `innerHTML` 模板串 7 处（现读 L60/61/**94/97/99/124/125**，
  行号较 r78 记的 93/96/98/122/123 各 +1，因并发会话在上方插了 `stopOpening()` 一行）；
  其中 L94 含 `width:${pct}%` ⇒ **被拦的不止颜色，是那条读数条的宽度**。
- **本地为什么看不见**：本地服务不发 CSP 头 ⇒ `browser_check.py` 对这类破坏全盲；只有打线上的 `public_check.py` 露出来。
- **探针边界（本轮新量到）**：自建 Playwright 探针（纯加载 + 单次滚动）= **0 命中** ⇒ 触发面在**交互路径**
  （第二幕读数 / 危机条 / 一键点亮）。⇒「打开首页看一眼没红」不构成反证。
- **修法（不改判据、不放宽 CSP）**：静态样式迁类（`margin-top:8px`→`.mt8`、`margin-bottom:8px`→`.mb8`、
  危机条 `border-color:#ff7a7a;color:#ff9a9a`→`.chip-crisis`）；动态值（颜色/宽度）在模板里改用 `data-c`/`data-w` 携带，
  `innerHTML` 之后一趟 CSSOM 赋值（`el.style.color=` / `el.style.width=` **不受 `style-src` 约束**，这是本修法成立的前提）。
  ⚠️ `src/css/style.css` 现读 13,813 B / 预算 13,888 ⇒ 余 **75 B**，加三条类大概率要按 r47 先例上调预算并把理由写进 CHANGELOG。
- **前提（可复算，缺则不得动手）**：`git status --short src/js/app.js` **为空**。
  本轮实测该文件正被并发写入：字节在两次读数间 15,526 → **17,285**（+37 行，注释自称「r80 开场自动播放」），
  且并发面从 5 项扩到 **13 项**，新入列的正是本修法会牵动的
  `deploy/xinyu/js/app.js`、`_test/browser_check.py`、`_test/j4_memory_check.py`、`_test/lightshow_check.py`、
  `_test/pixel_dual_check.py`、`_test/storage_resilience_check.py`。
- **验收**：`python _test/inline_style_check.py` 印 `已清偿=14` → `deploy_sync_check` 两面同改 →
  `browser_check`/`data_rights_check` 功能不回退 → **`public_check` 无 `Applying inline style`**（这一步才算线上真绿）。
- **本轮已落的部分**：`_test/inline_style_check.py`（213 行 / 9,829 B；夹具 13/13；真面主树 rc=0、HEAD 隔离面 rc=0；
  注入演习 rc=1 且点名到行）+ `.github/workflows/ci.yml` 前端 job 接线一步。**闸在位，代码未修**。

## 迁出留存（原文照录，勿当删除）

> 以下三行自 07 主壳迁出（壳仅剩 33 B 余量，4063/4096；R161 口径）。判定未变：**该 P0 项已作废**。

- [ ] ~~**PDF 起草（冻结待解冻）**~~ —— **已作废（2026-09-26 复测）**：PDF 早在 09-24 产出、09-25 三修、09-26 16:59 重渲染；
      本行与上一行同源：都是 `handoff.py sync` 对本项目结构检测部分失效留下的 **09-22 快照**（详见 08「已识别的判据误报」第 2 条）。
      ⇒ **读 P0 以 `memory/07-next-steps.md` 为准**，本文件 07 段是快照。
