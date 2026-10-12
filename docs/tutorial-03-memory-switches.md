# 教程 03 · 记忆三层开关（"跨设备记住你"要按哪个开关才成立）

> 这是本项目最容易被夸大成"已经做了"的一项能力。真相是：**代码层有、演示层开、公网层刻意不开**。
> 三层各归各的判据，混一层说就是虚报。

## 1. 三层开关分别在哪

| 层 | 位置 | 现值 | 含义 |
|---|---|---|---|
| 代码层 | `src/js/memory-store.js` 的 `isRemote()` | `cfg().remote === true && !remoteDown` | 只有显式 `remote: true` **且**本会话没熔断，才走服务端 |
| 本地演示层 | `src/js/demo-config.js:19` | `remote: true` | 本地 / fat jar 环境（Java 同时托管前端与 `/api/memory/**`）⇒ 开 |
| 公网层 | Cloudflare Pages / CloudBase 部署 | 不开 | 线上只实现了 `/api/chat`，**没有** `/api/memory/**` |

公网层不开的理由是实测的，不是保守：默认开启会让评委的浏览器控制台出现 404，
并直接顶掉 `_test/public_check.py` 的 `CONSOLE_ERRORS: 0` 断言。
（原话留在 `memory-store.js:18-23` 的注释里。）

## 2. 熔断：失败一次就别一直吵

`markDown()` 把 `remoteDown` 置真，之后本会话不再尝试。触发两种情况都算：

- **404** = 服务端根本没这个接口（公网双线就是这种）；
- **网络失败** = 服务端不在。

这一条的价值不是"优雅降级"，而是**避免持续噪音**：没有熔断，每一轮对话都会再撞一次墙、
再进一次控制台报错，而 `public_check.py` 数的正是控制台报错。

## 3. 复算：记忆真落库了吗

```bash
python _test/j4_memory_check.py      # 核心断言：清空 localStorage 后刷新，星图仍点亮
curl -s localhost:8123/api/memory/stats   # 计数；重启服务后应不变（H2 file，不是内存库）
```

`j4_memory_check.py` 的关键断言就一句话：**把浏览器本地存储清空，服务端还得记得你**。
只做"存进去了"不叫持久化——那可能只是 `localStorage` 在替服务端领奖。

> 为什么默认是 `server/data/xinyu.mv.db`（H2 **file**）而不是内存库：内存库重启即丢，
> 不算持久化，也就撑不起这条判据（决策记录 #3 的落地差异）。

## 4. 对外怎么说这句卖点（红线）

- ✅ 「本地/私有部署打开开关后，跨浏览器、跨重启都能记住你（判据 `j4_memory_check.py` 可现场复跑）」
- ❌ 「我们已经跨设备记住了」——公网层没开这个开关，这句话在线上不可复现。

同理，`src/js/voice.js:116` 明确写了：**语音的三层开关口径与 J4 记忆不是同一件事，不得混为一谈**。
两个都叫"开关"，但一个管声音能力的可用性，一个管记忆写向哪里。

## 5. 相关决策与文档

- `memory/AGENTS.md` — J4 三层红线（决策 #3）
- [`API.md`](API.md) / [`openapi.yaml`](openapi.yaml) — `/api/memory/**` 的契约面
- [`data-and-privacy.md`](data-and-privacy.md) — 存了什么、存在哪、怎么清
