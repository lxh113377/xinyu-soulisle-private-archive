# 05 功能状态 · 分卷 12（r102 续：面部表情判据扩容与重标）

> 承接 part11 的 r87（表情识别首版）。本卷记 r102：**表情判据 5 类 → 8 类 + 重标 + 新判据尺**。

## r102 · 面部表情识别精度与种类（2026-10-10）

### 接手时的前提核实（**字面不准，方向对**）

老大描述「当前系统大致只能识别三种情绪（愉悦、平静、焦虑）」。
磁盘实况：`face-smile-rules.js` r87 版声明 **5 类**（joy/sadness/anger/fear/calm），
用教科书最大 AU（0.8–1.0）跑，5 类分类全对。**但按真实摄像头强度（AU 0.15–0.5）重跑**：

```
scale=1.00  joy:joy  sadness:sadness  anger:anger  fear:fear   disgust:anger  surprise:fear
scale=0.50  joy:joy  sadness:sadness  anger:anger  fear:fear   disgust:calm   surprise:fear
scale=0.25  joy:calm sadness:calm     anger:calm  fear:calm   disgust:calm   surprise:calm
```

⇒ 低强度的 sadness/anger/fear 全部退回 calm；用户体感确实只剩三种。
**三类（surprise/disgust/contempt）根本不在词表里**，只能挤进 anger/fear
（实测 disgust 1.00→anger 0.47、surprise 1.00→fear 1.00）。
⇒ **「体感只有三种」成立，但根因是"权重没校准"不是"类没写"** —— 这个区别决定了改造方向。

### 五个实测缺陷（本轮全部修）

| # | 缺陷 | 实测读数 |
|---|---|---|
| D1 | 判据从未被真实数据校准（F5 只验 smile/neutral 两类口部分离，4 组权重里 3 组无真实样本） | 见上表 |
