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
