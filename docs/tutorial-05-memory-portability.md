# 教程 05：记忆可携带 —— 导出、导入与「为什么它必须幂等」

> 面向：要把一段会话从 A 机器搬到 B 机器（或只想在清理前留个底）的人。
> 相关接口：`GET /api/memory/export`、`POST /api/memory/import`、`DELETE /api/memory/{sessionId}`。
> 逻辑实现：`server/src/main/java/com/xinyu/soulisle/service/MemoryPortService.java`；
> 契约与运行态对账：`docs/openapi.yaml` + `python _test/api_contract_check.py`。

## 1. 一分钟版

```bash
# 导出（sessionId 必填）
curl "http://127.0.0.1:8123/api/memory/export?sessionId=demo-1" -o memory.json

# 在另一台机器上导入（同一份文件直接喂回去）
curl -X POST http://127.0.0.1:8123/api/memory/import \
     -H "Content-Type: application/json" --data-binary @memory.json
# -> {"ok":true,"sessionId":"demo-1","inserted":37,"skipped":0,"rejected":0}
```

导入返回三个数，`inserted + skipped + rejected` 恒等于你提交的条目数。**别只看 `ok:true`**：
`rejected>0` 说明有条目不合规被丢下，那部分数据并没有进来。

## 2. 为什么导入必须幂等（这不是洁癖）

真实用法是「换台机器导一次 → 不确定有没有成功 → 再导一次」。不幂等的导入会在几秒内把历史翻倍，
而且**看起来是成功的** —— 这比导入失败更糟，因为它不会被立刻发现。

本仓的判重键：

| 类型 | 判重键 | 命中后 |
|---|---|---|
| 消息 | `(role, content)` | 计入 `skipped`，不写第二条 |
| 情绪 | `(emotion, text)` | 计入 `skipped`，不写第二条 |

同一批次内部的重复也判（两条一模一样的消息只落一条 ⇒ `inserted=1, skipped=1`）。

⚠️ **判重窗口的诚实边界**：只比对**该会话最近 500 条**（`MemoryService.MAX_LIMIT`）。
比这更老的历史不参与判重 —— 单用户演示形态下够用；要无限深度的精确去重得换唯一索引，那是另一件事。

## 3. 会被拒绝的三种情况（整批拒绝，绝不导一半）

| 错误码 | 触发 | 为什么整批拒 |
|---|---|---|
| `schema-mismatch` | `schema` 字段不等于 `xinyu-memory/1` | 换格式意味着语义变了，半新半旧的数据最难收拾 |
| `too-many-items` | 单批 > 500 条 | 防一次把库写爆，也防超大 body 的重放放大 |
| `bad-json` | 非对象 / 缺 `sessionId` | 缺 sessionId 就不知道往哪儿写 |

条目级的非法（角色不是 `user`/`assistant`、内容空白、情绪名为空）**不中断整批**，
只计入 `rejected` —— 一条脏数据不该让你丢掉整份历史。

## 4. 导出为什么要强制 `sessionId`

`GET /api/memory/export` 不给 `sessionId` 直接 400。

这是刻意的：一旦提供「不传参数就导出全库」的形态，等于给任何拿到演示地址的人开一个**全量数据下载口**。
数据权要给用户，不是给路过的人。清除权同理只作用于自己的 `sessionId`
（`DELETE /api/memory/{sessionId}`）。

## 5. 复算与判据

```bash
python _test/api_contract_check.py            # C1/C2/C3/C7 离线对账 + C4 运行态（需服务在 8123）
python _test/api_contract_check.py --base http://127.0.0.1:8130   # 服务换端口时用这个
mvn -B -f server/pom.xml test                 # MemoryPortServiceTest / MemoryPortControllerTest
```

- 幂等那条腿在 `server/src/test/java/com/xinyu/soulisle/service/MemoryPortServiceTest.java`
  （`importIsIdempotent`、`dedupesWithinBatch` 两条）。
- 端点层还有一条「读用量不花用量」的对称性断言在 `UsageControllerTest`。

## 6. 三个"看起来坏了"

1. **第二次导入 `inserted=0, skipped=N`** —— 不是失败，正是幂等在工作。
2. **导出文件里 `counts` 与数组长度不符** —— 不会；两者同源现算。若真不符，是 `limit` 被归一到 500 上限。
3. **导出的 `createdAt` 是字符串** —— 是的，导出件走 JSON 而不是 Java 时间类型，跨语言可读优先。
