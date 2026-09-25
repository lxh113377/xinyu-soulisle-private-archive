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
- 测试专用文件清单（r23 填实，此前长期是 init 模板占位符 ⇒ 判据 `repo_config_check.py` G8 现在会盯这张表）：
  | 文件 | 条数 | 用途（谁在裁决时读它） | 来源 / provenance | 冻结状态 |
  |---|---|---|---|---|
  | `_test/emotion-eval-dataset.json` | **73 条** | `node _test/emotion_eval.js`（JS 侧）、`GET /api/emotion/eval`（Java 侧直读，决策 #5 不复制进 jar）、`engine_consistency_check.py` 双端逐条对账 | 团队自建：按 7 类情绪（joy/sadness/anger/fear/calm/love/crisis）人工撰写，**不来自任何模型输出或线上对话日志**；2026-09-23 由 36 条扩至 73 条（扩充部分同样人工写，含 6 条危机样本） | 结构冻结：新增只允许"人工写 + 双端复跑全绿"，禁止用 LLM 批量生成 |
  | `_test/vendor-manifest.json` | 3 条 | `vendor_freshness_check.py` 的完整性/版本对账声明源 | 本项目自维护（r21 建），非评测数据，列此仅为明确它**不属于**裁决用评测集 | 随 vendor 变更同步（`--refresh` 后人工核对 diff） |
- 红线：训练/生产数据禁止写入测试专用文件；新增评测数据先登记来源（provenance）
  - **为什么本项目特别要盯这条**：情绪评测集的准确率会被写进《应用方案》PDF 与答辩材料（当前 98.6% / 危机 6-6），
    一旦把"模型自己生成的样本"或"用户真实对话"混进测试集，这个数字就从"可复现的能力度量"退化成"自证循环"，
    而且双端对账（JS ↔ Java）会同时被污染 —— 两边都错也照样"全等"。
  - 真实对话落库走的是**另一张表**（`chat_message` / `emotion_record`，服务端持久化），与本清单物理分离，
    禁止把库里的用户文本直接回填评测集（既是污染，也是 PII 风险，见 iCAN 待办「③ PII 挂账」同源问题）。
- 机器责任：`python _test/repo_config_check.py` 的 **G8** 断言 ①本章节非占位符 ②清单里的文件真实存在
  ③`声称条数 == 文件实际 items 数`（改条数不改这里即红）。`--selftest` 用三类反例自证（抹登记行 / 改小条数 / 删章节）

## 分卷目录
- **卷1** `06-constraints.part1.md` — 已完成条目归档（R224 主壳自愈）
