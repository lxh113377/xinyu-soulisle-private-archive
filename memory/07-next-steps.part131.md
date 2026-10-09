# 07-next-steps.part131 — r101 收口与 r102 入口（2026-10-09）

> 建卷理由：r101 收口批（本卷实测 3,269 B）；主壳只留指针，防 07 主壳继续膨大。

## P0 — r102 必须做（按优先级）

- [ ] **把 12 条 `debt-open` 定长等待改成完成态等待**（耦合尺 C1_HARD 从 22 往下走的唯一正解）。
      靶子：`public_check.py:51/55/59`、`stream_contract.py:124`、`j2_chat_contract.py:46/50`、
      `j4_memory_check.py:101`、`clean_clone_check.py:122`、`emotion_wiring_check.py:162`、
      `storage_resilience_check.py:176`、`browser_check.py:70/75`。
      完成标准：`python _test/timing_coupling_check.py` 的 `C1` 严格小于 22 且基线随实测下调；
      `--baseline <现读>` 演习仍 rc=1。**禁止**改 `--baseline` 默认值来"降"（那是改尺不是改活）。
- [ ] **`ledger_age` 摘牌**：`peer_memory_probe.py` 把字段级 NA 计入 `blind/na` 声明位 + 错峰真采
      ⇒ 然后删 `NA_DIVERGE_WAIVED["peer-memory"]`。判据会自己提醒：`ledger_age --selftest` 的
      「真面自证 在册豁免每项当前确实分叉」那条在 probe 修好后转红。
- [ ] **采一轮带机器状态凭据的阶梯台账**：设 `XINYU_MACHINE=<稳定标识>` 后跑
      `perf_baseline_check.py --ramp 8,16,32,64 --ramp-reps 5 --ramp-warmup 1 --json 交付物/对标数据/perf-ramp-<当日>-a.json`
      ⇒ 让 `machine_tag` 进台账，再把跨轮对与同日静置对**分桶**重算阈值。
      完成标准：阈表出现 <50% 的档面且带反例腿（注入回退必红）。
- [ ] **peers 侧两件**（r100/r101 连续两轮顺延）：`benchmark-metrics.json` SNAP 错峰重采；
      `peer-community` 5 个 403 仓补采 —— **前置＝先给 `peer_community_probe.py` 建断点续采**
      （现无 `--repo`，而 `--repo` 语义是替换名册 ⇒ 会把 denominator 16 缩成 5，裸补采必造新失真）。
- [ ] **CHANGELOG/长行台账"吞行"常驻判据**（本轮第三次实发：我用 Edit 换 r100 条目时吞掉
      `### Fixed（r100① …）` 表头，靠 `git diff --numstat` 只有 +44 无 -M 才当场暴露）。
      正解方向：新增判据断言「标题行集合（`^#{2,3} `）只增不减」，反例腿=删一条标题必须判红。
- [ ] **`ml/data/build_dataset.py` 写侧锁 newline**（一行：`out_path.open("a", encoding="utf-8", newline="\n")`）
      ⇒ 否则下次重生数据又把 CRLF 写回工作树，`eol_parity` 那 8 项当场复发。
      属另一会话资产，本轮只登记不代改（老大 2026-10-09 批准的范围只覆盖"已入库四件归一"）。
- [ ] **`交付物/AIC/*` 13 项行尾红**归 AIC 会话自己收口（本轮命中 0 项，未代修）。
- [ ] **`A-project-handoff` 纪律 #17 死引用**：`shared_vol_commit_guard.py` 在 `D:/global_memory/scripts/`
      实测不存在（该面只有 `append_guard.py`/`volume_alloc.py`）⇒ 归全局技能治理链修，走镜像五步闭环。

## 已知红（不修不隐瞒，均非本轮引入）

第 4 次整跑现读 `132/137 rc=1`，判红 5 条／红因 3 条：
`live_sync` + `live_sync_alt`（公网 `chat-agent.js 14699⇄15225B`、`voice.js 4148⇄4798B`，
前提 = Cloudflare API Token）、`ci_status`（远端 run `37667798532` 红因即同一条漂移）、
`release_governance R1`（v1.8.1 后 6 feat／上限 5 ⇒ **到切版点**）、
`eol_parity` 13 项（AIC 会话未入库件，本轮改动命中 0 项）。

## 待老大裁决（r102 第 ⑦ 项，两条都是二选一，判据不得自选）

1. **切版还是继续攒**：切 `v1.8.2` 需 bump pom + 建 tag + 推 tag（发布动作）；
   在册顺序 = 先 tag 再整跑（否则 G12/R2a/R2c 在中间态必红）。
2. **`live_sync` 算阻塞还是 advisory**：`ci.yml:249` 的 job 标题写「不阻塞」且确有
   `continue-on-error: true`，但整跑按 rc=1 判红 ⇒ 标题与受理面互斥。改标题或改电池都行，**要人定方向**。
