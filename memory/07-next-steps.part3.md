# 07-next-steps.part3.md

<!-- 本卷为 07-next-steps.md 的延续 -->

- 2026-09-20 r16 — **方向定调**：老大要求把陪聊后续计划改为「**Java 全栈**」目标，已落进本文件「主线目标」章节（J1–J5 分阶段 + 不变量）。同轮补齐项目**版本控制基线**（此前唯一无 `.git`/`.gitignore` 的项目）：`git init -b main` + 新建 `.gitignore`（密钥 `src/js/demo-config.js` / `_test/cors_probe.py` / `.env*`；生成物 `__pycache__`、`_test/_shots/`；元数据 `.codebuddy/` 等），**未 commit**。
- 2026-09-20 r6 — 「越聊越点亮」星雾 + 底部对话坞（老大点子）：初始星雾全暗（极暗灰白微光轮廓），每句对话按其情绪点亮 1–8 颗星并持久化重放，清除数据即熄灭；第二幕探针 + 第三幕聊天融合为**底部常驻对话坞**（`#chat-dock`，可折叠、点叙事区自动收起）。为让"被点亮的星"看得见，`PointsMaterial` 换成 `ShaderMaterial` 支持逐粒子尺寸（暗星 0.05 / 点亮 0.22，实测有效像素 29 → 323）。踩坑：① 悬浮坞遮住第四幕清除按钮（已 padding 预留 + 自动收起 + 测试断言坞可收起）② 像素判据单比色距会被 1 像素噪点骗过 → 改双条件（色距 >0.25 且少数簇占比 >0.10）③ 次情绪必须入库否则重放少点。回归：browser_check（lit 0→5→17→刷新 17→清除 0）+ pixel_dual_check（多色 0.488/33.4% vs 单色 0.197/0.2%）双绿，console 0；deploy/xinyu 哈希全一致。
- 2026-09-20 r5 — 双色可分辨轮：老大反馈「双色看着像一个颜色」。根因=按**径向单调渐变**分色（内核主色→外晕次色），在 AdditiveBlending 下屏幕均值仍是单色；旧验证只看粒子数组 head/tail 色距（0.676）=内部数据不同≠屏幕看得出。修法：①6 条交替色带（软方波+纯色平台）取得空间分离；②`makeDistinct` 对同色系次色做色相分离（色相环距 <0.28 即旋开+提饱和）。验证=像素级 2-means（有效像素先证非空 1983/2306/2767；双色 0.522/0.384 vs 单色对照 0.088），常驻脚本 _test/pixel_dual_check.py + browser_check 两条断言全绿。同轮把上轮遗留的升级建议闭环：R255 落盘 A-memory-start 速查区第 ⑧ 条 + 版本历史 V10.52.0（rule_editor 补丁 6/6，镜像 SHA256 已同步，三门禁 mirror/noise/evolution 全 pass，提交 0002d3d）。部署副本 deploy/xinyu 哈希比对一致。

## 分卷目录
- **卷1** `07-next-steps.part2.md` — 07-next-steps 分卷（R199 自动拆卷）

