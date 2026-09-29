# 07-next-steps 分卷 · 卷88 — r81 账（二）：尺自身瘫 + 漂移档口径复现（2026-09-29）

## R81-02（本轮定位，高）主工作树对标尺 SyntaxError 瘫，且只有 CI 看得见

- `_test/benchmark_metrics.py` 工作树版 L1074 `blind_cur[0]["tree_error"] "boom"`（少比较符）⇒ 整文件 SyntaxError
  ⇒ 主树里 peers 取数 rc=1 起不来。该行语义（「树没取到 ⇒ 是**我这把尺瞎**，不得读成对手删了能力」）**是对的**，只是写坏了；
  他方 r79-D 在途的 `tree_blind_reason()` + `split_field()` 正是这一族修法，**本轮不重复修**。
- 同族第二条一手证据：我给自己 `--selftest` 夹具写嵌套转义时**当场又踩一次**（`"…\\"…"` → SyntaxError），被自己的夹具在提交前抓出。
- 现有防线 `python -m compileall -q _test`（ci.yml:26）与 `benchmark_metrics.py --selftest`（ci.yml:38）**只长在受理面**；
  本地拿尺的人第一次撞到的是 SyntaxError，而不是「哪条判据红」。⇒ 待办：把「尺的尺」做成本地入口前置，
  **落点不得进 `_test/run_all_suites.py`**（他方 r70 在途持有）。
- 本轮全部 peers 读数来自 `git worktree` 的 **HEAD 隔离副本**（取数面已在报告 §0 标明），收口时 `worktree remove` 并复验列表。

## R81-03（口径复现登记，中）实质漂移档把自己的失明写成对手退化

- 本轮 HEAD 面实测漂移 9 处 = 实质 3 + 抖动 6 + 补录 0；其中
  **`实质 Lum1104/MER-Factory docs: ['.env.example', '.github', 'README.md', 'docs', 'test'] -> []`**
  与**同一行**的「盲区点名（这些仓的 caps 不计入分母，全零不可解读为『对手没有』）：Lum1104/MER-Factory(树取数失败)」
  **自相矛盾** ⇒ caps 侧已按盲区处理，docs 侧仍落实质档。与 r77 §4.3、r78 §4.3 那条「字段级 `None -> 值` 仍落实质档」余债同源。

