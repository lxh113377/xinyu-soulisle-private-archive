# 11 - 面部（表情）识别准确率优化 · 诊断与方案（face-diag · r124）

> 立轮：2026-10-12。触发：老大真人实测「只能识别平静/低落/愉悦/厌恶，愤怒等识别不到，
> 误判较多，必须做明显表情（露齿）才判微笑」。授权口径（本轮已确认）：
> **目标准确率 = 有把握帧 top-1 ≥95% + 不确定帧 ≤30%**（分层，不追全帧）；**延迟 = 端到端 ≤500ms 且单帧计算 ≤100ms 双约束**；
> **路线 = 规则派**（补数据+复标阈值，零新依赖、隐私红线不动）。
> 红线不变：画面只在本机内存（不拍照/不上传/不留存）；crisis 恒 false。
> **本轮零 src/ 改动**——本文档是诊断+方案；执行轮按 §四 时间表动 `face-smile-rules.js`。

## 一、症状实测（node 复算 FaceEngine.read()，13 条向量；脚本全文见 `2026-10-12-face-diag.md`）

| 输入向量（真人低强度形态） | 期望 | 实际 | 结论 |
|---|---|---|---|
| 微笑 mouthSmile .85（露齿大笑） | joy | joy 0.958 ✓ | 只有大笑过线 |
| 微笑 mouthSmile .40（抿嘴笑） | joy | joy 0.396 ✓ | 过线但强度仅四成 |
| **微笑 mouthSmile .22（轻微笑）** | joy | **calm 0.381 > joy 0.217 ✗** | 沉底，界面笃定显示「平静」 |
| 微笑 mouthSmile .12（很轻微笑） | joy | calm 0.714，joy 0.100 ✗ | 彻底沉底 |
| 愤怒 browDown .65 / .40 | anger | anger ✓ | 明显怒可判 |
| **愤怒 browDown .20（轻度紧锁眉）** | anger | **calm 0.414 > anger 0.205 ✗** | 同上机制：低强度沉 calm |
| 愤怒真实照（face-api .64/.59） | anger | anger 0.631 ✓ | 「形态」没错，是「幅度」门槛 |
| 低落真照#1（Commons 实测 AU） | sadness | sadness 0.629 ✓（次分 surprise 0.468，margin 0.160 贴线） | r103 重标有效但贴置信线 |
| **担忧 browInnerUp .55 / .80** | calm | **sadness 0.344 / 0.500 ✗** | 未拍板误报面，实测坐实 |
| 说话 jawOpen .5 / 中性 | calm | calm ✓ | 真负样本不误报 |

**一句话根因**：peak=0.60 满强度归一化 + 分母 8 因子摊薄 + calm 残余线（top≥0.26 才翻得出 calm）
= 真实用户 0.2~0.45 幅度段的轻表情**系统性沉底成 calm**；愤怒"识别不到"不是形态问题是**幅度门槛**。
配套体感：界面只显示 argmax 一个标签，第二名的弱 anger/弱 joy（0.2 左右）完全不可见。

## 二、三维根因（详表 `.part1.md`，每条附实测证据）

- **数据层**：真实标注照 ≈8 张且只覆盖 joy/neutral/sadness/anger；fear/surprise/disgust/contempt 零真照；
  标定样本全是 0.6~0.98 表演级强度（4 张标 Duchenne、17 条合成向量标 peak），**无 0.1~0.4 低强度真人样本**；
  真实流判据 face_check F5/F10 因本机无摄像头**挂起** ⇒ 真实场景无尺子。
- **算法层**：peak 归一化对低强度系统性压半；分母摊薄（只笑嘴时 8 因子摊薄）；calm 残余线 0.26；
  单特征判 anger 与专注同构（已拍板代价）；browInnerUp 判 sadness 误报面（未拍板）；EMA α=0.3 无迟滞。
- **工程层**：无端到端延迟量化（8fps+EMA 收敛 ~1s 无测量）；质量门阈值未复标；界面无候选分布展示。

## 三、分卷索引

| 内容 | 文件 |
|---|---|
| 三维根因详表（12 条，带实测行号） | `11-face-accuracy.part1.md` |
| 三层优化建议（短/中/长期） | `11-face-accuracy.part2.md` |
| 执行方案（改进项×步骤/预期/资源/验收/时间） | `11-face-accuracy.part3.md` |
| 验证方案 + 质量标准 + 风险预案 | `11-face-accuracy.part4.md` |
| r184 六场景根因 / 修复 / 范畴核验 | `11-face-accuracy.part5.md` |

## 四、当轮复算入口（每轮跑，棘轮只降不升）

```bash
python _test/core_capability_baseline_check.py    # N2 单测 + F1 vendor + N1 语意
python _test/face_scene_check.py{,--selftest}     # F13 场景切片（r184 新）
python _test/face_discrim_check.py --selftest     # F11 反例8 已修活（16 条）
```
