/* 心屿 · 情绪曲线（Canvas 2D）
 *
 * 对标轮 r25 从 `app.js` 外提（第二刀，行为零改动）。
 * 选它的理由与第一刀相同：**与对话编排零耦合**（只读 `MemoryStore.all()` + `EmotionEngine` 取色/取标签），
 * 且行为面已有断言盯着 —— `browser_check.py` 断言曲线计数文案「本机已记录 N 条情绪」与清除后「还没有记录」，
 * 外提错了会当场红，而不是靠人眼比对画面。
 *
 * 两条原实现约束原样保留：
 *   1) HiDPI 用 CSS 像素逻辑绘制 + `setTransform` 缩放（高分屏不发虚），布局宽变化时同步画布尺寸；
 *   2) resize 走 200ms 防抖，且**无数据直接跳过** —— 拖动窗口期不该为一根空轴反复重算。
 */
window.Chart = (function () {
  const $ = (s) => document.querySelector(s);

  function render() {
    const cv = $("#mood-chart");
    if (!cv) return;                       // 公网/裁剪环境缺画布时静默，绝不抛错带走整页
    const ctx = cv.getContext("2d");
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const vw = cv.clientWidth || 560, vh = 220;
    if (cv.width !== Math.round(vw * dpr) || cv.height !== Math.round(vh * dpr)) {
      cv.width = Math.round(vw * dpr); cv.height = Math.round(vh * dpr);
    }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const data = window.MemoryStore.all();
    ctx.clearRect(0, 0, vw, vh);
    const count = $("#chart-count");
    if (count) {
      count.textContent = data.length ? `本机已记录 ${data.length} 条情绪（仅存于此浏览器）` : "还没有记录 — 聊几句就有了";
    }
    if (!data.length) {
      ctx.fillStyle = "#8a93b2"; ctx.font = "14px sans-serif"; ctx.textAlign = "center";
      ctx.fillText("暂无数据", vw / 2, vh / 2);
      return;
    }
    const W = vw, H = vh, pad = 26;
    const n = data.length;
    const x = (i) => pad + (W - pad * 2) * (n === 1 ? 0.5 : i / (n - 1));
    const y = (v) => H - pad - (H - pad * 2) * v;
    ctx.strokeStyle = "rgba(255,255,255,.07)";
    for (let g = 0; g <= 4; g++) { const gy = y(g / 4); ctx.beginPath(); ctx.moveTo(pad, gy); ctx.lineTo(W - pad, gy); ctx.stroke(); }
    ctx.beginPath();
    data.forEach((d, i) => { const px = x(i), py = y(d.intensity); i ? ctx.lineTo(px, py) : ctx.moveTo(px, py); });
    ctx.strokeStyle = "rgba(124,108,255,.8)"; ctx.lineWidth = 2; ctx.stroke();
    data.forEach((d, i) => {
      const c = window.EmotionEngine.colorOf(d.emotion);
      ctx.fillStyle = `rgb(${c.map(v => Math.round(v * 255)).join(",")})`;
      ctx.beginPath(); ctx.arc(x(i), y(d.intensity), d.emotion === "crisis" ? 6 : 4, 0, Math.PI * 2); ctx.fill();
    });
    // 图例：情绪分布计数（点数由数据决定，故天然覆盖 6 类 + crisis 的全集）
    const counts = {};
    data.forEach(d => { counts[d.emotion] = (counts[d.emotion] || 0) + 1; });
    let lx = pad, ly = 14;
    ctx.font = "11px sans-serif"; ctx.textAlign = "left";
    for (const [emo, cnt] of Object.entries(counts)) {
      const c = window.EmotionEngine.colorOf(emo);
      ctx.fillStyle = `rgb(${c.map(v => Math.round(v * 255)).join(",")})`;
      ctx.beginPath(); ctx.arc(lx + 4, ly, 4, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = "#8a93b2";
      const label = `${window.EmotionEngine.labelOf(emo)} ${cnt}`;
      ctx.fillText(label, lx + 12, ly + 4);
      lx += ctx.measureText(label).width + 34;
    }
  }

  /** 视口/布局变化按新 CSS 宽重绘：200ms 防抖 + 无数据跳过 */
  function init() {
    let timer = 0;
    addEventListener("resize", () => {
      clearTimeout(timer);
      timer = setTimeout(() => { if (window.MemoryStore.all().length) render(); }, 200);
    });
  }

  return { render, init };
})();
