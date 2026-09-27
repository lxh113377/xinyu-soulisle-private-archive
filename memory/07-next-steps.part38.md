# 07 卷38 — r44 数据权利面台账（2026-09-27 第四轮）

> 换卷理由：07 主壳 4,068B / 上限 4,096B（余 28B），r44 条目须整节迁出。报告见
> `交付物/对标分析报告-2026-09-27-r44.md`。

## 本轮闭合（✅当次实测 08:2x–08:5x）

| # | 项 | 证据 |
|---|---|---|
| H1 | 披露语随运行模式翻转（旧版写死「不上传」，而演示层 `remote:true` 时数据确实进服务端库） | `D1a PASS`＋`D1b PASS`（两态互斥） |
| H2 | 删除从 fire-and-forget 改为**带回执 + 独立复核**：等 DELETE → 读 `/stats` 验双归零 → UI 印数 | `D2b PASS（本机已清除 ｜ 服务端已删 3 条，复核为 0）`＋`D2c PASS` |
| H3 | 可携导出：`exportAll()` 复用只读端点拼服务端两份 + 本机一份，条数与 `/stats` 对齐（零后端改动、不重建 jar） | `D3 PASS（server 1/1、messages 2/2、local 1、mode=remote）` |
| H4 | 常驻判据 `_test/data_rights_check.py`（8 断言）＋桩 9/9；peers 探针桩 10/10、整采 16/16 BLIND 0 | `DATA-RIGHTS-PASS` / `9/9` / `10/10` |
| H5 | 新增 `docs/data-and-privacy.md`（含四条已知边界，不藏） | 文件已入库 |
| H6 | peers 实测：隐私文档 2/16、版本化迁移 1/16、导出删除命名件 1/16、README 删除权 **0/16**、留存期 **0/16** | `交付物/对标数据/peer-datarights-2026-09-27.json` |
| H7 | 权威源同步 + 既有回归：`DEPLOY-SYNC-PASS`、`browser_check ALL-ASSERT-PASS`、`j4_memory_check -MEMORY-PASS`、`j4_remote_down_check -FUSE-PASS` | 四条独立手跑 rc=0 |
| H8 | 电池 64→**67**（data_rights / data_rights_selftest / data_rights_probe_selftest） | G10 `实跑 64 + 豁免 3 == 67`；`REPO-CONFIG-PASS` |

## 本轮自犯 4 条（全文见报告 §3）

① 探针把 `src/privacy_filter.js` 当隐私政策件（3/16→2/16，收紧到文档扩展名 + 固定反例②）；
② 回执写进 `#probe-result` 被探针渲染覆写、且探针文案含"失败"二字致等待条件误命中（换槽 + 正则三态）；
③ 反向腿用 `reload + 覆写 localStorage` 被 `add_init_script` 每次导航重跑冲回（改第二 context 预置）；
④ 又踩「字面量内部再放引号」第 N 次（heredoc 含引号中文 → SyntaxError，整段零执行）⇒ 文档正文一律走 Write。

## P1 / P2 排期

1. README 加「数据与隐私」指针行 —— 受 16,384B 注入预算（现 16,364B，余 20B），须先精简他处。
2. 引入最小版本化迁移（`server/src/main/resources/db/migration/` + Flyway），解"改字段即删库"。
3. 服务端留存策略（超 N 天/N 条截断），与 H2 回执共用 stats。
4. 沿用 r40–r43 未动项：fat jar 构建路 `--with-build` 档、`@SpringBootTest` 冒烟、voice 假媒体设备、
   three.js 升级、A6 键盘全序遍历、对比度 23 格有效背景、真读屏人工回归、
   `js/demo-config.js` 404（需老大在场，见 `part37` §安全事件）。
