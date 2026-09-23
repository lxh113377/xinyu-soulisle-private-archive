/* 心屿 · WebGL 情绪星云（Three.js）
 * 粒子系统 + 滚动驱动镜头 + 情绪色相插值（支持主/次情绪双色星雾）。
 * WebGL 不可用时由 app.js 降级 CSS。
 */
window.ThreeScene = (function () {
  let renderer, scene, camera, points, crisisPulse = 0;
  let scrollT = 0; // 0..1 全局进度
  const COUNT = 2600;
  /* 情绪点亮机制（核心叙事）：每颗星独立记录「是否点亮 / 被哪种情绪点亮 / 点亮时刻」。
     未点亮 = 极暗灰白微光轮廓（能看出在转，但没有颜色）——“还没被了解”。 */
  const litState = new Uint8Array(COUNT);
  const litRGB = new Float32Array(COUNT * 3);
  const litAt = new Float64Array(COUNT); // performance.now()；0 = 历史重放，不闪
  const pSize = new Float32Array(COUNT); // 逐粒子尺寸：暗星小，点亮后变大发光
  const radius = new Float32Array(COUNT);
  const order = new Uint32Array(COUNT);  // 按半径升序的索引表（有序点亮用）
  /* 未点亮必须是「中性灰」：带蓝调的灰会落在低落蓝的色相区间里，
     被像素判据误读成「低落已经出现」（实测对照图里凭空多出 1% 的低落色像素）。 */
  const DIM = [0.105, 0.105, 0.115];
  // LIT_SIZE 需跟着分布尺度走：星云改成立体厚盘后（半径更大、更靠外），
  // 0.22 在只点亮几十颗时屏幕有效像素只剩 ~113（肉眼看不清），故补到 0.26。
  const DIM_SIZE = 0.05, LIT_SIZE = 0.26;
  let litCount = 0;
  let colorAttr = null; // aColor 属性引用：init 后缓存，tick 每帧复用，避免重复查表
  let cursor = 0;        // 有序点亮的游标（沿螺旋由内向外推进 → 每色形成一圈色环）
  let blackoutT0 = 0;    // 「清屏」黑屏的截止时刻（performance.now() 毫秒）
  let showTimers = [];

  function init(canvas) {
    if (!window.THREE) return false;
    try {
      renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
    } catch { return false; }
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    renderer.setSize(innerWidth, innerHeight);

    scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x070b18, 0.055);
    camera = new THREE.PerspectiveCamera(60, innerWidth / innerHeight, 0.1, 100);
    camera.position.set(0, 0, 9);

    // 粒子：螺旋星云分布
    const geo = new THREE.BufferGeometry();
    const pos = new Float32Array(COUNT * 3);
    const col = new Float32Array(COUNT * 3);
    const seed = new Float32Array(COUNT);
    /* 分布必须是「立体厚盘」而不是薄螺旋盘：薄盘在视角拉远时中心密成一坨。
       半径按 pow(u,0.55) 外扩（体积感更足），极角全空间采样（有厚度），
       方位角保留一点螺旋偏移维持星云造型，但不至于连成一条线。 */
    for (let i = 0; i < COUNT; i++) {
      const t = i / COUNT;
      const r = 1.6 + 7.6 * Math.pow(Math.random(), 0.55);
      const phi = Math.acos(1 - 2 * Math.random());          // 全空间极角 → 有厚度
      const theta = t * Math.PI * 5 + Math.random() * Math.PI * 2;
      pos[i * 3]     = r * Math.sin(phi) * Math.cos(theta);
      pos[i * 3 + 1] = r * Math.cos(phi) * 0.78;            // 略扁：像星云又不塌成盘
      pos[i * 3 + 2] = r * Math.sin(phi) * Math.sin(theta);
      radius[i] = r;
      col[i * 3] = DIM[0]; col[i * 3 + 1] = DIM[1]; col[i * 3 + 2] = DIM[2];
      pSize[i] = DIM_SIZE;
      seed[i] = Math.random();
    }
    // 有序点亮要「由内向外」，所以游标走的是按半径升序的索引表（不是原始索引）
    for (let i = 0; i < COUNT; i++) order[i] = i;
    order.sort((a, b) => radius[a] - radius[b]); // TypedArray 原生排序：与旧 Array.prototype.sort.call 同序
    geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    geo.setAttribute("aColor", new THREE.BufferAttribute(col, 3));
    geo.setAttribute("aSize", new THREE.BufferAttribute(pSize, 1));
    /* 用 ShaderMaterial 实现「逐粒子尺寸」：暗星小点、点亮的星大且柔光。
       PointsMaterial 的 size 是全局的，做不到「被点亮的那一颗变亮变大」——
       而 4 句话只点亮约 27 颗，若每颗仍是原来的小点，屏幕上几乎看不见。 */
    const mat = new THREE.ShaderMaterial({
      uniforms: { uScale: { value: 600 } },
      vertexShader: `
        attribute vec3 aColor;
        attribute float aSize;
        uniform float uScale;
        varying vec3 vColor;
        void main() {
          vColor = aColor;
          vec4 mv = modelViewMatrix * vec4(position, 1.0);
          gl_PointSize = aSize * uScale / max(0.001, -mv.z);
          gl_Position = projectionMatrix * mv;
        }`,
      fragmentShader: `
        varying vec3 vColor;
        void main() {
          float d = length(gl_PointCoord - vec2(0.5));
          if (d > 0.5) discard;
          float a = smoothstep(0.5, 0.05, d);
          gl_FragColor = vec4(vColor, a);
        }`,
      transparent: true, blending: THREE.AdditiveBlending, depthWrite: false
    });
    const scaleAttr = () => {
      const dpr = Math.min(devicePixelRatio, 2);
      mat.uniforms.uScale.value = (innerHeight * dpr) / (2 * Math.tan((60 * Math.PI / 180) / 2));
    };
    scaleAttr();
    points = new THREE.Points(geo, mat);
    scene.add(points);
    colorAttr = points.geometry.attributes.aColor;

    addEventListener("resize", () => {
      camera.aspect = innerWidth / innerHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(innerWidth, innerHeight);
      scaleAttr(); // 点尺寸随画布高度换算，必须同步
    });
    tick();
    return true;
  }

  function setScrollProgress(t) { scrollT = Math.max(0, Math.min(1, t)); }

  /* ---------- 双色可分辨保障 ----------
   * 「焦虑紫 + 低落蓝」「 irritable红 + 心动粉」这类同色系组合，即使空间分带也会看着像一个颜色。
   * 故次色上岗前先判色相距离，太近就沿色相环把它旋开到肉眼可分的最小角距并提饱和。
   */
  const MIN_HUE_GAP = 0.28; // 色相环占比，≈100°
  function hueDist(h1, h2) { const d = Math.abs(h1 - h2) % 1; return Math.min(d, 1 - d); }
  function rgb2hsl(c) {
    const mx = Math.max(c[0], c[1], c[2]), mn = Math.min(c[0], c[1], c[2]);
    const l = (mx + mn) / 2, d = mx - mn;
    if (!d) return { h: 0, s: 0, l };
    const s = l > 0.5 ? d / (2 - mx - mn) : d / (mx + mn);
    let h;
    if (mx === c[0]) h = ((c[1] - c[2]) / d + (c[1] < c[2] ? 6 : 0)) / 6;
    else if (mx === c[1]) h = ((c[2] - c[0]) / d + 2) / 6;
    else h = ((c[0] - c[1]) / d + 4) / 6;
    return { h, s, l };
  }
  function hsl2rgb(h, s, l) {
    const f = (n) => {
      const k = (n + h * 12) % 12;
      const a = s * Math.min(l, 1 - l);
      return l - a * Math.max(-1, Math.min(k - 3, 9 - k, 1));
    };
    return [f(0), f(8), f(4)];
  }
  function makeDistinct(second, main) {
    const A = rgb2hsl(main), B = rgb2hsl(second);
    const euclid = Math.hypot(second[0] - main[0], second[1] - main[1], second[2] - main[2]);
    if (euclid >= 0.35 && hueDist(A.h, B.h) >= MIN_HUE_GAP / 2) return second.slice();
    return hsl2rgb((A.h + MIN_HUE_GAP) % 1, Math.max(0.62, B.s), Math.max(0.55, B.l));
  }

  /** 点亮 n 颗尚未点亮的星。n 由情绪强度决定（1~8），从暗星里随机取，
   *  保证每条记忆都在星图上留下独立位置。opts.silent = 历史重放，不触发点亮脉冲。 */
  function lightUp(rgb, n, opts) {
    const now = performance.now();
    const silent = !!(opts && opts.silent);
    for (let k = 0; k < n; k++) {
      let i = -1;
      if (opts && opts.ordered) {
        // 走按半径升序的索引表 → 点亮沿「由内向外」推进，六种情绪各成一圈
        for (let c = cursor; c < COUNT && i < 0; c++) { const idx = order[c]; if (!litState[idx]) { i = idx; cursor = c + 1; } }
      } else {
        for (let tries = 0; tries < 32 && i < 0; tries++) {
          const c = (Math.random() * COUNT) | 0;
          if (!litState[c]) i = c;
        }
        if (i < 0) { for (let c = 0; c < COUNT; c++) if (!litState[c]) { i = c; break; } } // 快满时线性补漏
      }
      if (i < 0) return litCount; // 整片星图都亮了
      litState[i] = 1;
      litRGB[i * 3] = rgb[0]; litRGB[i * 3 + 1] = rgb[1]; litRGB[i * 3 + 2] = rgb[2];
      pSize[i] = LIT_SIZE;
      litAt[i] = silent ? 0 : now;
      litCount++;
    }
    if (points) points.geometry.attributes.aSize.needsUpdate = true;
    return litCount;
  }

  /** 记录一次情绪 → 点亮星雾。rgb=主情绪，rgb2=次情绪（可选）。
   *  返回实际采用的次色 RGB（可能已被 makeDistinct 旋开），供 UI 标注；无次情绪返回 null。 */
  function setEmotion(rgb, intensity, rgb2, opts) {
    const applied = rgb2 ? makeDistinct(rgb2, rgb) : null;
    if (!points) return applied;
    const n = 1 + Math.round(Math.min(1, Math.max(0, intensity)) * 7); // 强度 → 1~8 颗
    lightUp(rgb, n, opts);
    if (applied) lightUp(applied, Math.max(1, Math.round(n * 0.5)), opts);
    return applied;
  }

  /** 一键点亮（演示用）：先**清屏**，再播放「从全黑里一颗颗亮起来」的过程。
   *  ① douse 全部熄灭 → ② 黑屏 BLACKOUT_MS → ③ 暗星渐显的同时，沿螺旋由内向外逐颗有序点亮，
   *     六种情绪各 perEmotion 颗（默认 180 → 共 1080 颗≈41%，足够"满"）、每色间隔 GAP_MS、
   *     每颗间隔 STEP_MS、沿半径由内向外推进 → 每色形成一圈同心色环。
   *  仅做可视化，**不写入本机记忆**；返回 { palette（情绪 → 实际渲染色）, duration（整个过程毫秒）}。 */
  // 清屏停顿 1100ms：既让「先黑一下」看得清，也给自动化留够采样窗口
  // （700ms 时截图本身的耗时会让采样落在已点亮之后，测不出清屏）
  const SHOW_BLACKOUT = 1100, SHOW_GAP = 200, SHOW_STEP = 8;
  function lightShow(perEmotion = 180) {
    if (!points) return { palette: [], duration: 0 };
    cancelShow();
    douse();                                   // ① 清屏
    blackoutT0 = performance.now() + SHOW_BLACKOUT; // ② 先黑一下，让「点亮」有起点
    const pal = (window.EmotionEngine && window.EmotionEngine.palette) ? window.EmotionEngine.palette() : [];
    pal.forEach((p, i) => {
      const base = SHOW_BLACKOUT + i * SHOW_GAP;
      for (let j = 0; j < perEmotion; j++) {
        showTimers.push(setTimeout(() => lightUp(p.color, 1, { ordered: true }), base + j * SHOW_STEP));
      }
    });
    return { palette: pal, duration: SHOW_BLACKOUT + pal.length * SHOW_GAP + perEmotion * SHOW_STEP };
  }

  /** 中断演示点亮（用户再次点击 / 清除数据时调用） */
  function cancelShow() {
    showTimers.forEach(clearTimeout);
    showTimers = [];
    blackoutT0 = 0;
  }

  /** 熄灭整片星图（一键清除数据时调用） */
  function douse() {
    litState.fill(0); litAt.fill(0); litCount = 0; crisisPulse = 0;
    pSize.fill(DIM_SIZE); cursor = 0;
    if (points) points.geometry.attributes.aSize.needsUpdate = true;
  }
  function litInfo() { return { lit: litCount, total: COUNT }; }

  function setCrisis() {
    crisisPulse = 1;
    if (points) lightUp([1.0, 0.2, 0.25], 8);
  }

  function tick() {
    requestAnimationFrame(tick);
    if (!renderer) return;
    const time = performance.now() * 0.00016;

    // 滚动 → 镜头：第一幕正面 → 第二幕穿入 → 第三幕环绕 → 第四幕俯瞰 → 第五幕拉远
    const camY = Math.sin(scrollT * Math.PI * 2) * 1.6;
    const camZ = 9 - Math.sin(scrollT * Math.PI) * 4.2;
    camera.position.set(Math.sin(scrollT * Math.PI * 2) * 2.2, camY, camZ);
    camera.lookAt(0, 0, 0);

    points.rotation.y = time * 0.6 + scrollT * Math.PI * 1.5;
    points.rotation.z = Math.sin(time * 0.4) * 0.08;

    // 逐星着色：已点亮 = 被记住的那一瞬的情绪色（新点亮的 1.2s 内有点亮脉冲）
    //           未点亮 = 极暗灰白微光，只留下「还在转」的轮廓
    crisisPulse *= 0.985;
    const now = performance.now();
    // 演示点亮的「清屏 → 渐显」：黑屏期间连暗星也不画，结束后 600ms 内渐显，
    // 与逐颗点亮同时进行 → 观感是「从全黑里一颗一颗亮起来」
    let dimK = 1;
    if (blackoutT0) {
      const left = blackoutT0 - now;
      dimK = left > 0 ? 0 : Math.min(1, (now - blackoutT0) / 600);
      if (dimK >= 1) blackoutT0 = 0;
    }
    const attr = colorAttr || points.geometry.attributes.aColor;
    const arr = attr.array;
    for (let i = 0; i < COUNT; i++) {
      const tw = 0.75 + 0.25 * Math.sin(time * 6 + i);
      const pulse = crisisPulse * 0.6 * Math.abs(Math.sin(time * 20));
      let cr, cg, cb;
      if (litState[i]) {
        cr = litRGB[i * 3]; cg = litRGB[i * 3 + 1]; cb = litRGB[i * 3 + 2];
        const ago = now - litAt[i];
        if (litAt[i] > 0 && ago < 1200) {
          const boost = 1 + 2.2 * (1 - ago / 1200); // 刚点亮时闪一下渐暗到常态
          cr *= boost; cg *= boost; cb *= boost;
        }
      } else {
        cr = DIM[0] * dimK; cg = DIM[1] * dimK; cb = DIM[2] * dimK;
      }
      arr[i * 3]     = Math.min(1, cr * tw + pulse);
      arr[i * 3 + 1] = cg * tw * (1 - crisisPulse * 0.7);
      arr[i * 3 + 2] = cb * tw * (1 - crisisPulse * 0.7);
    }
    attr.needsUpdate = true;

    renderer.render(scene, camera);
  }

  /** 采样粒子配色（等距取样），仅供 _test/ 回归校验双色星雾，运行时不调用 */
  function sampleColors(n = 40) {
    if (!points) return [];
    const arr = points.geometry.attributes.aColor.array;
    const out = [];
    for (let k = 0; k < n; k++) {
      const i = Math.floor(k * (COUNT - 1) / (n - 1));
      out.push([+arr[i * 3].toFixed(3), +arr[i * 3 + 1].toFixed(3), +arr[i * 3 + 2].toFixed(3)]);
    }
    return out;
  }

  return { init, setScrollProgress, setEmotion, setCrisis, lightUp, lightShow, cancelShow, douse, litInfo, sampleColors };
})();
