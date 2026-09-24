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

- [x] **体积预算表加"必须全覆盖"判据**：实测抓到原 13 文件表漏登记 `src/data/emotion-strategy.js`（4,720B），
      且新增文件会静默绕过体积门禁 ⇒ 现漏登记即红

- [x] **`_test/benchmark_metrics.py` 对标源数据机器化**：14/14 仓采集成功、能力探测改**递归整树**
      （根目录一层探测无判别力：14 仓 sw/locales 全在子目录，只看根会一律报"无" = 把"没测到"当"没有"）

- [x] **公网跟进**：deployment `208e1743`（Cloudflare Pages），`live_sync`/`public_check`/`online_check` 三判据 rc=0

- [x] 版本推进 **v1.4.0**（`server/pom.xml` 1.3.0→1.4.0，JDK 17 构建 fat jar 29,419,279 B）+ CHANGELOG + 标签

- [x] **接口契约唯一声明源**：`docs/openapi.yaml`（11 条，实读控制器与 `LlmProxy` 取得）
      + `_test/api_contract_check.py`（C1 缺文档 / C2 幽灵 / C3 前端偷调 / C4 运行态真实打 8 端点 / C5 自证非恒真）
      → 实跑 **10/10 PASS**，电池 24 → **26** 套件，CI `java-build` 增 2 步；探测用 `contract-probe` 会话且结尾 DELETE 自清

- [x] **`.github/dependabot.yml`**（`maven`@`/server` + `github-actions`@`/`）——
      并**纠正 r20 自己的错误归因**"零构建挂不上 dependabot"（`06-constraints` 原条目保留 + 更正注）

- [x] 测量装置自纠：漂移比对纳入 `caps`/`docs`；self 套件数改以电池 SUITES 为唯一分母；参照池 14 → **16**

- [x] self 账面：`docs 8/9 → 9/9`、能力位 `api_spec` 与 `deps_autoupdate` 各 0 → 1（台账 `交付物/对标数据/benchmark-metrics.json`）
