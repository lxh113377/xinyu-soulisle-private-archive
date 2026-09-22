# 08 - AC-OBS 验收标准

> 本文件定义每个核心功能的可观测验收标准。
> 归档类型：增量（已验证的标准移入归档）
> 
> 格式规范：
> AC-OBS-NN: [功能描述] → [验证方式] + [证据类型]
> 
> 证据类型：截图 | 日志 | 测试输出 | API响应 | 数据库查询 | 视频录制
>
> **填写原则（2026-09-22 立）**：每条 AC 必须绑定**已存在的可执行手段**（常驻脚本 / 端点 / 命令），
> 禁止写"应该能…"这类无手段的空话 —— 没有执行方式的验收标准等于没有标准。

## 验收标准列表

### 前端叙事与可视化（证据来源：`_test/browser_check.py` / `pixel_dual_check.py` / `lightshow_check.py`）

- [x] AC-OBS-01: 3D 情绪星雾渲染且 WebGL 不可用时可降级 → `browser_check.py` 断言 `typeof THREE`/`gsap`/`ScrollTrigger` 已加载、`#gl` 活跃、五幕叙事存在 | 测试输出
- [x] AC-OBS-02: 每句对话按其情绪点亮星雾并持久化 → 同套件断言 `LIT: init=0 after1=5 after2=17 reload=17 clear=0` | 测试输出
- [x] AC-OBS-03: 双色星雾在**屏幕像素上**可分辨 → `pixel_dual_check.py` 判据**双条件**：两簇中心色距 > 0.25 **且** 少数簇占比 > 0.10；并带**单色对照**（对照不通过才算判据有效） | 测试输出
- [x] AC-OBS-04: 一键点亮是"清屏 + 播放过程"而非瞬间切换 → `lightshow_check.py` 采**黑屏关键帧**有效像素 = 0（证明清屏真发生）+ 结束后六色各占 8.4%~20.9% | 测试输出
- [x] AC-OBS-05: 叙事卡片随滚动淡入淡出且"明显可感" → `browser_check.py` 断言 `SCROLL_FADE: enter<0.6 / center>0.9 / leaving<0.5 且 <center` | 测试输出
- [x] AC-OBS-06: 危机信号最高优先级拦截并推送求助热线 → 同套件断言 `CRISIS: True` | 测试输出

### 后端服务（v2 Java 全栈，证据来源：`_test/j2_chat_contract.py` / `j4_memory_check.py` / `public_check.py` + curl）

- [x] AC-OBS-07: 服务端托管前端静态页且能自证源命中 → `GET /api/health` 返回 `status=UP` + `webRoot` 绝对路径 + `indexFound=true` + `vendorFound=true`；首页与 `js/css/vendor` 均 200 | API响应
- [x] AC-OBS-08: `POST /api/chat` 与 v1 契约 1:1（前端零代码改动即可切换） → `j2_chat_contract.py` **单变量对照**：A（proxy=Java）在线、B（不可达）回落离线；curl 补验 `no-key` 500 / `bad-json` 400 且**判定顺序与 v1 一致** | 测试输出 + API响应
> **2026-09-23 校正注（两段变更，均当日实测）**：① 评测集 36 → **73 条**；② 修掉 NEG/DEG 覆盖缺陷（见决策 #6）后准确率再升。
> 同一判据最新实测：`accuracy=98.6%` / `crisis_recall=6/6`，双端仍逐项相同。下面行内的 `94.4% / 3-3` 是 **2026-09-22 当日真值**（历史留痕不可改写），保留不动；**对外引用一律用新值 73 条 / 98.6% / 6-6**。

- [x] AC-OBS-09: 情绪引擎评测可现场复跑且双端一致 → `GET /api/emotion/eval` 返回 `accuracy=94.4%` / `crisis_recall=3/3`，且 `per_class`、`misses` 与 `node _test/emotion_eval.js` **逐项相同** | API响应 + 测试输出
- [x] AC-OBS-10: 情绪记忆真落库（跨浏览器、跨重启不丢） → `j4_memory_check.py` **核心断言**：清空 `localStorage` 后刷新星图仍点亮；`GET /api/memory/stats` 计数正确；重启服务后计数不变 | 数据库查询 + 测试输出
- [x] AC-OBS-11: 密钥零落前端、零入库 → `public_check.py` 报 `KEY_LEAK: False`；`git grep -E "sk-[A-Za-z0-9]{20,}" HEAD` 0 命中 | 测试输出
- [x] AC-OBS-12: 可选鉴权可开可关且边界正确 → 无 token 时全放行 200；有 token 时 无头 401 / 错头 401 / 对头 200，且 `/api/health` 与静态页**始终放行** | API响应
- [x] AC-OBS-13: 情绪引擎两端（JS/Java）**不静默分叉** → `engine_consistency_check.py` 三层判据全等（词表结构含重复项与顺序 / 逐条预测 / 汇总指标）；**判据非恒真已证**：`--selftest` 注入分叉报错 + 端到端改真词表 → FAIL 并精确指出差异 | 测试输出
- [x] AC-OBS-14: 远端记忆不可用时**熔断且不制造噪音** → `j4_remote_down_check.py`：无 `/api/memory` 时请求数上界 = 页面加载次数（3 句对话仅 2 请求）、本地存储照常写入、`isRemote()` 熔断后为 False | 测试输出
- [x] **AC-OBS-15（2026-09-23）**：fat jar **可脱离项目根独立部署** → 从系统临时目录启动 `deploy/jar/start.ps1 -Port 8125 -WebRoot <仓库外静态副本>`，`/api/health` = `UP` + `indexFound/vendorFound=true`，`/`、`/js/*`、`/vendor/*`、`/css/*` 全 200，公网版 `js/demo-config.js` `KEY_LEAK=False` | 启动日志 + HTTP 实测
- [x] **AC-OBS-16（2026-09-23）**：语音输入链路真机可跑 → `_test/voice_check.py` **VOICE-PASS**；事件序列 `start → audiostart → result:n=1 → end`（真出识别结果），监听态进入/恢复正常，console 0 错误 | 测试输出
- [x] **AC-OBS-17（2026-09-23）**：国内备用线 AI 对话可用 → `POST https://qwer-d4gf2r76o8829463b.service.tcloudbase.com/api` = **200** + 真实 DeepSeek 回复 + `access-control-allow-origin: *` | curl 实测
  ⚠️ 判据口径提醒：必须用 `service.tcloudbase.com`（云函数域），**不能用** `tcloudbaseapp.com/api/chat`（那里是 404，属静态托管域，测它会对国内线得出错误的"已死"结论）
- [x] **AC-OBS-18（2026-09-23）**：Dockerfile 的**镜像内容物与运行参数**在无 Docker 时也可证 → `python _test/docker_image_sim_check.py` **DOCKER-SIM-PASS**：COPY×3/ENV×5/WORKDIR 从 `server/Dockerfile` **解析**（非手抄）后磁盘等价实现 → 写入 14 文件、评测集 73 条、**镜像内 `sk-` 0 命中**、`status=UP`/`indexFound`/`vendorFound` 全真、4 条静态资源 200、`/api/emotion/eval` = 73 条 / 98.6% / 危机 6-6。
  判据附带**隔离桩**（`--selftest`）：注入 1 处假密钥 → 恰好命中 1；移除 → 回到 0 ⇒ 「0 命中」类判据非恒真/恒假。
  ⚠️ **边界（不谎称已验）**：本项**不等于 `docker build` 通过** —— 基础镜像拉取、层缓存、ENTRYPOINT exec 形式、容器网络/端口映射仍未验；且本机 Docker 尚未可用（`Docker.sbx` 即 Docker Sandboxes 无 `docker` CLI、daemon 起不来，非构建器）。

## 已识别的判据误报（保留记录，不修改数据）

- ⚠️ `handoff.py review` 的「交叉一致性」会对 05 已完成项与 07 P0 未勾选项做**关键词重叠**匹配。
  2026-09-22 实测报出 5 条「05 已完成 X ↔ 07 P0 未勾选 J3/J4 变现」—— 核对后确认**全部为误报**
  （05 里的条目是"3D 情绪星雾/点亮/对话坞"等已实现功能，与 07 的"J3/J4 变现"是两件事，仅因命中同名词而挂钩）。
  处置：**判定为判据假阳性，不改 05/07 以求绿**（同 R263 精神：先证判据再动数据）。
  > **校正注（2026-09-22 复核）**：当日 5 条为旧快照；本次复核实测为 **3 条**（05/07 内容已迭代）。根因经诊断确认 = 旧判据「任意 ≥1 词交集即报」，且 3 条误报的 07 项**均内嵌 ✅ 子项**（父项未完成、子项已完成属正常非矛盾）。**判据已修复**（A-project-handoff V3.44.0：复合未完成项跳过 + 过滤标签/扩展名 token），复跑 `review` 误报归零、Score 9/9。保留原「5 条」记录不改写（历史留痕）。

- ⚠️ `handoff.py sync` 的自动检测对本项目结构**部分失效**（实测 2026-09-22）：02 目录树可用但含 `.codebuddy/`/`.wrangler/` 等 ignore 目录；03 报「未检测到技术栈配置文件」（因 `pom.xml` 在 `server/` 子目录，sync 只扫项目根）；04 会把 `deploy/cloudbase/functions/chat/index.js` 当入口（真入口是 `src/index.html` + `SoulIsleApplication.java`）。
  处置：**以手工区内容为准**，自动块仅作参考；已在 02/03/04 的手工区加注记说明。
  > **校正注（2026-09-22 已修复）**：三处判据缺陷已在 A-project-handoff **V3.44.0** 根治——03 增子目录清单兜底、04 增 Java 启动类 + 副本降权、02 树并入 `.gitignore` 目录条目。复跑 `sync` 实测：03 显示 `Java (Maven) — server/pom.xml`、04 入口 `src/index.html`+`SoulIsleApplication.java` 排前、02 树不含 `.codebuddy/`。02/03/04 手工区「失效」注记已相应更新为「已修复」。

<!-- 验证通过后标记 - [x]，归档时自动移入 archive -->
