# 卷47 — r49 一键点亮补回：窄屏改「收图标」而非「整块藏」，豁免账已撤（2026-09-27）

> 前卷：`part43`（归因）｜`part44`（判据与两条未闭环）。本轮起因 = 老大改判「把这个功能补回来」⇒ 动样式。

## 1. 改法（三处，src 与 deploy/xinyu 逐字节同步）

- `style.css` 480 档：`#btn-lightshow{display:none}` ⇒
  `#btn-lightshow .ls-word{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)}`
- `index.html:101`：文案拆 `<span class="ls-ico">✨</span> <span class="ls-word">一键点亮</span>`
- `app.js`：加 `setShowLabel(ico, word)`，两处整串 `textContent=` 改走它（✨ / ↺ 两态同步）

用 sr-only 裁切而非 `display:none` 藏文字，是为了**可访问名与桌面档逐字相同**：
四档 `get_by_role("button", name="✨ 一键点亮")` 均命中 1，`a11y_check` 12 单元违规节点 0。

## 2. 回执（真点，不是"看起来在"）

四档（390x844 / 320x568 触屏，479x900 / 1280x800 细指针；每档先反注册 SW 再测，防旧缓存假绿）：
入口尺寸 触屏 **44x44**（WCAG 2.5.8）｜479 档 38x27｜1280 档 **87x27 与改前逐像素一致**（桌面零漂移）；
点下去 `body.showtime` 命中 + 坞 opacity<0.05 + `LIT 0→900`（标签转 `↺ 回到我的记忆`）
→ 右下角退出**保留 900** → 再点回记忆**清零 0**；`MemoryStore` 全程不变（不写记忆，AC-OBS-04 语义未破）；
320/390 零横向溢出、console 0 报错。
判据复跑：`ENTRY-REACH-PASS 无入口消失 visible=7/8 narrow_ok=7 gap=0 declared=0 stale=0`
（撤账后 gap 归零，且「陈旧豁免」断言未被触发 = 账确实被实测追平）；`--selftest 11/11`。
邻面 rc 全 0：`lightshow_check` `browser_check` `ux_guards` `mobile_check`(r47 的，116 目标) `a11y`
`eol_parity` `tracked_secret` `deploy_sync` `size_budget`。

## 3. 自犯一条

第一版用 `max-width:46px;overflow:hidden` 硬裁文字，**几何断言全绿**，但 320px 目检切出「✨ 一」半个字
（CJK 之间无空格可落）。⇒ 凡改可见性，回执必须含一张截图目检，不能只有数字。

## 4. 四条收尾账

1. ⚠️ **字节余量到地板**：`style.css 13,813/13,888`（余 75B）｜`app.js 14,294/14,390`（余 96B）｜
   `index.html 9,637/9,936`（余 299B）。下次改这三件须按惯例先上调预算并写理由。
2. ✅ **提交曾挂起约 22 分钟（避让他人暂存面），现已干净落库**：改完时 r47 会话已 `git add` 13 个文件，
   含 `src/css/style.css`、`memory/07-next-steps.md`、`_test/run_all_suites.py`（SUITES 71→74）。
   我的样式改动叠在它未入库的**同一文件**上，此刻提交必把它的 r47 内容卷进我这笔
   （承「禁卷入他人未入库文件并推远端」实踩教训）⇒ 不动他人暂存面、也不绕它，只把改动留在工作树等窗口。
   11:55 其 `28520f4` 落库后复测 `git diff --stat` = 8 文件 30+/14−，逐条抽验只含本轮三处改动，随即提交。
3. ⚠️ **台账分卷链被并发改写一次，已修**：我的 `43-44 r48` 指针曾被 r47 换成 `45-46 r47（故 43-44 在前）`
   ⇒ 现三段并列，注记改为「卷号按取号序而非时间序」（43-44=r48 判据｜45-46=r47 触屏｜47=r49 补回）。
   索引 4013/4096B，仅剩 83B —— 下次追加指针前须先拆卷。
4. ⚠️ `entry_reach` 两条仍未进 SUITES（现 74，接上应为 **76**）：接线口刚被 r47 动过，留下一轮与
   `mobile_check` 同处追加，避免第三次同文件互覆盖。

## 5. 公网部署

见 `part48`（并入本卷会越 4,096B 封顶，按语义拆卷）。
