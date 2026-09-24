# 05 - 功能状态

> 本文件记录各功能的实现状态。
> 归档类型：增量（✅ 已实现的项移入归档）

## ✅ 已实现
- [x] 3D 情绪星雾 — Three.js 粒子星云，滚动驱动镜头；WebGL 不可用降级 CSS 渐变

## ✅ 已实现（v2 / J3-J4 变现，2026-09-22）

- [x] **J3 两端一致性常驻守卫**：`_test/engine_consistency_check.py`（+ `engine_lexicon_dump.js`，Java 侧加 `/api/emotion/lexicon` 与 `eval?detail=1`）
  - 三层判据：**A 词表结构**（含**重复项与顺序**，重复词会被重复计分）/ **B 逐条预测 73 条**（2026-09-23 由 36 扩至 73；只比汇总会漏"两条错误互相抵消"）/ **C 汇总指标**
  - **判据非恒真已证**：`--selftest` 注入分叉报出 2 问题；**端到端对照**（真改 JS 词表 → FAIL 并精确指出 `仅JS=['考上了X'] 仅Java=['考上了']`；还原 → PASS 且文件 SHA 不变）
  - 设计取舍：**不删本地词典**（离线降级是红线）→ 目标从"消灭重复"改为"让重复不可能**静默**分叉"
- [x] **J4 本地演示开启服务端持久化**：`src/js/demo-config.js` 预置 `remote: true` → **"跨设备、清缓存都不丢"成立**
  - 配套**熔断**（`memory-store.js`）：探测遇 404 / 网络失败即 `remoteDown`，本会话不再重试
  - **公网版刻意不开**：Pages/CloudBase 只有 `/api/chat`、无 `/api/memory`，默认开会给评委看 404 且打破 `public_check` 的 `CONSOLE_ERRORS: 0`
  - 常驻对照组 `_test/j4_remote_down_check.py` **J4-FUSE-PASS**（3 句对话仅 2 请求 = 上界；本地存储照常；熔断后 `isRemote()` False）
- [ ] ⏳ 仅剩：fat jar 部署到国内可达机器（摆脱 CloudBase 首访中间页）

## ✅ 已实现（对标轮第二轮 2026-09-24：把首轮"赛后再做"直接落地）

> 详见 `交付物/对标分析报告-2026-09-24-v2.md`（14 仓 gh api 实测指标）与 `03-tech-stack.md` 决策 #6–#9。

- [x] **M1 逐字流式输出（SSE）**：`/api/chat` 认 `stream:true`；Pages Function 与 Java 侧 SSE 直通，前端 `onDelta` 逐字渲染
  - **不带该字段的请求逐字不变** → AC-OBS-08 契约 1:1 未破（判据 A 守住）；代理不支持流式时按 `content-type` **自动回落整包**，不留半成品气泡
  - 实测：`_test/stream_contract.py` → A-PASS / **B-PASS（32 帧中 30 帧含 `delta.content`，拼回 51 字）** / C-PASS（在线出现「逐字流式」标签；不可达端点落回离线模板且**不冒充**）
  - ⚠️ CloudBase 云函数按 HTTP 请求-响应模型**刻意不做流式**（设计内回落，函数头注释已写明）
- [x] **M2 共情策略表 SSOT**：`src/data/emotion-strategy.js`（persona / rules / 分类器提示 / 危机话术 / 每情绪 `lead`+模板+采样参数），`chat-agent.js` 只做编排
  - 守卫 `_test/strategy_check.py`：键序一致 / 覆盖完备 / 反向不遗 / 危机话术与 `classify.sys` 自洽；`--selftest` 注入分叉报 2 问题 ⇒ 判据非恒真
- [x] **M3 多模型 provider 适配层**：`LLM_BASE/LLM_MODEL/LLM_KEY`（`DEEPSEEK_*` 兼容别名，Java 用嵌套占位符）+ 设置面板 5 家预设（DeepSeek/OpenAI/通义/Kimi/本地 Ollama）
- [x] **M4 回复朗读 TTS**：`speechSynthesis`（zh-CN）开关，零依赖；浏览器不支持即隐藏按钮；开关态持久化 `peiliao.speak.v1`（刻意**不**进对话配置，避免被 `setCfg` 牵连清历史）
- [x] **M5 对话列表窗口化**：DOM 上界 60 + 配额制「展开较早」（每次放回 20 条并临时抬高配额，新消息收回）
  - 实测证明**窗口化不截断模型上下文**：`getHistory()` 仍为既存 40 条上限、`MemoryStore` 45 条 = 发送条数
- [x] **M6 响应式三档 + 粒子按视口降档**：480/768/1024 断点；粒子 900/1200/**2600**（桌面档恒 2600，保住 `browser_check` 的 `LIT` 标定与 `pixel_dual_check` 占比判据）
- [x] **M7 CI 三条门禁**：新增 `java-build` 内**词表一致性红线机器化**（起无密钥 fat jar 跑 `engine_consistency_check.py`）+ 密钥零入库扫描（拼接生成对照组，防 workflow 自伤命中）+ 独立 `browser-regression` job（runner 无 GPU → `XINYU_BROWSER_ARGS` 强制 SwiftShader，本机已用同参数复跑 PASS）
- [x] **M8 维护可见性**：`ROADMAP.md`（已完成/计划/**明确不做+理由**）、`server/pom.xml` `0.1.0-J1`→**1.3.0**、CHANGELOG `[1.3.0]`、标签 `v1.3.0`
- [ ] **仍存差距（已登记 ROADMAP 中优先）**：`/api/emotion` 前端接线（消除两份真相最后一环）· PWA · persona 偏好记忆 · `app.js` 模块化拆分 · 真机 iOS/Android 帧率与布局未测（❌）

## 分卷目录
- **卷1** `05-feature-status.part1.md` — 05-feature-status 分卷（R199 自动拆卷）

