# 11-face-accuracy · part3 — 执行方案（改进项 × 步骤 / 预期 / 资源 / 验收 / 时间）

> 时间锚（假设值，待老大确认）：复赛 ≈10 月下旬 ⇒ 短期 T+7；决赛 ≈11 月 ⇒ 中期 T+28。
> 每项验收都是机器判据（跑得出 rc），禁"看起来好了"。资源单位：轮（一个 agent 会话）。

## S1 低强度动态分母（算法，修 A1+A2）

- **步骤**：① `src/js/face-engine.js scores()`：pos 只累加 `bs[k]≥cue.min` 的正权项；
  ② `face-smile-rules.js` 加 `dynDenom: true` 开关（回滚=置 false，旧路径不动）；
  ③ 症状 13 向量 + face_discrim 全量回归；④ 同步 deploy/xinyu + SHA256 双向比对。
- **预期**：轻微笑 .22 → joy ~0.8（主壳表第 3 行翻 ✓）；抿嘴笑 .40 强度 0.396 → ~0.9。
- **资源**：1 轮。**验收**：face_discrim 全 PASS + 新增低强度用例（0.12~0.45 五档×六类）全 ✓；
  core_capability N2 只升（31/31 起步）。**时间**：T+3 天。

## S2 弱信号档输出（界面，修 A4 体感）

- **步骤**：`read()` 加 `weak` 标记（top∈[0.08,0.26) 且不 confident）；app.js paintHud/faceChipHtml
  出「轻微 X（读数仅供参考）」三态文案。
- **预期**：轻表情有可见反馈；"必须明显表情"体感消除。
- **资源**：1 轮。**验收**：browser_check 全 PASS；三态文案截图留档。**时间**：T+5 天。

## S3 anger 复标 + 专注区分（算法，修 A5/A1）

- **步骤**：anger 加 browInnerUp −0.5（第二 AU 分焦虑/专注与愤怒）；用 S4 首批 20 张照扫
  browDown∈[0.15,0.35] 区间，中点取值。
- **预期**：轻紧锁眉 .20 → anger ✓；专注（browDown .3 + innerUp .3）→ calm ✓。
- **资源**：1 轮（依赖 S4 数据）。**验收**：12 条 anger 低强度/专注对照全 ✓；误报不高于 r103 水位。
  **时间**：T+10 天。

## S4 真照片 AU 批跑尺（工程地基，修 D4/E1）

- **步骤**：① 建 `_test/face_au_replay_check.py`：读 `_test/face-au/*.json`（52 维向量+标注+质量标签）
  → node 复算 `FaceEngine.read()` → 分场景 top-1 统计；② face-harness 在 Chrome 跑首批 20 张标注照
  导出 AU JSON（**只存参数不存图**，守隐私）；③ 接入电池 SUITES。
- **预期**：真实流准确率首次有常驻尺子；先量基线（预估 60~75%）再谈提升。
- **资源**：1 轮 + 20 张照（1~2h 标注）。**验收**：判据 rc=0；基线写回 10-core-capabilities。
  **时间**：T+7（首批）/ T+28（120 张）。

## M1 权重复标 + sadness 拍板（中期主线，修 A6/D2）

- **步骤**：标注集扩 120~200 张 → 逐类扫权重区间（r103 方法：6/6 档全过取中点）→
  sadness 担忧面复标（browInnerUp/jawOpen）→ 老大拍板后落 rules 注释 + 07 台账。
- **预期**：担忧 .55/.80 不再误报低落；八类权重全部有真照支撑。
- **资源**：2 轮 + 标注 4~6h。**验收**：有把握帧 top-1 ≥95%；担忧负样本 ≥8 条全 ✓。
  **时间**：T+28 天。

## M2 质量门复标 + 演示模式（修 E3/E4）

- **步骤**：标注照批跑亮度/方差/yaw 分布 → 重标 bright/blurVar/yaw；`?faceMode=demo` 预设
  （放宽亮度窗 + 文案升档）。
- **验收**：暗光/侧脸下"仅供参考"误命中降 ≥50%（S4 尺前后对账）。**时间**：T+21 天。

## ✅ 轮132 交付（S4 尺 + 延迟埋点）

S4 真照片尺已建：`face_au_export.py`（只存参数不存图）+ `face_au_replay_check.py`（纯 node 进电池）。实测真照片 12 张 top-1 100%、有把握帧 10/12；⚠️**语料全表演级强度、零低强度**，sadness/fear/disgust/contempt 零真照 ⇒ **S1 靶场仍只靠 F12**。

## 回滚锚（通用）

规则改动独立 commit（revert 即回滚）；`face-smile-rules.js` 开关默认 false 起步、灰度参数放 src 版；
deploy 三类归零才发布；AU JSON 与照片分离存放（照片只在标注者本机）。
