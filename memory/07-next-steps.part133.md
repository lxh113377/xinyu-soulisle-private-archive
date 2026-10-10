# 07 下一步 · 分卷 133（r102 挂账）

> r102 收口时**未完成**的条目。P0 永不为空（memory/07-next-steps.md）。

## P1 · 表情真实照片扩到 7 类（r102 挂账，本轮唯一未完成项）

**现状**：`_test/face-fixtures/` 只有 **8 张**（4 smiling + 4 neutral）。
`_test/face_check.py` 的 F5 只验「微笑组 vs 中性组口部分离」，**七类里只碰了 joy 与 calm 两类**。

**为什么本轮没做**：已实测尝试从 Wikimedia Commons 抓取 sadness/anger/fear/surprise/disgust
五类的真实人脸照片（API 可达，HTTP 200），但**检索面被非照片题材污染**：
`painting / engraving / drawing / illustration / manuscript / mugshot / 书籍插页 / 卡通` 占绝大多数，
5 类各检索到 13–56 个候选，**可用真实人脸照片近乎为零**（fear 类候选里出现猫、考拉、月亮照片）。
⇒ **不硬凑**。硬凑的代价是：判据会去拟合一批"本来就是画的表情"，
把规则标歪，且再也分不清哪条是真数据。

**要做需要什么**：人工标注的公开数据集（FER2013 / AffectNet / RAF-DB），
或人工筛选 Wikimedia 候选并逐张标注。**这是人工活，不是脚本能替代的。**

**为什么仍然重要**：F11 的 17 条标注向量是**合成 FACS 向量**，
验的是「判据结构有判别力、阈值真的参与计算」，
**不等于真实场景准确率**。补上真实照片，才谈得上"识别更准"有数据支撑。

## P3 · valence / arousal 连续情感轴（**建议本轮不做**）

emonet/face-analysis 的能力位：除分类外给 valence/arousal 连续量（实测 CCC 0.82/0.75），
能表达"难受但平静"这类混合态 —— 当前 8 类离散标签表达不了。

**不做��理由**：① 会引入**第二个需要标定的量**，当前规则判据撑不住；
② 且上面那条（真实照片）未完成前做它，等于建在沙上；
③ 本项目定位是"情绪陪伴"，离散的"用户现在更接近哪一类"对可用性贡献更直接。

## 已完成（本轮，见 05-feature-status.part13.md）

- ✅ F11 分类判别力尺（含 6 条反例 selftest）
- ✅ `peak` 重标（0.45 语义重定义 → 0.60），饱和 25% → 3%
- ✅ 表情 5 类 → 8 类（新增 surprise/disgust/contempt + 三组易混对分水岭）
- ✅ `family` 映射 + `confidence` 置信度 + 界面「读数不稳」标注

## 尚未决定（等老大指示）

- **是否部署到公网**：r102 全程未部署（`deploy/xinyu/` 已同步且 `deploy_sync_check` PASS，
  但未执行 `wrangler pages deploy`）。老大未指定，故未做。
- **社区协作（issue/PR）**：沿用 r100 §2.6 裁决 —— 对标登记全是能力位对比，非对方缺陷 ⇒ 零动作。