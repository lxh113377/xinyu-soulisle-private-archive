# 05 - 功能状态 · 卷12（r39 遗留盘点：三条「仍存差距」实为已完成，逐条取证留痕）

- [ ] **仍存差距（r39 实测逐条复核 @20:23，四条里三条已完成）**：~~`/api/emotion` 前端接线~~ ✅ 已接（`src/js/chat-agent.js:189` 后端为准＋回落本地，`emotion-remote.js` 在册）· ~~PWA~~ ✅ 已交付（`src/sw.js` + `src/manifest.webmanifest` 实测存在，离线壳判据 17 项）· ~~`app.js` 模块化拆分~~ ✅ 已四刀（`src/js/` 现 12 个模块）· **persona 偏好记忆**（未做）· **真机 iOS/Android 帧率与布局**（❌ 仍未实测）
  > 这三条是 r39 遗留盘点用命令逐条查出来的**文档落后于构建**（R240 反向形态）：三条在 r20–r28 就已落地，但本行的增量段落一直没回扫。历史留痕只加注不改写（R241），故用删除线保留原文＋补实测状态与取证时刻。

## ✅ 当前构建状态（对标轮 r20–r35，2026-09-26 回写）

> 本节是 05 的**现行事实面**；上方各轮段落属增量留痕，落后于本节处以本节为准。
> 权威数字不抄在这里：套件数由 `python _test/repo_config_check.py` 的 G4 与 README 对账，
> 版本由 G12 三源对账，成片指纹见 `交付物/提交包/提交清单与验收状态.md`。

- [x] **诚实性三态徽章**（r32）：`● 在线 AI` / `● 离线共情模板` / `网络不可用（配置为在线）`，
      任何情况下不伪装在线；判据 `emotion_wiring_check` + `settings_panel_check` S7a/S7b。
- [x] **本机开场白诚实标签**（r32）：首条开场消息标「本机开场白 · 未经大模型」，
      复算 `grep -rn "本机开场白" src/js/ deploy/xinyu/js/` 命中 >0。
- [x] **只读离线壳**（r28）：`src/sw.js` + `_test/offline_shell_check.py`（A1–A10 / R1–R9，14 项 + 13 类反例），
      公网真断网仍可演；`/api/**` 与含密钥件永不落缓存。
- [x] **可下载交付物（r37）**：首个 GitHub Release `v1.4.1` = fat jar 28,438,588B（内嵌 1.4.1、
      0 前端文件、0 密钥形态）+ 零密钥前端包 249,409B/23 文件；远端实测非草稿、2 资产。
- [x] **安全策略第二层（r38）**：`SafetyGuard` 输入侧护栏（8 类注入模式 + 4000 字截断），判定落响应头
      `X-Xinyu-Safety`、响应体仍逐字透传；判据 `safety_guard_check` 双向实测（CI 无密钥下仍验 15 项）。
- [x] **行尾与工作树字节确定性（r36）**：`.gitattributes` 钉 `* text=auto eol=lf` + 显式 binary 名单，
      108 文本文件 renormalize（内容零改动，由 `git diff --name-only` == `--ignore-cr-at-eol --name-only` 证明）；
      常驻判据 `_test/eol_parity_check.py`（E1–E4 + 8 类自证）。公网已按 LF 版重部署，
      `live_sync_check` 现走**逐字节相等**分支（`live=9288 == local=9288`），不再依赖"仅行尾差异"兜底。
- [x] **构建状态历史条目（r24–r35）**：`app.js` 四刀切分 / 演示视频代际 r34 /
      r35 受理面三条真红与新增常驻判据 ⇒ 逐字迁 `05-feature-status.part11.md`
