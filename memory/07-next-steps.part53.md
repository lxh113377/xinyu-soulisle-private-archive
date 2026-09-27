# 07 分卷 53 — 对标轮 r50 / r51 / r52 条目全文（自 07 主壳迁出）

> 迁卷动因：07 主壳逼近 R161 的 4,096 B 上限而 r52 需加一行。
> 按既有做法把已完成条目的**长描述**迁进本卷，主壳留一行短索引（迁移不是删除）。
> 这三条的更完整证据分别在 `part50/51`（r50）、`part52`（r51）、本卷 §r52 与
> `交付物/对标分析报告-2026-09-27-r50/-r51/-r52.md`。

## r50 协作治理与健康度面（已完成，→ 电池 75）

实测**漏洞告警整条关着**：`dependabot.yml` 自 r21 在册、也确实开过 4 个 PR，但
`gh api .../dependabot/alerts` 回 HTTP 403「alerts are disabled for this repository」
⇒ 升级在跑、告警关着，出 CVE 连平台都不通知；对任何"文件在不在"式检查完全隐形。
已开启并读回 `404 → HTTP 204`、0 告警。peers 有行为回执的只 2/16。判据：`peer_community_probe.py`
（A 声明 / B 平台 / C 行为三通道，各自独立取数）。

## r51 故障注入与错误可见性面（已完成，→ 电池 78）

把上游真打挂（500／200+非 JSON／断连／黑洞挂起／恢复）再读界面。两条实测缺陷：
① **徽章在故障下说谎**：气泡写「大模型暂不可用」而 `#mode-badge` 仍写「● 在线 AI」，
   同屏自相矛盾且撞红线"禁伪装在线" ⇒ `ChatAgent.llmBad()` + `refreshBadge()` 同帧翻面。
② **挂起型空转 60.6 s** ⇒ 超时降到 15 s，复测 30.2 s。
peers 监控集成真值 **2/16**（首版把 `highlight.js` 当监控厂商而虚报 5/16，出报告前作废重测）。
夹具教训两条已在 `part52` 与 `_test/fault_injection_check.py` 的注释里逐字在册，此处不重抄。

## r52 长期记忆召回与上下文管理面（已完成，→ 电池 83）

十三份对标把「记忆系统」记成 **✅ localStorage + 服务端双表**（存在性），从没量过
"写进去的记忆有没有读回来喂给模型"。一手 grep：`chat-agent.js:137-151` 只拼策略表 +
`history.slice(-10)`；`memory-store.js:142` 导出面**零召回项** ⇒ 模型侧对用户历史一无所知，
"跨设备记住你"当时只成立在星图展示层。

落地：`MemoryStore.recall()/count()`（次数/跨度/高频情绪三量，**不含用户原话**）→ `SYSTEM(emo)`
末尾注入 → `respond()` 返回 `memory`（只在 `mode==model` 时非零）→ 气泡尾注「已带入 N 条记忆」。
新判据三件：`memory_recall_check.py`（拦 `/api/chat` 读 `post_data`；R4 反向腿=清库后必须消失）、
`peer_memory_probe.py`（16 仓三通道，引用边只认正向回执）、`readme_troubleshooting_check.py`
（README ⇄ 代码状态标签双向对账）。

同轮收 r51 两账：① README 使用者排障段（首跑即被抓出产品里不存在的 `● 已离线`，
并逼出未文档化的第四态 `● 网络不可用（配置为在线）`）；② 30.2 s 归因——黑洞原先按 **accept 次数**
记 hit，keep-alive 下两请求共用连接 ⇒ 记成 1 次造成"无法归因"假象；改数 `POST` 次数 + 页面内
fetch 打时刻 ⇒ 看见 2 条腿、间隔 15.0 s（classify 与 reply 各吃满一个熔断、串行相加）。
分类腿单独 6 s ⇒ 整轮 **30.2 → 21.3 s**，`HANG_BUDGET_S` 35 → 25，新增 F4b「未归因即判红」。

✅ **本轮末已切 v1.6.0**：r51+r52 两个 feat 把 feats 推到 6/上限 5 ⇒ 按先例切版归零
（同 v1.5.0 当时 feats=11/上限 5），不抬上限也不改前缀绕计数。
复算 `release_governance_check` → `feats=0（上限 5 余量 5）`。
⚠️ 仍欠 `release_cut.py`（r45 遗留：把 CHANGELOG 版本段 / pom version / ROADMAP 版本行 / 注解 tag 自动化）。
⚠️ v1.6.0 的 fat jar 未在本轮重构建（8123 进程持有 target/，产物 gitignored 可再生；Java 源码零改动）。
其余 P1：后端分类腿（`/api/emotion` + `LlmProxy` 60 s）的挂起注入不在本轮取数面内；
上下文滚动摘要须先量"10 条之外丢多少"再做；真机复跑故障注入与召回。
