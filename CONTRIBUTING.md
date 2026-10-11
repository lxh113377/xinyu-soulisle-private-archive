# 贡献指南 — 心屿 MindIsle

感谢关注！本仓库改动半径小、红线多，动手前请先读完本页。

## 环境要求

> **全新 clone 第一步**：`cp deploy/xinyu/js/demo-config.js src/js/demo-config.js`
> `src/js/demo-config.js` 持本机真实 Key，被 `.gitignore` 永久排除；但 `index.html` 用 `<script>` 静态引它 ——
> 不补就会首屏 3 个 404，并打破 `browser_check` 的「console 0 报错」判据（CI 已自动化这一步，本地需手工补一次）。
> 复制来的是**零密钥同源代理版**（按域名自适应）；只有需要浏览器直连跑演示时，才自己填入 Key。

| 工具 | 版本 | 说明 |
|---|---|---|
| JDK | **17**（必须显式设置 `JAVA_HOME`） | 系统默认可能是 JDK 8，Spring Boot 3 会编译失败 |
| Maven | 3.9+ | `mvn -f server/pom.xml package` |
| Node.js | 20+ | 跑情绪评测与前端一致性脚本 |
| Python | 3.10+ | 回归判据脚本。**需要装依赖**：`pip install -r _test/requirements.txt`（playwright / PyYAML / pypdf / Pillow —— 单一清单，CI 与本地同源，由 `repo_config_check` G11 与 `_test/*.py` 的实际 import 对账） |

> ⚠️ 更正注 r96（2026-10-05 一手实测）：本行原写「回归脚本（仅标准库，无需 pip 安装）」是**假的**。
> 照它做 clone 后，第一批浏览器判据（`browser_check` / `public_check` / `pixel_dual_check` …）会直接
> `ModuleNotFoundError: playwright` 而 rc=2 报「ENV-ERROR」，而 `_test/requirements.txt` 的注释里
> 记着 CI 因为漏装 PyYAML 曾长期红着。这条比下面那节「浏览器版本不匹配」更致命，所以同笔改。
> 现在由 `_test/browser_engine_declare_check.py` 的 **E5 腿**常驻盯着（正文出现该类虚报字样即红；
> 唯一豁免是**同一行**带 `更正注` 三字——用于保留被推翻的原文，见该函数 docstring 的窄豁免说明）。

## 浏览器判据与本机引擎（clone 必读）

本仓有 32 个 `_test/*.py` 通过 Playwright 驱动浏览器做判据。**它们实际用的是哪台浏览器，会影响
"本地全绿"这句话的含义**，所以写清楚：

1. **症状**（本机 2026-10-05 实测原文，一字不改贴出来，方便新人一搜就到）：

   ```
   BrowserType.launch: Executable doesn't exist at
   D:\playwright-cache\chromium_headless_shell-1223\chrome-headless-shell-win64\chrome-headless-shell.exe
   ```

   根因：`playwright 1.60.0` 的 `driver/package/browsers.json` 要 Chromium revision **1223**，
   而本机 `D:\playwright-cache` 里只有 `chromium-1228 / chromium-1243`。

2. **本仓的实际行为 = 回退系统 Edge**（实测 Edge 154.0.4258.53 可通）。⇒
   **本地浏览器套件全绿 ≠ 受理面（CI ubuntu + 受管 chromium）全绿**，两侧不是同一台浏览器。
   这条与本页「CI 会复跑同样判据」并列时须知：判据逻辑同源，**渲染引擎不同源**。

3. **两条修复通道**（任选其一；第二条零下载）：

   ```bash
   playwright install chromium                        # 联网装受管版本，装完走 chromium
   set XINYU_CHROMIUM_PATH=D:\playwright-cache\chromium-1243\chrome-win64\chrome.exe
   #   实测该可执行体能起（Chromium 153.0.8010.12），拿到的是"真 chromium 面"而非 Edge 面
   ```

4. **自查命令**（跑它确认本机到底用了什么，以及本节的声明还活着）：

   ```bash
   python _test/browser_engine_declare_check.py --machine
   ```

   判据行会把引擎身份折进去（例：`BROWSER-ENGINE-PASS: … 本机面=msedge(154.0.4258.53)`）。
   新增/改造浏览器套件时请 `from browser_engine import launch`（唯一实现），不要再手写
   `try/except` 回退——`_test/browser_engine_declare_check.py` 的 **E2 腿**把"回退余量"钉成
   只降不升的棘轮，新写一份回退会当场红。

   ⚠️ 更正注 r98：上面这句在 r96 写下时 E2 的口径是「未接入数 = 站点数 − 已接入数」，而
   「已接入」被定义成*同时*含裸 `chromium.launch(` 且已 import 的文件 ⇒ 一件接完就离开分母，
   该分子恒 ≈0 ⇒ 当时给下一轮的验收标准「统一入口 N/32 已接（N 单调升）」**按构造不可达**。
   现口径：`回退余量`（AST 现读）+ 起点名册 32 − 现读 = 已接，另有 E2b（离开分母者必须
   「在册 ∧ import ∧ 裸 launch==0」）与 E2c（半接入残留必须为 0）两条腿钉住"降的是真接入"。
   全文见 `交付物/对标分析报告-2026-10-06-r98.md` §2 F1。本仓现状：**32 → 24（已接 8）**。

## 五条红线（违反任一 = 拒收）

1. **密钥红线**：密钥零落前端、零入库、零进镜像。环境变量文档写进 `.env.example`（占位符），真实值只走部署平台。
2. **同步红线**：改 `src/` 必须同步 `deploy/xinyu/`，并跑 `python _test/deploy_sync_check.py` 至 `DEPLOY-SYNC-PASS`（MISSING/DIFF/EXTRA 三类归零）。`deploy/xinyu/js/demo-config.js` 是零密钥代理版，**禁止**被 `src` 版覆盖。
3. **词表一致性红线**：情绪引擎 JS/Java 两端并存（本地那份是离线降级，不可删）。改任一端词表必须两端同步，并跑 `python _test/engine_consistency_check.py`（词表结构 / 逐条 73 预测 / 汇总指标三层判据，不一致即失败）。
4. **契约红线**：`POST /api/chat` 与 v1 Pages Function 保持 1:1（错误体、判定顺序、上游透传均一致），改动须同步更新并通过 `_test/j2_chat_contract.py`（单变量对照：A 组在线 / B 组回落离线）。
   `stream:true` 是**新增可选字段**，不属于破坏性变更：不带该字段的请求路径必须逐字不变（`_test/stream_contract.py` 判据 A 守这条）。
5. **策略表成对红线**：共情文案的唯一真相源是 `src/data/emotion-strategy.js`（纯 JSON 字面量，禁 JS 表达式）。**加一类情绪 = 同时改词表与本表**，只改一处会在运行时静默回落 calm（答非所问但不报错）。改完必须跑 `python _test/strategy_check.py`；判据本身用 `--selftest`（注入分叉必须报 FAIL）证明非恒真。

## 开发流程

```bash
# 1. 起服务（工作目录必须是仓库根——静态页直读 ./src/）
java -jar server/target/soulisle-server.jar --server.port=8123

# 2. 改动后本地验证（CI 会复跑同样判据）
python _test/deploy_sync_check.py       # src ↔ deploy 同步守卫
node _test/emotion_eval.js              # 情绪评测（条数以该脚本自印为准；旧注写 73 条是 2026-09-23 前的快照，HEAD 面现为 85 条——G8 两面判据盯着这类声称）
mvn -f server/pom.xml -B package        # Java 构建

# 3. 涉及前端运行时行为时，追加：
python _test/browser_check.py           # 离线降级/双色/滚动淡入淡出 → ALL-ASSERT-PASS
python _test/pixel_dual_check.py        # 双色像素级三用例
python _test/public_check.py            # KEY_LEAK: False
python _test/strategy_check.py          # 策略表 ↔ 词表成对性（红线 5）；--selftest 证判据非恒真
python _test/stream_contract.py         # 流式三判据（需 env 里有可用的 LLM 密钥才能过 B）
python _test/ux_guards_check.py         # TTS / 对话窗口化 / 响应式与粒子降档
```

CI 与本地同口径：`.github/workflows/ci.yml` 三个 job 分别跑「同步+评测+策略表+密钥扫描」「Java 构建+词表一致性红线」「浏览器回归」。
需要真实密钥的判据（`stream_contract` 的 B 组、`public_check`）**不进 CI**——CI 只跑零密钥可复现的部分，避免把密钥带进托管环境。

## 如何跑电池（推送前必做，别只挑几条跑）

```bash
python _test/run_all_suites.py --exclude-llm     # 全量回归（豁免 3 条需真实密钥的套件）
python _test/run_all_suites.py --list            # 套件名册（唯一真相源 = SUITES 列表，不手抄条数）
python _test/run_all_suites.py --only deploy     # 只跑名字含 deploy 的套件（调试用，**不算**推送前验证）
```

四类结论，含义不同，**别把它们读成两档**：

| 结论 | 含义 | 该做什么 |
|---|---|---|
| `*-PASS`（rc=0） | 判据跑完且干净 | 可以收工 |
| `*-FAIL`（rc=1） | 判据跑完且判红 | 修产品，不是放宽判据 |
| `*-UNVERIFIED`（rc=2） | 取数面不可读／输入为空／环境缺件 | **不是通过**；把缺的那一面补出来再判 |
| `CRASH`／`SUITE-TIMEOUT` | 判据进程自己崩了或没跑完 | 与"产品红""环境未验"三档分列，红因必须自己点名 |

配套纪律（每条都在本仓有常驻判据兜着，不是口头约定）：

- **判据必须自带反例腿**：新增或改动判据时同轮加 `--selftest`，且**先看它红一次**（把守卫摘掉必须翻红），
  否则等于写了一条永远绿的装饰。跑法：`python _test/<某判据>.py --selftest`。
- **数字别手抄**：套件数由 `repo_config_check` 的 G4 与 README 断言等值对账；评测集条数由 **G8**
  在**工作树面与受理面（`git show HEAD:`）各判一次**——只在本机对上一句、CI 检出的那份不对，G8 会点名是哪一面。
- **整跑不可重入，也不可与单跑并行**：并发第二条一律 `BATTERY-UNVERIFIED(并发)`（不给绿也不造假红）。
  共享工作树里常有并行会话，起服务前先量端口归属：`Get-NetTCPConnection -LocalPort 8123 -State Listen`。
- **提交一律 pathspec 限定**：`git add <本次路径…> && git commit -m "…" -- <本次路径…>`，
  提交后 `git show --name-only HEAD` 核对只含本次文件；`git add -A` 在多人同树是事故源。
- **行尾**：本仓按 LF 落盘，改完跑 `python _test/eol_parity_check.py`——Windows 下编辑器写出 CRLF
  会让"逐字节／SHA256／字节预算"类主张在别人 clone 上不可复算（r119 一手实测：一次编辑落 168 个 CR）。

## 提交规范

沿用仓库既有风格：`type(范围): 中文描述`，type ∈ `feat / fix / perf / docs / test / chore`。
一次提交一件事；文档与代码分开提交。

## 其它约定

- 禁止把前端复制进 `server/src/main/resources/static/`（零副本策略，见 README「架构」）。
- 禁止把评测集复制进 jar 资源目录（服务端直读 `_test/emotion-eval-dataset.json`）。
- 新增 `_test/` 回归脚本必须自带失败出口（非零退出码），不允许"打印 FAIL 但 exit 0"。
- Java 源码一律 UTF-8；构建前确认 JDK 17（`java -version` 应为 17.x）。
