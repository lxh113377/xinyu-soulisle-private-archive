# 07-next-steps 卷66 — r65（半开流看门狗 + 清除入口可达 + 双主人拆槽）

> 取号 `volume_alloc.py`（O_EXCL）｜全文见 `交付物/对标分析报告-2026-09-28-r65.md`

## 一、修了三条

1. **半开流（P0，接 r64）**：`fetchWithTimeout` 的熔断定时器写在 `finally { clearTimeout }` 里，而
   `await fetch()` **在响应头到达时即 resolve** ⇒ 头之后的 `res.json()`（3 处）与 `readSSE` 的
   `reader.read()` 零超时零 signal。现改整轮看门狗：首包按各腿预算（reply 15s／classify 6s），头到达
   后经 `res.arm` 交回消费方，每分片续期 `BODY_IDLE_MS` 6s ⇒ **长回答仍不受总时长限制**（r51 的刻意
   行为没破坏）。停滞两种：未吐字→AbortError→离线模板（该句照常落库点亮）；已吐部分字→保留半句加 `…`。
2. **第四幕清除入口（P1，接 r61）**：**没动 CSS**——`.act` 的 150px 净空低估了坞 open 态（实测占
   y≈323–800），而 `setDock(false)` 注释自证设计意图就是「避免坞长期遮住幕内按钮」，此前只挂点击没挂
   滚动。补 `onAct(4)` 一个分支；`#btn-export` 同行"待测"随之销账。
3. **`#chart-count` 双主人拆槽（锁红源）**：整跑 B 轮 `browser_check` 红而单跑 3/3 绿，折叠行给出差异
   （`after clear: 本机已清除…` ⟷ `还没有记录`）⇒ 条数与回执同槽，`afterClear` 一直靠「故意不调
   `Chart.render()`」把冲突压成时序运气（r56 在册：CI r54 绿 r55 红）。拆法：新增 `#chart-receipt`
   (role=status) 归 `say()`，`#chart-count` 唯一写入方回到 `Chart.render()`，`afterClear` 恢复调用；
   **两判据读侧选择器同批改指**（只改写侧＝把绿判据换成红判据）。

## 二、复算

- `fault_injection --base …:8124`（未修版＝同步前的 `deploy/xinyu/`，sha256==HEAD 已证）→ **rc=1**，
  红因 `F7 stalled_stream：兜底耗时 None`；`--base …:8123` → **rc=0**（`settled 21.4s ≤ 25s`、
  `hits=2`）；`--selftest` **14/14**。
- 遮挡：滚到第四幕后两入口 `clickable=true`、`dockOpen=false`；一次点击 `getHistory()=0`、`count()=0`。
- 拆槽：`browser_check` ×2 rc=0（条数不再靠运气）｜`data_rights` rc=0｜`storage_resilience` rc=0。
- 副本三类归零；`BUDGET-PASS total=846,624`（app.js 余量反升到 72B）。

## 三、受理面 4 连红（未闭合）

- `gh run list` → 近 4 次 run（含入场基线 `d6082c4`）**全 failure**，失败步骤=「全量回归电池」。
- 本地整跑同判红 `clean_clone`：C3 超时 + C4 新面孔 `['scroll-story.js','chat-window.js']`。
  **否证"缺件"**：`git ls-tree HEAD` 两件都在册、curl 克隆产物 **200**。候选真因在判据自己：
  `requestfailed` 丢了 `failure` 原因（良性中止与真缺件不可分）+ 托管用**单线程** `TCPServer`。
- 已做：补原因面（现印 `demo-config.js<-net::ERR_ABORTED`）+ 换 `ThreadingTCPServer` ⇒ 同一 HEAD
  **3/3 全绿**。**诚实边界**：失败不可稳定复现 ⇒ 未做单变量隔离，记「已消除候选源」非「已证明根因」；
  转绿只认推送后 CI 回执（`bash _test/push_and_watch.sh`）。

## 四、在册主张被否证一条

`server/target/*.jar` 实为 **55,882B thin jar**，`java -jar` 报 `没有主清单属性` ⇒「fat jar 两条部署路
均已实测就绪」对当前产物不成立。本轮重建 28,445,749B 且 `/api/health` 回 UP。待登记成因。

## 五、纪律

本轮**撤销三条自己的错误假设**：① `caps_blind` 不是尺的缺陷，是有意不双标；② `emotion-remote.js` 不是
同形缺陷（其 `finally` 包住 `res.json()`、4s 覆盖整轮）；③ `clean_clone` 新面孔起初被判成缺件，实测否证。
另 r51/r52 取值实测从注释迁入 `CHANGELOG.md` 腾出余量，有损两句仅存 `git log -p`，引用前回仓重测。
未闭合：CI 转绿未验｜公网重部待授权（`live_sync` 判红）｜flake 对标缺原文。
