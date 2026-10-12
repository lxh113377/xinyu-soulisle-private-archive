# 教程 06：成本闸与性能基准 —— 让「花了多少」和「有多快」都有数

> 面向：要把它放到公网演示、担心密钥被白嫖，或想回答"这次改动有没有变慢"的人。
> 相关实现：`server/src/main/java/com/xinyu/soulisle/config/UsageLedger.java`（按日台账）、
> `server/src/main/java/com/xinyu/soulisle/config/QuotaFilter.java`（日额熔断）、
> `server/src/main/java/com/xinyu/soulisle/config/ApiGuardFilter.java`（瞬时令牌桶）。
> 判据：`python _test/perf_api_check.py`、`python _test/api_contract_check.py`。

## 1. 两道闸不是重复，是互补

| 闸 | 挡什么 | 挡不住什么 |
|---|---|---|
| `ApiGuardFilter`（令牌桶，r128） | 突发：短时间内打一大片 | **慢速持续** —— 每分钟 1 次永远填不满桶，却能一天打满 1440 次 |
| `QuotaFilter`（按日台账，r130） | 总量：一天累计到日额就熔断 | 单秒内打爆（那是上一道闸的活） |

`POST /api/chat` 是全仓**唯一真花钱**的端点，所以默认只计量它（`xinyu.quota.paths`）。
情绪识别走本地词典（危机短路后连 LLM 都不调），记忆读写只是本地库 —— 把它们也计入日额
只会白白吃掉演示期的正常预算。

## 2. 三分钟自查

```bash
curl http://127.0.0.1:8123/api/usage
# {"day":"2026-10-12","requests":812,"tokens":20431,
#  "requestLimit":2000,"tokenLimit":0,"tokensAreEstimated":true}
```

日额打满后 `/api/chat` 返回 `429`，并带三个头：`X-Quota-Day-Used`、`X-Quota-Day-Limit`、
`Retry-After`（到次日零点的秒数）。

⚠️ **`tokens` 是估算不是账单**：它是「请求体字节数 ÷ 4」的粗折，响应里 `tokensAreEstimated:true`
是明说的。别拿它对账上游账单 —— 它只用来回答"今天大概打出去多少"。因此
`xinyu.quota.daily-tokens` 默认配 **0（不限）**：在你确认能接受这个误差之前，别开它。

## 3. 逃生阀与默认值

| 配置 | 默认 | 含义 |
|---|---|---|
| `xinyu.quota.enabled` | `true` | 置 `false` 整道闸旁路（演示排障用） |
| `xinyu.quota.daily-requests` | `2000` | `0` = 不限 |
| `xinyu.quota.daily-tokens` | `0` | 估算口径，默认不开 |
| `xinyu.quota.paths` | `/api/chat` | 逗号分隔；空串 = 一个都不计量 |

## 4. 性能：先有尺，再谈快慢

```bash
python _test/perf_api_check.py --calibrate        # 只出数字，不判红（登记阈值用这个）
python _test/perf_api_check.py                    # 判红/绿，并落台账
python _test/perf_api_check.py --selftest         # 内置桩自证（零服务依赖）
```

读数是 `p50/p95/mean/max` + 一次并发腿（默认 8 并发 × 32 请求），落盘到
`交付物/对标数据/perf-api-<date>.json`。

三条使用纪律，写在代码注释里也会被后人踩：

1. **不横比**。八维对标里 peers 侧基准在册是 **0/16**（`_test/peer_perf_probe.py` 三通道现采），
   没有任何同规格基准 ⇒ 这些数只作 **self 自身趋势**，不能说"我们比谁快"。
2. **`--rounds` 别超过 20**。令牌桶容量 `burst=20`，打 30 次会有 10 次被自家闸打回 429；
   判据会把 429 单独计成 `rate_limited` 而不是 `fail`（限流是闸在正常工作，不是服务慢），
   但样本不足 60% 时它会直接判 **未验（rc=2）** 而不是拿残缺样本下结论。
3. **换产物要重新校准**。台帐里记了服务指纹（`service/stage/java/webRoot` + **`build`**）。
   `build` 是 r131 新增的**产物身份**（`jar:<名>:<摘要12>:<字节数>` / `classes:<目录>:<mtime>`），
   补它就是因为前四个字段在新旧产物上**逐字相同**——r128、r130 两次误把他人旧产物当成本轮新代码来测
   （实测坐实：8123 的 health 不带 `build`，即它跑的是旧产物）。
   实测判别：本轮新实例回 `classes:classes:1791767315194`，8123 回**无此字段** ⇒ 一眼可分。
   即便如此，换产物仍请显式重跑 `--calibrate` 并更新 `THRESHOLDS`。
4. **别紧挨着跑别的判据**。令牌桶是**服务端共享状态**：先跑 `api_contract_check`（连打 15 条接口）
   会吃掉桶，紧跟着跑基准就会看到 `429=9`（实测）——那不是服务慢，是上一个判据的余温。
   本脚本检出后会等 22s（= burst 20 ÷ 1 token/s）重跑一次；`--no-settle` 可关（用于复现该现象）。

## 5. 三个"看起来坏了"

1. **`/api/chat` 突然全 429** —— 先看 `/api/usage`：日额到了就是它。调 `daily-requests` 或等次日。
2. **并发腿 `429=0` 但 rps 忽高忽低** —— 本机负载噪声，看 p95 而不是 rps；同机同指纹才可比。
3. **`perf_api_check` 报 rc=2** —— 服务没起、或样本被限流打残。它**不会**给你一个假的绿。
