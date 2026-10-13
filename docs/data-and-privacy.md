# 数据与隐私（r44 起有常驻判据）

心屿存的是**情绪记录与原话对话**，按个保法口径属敏感个人信息。这一页只写实测得到的能力，不写形容词。

| 权利 | 现在怎么做 | 谁能核验 |
|---|---|---|
| 知情 | 第四幕披露语按运行模式实时翻转：开 `remote` 时明写「会同步到本演示实例的服务端」，关时明写「只留本机、不上传」——两态互斥，不存在"永远说不上传"的那一版 | `_test/data_rights_check.py` D1a/D1b（双向断言） |
| 删除 | 「清除我的数据」= 清本机 + 调 `DELETE /api/memory/{sid}`，**再读 `/api/memory/stats` 复核归零**，回执写明「服务端已删 N 条，复核为 0」 | 同判据 D2a/D2b/D2c（UI 回执与独立 HTTP 通道各测一次） |
| 可携 | 「导出我的数据」打包服务端情绪/对话 + 本机 localStorage 为一个 JSON，条数须与 `/stats` 对齐 | 同判据 D3 |

实测回执样本（✅ 2026-09-27 08:4x）：`本机已清除 ｜ 服务端已删 3 条，复核为 0`。

## 已知边界（不藏）

- **无账号体系**（决策 #4）⇒ 会话身份是浏览器内生成的 `sessionId`，换设备即换身份。
  跨设备"记得你"靠的是同一个 sessionId，不是用户鉴权；私有部署要先加账号层才谈得上多用户数据隔离。
- **公网版刻意不开 remote**：Pages / CloudBase 只有 `/api/chat`、没有 `/api/memory`，
  开了只会给评委看到 404，所以公网那一份数据本就只留在访问者本机。
- 服务端 H2 文件库（`server/data/`）**无自动留存策略与到期清理**，由部署方自行约定；
  schema 变更目前只有 `schema.sql` 全量脚本，**无版本化迁移工具**（peers 侧实测同样只有 1/16 有）。
- README 尚无「数据与隐私」指针行：README 受 16,384B 注入预算约束（现 16,364B，余 20B），
  加行须先精简他处 ⇒ 已登记 P1，见 `memory/07-next-steps.part38.md`。

## 成本与滥用敞口（r168 补，两条线分开写，边界带取证命令）

这一节的存在理由：本页此前的四条边界都关于「用户数据」，而「这把 Key 能被谁花掉多少」一直没写。
`/api/chat` 是本仓唯一真花钱的端点，所以它的防护面必须和权利面一样**逐条可核验**，
不得用一句「已做限流」顶替一整维的测量。

| 暴露面 | 现在有什么 | 压得住什么 | **压不住什么（如实写）** | 取证 |
|---|---|---|---|---|
| v2 Java 服务端 `POST /api/chat` | 令牌桶（`ApiGuardFilter`，默认 60/min、桶容量 20）+ 按日总量闸（`QuotaFilter`+`UsageLedger`，默认 2000 次/日，token 维默认关）+ 256 KiB 请求体上限 | 单实例内的瞬时打爆 **和** 慢速长期白嫖 | 多实例不共享计数；token 数是「字节/4」粗估（`/api/usage` 自报 `tokensAreEstimated=true`） | `python _test/server_hardening_check.py`（H1/H2/H5）＋ `mvn -B -f server/pom.xml test`（`ApiGuardFilterTest`/`QuotaFilterTest`/`UsageLedgerTest`，零密钥零公网） |
| **v1 公网线**（Cloudflare Pages Function `deploy/functions/api/chat.js`） | r168 起有**按 IP 次数上限**（默认 30 次/分/IP，`LLM_MAX_PER_MIN=0` 关闭），命中回 429 + `Retry-After` + `X-RateLimit-*` | 同一个 IP 在**同一个 isolate 活着的时候**猛打 | ① **无持久层**：isolate 冷启动即归零；② 换 IP 即绕开；③ **没有按日累计**（要 KV/D1 绑定 ⇒ 属对外发布动作，r130 §9 选项①，本项未做）；④ 同 NAT 出口会互相挤占额度 | `python _test/v1_cost_guard_check.py`（8 场景 61 条读数，node 里假 fetch+假时钟驱动真函数模块，零公网零密钥）＋ `python _test/api_egress_headers_check.py`（429 那条出口的安全头与契约形状，含摘头反向腿⑧） |

> ⚠️ **公网面此刻仍未重新发布**：上表写的是 `deploy/functions/api/chat.js` 的**源码**状态。
> 线上海报版本要等下一次发布才带上这道闸（发布属对外动作，须老大点头）。
> 复核线上到底有没有：`curl -s -o /dev/null -D- -X POST https://xinyu-soulisle.pages.dev/api/chat -H 'content-type: application/json' -d '{"messages":[]}' | grep -i x-ratelimit`
> —— 读不到 `X-RateLimit-*` 就说明线上还是旧函数，本节描述的是源码而非线上。

复算：`python _test/data_rights_check.py`（8 条断言全绿）；`python _test/data_rights_check.py --selftest`（9 例）；
`python _test/peer_data_rights_probe.py --selftest`（10 例）；成本面见上表最后一列的两条命令。
