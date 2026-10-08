## r100 收口（2026-10-08 对标增量轮 · 四项改造，含一条负面结论）

### 一手教训（三条会再犯的）

1. **命名纪律会让"相邻两份"变成"首尾两份"**：`ledgers()` 按 `(日期, 字典序)` 取相邻两份，而 `.`(0x2E) > `-`(0x2D)
   ⇒ 当天第一份写成无后缀就排到最后，实测产出 2 条 `t16 p95 +67.9%` **假红**。正解＝同日多份一律 `-a`/`-b`… 递增。
2. **LOC 门与普查尺打架**：为过 ≤150 行/函数把 `wait+read` 提进 helper，`timing_coupling` 就把那两处从
   `C1_HARD` 改判 `READ_NO_DECIDE` ⇒ **提取函数成了一条降噪通道**。基线 9 未动（现读 6），余量 3 是
   **没锁住的余量，不是成绩**。
3. **新写的产物会掉进别的尺的分母**：我把噪声汇总件命名成 `perf-ramp-noise-2026-10-08.json`，撞进
   `perf_ramp_delta_check.py` 的 glob `perf-ramp-*.json` ⇒ 漂移尺把它当"最新台账"，整跑电池当场
   `ENV-UNVERIFIED: perf_ramp_delta`。正解不是只改名：加 `is_ramp_ledger()`（坏 JSON 仍算台账＝fail-closed，
   `ramp=null` 算非台账但必须被 `foreign_files()` **出声点名**）＋ 六向分母自卫桩（selftest 34→40）。
   ⇒ 立一条纪律：**新写产物前先 grep 它的名字落在谁的 glob / 分母里**。

### r101 入口（四条，前提命令可复算）

- 🔴 **按档定阈**（数据已给全，**无需再采样**）：t32/t64 由 `相邻轮最坏差 × ~2` 推每档阈值
  （16.6%→约 34%、9.2%→约 19%），t8/t16 走 NA(noise-floor)；根子＝台账**没有机器状态字段**。
  取数面 = `交付物/对标数据/perf-ramp-noise-2026-10-08.json`。
- 🟠 `timing_coupling` 被审面扩到**跨函数返回值的消费者**；验收＝两处定长回到 C1_HARD（现读应从 6 回 9）。
- 🟠 r99 §6 登记的**假理由普查**（注释里的"为什么不接线"句 ⇄ 该件实际 import/网络调用），需新尺 + 反例腿。
- 🟢 `peer-community` 403 面补采（5 仓）；验收 `LEDGER-AGE-PASS` 且 degraded=0。
- ⏸ **v1.8.1 推送链仍 blocked**（Pages 面拦在 Cloudflare API Token）：`live_sync` 现点名两件
  `chat-agent.js 14699→15225B`、`voice.js 4148→4798B`；前提 = 老大给 CF Token。
  本轮**不发版、不打 tag、不改 pom 版本**（v1.8.1 已在远端）。
