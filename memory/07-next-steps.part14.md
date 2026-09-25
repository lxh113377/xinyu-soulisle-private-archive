# 07-next-steps.part14.md

<!-- 本卷为 07-next-steps.part13.md 的延续 -->

- [x] 🔴 ~~**J3/J4 变现第①件：前端切 `/api/emotion`（消除情绪引擎"两份真相"）~~ → **2026-09-25 对标轮 r20 已落地并配判据**：
      新增 `src/js/emotion-remote.js`（三层开关与 J4 完全同口径：代码层 `cfg.emotionRemote === true` 默认关闭 /
      本地演示 `src/js/demo-config.js` 置 true / **公网 `deploy/xinyu/js/demo-config.js` 刻意不含**——Pages Function 无 `/api/emotion`）。
      **危机词在函数体内先本地短路，绝不为网络等待**；404/超时/响应形状不合法即熔断回落本地引擎；气泡如实标注「情绪:后端」。
      判据 `_test/emotion_wiring_check.py` **9 项 PASS**（W1 接线顺序 / W2 公网零开关 / W2b 副本一致 /
      W3 危机短路顺序 + W3b 实测 `attempted=0` 未经后端 / W4 后端路径生效且如实标注 / W5 不可达熔断不伪装 /
      W6 词典层双端同句同结论 / W7 零 pageerror）+ `--selftest` 3 类篡改全抓到（证判据非恒真）。
      本地那份 JS 引擎**按设计保留为离线降级**，未删。详见 `交付物/对标分析报告-2026-09-25.md`

- [x] **对标轮 r21（2026-09-25 同日第二轮）已落地**：① 接口契约唯一声明源 `docs/openapi.yaml`（11 条）+ 三方对账守卫
      `_test/api_contract_check.py`（C1 不缺文档 / C2 不虚文档 / C3 前端偷调即红 / C4 运行态状态码与必需键 / C5 自证）
      ② `.github/dependabot.yml`（maven@/server + github-actions@/）③ 测量装置自纠（漂移纳入 caps/docs；
      self 套件数改取 `run_all_suites.py` 条目数为唯一分母）④ 参照池 14→16。电池 **26 套件**。
      **同时勾销一处 r20 错误归因**："零构建挂不上 dependabot"→ 实测 Maven 与 Actions 两个 ecosystem 可直接挂，
      更正注在 `06-constraints.md`（原条目保留，不删改历史）。

- [x] **对标轮 r22（2026-09-25 第三轮）已落地**：本轮 16 参照仓指标**零漂移** ⇒ 差距全部来自复审自己上一轮的交付物，
      抓到两处真缺陷并修：① 契约探测原先 `done >= 8` 而真实操作 11 条（阈值低于总量即掩盖），现 C6 精确对账
      `探测+豁免==操作数` + C6b 零豁免，`docs/openapi.yaml` 补齐 3 条 `x-live-check`（探测 8 → 11 全覆盖）；
      ② 新增 `_test/repo_config_check.py`（G1 dependabot schema/目录可达、G2 CI job 数==README 声称、
      G3 契约被索引引用、G4 电池条目数==README 声称、G5 `--online` 默认分支受理面）——**上线当场抓到真实脱节**：
      加 2 条套件后 README 仍写 26，G4 报「实测 28、声称 26」，改文档转绿（红→绿即判别力证明）。
      电池 26 → **28** 套件；G5 实测 dependabot 在默认分支可见。

- [x] **对标轮 r23（2026-09-25 第四轮）已落地**：外部数据零漂移 ⇒ 转做"强制项空壳"排查，实测
      `memory/06-constraints.md` 的 R196「测试专用文件清单」**至今是 init 模板占位符** ⇒ 评测红线从未落地
      （评测集 73 条 / 98.6% 是要进答辩材料的数字）。填为登记表（文件/条数/裁决读取方/provenance/冻结状态，
      并写明真实对话走 `chat_message` 表、与评测集物理分离、禁止回流刷分）+ 新增判据 **G8**
      （占位符残留 / 登记文件不存在 / 声称条数≠实际 items 数 / 未登记的裁决数据文件），`--selftest` 十类全抓。
      判据自身两次假红（泛指括号示例、vendor 台账按样本计数）已修并写明原因：**判据错先修判据，不改数据凑绿**。
      回归：`repo_config --online` 7/7、电池 14+14 ⇒ **28/28 rc=0**。
