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
  - **2026-09-23 补强（判据稳定性治理，阈值未放松）**：早前判据会因采样相位抖动而时好时坏（同色用例曾判出 0.338 色距的假双色；干净树基线对照同样复现 ⇒ 非回归、属判据本身不稳）。修法全在**测试侧**：① init script 定种子替换 `Math.random` → 星位可复现；② Playwright clock `pause_at` 固定时刻 → `performance.now()` 恒定 → 动画相位冻结；③ 新增**空白星图负对照**；④ console 报错改按**来源 URL** 精确豁免注入端点（不再"凡 CONNECTION_REFUSED 一律放行"）。**生产代码零测试钩子**（中途曾加 `?seed=` 生产侧钩子，终稿已移除）。
  - **连跑实测**：(色距, 少数簇占比) multi ≈ (0.53~0.57, 0.27~0.35) / single ≈ (0.02~0.11, 0.004~0.04)；blank = (0.428, 0.004) 判不出双色。判据余量 ≥2.2×，`LIT-COLOR-CHECK-PASS`。
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
- [x] AC-OBS-20: 接口契约与实现不脱节（r21）→ `api_contract_check.py`：C1 控制器 11 条路由全部已文档化、C2 spec 无幽灵路径、C3 前端未偷调未文档化端点、C4 真实打 8 个端点状态码与必需键一致（含 `/api/chat`、`/api/emotion` 在线调用；探测会话 `contract-probe` 由 DELETE 自清）、C5 `--selftest` 四类合成篡改全抓到 | 测试输出 + API响应
- [x] AC-OBS-17: 情绪识别可切后端且降级不伪装（r20）→ `emotion_wiring_check.py` 9 项：W4 实测 `stats.ok≥1` 且气泡标「情绪:后端」；W5 拦掉 `/api/emotion` 即 `isDown()=True`、回复照常、**不出现**后端标注；W6 同句双端词典结论相同 | 测试输出
- [x] AC-OBS-18: 危机拦截不因后端化而延迟（r20）→ W3 源码级判据（`lex.crisis` 分支先于 `fetchEmotion(text)`）+ W3b 实测 `crisisShortCircuit≥1 且 attempted=0`（后端一次都没被调） | 测试输出 + API响应
- [x] AC-OBS-19: 首屏第三方库可溯源（r20）→ `vendor-manifest.json` 声明版本/sha256，`vendor_freshness_check.py` V1 完整性 V2 从文件内容解析版本对账（正则零命中即红）V3 新库漏登记即红；`--selftest` 4 类篡改全抓到 | 测试输出
- [x] AC-OBS-13: 情绪引擎两端（JS/Java）**不静默分叉** → `engine_consistency_check.py` 三层判据全等（词表结构含重复项与顺序 / 逐条预测 / 汇总指标）；**判据非恒真已证**：`--selftest` 注入分叉报错 + 端到端改真词表 → FAIL 并精确指出差异 | 测试输出
- [x] AC-OBS-14: 远端记忆不可用时**熔断且不制造噪音** → `j4_remote_down_check.py`：无 `/api/memory` 时请求数上界 = 页面加载次数（3 句对话仅 2 请求）、本地存储照常写入、`isRemote()` 熔断后为 False | 测试输出
- [x] **AC-OBS-15（2026-09-23）**：fat jar **可脱离项目根独立部署** → 从系统临时目录启动 `deploy/jar/start.ps1 -Port 8125 -WebRoot <仓库外静态副本>`，`/api/health` = `UP` + `indexFound/vendorFound=true`，`/`、`/js/*`、`/vendor/*`、`/css/*` 全 200，公网版 `js/demo-config.js` `KEY_LEAK=False` | 启动日志 + HTTP 实测
- [x] **AC-OBS-16（2026-09-23）**：语音输入链路真机可跑 → `_test/voice_check.py` **VOICE-PASS**；事件序列 `start → audiostart → result:n=1 → end`（真出识别结果），监听态进入/恢复正常，console 0 错误 | 测试输出
- [x] **AC-OBS-17（2026-09-23）**：国内备用线 AI 对话可用 → `POST https://qwer-d4gf2r76o8829463b.service.tcloudbase.com/api` = **200** + 真实 DeepSeek 回复 + `access-control-allow-origin: *` | curl 实测
  ⚠️ 判据口径提醒：必须用 `service.tcloudbase.com`（云函数域），**不能用** `tcloudbaseapp.com/api/chat`（那里是 404，属静态托管域，测它会对国内线得出错误的"已死"结论）
- [x] **AC-OBS-18（2026-09-23）**：Dockerfile 的**镜像内容物与运行参数**在无 Docker 时也可证 → `python _test/docker_image_sim_check.py` **DOCKER-SIM-PASS**：COPY×3/ENV×5/WORKDIR 从 `server/Dockerfile` **解析**（非手抄）后磁盘等价实现 → 写入 14 文件、评测集 73 条、**镜像内 `sk-` 0 命中**、`status=UP`/`indexFound`/`vendorFound` 全真、4 条静态资源 200、`/api/emotion/eval` = 73 条 / 98.6% / 危机 6-6。
  判据附带**隔离桩**（`--selftest`）：注入 1 处假密钥 → 恰好命中 1；移除 → 回到 0 ⇒ 「0 命中」类判据非恒真/恒假。
  ⚠️ **边界（不谎称已验）**：本项**不等于 `docker build` 通过** —— 基础镜像拉取、层缓存、ENTRYPOINT exec 形式、容器网络/端口映射仍未验；且本机 Docker 尚未可用（`Docker.sbx` 即 Docker Sandboxes 无 `docker` CLI、daemon 起不来，非构建器）。
  ✅ **本项的边界已于同日闭合** —— 见 AC-OBS-19（真 Docker 已跑通，模拟降级为历史过渡证据）。
- [x] **AC-OBS-19（2026-09-23）**：容器镜像**真构建真运行**通过 → Docker Desktop 4.91.0（daemon `Server 29.8.0 / linux / overlayfs`）→ `docker build` 成功，镜像 `xinyu-soulisle:latest` **482 MB**；`docker run -p 8080:8080 -v xinyu-data:/app/data` 后 `Up`；`/api/health` = `UP` + `webRoot=/app/web` + `indexFound/vendorFound=true`；4 条静态资源全 200；`/api/emotion/eval` = **73 / 98.6% / 危机 6-6**；**镜像内 `sk-` = CLEAN**（附对照：输入非空 15 文件 / 注入假密钥 `GREP_EFFECTIVE` / 干净文件 `NO_FALSE_POSITIVE`）。
  **持久化（Docker 专属坑）**：写 2 情绪 + 1 消息 → `docker restart` → 重启后仍 2 / 1 ⇒ DB 确实落在挂载卷（Dockerfile 用 `XINYU_DB_URL` 显式覆盖相对路径 + 声明 `VOLUME /app/data` 是有效设计）。
  ⚠️ **前置坑（不解决则永远 build 不了）**：本机**无法访问 Docker Hub**（`registry-1.docker.io` 探测 = **000**），`docker build` 报 `failed to authorize ... dial tcp 88.191.249.182:443`。解法 = 先从可用源拉基础镜像并本地打标（本次用 `docker.1ms.run`，实测 401=通），之后 build 走本地镜像。

### 对标轮第二轮（2026-09-24，证据来源：`_test/stream_contract.py` / `strategy_check.py` / `ux_guards_check.py`）

- [x] AC-OBS-13: 加 `stream:true` 后**逐字流式**可用，且**不带该字段的旧契约逐字不变** → `stream_contract.py` 判据 A（非流式仍回整包 JSON + `choices[0].message.content`）+ 判据 B（`text/event-stream`，实测 32 个 data 帧中 **30 帧含 `delta.content`**、拼回 51 字）。分片数 ≥2 是"边生成边下发"的机器证据，防"整包塞进一个帧"糊过去 | API响应
- [x] AC-OBS-14: 代理不支持流式时**自动回落且不冒充** → 同脚本判据 C 对照组：不可达端点必须落「离线共情模板」，标签出现「逐字流式」或「在线大模型生成」即 FAIL | 测试输出
- [x] AC-OBS-15: 共情策略表与词表**成对成立**（只改一处必被拦） → `strategy_check.py` PASS（键序一致 / 6 情绪覆盖完备 / 危机热线号确实出现在话术里 / `classify.sys` 提及所有情绪键）+ `--selftest` 删 love 策略与抹热线 → 报 2 问题 = 判据非恒真 | 测试输出
- [x] AC-OBS-16: 朗读、窗口化、响应式三项**行为可证伪** → `ux_guards_check.py` 21 项：U1 注入计数器实测 `SpeechSynthesisUtterance` 构造数（开→1，关→不再增长，证"关得掉"）；U2 `.msg` DOM ≤60 且 `getHistory()`/`MemoryStore` 未被窗口化截断 + 展开真放回 + 新消息收回上界；U3 375/700/1300 三档无横向溢出且粒子 900<1200<**2600**（桌面档恒 2600，与 `browser_check` LIT 标定互不破坏）| 测试输出

---

## 已识别的判据误报（保留记录，不修改数据）

- ⚠️ **AC 编号碰撞（既有，2026-09-25 r20 实测发现，未改写历史条目）**：`AC-OBS-13`/`AC-OBS-14`/`AC-OBS-15`
  在本文件里**各出现两次**（「后端服务」节 与 「对标轮第二轮」节各自取了同一号），
  根因 = 两轮各自追加时只看了自己那节的尾部编号、没全文件对账。
  处置：r20 新增项**改用 17/18/19 避让**（不改他人已交付条目，避免 07/报告里对 `AC-OBS-13` 的引用失效）；
  **待办**：若日后统一重排，须同步改 `memory/07-next-steps*`、`交付物/` 里对旧编号的引用，并留更正注。
  教训固化：**取号必须全文件 grep 对账，不能只看本节尾部**。

- ⚠️ `handoff.py review` 的「交叉一致性」会对 05 已完成项与 07 P0 未勾选项做**关键词重叠**匹配。
  2026-09-22 实测报出 5 条「05 已完成 X ↔ 07 P0 未勾选 J3/J4 变现」—— 核对后确认**全部为误报**
  （05 里的条目是"3D 情绪星雾/点亮/对话坞"等已实现功能，与 07 的"J3/J4 变现"是两件事，仅因命中同名词而挂钩）。
  处置：**判定为判据假阳性，不改 05/07 以求绿**（同 R263 精神：先证判据再动数据）。
  > **校正注（2026-09-22 复核）**：当日 5 条为旧快照；本次复核实测为 **3 条**（05/07 内容已迭代）。根因经诊断确认 = 旧判据「任意 ≥1 词交集即报」，且 3 条误报的 07 项**均内嵌 ✅ 子项**（父项未完成、子项已完成属正常非矛盾）。**判据已修复**（A-project-handoff V3.44.0：复合未完成项跳过 + 过滤标签/扩展名 token），复跑 `review` 误报归零、Score 9/9。保留原「5 条」记录不改写（历史留痕）。

- ⚠️ `handoff.py sync` 的自动检测对本项目结构**部分失效**（实测 2026-09-22）：02 目录树可用但含 `.codebuddy/`/`.wrangler/` 等 ignore 目录；03 报「未检测到技术栈配置文件」（因 `pom.xml` 在 `server/` 子目录，sync 只扫项目根）；04 会把 `deploy/cloudbase/functions/chat/index.js` 当入口（真入口是 `src/index.html` + `SoulIsleApplication.java`）。
  处置：**以手工区内容为准**，自动块仅作参考；已在 02/03/04 的手工区加注记说明。
  > **校正注（2026-09-22 已修复）**：三处判据缺陷已在 A-project-handoff **V3.44.0** 根治——03 增子目录清单兜底、04 增 Java 启动类 + 副本降权、02 树并入 `.gitignore` 目录条目。复跑 `sync` 实测：03 显示 `Java (Maven) — server/pom.xml`、04 入口 `src/index.html`+`SoulIsleApplication.java` 排前、02 树不含 `.codebuddy/`。02/03/04 手工区「失效」注记已相应更新为「已修复」。

<!-- 验证通过后标记 - [x]，归档时自动移入 archive -->
