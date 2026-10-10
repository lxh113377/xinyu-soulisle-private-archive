# r103 部署段 · 公网部署现场记录

## 一句话结论

**部署成功**：`deploy/xinyu` → `https://xinyu-soulisle.pages.dev`，
`LIVE-SYNC-PASS`（24/24 逐字节）、`PUBLIC-ONLINE-ALL-PASS`（10 腿）、`FACE-PUBLIC PASS`（公网真脸出 joy/duchenne 0.81）。

## 正确的部署命令（记牢，别再猜）

```bash
# 必须 cd 到 **deploy/**（wrangler.toml 所在目录），不是项目根，也不是 deploy/xinyu
cd deploy
wrangler pages deploy xinyu --commit-dirty=true
```

**判据在回执里**：输出必须含 `Compiled Worker successfully` + `Uploading Functions bundle`。
缺这两行 = Functions 没打包进去，`POST /api/chat` 会从 `400 bad-json` 变 `405 Method Not Allowed`。

### 我从 r101 报告读过但理解错了的那条

r101 §2 写「从项目根跑会丢 Functions ⇒ 从 `<staging>` 跑」。
我照字面在 `deploy/xinyu` 里跑 → 第一发 Functions 又丢了。
**真实规则不是"在产物目录里跑"，而是"在 wrangler.toml 所在目录跑"**：
wranger 从 **cwd** 的平级找 `functions/`，而本仓 `functions/` 位于 `deploy/functions`
（`deploy/wrangler.toml` 的 `pages_build_output_dir = "xinyu"` 指向产物子目录）
⇒ 只有 cwd = `deploy/` 时才能同时看到 `xinyu/` 与 `functions/`。

**教训**：报告里的命令要连它的**目录前提**一起读。
「从 staging 跑」的 staging 当初指的是含 functions 与 toml 的那一层，不是产物目录。

## 顺手修好的环境债（两个平台包缺失）

全局 wrangler 崩在两处 `generateBinPath`，都是 npm 全局安装时**可选的平台包没装上**
（本机 npm 装全局装时跳过了 optionalDependencies）：

| 缺失包 | 报错位置 | 修法 |
|---|---|---|
| `@cloudflare/workerd-windows-64` | `wrangler/node_modules/workerd/lib/main.js` | `npm i -g @cloudflare/workerd-windows-64` |
| `@esbuild/win32-x64@0.28.1` | `wrangler/node_modules/esbuild/lib/main.js` | `npm i -g @esbuild/win32-x64@0.28.1` |

⚠️ esbuild 的包名**不匹配 wrangler 内版本会 404/解析失败**：
wrangler 4.124.0 内嵌 esbuild 0.28.1 ⇒ 必须装同版本的 `@esbuild/win32-x64`。
（`@esbuild/windows-64` 是旧命名，已 404。）

## 关于「Functions 是不是我这发弄丢的」——取证结论

第一发之后我立刻查了**旧生产别名** `https://xinyu-soulisle.pages.dev/api/chat`
⇒ **也是 405（空 body）**，与本发的新部署子域表现一致。
⇒ Functions 在**本轮之前就已经不在线上了**，不是 r102/r103 改出来的。
但我这一发（从 `deploy/xinyu` 跑）也没有修好它，所以两者都算我没看好 ——
区别只在"不是我打破的"，验收标准不能因此降低。

## 已入账的验收结论（供下轮读）

- `python _test/live_sync_check.py` → `LIVE-SYNC-PASS`（24 项逐字节）
- `python _test/public_check.py` → `PUBLIC-ONLINE-ALL-PASS`（10 腿，P6/P8/P9 全过）
- `python _test/face_check.py --public https://xinyu-soulisle.pages.dev` → `FACE-PUBLIC PASS`
  （wasm 200、bundle 200、公网真脸 `joy/duchenne 强度=0.81`、星雾驱动）
- 本轮改的 4 个文件（face-smile-rules / face-engine / app.js / style.css）全部上线