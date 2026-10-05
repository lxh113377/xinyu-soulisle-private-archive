
## ④ 受理面四轮链的最终回执（本卷收尾行）

| # | 提交 | 受理面读数 | 归因去向 |
|---|---|---|---|
| 1 | `3991069`（v1.8.0 发布提交） | `CI-WATCH-GREEN`（run 37289599171，四 job success） | 发布面本身 |
| 2 | `d03e066`（收口文档） | 🔴 `CI-WATCH-RED`（run 37294500147）`BATTERY: 122/125 RED: j4_memory` | §2.10：定长 8s 押完成时刻 |
| 3 | `90d4506`（j4 修复） | 🔴 `CI-WATCH-RED`（run 37299161773）`BATTERY: 122/125 RED: data_rights`（j4 本次绿） | §2.10 追记：快照⇄导出跨时刻 ⇒ 升公共尺 `settle_wait.py` |
| 4 | `329f034`（公共尺） | 🔴 `CI-WATCH-RED`（run 37301861423）`BATTERY: 123/126 RED: disclaimer_forensics` | 我自己新写的一句「不可比」命中本轮新加的 `BOUNDARY` 词 ⇒ 补一手实测，不删词表（R263） |
| 5 | `3d99e9d`（补取证） | 🟢 **`CI-WATCH-GREEN \| 3d99e9d`**（run 37304135213，四 job 全 success）`BATTERY: 124/126 rc=2 ENV-UNVERIFIED: java_test_guard,hook_wiring`，**零判红** | 该 rc=2 两件是本仓 CI 常态（`3991069` 绿轮同样存在），如实并列报出，不并入"已验" |

- 同轮 CI 面上三件套件实测：`voice rc=0 50.8s VOICE-PASS`、`j4_memory rc=0 34.7s`、`data_rights rc=0 5.0s`。
  ⚠️ **仍不能据此说 voice 那条腿在 CI 被验过** —— 电池对 PASS 套件只留一行，`A4=SKIP|PASS` 没有读数（§2.9 更正注）。
- 本机第八轮冻结树 `124/125 RED: voice`（§0/§2.9）与 CI 的 `124/126 零判红` 是**两个面的两份读数**，
  不互相覆盖：voice 的红是本机浏览器面咬到的产品缺陷，CI 面本轮没咬到它。

## ⑤ 下一轮入口（r97）新增两条

1. **改 `交付物/*.md` 之后必须点名复跑 `disclaimer_forensics_lint --all` 再推送** ——
   本轮实测：`repo_config / ci_contract / loc_guard / verdict_exit_parity` 全绿而 CI 仍判红，
   因为 `disclaimer_forensics` 是**电池件、不在 14 条 pre-push 契约里**（契约绿≠判据全集绿）。
   若要把它升进契约，先实测 `cost_ms` 再改 `budget` 声明（"声明==各条之和"必须仍绿），禁抄数。
2. **受理面浏览器套件群的时刻耦合**：本轮已把咬到的两处升到 `_test/settle_wait.py`。
   其余含 `wait_for_timeout` 的套件未逐一普查 ⇒ r97 用一次普查把"还有哪些判据把成败押在负载上"变成读数，
   判据形态：扫 `_test/*.py` 里 `wait_for_timeout(≥3000)` 的调用点，逐条标「等的是完成态还是时长」。
