# 07-next-steps.part9.md

<!-- 本卷为 07-next-steps.part6.md 的延续 -->

- [ ] 🔴 **iCAN 提交硬截止 2026-09-30**（今天 09-22，剩 8 天；截止即锁团队信息）：官网报名 + 提交。缺件风险：官方要《应用方案》PDF（≤20 页），而该项此前按老大 09-19「视频/PPT/PDF 不管」指令被冻结 —— 需一句话解冻即开做
- [x] ~~CloudBase 国内线决策~~ ✅ 2026-09-22 老大定：**接受中间页，仅作备用**（零成本，保持现状）。注意：CloudBase 云函数的 Key 仍是旧值（CLI 无 `fn env push`，只能控制台改）；若旧 Key 被平台作废，国内备用线会失效，需在控制台同步新 Key
- [x] ~~云端密钥轮换~~ ✅ 2026-09-22：新 Key 实测 `200 OK` → `wrangler pages secret put DEEPSEEK_KEY`（**wrangler@3 报错，@4 成功**）+ `pages deploy` 重部署使其生效（secret 需新部署才绑定）→ 生产 `PUBLIC-ONLINE-ALL-PASS`（在线 AI 1206ms、`KEY_LEAK: False`）
- [x] ~~部署在线演示~~ ✅ 2026-09-19 Cloudflare：**https://xinyu-soulisle.pages.dev** （Pages + Function 代理 /api/chat，密钥在 env，前端零密钥）；✅ 2026-09-20 加国内线：**https://qwer-d4gf2r76o8829463b-1458054906.tcloudbaseapp.com**（CloudBase 静态托管 + 云函数 chat，环境有效期至 2027-03-14）。两端均实测 PUBLIC-ONLINE-ALL-PASS；前端 demo-config 按域名自适应指向对应代理
- [x] ~~**待老大决策**（CloudBase 中间页）~~ ✅ 2026-09-22 老大定：**选 ① 接受中间页，CloudBase 仅作备用**（零成本，保持现状）。背景：测试域名首访有「风险提醒」中间页（点一次放行；官方无免备案开关，需绑 ICP 备案自定义域名才能去掉，且默认域名有风控关停风险）。②办备案约 1–3 周（赶得上 10 月复赛但赶不上 09-30 提交）；③撤回国内线 —— 均未采用

## 分卷目录
- **卷1** `07-next-steps.part5.md` — 07-next-steps 分卷（R199 自动拆卷）

