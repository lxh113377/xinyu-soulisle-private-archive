# 心屿 SoulIsle API 手册（人类可读版）

> 机器契约唯一真相源 = `docs/openapi.yaml`（11 路径，`_test/api_contract_check.py` 强制三条：文档不缺/不虚/前端不偷调）。
> 本手册是人阅读版，字段与示例逐条对 yaml + 控制器实测（`HealthController/ChatController/EmotionController/MemoryController`），yaml 改了这里必须跟改。
> 基地址：本地 `http://127.0.0.1:8123`；公网 Pages 只有 `/api/chat`（其余接口不在此形态暴露）。

## 1. 健康自证 `GET /api/health` → 200

`curl http://127.0.0.1:8123/api/health`
回 `{status,indexFound,vendorFound,webRoot,stage,java}`；`indexFound/vendorFound` 双 true 才算静态源命中。

## 2. 对话代理 `POST /api/chat`

- 请求：`{messages:[{role,content}],temperature?,max_tokens?,stream?}`；判定顺序**先查密钥再解析 body**（与 v1 一致）。
- 成功 200：上游逐字透传；`stream:true` 且上游 SSE ⇒ `text/event-stream`。
- 失败：无 key 500 `{error:no-key}`；body 非法 400 `bad-json`；上游失败 502 `upstream-error/upstream-nonjson`。
- `curl -X POST http://127.0.0.1:8123/api/chat -H "Content-Type: application/json" -d "{\"messages\":[{\"role\":\"user\",\"content\":\"你好\"}],\"max_tokens\":8}"`

## 3. 情绪识别 `POST /api/emotion`

- 请求：`{text}`（≤500 字）。危机命中**不调 LLM**（`llm=null`），分歧采信 LLM。
- 成功 200 必含 `lex,final,path`（`lex` 含 emotion/intensity/color/all/crisis）。
- `curl -X POST http://127.0.0.1:8123/api/emotion -H "Content-Type: application/json" -d "{\"text\":\"今天被导师批评了，心情很低落\"}"`
- 附带：`GET /api/emotion/lexicon`（词表四键 lex/neg/deg/crisis）；`GET /api/emotion/eval?detail=0|1`（评测集 73 条，现值 accuracy 98.6%，crisis 6/6）。

## 4. 记忆（J4，需前端 `cfg.remote===true` 才启用）

| 接口 | 用法 |
|---|---|
| `POST /api/memory/emotion` | `{sessionId,emotion,intensity?,secondary?,text?}` → `{ok,count}` |
| `GET /api/memory/emotions?sessionId=&limit=200` | 数组元素必含 emotion,intensity |
| `POST /api/memory/message` | `{sessionId,role:user\|assistant,content}` → `{ok,count}` |
| `GET /api/memory/messages?sessionId=&limit=40` | 数组元素必含 role,content |
| `GET /api/memory/stats?sessionId=` | `{sessionId,emotions,messages}`（AC-OBS-10 判据口） |
| `DELETE /api/memory/{sessionId}` | `{ok,removed}`（对应界面"清除我的数据"） |

## 5. 鉴权与错误码总表

- `xinyu.api-token` 留空=全放行；置非空后缺/错头 401（`/api/health` 与静态页始终放行）。
- 通用：400 `bad-json`｜500 `no-key`｜502 上游｜404 `dataset-not-found`（仅 eval）。
