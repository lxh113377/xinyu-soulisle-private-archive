# 任务卡 · 表情识别诊断与优化方案（face-diag 轮）

> 建卡时刻：动手前（早于首个写盘），符合致命纪律 #15。G8 数据流假设块 = GM `memory/2026-10-12.part28.md`
> （`dag_precheck --require-mark face-diag` ⇒ `[GATE:dag-pass]`，命中 n=28）。详细方案 = `memory/11-face-accuracy.md` 四卷。

## 本轮目标

诊断老大真人实测的三症状（只能识别平静/低落/愉悦/厌恶；愤怒等识别不到；误判较多；必须明显表情才判微笑），
输出三维根因 + 短中长期优化 + 执行方案 + 验证方案 + 质量标准 + 风险预案六件套。
**本轮零 src/ 改动**（纯诊断+方案文档），执行轮按 11 号文件 §四 时间表推进。

## 验收判据（二元，附复算命令）

1. 根因有实测证据：13 条症状向量读数表（node `FaceEngine.read()`）落在 `memory/2026-10-12-face-diag.md`，
   任一行可复算：`node <脚本>`；低强度沉 calm 结论与主壳表三行 MISS 逐字对应。
2. 六件套齐：三维根因（part1）/三层建议（part2）/执行方案（part3）/验证+标准+风险（part4）各卷 ≤4096B 且指针从主壳可达。
3. 挂账完整：07-next-steps P0 新增条目指向 11 号文件；10-core-capabilities 轨迹表加行；
   05-feature-status 指针段 + CHANGELOG 条目在案。
4. 每轮复算入口仍绿：`python _test/core_capability_baseline_check.py` N2 表情 31/31 不回退（N1 FAIL = 他人 +20 条假红，已核实 r123 记载）。

## 备选方案与取舍（≥2）

- A. 改"诊断+方案"为"直接动 rules 代码"——弃：老大点名的交付是六件套文档；直接改码没有标注数据支撑会窄峰拟合（r103 教训）。
- B. 换混合派/模型派（face-api.js 二路融合）——弃：老大 r124 授权规则派；混合派触发成本（F1 vendor 四件套 + 隐私论证 + 体积预算）写进 part4 R6 预案。
- C. 只写文档不建尺子——弃：D4（真实流无尺子）是根因之一 ⇒ S4 真照片 AU 批跑尺列为执行第一优先，否则后续优化无法验证。
- D. 选定：先建"无摄像头真照片尺"再造数据复标权重，与老大授权的规则派路线一致。

## to-do

① G8 锚点+dag ② 11 号四卷 ③ 任务卡+轮次日志 ④ 07/10/05/CHANGELOG 挂账 ⑤ core_capability 复算 ⑥ volume+noise ⑦ commit（显式 pathspec）⑧ footer+gate

## checkpoint / 回滚预案

本仓 49 个在途 M（并行会话）⇒ 只碰本文档族，`git add` 逐个显式路径，禁 `-A`；Edit 锚点未命中即停手重读禁猜；
回滚锚 = 首个提交前 HEAD `fcb44039`；本轮零删除、产物只增不改名。
