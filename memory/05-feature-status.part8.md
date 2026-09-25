# 05-feature-status.part8.md

<!-- 本卷为 05-feature-status.part7.md 的延续 -->

## 📋 计划中

- [x] 交付链全跑：`index.html` 顺序 voice→chart→app（实测 6813/6845/6885）→ `DEPLOY-SYNC-PASS`
      → `size_budget` 登记（17 文件，关键路径 822,936 / 858,752）→ 公网重部署 `0c90a2d9` → 三判据 rc=0
      → 电池 `--slice 0 14` 14/14、`--slice 14 28` 14/14 ⇒ **28/28 rc=0**

- [x] 外部漂移 3 处（lobehub 82,808 / ST 33,745 / OLV 13,903，能力矩阵无变化）⇒ 七维无翻牌，本轮不编造差距

- ⚠️ **本轮两处自伤**：① 打 `size_budget` 补丁时锚点写成 `4_355`（实为 `4355`），`replace` 未命中却照常打印"已登记"
      ⇒ 被 coverage 判据当场报「未登记文件」；已改成替换前后各加 assert。② 抽曲线的脚本锚点条件过窄（依赖 `measureText` 前一行）
      ⇒ `StopIteration` 死在半路；改用 `#btn-clear`/resize 注释这类语义锚点 + 边界行 assert。
      两条同族：**工具"没报错"不等于"生效了"**（与 r23 的 `done >= 8`、r24 的 `2>/dev/null` 同族，已连续三轮复发）。

- [x] **切分未完成**（登记于 r25，r26 已推进到第三刀）：剩余可摘模块 = **设置面板**；
      每一刀都须沿用同一套动作（外提 → index.html 顺序 → deploy 同步 → size_budget 登记 → 电池全绿 → 重部署）。
      ⚠️ 本条目原写"`app.js` 仍 403 行"是**手抄数字且当轮就已过期** ⇒ 按 06 立的规矩改判据：
      行数不写进正文，用下方 r26 条目的复算命令现读。

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
