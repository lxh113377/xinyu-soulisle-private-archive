# 07-next-steps.part102.md

<!-- 本卷为 07-next-steps.part101.md 的延续 -->

## ⑦ r86 —— 作品更名 MindIsle 全线执行 + 备用线改判真实在线 + 悬案破案（2026-10-01）

3. 备用线 `/api/chat` 404 与三项目共用 CloudBase env（需控制台动作 + 三方同意）。
4. ~~交付面静默删除的肇事者仍未找到~~ → **✅ 破案（2026-10-01 老大原话）**：元凶是**老大本人**——
   曾有文件被放在**工作区之外**，老大看到就删了。不是 bug，不是并行会话互删；闸保留（防真丢失），
   并立规：**产物一律落工作区内，不落 %TEMP%/家目录**（已写进全局记忆）。

## ⑥ r85 续补（同一夜的收尾，提交 `7ff9139` 之后）

- **受理面三连绿**：`ci_watch` 对 `7ff9139`、`8e6f72e`（报告定稿）、`0bb9f30`（同族③修复）均
  **`CI-WATCH-GREEN`（run 全 success）**。8e6f72e 与 0bb9f30 首取时 300 s 超时 ⇒ 记 UNVERIFIED 不当通过，
  重跑判据才取到绿 —— 三态口径在受理面上又一次照做。本卷这笔收尾提交自身的 CI 回执留给下一会话开场取
  （两段式收口的惯例，不为取回执无限加提交）。
- **同族第三例当场修掉**（不再绕）：`deliverable_inventory_check` 目录-token 假缺失 ⇒ note 跳过 +
  指丢照旧红，Ⓟ/Ⓠ 反向腿，自证 14→**16** 腿；清单文案改回完整路径实测 PASS rc=0。见 §②-③。

## ⑦ r86 —— 作品更名 MindIsle 全线执行 + 备用线改判真实在线 + 悬案破案（2026-10-01）

- **品牌改版（老大拍板"改"）**：SoulIsle → **MindIsle**。改动面：`src/index.html` 品牌位 + manifest +
  css 注释 → deploy 同步（`DEPLOY-SYNC-PASS`）→ **9 张提交包截图按当前 UI 全部重截**
  （`_test/_reshoot_r86.py`，先落 `_shots/r86/` 逐张目检；旧 s07/s02 的构图随旧版探针 UI 一起消失，
  图 2 图注同步重写——r32 只回扫 s01/s08，这处漏了三轮）→ PDF 重渲染（20 页/9 图，双门过）→
  视频重录（221.4s，RECORD-PASS 8 幕）→ pages.dev 重发（`LIVE-SYNC-PASS` + `PUBLIC-ONLINE-ALL-PASS`）。
  **不动的技术标识**：域名 `xinyu-soulisle.pages.dev`、Java 包名 `com.xinyu.soulisle`、jar 名。
  SoulIsle 提交版留档 `_参考资料-非提交/已提交留档-SoulIsle-20260930/`。
- **备用线"修"（老大拍板）**：`service.tcloudbaseapp.com` 实测 TLS 证书不匹配（浏览器握手即死）⇒
  CloudBase 控制台路由这条路本机修不了；改道——前端跨域调 pages.dev 函数，`chat.js` 加
  **CORS 白名单**（自家 4 来源，不开 `*`，密钥仍只在 CF env）+ stub 换指向。
  `backup_online_check` 四腿全过（真浏览器过"确定访问"验证页 → 在线标签）⇒ 电池 107→**108 套件**。
- **悬案破案（老大口径）**：静默删除 = 老大清理**工作区外**的文件 ⇒ 立规"产物一律落工作区内"；
  in-仓闸保留。改名提交按钩子官方通道 `XINYU_SKIP_DELIV_HOOK=1`（台账 .git/xinyu-hook-skip.log）。
- **demo_video_pipeline 两修**：requestSubmit（同截图脚本的视口外点击坑）；ffmpeg/ffprobe 不在机 ⇒
  imageio-ffmpeg 解析 + `_media_seconds`（ffmpeg stderr Duration 行），不再依赖未登记二进制。
- **受理面回执**：电池 r86 定版读数 `101/105`（3 红：2 项为 HEAD 未更新暂态已随提交消失、
  eol_parity 的 pptx 裸 CRLF 由 `.gitattributes` 补 `*.pptx/*.docx/*.mov binary` 修掉 ⇒ `EOL-PARITY-PASS`）；
  CI：`b363e6c` **RED**（eol_parity，即被修那两条）⇒ `da033ad` **GREEN**（4/4 job success）——
  红被自己的下一笔修掉，时序回执以此为准。改名提交按钩子官方通道跳过在位闸一次（台账 .git/xinyu-hook-skip.log）。
