# 07 分卷 · 卷89 — r80（2026-09-29 · 一键点亮默认打开 + 团队名单署进 PDF）

> 本轮由老大的三项指令触发：① 默认把一键点亮打开 ② 盘点已完成/待处理并给提交前清单 ③ 给出五人名单。
> 入场基线 `3f4eca5`；**同 worktree 并存两个他方在途轮次**：r70（电池 99→101 套件 + 资源普查 + 耗时台账）
> 与 r81（CSP 内联样式判据 `inline_style_check.py`，正在写 `ci.yml`/`CHANGELOG.md`/07 壳）。

## ① 一键点亮默认打开（裁决：每次加载都自动播放）

- [x] ✅ **开场自动播放落地**：`src/js/app.js` 新增 4.6 节 `startOpeningShow()`，挂在 boot 末
      `replayStars()` 之后 ⇒ 每次加载自动播一次「清屏→六色由内向外逐颗点亮」。
      与手动演示态**两处刻意差异**（其余逐字不变）：
      ① **不加 `body.showtime`** —— 叙事与对话坞在开场那几秒仍可点（手动路径的"全部 UI 让位"是给人
      专心看星用的，开场若也遮 UI，评委一进来就落在一个不可交互的页面上）；
      ② **播完自动回到「我的记忆」**（`duration + 1500ms` 后 `replayStars()`），不留在清屏画面。
      手动点击那条路（AC-OBS-04 的 ①-⑦：清屏、不自动跳回、右下角保留星雾、↺ 才清空）行为未动。
- [x] ✅ **同步点而非固定 sleep**：`window.__XINYU__.opening` 四态 `idle→playing→lit→done`。
      动因（一手）：既有 4 个套件在 reload 后 700-1500ms 就取星图像素/读数，而开场要 3.74s 播 + 1.5s 停留
      ⇒ 不改等待方式，它们采到的是**演示星**，判据会在"代码没错"的情况下变红。
      接入面：`lightshow_check.py`（新判据⑧）、`browser_check.py`、`j4_memory_check.py`、
      `storage_resilience_check.py`；`pixel_dual_check.py` 跑在**假时钟**下（`page.clock.install`），
      定时器不会自己走完 ⇒ 改用 `page.clock.run_for(7000)` 把钟点拨过整段开场并当场断言 `done`。
