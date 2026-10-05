# 07-next-steps.part113 — r96 收口最终回执 + voice 改判（2026-10-05）

## ① 第八轮电池 = 发布提交冻结树上的最终回执

- 复算：`python _test/run_all_suites.py --exclude-llm`（日志 `交付物/对标数据/bench-r96-battery8.log`）
- 读数：`BATTERY: 124/125 rc=1 RED(判红，必须修): voice`｜合计 **734s**｜恒等式 实跑 125 + 豁免 3 == 128 ✓
- 冻结性取证：跑前跑后 `git status --porcelain` 只剩电池自身日志（未跟踪件），**跑电池期间不编辑任何在跟踪件**
  —— 这条是本轮作废第 1、6 两轮回执后立的规矩。
- ⇒ **r96 收口没有拿到 ALL-GREEN**。第四轮的 `125/125` 是**切版前的树**，不得当发布提交的回执引用。
- 受理面：`CI-WATCH-GREEN | 3991069c | 全部 run success（1 条）`（run `37289599171`，四只 job 全 success）。

## ② voice 由「在册 flaky」改判为「产品真缺陷」（新增 P1，待老大）

一手取证（同一台机器、jar@8123 内嵌版本 1.8.0）：

| 面 | 读数 |
|---|---|
| 第八轮电池 | `A5 卡在监听态，未恢复（8s 内 class=recording 未移除）` |
| 单跑 1 / 2 | `VOICE-PASS`（`ev=['start','audiostart','result:n=1','end']`，`stopped:1`）|
| 单跑 3 | `VOICE-FAIL`，`hook(final)={constructed:True, started:1, stopped:1, ev:['start','audiostart']}` |

**决定性一条 = 失败那次的 `stopped:1`**：`recognition.stop()` 确实被调用过（点击落到了按钮上），
但浏览器始终没回吐 `end`；前端退出监听态**只挂在 `onend`/`onerror` 上** ⇒ `class=recording` 永不摘除
⇒ **用户侧症状 = 点过语音按钮后卡在"正在听"，只能刷新页面恢复**。

- 排除的两个假因：① 不是"我的点击没落"（`stopped:1` 证伪）；② 不是电池负载（单跑第 3 次同样红，单跑比电池更空）。
- **判据不动**：`_test/voice_check.py:172` 的 8s 上限保持原值 —— 这条红恰恰证明它有牙。不加重试、不放宽预算。
- **受理面从未覆盖这条腿**：CI 无音频输入设备 ⇒ A4 走 SKIP（`voice_check.py:161`），跑不到 A5。
  ⇒ "CI 全绿"在这条判据上不等于"验过"。这是它能以 flaky 名义活过 r94/r95/r96 三轮的原因。
- 取数自纠：第一次单跑我**漏传 base**，`voice_check.py:14` 缺省落到 `http://127.0.0.1:8125/`
  ⇒ `net::ERR_CONNECTION_REFUSED`，与 r95 记的「用法错」同形态。**那次不算 voice 的红**；
  复算命令必须带 base：`python _test/voice_check.py http://127.0.0.1:8123`。
- **为何本轮不修**：修复属 `src/` 行为码 ⇒ 破本轮「`src/` `server/` `deploy/` 零改动」红线，
  且 v1.8.0 已发布、动它要重新切版。列 **P1 待老大决定**（报告 §3 #9 已给二元完成标准：
  带 base 单跑 5 次全 rc=0 + 新增一条"桩里 `stop()` 后不派 `end` ⇒ 按钮仍必须复位"的控制腿）。

## ③ 本轮与计划的偏离（两处，如实登记）

1. **`ledger_age` 未进 `.ci/contract.json` 的 blocking**（计划完成标准写的是 `checks=15`）。
   实测现值 `CI-CONTRACT-PASS: tracked=True checks=14(blocking) deferred=7 … 问题=0` —— 它被放进 **deferred**
   （`ledger-age-fuse`）。理由：pre-push 预算里塞一条"任何正常提交都变不了绿"的门 = 会把整条契约训练成噪声；
   新鲜度这件事已由 `ledger_age` **进电池**（第 125/128 条）拿到执行位。
2. **peers 侧未做全量 burst 重采**（详见报告 §5）：12 探针 burst 已实测撞 secondary rate limit，
   降级件一律改道 `_partial/` 不覆写基线。
