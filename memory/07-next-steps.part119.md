
# 07-next-steps.part119 — ⑦ savepoint 由「恒拒」转为可跑通：项目级豁免通道上线（2026-10-05 晚）

**老大选的正是 B**（不改跨项目共享 allowlist，而是给 `noise_lint` 加项目级豁免通道）⇒ 我按「加通道而不是加豁免」实现：
共享面只多一条**通用能力**，每个仓在自己的根部放 `.noise-exempt` 声明，且**只有提交进 HEAD 的那一份生效**。

## 本仓落地面

- 新增根部文件 `.noise-exempt`（提交 `bc551ae`）：点名 `.ci`，理由=「CI 全绿契约本体（`contract.json` 必须入库，
  pre-push 钩子与 greencheck 读它）」；文件头把四条窄规则与「为何不走 `.gitignore` 那条腿」写在里面，
  下一轮不必去读 skill 源码才知道这条豁免为什么存在。
- 端到端负控制（同一条命令、同一份清单，唯一差别是提交与否）：
  | 状态 | noise 输出 |
  |---|---|
  | 清单在工作树、未提交 | `violation:1 exempt:0` ⇒ `[GATE:noise-fail]`（**不生效**，fail-closed 成立）|
  | 清单已提交 | `violation:0 exempt:1` ⇒ `[GATE:noise-pass]`，并把 `EX .ci 理由=…` 显式印出 |
- **⑦ `handoff.py savepoint .` 由 rc=1 被拒转 rc=0**（尾行 `🎯 本次对话已安全落盘`）。
  任务 #14（待授权项）就此闭环。

## 通道为什么长成这样（牙齿清单，改的人别削）

1. 生效面 = HEAD 里那一份 ⇒ 「改一行就能在本地放行」不可能；
2. 精确名匹配，无 glob、无前缀 ⇒ 一条豁免不会顺带吃掉一片；
3. 名字里带 `/` 或 `\` ⇒ 拒（只管根部一层）；
4. 命中 `*_bak` / `*.tmp` / `*_old` / `*backup*` 等散落形 ⇒ 拒（豁免不给散落物发通行证）；
5. 生效项必须**印出来**（`EX …  理由=…`）⇒ 静默放行等于把豁免变成只有源码里知道的事；
6. 清单本体固定判 `ok` ⇒ 否则「加这条通道」这个动作本身立刻造出一个新 VIOL（自指陷阱，实测过）。

## 下一轮入口（两条，都可复算）

- `python D:/global_skills/A-project-handoff/scripts/noise_lint.py --selftest`
  ⇒ 期望 `NOISE-SELFTEST-PASS（17/17 条）`；git 不可用时期望是 `UNVERIFIED` rc=2 而**不是** PASS。
- 若再有目录被误判散落：**优先在本仓 `.noise-exempt` 加一行 + 写理由并提交**，不要往 KNOWN_CORE 手抄清单
  （同一形态已四次 R49/R281/R287/R313 —— 手抄清单必滞后于人口）。

## 本轮遗留（不隐藏）

- `global_skills` 侧提交 `c9b54e9e` 含 `noise_lint.py` + SKILL.md 3.117.0 + commands.md + version-history；
  **15:19 起 github.com:443 持续拒连，post-commit 钩子自动推送失败 8 次、我手推 6 次亦失败**
  ⇒ 本地领先远端 3 个提交未推平，`.git/push-failure.log` 有记录 ⇒ 网络恢复后必须补推并 `ls-remote` 复算。
- 首跑 selftest 抓到的是我自己两处错（实现层缓存键 + 测试层期望值），已各自修掉并在 skill 版本历史留痕；
  另一次「补丁器打印成功但实际没改到」的静默 no-op，也已当场识破 —— 记录在案防再犯。
