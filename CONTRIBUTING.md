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
node _test/emotion_eval.js              # 情绪评测（73 条，输出 JSON）
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

## 提交规范

沿用仓库既有风格：`type(范围): 中文描述`，type ∈ `feat / fix / perf / docs / test / chore`。
一次提交一件事；文档与代码分开提交。

## 其它约定

- 禁止把前端复制进 `server/src/main/resources/static/`（零副本策略，见 README「架构」）。
- 禁止把评测集复制进 jar 资源目录（服务端直读 `_test/emotion-eval-dataset.json`）。
- 新增 `_test/` 回归脚本必须自带失败出口（非零退出码），不允许"打印 FAIL 但 exit 0"。
- Java 源码一律 UTF-8；构建前确认 JDK 17（`java -version` 应为 17.x）。
