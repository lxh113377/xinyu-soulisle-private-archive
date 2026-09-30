# 07-next-steps 分卷 · part101 —— r85 全记录（2026-09-30，提交当日）

> 壳（`07-next-steps.md`）只有 4058/4096 B ⇒ 长段落一律落这儿。入场基线 `a5b6552`（r84 收口），出场 `f1d5a0a` + 本卷这一笔。

## ① 本轮四件事（按做的顺序）

| # | 事 | 结果 | 一手回执 |
|---|---|---|---|
| 1 | 公网重部署（R82-02） | ✅ 转绿 | deployment `a07fee7f`（回滚锚点 `0c272d75`）；`LIVE-SYNC-PASS`（index 9366==9366、21 项逐字节等）+ `PUBLIC-ONLINE-ALL-PASS`（`CONSOLE_ERRORS: 0`，旧版内联样式触发的 CSP 报错已清） |
| 2 | CI「浏览器回归」作业判红口径对齐 | ✅ | `.github/workflows/ci.yml` 只对电池 `rc=2`（ENV-UNVERIFIED）放行并 `::notice` 喊名单；`rc=1` 与其它非零照旧判红。**验牙**：stub rc=0/1/2/3 ⇒ 步骤退出码 0/1/0/3 |
| 3 | 提交定版包入库 + 品牌分叉隔离 | ✅ | `交付物/心屿SoulIsle-作品提交-20260930.zip`（24.77 MB）内 PDF/MP4 与仓内**逐字节相等**（`7ed80c3d…` / `04a7f7bf…`）；两份 `心屿MindIsle_参赛方案`（pdf/pptx）**移出** `提交包/` → `_参考资料-非提交/MindIsle-品牌分叉-待裁决/`（未删、未 add） |
| 4 | `hook_wiring` 的「解释器吃哪种路径形态」坑 | ✅ 修完 | 见 §② |

## ② hook_wiring 那条红：同族第四例（本轮最该记的）

- **现场**：`python _test/run_all_suites.py --exclude-llm`（`run_logged` 包装，尾行 `BATTERY_R85_FINAL_RC=1`）
  `BATTERY: 102/104 rc=1 RED(判红，必须修): hook_wiring,hook_wiring_selftest`。
- **红因原文**：`W1 钩子源解析不过（sh -n rc=127）：/bin/bash: C:Users37533Desktopworkspace项目陪聊_testhookspre-commit: No such file or directory`。
- **根因（现读，不是推断）**：`shutil.which("sh")` = **None** ⇒ 回退到 `which("bash")` =
  `C:\Windows\system32\bash.EXE`（**WSL 启动器**）⇒ 它不吃 `C:\...`（反斜杠被当转义吃掉）⇒ rc=127。
  同一根因把 selftest ⑪（端到端删件须 rc=1）与 ⑫（复原须 0/2）一起带红 ⇒ **2/12 未过**。
- **关键辨别**：W2 当场显示「副本 == 源 sha=b0403aeb2a60」⇒ **钩子没坏，坏的是喂路径的形态**。
  05:13 那次电池（同一份代码）`HOOK-WIRING-PASS` ⇒ 是**环境在两次之间漂了**，不是本轮提交引入的红。
- **处置（不放宽判据）**：`sh_exe()` 优先 Git 自带 bash（`C:\Program Files\Git\usr\bin\bash.exe`，本机在位、
  吃 Windows 路径）；只剩 WSL 启动器时由 `path_for_sh()` 转 `/mnt/<盘符>/...`。**解析不过仍旧判红**。
- **自证加钉 3 腿**（13→15）：⑬ WSL 启动器必收 `/mnt/c/...`；⑭ Git bash 收原样不得多此一举；
  ⑮ `bash` 裸串不得误命中 ⇒ `HOOK-WIRING-SELFTEST-PASS: 15 腿全过`。
- **同族台账**（四条一起看，判据自己被环境形态绊倒再把伤报成被检对象的错）：
  ① r83 CSP 闸自己对 CSP 全盲；② r84 `ci_watch` 分不清「取数失败」与「没有 run」且丢 stderr；
  ③ 本轮 `deliverable_inventory_check` 把清单里写的**目录路径**当成「声明要交的文件」判假缺失
  —— **r85 续已当场修掉，不再绕**：在位目录记 note 跳过（不是未验，否则一个文档指针会把整条判据压成 rc=2）、
  指丢的路径照旧红；补 Ⓟ/Ⓠ 两条反向腿（端到端反向腿 14→**16**），`--selftest` PASS、真面 `PASS rc=0`
  （清单文案已改回带 `交付物/` 前缀的完整路径并实测不再假红）；④ 本条。
  ⇒ 07 壳「同族坑收口」那一行**继续挂着**，下轮优先做 ③（判据侧）而不是继续绕。

## ③ 受理面（本轮最硬的一条）

- `python _test/ci_watch.py --sha f1d5a0a --no-run-grace 240` → **`CI-WATCH-GREEN`（1 条 run 全 success）**。
- 逐 job（run **36703817161**）：Java 服务端构建 + 词表一致性红线 / 同步守卫 + 情绪评测·策略表门禁 + 密钥扫描 /
  线上↔权威源逐字节新鲜度 / 浏览器回归 —— **4/4 success**。
- 对照 r84 §5b 那句「main 分支最近 5 次 run conclusion 全 failure、任何本地正常提交都变不了绿」：
  **该断言已被本轮否证**（公网刷新 + rc=2 分档两件事一起做掉）。⇒ 又是一条「稳定/永远」类断言被下一轮打脸，
  与 r84 否证 r83「三次稳定」同形 —— **这类词必须自带样本数与失效条件**。

## ④ 定版电池读数（本轮内容全部在工作树里时取）

- 门面：`BATTERY: 102/104 rc=1 RED(判红，必须修): hook_wiring,hook_wiring_selftest`（修完前）
  ｜日志尾行 `BATTERY_R85_FINAL_RC=1`（采信尾行，不看调度层）
- `LEDGER-SKIP: 实跑 104/107 ⇒ 子集读数不得覆盖全量台账`；耗时 top5
  `mobile=124.5 / fault_injection=63.4 / pixel_dual=58.8 / live_sync=40.6 / public_check=40.5`，合计 **776 s**
- 对照 r84 收口时 `101/104 RED=ci_status,public_check,live_sync`：**那三条已全绿**，红的位置换了 ⇒
  「红的总数相近」≠「同一批红」，台账必须记红因不记条数。

## ⑤ 仍未闭合（不折叠）

1. ~~iCAN 官网提交~~ → **✅ 闭环（2026-10-01 老大确认"作品已经提交了"）**，登记见 07 壳 P0 首行。
2. **品牌终裁**：MindIsle 件已隔离不进提交面，但「要不要改品牌」仍待老大一句话（改 ⇒ 6 处同步，见该目录 README）。
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
