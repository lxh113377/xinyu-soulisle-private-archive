# 07 卷35 — r42 无障碍面（2026-09-27 第二轮）台账

> 换卷理由：07 主壳 3,973B / R161 上限 4,096B（余 123B），r42 条目须整节迁出。
> 报告全文：`交付物/对标分析报告-2026-09-27-v2.md`。

## 本轮闭合（全部 ✅当次实测，时刻 05:1x–06:1x）

| # | 项 | 证据锚点 |
|---|---|---|
| H1 | 新观测面 `_test/peer_a11y_probe.py`（三通道：树命名件 / README 声明 / 清单真依赖） | `A11Y-SELFTEST: 31/31`；整采 `应测 16 仓 BLIND 0 恒等式 OK` |
| H2 | 全零的第二条独立通道（README 声明 0/16） | 探针 base64+正则 vs 独立 `curl Accept: raw + grep` 逐仓 16 行全 0；lobehub README 39,136B 证输入非空 |
| H3 | 常驻判据 `_test/a11y_check.py` A1–A8（6 状态 x 2 主题，规则集含 experimental） | 首跑 `A11Y-FAIL 违规节点=16 红状态=8 动效比=0.77`；收口 `A11Y-PASS 12 项 违规节点=0 未验=0` |
| H4 | WCAG 2.5.3：`#btn-settings` / `#btn-theme` 图标降装饰 + 无障碍名以可见文字开头（随主题同步） | A2 违规 16→0、A7 不匹配 2→0；**未改判据口径** |
| H5 | 兑现 `prefers-reduced-motion`：`three-scene.js` 冻结 WebGL 自走时钟，镜头位移留滚动通道 | 帧间像素差 0.0516 → **0.0000**；A5a 同时断正常态在动（防"删光动画"式作弊） |
| H6 | axe vendored（553,290B）长度钉死 + 可 sha256 钉，禁在线回落 | 取不到 ⇒ `rc=2 ENV-UNVERIFIED` |
| H7 | 判据桩 `--selftest` 12/12，像素数学单一实现 `mean_abs_delta()` | main 与桩共用同一函数（M5⑥） |
| H8 | 权威源三件改动同步 `deploy/xinyu` | `DEPLOY-SYNC-PASS missing=0 diff=0 extra=0`；`js/demo-config.js` 零密钥 True |
| H9 | 电池 58→61（`a11y_probe_selftest` / `a11y` / `a11y_selftest`），README 与 docs 声称值同步 | `REPO-CONFIG-PASS`、G10 `实跑 58 + 豁免 3 == 61` |
| H10 | README「♿ 无障碍」节 + docs「无障碍」节；顺手把 docs 里陈旧的 47 条更正注 | `git diff` 复核只有 3 处行替换、零吞行；README 16,364B ≤ 16,384B 预算（余 20B） |

## 既有回归复核（改权威源后独占手跑，✅05:5x）

`browser_check ALL-ASSERT-PASS`｜`pixel_dual PASS`｜`lightshow PASS`
⇒ 三条像素级判据共同背书：`REDUCE` 在 headless 默认（no-preference）下取 false，运行时行为与改前一致。

## r42 P1/P2 序（截止后）

1. 危机转介条 / 情绪曲线 canvas 的**读屏可懂性**：现只有 `aria-live`，曲线图纯视觉 ⇒ 要文字化读数（汇总 `aria-label` + 可 Tab 的逐点表）。
2. `color-contrast incomplete` 23 格做**有效背景合成**后逐格判定（现只能弃权并被 A4 棘轮钉住，上限 30）。
3. A6 键盘只测了首个 Tab 落点 ⇒ 升为"页顶到底全序遍历覆盖全部可交互件"。
4. 真读屏器人工回归（NVDA + VoiceOver 各一次）。
5. **README 16,384B 预算无判据守护**：本轮三次顶破（17.1KB→16.5KB→16.36KB）全靠手量发现，
   而 `docs/quality-gates.md` 第 3 行把它写成明文约定 ⇒ 应补常驻判据（同 r39 体量体检家族，P2）。
6. 沿用 r40/r41 排期未动：`@SpringBootTest` 上下文冒烟、`voice` 假媒体设备、上游限流显影、three.js r128→r186。

## 不做（理由进报告 §4/§5，别再来问）

JS 侧 a11y lint 工具链（原生 ES Module 无构建链，为一条规则引整条工具链不成立）；
axe 违规分档放行（12 单元只有 0/非 0 有意义）；覆盖率百分比（16 家公开数值 0 家，无分母）；
i18n 框架化 / 插件市场 / 换 React / Spring Security / 多用户（维持 r41 判定）。
