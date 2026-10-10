# 第三方资产与授权说明（THIRD-PARTY-NOTICES）

> 为什么单列这个文件：`LICENSE` 是 MIT，但**MIT 只覆盖本项目自研代码**。
> `src/vendor/`（以及其公网副本 `deploy/xinyu/vendor/`）里的第三方库、以及 `_test/vendor/` 里的测试专用第三方资产，
> 各有自己的授权条款，其中 **GSAP / ScrollTrigger 不是 MIT**（banner 自证：`@license Copyright 2026, GreenSock. All rights reserved.
> Subject to the terms at https://gsap.com/standard-license`），**axe-core 也不是 MIT**（是 **MPL-2.0**）。
> 把整个仓库一律标成 MIT 是**不准确的授权声明** —— 本文件把边界写清，并由
> `_test/repo_config_check.py` 的 G6/G7 判据保证不脱管（缺文件、漏登记某个 vendored 库、
> 登记行里不写许可条款、README 缺授权口径行 ⇒ 直接报红）。
>
> ⚠️ **r46 补记一条自己的漏**：G6 的分母原先写死 `src/vendor/*.js`，于是 r42 引入的
> `_test/vendor/axe-core-4.10.2.min.js` 在授权边界上隐形了一整轮（正文那句"`_test/` … 全部原创"当时即为假陈述）。
> 同族缺陷 r43 已在 `vendor_freshness_check.py` 上治过一次（当时只修了那一处），本轮把 G6 的分母也改成
> **从 `vendor-manifest.json` 现读**，并加"表行必须含许可条款"的对账，防止"提个文件名"被当成已声明。

## 逐文件清单（哈希与版本以 `_test/vendor-manifest.json` 为唯一声明源，由 `vendor_freshness_check.py` 校验）

| 文件 | 库 / 版本 | 授权 | 上游 | 用途 | 再分发注意 |
|---|---|---|---|---|---|
| `src/vendor/three.min.js` | three.js **r128** | **MIT**（banner `@license Copyright 2010-2021 Three.js Authors`） | https://github.com/mrdoob/three.js | 3D 情绪星雾（WebGL 粒子） | MIT 允许随仓库再分发，需保留版权行（已保留在文件头） |
| `src/vendor/gsap.min.js` | GSAP **3.15.0** | **GreenSock Standard License**（非 MIT、非 OSI；免费用于非竞争性产品） | https://gsap.com / https://github.com/greensock/GSAP | 五幕滚动叙事的补间 | 随源码分发允许，但**不得**用它构建与 GSAP 竞争的动画产品；条款以 https://gsap.com/standard-license 为准 |
| `src/vendor/ScrollTrigger.min.js` | ScrollTrigger **3.15.0** | **GreenSock Standard License**（同 GSAP 主库，成对使用） | 同上 | 滚动进度驱动与 `ScrollTrigger.refresh()` | 同上；两文件必须同版本（由 `vendor_freshness_check.py` V2 版本对账保证） |
| `_test/vendor/axe-core-4.10.2.min.js` | axe-core **4.10.2** | **MPL-2.0**（banner 自证 `Copyright (c) 2015 - 2024 Deque Systems, Inc.` + `Mozilla Public License, v. 2.0`） | https://github.com/dequelabs/axe-core | r42 起的运行时无障碍审计引擎（`a11y_check.py` 注入用） | **不进公网 bundle**（判据依赖而非首屏载荷）；MPL 是**文件级**copyleft ⇒ 不修改该文件即无开源义务外溢，若打补丁则须按 MPL 提供该文件的源码可用版本；版权行已保留在文件头 |
| `src/vendor/mediapipe/vision_bundle.js` | @mediapipe/tasks-vision **0.10.22-rc.20250304** | **Apache-2.0**（上游 banner 在本仓这份里已被压缩，许可全文以同目录 `LICENSE-Apache-2.0.txt` 旁证） | https://github.com/google-ai-edge/mediapipe | r87 面部表情识别：FaceLandmarker 的 ESM 入口 | **懒加载**：只在用户点开表情感知时才下载；上游文件名为 `vision_bundle.mjs`，本仓因静态托管对 `.mjs` 的 MIME 不统一而改名 `.js`（内容字节未改，sha256 与上游一致） |
| `src/vendor/mediapipe/vision_wasm_internal.js` | MediaPipe vision wasm loader（SIMD）**0.10.22-rc.20250304** | **Apache-2.0**（同目录 `LICENSE-Apache-2.0.txt` 旁证） | 同上 | wasm 加载器（SIMD 版） | 同上；**未 vendor 非 SIMD 套件**（9.4MB）：目标浏览器自 2021 年起全支持 SIMD，非 SIMD 浏览器由 `face-engine.js` 显式探测并降级为"不可用"，不白屏 |
| `src/vendor/mediapipe/vision_wasm_internal.wasm` | MediaPipe vision wasm binary（SIMD）**0.10.22-rc.20250304** | **Apache-2.0**（二进制无法自带 banner ⇒ 同目录 `LICENSE-Apache-2.0.txt` 旁证） | 同上 | 推理内核（9.57MB） | 懒加载；`.gitattributes` 已钉 `*.wasm binary`，字节永不被行尾改写（否则哈希类判据在他人机器上不可复算） |
| `src/vendor/mediapipe/face_landmarker.task` | MediaPipe FaceLandmarker model **float16/1** | **Apache-2.0**（模型权重随上游 Apache-2.0 分发；同目录 `LICENSE-Apache-2.0.txt` 旁证） | https://ai.google.dev/edge/mediapipe | 人脸关键点 + 52 维 blendshape 的模型权重（3.76MB） | 懒加载；**不可再训练再分发**以外的用途均在上游许可内；本仓不修改权重、不落任何人脸数据（画面只在内存里过一遍，零上传零落盘） |

## 本项目自研代码

除上表**八个**文件（`src/vendor/` 三件 + `src/vendor/mediapipe/` 四件及其在 `deploy/xinyu/vendor/` 的
逐字节副本，加上 `_test/vendor/` 的 axe-core 测试资产）外，`src/`、`server/`、`_test/`（`_test/vendor/` 除外）、
`deploy/functions/` 等全部由心屿 MindIsle 团队原创，按 `LICENSE` 的 **MIT** 授权。

## 参赛与展示场景的口径（本项目实际情形）

- 本项目是**高校参赛演示作品**，非商业发行物，且不使用 GSAP 构建与其竞争的动画库/插件 ⇒ 落在 GreenSock
  Standard License 的免费使用范围内。
- 公网副本（Cloudflare Pages）与 fat jar 部署包都会原样携带上述三个 vendor 文件，因此本文件必须随仓库存在；
  若日后**更换 GSAP**（如改 Web Animations API 或改用 `@gsap/shim` 之外的授权版本），需同步更新本表与
  `vendor-manifest.json`，并由 `vendor_freshness_check.py` 的哈希判据确认文件真被替换（防"改了声明没改文件"或反之）。

## 机器责任（谁保证这张表不烂）

| 判据 | 命令 | 断言 |
|---|---|---|
| G6 | `python _test/repo_config_check.py` | 分母 = `vendor-manifest.json` 的 `libs[].file`（**名册现读，不再扫死目录**）：每个 vendored 文件都必须在本表有一行，**且行内写明许可条款**（写"见上游"视为未声明即红）；名册含非 `src/` 件时本文必须交代 `_test/vendor` 边界 |
| G7 | 同上 | README 必须存在"第三方授权"口径行（防止有人删掉边界说明，把仓库重新说成纯 MIT） |
| V1/V2 | `python _test/vendor_freshness_check.py` | 版本与 sha256 与 `vendor-manifest.json` 对账（内容与声明不符即红） |
| 副本一致 | `python _test/deploy_sync_check.py` | `src/` ↔ `deploy/xinyu/` 三类归零（含 vendor，防公网副本与授权表脱节） |
