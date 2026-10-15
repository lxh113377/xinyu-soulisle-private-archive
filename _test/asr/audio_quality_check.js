/* audio-quality.js 的纯函数判据 —— 无 DOM、无麦克风，直接 node 跑。
 * 判据编号 Q1–Q10（与 src/js/audio-quality.js 头部注释交叉引用）。
 *   node _test/asr/audio_quality_check.js
 *
 * 源模块是浏览器 classic script（IIFE 挂 window.AudioQuality），node 下没有 window，
 * 故此处补最小 shim —— 只为让纯函数可测，**不改源模块的浏览器契约**。
 */
const path = require("path");
global.window = global.window || {};
require(path.join(__dirname, "..", "..", "src", "js", "audio-quality.js"));
const AQ = global.window.AudioQuality;
if (!AQ) { console.error("AUDIO-QUALITY-FAIL: 模块未挂载 window.AudioQuality"); process.exit(1); }

let pass = 0, fail = 0;
function chk(id, name, cond, detail) {
  if (cond) { pass++; console.log(`[OK ] ${id} ${name}`); }
  else { fail++; console.log(`[FAIL] ${id} ${name}${detail ? " -> " + detail : ""}`); }
}

const FS = 32768;
function tone(n, amp, hz) {
  const out = new Float32Array(n);
  for (let i = 0; i < n; i++) out[i] = amp * Math.sin(2 * Math.PI * hz * i / FS);
  return out;
}
function noise(n, amp, seed) {
  let s = seed || 1;
  const out = new Float32Array(n);
  for (let i = 0; i < n; i++) { s = (s * 1103515245 + 12345) & 0x7fffffff; out[i] = amp * ((s / 0x7fffffff) * 2 - 1); }
  return out;
}
function mix(a, b) { const o = new Float32Array(a.length); for (let i = 0; i < a.length; i++) o[i] = a[i] + (b[i] || 0); return o; }
function framesFrom(spR, nsR, nSp, nNs) {
  const f = [];
  for (let i = 0; i < nSp; i++) f.push({ r: spR, speech: true });
  for (let i = 0; i < nNs; i++) f.push({ r: nsR, speech: false });
  return f;
}

/* Q1 rms 基本正确 */
{
  const r = AQ.rms([1, -1, 1, -1]);
  chk("Q1", "rms([1,-1,1,-1]) = 1", Math.abs(r - 1) < 1e-6, `got ${r}`);
  chk("Q1", "rms(空) = 0 且不抛错", AQ.rms([]) === 0 && AQ.rms(null) === 0);
}

/* Q2 削波率 */
{
  const clean = tone(1000, 0.2, 300);
  chk("Q2", "正常幅度削波率=0", AQ.clipRate(clean, FS) === 0, `got ${AQ.clipRate(clean, FS)}`);
  const clip = new Float32Array(1000).fill(FS);
  chk("Q2", "全满量程削波率=1", AQ.clipRate(clip, FS) === 1, `got ${AQ.clipRate(clip, FS)}`);
}

/* Q3 SNR 估计方向性 */
{
  const hi = AQ.snrDb(framesFrom(0.2, 0.01, 10, 10));
  const lo = AQ.snrDb(framesFrom(0.2, 0.15, 10, 10));
  chk("Q3", `干净 SNR 高 (${hi && hi.toFixed(1)}dB) > 嘈杂 SNR 低 (${lo && lo.toFixed(1)}dB)`, hi > lo);
}

/* Q4 SNR 样本不足必须返回 null，不许编数 */
{
  chk("Q4", "非语音帧不足 → null", AQ.snrDb(framesFrom(0.2, 0.01, 10, 2)) === null);
  chk("Q4", "空输入 → null", AQ.snrDb([]) === null && AQ.snrDb(null) === null);
}

/* Q5 准入：干净音频放行 */
{
  const clean = mix(tone(16000, 0.2, 300), noise(16000, 0.002, 7));
  const q = AQ.assess({ samples: clean, frames: framesFrom(0.2, 0.01, 10, 10), fs: FS });
  chk("Q5", `干净音频放行 (code=${q.code})`, q.ok === true, JSON.stringify(q));
}

/* Q6 准入：爆音必须拦下（code=clipped），且优先于其它判定 */
{
  const clip = new Float32Array(16000);
  for (let i = 0; i < clip.length; i++) clip[i] = (i % 2 ? FS : -FS) * 0.99; // >98.5% 阈
  const q = AQ.assess({ samples: clip, frames: framesFrom(0.5, 0.1, 10, 10), fs: FS });
  chk("Q6", `爆音拦截 code=${q.code}`, q.ok === false && q.code === "clipped", JSON.stringify(q));
  chk("Q6", "拦下时必须给出可展示的中文提示", typeof q.hint === "string" && q.hint.length > 4);
}

/* Q7 准入：过短必须拦下 */
{
  const tiny = tone(4800, 0.2, 300);  // 4800/32768 ≈ 146ms < 300ms
  const q = AQ.assess({ samples: tiny, fs: FS });
  chk("Q7", `过短拦截 code=${q.code}`, q.ok === false && q.code === "too_short", JSON.stringify(q));
}

/* Q8 准入：强噪声必须拦下 */
{
  const loud = mix(tone(32000, 0.2, 300), noise(32000, 0.18, 3));
  const q = AQ.assess({ samples: loud, frames: framesFrom(0.2, 0.15, 10, 10), fs: FS });
  chk("Q8", `强噪声拦截 code=${q.code}`, q.ok === false && q.code === "too_noisy", JSON.stringify(q));
}

/* Q9 采集链自适应：噪声大关 AGC，判据不可得不瞎猜 */
{
  // 用明确低于阈值的噪声（0.2/0.08 → 20log10(2.5) ≈ 7.96dB，远低于 snrWarnDb=12），
  // 避免骑在阈值上 —— 刀锋测试会把「< 还是 <=」的语义变化藏起来。
  const noisy = AQ.assess({ samples: mix(tone(32000, 0.2, 300), noise(32000, 0.08, 5)),
                            frames: framesFrom(0.2, 0.08, 10, 10), fs: FS });
  chk("Q9", `噪声环境关 AGC (code=${noisy.code}, snr=${noisy.snrDb && noisy.snrDb.toFixed(2)})`,
      noisy.code === "ok_noisy" && AQ.adapt(noisy).autoGainControl === false,
      JSON.stringify(AQ.adapt(noisy)));
  const unknown = AQ.adapt({ ok: true, code: "ok", snrDb: null, level: 0 });
  chk("Q9", "判据不可得 → 不瞎猜（不改 autoGainControl）",
      !("autoGainControl" in unknown), JSON.stringify(unknown));
  const clipped = AQ.adapt(AQ.assess({ samples: new Float32Array(16000).fill(FS), fs: FS }));
  chk("Q9", "削波 → 关 AGC", clipped.autoGainControl === false, JSON.stringify(clipped));
  // 边界语义显式钉住：恰好等于 snrWarnDb 视为「不算噪声」，不关 AGC。
  // 文档口径是「低于 warn 阈值才收紧」，故此处用严格小于；改成 <= 会让此判据变红。
  const edge = AQ.snrDb(framesFrom(0.2, 0.2 / Math.pow(10, 12 / 20), 10, 10));
  chk("Q9", `恰好 snrWarnDb=12 时按「不算噪声」处理 (实测 ${edge && edge.toFixed(3)}dB)`,
      edge !== null && Math.abs(edge - 12) < 1e-6 &&
      AQ.adapt({ ok: true, code: "ok", snrDb: edge, level: 0.2 }).autoGainControl !== false);
}

/* 附加：阈值可覆盖且能还原 */
{
  AQ.configure({ snrRejectDb: 100 });
  const q = AQ.assess({ samples: tone(32000, 0.2, 300), frames: framesFrom(0.2, 0.01, 10, 10), fs: FS });
  chk("Q10", "configure 覆盖阈值生效", q.ok === false, JSON.stringify(q));
  AQ.reset();
  const q2 = AQ.assess({ samples: tone(32000, 0.2, 300), frames: framesFrom(0.2, 0.01, 10, 10), fs: FS });
  chk("Q10", "reset 后还原默认", q2.ok === true, JSON.stringify(q2));
}

console.log(`\nAUDIO-QUALITY: ${pass} passed, ${fail} failed`);
console.log(fail === 0 ? "AUDIO-QUALITY-PASS" : "AUDIO-QUALITY-FAIL");
process.exit(fail === 0 ? 0 : 1);