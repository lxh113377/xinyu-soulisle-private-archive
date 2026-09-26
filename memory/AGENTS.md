# AGENTS.md — 陪聊 项目级 Skill 绑定表（P-1，A-project-handoff）

> 手动维护。agent 检测到本项目路径时第一动作 Read 本文件；命中触发条件 → 加载对应 skill，禁裸跑。

## Skill 强制绑定（命中即加载）

| 触发条件 | 必加载 skill |
|---------|-------------|
| 任何项目修改操作（代码/记忆/技能/文档/配置） | A-project-handoff |
| 每轮复杂任务开场 | A-memory-start |
| 任务结束/复盘/经验沉淀 | A-get-memory |
| 动手前需求澄清 | A-ask-questions |
| **任何 Java 代码 / 编译运行 / JDK 环境相关** | **A-java-problem**（铁律 #45，禁绕过） |
| **技术栈 / 架构选型决策（新增、变更、推翻）** | **A-project-handoff** —— 唯一落盘位置 `03-tech-stack.md` 的「📋 选型决策记录」节（2026-09-22 老大定：此类决定由该 skill 负责，禁止散落在对话或 `.codebuddy/` 记忆里） |
| （按需追加：部署/审计/UI 等专用 skill） | 项目名-deploy 等 |

## 铁律

- `memory/07-next-steps.md` P0 永不为空；`savepoint` 后才能结束对话
- **当前主线 = Java 全栈改造（2026-09-20 定）**：分阶段 J1–J5 落在 `07-next-steps.md`，每阶段必须能跑 + 过 `_test/browser_check.py`，禁止一次性推倒重写
- **密钥红线**：密钥零落前端、零入库。`src/js/demo-config.js`（含 Key）已在 `.gitignore`；`deploy/xinyu/js/demo-config.js`（零密钥代理版）**禁止**被 src 版覆盖
- **同步红线**：改 `src/` 必须同步 `deploy/xinyu/` 并做 SHA256 双向比对（MISSING / DIFF / EXTRA 三类全归零）→ **已固化为 `python _test/deploy_sync_check.py`**（2026-09-23 立）。
  ⚠️ 立规缘由：修完 `src/js/emotion-engine.js` 缺陷后公网副本**仍是旧引擎**，差点把带缺陷的版本部署上线；且首次手工比对被 PowerShell 别名 `h`(Get-History) 覆盖自定义函数 → 两端哈希都取不到 → `None==None` → **全报 SAME（假通过）**。故脚本强制哈希非空 + 输入非空断言，并自带对照组用法。
  `js/demo-config.js` **不参与内容比对**（两端本就该不同：src 版含真实 Key，deploy 版是零密钥 stub），只做红线复核（零密钥 + 与 src 版不同）。
- Java 任务（v2 起）：源码一律 UTF-8，编译必须 `javac -encoding UTF-8`；JDK 版本切换后必须重验编码
- **Java 构建环境（2026-09-21 实测，禁凭记忆猜路径）**：JDK 17 = `C:\Program Files\Eclipse Adoptium\jdk-17.0.20.101-hotspot`；Maven = `%USERPROFILE%\.local\maven\apache-maven-3.9.9\bin\mvn`（不在 PATH）。⚠️ **默认 `JAVA_HOME` 是 JDK 8，每次构建/启动前必须显式切换**，否则 Spring Boot 3 编译失败
- **静态页托管红线**：服务端直读 `src/`（`static-locations=file:${XINYU_WEB_ROOT:./src/}`），**禁止**把前端复制进 `src/main/resources/static/`（会造出第三处副本同步点）
- **评测集红线（J3）**：`GET /api/emotion/eval` 从 `_test/emotion-eval-dataset.json` **直读权威源**（`XINYU_EVAL_DATASET` 可覆盖），**禁止**把评测集复制进 jar/资源目录
- **🔴 词表一致性红线（J3，2026-09-22 立）**：情绪引擎在 JS / Java **各有一份**（本地那份是**离线降级**用的，不可删）。**改任一端的词表，必须两端同步改，并跑 `python _test/engine_consistency_check.py`**（三层判据：词表结构含重复项与顺序 / **逐条预测 73 条**（2026-09-23 由 36 扩至 73）/ 汇总指标）—— **不一致即失败**，禁止只看 `emotion_eval.js` 单侧通过就提交
- **J4 开关（2026-09-23 校正：此前只写「默认关闭」，与磁盘实况不符）**：分三层，**不得混为一谈**
  1. **代码层**（`src/js/memory-store.js`）—— 判定仍是 `cfg.remote === true` 才发远端请求，**默认关闭**；服务端不可达即熔断（404/网络失败 → `remoteDown`，本会话不再重试），本地 `localStorage` 照常写入
  2. **本地演示预置层**（`src/js/demo-config.js`）—— 已置 **`remote: true`** ⇒ **本地 / fat jar 演示默认开启**服务端持久化（"跨设备、清缓存都不丢"成立）
  3. **公网部署层**（`deploy/xinyu/js/demo-config.js`）—— **刻意不含 `remote`** ⇒ Pages / CloudBase 上默认关闭（那里只有 `/api/chat`、没有 `/api/memory`，开了会给评委看到 404）
  改动任一层都须先跑 `_test/j4_memory_check.py` + `_test/j4_remote_down_check.py` + `_test/browser_check.py`
- **密钥红线（J5）**：`DEEPSEEK_KEY` 只从环境变量读；`XINYU_API_TOKEN` 留空=不鉴权（演示默认），私有部署时置非空

## 架构决策（索引 —— 详表见 `03-tech-stack.md`「📋 选型决策记录」）

> **约定（2026-09-22 老大立）**：技术栈/架构选型类决定由 **A-project-handoff** 负责，唯一落盘位置 = `03-tech-stack.md`「📋 选型决策记录」；每条须含五要素（背景 / 选项 / 结论 / 已知代价 / 重评触发条件），未落地项标「待落地验证」，被推翻的决策保留原条目 + 增更正注。

- **后端语言 = Java(Spring Boot)** —— 已执行；但**复核结论：若重做本作品会选 Python**，不返工。重评触发条件 = 需要本地模型/Embedding/RAG/微调/AI 生态 → 届时起 **Python 侧服务由 Java HTTP 调用**，不用 Java 硬啃 AI 生态
- **静态页直读 `src/`**（不复制进 `resources/static/`）—— 消灭第三处副本同步点；代价 = 启动工作目录必须是项目根
- **J4 远端记忆默认关闭**（`cfg.remote`）—— 零回归风险；代价 = 不主动开启则"跨设备记住你"不成立
- **鉴权用轻量 token 过滤器**（未引 Spring Security）—— 够用 + 依赖最小；代价 = 无多用户/角色/会话管理
- **评测集不复制进 jar**（服务端直读 `_test/`）—— 保证 Java 侧与 JS 侧跑的是同一份数据


## 排障手册（本轮一手实测，进仓即读）

> 只登记**本机本仓亲测复现过**的报错特征，一条一测；未复现的传闻不写（写进来就会有人当真理）。

| 症状 / 报错原文 | 真因 | 处置 |
|---|---|---|
| `[GATE:dag-fail] ... 块内找不到本次改动标识 require_mark=` 但 `blocks` 数在涨 | `dag_precheck.py` 的块体＝**锚点行之后到空行之前**；把"本次标识"写在 `##` 标题行 = 在块体外 | 标识必须写在 `【数据流假设】` 锚点**下面的块体内**（如 `本次标识: xxx`）；工具只扫 GM `D:/global_memory/memory/` 与焚诀 `.workbuddy/memory/`，写项目日志无效。**V10.72.0 起这条判据已直接写进报错面**，不必再读源码 |
| `gh api` 调用抛 `json.decoder.JSONDecodeError` / 结果恒空 | 本仓 `_test/benchmark_metrics.py:gh()` 会 `json.loads(整个响应)` 且非零退出即抛 ⇒ 带 `--jq` 出来的**裸字符串不是合法 JSON** | 取整份 dict 再自己挑字段（`gh("repos/x")["description"]`）；要用 `--jq` 就得绕开该 helper |
| 文档里某条红线/条目**表头整行消失**，只剩续行 | 用"既有条目行的前缀"当 Edit 锚点，替换文本里没把原表头回写（长行台账同族第四形态） | 锚点须含被改动的**整行**并在 new 里回写；改完必查 `git diff --stat`：**只有 +N 无 -M** 才算没吞行 |
| `SyntaxError: bytes can only contain ASCII literal characters` | 写了 `b"中文"`（bytes 字面量不能含非 ASCII） | 用 `文本.decode/encode` 或先 `.decode("utf-8", errors="replace")` 再做子串判断（**2026-09-27 r40d 我自己又犯一次**：在校对分卷占位符的脚本里写了 `b'卷{N}' in b`，同一条报错当场复现 —— 排障表写进仓不等于会被读，写脚本前先想这一族） |
| Python 里 `/tmp/xxx` 报 `FileNotFoundError: '\tmp\xxx'` | Git Bash 的 `/tmp` ≠ Windows Python 的 `/tmp`（后者按当前盘根解析） | 跨 bash/python 传文件用显式 `C:/Users/37533/AppData/Local/Temp/...` |
| `[GATE:dag-fail] ... 存在四标签齐全的块，但块内找不到本次改动标识` 而**你确定块已落盘** | **锚点行尾多写了说明文字** —— 正则要求 `【数据流假设】` 独占一行（`^\s*[#>\-\s]*【数据流假设】\s*$`），后面多跟一个字整块就不成立。⚠️ 本行原先写「四个标签用全角冒号让块隐形」是**我的错误归因，已按实测撤销**：`LABEL_RE` 的字符类是 `[:：]`，全角与半角同样接受（自测反证用例当场证伪） | 把说明文字挪到上一行标题或下一行正文；V10.74.0 起报因直接给可疑行号，且 `--require-mark` 改整词匹配（短标识被同卷长标识当前缀命中不再算绿） |
| 迁移脚本自己打印 `SHELL=4128B(<=4096)` —— 断言明明通过了，磁盘却超限 | `pathlib.write_text()` 在 Windows 走文本模式 ⇒ **`"\n"` 被翻译成 `"\r\n"`**，而断言比的是 `len(str.encode("utf-8"))`（LF 口径），每条少算 1 B/行；R161 的 4,096 B 阈值是按磁盘字节量的 ⇒ 判据在量错对象 | 断言与打印一律用**写完后回读**的 `len(Path(...).read_bytes())`；只量字符串长度的 4KB 检查是假绿（r35 实测：主壳字符串 4,083B / 磁盘 4,128B） |
| 电池里某条套件 `rc=3221225773`（`0xC0000409`）且 **stdout 完全空** | 判据进程硬崩（Windows fastfail），不是断言失败也不是环境不可达。第一版收口行按"非 1 即环境"分类，把它印成了 `ENV-UNVERIFIED` ⇒ **给崩溃发了通行证**（与"换原因的常红"同一族：分类维度少一挡就会掩盖一类真问题） | 现在分三类：`rc=1` 判红 / `rc=2` 环境未验 / **其余一律 `CRASH(...，必须查)`**；反例经合成四态套件验证（PASS 不进红名单、崩溃不冒充环境） |
| CI 日志里某判据只有 `XXX-PASS`，**一个数字都没有**（本地跑明明满屏明细） | 电池对每个套件**只保留最后一条含 `PASS\|FAIL\|CLEAN\|UNVERIFIED\|OK` 的 stdout 行** ⇒ 逐项明细行系统性进不了 CI；判据是棘轮时，被检环境的值全部丢失 | 把 `峰值/余量/计数` **折进含判据词的那一行本身**（禁为个别判据开日志例外）；接通聚合层后必须**从聚合产物侧回读一次**确认真的活下来了（r40b 实装两处：`perf_baseline`、`REPO-CONFIG-PASS`） |
| `BATTERY-FAIL: --slice 25 49 越界（套件总数 46）` | `--slice` 的下标是**过滤后可跑面**的下标：带 `--exclude-llm` 时上界是 46 而不是 SUITES 的 49 | 分段用 `--slice 0 25` + `--slice 25 46`；条数恒等式由 runner 自己印（`实跑 46 + 豁免 3 == 49`），别拿 49 当下标上界 |
| `git show --numstat` / commit 回执里出现**不属于我的 deletions**（本次是新建文件，本该零删除） | 共享分卷目录里"`ls` 取 max + 写文件"是两步，**窗口内并行会话会把同号建卷并入库**；`Write` 不报错，直接整卷覆盖对方内容 | 立即 `git show <覆盖前>:<path>` 写回 + `cmp` 证零差异，再**追加**提交（不改写已推送历史）；建新卷一律走 `D:/global_memory/scripts/volume_alloc.py --dir memory --template "…part{N}.md" --from-file <tmp>`（O_EXCL 独占取号 + 写入端 4KB 封顶） |
| `[GATE:secret-fail] 🔴 …:48 [OpenAI 风格 sk- 密钥] sk-interpret…path`（普通文档被拒入库） | `scripts/secret_scan.py:35` 的规则 `sk-[A-Za-z0-9_\-]{16,}` **字符类里含 `-`** ⇒ `ta`+`sk-interpreter-path` 这种**词内** `sk-` 被当成密钥 | 正解是给规则加词边界 `(?<![A-Za-z0-9])`；未修前正文里这类 slug 用 U+2011 非断行连字符绕行（**绕行本身即该缺陷的可复现证据**，见 GM `memory/2026-09-26.part62.md`） |
| `git add -- MEMORY.md`（共享索引）后 `git diff --cached` 里 **31 行 `+` 有 30 行不是我写的** | pathspec 的粒度是**文件**，而共享索引文件的并发单位是**行** ⇒ "只提交显式路径"不构成"只含本次改动"的保证 | 共写文件提交前先 `git diff --cached --numstat` 并逐行看 `+` 的归属；发现裹挟立刻 `git restore --staged <file>`，把自己的行留在工作树、由该文件的下次归属提交带走。⚠ 已知残余失败面：**同一行**被两会话各改一版时 numstat 会伪装成"只含我的"（须按块提交或行级核对） |
| `upgrade_footer_gate.py` 回 `[GATE:evolution-fail]`：`改法超 40 字` / `块内存在非法行` / `未找到 footer 锚点块` | footer 文法是**精确正则**：块须 `<!-- footer:begin session=… ts=… -->` … `<!-- footer:end -->`；`[升级建议]` 五段顺序固定、**括号内不得含 `)`**、`改法 ≤40 字`；`[记忆预检]` 只允许 `lessons=\| 工具=\| 说明=` 三字段且**单行、说明 ≤40 字** | 照 `A-memory-start/references/reply_footer.md §1` 填；填完必用 `--file <本次卷>` 复跑一次，**断言回执里的 source 是自己那块**（否则那个 pass 可能是别人的块给的） |
| push 完就收工、CI 结果靠下一轮想起来再查 | 49/51/52 条判据里有一批只在 CI 才判得动（Linux runner、浅克隆无 tag 走 ls-remote 分支），本地全绿不等于受理面全绿 | **推送一律走 `bash _test/push_and_watch.sh`**：push → 轮询该 sha 的 run → 逐 job 点名 → `--log-failed` 末 40 行 + 四条下一步指令；退出码 0 绿 / 1 红 / 2 未验证（无 run、超时、gh 不可用都不算过） |
| `python - <<'PY'` 打完补丁后目标文件 `SyntaxError: unterminated string literal` | 内联脚本的 replacement 含 `\\n` 时被多层解释把**转义落成真实换行**插进字符串字面量（本仓第 10 次遇到"内联/heredoc 吞反斜杠"族） | 含转义序列的文本改动**一律走 Edit 工具**；必须内联时把待插入内容写成单行字面量或 `chr(10).join([...])` |

