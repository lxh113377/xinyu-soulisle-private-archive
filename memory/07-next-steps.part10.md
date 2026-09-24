# 07-next-steps.part10.md

<!-- 本卷为 07-next-steps.part5.md 的延续 -->

- [x] ~~DeepSeek Key 轮换~~ ✅ 2026-09-22 已完成（见 `part9`）。**本条属台账漂移**：`part5` 一直挂着未勾，2026-09-23 盘点时确认为重复条目，已关闭。

## P2 — 可以做
- [ ] 待老大决策（2026-09-21 提出）：`03-tech-stack.md` / `02-structure.md` 里的**目标技术选型**（如「前端置于 `src/main/resources/static/`」）在 J1 落地时被证明会造第三处副本同步点 → 是否给「规划中」条目统一加「待落地验证」标注，避免计划被当成事实
- [x] 多情绪混合展示：双色星雾 ✅ 2026-09-20 完成（沿螺旋 6 条交替色带做空间分离 + 同色系次色做色相分离 ≥100°，次情绪须达主情绪 40% 权重；常驻断言 = _test/browser_check.py 两条 + _test/pixel_dual_check.py 像素级三用例）
- ~~角色形象（VRM 或 SVG 表情脸）~~ ❌ 老大 2026-09-19 指示：不做，已从待办移除

## 最近对话摘要
- 2026-09-23 r-优化 — 老大「全面深度优化（代码质量/性能/可维护性/体验，不改变核心功能与选型）」→ **16 文件改动已 commit+push（`dbd5520`）**。前端 12 处（Key/proxy 防洗、`lexAll` 复用消除二次词典扫描、否定判定窗口缓存、LLM 60s 超时、HiDPI 曲线+防抖重绘、焦点环/减弱动效/aria、死 CSS 清理）+ 4 处隐雷（`lightShow` 空形、`douse` 清危机脉冲、`showTimer` 声明前置、`order` 走 TypedArray 原生排序）；服务端 1 处（`LlmProxy` 上游非 JSON 体折成 `upstream-nonjson`，与 v1 Function 契约对齐）；测试 1 处（pixel 判据相位抖动治理，见 AC-OBS-03）。
  **门禁实测**：`DEPLOY-SYNC-PASS` / `ENGINE-CONSISTENCY-PASS`（73 条 98.6%、危机 6-6 双端全等）/ `LIT-COLOR-CHECK-PASS` / `browser_check ALL-ASSERT-PASS` / `LIGHTSHOW-CHECK-PASS` / `J4-MEMORY-PASS` / `J4-FUSE-PASS` / `VOICE-PASS` / `mvn BUILD SUCCESS` / 入库密钥 0 命中。`j2` / `online` / `public` 因本机无 `DEEPSEEK_KEY` 未跑。
  **老大定下的演示期铁律**：**演示前先 `git pull`，再跑一遍 `python _test/deploy_sync_check.py` 过绿，才允许进入演示**（防 `src`→`deploy/xinyu` 副本漂移导致公网页与本地不一致）。
  **踩坑**：① 旧会话残留的"改测试阈值"授权未必要用——本次是**根因修复**（相位抖动），阈值保持原值不放松；② 生产侧 `?seed=` 测试钩子最终移除，改由 Playwright 侧注入随机源 + 冻结时钟，生产代码零钩子；③ 后台 `java -jar` 进程会锁住 `server/target` 里的 jar，**重打包前必须先停服**，否则 `repackage` 报 `Unable to rename ... .jar.original`（编译其实已成功，只有替换失败）。
- 2026-09-22 r2 — 老大「全部授权」+ 定 CloudBase 决策 + 给新 Key + 要求**完成 J3/J4/J5** → 主线 Java 全栈 J1–J5 **全部贯通**。要点：**J3** 词表逐字移植（注意 JS 里 `难受`/`不` 有重复项会被重复计分，必须原样保留否则对不上 94.4%），双端对账逐项一致；**J4** H2 file 默认/MySQL 可切，核心断言是「清空 localStorage 后刷新星图仍点亮」；**J5** 轻量 token 过滤器（不引 Spring Security）+ Dockerfile（Docker 未装未实测）。踩坑：① 我一度写出**重复的 `spring:` YAML 键**（SnakeYAML 会直接启动失败），读盘自查后合并 ② `wrangler@3` 报错、**`@4` 成功** ③ Pages **secret 需重新部署才生效** ④ 顺手修了 `src/js/demo-config.js` 缺 `!cur.proxy` 守卫的老坑（J2 踩到的就是它）。生产 `PUBLIC-ONLINE-ALL-PASS`。

## 分卷目录
- **卷1** `07-next-steps.part4.md` — 07-next-steps 分卷（R199 自动拆卷）

