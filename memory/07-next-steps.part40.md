# 卷40 — r45 发布治理面（下）：两条闸的落地 + v1.5.0 切版 + 未闭环序（2026-09-27）

> 上卷 `part39`：受理面二次红的链条与 16 仓实数。

## 4. 落地的两条闸（电池 68→70）

- `_test/peer_release_probe.py --selftest` 13/13（semver 6｜lag 3｜CHANGELOG 3）。
  自犯一处：`lag` 首版整数天截断，把 22 小时读成 `lag=0` ⇒ 改小数天 + 补「30 小时=1.25」用例。
- `_test/release_governance_check.py`（判据 + `--selftest` 12/12，正例 3｜反例 6｜边界 3）：
  R1 feat 增量 ≤5（PASS 行印当前值与余量，不做零余量地板）｜R2 CHANGELOG ⇄ git 双向对账 +
  **R2c 逐轮点名**｜R3 已发布 tag 必须有版本段｜R4 滞后**只报不拦**（墙钟判据会在零提交时自己翻红）。
  取不到 tag 回落 `ls-remote`，双否 ⇒ rc=2 UNVERIFIED，不把"读不到"判成"违规"。
- 首跑真判红（不是设计意图）：`feats=11（上限 5）` + `R2c r38,r41,r42,r43`。
  其中 **r38 是判据自己错** —— `## [1.4.3]` 段标题写着"对标轮 r38 续"，功能早已随版发布，
  tag 之后只剩 docs 尾巴 ⇒ 分母收窄到 feat/fix/perf/refactor，并补「正例③ docs/chore 免登记」钉边界。
- 上线第一分钟咬到作者：changelog 写进工作树尚未 commit，R2b 立刻报
  「有 3 条 bullet 而 v1.5.0..HEAD 零 commit ⇒ 文案先行」（rc=1，commit 后即绿）。

## 5. v1.5.0 切版与资产（本轮手工，#5 待自动化）

- 版本三源同推：`server/pom.xml` 1.4.3→1.5.0、`ROADMAP.md` 当前版本行、`CHANGELOG.md` 段标题
  （✅ `G12 tag=v1.5.0 pom=1.5.0 文档=['README.md','ROADMAP.md']`；`G4 实测 70 | README 声称 70`）。
- `python _test/build_jar.py` → `BUILD-JAR-PASS 体积 28,445,748 B｜内嵌 version=1.5.0 == pom｜
  密钥命中 0 条｜jar 内前端静态件 0 条`。
- 资产：`soulisle-server-1.5.0.jar` sha256 前缀 `decf70ed220da3c4`；
  `xinyu-web-1.5.0.zip` 252,789 B（24 条目，比 1.4.3 多的正是 `js/data-rights.js`）sha256 前缀 `9059da87d80590be`。
- 规矩：**tag 打在已过闸的 sha 上，发布完以远端可见物为凭**（`gh release view --json assets` 回读）。

## 6. 未闭环（P1 序）

- [ ] **P1 `_test/release_cut.py`**：一条命令串「G12 预检 → build_jar 验货 → web zip → commit → tag →
      push → 等 CI 绿 → `gh release create` → 远端回读比对 size/sha」，任一步失败不产生对外可见物。
      根因承接：本轮又手敲了 mvn/zip/tag/gh 四步，手敲就有漏步骤的风险（上一轮漏 PRECACHE 同族）。
- [ ] P2 README「数据与隐私」指针行 —— README 余量 20 B / 16,384 B，须先一次性瘦身（把 r41–r45 长行折进 ROADMAP）。
- [ ] P2 `js/demo-config.js` 404 消除（`clean_clone` 已登记为已知缺口，命中数 1）——需老大在场。
- [ ] ⚠️ 上一轮遗留：`src/js/demo-config.js` 曾被我的 `head -20` 打进对话，**密钥撤销动作在老大侧**，
      文件本身仍 gitignore、未被反跟踪、值不落任何文件或提交。
- [ ] 跨项目：volumegov `scan_workspace` 的 `:430` 主循环改单遍 `os.scandir` + 归档面增量缓存
      （分相计时基线已在册，walk 占 99.8%，但 `timings=` 无生产调用方 ⇒ 子归属仍未闭合）。
