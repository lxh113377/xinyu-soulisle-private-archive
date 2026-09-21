# 心屿 SoulIsle — 2026 iCAN AI应用创新挑战赛·软件赛道

对话陪聊 + 情感陪伴：滚轮驱动的 3D 情绪叙事页（WebGL + GSAP），AI 共情链路真实嵌入。

**在线演示（双线并存）**

- 主推：**https://xinyu-soulisle.pages.dev** —— 评委免配置即在线AI；LLM 经同源 `/api/chat` Cloudflare Function 代理，密钥隔离服务端。实测浏览器可直开、无任何中间页。
- 国内备用：**https://qwer-d4gf2r76o8829463b-1458054906.tcloudbaseapp.com** —— 腾讯云 CloudBase 静态托管 + 云函数 `chat` 代理（密钥在云端环境变量，前端零密钥）。
  ⚠️ 该地址是平台**测试域名**，浏览器首次打开会出现「风险提醒」中间页，**点一下「确定访问」即可**（之后同浏览器不再弹）；换设备/清缓存会再弹一次。这是平台合规策略，绑定**已备案的自定义域名**后中间页才会消失。

## 本地运行
```powershell
python -m http.server 8123 --directory src
# 浏览器打开 http://localhost:8123
```
零构建、零依赖安装（vendor 已本地化）。本机演示为**评委体验模式**（`src/js/demo-config.js` 预置 DeepSeek Key，自动切换"在线 AI"；可一键清除）。🔴 该文件含密钥：源码提交/公网部署前必须排除（公网部署版用 proxy stub，见 deploy/ 目录）。

## 部署（双平台并存，同一份前端产物）

前端产物 `deploy/xinyu/` 里 `js/demo-config.js` 会**按域名自适应**：`*.tcloudbaseapp.com` 走 CloudBase 云函数，其余走同源 `/api/chat`。所以同一份产物两个平台通用。

```powershell
# ① Cloudflare Pages（境外/兜底，浏览器直开无中间页）
#    密钥：wrangler pages secret put DEEPSEEK_KEY --project-name=xinyu-soulisle（勿入源码）
cd deploy
npx wrangler pages deploy xinyu --project-name=xinyu-soulisle --commit-dirty=true

# ② 腾讯云 CloudBase 静态托管（国内备用；环境 qwer-d4gf2r76o8829463b，有效期至 2027-03-14）
cd deploy\cloudbase
tcb fn deploy chat --dir functions/chat --runtime Nodejs20.19 --install-dependency false --force --path /api
tcb hosting deploy ../xinyu / -e qwer-d4gf2r76o8829463b
```

CloudBase 注意事项（实测得来）：
- 云函数 `chat` 的 HTTP 访问服务地址 = `https://qwer-d4gf2r76o8829463b.service.tcloudbase.com/api`（`OPTIONS→204` / `POST→200` 实测通过）。
- **密钥只在云端**：首次部署时经 `cloudbaserc.json` 的 `envVariables` 写入后已抹除；要更换请在控制台 → 云函数 `chat` → 配置 → 环境变量里设置（CLI 只有 `fn env pull`，不能 push）。
- **测试域名中间页**：浏览器首访会出现「风险提醒」，点一次「确定访问」放行（同浏览器记住；换设备/清缓存会再弹）。官方文档明确：去掉中间页**只能绑定已 ICP 备案的自定义域名**，无免备案开关；且文档不建议默认域名用于生产分发（有风控关停风险）。
- 静态托管的默认首页文档已是 `index.html`，根路径 `/` 可直接访问。

## 目录结构
```
src/            工作区（可运行原型）
  index.html    5幕叙事页
  css/          设计令牌与样式
  js/           emotion-engine / chat-agent / three-scene / scroll-story / memory-store / app / demo-config(本地Key)
  functions/api/chat.js  Cloudflare Pages Function（LLM代理，密钥在env）
  vendor/       three.js r128 + gsap 3.12（本地化）
deploy/         部署产物（xinyu/ 静态副本[proxy stub] + functions/ + wrangler.toml）
交付物/
  提交包/       应用方案大纲、演示视频脚本（待扩写为PDF/MP4）
  iCAN评审/     01评分机制 02诊断 03优先级 04答辩与风险 05差距 + 截图
memory/         项目记忆（A-project-handoff）
_test/          浏览器实测脚本（回归证据）
```

## 验证
```powershell
python _test/browser_check.py   # 需 http.server 8123 在线；输出 ALL-ASSERT-PASS
```
最近实测（2026-09-19）：console 0 报错；情绪探针/危机转介/对话降级/曲线记录/滚动驱动全断言通过。

## 当前状态与待办
见 `memory/07-next-steps.md`。提交截止 **2026-09-30**（官网 www.g-ican.com）。
