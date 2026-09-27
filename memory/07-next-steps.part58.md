# 07-next-steps 卷58 — r57 补记（CI 回执之后又做的一格）

> 取号：`volume_alloc.py`（O_EXCL 独占）｜与卷57 同轮，卷57 已近 4,096B 封顶，故另起一卷不削内容

- `repo_config_check.py` 新增 **G16**：电池 `SUITES` 现读的 **59 条** `_test/*.py|js` ⇄
  `docs/quality-gates.md` **双向**对账（电池有、文档无 ⇒ 红；文档写了、`_test/` 查无此件 ⇒ 也算红）。
  首跑抓到 **26 条判据从未在该文档在册**（先 16 条非 selftest 套件，补完再抓 10 条：
  `ci_watch`/`lightshow`/`pixel_dual`/`server_preflight`/`voice` + 五支 `peer_*_probe`），
  这条盲区活了 **15 轮**无人报警。
  根因不是"文档没数字"（它头写着"本文件不抄数"，数字确实没骗人），而是它作为从 README 迁出的
  「判据体系明细」被当作清单读 ⇒ 同族 **M5⑥ 一个清单两处实现**。
  四腿自证（`--selftest` ㉑a–㉑d）：正向拿**真文档真电池**跑（防误伤）／抹一条真判据必红／
  写一条幽灵必红／分母取空不得判绿。
- `push_and_watch.sh` 把两种红分开：`ENV-QUOTA(` 有而 `RED(判红` 无 ⇒ 印
  「零判红 + 处置动作只有老大能做 + 记未验禁写全绿」，不再一律"按指令修"。
  取证用两份**真实**日志双向跑过：`pw57c.txt`（84/85 仅 quota）走 quota 支、`pw57.txt`（含真红）走修判据支。
  ⚠️ 改 `tee` 落盘后退出码必须取 `${PIPESTATUS[0]}` —— 实测 `false | tee` 之后 `$?` = 0（tee 的码）。
- git **幽灵脏件**（`status` 报 M、`git diff` 空、三方 OID 全等）：`--refresh`/`--really-refresh`
  对它不落地，`git update-index --add <path>` 才治好（内容相同 ⇒ 纯重取 stat，index OID 不变）。
  修法与前置判据见项目记忆 `reference-git-stat-cache-phantom-dirty.md`。
- ⚠️ **`feats` 现为 5/5、余量 0**：下一个 `feat` 提交会被 R1 拦红。正解 = **先手工切 v1.6.1**
  （`release_cut.py` 自 r45 挂账未做），**不是抬上限**。这是 r58 的第一件实事。
- 下一格（沿用卷57 未做清单，优先级不变）：`headers_csp_check --live-api`（含反向腿，接 CI 出 rc=2 单列）
  → `deploy_sync_check` 扩到 `deploy/functions/` → `/api/emotion` 挂起注入 → 真机复跑或正式收敛。
