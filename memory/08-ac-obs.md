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
- [x] AC-OBS-09: 情绪引擎评测可现场复跑且双端一致 → `GET /api/emotion/eval` 返回 `accuracy=94.4%` / `crisis_recall=3/3`，且 `per_class`、`misses` 与 `node _test/emotion_eval.js` **逐项相同** | API响应 + 测试输出
- [x] AC-OBS-10: 情绪记忆真落库（跨浏览器、跨重启不丢） → `j4_memory_check.py` **核心断言**：清空 `localStorage` 后刷新星图仍点亮；`GET /api/memory/stats` 计数正确；重启服务后计数不变 | 数据库查询 + 测试输出
- [x] AC-OBS-11: 密钥零落前端、零入库 → `public_check.py` 报 `KEY_LEAK: False`；`git grep -E "sk-[A-Za-z0-9]{20,}" HEAD` 0 命中 | 测试输出
- [x] AC-OBS-12: 可选鉴权可开可关且边界正确 → 无 token 时全放行 200；有 token 时 无头 401 / 错头 401 / 对头 200，且 `/api/health` 与静态页**始终放行** | API响应

## 已识别的判据误报（保留记录，不修改数据）

- ⚠️ `handoff.py review` 的「交叉一致性」会对 05 已完成项与 07 P0 未勾选项做**关键词重叠**匹配。
  2026-09-22 实测报出 5 条「05 已完成 X ↔ 07 P0 未勾选 J3/J4 变现」—— 核对后确认**全部为误报**
  （05 里的条目是"3D 情绪星雾/点亮/对话坞"等已实现功能，与 07 的"J3/J4 变现"是两件事，仅因命中同名词而挂钩）。
  处置：**判定为判据假阳性，不改 05/07 以求绿**（同 R263 精神：先证判据再动数据）。

- ⚠️ `handoff.py sync` 的自动检测对本项目结构**部分失效**（实测 2026-09-22）：02 目录树可用但含 `.codebuddy/`/`.wrangler/` 等 ignore 目录；03 报「未检测到技术栈配置文件」（因 `pom.xml` 在 `server/` 子目录，sync 只扫项目根）；04 会把 `deploy/cloudbase/functions/chat/index.js` 当入口（真入口是 `src/index.html` + `SoulIsleApplication.java`）。
  处置：**以手工区内容为准**，自动块仅作参考；已在 02/03/04 的手工区加注记说明。

<!-- 验证通过后标记 - [x]，归档时自动移入 archive -->
