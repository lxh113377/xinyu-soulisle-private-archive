# Security Policy

## 密钥政策（本项目最高红线）

- **任何密钥（LLM API Key、数据库口令、鉴权 token）禁止写入前端源码、禁止提交入库、禁止打进 Docker 镜像。**
- 唯一合法入口是环境变量 / 平台侧密钥管理：
  - Cloudflare Pages：`wrangler pages secret put DEEPSEEK_KEY --project-name=xinyu-soulisle`
  - CloudBase：控制台 → 云函数 `chat` → 环境变量（CLI 不能 push）
  - Java 服务端：`DEEPSEEK_KEY` / `XINYU_API_TOKEN`（见 `.env.example`）
- `src/js/demo-config.js`（含本机演示 Key）已在 `.gitignore`；机器校验由 `_test/public_check.py`（`KEY_LEAK: False`）与 CI 承担。
- 提交历史扫描红线：`git grep -E "sk-[A-Za-z0-9]{20,}" HEAD` 必须 0 命中。

## 接口安全

- `/api/chat`、`/api/emotion`、`/api/memory/**` 支持可选 token 鉴权（`XINYU_API_TOKEN`，留空 = 放行，仅演示默认）。私有部署务必置非空。
- LLM 上游地址只来自服务端配置（`DEEPSEEK_BASE`），永不接受请求体传入，杜绝 SSRF 注入面。

## 漏洞报告

本项目为 2026 iCAN 参赛作品，仓库暂未开启 GitHub Security Advisories。
发现安全缺陷请通过仓库 Issues 的 **security** 标签私密联系维护者（或提交后立刻编辑标题为 `[DO-NOT-INDEX]`），勿在公开场合贴出可复现的利用细节。

## 免责声明

产品定位为情感陪伴，不提供医疗诊断或心理治疗；危机信号触发的是求助热线转介（全国心理援助热线 12356），不是专业干预。
