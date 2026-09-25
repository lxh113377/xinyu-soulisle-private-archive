# 05-feature-status.part4.md

<!-- 本卷为 05-feature-status.part3.md 的延续 -->

## 📋 计划中

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

- [x] **接口契约探测 8 → 11 全覆盖**：C6 `探测 + 豁免 == 操作总数` + C6b 零豁免，
      取代上一轮"阈值低于总量"的 `done >= 8`（我上一轮自己留的洞）

- [x] **仓库配置自洽守卫** `_test/repo_config_check.py`（G1 dependabot schema/目录可达、
      G2 CI job 数==README 声称、G3 契约被索引引用、G4 电池条目数==README 声称、G5 `--online` 默认分支可见）
      → 实跑 5/5 PASS，`--selftest` 四类合成篡改全抓到

- [x] **该守卫上线当场抓到一个真实脱节**（红→绿留证）：加 2 条套件后 README 仍写 26 ⇒ G4 报
      实测 28、声称 26，改文档后转绿

- [x] 电池 26 → **28** 套件；本轮 16 参照仓数据**零漂移**（对标对象侧无新变化）

- [x] **发现并填补 R196 强制项空壳**：`memory/06-constraints.md` 的「测试专用文件清单」至今是 init 模板占位符
      （`（如 eval/testset_provenance.json / blindset / frozen）`）⇒ 「新增评测数据先登记 provenance」这条红线从未真正落地，
      而评测集 accuracy（73 条 / 98.6%）是要进《应用方案》和答辩材料的数字。
      现填为登记表：文件 / 条数 / 谁在裁决时读它 / provenance（人工撰写，不用模型生成样本）/ 冻结状态，
      并写明「真实对话走 `chat_message` 表，与评测集物理分离，禁止回流刷分」（同源 PII 风险）

- [x] **判据化**：`repo_config_check.py` 新增 **G8**（模板原句残留 / 登记文件不存在 R240 / 声称条数≠实际 items 数 /
      未登记的裁决数据文件），`--selftest` 扩到 **十类**合成篡改全抓；判据自身两次假红已修并写进注释：
      ① 用"段里出现（如 "当占位符 → 已填实的表被误判 ② 对所有登记文件比 items 长度 → 把
      `vendor-manifest.json` 的「3 条」当成 3 个样本 ⇒ 分母混用。教训同族：**判据错、不是数据错，先修判据**

- [x] 回归：`repo_config --online` 7 项全 PASS、`--selftest` 十类全抓；全量电池 `--slice 0 14` 14/14 + `--slice 14 28` 14/14 ⇒ **28/28 rc=0**
