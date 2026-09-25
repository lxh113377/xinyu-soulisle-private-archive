# 第三方资产与授权说明（THIRD-PARTY-NOTICES）

> 为什么单列这个文件：`LICENSE` 是 MIT，但**MIT 只覆盖本项目自研代码**。
> `src/vendor/`（以及其公网副本 `deploy/xinyu/vendor/`）里的第三方库各有自己的授权条款，
> 其中 **GSAP / ScrollTrigger 不是 MIT**（banner 自证：`@license Copyright 2026, GreenSock. All rights reserved.
> Subject to the terms at https://gsap.com/standard-license`）。
> 把整个仓库一律标成 MIT 是**不准确的授权声明** —— 本文件把边界写清，并由
> `_test/repo_config_check.py` 的 G6/G7 判据保证不脱管（缺文件、漏登记某个 vendor 库、README 缺授权口径行 ⇒ 直接报红）。

## 逐文件清单（哈希与版本以 `_test/vendor-manifest.json` 为唯一声明源，由 `vendor_freshness_check.py` 校验）

| 文件 | 库 / 版本 | 授权 | 上游 | 用途 | 再分发注意 |
|---|---|---|---|---|---|
| `src/vendor/three.min.js` | three.js **r128** | **MIT**（banner `@license Copyright 2010-2021 Three.js Authors`） | https://github.com/mrdoob/three.js | 3D 情绪星雾（WebGL 粒子） | MIT 允许随仓库再分发，需保留版权行（已保留在文件头） |
| `src/vendor/gsap.min.js` | GSAP **3.15.0** | **GreenSock Standard License**（非 MIT、非 OSI；免费用于非竞争性产品） | https://gsap.com / https://github.com/greensock/GSAP | 五幕滚动叙事的补间 | 随源码分发允许，但**不得**用它构建与 GSAP 竞争的动画产品；条款以 https://gsap.com/standard-license 为准 |
| `src/vendor/ScrollTrigger.min.js` | ScrollTrigger **3.15.0** | **GreenSock Standard License**（同 GSAP 主库，成对使用） | 同上 | 滚动进度驱动与 `ScrollTrigger.refresh()` | 同上；两文件必须同版本（由 `vendor_freshness_check.py` V2 版本对账保证） |

## 本项目自研代码

除上表三个文件（及其在 `deploy/xinyu/vendor/` 的逐字节副本）外，`src/`、`server/`、`_test/`、`deploy/functions/`
等全部由心屿 SoulIsle 团队原创，按 `LICENSE` 的 **MIT** 授权。

## 参赛与展示场景的口径（本项目实际情形）

- 本项目是**高校参赛演示作品**，非商业发行物，且不使用 GSAP 构建与其竞争的动画库/插件 ⇒ 落在 GreenSock
  Standard License 的免费使用范围内。
- 公网副本（Cloudflare Pages）与 fat jar 部署包都会原样携带上述三个 vendor 文件，因此本文件必须随仓库存在；
  若日后**更换 GSAP**（如改 Web Animations API 或改用 `@gsap/shim` 之外的授权版本），需同步更新本表与
  `vendor-manifest.json`，并由 `vendor_freshness_check.py` 的哈希判据确认文件真被替换（防"改了声明没改文件"或反之）。

## 机器责任（谁保证这张表不烂）

| 判据 | 命令 | 断言 |
|---|---|---|
| G6 | `python _test/repo_config_check.py` | `src/vendor/*.js` 里**每一个文件**都必须在本表中被点名（漏一个即红） |
| G7 | 同上 | README 必须存在"第三方授权"口径行（防止有人删掉边界说明，把仓库重新说成纯 MIT） |
| V1/V2 | `python _test/vendor_freshness_check.py` | 版本与 sha256 与 `vendor-manifest.json` 对账（内容与声明不符即红） |
| 副本一致 | `python _test/deploy_sync_check.py` | `src/` ↔ `deploy/xinyu/` 三类归零（含 vendor，防公网副本与授权表脱节） |
