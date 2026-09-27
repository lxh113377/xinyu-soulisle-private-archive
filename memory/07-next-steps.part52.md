# 卷52 — r51 故障注入与错误可见性（2026-09-27 第九轮）

> 换卷理由：首次从"把上游打挂"的方向量降级，前十一轮只把降级当功能量。
> 报告全文：`交付物/对标分析报告-2026-09-27-r51.md`

## 已完成

- ✅ **新常驻判据 `_test/fault_injection_check.py`**（+ `--selftest` 9 例）：Playwright 拦 `/api/chat`，
  注入 HTTP500／200-非JSON／断连／**黑洞挂起**／恢复 五类。两条硬自证：`hit_count` 全非零（证注入
  真打到通道，否则"没报错"可能只是"没打到"）；`hit_count==0` 记 **INVALID 不记 PASS**。
- ✅ **修「降级了却说没降级」**：四类故障下气泡写"大模型暂不可用"而徽章仍写「● 在线 AI」
  —— 界面两个真相源。改：`chat-agent.js` 外提 `llmBad()`（mode=="model" 复位、catch 置位），
  `app.js` 每轮 `refreshBadge()` 同帧翻面为「● 大模型暂不可用（已降级本机模板）」。
- ✅ **上游超时 60 s → 15 s**（`LLM_TIMEOUT_MS`）：挂起型兜底 60.6 s → **30.2 s**（预算 35 s）。
- ✅ **对标探针 `_test/peer_fault_probe.py`**（+ `--selftest` 6 例）：只取结构与声明证据；
  `ceiling_note` 写死"故障注入无法对他人站点实施 ⇒ 不得写成报错体验对比结论"。
  真值：**error-monitoring 集成 2/16 ｜ README 使用者排障段 1/16 ｜ self 0+无**。
- ✅ 电池 75→**78** 登记（`fault_injection`／`_selftest`／`fault_peer_selftest`）；README 计数由
  `repo_config_check` G4 等值对账，G10 恒等式 75 实跑 + 3 豁免 == 78。
- ✅ `app.js` 体积预算 14,390→15,490（注释写明增量来源，非"改判据求绿"）。

## 本轮我自己踩的（八条，四条是度量学）

1. **`highlight` 歧义名致虚报 5/16**（真值 2/16）：裸子串通道把 `highlight.js`（语法高亮库）当成
   监控厂商 Highlight.io，误判 SillyTavern／Loyal-Elephie／leemo 三家。**虚高方向恰好利于我的叙事**
   （显得"大家都做了、我只差一点"）。修法：`AMBIGUOUS={"highlight"}` 只准走 `@highlight-run/*`
   精确通道 + 反例④双向；**未修前的 5/16 一律作废**。同 r46「宽匹配把 notice.html 当归属件」一族。
2. **先引用后创建**：CHANGELOG 写了 `peer_fault_probe.py` 时该文件还不存在（违反「文档写了≠磁盘有」）。
3. `blobs.values()[:40]` → TypeError（dict view 不可切片）。
4. `sentry.client.config.ts`（Next.js 主流命名）首版不认 ⇒ `MON_FILE` 扩三种形状。
5. **Playwright 回调 arity 陷阱**：`def handler(route, m=mode, ...)` 的 `m` 被 route 对象冲掉 ⇒
   五模式走同一分支，读数干净但全是假的。改工厂闭包 `make(m, hs)`，只接一个位置参数。
6. 同步 handler 里 `time.sleep(400)` **阻塞 dispatch loop** ⇒ 返回 None，F4 根本没测到。改用真实
   socket `accept` 后不响应，让浏览器侧自己超时。
7. 探针用不存在的 `#chat-send` ⇒ "没报错"是"没点到"的假阴性。
8. **heredoc 吞引号（同族第 12 次复发）** —— 机器化路径仍挂在 `part36`，**未闭环**。

## P1（下一轮）

- **分相计时归因 F4 剩余 ~15 s**：15 s 是 `LLM_TIMEOUT_MS`，另 ~15 s 来源不明。
  **未归因前不得写成"还有 2 倍优化空间"**。
- heredoc/字面量引号族接进 `repo_config_check` AST 面（与 G9 同趟遍历，不新增判据号）。
- 遗留：`release_cut.py`(r45)／JVM 依赖许可(r46)／键盘+视口几何(r47)／alerts 回读(r50)。

## P2（需老大在场或真机）

- README 增"面向使用者"的排障段（peers 亦仅 1/16，属共同空白，做=差异化）。
- 真机（iOS Safari／Android Chrome）复跑故障注入。
- **明确不做**：引入 Sentry/Datadog 等第三方错误监控 —— 与"情绪与对话只留本机/本演示实例服务端"的
  披露承诺冲突。**这一项是对标主动排除项，不是落后项。**
