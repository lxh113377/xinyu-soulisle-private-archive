# 05-feature-status.part3.md

<!-- 本卷为 05-feature-status.part2.md 的延续 -->

## 📋 计划中

- [x] **M5 对话列表窗口化**：DOM 上界 60 + 配额制「展开较早」（每次放回 20 条并临时抬高配额，新消息收回）
  - 实测证明**窗口化不截断模型上下文**：`getHistory()` 仍为既存 40 条上限、`MemoryStore` 45 条 = 发送条数

- [x] **M6 响应式三档 + 粒子按视口降档**：480/768/1024 断点；粒子 900/1200/**2600**（桌面档恒 2600，保住 `browser_check` 的 `LIT` 标定与 `pixel_dual_check` 占比判据）

- [x] **M7 CI 三条门禁**：新增 `java-build` 内**词表一致性红线机器化**（起无密钥 fat jar 跑 `engine_consistency_check.py`）+ 密钥零入库扫描（拼接生成对照组，防 workflow 自伤命中）+ 独立 `browser-regression` job（runner 无 GPU → `XINYU_BROWSER_ARGS` 强制 SwiftShader，本机已用同参数复跑 PASS）

- [x] **M8 维护可见性**：`ROADMAP.md`（已完成/计划/**明确不做+理由**）、`server/pom.xml` `0.1.0-J1`→**1.3.0**、CHANGELOG `[1.3.0]`、标签 `v1.3.0`

- [x] **情绪识别后端化接线**（07 P0「J3/J4 变现」第①件，自 J3 落地起挂账 3 天）
      `src/js/emotion-remote.js`：后端 `/api/emotion` 可用时以后端为准 ⇒ **消除 JS/Java 两份真相**；
      三层开关与 J4 同口径（默认关 / 本地演示开 / **公网刻意不开**）；**危机先本地短路不为网络等待**；
      404·超时·形状不合法即熔断回落本地；界面如实标注「情绪:后端」
      判据 `_test/emotion_wiring_check.py` 9 项 PASS（含 W3b 实测 `attempted=0` 未经后端、W5 熔断不伪装、
      W6 同句双端词典结论相同）+ `--selftest` 3 类篡改全抓到

- [x] **vendor 供给链守卫** `_test/vendor-manifest.json` + `_test/vendor_freshness_check.py`
      （零构建项目没有 lockfile/dependabot ⇒ 第三方库漂移此前是**纯盲区**）：
      V1 sha256 完整性 V2 从文件内容解析版本对账（正则零命中即红，不把"没测到"当"通过"）
      V3 新库漏登记即红 V4 `--check-upstream` 报落后（`--strict` 才判红）；`--selftest` 4 类篡改全抓到

- [x] **gsap + ScrollTrigger 3.12.5 → 3.15.0 成对升级**：前端实到 API 面仅 5 处；
      `browser_check`/`lightshow_check`/`pixel_dual_check` 三套件 rc=0；体积 +1,908B 仍在预算内
