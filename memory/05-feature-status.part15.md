## r87 面部表情识别（2026-10-10 落地，已上公网）

- [x] **摄像头表情识别双入口（r87）**：第二幕「摄像头扫描一次」（`#face-probe`）+ 对话坞实时表情感知
      小窗（`#face-hud`，8fps、关闭即真停轨道 + `landmarker.close()`）。引擎 `src/js/face-engine.js`
      （`window.FaceEngine`，输出与 `EmotionEngine.scan` 同构）、判据单一真相源 `src/data/face-smile-rules.js`、
      全站唯一 ESM 桥 `src/js/face-mediapipe-bridge.js`（vendor：`src/vendor/mediapipe/` 四件 13.7MB，
      **惰性加载**——用户点开才下，已登记 `size_budget` 懒加载块预算与 `THIRD-PARTY-NOTICES`）。
      `love` 表情侧不判定（诚实标注）；crisis 恒 false（不判也不解除危机）。
      **r87b**：加摄像头总闸 `#btn-cam`（关=立即真停+隐藏入口+localStorage 记住）与 HUD 看门狗
      （开摄像头但没人脸时标签翻成"没有看到人脸"，不再永远停在"正在识别…"）。
- [x] **强颜欢笑可验证判据（Duchenne，回应老师「大笑怎么验证」的追问）**：
      真笑 = 口部 AU12 高 **且** 眼周参与（AU6 颊肌/AU7 眼轮匝肌）/口部 ≥ `ratioOn`；
      社交性微笑 + 抿唇/眉心紧张线索 → 徽章「社交性微笑·可能是强颜欢笑」。
      ⚠️ `ratioOn=0.20` 是**真照片实测标定的**：首版 0.45 被 4 张 Wikimedia 真笑照证伪
      （实测 ratio 0.269–0.326 全被判成"社交笑"）。区分度：微笑组 mouth 0.509–0.958 vs 中性组 0.000。
- [x] **表情=并列第三路，不抢裁决**：`chat-agent.js` 返回结构增 `face`/`divergence` 字段
      （love 时记 `n/a`），文字与表情不一致时读数面板 + 对话气泡如实标注「可能是强颜欢笑」；
      双路（词典/LLM）裁决规则一字未动 ⇒ 文本链路准确率零回归。
- [x] **常驻判据 `_test/face_check.py`（F1–F6 + selftest 11 反例）**：vendor sha256 完整性 / 接线面
      （ESM 桥挂号 + CSP + camera 策略 + SW 预缓存）/ 判据单测（`_test/js/face-engine.unit.test.mjs` 10 例，
      含"抬阈值必须翻面"的可证伪腿）/ 假摄像头真脸端到端（ffmpeg 现做 y4m 喂 `--use-file-for-fake-video-capture`，
      断言出读数 + 星雾驱动 + 关闭真停）/ 8 张真实照片实跑 / 无摄像头降级（入口消失 + 一句人话原因）。
      公网验收腿 `--public <URL>`：线上真脸出读数 `joy/duchenne`，截图 `_test/_shots/face_public_live.png`。
- [x] **部署侧三处连带（都有实测依据）**：`_headers` 补 `'wasm-unsafe-eval'` + `media-src 'self' blob:`
      + `Permissions-Policy: camera=(self)`；**`'unsafe-eval'` 是被迫的唯一具名放宽**
      （MediaPipe wasm 链要 eval，不放行则公网报 `Evaluating a string as JavaScript violates …` 且永远建不起来
      ——本地无 CSP 所以测不出来），按"放宽须改判据留名"立 `CSP-EVAL-EXCEPTION` 标记 +
      `headers_csp_check` H3/L2 认标记、无标记照红（selftest +2 腿=15/15）；`sw.js` PRECACHE 增 3 个面部模块。
- [x] **已上公网并真跑**：`wrangler pages deploy` 多轮，`face_check --public https://xinyu-soulisle.pages.dev` PASS
      （wasm 200/application/wasm、bundle 200/application/javascript —— 佐证 vendor 从 `.mjs` 改名 `.js` 是对的）。
      已知前提：getUserMedia 需安全上下文 ⇒ 演示用 https/localhost，禁 file:// 双击。
- 备考：`.mjs` 被本机 python http.server 发成 `text/plain` ⇒ 浏览器拒绝执行模块脚本（功能静默消失），
  故 vendor 改名 `vision_bundle.js`；SW PRECACHE 数组注释里**禁出现双引号与数组结束符字面量**
  （`offline_shell_check` 按源码正则复算清单，本轮连踩两次：注释被读成缺件、清单被截断）。
