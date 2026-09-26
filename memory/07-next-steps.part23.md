# 07 - 下一步 · 卷23（r35 人工拆卷：已完成条目 r33 公网重部署 / r34 成片再录，逐字迁自 `07-next-steps.md` 主壳，未改写）
- [x] ✅ **r33 公网已重部署并复核**（deployment `b5f46ecf`）：`LIVE-SYNC-PASS`（逐字节等）+
      `PUBLIC-ONLINE-ALL-PASS`（标签实测「在线大模型生成 · 逐字流式」/ 危机 True / console 0）+
      `/api/chat` 200 + 公网 `app.js` 含降级徽章、`chat-window.js` 含诚实标签。
      ⚠️ 部署命令必须 `cd deploy` 再跑（Functions 目录按 cwd 解析，日志须见 "Uploading Functions bundle"）。
- [x] ✅ **r34 成片再录完成**：`RECORD-PASS scenes: 8` + `VIDEO-PIPELINE-PASS dur=218.5s`，抽帧目检画面已含
      「本机开场白 · 未经大模型」+「● 在线 AI」；配置按 sha256 逐字节还原、公网 stub 未触碰、
      `public_check` → `KEY_LEAK: False`。指纹与代际**不抄在这里**：见提交清单第 2 行。
