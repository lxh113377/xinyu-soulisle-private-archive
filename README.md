# 心屿 SoulIsle

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/lxh113377/xinyu-soulisle-private-archive/actions/workflows/ci.yml/badge.svg)](https://github.com/lxh113377/xinyu-soulisle-private-archive/actions/workflows/ci.yml)
[![情绪评测](https://img.shields.io/badge/%E6%83%85%E7%BB%AA%E8%AF%84%E6%B5%8B-98.6%25%20%2F%2073%E6%9D%A1-brightgreen)](#-验证)
[![危机召回](https://img.shields.io/badge/%E5%8D%B1%E6%9C%BA%E5%8F%AC%E5%9B%9E-6%2F6-red)](#-功能概览)
[![零密钥](https://img.shields.io/badge/%E5%AF%86%E9%92%A5%E6%B3%84%E9%9C%B2-0-blueviolet)](SECURITY.md)
[English](README.en.md)

<details open><summary><b>目录</b></summary>

- [功能概览](#-功能概览) · [技术栈](#-技术栈) · [快速开始](#-快速开始) · [架构](#-架构) · [目录结构](#-目录结构) · [部署](#-部署) · [验证](#-验证) · [文档](#-文档) · [免责声明](#-免责声明) · [许可证](#-许可证) · [状态](#-状态)

</details>

> 对话陪聊 + 情感陪伴的 AI 网页应用：以滚轮驱动的 **3D 情绪叙事页**（WebGL + GSAP）承载一条真实的 AI 共情链路。
>
> 情绪识别 → 共情策略 → 在线 LLM 生成 → 情绪可视化（星雾变色与点亮）→ 记忆留存，形成闭环，而不是套壳聊天框。

**在线演示（双线并存）**

- **主推**：https://xinyu-soulisle.pages.dev —— 评委免配置即在线 AI；LLM 经同源 `/api/chat`（Cloudflare Pages Function）代理，密钥隔离在服务端。实测浏览器可直开、无中间页。
- **国内备用**：https://qwer-d4gf2r76o8829463b-1458054906.tcloudbaseapp.com —— 腾讯云 CloudBase 静态托管 + 云函数 `chat` 代理（密钥在云端环境变量，前端零密钥）。
  ⚠️ 该地址是平台**测试域名**，首次打开会出现「风险提醒」中间页，**点一下「确定访问」即可**（同浏览器此后不再弹；换设备/清缓存会再弹一次）。这是平台合规策略，绑定**已备案的自定义域名**后中间页才会消失。

---

## ✨ 功能概览

| 模块 | 说明 |
|---|---|
| 3D 情绪星雾 | Three.js 粒子星云，滚动驱动镜头；检测到的情绪会点亮对应颜色的星（主色 n 颗 + 次色 n/2 颗） |
| 五幕滚动叙事 | GSAP + ScrollTrigger 驱动的叙事页：相遇 → 情绪探针 → AI 对话 → 情绪曲线 → 陪伴 |
| 双路情绪识别 | **词典快判**（本地，零延迟）+ **LLM 精判**，两路一致采信 LLM、分歧亦采信 LLM、LLM 失败回落词典；判定路径在界面上明示 |
| 危机优先拦截 | 危机词命中即最高优先级，**不调用 LLM**，直接返回求助热线转介（实测危机召回 6/6） |
| 情绪曲线 | Canvas 2D 绘制历次情绪强度变化 |
| 对话与记忆 | 在线 LLM 生成共情回复；本机 `localStorage` 持久化，服务端持久化可选开启（`cfg.remote`） |
| **逐字流式输出** | `stream:true` → 同源代理 SSE 直通，回复边生成边显示；代理不支持流式时**按 content-type 自动回落整包**，不留半成品气泡 |
| **共情策略表 SSOT** | 每种情绪的共情要点 / 离线模板 / 采样参数集中在 `src/data/emotion-strategy.js`（与词表同形态的纯 JSON），**加一类情绪只改数据文件，代码零改动** |
| **多模型 provider** | `LLM_BASE/LLM_MODEL/LLM_KEY` 通用环境变量（`DEEPSEEK_*` 保留兼容），设置面板内置 DeepSeek / OpenAI / 通义 / Kimi / 本地 Ollama 快捷预设 |
| 语音输入 + 回复朗读 | Web Speech API：ASR（zh-CN）语音输入 ＋ `speechSynthesis` 逐条朗读（可开关，实测关得掉）；浏览器不支持即隐藏按钮 |
| 长会话窗口化 | 对话列表 DOM 上界 60 条，较早记录折叠可分批展开；模型上下文与情绪记忆不受窗口化影响（判据实测） |
| 响应式与降档 | 480/768/1024 三档断点 + 星雾粒子按视口降档（手机 900 / 平板 1200 / 桌面 2600），移动端无横向溢出 |
| 优雅降级 | WebGL 不可用 → CSS 渐变；LLM 不可用 → 离线共情模板。⚠️ **降级在界面上明示，绝不把模板伪装成在线 AI** |

---

## 🧩 技术栈

| 层 | 选型 | 备注 |
|---|---|---|
| 前端 | 原生 ES Module + Three.js（本地 vendor）+ GSAP/ScrollTrigger（本地 vendor） | **零构建、零 `node_modules`** |
| 前端存储 | `localStorage`（键 `peiliao.*.v1`） | 离线可用 |
| 服务端 | Spring Boot 3.2.5 / JDK 17 / MyBatis-Plus 3.5.7 | `server/`，单体应用 |
| 数据库 | H2 file（默认，`server/data/`）；MySQL 8 驱动已引入可切 | 表：`chat_message` / `emotion_record` |
| LLM | 任意 OpenAI 兼容上游（默认 DeepSeek）；JDK 内置 `HttpClient` 转发 | `LLM_*`／`DEEPSEEK_*` 双名，密钥走环境变量，**零落前端、零入库** |
| 鉴权 | 轻量 token 过滤器（`xinyu.api-token`，留空 = 放行） | 私有部署时可选开启 |
| 部署 | 静态托管 / fat jar / Docker | 三选一，互不影响 |

---

## 🚀 快速开始

### ① 静态页（最轻，前端-only）

```powershell
python -m http.server 8123 --directory src
# 浏览器打开 http://localhost:8123
```

零构建、零依赖安装（vendor 已本地化）。
本机演示为**体验模式**：`src/js/demo-config.js` 预置配置，自动切换「在线 AI」（可一键清除）。
🔴 **该文件含真实 API Key，已被 `.gitignore` 排除，绝不入库、绝不进镜像**；公网部署用 `deploy/xinyu/js/demo-config.js`（零密钥同源代理版）。

### ② fat jar（Java 服务端，含全部 API）

```powershell
# ⚠️ 系统默认 JAVA_HOME 是 JDK 8，本项目必须显式切到 JDK 17
$env:JAVA_HOME = "C:\Program Files\Eclipse Adoptium\jdk-17.0.20.101-hotspot"
& "$env:USERPROFILE\.local\maven\apache-maven-3.9.9\bin\mvn" -f server/pom.xml package

# ⚠️ 工作目录必须是仓库根：服务端直读 ./src/（零副本策略，见下文「架构」）
java -jar server\target\soulisle-server.jar --server.port=8123
```

### ③ Docker

```powershell
# build context 必须是仓库根
mvn -f server/pom.xml package
docker build -f server/Dockerfile -t xinyu-soulisle .

# 密钥只走环境变量，绝不打进镜像
docker run -p 8080:8080 -e DEEPSEEK_KEY=sk-xxx -v xinyu-data:/app/data xinyu-soulisle
```

⚠️ 构建前**必须先同步 `deploy/xinyu/` 并跑 SHA256 双向比对**（同步红线），否则会把过时的前端打进镜像。

---

## 🏗 架构

```
浏览器（src/ 或 deploy/xinyu/）
   │ 同源 HTTP
   ▼
Spring Boot（server/）
   ├── /api/health          健康检查（回传 webRoot / indexFound / vendorFound 作可复核判据）
   ├── /api/chat            LLM 代理（契约与 v1 Pages Function 1:1）
   ├── /api/emotion         服务端情绪识别（词典 + LLM 双路 + 危机优先）
   ├── /api/emotion/eval    复跑评测集，输出与前端引擎同构的逐项结果
   └── /api/memory/**       对话与情绪记录 CRUD + stats（J4，默认关闭）
```

**两条关键设计约束（改代码前请先读）**

1. **零副本：前端静态页直读 `src/`** —— `spring.web.resources.static-locations=file:${XINYU_WEB_ROOT:./src/}`。不复制进 `src/main/resources/static/`，避免出现第三处需要同步的副本。代价：启动时工作目录必须是仓库根。
2. **评测集直读 `_test/emotion-eval-dataset.json`**，不复制进 jar —— 保证「Java 侧跑的就是 JS 侧跑的那份数据」，这也是双端逐项对账能一致的前提。

---

## 📁 目录结构

```
src/                     权威源码（唯一改这里）
  index.html             五幕叙事页 + 底部对话坞 + 星雾 canvas
  css/                   设计令牌与样式
  js/                    emotion-engine / chat-agent / three-scene / scroll-story /
                         memory-store / app / demo-config(本地 Key，已 ignore)
  vendor/                three.js + gsap + ScrollTrigger（本地化）
  functions/api/chat.js  Pages Function 源
deploy/                  部署产物（改完 src/ 必须同步此处并做 SHA256 双向比对）
  xinyu/                 前端公网副本（js/demo-config.js 为零密钥代理版）
  functions/             Cloudflare Pages Function
  cloudbase/             腾讯云 CloudBase 云函数
server/                  Spring Boot 工程（J1–J5）
交付物/                  iCAN 评审文档、截图、提交包
_test/                   常驻回归脚本与评测集
memory/                  项目交接记忆
```

---

## 🚢 部署

前端产物 `deploy/xinyu/` 里的 `js/demo-config.js` **按域名自适应**：`*.tcloudbaseapp.com` 走 CloudBase 云函数，其余走同源 `/api/chat`。同一份产物两个平台通用。

```powershell
# ① Cloudflare Pages（境外/兜底，浏览器直开无中间页）
#    密钥：wrangler pages secret put DEEPSEEK_KEY --project-name=xinyu-soulisle（勿入源码）
cd deploy
npx wrangler pages deploy xinyu --project-name=xinyu-soulisle --commit-dirty=true

# ② 腾讯云 CloudBase（国内备用；环境 qwer-d4gf2r76o8829463b，有效期至 2027-03-14）
cd deploy\cloudbase
tcb fn deploy chat --dir functions/chat --runtime Nodejs20.19 --install-dependency false --force --path /api
tcb hosting deploy ../xinyu / -e qwer-d4gf2r76o8829463b
```

CloudBase 注意事项（实测得来）：

- 云函数 `chat` 的 HTTP 访问服务地址 = `https://qwer-d4gf2r76o8829463b.service.tcloudbase.com/api`（`OPTIONS→204` / `POST→200` 实测通过）。
- **密钥只在云端**：首次部署经 `cloudbaserc.json` 的 `envVariables` 写入后已抹除；更换请在控制台 → 云函数 `chat` → 配置 → 环境变量里设置（CLI 只有 `fn env pull`，不能 push）。
- **测试域名中间页**：首访会出现「风险提醒」，点一次「确定访问」放行（同浏览器记住；换设备/清缓存会再弹）。官方文档明确：去掉中间页**只能绑定已 ICP 备案的自定义域名**，无免备案开关；且不建议默认域名用于生产分发（有风控关停风险）。

---

## ✅ 验证

```powershell
python _test/browser_check.py            # 离线降级 / 双色 / 滚动淡入淡出，输出 ALL-ASSERT-PASS
python _test/deploy_sync_check.py        # src → deploy/xinyu 三类比对（MISSING/DIFF/EXTRA 归零）
python _test/engine_consistency_check.py # JS 引擎 ↔ Java 引擎逐项对账（词表结构级）
python _test/strategy_check.py           # 共情策略表 ↔ 词表成对性（--selftest 注入分叉证判据非恒真）
node _test/emotion_eval.js               # 前端情绪评测集复跑
python _test/stream_contract.py          # A 非流式契约不破 / B SSE 含内容帧≥2 / C 前端逐字且回落不冒充
python _test/ux_guards_check.py          # TTS 朗读 / 对话窗口化 / 响应式与粒子降档（逐项 21 判据）
```

GitHub Actions 三条门禁（`.github/workflows/ci.yml`）：同步守卫+评测+策略表+密钥扫描、Java 构建+**词表一致性红线**（此前只写在 `memory/AGENTS.md` 靠人记，现已机器化）、浏览器回归（runner 无 GPU，强制 SwiftShader）。
三条 job **均在 GitHub 真跑验证**；浏览器 job 首轮就抓到本机看不到的真实缺陷：`src/js/demo-config.js` 被 gitignore，全新 clone 下 `<script>` 静态引它 → 首屏 3 个 404 打破「console 0 报错」。修法＝CI 自动用公网零密钥 stub 补占位（本地按 `CONTRIBUTING.md` 第一步手工补一次）。

最近实测（2026-09-24 对标轮）：`browser_check` ALL-ASSERT-PASS；情绪评测 **73 条 / 98.6% / 危机 6-6**（JS ↔ Java 逐项全等）；`stream_contract` A/B/C 全 PASS（SSE 32 帧 / 30 含内容帧 / 拼回 51 字）；`ux_guards_check` 21/21；`deploy_sync_check` 三类归零。

---

## 📚 文档

| 文档 | 内容 |
|---|---|
| [CONTRIBUTING.md](CONTRIBUTING.md) | 环境要求、五条红线（密钥/同步/词表一致性/契约/策略表成对性）、开发流程与提交规范 |
| [SECURITY.md](SECURITY.md) | 密钥政策、接口安全、漏洞上报 |
| [CHANGELOG.md](CHANGELOG.md) | 版本变更史（Keep a Changelog） |
| [.env.example](.env.example) | 全部环境变量文档化（名称实读自配置与函数源码） |
| [ROADMAP.md](ROADMAP.md) | 公开路线图（对标差距 → 已完成 / 进行中 / 计划 / 明确不做，含"为什么不做"） |
| [交付物/对标分析报告-2026-09-24.md](交付物/对标分析报告-2026-09-24.md) | 与 LobeChat / Open-LLM-VTuber / SillyTavern 的七维度对标与差距清单 |
| [交付物/对标分析报告-2026-09-24-v2.md](交付物/对标分析报告-2026-09-24-v2.md) | 第二轮：14 仓实测指标横向对账（含同体量垂类项目）+ 本轮已落地项与实证 |
| `memory/` | 项目交接记忆（目标/结构/技术栈/决策记录/验收标准），工程过程档案 |

---

## ⚠️ 免责声明

本项目用于**技术研究与情感陪伴**，**不提供医疗诊断或专业心理治疗**。
遇到紧急危险或自伤风险，请立即联系当地急救机构或危机干预热线（全国心理援助热线 **12356**，24 小时）。

---

## 📄 许可证

[MIT License](LICENSE) © 2026 心屿 SoulIsle 团队

---

## 📌 状态

2026 iCAN AI 应用创新挑战赛·软件赛道参赛作品。提交截止 **2026-09-30**（官网 www.g-ican.com）。
详细进度与待办见 `AGENTS.md` 与 `memory/`。
