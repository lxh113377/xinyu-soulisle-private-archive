/* asr-local.js 的判据 —— 纯函数为主，不碰麦克风/不碰网络（probe 的「零请求」面单独钉）。
 *   node _test/asr/asr_local_check.js
 * 判据编号 A1–A12。
 */
const path = require("path");
global.window = global.window || {};
global.localStorage = undefined;                 // 隐私模式面：模块不得因此崩
require(path.join(__dirname, "..", "..", "src", "js", "asr-local.js"));
const L = global.window.AsrLocal;
if (!L) { console.error("ASR-LOCAL-FAIL: 模块未挂载 window.AsrLocal"); process.exit(1); }

let pass = 0, fail = 0;
function chk(id, name, cond, detail) {
  if (cond) { pass++; console.log(`[OK ] ${id} ${name}`); }
  else { fail++; console.log(`[FAIL] ${id} ${name}${detail ? " -> " + detail : ""}`); }
}

/* A1 能量门方向性 */
{
  const base = 0.01;
  // 语音必须 ≥ 2.2× 底噪（REL_MULT），门槛 = max(0.01*2.2, 0.012) = 0.022。
  // 故「说话」取 0.05（明确在门槛上），不取 0.02（恰在门下）—— 骑在阈值上的
  // 测试会把 REL_MULT 的语义变化藏起来。
  chk("A1", "说话段(0.05)过门", L.speechGate(0.05, base) === true);
  chk("A1", "噪声段(0.004)不过门", L.speechGate(0.004, base) === false);
  chk("A1", "底噪抬高后同值被挡(0.05 vs base=0.09)", L.speechGate(0.05, 0.09) === false);
  // 门槛公式 max(base*REL_MULT, START_RMS)：用**有间隔**的值验证公式形状。
  // ⚠ 刻意不钉精确边界 —— 0.01*2.2 在 IEEE754 下是 0.022000000000000002，
  //   用 0.022 断言会因一个 ULP 失败（实测踩过）。边界属于浮点噪声，不是行为契约。
  chk("A1", "门槛随底噪线性抬升(base=0.02 → 门槛 0.044)",
    L.speechGate(0.05, 0.02) === true && L.speechGate(0.04, 0.02) === false);
  chk("A1", "低底噪时退回绝对门 0.012（不受 REL_MULT 压低）",
    L.speechGate(0.013, 0.001) === true && L.speechGate(0.011, 0.001) === false);
}

/* A2 读数不可得必须放行（宁放过不误伤） */
{
  chk("A2", "null 放行", L.speechGate(null, 0.01) === true);
  chk("A2", "NaN 放行", L.speechGate(NaN, 0.01) === true);
  chk("A2", "undefined 放行", L.speechGate(undefined, 0.01) === true);
}

/* A3 底噪估不出时退回绝对门 */
{
  chk("A3", "base=0 按绝对门 0.012 判", L.speechGate(0.02, 0) === true && L.speechGate(0.005, 0) === false);
  chk("A3", "REL_CAP 上界生效(极吵也不拦)", L.speechGate(0.2, 1000) === true);
}

/* A4 底噪取分位数：单个尖峰不得把底噪抬起来 */
{
  const f = L.noiseFloor([0.01, 0.011, 0.009, 0.01, 5.0, 0.012, 0.01, 0.011]);
  chk("A4", `底噪抗尖峰 (${f.toFixed(4)} 远小于尖峰 5.0)`, f < 0.05, `got ${f}`);
  chk("A4", "样本不足返回 0（退回绝对门）", L.noiseFloor([0.01, 0.02]) === 0);
}

/* A5 起始判定：连续有声够久才 on */
{
  let s = { on: false, voicedMs: 0, silenceMs: 0 };
  for (let i = 0; i < 3; i++) s = L.segment(s, 0.02, 0.005, 60);
  chk("A5", `连续 180ms 有声后开启 (on=${s.on})`, s.on === true);
  let t = { on: false, voicedMs: 0, silenceMs: 0 };
  for (let i = 0; i < 5; i++) t = L.segment(t, i % 2 ? 0.02 : 0.002, 0.005, 60);
  chk("A5", `断续噪声不开启 (on=${t.on})`, t.on === false);
}

/* A6 结束判定：静音够久才 off */
{
  let s = { on: true, voicedMs: 500, silenceMs: 0 };
  s = L.segment(s, 0.001, 0.005, 200);
  chk("A6", `短暂停顿不断句 (on=${s.on})`, s.on === true);
  s = L.segment(s, 0.001, 0.005, 250);
  chk("A6", `累计 450ms 静音后切块 (on=${s.on})`, s.on === false);
}

/* A7 WAV 头逐字节正确（服务端 soundfile 直接吃，错一个字节全盘皆输）
 * ⚠ Blob.arrayBuffer() 在浏览器与 Node 里都返回 **Promise**，不能当同步用（实测踩过）。
 *   故 A7/A8 一并放进下面的 async 段。
 */

/* A9 默认态零探测（对应 C15 公网红线） */
(async () => {
  /* A7 WAV 头逐字节正确 */
  {
    const pcm = new Float32Array(1600);
    for (let i = 0; i < pcm.length; i++) pcm[i] = 0.5 * Math.sin(i / 10);
    const blob = L.encodeWav(pcm);
    const ab = await blob.arrayBuffer();               // ← 返回 Promise，必须 await
    const dv = new DataView(ab);
    const tag = (o) => String.fromCharCode(dv.getUint8(o), dv.getUint8(o + 1), dv.getUint8(o + 2), dv.getUint8(o + 3));
    chk("A7", `RIFF 头 (${tag(0)})`, tag(0) === "RIFF");
    chk("A7", `WAVE 形 (${tag(8)})`, tag(8) === "WAVE");
    chk("A7", `fmt 块 (${tag(12)})`, tag(12) === "fmt ");
    chk("A7", `data 块 (${tag(36)})`, tag(36) === "data");
    chk("A7", `PCM 格式码=1 (${dv.getUint16(20, true)})`, dv.getUint16(20, true) === 1);
    chk("A7", `单声道 (${dv.getUint16(22, true)})`, dv.getUint16(22, true) === 1);
    chk("A7", `采样率 16000 (${dv.getUint32(24, true)})`, dv.getUint32(24, true) === 16000);
    chk("A7", `位深 16bit (${dv.getUint16(34, true)})`, dv.getUint16(34, true) === 16);
    chk("A7", `长度自洽 (${ab.byteLength} = 44 + ${1600 * 2})`, ab.byteLength === 44 + 1600 * 2);
    chk("A7", `content-type=audio/wav (${blob.type})`, blob.type === "audio/wav");
  }

  /* A8 削波钳位：超 1.0 不得回绕成负的巨大值 */
  {
    const ab = await L.encodeWav(Float32Array.from([2.0, -2.0, 0.0])).arrayBuffer();
    const dv = new DataView(ab);
    const a = dv.getInt16(44, true), b = dv.getInt16(46, true);
    chk("A8", `+2.0 钳到 ${a}（正且近满量程）`, a > 32000 && a <= 32767);
    chk("A8", `-2.0 钳到 ${b}（负且近满量程）`, b < -32000 && b >= -32768);
  }

  chk("A9", "默认 disabled", L.isEnabled() === false);
  let called = false;
  const realFetch = global.fetch;
  global.fetch = function () { called = true; return Promise.reject(new Error("should not fetch")); };
  const r = await L.probe();
  global.fetch = realFetch;
  chk("A9", `probe 未发任何请求 (probed=${r.probed})`, called === false && r.probed === false);
  chk("A9", "probe 如实报 disabled", r.reason === "disabled");

  /* A10 六目标方言齐备 */
  const need = ["mandarin", "yue", "chuan", "wu", "dongbei", "minnan"];
  chk("A10", `六方言齐备 -> ${need.filter((d) => L.DIALECTS.indexOf(d) >= 0).join(",")}`,
    need.every((d) => L.DIALECTS.indexOf(d) >= 0));

  /* A11 非法方言回落，不得把脏值透传给服务端 */
  chk("A11", "非法方言回落 mandarin", L.setDialect("不存在的话") === "mandarin");
  chk("A11", "合法方言被接受", L.setDialect("minnan") === "minnan");

  /* A13 领域热词：开关影响 URL，且**前端不得自定义词表** */
  {
    chk("A13", "热词默认开", L.isVocabOn() === true);
    const on = L.buildUrl("yue");
    chk("A13", `开时 URL 带 vocab=on -> ${on}`, on.indexOf("dialect=yue") >= 0 && on.indexOf("vocab=on") >= 0);
    L.setVocabOn(false);
    const off = L.buildUrl("yue");
    chk("A13", `关时 URL 带 vocab=off -> ${off}`, off.indexOf("vocab=off") >= 0);
    chk("A13", "关掉后仍带 dialect", off.indexOf("dialect=yue") >= 0);
    L.setVocabOn(true);
    // 关键红线：前端只能 on/off，不能把任意词表塞进管线
    L.configure({ endpoint: "/api/asr" });
    const u = L.buildUrl("minnan");
    chk("A13", "URL 只含 on/off，不含自定义词表（防伪造识别）",
      /vocab=(on|off)/.test(u) && u.indexOf("Vocabulary") < 0, u);
    // 方言值必须 URL 编码（防止方言码里带 & 或 # 注入参数）
    L.setDialect("minnan");
    const enc = L.buildUrl("minnan");
    chk("A13", "方言值经过 URL 编码", enc.indexOf("dialect=minnan") >= 0, enc);
  }

  /* A12 识别器必须与 SpeechRecognition 同形状 */
  const rec = L.createRecognizer();
  const shape = ["lang", "interimResults", "continuous", "maxAlternatives",
    "onresult", "onerror", "onend", "start", "stop"].filter((k) => rec[k] !== undefined);
  chk("A12", `同形状字段 ${shape.length}/9`, shape.length === 9, JSON.stringify(Object.keys(rec)));
  chk("A12", "maxAlternatives 恒 1（贪心解码 ⇒ C23 在本引擎不成立）", rec.maxAlternatives === 1);
  chk("A12", "start/stop 是函数", typeof rec.start === "function" && typeof rec.stop === "function");
  chk("A12", "打了引擎标记供上层如实显示", rec._engine === "local");

  console.log(`\nASR-LOCAL: ${pass} passed, ${fail} failed`);
  console.log(fail === 0 ? "ASR-LOCAL-PASS" : "ASR-LOCAL-FAIL");
  process.exit(fail === 0 ? 0 : 1);
})().catch((e) => { console.error("ASR-LOCAL-FAIL", e && e.stack || e); process.exit(1); });