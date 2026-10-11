# 07 - 下一步 · 卷111（r116 语音通话轮收尾推荐，2026-10-12）

> 从 07 壳迁入（壳已 14.5KB 超 R161 4096B 硬顶，属并行轮在途膨胀；本轮只落指针不往壳堆正文）。
> 本轮交付：语音通话 + 15 档机器人音色 + 语义收句 + 分句出声；判据 `_test/voice_call_check.py`
> `VOICECALL-PASS C腿=11/11 U组=10`，提交面（`git archive HEAD` 干净树）同读数复算通过。

## 收尾推荐（≤3 条，带稳定 id）

- [ ] 🟠 **[推荐:R116-01｜用户操作]** **本地 main 与远端分叉未解 ⇒ 本轮 3 个提交只在本地**：
      `git rev-list --left-right --count origin/main...HEAD` = **18 / 52**，普通 push 必被拒。
      三选一（merge 并回旧线 ／ force 覆盖需先 bundle 备份 ／ 改口径挂账）与 07 壳
      [推荐:R105-01] 是同一件事，**老大点头前不推**。判据：`python _test/ci_watch.py --sha $(git rev-parse HEAD)`。
- [ ] 🟠 **[推荐:R116-02｜用户操作]** **公网面未发布 ⇒ 三条线上判据必红**：
      `offline_shell` R9a 报 `缺=['/js/voice-call.js','/css/voice-call.css']`、`live_sync` /
      `live_sync_alt` 报 `js/voice.js(live=4798B local=11125B)`。发布（wrangler pages deploy）属对外动作，
      配方在 `memory/07-next-steps.part89.md`；发布后三条须复跑归零。
- [ ] 🟢 **[推荐:R116-03｜agent 自动]** **真麦克风手感 + 无 TTS 兜底腿**：本机只有假音频设备，
      收句常数 620ms/1.9s 需现场试；另补一条「`speechSynthesis` 缺失时通话仍完成整轮（只出字幕）」的桩腿，
      现分支有码无判据。前提：`python _test/voice_call_check.py http://127.0.0.1:8123` 复算仍 11/11。

## 本轮未闭环登记（他人资产，不代改）

- `A-project-handoff` 的 `handoff.py recycle` 在 **Windows 保留设备名**上自身崩：
  `recycle.py:182 os.path.relpath` 抛 `ValueError: path is on mount '\.
ul'`。
  本轮按 R269 例外通道把 `nul` 登记进 `.gitignore`（命中即降级 quarantine）才过噪声门；
  工具侧缺陷归该件归属轮，本轮不代改他人治理。
