# 07 分卷 56 — 上游余额耗尽（r54 收尾时的一手直证，当前最高优先阻塞）

> 从 part55 拆出（R161 单卷 ≤4,096 B）。

## 附：上游余额耗尽（r54 收尾时的一手直证，P0 级环境阻塞）

```
curl -X POST http://127.0.0.1:8123/api/chat -d '{"messages":[{"role":"user","content":"hi"}],"max_tokens":4}'
→ {"error":{"message":"Insufficient Balance (request_id: 44b85548-...)","type":"unknown_error"}}  HTTP 402
```

- 本轮三条判红（`api_contract` C4、`safety_guard` 13 项里的注入样本、`public_check` 的 14 条 console 402）
  **真因都是这一条**，不是 r54 的 CSP/外提改动：同一批套件在 r53 电池里 82/82 全绿，间隔不到 30 分钟。
- 电池为此新增第四档 `ENV-QUOTA`（`split_quota` + `quota_selftest` 5/5 双向桩）：签名匹配的是
  **响应体原文**而不是套件名，所以 `api_contract` 自动归未验；而 `safety_guard`/`public_check`
  的失败行**只印状态码不印响应体** ⇒ 仍留 RED（刻意保守：`402` 本身不是"计费"的证据，
  真契约缺陷也会回 402 类状态）。**下一轮的修法不是放宽签名，而是让这两条套件把响应体带进
  失败明细**（fail 行缺原文 = 判据答不出"哪一条 FAIL"，本来就是 r28 在册的老问题）。
- 归老大：DeepSeek 账号充值或换 Key（只走环境变量 `DEEPSEEK_KEY`，禁入库/禁进前端）。
  距离 iCAN 提交截止 2026-09-30 剩 3 天，"在线大模型生成"这一屏是演示主证据 ⇒ 这是当前**最高优先阻塞**。
