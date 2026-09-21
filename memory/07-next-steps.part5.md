# 07-next-steps.part5.md

<!-- 本卷为 07-next-steps.md 的延续 -->

- [ ] ⏸ **已冻结（范围冲突待老大一句话解冻）**：起草《应用方案》PDF（大纲：交付物/提交包/应用方案大纲.md；AI核心作用章节可直接引用：双路情绪引擎实测分歧案例 + 词典层评测 94.4%/危机召回3/3 + **Serverless密钥隔离架构**，见 _test/emotion_eval.js / src/functions/api/chat.js）

## P1 — 应该做
- [ ] 情绪引擎评测集扩到 ≥60 条（当前36条、94.4%；剩2误判=真歧义类，可标注为"混合情绪"改评分口径为top-k命中）
- [ ] 语音输入真机验证（Web Speech API 代码已就位，msedge 实测需麦克风权限，演示前过一遍）
- [ ] DeepSeek Key 已出现在对话中——**建议到 platform.deepseek.com 轮换**，轮换后 `wrangler pages secret put DEEPSEEK_KEY` 更新 + 重部署

## P2 — 可以做
- [ ] 待老大决策（2026-09-21 提出）：`03-tech-stack.md` / `02-structure.md` 里的**目标技术选型**（如「前端置于 `src/main/resources/static/`」）在 J1 落地时被证明会造第三处副本同步点 → 是否给「规划中」条目统一加「待落地验证」标注，避免计划被当成事实
- [x] 多情绪混合展示：双色星雾 ✅ 2026-09-20 完成（沿螺旋 6 条交替色带做空间分离 + 同色系次色做色相分离 ≥100°，次情绪须达主情绪 40% 权重；常驻断言 = _test/browser_check.py 两条 + _test/pixel_dual_check.py 像素级三用例）
- ~~角色形象（VRM 或 SVG 表情脸）~~ ❌ 老大 2026-09-19 指示：不做，已从待办移除

## 最近对话摘要
- 2026-09-22 r2 — 老大「全部授权」+ 定 CloudBase 决策 + 给新 Key + 要求**完成 J3/J4/J5** → 主线 Java 全栈 J1–J5 **全部贯通**。要点：**J3** 词表逐字移植（注意 JS 里 `难受`/`不` 有重复项会被重复计分，必须原样保留否则对不上 94.4%），双端对账逐项一致；**J4** H2 file 默认/MySQL 可切，核心断言是「清空 localStorage 后刷新星图仍点亮」；**J5** 轻量 token 过滤器（不引 Spring Security）+ Dockerfile（Docker 未装未实测）。踩坑：① 我一度写出**重复的 `spring:` YAML 键**（SnakeYAML 会直接启动失败），读盘自查后合并 ② `wrangler@3` 报错、**`@4` 成功** ③ Pages **secret 需重新部署才生效** ④ 顺手修了 `src/js/demo-config.js` 缺 `!cur.proxy` 守卫的老坑（J2 踩到的就是它）。生产 `PUBLIC-ONLINE-ALL-PASS`。

## 分卷目录
- **卷1** `07-next-steps.part4.md` — 07-next-steps 分卷（R199 自动拆卷）

