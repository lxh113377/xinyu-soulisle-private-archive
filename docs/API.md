# 心屿 MindIsle API 手册（人类可读版）

> 机器契约唯一真相源 = `docs/openapi.yaml`（16 路径，`_test/api_contract_check.py` 强制：文档不缺/不虚/前端不偷调/运行态一致/零豁免探测，
> 并自 r89 起**把本手册也钉进对账**（C7：yaml 每条路径必须在本文件出现、本文件不得虚报接口、上方路径计数必须等于实值）——
> 手册此前"没有任何读者"，yaml 一改它就静默过期）。
> 基地址：本地 `http://127.0.0.1:8123`；公网 Pages 只有 `/api/chat`（其余接口不在此形态暴露）。

## 1. 健康自证 `GET /api/health` → 200

`curl http://127.0.0.1:8123/api/health`
回 `{status,indexFound,vendorFound,webRoot,stage,java,build}`；`indexFound/vendorFound` 双 true 才算静态源命中。
`build` 是 **r131 加的产物身份**（`jar:<名>:<摘要12>:<字节数>` 或 `classes:<目录>:<mtime>`）——
`service/stage/java/webRoot` 在新旧产物上逐字相同，**只有它能回答「这个实例跑的到底是哪份产物」**
（r128、r130 两次栽在「以为测的是新代码，实际打的是他人旧 jar」）。

## 1b. 数据库面自证 `GET /api/health/db` → 200（r169；r179 补进契约与手册）

`curl http://127.0.0.1:8123/api/health/db`
为什么另开一面：`/api/health` 只看 `index.html` 与 `vendor` 目录，**库整面死掉时它照样回 `status=UP`**；
而「优雅降级」的输入端正是「先知道库死了」。另一半原因是别把高健康面污染掉 ——
`/api/health` 被性能判据高频打，在那里加一次真连库往返会把「服务本身」的读数变成「库」的读数。

- 状态码**恒 200**，结论在 body：`{service,status,acquireMs}` 两态都在；UP 另有
  `product/productVersion/driver/tables/charset/pool`，DOWN 另有 `error`（异常类名，不外泄堆栈）。
  本端点**永不抛** —— 探测失败本身就是它要报告的内容，抛出去等于把唯一一次读数机会弄丢。
- `tables` 用「一次列全表 + 大小写不敏感比对」而不是 `getTables(名)` 逐张探：
  H2 把未加引号标识符折成大写（`CHAT_MESSAGE`），MySQL 在 Linux 区分大小写，逐张探会在 H2 侧得到「两张表都缺」的假红。
- `pool` 取连接**之后**才读（HikariCP 惰性建池，先读会把刚初始化的池报成 unverified）；
  池未初始化回 `live=unverified(...)`，**不许读成「0 条连接、一切正常」**。
- ⚠️ 鉴权边界与 `/api/health` **不同**：`ApiTokenFilter` 只对 `/api/health` 精确放行，
  所以配了 `xinyu.api-token` 后本端点**需要带 token**（它回吐库版本/字符集/池水位，属运维信息，不该比业务接口更开放）。

## 2. 对话代理 `POST /api/chat`

- 请求：`{messages:[{role,content}],temperature?,max_tokens?,stream?}`；判定顺序**先查密钥再解析 body**（与 v1 一致）。
- 成功 200：上游逐字透传；`stream:true` 且上游 SSE ⇒ `text/event-stream`。
- 失败：无 key 500 `{error:no-key}`；body 非法 400 `bad-json`；上游失败 502 `upstream-error/upstream-nonjson`。
- `curl -X POST http://127.0.0.1:8123/api/chat -H "Content-Type: application/json" -d "{\"messages\":[{\"role\":\"user\",\"content\":\"你好\"}],\"max_tokens\":8}"`

## 3. 情绪识别 `POST /api/emotion`

- 请求：`{text}`（≤500 字）。危机命中**不调 LLM**（`llm=null`），分歧采信 LLM。
- 成功 200 必含 `lex,final,path`（`lex` 含 emotion/intensity/color/all/crisis）。
- `curl -X POST http://127.0.0.1:8123/api/emotion -H "Content-Type: application/json" -d "{\"text\":\"今天被导师批评了，心情很低落\"}"`
- 附带：`GET /api/emotion/lexicon`（词表四键 lex/neg/deg/crisis）；`GET /api/emotion/eval?detail=0|1`（评测集 105 条，r179 现读 `GET /api/emotion/eval` = accuracy 99.0% / crisis 6-6 / misses 1 条；手册此前长期抄 09-23 的「73 条 98.6%」，该值已由 `memory/06-constraints.md` 的 G8 条数对账更正）。

## 4. 记忆（J4，需前端 `cfg.remote===true` 才启用）

| 接口 | 用法 |
|---|---|
| `POST /api/memory/emotion` | `{sessionId,emotion,intensity?,secondary?,text?}` → `{ok,count}` |
| `GET /api/memory/emotions?sessionId=&limit=200` | 数组元素必含 emotion,intensity |
| `POST /api/memory/message` | `{sessionId,role:user\|assistant,content}` → `{ok,count}` |
| `GET /api/memory/messages?sessionId=&limit=40` | 数组元素必含 role,content |
| `GET /api/memory/stats?sessionId=` | `{sessionId,emotions,messages}`（AC-OBS-10 判据口） |
| `GET /api/memory/search?q=&sessionId=&limit=10` | `{query,pool,count,results[]}`（r128：BM25 长期记忆检索；sessionId 可省＝全库检索，score 只在本次候选集内可比） |
| `DELETE /api/memory/{sessionId}` | `{ok,removed}`（对应界面"清除我的数据"） |
| `GET /api/memory/export?sessionId=&limit=500` | `{schema,sessionId,counts,messages[],emotions[]}`（r130：数据**可携带**；`sessionId` 必填，不给就 400 —— 不开"匿名导出全库"这个口子） |
| `POST /api/memory/import` | `{schema:"xinyu-memory/1",sessionId,messages[],emotions[]}` → `{ok,inserted,skipped,rejected}`（r130：**幂等**，判重键＝消息 (role,content) / 情绪 (emotion,text)；单批 ≤500，结构性错误整批拒绝不导一半） |

## 5. 用量读数 `GET /api/usage` → 200（r130）

`curl http://127.0.0.1:8123/api/usage` → `{day,requests,tokens,requestLimit,tokenLimit,tokensAreEstimated:true}`。
`tokens` 是「请求体字节数 ÷ 4」的**粗估**，不是上游计费口径；`requestLimit/tokenLimit` 为 0 表示不限。
配合 `QuotaFilter` 的按日熔断：日额打满后 `/api/chat` 返 429 + `X-Quota-Day-Used/-Limit` + `Retry-After`（到次日零点）。

## 6. 鉴权与错误码总表

- `xinyu.api-token` 留空=全放行；置非空后缺/错头 401（`/api/health` 与静态页始终放行）。
- 通用：400 `bad-json`｜500 `no-key`｜502 上游｜404 `dataset-not-found`（仅 eval）。
