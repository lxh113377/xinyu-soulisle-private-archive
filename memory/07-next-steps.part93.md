# 07-next-steps.part93.md

<!-- 本卷为 07-next-steps.part89.md 的延续 -->

## ④ 07 壳补的那条 P0：重部署公网的可复算配方（**未执行，等老大点头**）

- [x] ✅ **腰斩缺陷当场发现并修**（这条差点漏掉）：远端记忆 hydrate 的 `.then(replayStars)` 会在开场跑到
      一半时把它打断 —— 而 `src/js/demo-config.js` 正是 `remote: true`（本地 fat jar 演示档），
      即**最能代表评委所见的那条链路**上，开场会被 100-300ms 内的 hydrate 回执腰斩。
      修法 = `afterOpening(fn)`：开场进行中的重建请求排队，`done` 之后统一 flush；
      用户主动清除数据仍走 `replayStars()` → `stopOpening()` 立即收尾（那是用户意图，不该等动画）。
- [x] ✅ 牙（变异体）：把 `startOpeningShow()` 那一行注释掉 ⇒ `lightshow_check` **rc=1**，
      红因点名「开场自动播放没有进入 'lit' 态」；按字节还原（sha256 前缀 `2ba761a5c20a147a` 前后相同）⇒ rc=0。
- [x] ✅ 端到端手测（jar@8123，Playwright）：两次加载均 `playing→lit(1080 颗)→done(回到真实记忆 4 颗)`、
      `showtime=False`、按钮标签全程「一键点亮」、手动点 ✨ 仍进演示态且播完不跳回、
      右下角返回保留星雾、↺ 清零、`peiliao.emotions.v1` 条数不变（演示不写记忆）、console 0 报错。

## ④ 07 壳补的那条 P0：重部署公网的可复算配方（**未执行，等老大点头**）

一手读数（r80，13:58 复算）：`python _test/live_sync_check.py` → `LIVE-SYNC-FAIL: 线上内容与权威源不一致
['js/app.js(live=15350B local=17036B)', 'js/chat-agent.js(...)', 'js/data-rights.js(...)']`，
且 CI 上「线上↔权威源逐字节新鲜度」job 在 3 个连续 push（`ee839f2`/`b79731d`/`7cecb60`）上都判 failure
⇒ 评委打开 `https://xinyu-soulisle.pages.dev` 看到的是 **r79 之前**的构建，一键点亮的默认打开与 r81 的改动都不在里面。

执行序（**前置 = 老大明确说"部署"**；这一步是对公网发布，不自行触发）：
1. `cd deploy` —— 必须 cd 进去，Functions 目录按 cwd 解析，否则 `/api/chat` 会掉成 404；
2. 全局 wrangler 已坏（workd `bin/` 空目录伪装成"平台不符"）⇒ 走**临时前缀独立安装**，不动共享全局面；
3. `npx wrangler pages deploy xinyu --project-name=xinyu-soulisle --commit-dirty=true`，
   部署日志须出现 `Uploading Functions bundle`，否则视为函数没带上；
4. 复算两件套：`python _test/live_sync_check.py` 须 `LIVE-SYNC-PASS`（逐字节等）+
   `python _test/public_check.py` 须 `PUBLIC-ONLINE-ALL-PASS` 且 `KEY_LEAK: False`；
5. 顺手在公网验一次新功能：加载后 `window.__XINYU__.opening` 应走 playing→lit→done（reduce 偏好下应直接 done）。

⚠️ 部署会把 **r79+r80+r81 三轮**一次性推上线，而 R81-01（CSP 内联样式，线上情绪强度条实际失效）**尚未修**
⇒ 先修 R81-01 再部署，比先部署更划算；两条都在待办面上（07 壳的 R81-01 行前提已成立）。
