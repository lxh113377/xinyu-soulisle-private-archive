# 07 卷37 — r43 可复现面台账（2026-09-27 第三轮）

> 换卷理由：07 主壳 4,093B / 上限 4,096B（余 3B），r43 条目须整节迁出。报告全文见
> `交付物/对标分析报告-2026-09-27-r43.md`。

## 本轮闭合（✅当次实测 07:1x–07:5x）

| # | 项 | 证据锚点 |
|---|---|---|
| H1 | vendored 资产治理闭合：名册登记 axe-core（sha/size/上游）+ `vendor_dirs` 化枚举 + `audit_coverage` 改相对路径整条比（挡同名顶包）+ 桩扩到 5 类篡改 | `VENDOR-FRESHNESS-PASS（枚举面=src/vendor,_test/vendor，磁盘 4 件）`；`SELFTEST-PASS: 5 类篡改全部被抓到` |
| H2 | `a11y_check` 的 sha/长度改为**从名册现读、默认强制**（原 `XINYU_AXE_SHA` 默认空 = 事实上没钉；等长替换不可见） | 改后重跑 `A11Y-PASS 违规节点=0 … 未验=0 rc=0` |
| H3 | 新观测面探针 `_test/peer_repro_probe.py`（A 锁定件 / B README 上手 / C 钉版率，n/a 单列不并入 0） | `REPRO-SELFTEST: 19/19`；整采 `应测 16 仓 BLIND 0 恒等式 OK`；peers：lock 10/16、env 模板 5/16、compose/Docker 6/16、可执行上手 8/16、钉版≥90% 仅 1/13 |
| H4 | 新常驻判据 `_test/clean_clone_check.py`：从 **HEAD** 克隆（未提交改动不得参与证明）→ 真加载 → 真发一句话 → 报错须 ⊆ 计数化已知缺口，0 命中即催销账 | `CLEAN-CLONE-PASS 从 HEAD(f24059a) 克隆可跑`；桩 `5/5`（含"console 404 真机原文形状"三条漏报侧专属反例） |
| H5 | 电池 61→**64**，README(16,364B ≤ 预算)/docs 声称值同步 | G10 `实跑 61 + 豁免 3 == 64`；`REPO-CONFIG-PASS` |

## 🔴 本轮安全事件（必须留在台账里，防止"改密钥面"被顺手做掉）

为核对配置形态 `sed src/js/demo-config.js` 前 20 行，**把该文件里的明文 DeepSeek Key 打印进了会话输出**。
git 面未泄露（该件 .gitignore），transcript/日志面已泄露 ⇒ **撤销并重发 Key 归老大**，
agent 不代做密钥迁移、不把它抄进任何文件/记忆/提交说明。
连带决策：**那条 404 本轮不消除**——安全的改法要动密钥面（把该路径改成入库零密钥版），
一旦 `git add` 时旧内容还在就把真 Key 提交进**已推送**历史，不可逆。需老大在场 + 先撤销 Key。

## r43 未消除 / 排期

1. `js/demo-config.js` 404（唯一已登记缺口，`clean_clone` 每轮计数显影，0 命中即催销账）。
2. 干净克隆的 **fat jar 构建路**未进判据（mvn 不入阻断链，承 r41）⇒ 加 `--with-build` 人工档。
3. `server/Dockerfile` 至今未实测构建 ⇒ README/AGENTS 里"两条部署路均已实测就绪"措辞偏强，待改。
4. README 拆独立 `docs/quick-start.md`（peers 8/16 有可执行上手）。
5. 沿用 r40/r41/r42 排期未动：`@SpringBootTest` 冒烟、voice 假媒体设备、上游限流显影、three.js 升级、
   A6 键盘全序遍历、对比度 23 格有效背景、a11y 真读屏人工回归。

## 不做

追 lockfile（JVM + 零构建前端 ⇒ 记 n/a，非缺失）；把 mvn 接进阻断链；
JS lint / 覆盖率百分比 / i18n / 插件市场 / React / Spring Security（维持 r41、r42 判定）。
