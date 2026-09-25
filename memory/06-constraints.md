# 06 - 已知约束

> 本文件记录已知问题、技术债和约束。
> 归档类型：增量（已解决的问题移入归档）

## 已知 Bug
<!-- 格式：- [BUG] 描述 — 影响范围 | 状态：未修复/修复中 -->
<!-- 解决后标记 - [x]，归档时自动移入 archive -->

## 技术债
<!-- 格式：- [DEBT] 描述 — 建议的还债方式 -->
<!-- 还清后标记 - [x] -->

- [DEBT] **`src/vendor/three.min.js` = r128（2021 年），上游已 r186（2026-09-24 实测）— 落后 58 个大版本**
  — 还债方式：iCAN 截止后独立阶段升级，**必须带视觉基线对照**（r152 起默认色彩管理改写、`Geometry` 移除、
  自定义 `ShaderMaterial` uniform 约定变更 ⇒ 星雾"暗星 0.05/点亮 0.26"与 `pixel_dual_check` 的双色像素级标定需整体重定）。
  截止前不动的理由 = 素材冻结期重做可视化不划算，不是拖延。
  **本条机器可见**：`python _test/vendor_freshness_check.py --check-upstream --strict`（现返回 rc=1，即"落后"不再可隐藏）。
- [DEBT] **`src/vendor/` 三个前端第三方库无包管理器可托管**（r21 更正本条范围，原写"零构建=挂不上 dependabot"是**错误归因**）
  — 已用 `_test/vendor-manifest.json`（版本 + sha256 唯一声明源）+ `vendor_freshness_check.py`（V1 完整性 /
  V2 从文件内容解析版本对账 / V3 新库漏登记即红）承担同等职责。**代价**：这三个库的上游发新版不会自动通知，须人工跑 `--check-upstream`。
  - ⚠️ **更正注（r21，2026-09-25）**：上一轮把"npm 生态挂不上 dependabot"扩大成"整个项目挂不上"，据此放弃了本可自动化的两半。
    实测更正：**Maven（`server/pom.xml`）与 GitHub Actions（`.github/workflows`）两个 ecosystem 与 npm 无关，可以直接挂**
    ⇒ 已加 `.github/dependabot.yml`（maven@/server + github-actions@/，每周二 08:00 Asia/Shanghai，PR 上限 3/2）。
    本条剩余真实盲区只有 `src/vendor/` 那三个手工 vendored 的 JS 库，由上面的 manifest 守卫承担。
- [DEBT] `src/js/app.js` 469 行单体编排（对话/星图/曲线/朗读/设置混在一个 IIFE）— 还债方式：voice/chart/window/编排 四模块纯切分，不改行为（排截止后）。
- [DEBT] `tick()` 每帧遍历全部粒子做 CPU 侧着色（桌面档 2600 次/帧）；**真机帧率 ❌未实测** → 不进任何"性能领先"结论。
- [DEBT] 情绪引擎仍是**两份实现**（JS 离线降级用 + Java 后端权威）。本轮已把前端接到后端，但**词表仍须两端同步改**
  （红线不变，判据 `engine_consistency_check.py`）；`emotion_wiring_check.py` W6 另加一条"同句双端词典结论必须相同"。
  彻底消除两份 = 需要"JS 侧只保留极简危机词表"的重构，未排期。

- [x] [DEBT] 情绪引擎「两份真相」（`src/js/emotion-engine.js` + `server/.../EmotionLexicon.java`）—— 已由 J3 两端一致性常驻守卫 `_test/engine_consistency_check.py` 消除静默分叉风险（三层判据 + 端到端对照）；本地词典保留为离线降级（红线，不删）
- [ ] [DEBT] fat jar 尚未部署到国内可达机器（当前依赖 CloudBase 中间页）—— 见 `07-next-steps.md` P0 ③

## 红线（不能改）
<!-- 绝对不能修改的模块/约定 -->
- **密钥红线**：密钥零落前端、零入库；`src/js/demo-config.js`（含 Key）已 ignore，`deploy/xinyu/js/demo-config.js`（零密钥代理版）禁被 src 版覆盖
- **同步红线**：改 `src/` 必须同步 `deploy/xinyu/` 并做 SHA256 双向比对（MISSING/DIFF/EXTRA 三类归零）
- **静态页托管红线**：服务端直读 `src/`（`static-locations=file:${XINYU_WEB_ROOT:./src/}`），禁把前端复制进 `resources/static/`（第三处副本）
- **评测集红线**：`/api/emotion/eval` 直读 `_test/emotion-eval-dataset.json`，禁复制进 jar
- **词表一致性红线**：改 JS/Java 任一端词表须两端同步 + 跑 `_test/engine_consistency_check.py`

## 性能/兼容性约束
<!-- 性能要求、浏览器兼容性、系统兼容性等 -->
- 

## 环境隔离（R196，init 必填）
<!-- 声明当前运行环境模式；dev 禁连 prod 库/密钥；production 操作前必须有近期备份 -->
- env_mode: development（枚举：development / staging / production）
- 红线：dev/staging 禁止连接 production 数据库与 API key
- production 操作前检查：近期备份存在（archive/ 或 DR 快照 ≤7 天）+ 密钥不复用
- 保护文件 .env.prod / .env.production 禁止入库（.gitignore 已含规则）

## 评测集隔离（R196）
<!-- 标注测试专用文件，禁止把训练数据写入测试集；新增评测数据先登记 provenance -->
- 测试专用文件清单：（如 eval/testset_provenance.json / blindset / frozen）
- 红线：训练/生产数据禁止写入测试专用文件；新增评测数据先登记来源（provenance）

## 分卷目录
- **卷1** `06-constraints.part1.md` — 已完成条目归档（R224 主壳自愈）
