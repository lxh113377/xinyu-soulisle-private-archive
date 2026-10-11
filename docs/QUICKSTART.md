# 快速上手（QUICKSTART）— 心屿 MindIsle

> 面向**第一次拿到这份代码的人**：三条起步路 + 每条路的"起来了"判据 + 十分钟内能自己复算的验证。
> 与 `../README.md`「快速开始」的分工：README 给最短命令，本文给**为什么这么起、起不来先看哪一条**。
> 所有命令都在**仓库根**执行（工作目录不是仓库根时，服务端直读 `./src/` 会 404 —— 见决策 #2）。

## 0. 前置（一次就够）

| 项 | 值（本机实测） | 为什么必须写死 |
|---|---|---|
| JDK | **17**：`C:\Program Files\Eclipse Adoptium\jdk-17.0.20.101-hotspot` | 系统默认 `JAVA_HOME` 指向 **JDK 8**（课程作业用），不显式切换 → Spring Boot 3.2.5 直接编译失败 |
| Maven | `%USERPROFILE%\.local\maven\apache-maven-3.9.9\bin\mvn` | **不在 PATH**，必须写全路径 |
| 前端 | 无需 npm/构建 | 零构建纯静态，`three`/`gsap` 已本地化进 `src/vendor/`（离线可完整演示） |

```powershell
$env:JAVA_HOME = "C:\Program Files\Eclipse Adoptium\jdk-17.0.20.101-hotspot"
```

## 1. 路 A：只看前端（最快，30 秒）——离线模式

```powershell
python -m http.server 8123 --directory src
# 浏览器打开 http://localhost:8123
```

- 此时**没有** `/api/*`：情绪走本地词典引擎，回复走离线共情模板，界面会**明示**是模板而不是"在线 AI"
  （红线：禁止把模板伪装成在线）。
- `src/js/demo-config.js` 在 clone 里**本来就不存在**（含真实 Key，被 `.gitignore` 排除）。
  缺它 = 正常状态，不是故障；要在线请看路 B 或下面的「给密钥」。
- 公网副本在 `deploy/xinyu/`（零密钥同源代理版）—— **永远不要用 `src/` 版覆盖它**。

## 2. 路 B：fat jar（含全部服务端能力）——推荐

```powershell
# 打包（test 阶段会跑构建期单测 + 覆盖率门 LINE/BRANCH ≥ 0.90，别加 -DskipTests）
& "$env:USERPROFILE\.local\maven\apache-maven-3.9.9\bin\mvn" -f server/pom.xml package

# 起服务：工作目录必须是仓库根（静态页直读 ./src/，零第三份副本）
java -jar server\target\soulisle-server.jar --server.port=8123
```

**判"起来了"（可复核，不是肉眼看页面）**：

```powershell
curl -s http://127.0.0.1:8123/api/health
# 期望：status=UP，且 webRoot 指向本仓 src/、indexFound=true、vendorFound=true
```

拿到 `UP + indexFound/vendorFound=true` ⇒ 托管与静态资源命中权威源（`AC-OBS-07` 就是这么验的）。
端口被占（例如并行会话正在用 8123）就换空闲端口：`--server.port=8147`，后面所有 `BASE` 跟着换。

## 3. 给密钥（三条路，按场景选）

| 场景 | 做法 | 密钥落在哪 |
|---|---|---|
| 本机演示 | 页面右上「模型设置」→ 填 Base / Model / Key → 保存 | `localStorage["peiliao.cfg.v1"]`，只在本机 |
| 评委即用（本地） | 自建 `src/js/demo-config.js` 预置配置（**该文件已在 `.gitignore` 内**） | 仅本机，绝不入库 |
| fat jar / Docker | 环境变量 `DEEPSEEK_KEY`（或 `LLM_KEY`） | 进程环境，零落盘零入库 |

三条密钥安全语义有判据逐条盯着（`_test/settings_panel_check.py` 的 S1–S8）：Key 输入框**恒不回显**已存密钥；
**留空保存 = 不改**（空输入直接覆盖会把已存 Key 洗掉）；密钥**绝不**进前端源码、镜像与提交。

## 4. 十分钟自证（改完代码想知道有没有弄坏东西）

```powershell
python _test/browser_check.py            # 离线降级链路 / 危机转介 / 情绪点亮 / 滚动淡入淡出
python _test/j2_chat_contract.py         # /api/chat 与 v1 契约 1:1（单变量对照：代理在/不在）
node _test/emotion_eval.js               # 评测集逐条复算（条数以脚本自印为准，别手抄）
python _test/run_all_suites.py --exclude-llm   # 全量电池（套件数现读；勿与他人的整跑并发，锁不可重入）
python _test/perf_baseline_check.py      # 性能基线（起 jar 后跑；含并发吞吐与进程资源占用三项）
```

判据结论只有三类，**别把第三类读成通过**：`PASS` 绿 / `FAIL` 红 / `UNVERIFIED`＝没跑到
（node 缺失、端口被占、没网、需要浏览器的腿在无浏览器机上不跑）。口径与逐条复算命令见 [`quality-gates.md`](quality-gates.md)。

## 5. 起不来 / 不对劲，按这个顺序查

1. **`Unsupported class file major version`** → 在用 JDK 8，回去设 `JAVA_HOME`。
2. **页面 404 但接口 200** → 工作目录不是仓库根，`./src/` 解析到了别处。
3. **界面显示"离线模板"** → 没配 Key 或 `/api/chat` 不可达（这是**设计要求**：降级必须显式标注）。
4. **徽章显示"配了在线却降级"** → 上游报错/超时，看 `curl -i -X POST http://127.0.0.1:8123/api/chat` 的错误体
   （`no-key` / `bad-json` / `upstream-nonjson` / `upstream-error`）。
5. **判据红但不明原因** → 先读它自己打印的红因与面别（工作树面 / HEAD 面），再决定动数据还是动判据。

## 6. 路 C：容器（部署形态）

```powershell
mvn -f server/pom.xml package
docker build -f server/Dockerfile -t xinyu-soulisle .
docker run -p 8080:8080 -e DEEPSEEK_KEY=sk-xxx -v xinyu-data:/app/data xinyu-soulisle
```

⚠️ 构建上下文必须是**仓库根**（Dockerfile 要 COPY `src/`）；本机没装 Docker 时这条路按"未实测"对待，
不要把它当默认可用。公网双线（Cloudflare Pages / CloudBase）见 `../README.md`「部署」。
