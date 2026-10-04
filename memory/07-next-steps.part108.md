# 07-next-steps 分卷 · r95①（2026-10-04 起 / 2026-10-05 收口）

> 本轮主线**不是又一轮「对标读数」，而是把「门」从「在位」变成「有牙」**。轮次跨天：
> r95 于 10-04 起了个头后**中断未提交**，10-05 续接收口；台账按「r95 一轮」记，不拆 r95a/r95b
> —— 拆轮次的代价是同一批改动被两轮各记一半，而这两半本来就互为前提。
> 本卷记 §①②，§③④⑤⑥ 见 `part109.md`。

## ① 本轮最硬的一件：**CI 全绿契约装了 5 轮，一次都没真正生效过**（P0，r90 登记至今）

```
$ git ls-files --error-unmatch -- .ci/contract.json     → rc≠0（从未入库）
$ greencheck.py run --repo-dir .
  [greencheck] UNKNOWN（契约未被 git 跟踪 ⇒ 拒绝执行（契约即代码））
  rc=0                                                     ← ⚠️
```

- `greencheck.py` 硬规矩第 2 条明写「**契约必须被 git 跟踪**，否则 runner 拒绝执行」；
  它的 `main()` 对 `run` 模式走 `return 1 if verdict == "RED" else 0`
  ⇒ **UNKNOWN 落进 `else 0` ⇒ rc=0** ⇒ `.git/hooks/pre-push` 打印
  「PASS: 契约内 blocking 检查全绿，放行推送」并 `exit 0`。
- 钩子头注自称「找不到判据时**失败关闭**」—— **实测恒放行**，不抛异常、不打警告、不留痕。
- 前一版契约另三个缺陷：`checks` 只 4 条且含 **2 组同名**（bootstrap 按 workflow *step 名*命名，
  一个 step 内跑多条命令就撞名）；CI 最重的两条（`mvn verify` / 全量电池）**全被 defer**；
  `cost_ms` **全写死 5000（assumed）**。

**根因归属**：不是忘了 `git add`，而是**「有门」与「门有牙」分家** —— 与本仓已修过的
「判据印 FAIL 却无非零退出路径」同一个根（r93 抓到 `j2_chat_contract`、r94 抓到 `j4_memory_check`，
两次都是修例不修类 ⇒ 同族第三次复发）。r78 说过「有配置 ≠ 有门」，这轮同一句话在本仓自己身上又成立一次。

**修法**：手写 blocking **14 条**（本机 `Stopwatch` 逐条实测，合计 **10,021 ms** / 20s pre-push 预算），
name 唯一、每条带实测 `cost_source`、**声明总预算 == 各条之和（可复算）**、
**每条 blocking 的脚本都在 CI 或电池里有执行位**；`deferred` 6 条逐条写明承接面。
入库后实测：`[greencheck] GREEN`，14 条全绿，rc=0，**10.1s**。

**bootstrap 为什么不能用**：`bootstrap --repo-dir .` 本轮实测 `checks=[]`（r90 同一结果）——
本仓门禁是自写电池，不是 package.json / pom.xml / Makefile 里的标准门，探测器结构上认不出
⇒ 自动生成只能得到**空契约 = 零保护还像成功了**。07 P0 原文就是「禁造空契约；须手写」。
另注：07/09 台账写的「加 run step 并 `--sweep` 复扫到 `matched==declared`」在本仓**不成立** ——
`greencheck.py --help` 实测只有 6 个子命令（panel/run/show/bootstrap/ledger/--selftest），无 `--sweep`；
该腿已由 `_test/ci_contract_check.py` 的接线腿替代。

## ② 「门恒放行」这一族，本轮是第三次撞上 ⇒ 两件常驻判据把族立起来

| 轮次 | 对象 | 形态 | 立族的动作 |
|---|---|---|---|
| r93 | `j2_chat_contract.py` | 印 `J2-CONTRACT-FAIL` 而 rc=0 | 只修那一件 |
| r94 | `j4_memory_check.py` | 类扫 90 套件又抓到 1 处（AC-OBS-10 的验收判据） | 只修那一件 |
| **r95** | `pre-push` + 未入库契约 | 钩子跑 greencheck，UNKNOWN→rc=0→打印 PASS 放行 | **`verdict_exit_parity_check.py`**（判据的判据，93 套件 defect=0）+ **`ci_contract_check.py`**（契约的判据，9 腿 / 自检 15 条） |

两条同源：**执行方按 rc 记账，而失败那一侧没被翻译成非零 rc。**
落点差异：`verdict_exit_parity` 站电池；`ci_contract` **同时站电池与契约 blocking 自身** ——
「契约是否入库」正是 greencheck/pre-push 能不能生效的前提，**门必须站在门里面**。