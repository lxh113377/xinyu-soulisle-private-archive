# 05-feature-status.part6.md

<!-- 本卷为 05-feature-status.part5.md 的延续 -->

## 📋 计划中

- [x] **判据化**：`repo_config_check.py` 新增 **G8**（模板原句残留 / 登记文件不存在 R240 / 声称条数≠实际 items 数 /
      未登记的裁决数据文件），`--selftest` 扩到 **十类**合成篡改全抓；判据自身两次假红已修并写进注释：
      ① 用"段里出现（如 "当占位符 → 已填实的表被误判 ② 对所有登记文件比 items 长度 → 把
      `vendor-manifest.json` 的「3 条」当成 3 个样本 ⇒ 分母混用。教训同族：**判据错、不是数据错，先修判据**

- [x] 回归：`repo_config --online` 7 项全 PASS、`--selftest` 十类全抓；全量电池 `--slice 0 14` 14/14 + `--slice 14 28` 14/14 ⇒ **28/28 rc=0**

- [x] **`src/js/voice.js` 外提**（`app.js` 471 → 403 行，语音 99 行独立模块）：
      `window.Voice = { init(), speak(), isSpeaking() }`；保留原三条约束注释（不支持即隐藏 / 异常一律吞掉不带崩主链路 /
      开关走独立键 `peiliao.speak.v1` 不进 `cfg`）。选它当第一刀的理由是**与编排零耦合 + 判据最密**
      （`ux_guards` U1 实测 utterance 构造计数与开关、`voice_check` A1-A6 盯 ASR 与按钮）
