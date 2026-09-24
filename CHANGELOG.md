# Changelog

本项目所有值得注意的变更都记录在此。
格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

## [1.3.0] - 2026-09-24 — 对标轮第二轮：把"赛后再做"直接落地

### Added
- 工程化七件套（本轮前一并入 1.3.0 发版）：GitHub Actions CI、`.env.example`、`SECURITY.md`、
  Issue & PR 模板、英文 README、首轮对标分析报告
- **逐字流式输出（SSE）**：`/api/chat` 认 `stream:true`；Pages Function 与 Java 侧 SSE 直通，
  前端 `onDelta` 逐字渲染；代理不支持流式时按 `content-type` 自动回落整包，不留半成品气泡
- **共情策略表 SSOT** `src/data/emotion-strategy.js`：persona / rules / 分类器提示 / 危机话术 /
  每种情绪的共情要点·离线模板·采样参数集中一处，新增情绪类别代码零改动
- **多模型 provider 适配层**：`LLM_BASE/LLM_MODEL/LLM_KEY`（`DEEPSEEK_*` 保留兼容别名）
  + 设置面板 5 家快捷预设（DeepSeek / OpenAI / 通义 / Kimi / 本地 Ollama）
- **回复朗读**：`speechSynthesis`（zh-CN）开关，零依赖；浏览器不支持即隐藏按钮
- **对话列表窗口化**：DOM 上界 60 条 + 配额制「展开较早」；模型上下文与情绪记忆不受影响
- **响应式三档**（480/768/1024）+ **星雾粒子按视口降档**（900/1200/2600）
- 新判据三条：`_test/strategy_check.py`（含 `--selftest` 防恒真）、`_test/stream_contract.py`
  （A 非流式不破 / B 含内容帧≥2 / C 前端逐字且回落不冒充）、`_test/ux_guards_check.py`（21 项逐项判定）
- CI 增两条门禁 job：`java-build` 起**无密钥** fat jar 跑词表一致性红线（此前只写在 `memory/AGENTS.md` 靠人记）、
  `browser-regression` 跑浏览器回归（runner 无 GPU，强制 ANGLE/SwiftShader）；密钥扫描带拼接生成的对照组
- `ROADMAP.md`：对标差距 → 已完成 / 计划 / **明确不做（附理由）**

### Changed
- 红线从 4 条增至 5 条（新增「策略表成对红线」），`CONTRIBUTING.md` 同步
- CloudBase 云函数按 HTTP 请求-响应模型**刻意不做流式**（注释写明属设计内回落，非缺陷）

### Fixed
- CI 密钥扫描自伤：写死在 workflow 里的对照密钥会命中自身扫描 → 改拼接生成（本机实跑抓出）
- 「展开较早记录」原先放回即被同一上限裁回（等于没展开）→ 改配额制，新消息才收回上界

## [1.2.0] - 2026-09-24 — 提交包产出

### Added
- 《应用方案》PDF（18 页，含 8 图）+ 作品简介（259 字）+ 盲审遗留处置
- `_test/screenshots_resubmit.py` 重渲染链路（临时文件 → 校验 → 原子替换）
### Fixed
- Edge 打印页脚泄露本机文件路径（`--no-pdf-header-footer` + 全页复扫）
- `render-pdf.ps1` 先毁后坏缺陷

## [1.1.0] - 2026-09-23 — 体验与部署收口

### Added
- Docker 镜像真构建真运行实测（482MB，重启持久化、镜像内密钥扫描对照）
- `deploy/jar/` fat jar 部署包（start.ps1 / start.sh，JDK≥17 探测）
- `deploy_sync_check.py`（src→deploy SHA256 三类归零守卫）、`docker_image_sim_check.py`
- 评测集 36→73 条；语音输入实测
### Changed
- 全栈体验与健壮性优化 16 处；pixel 双色判据破除相位抖动（双条件判据 + 单色对照）
### Fixed
- Dockerfile 红线缺陷：`COPY src/` 会把含 Key 的 demo-config 打进镜像 → 改 `COPY deploy/xinyu/` + `.dockerignore` 纵深防御

## [1.0.0] - 2026-09-22 — Java 全栈主线贯通（J1–J5）

### Added
- Spring Boot 3.2.5 服务端：`/api/health`、`/api/chat`（与 v1 契约 1:1）、`/api/emotion`（+ `/eval` 双端逐项一致）、`/api/memory/**`（H2 file / MySQL 可切）
- 轻量 token 鉴权过滤器（`XINYU_API_TOKEN`，留空放行）
- 两端一致性守卫 `engine_consistency_check.py`；选型决策记录落盘（五条）
### Changed
- 静态页直读 `src/` 权威源（零副本策略）；评测集服务端直读不复制进 jar

## [0.x] - 2026-09-19 ~ 09-21 — v1 原型与基线

- 五幕 3D 情绪叙事页（Three.js + GSAP，零构建）；双路情绪引擎 + 危机优先拦截；
- Cloudflare Pages Function + CloudBase 云函数双线在线；localStorage 持久化与离线降级；
- 版本控制基线建立（2026-09-21）；MIT 协议与对外 README（2026-09-24 随词表 SSOT 化补入）

> 更早明细见 `git log`；本文件自 2026-09-24 起维护。
