# 05-feature-status.part9.md

<!-- 本卷为 05-feature-status.part8.md 的延续 -->

## 📋 计划中

- [x] **`src/js/chat-window.js` 外提**（对话窗口化：60 条 DOM 上界 / 配额制折叠 / 展开较早）：
      对外只留 `init/push/update/setTag/toBottom`，`quota`、`trimmedBuf`、`.log-fold` 提示条留在模块内。
      判据 = `python _test/ux_guards_check.py` 的 U2a–U2f（**行为级**，非源码 grep，搬错即红）21 项全绿；
      全量电池 `python _test/run_all_suites.py` ⇒ 29/29 rc=0；公网 `61ec115b` 后 `live_sync` 等值字节复验。
      行数一律用复算命令读，不手抄：`python -c "import pathlib as p;print({f:len(p.Path('src/js/'+f).read_text('utf-8').splitlines()) for f in ['app.js','chat-window.js']})"`

- [x] **G9 判据脚本 import-safe**（`repo_config_check.py`）：顶层入口调用必须在 `__main__` 守卫后；
      复算 = `python _test/repo_config_check.py --selftest`（十一类）+ `python _test/repo_config_check.py`（G1–G9）

- [x] **`src/js/settings.js` 外提**（模型设置面板：provider 预设 / 密钥录入 / 流式开关）：
      三条密钥语义原样随迁（Key 恒不回显、留空即不改、proxy 保留），徽章刷新用 `init({onSaved})` 注入。
      **动刀前先立判据**：`python _test/settings_panel_check.py`（S1–S8）旧代码基线 9/9 绿，外提后复跑同判据 9/9 绿；
      `python _test/settings_panel_check.py --selftest` 五类注入反例（Key 回显 / 洗 Key / 预设未填 / 取消仍写 / 空徽章）全抓。
      行数一律现读（本仓第 N 次提醒自已）：
      `python -c "import pathlib as p;print({f:len(p.Path('src/js/'+f).read_text('utf-8').splitlines()) for f in ['app.js','voice.js','chart.js','chat-window.js','settings.js']})"`

- [x] **能力覆盖率分母证明**（`coverage_hits`）：树截断/取数失败仓踢出分母并点名原因；实测核对 lobehub 树
      `truncated=false` + 20,740 对象 + `sw.js|service-worker.js|sw.ts` 零命中 ⇒ `pwa_offline=0/16` 是真零不是漏数。
      复算：`python _test/benchmark_metrics.py`（首行即「有效分母 N/16」）+ `--selftest`（含负控制）

- [x] 切分四刀全部完成（语音 / 曲线 / 窗口化 / 设置面板），`app.js` 已无可独立外提的低耦合块 ⇒ 切分线收口

- [x] **`src/sw.js` 只读离线壳**：HTML/JS/CSS network-first；`vendor/`+`assets/` cache-first（缓存名由 vendor 内容
      指纹钉住，换库忘 bump 即判红）；`/api/**` 与非 GET **完全不碰缓存**；`js/demo-config.js`（本地含密钥）
      **既不预缓存也不写缓存**。判据 = `python _test/offline_shell_check.py`（A1–A10 静态 + R1–R9 运行时，
      含 13 类注入反例），其中 **R9 = 在公网上真断网重载**；公网 `54fb9778` 实测 sw.js 200 / 4,773B / no-cache

- [x] **`deploy/xinyu/_headers`**：只钉真正缺头的两条（实测 `/index.html` 原本无 Cache-Control 且 308 到 `/`；
      `/sw.js` 显式 no-cache）。本地 jar 侧 `spring.web.resources.cache.period=0` 已统一给 `no-store`
      ⇒ **我原先写的 Java 过滤器是死代码，实测后删除**（少写代码也是产出）

- [x] **CI 挂上真发布路径**：browser-regression job 从"只跑 browser_check 一条"改为整跑电池
      `python _test/run_all_suites.py --exclude-llm`（runner 无密钥 ⇒ 显式豁免两条并点名，恒等式自证）；
      新增常驻判据 **G10**（CI 覆盖分母）。复算：`python _test/repo_config_check.py`（G1–G10）与 `--selftest`

- [x] 电池 29 → **33 套件**；CI 同款命令本地实测 31/31 rc=0，全量含密钥 33/33 rc=0
