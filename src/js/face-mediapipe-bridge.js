/* 心屿 · MediaPipe 桥（本项目**唯一**一个 ES Module 脚本）
 *
 * 为什么要有这一层：MediaPipe Tasks Vision 只发 ESM，而本站是零构建纯静态页
 * （经典 <script> + window.X 命名空间，全站 0 处 type=module）。把整站改 ESM
 * 会波及 15 个经典脚本与全部浏览器判据 —— 代价远大于收益。
 * 于是只在**边界处桥接一次**：本文件 import ESM，把能力挂到 `window.__XINYU_FACE_VISION__`，
 * 其余代码形态一字不改。
 *
 * 三条硬规则：
 *   1) 模型与 wasm 全在本地 `vendor/mediapipe/` ⇒ 画面帧**永远不出浏览器**（红线：零上传）；
 *   2) 初始化失败只置 `ok=false` + 写 `err`，**不抛到全局**（页面其余部分照常可用）；
 *   3) 模块脚本是 defer ⇒ 经典脚本必须**异步等** `ready`，禁止同步依赖。
 */
/* ⚠️ vendor 文件刻意叫 `vision_bundle.js` 而不是上游的 `.mjs`：
 * 静态托管对 .mjs 的 MIME 不统一（本机 python http.server 实测发成 `text/plain`，
 * 浏览器按 HTML 规范**拒绝**执行 MIME 非 JS 的模块脚本 ⇒ 整个功能静默消失）。
 * `.js` 在任何静态托管上都按 JavaScript 发；内容仍是 ESM，扩展名不影响 import。 */
import { FaceLandmarker, FilesetResolver } from "../vendor/mediapipe/vision_bundle.js";

const BASE = new URL("../vendor/mediapipe/", import.meta.url).href;
const MODEL = new URL("../vendor/mediapipe/face_landmarker.task", import.meta.url).href;

/** WebAssembly SIMD 探测：(module (func (result v128) v128.const i32x4 0 0 0 0))
 *  非 SIMD 浏览器拿不到 simd 版 wasm（本仓只 vendor 了 SIMD 版）⇒ 明确降级而不是白屏报错。 */
function simdOk() {
  try {
    return WebAssembly.validate(new Uint8Array([
      0, 97, 115, 109, 1, 0, 0, 0,            // magic + version
      1, 5, 1, 96, 0, 1, 123,                 // type section: () -> v128
      3, 2, 1, 0,                             // func section
      10, 10, 1, 8, 0, 65, 0, 253, 15, 253, 98, 11   // code: v128.const i32x4 0
    ]));
  } catch (e) {
    return false;
  }
}

const V = {
  ok: false,
  err: null,
  simd: simdOk(),
  ready: null,          // 由 ensure() 惰性创建；**不在模块执行时就下 13MB**
  createLandmarker: null,
  closeLandmarker: null,
  ensure: null,
  version: "tasks-vision-0.10.22-rc.20250304"
};
window.__XINYU_FACE_VISION__ = V;

async function makeLandmarker(fileset, delegate) {
  return FaceLandmarker.createFromOptions(fileset, {
    baseOptions: { modelAssetPath: MODEL, delegate: delegate },
    runningMode: "VIDEO",
    numFaces: 1,
    outputFaceBlendshapes: true,
    outputFacialTransformationMatrixes: false
  });
}

async function boot() {
  if (!V.simd) { V.err = "no-simd"; return false; }
  const fileset = await FilesetResolver.forVisionTasks(BASE);
  let lm = null;
  // GPU 优先，失败回落 CPU（集显/虚拟机会在这步失败，属预期内的正常降级）
  try { lm = await makeLandmarker(fileset, "GPU"); }
  catch (e) { lm = await makeLandmarker(fileset, "CPU"); }
  V.createLandmarker = async () => lm;
  V.closeLandmarker = () => { try { lm.close(); } catch (e) { /* 已释放 */ } };
  V.ok = true;
  return true;
}

/* 惰性加载（r87 实测修正）：初版在模块执行时就 boot ⇒ **每个访客每次打开都先下 13MB**，
   哪怕他从不点开表情功能；公网冷启动实测还把能力状态卡在 boot 超过 90s。
   正解：只有用户真的要用（start/probeOnce）时才 ensure()，且同一页只下一次。 */
V.ensure = function () {
  if (!V.ready) {
    V.ready = boot().catch((e) => {
      V.err = String((e && e.message) || e || "unknown");
      V.ok = false;
      return false;
    });
  }
  return V.ready;
};
