# 07-next-steps 卷69 — r69（一次崩溃暴露：回归锁按 TTL 判死 + 运行器不会报耗时）

> 取号 `volume_alloc.py`（O_EXCL）｜报告 `交付物/对标分析报告-2026-09-28-r69.md`

## 一、一手现场（差距是我自己撞出来的，不是 peers 给的）

peers 同日两次整面重采**实质漂移 0** ⇒ 本轮无可抄项，镜头转内因。随后我自己的补丁崩了一次
`NameError`：`"import time" in t` 被 `import timeit` 之类子串**假命中**，我的存在性断言等于没断言。
崩溃后运行器把后续整跑挡了 30 分钟：

- `BATTERY-UNVERIFIED(并发): pid=18600 起于 33s 前，未到 TTL 1800s`
- 而 `tasklist //FI "PID eq 18600"` 实数 **0 个进程** ⇒ 锁的属主根本不存在
- 它给的绕行提示"或用 `--only` 子集"**实测同样 rc=2** ⇒ 提示与行为不符

## 二、修了三条

1. **锁按属主存活判陈旧**：`pid_alive()`（Win `OpenProcess` / POSIX `os.kill(pid,0)`）；
   **探测失败一律按"活着"** ⇒ 这条改动只能变严、不能变松；崩溃残留自动放行。
2. **夹具不得读本机状态**（自查发现，未等它翻红）：既有反例 `lock_state("8<TAB>999.5", …)`
   用裸 pid 8，加判活后其结果取决于**这台机器上 pid 8 在不在** ⇒ 正反两例都注入 `alive` seam，
   并补 `r69 正例 属主已死的锁必须放行`。`--selftest` **7/7**；
   **变异对照**＝摘掉判活那一步 → `LOCK-SELFTEST-FAIL: r69 正例 属主已死的锁必须放行（6/7）`，
   真实源跑前跑后 sha 相等、副本清零。
3. **运行器开始报耗时**：此前整跑日志全文只有 1 行含时间样式 ⇒ r68 那条"先出耗时分布再谈并行"
   根本取不到读数。现套件行带 `0.1s`，收口前印 `耗时 top5 ｜ 合计 Ns ⇒ 并行方案只能在这个读数
   存在之后才提`。切片 `--slice 0 4` 实跑验证（`perf_baseline=1.3s` 等）。

## 三、复算

- `python _test/run_all_suites.py --selftest` → `LOCK-SELFTEST-PASS（7/7 类桩）`
- `python _test/run_all_suites.py --slice 0 4` → 套件行含秒数 ＋ 耗时 top5 行
- 回收死锁：`cat %TEMP%/xinyu_battery_<sha1前12>.lock` 取 pid → `tasklist //FI "PID eq <pid>"`
  数到 0 即确认可回收（**先验归属再删**，别拿 `rm` 当默认动作）。

## 四、未闭合（不折叠）

全量耗时分布本轮未取（下轮读 `耗时 top5` 后再决定并行度；无分布不得动闸）｜
`live_sync`／`ci_status` 待对外发布授权｜flake 对标缺原文｜peers 跨日必须重采。
