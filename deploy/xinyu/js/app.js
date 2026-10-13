/* 心屿 · 主装配 */
(function () {
  const $ = (s) => document.querySelector(s);

  // 1) WebGL 初始化（失败降级 CSS 渐变背景）
  let gl = false;
  try { gl = window.ThreeScene.init($("#gl")); } catch { gl = false; }
  if (!gl) {
    $("#gl").hidden = true;
    $("#gl-fallback").hidden = false;
  }

  // r104：顶栏滚动态（滚过 8px 加深）+ 进入叙事后自动收起对话坞（老大拍板）；只切 class。
  //   三条护栏：① 焦点在坞内不收（话没打完坞不能跑）；② 向下挪够 AUTO_HIDE_PX 才收，
  //   向上滚**不自动展开**（只收不放，防来回抖动反复弹）；③ 演示态（showtime）不动坞。
  //   注：用到后文声明的 dockOpen/setDock —— 回调在事件循环里跑，不踩 TDZ（本轮刚修过一例）。
  const tb = $("#topbar");
  const AUTO_HIDE_PX = 80;
  let autoHideY = scrollY;
  /* r109 全屏态虚拟滚动：页面滚动被锁后，滚轮/触摸量映射成星雾进度（0..1 端点停），
     退出全屏回真实进度；lastRealT 由 ScrollStory 的 onProgress 持续刷新。 */
  let lastRealT = 0, virtT = 0, touchLastY = 0;
  addEventListener("scroll", () => {
    tb.classList.toggle("solid", scrollY > 8);
    const y = scrollY, moved = y - autoHideY;
    if (Math.abs(moved) > AUTO_HIDE_PX) autoHideY = y;  // 基准只在真正挪动过一段后刷新，防临界抖动反复触发
    if (moved < AUTO_HIDE_PX || !dockOpen()) return;
    if (document.body.classList.contains("showtime")) return;
    if (dockFull()) return;   // r108：全屏对话时页面滚动已被锁，这里再收一次会把人从全屏踢出去
    const a = document.activeElement;
    if (a && a.closest && a.closest("#chat-dock")) return;
    setDock(false);
  }, { passive: true });

  // 2) 滚动叙事
  window.ScrollStory.init(
    (t) => {
      lastRealT = t; window.__XINYU_SCROLL_T__ = t;   // 判据取数口（dock_auto_check D10/D11）
      // ⚠️ 这里**不能引用 dockFull()**：reload 恢复滚动位置≠0 时 ScrollTrigger 会在 boot 早期
      //    同步触发本回调，那时后文的 const 还在 TDZ —— 一抛则整页 boot 停摆（browser_check
      //    实测抓到：Cannot access 'dockFull' before initialization）。只查 body class，任何时刻可读。
      if (gl && !document.body.classList.contains("dock-full")) window.ThreeScene.setScrollProgress(t);
    },
    // r61 遮挡：见 CHANGELOG；r104：顺带点亮幕次导航当前项（同样只切 class）
    (act) => {
      if (act === 4) { window.Chart.render(); if (dockOpen()) setDock(false); }
      document.querySelectorAll("#actnav a").forEach(a => a.classList.toggle("on", +a.dataset.i === act));
    }
  );

  // 3) 引擎徽章
  function refreshBadge() {
    const b = $("#mode-badge");
    // navigator.onLine 只用来把"配置说在线"降级为"网络不可用"，绝不反向用它宣称在线
    //（个别环境恒 true 不代表真能出网；方向性保守，避免把幸运观察当普适规律）
    const cfgOnline = window.ChatAgent.isOnline();
    const netDown = cfgOnline && navigator.onLine === false;
    /* r51 实测：上游故障时气泡写「暂不可用」而徽章仍写「在线 AI」，同屏打脸 ⇒ 撞红线"禁伪装在线" */
    const llmBad = cfgOnline && !netDown && window.ChatAgent.llmBad();
    if (netDown) { b.textContent = "● 网络不可用（配置为在线）"; b.classList.add("offline"); }
    else if (llmBad) { b.textContent = "● 大模型暂不可用（已降级本机模板）"; b.classList.add("offline"); }
    else if (cfgOnline) { b.textContent = "● 在线 AI"; b.classList.remove("offline"); }
    else { b.textContent = "● 离线共情模板"; b.classList.add("offline"); }
    $("#chat-engine").textContent = "引擎：" + (netDown ? "在线大模型（当前网络不可用）"
      : cfgOnline ? "在线大模型（OpenAI 兼容）" : "离线共情模板引擎");
  }
  refreshBadge();
  addEventListener("online", refreshBadge);
  addEventListener("offline", refreshBadge);

  // 3.5) 评委体验模式提示条
  if (window.__PEILIAO_DEMO__) {
    $("#demo-strip").hidden = false;
    $("#btn-demo-clear").addEventListener("click", () => {
      localStorage.removeItem("peiliao.cfg.v1");
      window.__PEILIAO_DEMO__ = false;
      $("#demo-strip").hidden = true;
      refreshBadge();
    });
  }

  function rgbHex(c) {
    return "#" + c.map(v => Math.round(v * 255).toString(16).padStart(2, "0")).join("");
  }
  // 动态色/宽度走 data-* + CSSOM：markup 内联 style 会被线上 CSP（style-src 'self'）拦成失效
  function paint(root) {
    root.querySelectorAll("[data-fg]").forEach(n => { n.style.color = n.dataset.fg; });
    root.querySelectorAll("[data-bg]").forEach(n => { n.style.background = n.dataset.bg; });
    root.querySelectorAll("[data-w]").forEach(n => { n.style.width = n.dataset.w + "%"; });
  }
  /** 星雾配色说明文案：有次情绪时标注「双色星雾」。secondRGB 必须是渲染实际采用的颜色
   *  （ThreeScene 为保证两色可分辨，可能已把次色沿色相环旋开），否则色点与星雾对不上。 */
  function mistText(main, second, secondRGB) {
    const L = window.EmotionEngine.labelOf;
    const rgbSec = secondRGB || (second ? window.EmotionEngine.colorOf(second) : null);
    return second
      ? `星雾配色：<b data-fg="${rgbHex(window.EmotionEngine.colorOf(main))}">${L(main)}</b> 主 ＋ <b data-fg="${rgbHex(rgbSec)}">${L(second)}</b> 辅（双色星雾）`
      : `星雾配色：<b data-fg="${rgbHex(window.EmotionEngine.colorOf(main))}">${L(main)}</b> 单色`;
  }

  // 4) 星图点亮：刷新履历 —— 从本机情绪记忆逐条重放（持久化），之后新对话继续点亮
  function syncStars() {
    const info = gl ? window.ThreeScene.litInfo() : { lit: 0 };
    const mem = window.MemoryStore.all().length;
    $("#lit-count").textContent = info.lit;
    $("#lit-count-dock").textContent = info.lit;
    $("#mem-count").textContent = mem;
    $("#mem-count-dock").textContent = mem;
  }
  function replayStars() {
    if (gl) {
      window.ThreeScene.douse();
      for (const d of window.MemoryStore.all()) {
        if (d.emotion === "crisis") { window.ThreeScene.setCrisis(); continue; }
        window.ThreeScene.setEmotion(window.EmotionEngine.colorOf(d.emotion), d.intensity || 0.5,
          d.secondary && window.EmotionEngine.colorOf(d.secondary), { silent: true });
      }
    }
    syncStars();
  }

  /* ── 面部表情读数（r87）───────────────────────────────────────────────
     表情走的是与文本**同构**的结构（face-engine.js 保证），所以这里复用同一套
     chip / 强度条 / 配色渲染，不新增第二种视觉语言。 */
  function smileBadgeHtml(s) {
    if (!s) return "";
    // r113 质量门：嘴部区域看不清时微笑三态停用，如实说明而不是报一个「未检出微笑」
    if (s.occluded) return `<span class="face-smile-badge is-none">嘴部看不清（可能被遮挡），微笑判读暂停</span>`;
    const map = { duchenne: ["真笑（眼周有参与）", "is-duchenne"], social: ["社交性微笑", "is-social"], none: ["未检出微笑", "is-none"] };
    const one = map[s.kind] || map.none;
    const extra = s.masking ? " · 伴紧张线索，可能是强颜欢笑" : "";
    return `<span class="face-smile-badge ${one[1]}">${one[0]}${extra}</span>`;
  }
  /* ── 细分子维度展示（r173）────────────────────────────────────────────────
   * 身份类（愉悦/低落/…）是互斥的一维答案；下面这些属性与它**并存**，以前只活在引擎里
   * 没露过面 ⇒ 界面看不到 = 用户感知不到，等于没做。故在此渲染，上限 3 个标签
   * （再多就开始像噪声，而不是信息）。
   * ⚠️ 只渲染 subs 里为 true 的项，一个都不为 true 就整体不显示 —— 不摆空壳占位。 */
  const FACE_SUB_LABELS = {
    neutral: "中性", duchenne: "真笑", social: "社交性微笑", masked: "强颜欢笑",
    worry: "担忧", tense: "紧绷", micro: "微表情线索", asymmetric: "单侧不对称"
  };
  function faceSubsText(v) {
    const s = v && v.subs;
    if (!s) return "";
    const tags = [];
    for (const k in FACE_SUB_LABELS) if (s[k]) tags.push(FACE_SUB_LABELS[k]);
    if (!tags.length) return "";
    const shown = tags.slice(0, 3);
    return "细分：" + shown.join(" · ")
      + (tags.length > shown.length ? " +" + (tags.length - shown.length) : "");
  }
  function faceChipHtml(v) {
    const hex = rgbHex(v.color);
    const pct = Math.round((v.intensity || 0) * 100);
    // 低置信度（主次分贴太近）如实显示「读数不稳」；r161 弱信号帧显示「读数仅供参考」，都不假装确定
    const wobble = v.weak
      ? `<span class="face-wobble" title="信号够真但不够强，这一帧的读数仅供参考">读数仅供参考</span>`
      : (v.confident === false
        ? `<span class="face-wobble" title="主情绪与次情绪分数接近，这一帧的读数仅供参考">读数不稳</span>` : "");
    const subs = faceSubsText(v);
    return `<span class="emotion-chip"><i class="dot" data-bg="${hex}"></i>表情：${v.weak ? "轻微" : ""}${window.FaceEngine.labelOf(v.emotion)}${wobble}`
      + `<span class="intensity-bar"><i data-w="${pct}" data-bg="${hex}"></i></span></span>`
      + (subs ? `<span class="face-subs" title="细分子维度：与主情绪并存的表情属性，不是另一个结论">${subs}</span>` : "")
      + smileBadgeHtml(v.smile);
  }
  function divergenceHtml(view) {
    const E = window.EmotionEngine, f = view.face;
    if (!f || !view.divergence) return "";
    // 表情侧可能报文本没有的类（惊讶/厌恶/轻蔑），用 family 归并后再比，
    // 否则「表情说轻蔑、文字说烦躁」会被渲染成"不一致"，而其实是同一族（r102）
    const fLabel = (f.weak ? "轻微" : "") + window.FaceEngine.labelOf(f.emotion);
    if (view.divergence === "disagree") {
      // 老师追问的那条：嘴在笑、话里是苦的 ⇒ 如实写"不一致"，不替用户下结论
      const hint = f.smile && f.smile.masking ? " · 伴紧张线索，可能是强颜欢笑" : "";
      return `<div class="face-divergence disagree">⚠ 表情与文字不一致：文字「${E.labelOf(view.emotion)}」· 表情「${fLabel}」${hint}</div>`;
    }
    if (view.divergence === "agree") return `<div class="face-divergence agree">✓ 表情与文字一致：${fLabel}</div>`;
    return "";
  }

  /** 第二幕「它记住了你」读数面板：情绪 chips + 双路路径 + 星雾配色（+ 表情第三路） */
  function renderReadout(view) {
    const E = window.EmotionEngine;
    const crisis = view.emotion === "crisis";
    const chips = view.all.slice(0, 3).map(x => {
      const c = E.colorOf(x.emotion);
      const hex = rgbHex(c);
      const pct = Math.round(Math.min(1, x.score) * 100);
      return `<span class="emotion-chip"><i class="dot" data-bg="${hex}"></i>${E.labelOf(x.emotion)}<span class="intensity-bar"><i data-w="${pct}" data-bg="${hex}"></i></span></span>`;
    }).join("") || `<span class="emotion-chip">未检测到明显情绪词，按平静处理</span>`;
    const box = $("#probe-result");
    box.innerHTML =
      (crisis ? `<div class="emotion-chip crisis-chip"><i class="dot"></i>检测到危机信号 — 已启用安全转介策略</div>` : "") +
      chips +
      (view.face ? `<div class="face-row">${faceChipHtml(view.face)}</div>` : "") +
      divergenceHtml(view) +
      `<p class="muted readout-line">${view.path || "词典快判"}：${E.labelOf(view.emotion)}（强度 ${Math.round((view.intensity || 0) * 100)}%）</p>` +
      `<p class="muted" id="probe-mist">${mistText(view.emotion, view.secondary, view.appliedSecondary)}</p>`;
    paint(box);
  }

  // 4.5) 一键点亮：六种情绪各点一簇（仅演示，不写入记忆）；再点一次回到「我的记忆」
  let showMode = false;
  let showTimer = null; // 声明前置：点击回调里读写它，禁止先用后声明
  // 标签分两段（图标 + 文字）：窄屏只裁文字留图标，能力不消失（见 style.css 的 .ls-word）
  const setShowLabel = (ico, word) => {
    const b = $("#btn-lightshow");
    b.querySelector(".ls-ico").textContent = ico;
    b.querySelector(".ls-word").textContent = word;
  };
  $("#btn-lightshow").addEventListener("click", () => {
    if (!gl) return;
    openingStop();                             // 开场在跑时先收尾，禁两套定时器交错点亮
    showMode = !showMode;
    if (showMode) {
      const { palette, duration } = window.ThreeScene.lightShow(180);
      setShowLabel("↺", "回到我的记忆");
      $("#probe-result").innerHTML = `<p class="muted">正在清屏，重新点亮六种情绪…（按 Esc 或点一下画面退出）</p>`;
      if (dockFull()) setFull(false);   // r108：演示态要的是「只剩星雾」，全屏坞先退回常规
      document.body.classList.add("showtime");   // 隐藏全部 UI，只留背景星雾
      // 播放结束**不跳回**：继续停在清屏画面欣赏，唯一退出口是右下角按钮
      showTimer = setTimeout(() => {
        $("#probe-result").innerHTML =
          `<p class="muted readout-lead">六种情绪已由内向外点亮成六圈（仅演示，不会写进你的记忆；想清空再点「↺ 回到我的记忆」）：</p>` +
          palette.map(p => `<span class="emotion-chip"><i class="dot" data-bg="${rgbHex(p.color)}"></i>${p.label}</span>`).join("");
        paint($("#probe-result"));
        syncStars();
        showTimer = null;
      }, duration + 500);
    } else {
      exitShow();
    }
  });

  // 演示态退出（清空演示点亮，回到真实记忆）—— 由坞里的「↺ 回到我的记忆」触发
  function exitShow() {
    if (showTimer) { clearTimeout(showTimer); showTimer = null; }
    document.body.classList.remove("showtime");
    if (gl) window.ThreeScene.cancelShow();
    showMode = false;
    replayStars();                              // 回到真实记忆（会清空演示点亮）
    setShowLabel("✨", "一键点亮");
    $("#probe-result").textContent = "已回到你的真实记忆 —— 继续和它说话，星雾会按你的情绪继续亮。";
  }

  // 右下角按钮：只恢复 UI，**保留**刚点亮的星雾；滚动欣赏不会被打断
  $("#btn-exit-show").addEventListener("click", () => {
    document.body.classList.remove("showtime");
  });

  // 4.6) r80 默认打开：每次加载自动播一次一键点亮，播完回到「我的记忆」。
  //      与手动演示态两处差异：不遮 UI（叙事与坞全程可点）、播完自动归位。
  //      `__XINYU__.opening` 四态（playing→lit→done）= `_test/` 按像素取样的同步点，固定 sleep 会采到演示星。
  let openingT = [];
  const openingStop = () => { openingT.forEach(clearTimeout); openingT = []; window.__XINYU__.opening = "done"; };
  function startOpeningShow() {
    window.__XINYU__ = { opening: "done" };
    // 离线降级（CSS 渐变）不排定时器；`prefers-reduced-motion: reduce` 同样不自动播 ——
    // 自动播放的动画必须由该偏好关掉（判据 `_test/a11y_check.py` A5b：reduce 态动效须显著降档，
    // r80 实测未加这道门时动效比 0.796 ≈ 没降，判红；手动点 ✨ 是用户主动发起，不受此门限制）。
    if (!gl || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    window.__XINYU__.opening = "playing";
    let d = 0;
    try { d = window.ThreeScene.lightShow(180).duration; } catch (e) { d = 0; }
    if (!(d > 0)) return;
    openingT = [
      setTimeout(() => { window.__XINYU__.opening = "lit"; }, d),
      setTimeout(() => { openingT = []; replayStars(); window.__XINYU__.opening = "done"; }, d + 1500)];
  }

  // 底部对话坞三态（r108 老大拍板）：常规 ⛶ → 全屏 ▾ → 收起 ▴ → 常规。
  //   标题栏右上角只有这一个按钮，写的是「下一个动作」不是当前状态；点标题条展开（r104）与
  //   滚动自动收起两条老路径都保留，全屏态不参与自动收起。
  const dockEl = $("#chat-dock");
  const dockOpen = () => dockEl.classList.contains("open");
  const dockFull = () => dockEl.classList.contains("full");
  const DOCK_NEXT = {   // 键 = 当前状态，值 = 按钮此刻该显示的「下一动作」
    normal:    { word: "全屏", ico: "⛶", expanded: "true",  tip: "进入全屏（对话铺满画面）" },
    full:      { word: "收起", ico: "▾", expanded: "true",  tip: "收起对话坞（只留一条细条）" },
    collapsed: { word: "展开", ico: "▴", expanded: "false", tip: "展开对话坞" },
  };
  const dockState = () => dockFull() ? "full" : (dockOpen() ? "normal" : "collapsed");
  function paintDock() {
    const s = DOCK_NEXT[dockState()], b = $("#btn-dock");
    b.querySelector(".db-word").textContent = s.word;
    b.querySelector(".db-ico").textContent = s.ico;
    b.setAttribute("aria-expanded", s.expanded);
    b.title = s.tip + "（三态循环）";
  }
  function setDock(open) {          // 既有入口：滚动自动收起 / 点叙事区 / 点标题条 / 全屏态点按钮
    const wasFull = dockFull();
    dockEl.classList.toggle("open", open);
    if (!open) {
      dockEl.classList.remove("full");
      if (wasFull) {   // r109：从全屏退出的**任何**路径都把镜头还给真实滚动进度（D11 判据）
        if (gl) window.ThreeScene.setScrollProgress(lastRealT);
        window.__XINYU_SCROLL_T__ = lastRealT;
      }
    }
    document.body.classList.toggle("dock-full", dockFull());
    paintDock();
  }
  function setFull(on) {
    dockEl.classList.toggle("full", on);
    if (on) dockEl.classList.add("open");
    document.body.classList.toggle("dock-full", on);
    // r109：进入全屏从真实进度出发继续推；退出时把镜头还给真实滚动进度
    if (on) virtT = lastRealT;
    else if (gl) window.ThreeScene.setScrollProgress(lastRealT);
    window.__XINYU_SCROLL_T__ = on ? virtT : lastRealT;
    paintDock();
  }
  $("#btn-dock").addEventListener("click", () => {
    const s = dockState();
    if (s === "normal") setFull(true);
    else if (s === "full") setDock(false);
    else setDock(true);             // 收起 → 回常规展开（不跳全屏，免得"想说话却铺满屏"）
  });
  // Esc 退出全屏（Esc 本职是关对话框，有 dialog 开着时不抢）
  addEventListener("keydown", (e) => {
    if (e.key === "Escape" && dockFull() && !document.querySelector("dialog[open]")) setFull(false);
  });
  // r109：全屏态滚轮/触摸 → 星雾进度（0..1 端点停）。
  // r172b 修复（老大报障，本地/线上双复现）：旧规则「日志先滚、到头才交镜头」把滚轮驱动的
  // 星雾打没了——全屏态 chat-log 占满坞内大半高且默认停底，向上滚想飞回去时滚轮整段被日志
  // 吃掉、星雾毫无响应（实测 t 恒 1、logScrollTop 狂转）。新规则：滚轮优先给星雾，没到端点
  // 这一下永远归镜头；只有星雾在端点（0/1）且日志该方向还滚得动，才让给日志 ⇒ 滚轮驱动
  // 无中断、无丢失，读历史的活路也不丢。
  function fullScrollDrive(d) {
    virtT = Math.min(1, Math.max(0, virtT + d));
    window.__XINYU_SCROLL_T__ = virtT;
    if (gl) window.ThreeScene.setScrollProgress(virtT);
  }
  function logWantsIt(e) {
    const log = $("#chat-log");
    if (!log || !log.contains(e.target) || log.scrollHeight <= log.clientHeight + 2) return false;
    const atTop = log.scrollTop <= 1, atBottom = log.scrollTop + log.clientHeight >= log.scrollHeight - 1;
    return !((e.deltaY < 0 && atTop) || (e.deltaY > 0 && atBottom));
  }
  addEventListener("wheel", (e) => {
    if (!dockFull() || e.deltaY === 0) return;
    const dir = e.deltaY > 0 ? 1 : -1;
    const fogAtEnd = (dir > 0 && virtT >= 1) || (dir < 0 && virtT <= 0);
    if (!fogAtEnd) {           // 星雾还走得到这一侧 ⇒ 滚轮归镜头，日志不许抢
      e.preventDefault();
      fullScrollDrive(e.deltaY * 0.0011);
    } else if (!logWantsIt(e)) {
      e.preventDefault();      // 星雾到端点、日志也接不住 ⇒ 拦掉这回默认滚动，防空转
    }
    // 其余（星雾到端点 + 日志该方向还能滚）：不拦，让 chat-log 原生滚——读历史的出口
  }, { passive: false });
  addEventListener("touchstart", (e) => { touchLastY = e.touches[0] ? e.touches[0].clientY : 0; }, { passive: true });
  addEventListener("touchmove", (e) => {
    if (!dockFull() || !e.touches.length) return;
    const y = e.touches[0].clientY, d = touchLastY - y;
    touchLastY = y;
    const log = $("#chat-log");
    if (log && log.contains(e.target) && log.scrollHeight > log.clientHeight + 2) return;
    fullScrollDrive(d * 0.0022);
  }, { passive: true });
  $("#story").addEventListener("click", (e) => { if (!e.target.closest("#chat-dock")) setDock(false); });
  // r104：点标题条展开（老大拍板）—— 补鼠标/触屏路径，键盘仍走带 aria-expanded 的 #btn-dock。
  //   刻意不给 #dock-bar 加 role=button：它内部套着真按钮，再套一层会撞嵌套交互规则。
  $("#dock-bar").addEventListener("click", (e) => {
    if (dockOpen() || e.target.closest("#btn-dock,#btn-face-panel")) return;
    setDock(true);
  });
  paintDock();   // 首帧把按钮刷成与初始态一致（HTML 里写的是默认态，防两处漂移）

  // 5) 对话（刷新后恢复历史，多轮上下文不丢）
  //    窗口化（DOM 上界 60 / 折叠配额 / 展开较早）r26 外提到 `src/js/chat-window.js`；
  //    判据 = `ux_guards_check.py` U2a–U2f（浏览器实跑行为，不是源码 grep，搬错即红）。
  const CW = window.ChatWindow;
  CW.init("#chat-log", { history: () => window.ChatAgent.getHistory() });

  /* r116：「一句话走完整共情链路」抽成 sendTurn，文字模式（提交表单）与通话模式共用一条路。
     extraDelta 是给通话层做「边生成边念第一句」的按句出队用的；文字模式传 null ⇒ 行为与抽取前一致。
     为什么抽而不是复制：通话若另起一条链路，情绪双路/记忆注入/危机短路/星雾点亮就要维护两份，
     那正是本仓「两份真相」红线刚消掉过的形态（见 03 决策 #1 的 J6 更正注）。 */
  async function sendTurn(text, extraDelta) {
    CW.push("user", text);
    const thinking = CW.push("ai", "心屿正在感受你的话…", "");
    thinking.classList.add("thinking");
    /* 流式：首个增量到达时才把 thinking 换成正式气泡并逐字覆写；
     * 上游/代理不支持流式时 onDelta 永不触发，收尾按整包一次性渲染（与旧行为一致）。 */
    let bubble = null;
    const onDelta = (full) => {
      if (extraDelta) { try { extraDelta(full); } catch { /* 通话层是观测+出声侧，不得把主链路带崩（voice.js 约束2 同族） */ } }
      if (bubble) { CW.update(bubble, full); return; }
      window.__seenStreamingBubble = true;   // 供 _test/stream_contract.py 断言「确实出现过逐字气泡」
      thinking.remove();
      bubble = CW.push("ai", full, "逐字生成中…");
      bubble.classList.add("streaming");
    };
    try {
      const r = await window.ChatAgent.respond(text, onDelta);
      if (bubble) bubble.remove(); else thinking.remove();
      /* r132 引用核对面：模型句末标的〔依据:编号·级〕必须与本轮真实注入的条目集合比对，
       * 未命中的一律标「未查证」——知识库 E 级已在构建期排除，但模型仍可能凭空编号。
       * 只改标记不删原文；verifyCitations 未挂载（旧缓存）时静默回落原样，不拖垮主链路。 */
      const cite = (typeof window.ChatAgent.verifyCitations === "function")
        ? window.ChatAgent.verifyCitations(r.reply, r.kbUsed)
        : { text: r.reply, checked: 0, matched: 0, unmatched: 0 };
      const citeLabel = cite.checked
        ? (cite.unmatched ? " · 依据 " + cite.matched + "/" + cite.checked + "，未查证 " + cite.unmatched : " · 依据 " + cite.matched + "/" + cite.checked + " 已核对")
        : "";
      const modeLabel = { model: "在线大模型生成", fallback: "大模型暂不可用 · 离线共情模板", offline: "离线共情模板", guard: "安全转介策略" }[r.mode];
      refreshBadge();   // r51：降级发生过就必须让徽章同帧翻面（判据 fault_injection_check F3）
      // 情绪识别来源必须如实标注：后端 /api/emotion 与本地词典是两套实现，界面不得含糊
      const emoSrcLabel = r.emoSrc === "backend" ? " · 情绪:后端" : "";
      // r52：AI 引用了长期记忆就要说出来——隐私承诺是"只留本机"，那"被带进模型"这件事也得可见
      const memLabel = r.memory ? " · 已带入 " + r.memory + " 条记忆" : "";
      // r53：滑出窗口的历史被概要替代了就要说出来（否则用户以为模型"记得全部"）
      const dropLabel = r.dropped ? " · 早前 " + r.dropped + " 条已概要" : "";
      // r87：表情是**并列第三路**——只标注，不覆盖文本/LLM 的裁决（保住文本链路准确率不回退）
      const faceLabel = r.divergence === "disagree" ? " · 表情与文字不一致（可能是强颜欢笑）"
        : r.divergence === "agree" ? " · 表情与文字一致" : "";
      /* r172 C1：基调来自表情时必须说出来 —— 这轮你没说情绪，回复底色取自摄像头读数。
       * 不标注就等于让用户以为 AI 听懂了他说的话。 */
      const faceToneLabel = r.faceTone ? " · 本轮基调参考了表情（" +
        window.EmotionEngine.labelOf(r.faceTone) + "），非你说出的话" : "";
      const aiMsg = CW.push("ai", cite.text,
        `${modeLabel}${r.streamed ? " · 逐字流式" : ""}${r.path ? " · 情绪双路：" + r.path : ""}${emoSrcLabel}${memLabel}${dropLabel}${citeLabel}${faceToneLabel}${r.latency ? " · " + r.latency + "ms" : ""} · 情绪：${window.EmotionEngine.labelOf(r.emotion)}${faceLabel}`);
      aiMsg.dataset.emotion = r.emotion;
      /* r172：把本气泡里的〔依据:编号·级〕变成可点，点开显示卡片正文与来源 URL。
       * 未挂载时静默跳过（旧缓存不得把主链路带崩，与既有 verifyCitations 兜底同纪律）。 */
      try {
        if (window.KbSourcePanel && aiMsg) window.KbSourcePanel.enhance(aiMsg);
      } catch (e) { /* 面板是增强层，失败不得影响本轮回复与渲染 */ }
      // 朗读开关打开时同步播出；通话中改由通话层按句出声，这里不重复念（失败静默，绝不影响主链路）
      if (!(window.VoiceCall && window.VoiceCall.isCalling())) window.Voice.speak(cite.text);
      // 记住这条情绪 → 点亮一簇星（一个瞬间 = 1~8 颗，强度越高越多）
      // 复用 respond 里已算好的词典结果，避免同文本二次 scan；旧版本无 lexAll 时回落重扫
      const lexAll = r.lexAll || window.EmotionEngine.scan(text).all;
      const sec = window.EmotionEngine.secondaryOf(lexAll, r.emotion);
      let applied = null;
      if (gl) {
        if (r.emotion === "crisis") window.ThreeScene.setCrisis();
        else applied = window.ThreeScene.setEmotion(window.EmotionEngine.colorOf(r.emotion), r.intensity || 0.5,
          sec && window.EmotionEngine.colorOf(sec));
      }
      syncStars();
      renderReadout({ all: lexAll, emotion: r.emotion, intensity: r.intensity, secondary: sec,
        appliedSecondary: applied, path: r.path ? "双路情绪 · " + r.path : "词典快判",
        face: r.face || null, divergence: r.divergence || "" });
      window.Chart.render();
      return r;
    } catch (err) {
      thinking.remove();
      CW.push("ai", "刚才我走神了一下（网络不稳定）。你可以再发一次，或点右上角「模型设置」检查连接。", "友好错误态");
      if (window.VoiceCall && window.VoiceCall.isCalling()) throw err;
      // 通话态把错误抛回通话层：它的字幕兜底（sys 行）在浮层里看得见，左侧气泡通话用户看不到
      // （r123 实证：sendTurn 吞掉 return null 时，通话浮层零提示 = 用户侧"没回声"）。
      return null;
    }
  }

  $("#chat-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const input = $("#chat-input");
    const text = input.value.trim();
    if (!text) return;
    input.value = "";
    sendTurn(text, null);
  });

  /* r116：语音通话层接线。只把 sendTurn 注进去（通话层不认识 ChatAgent / EmotionEngine），
     出声与耗时读数由通话层自己经 window.Voice 的能力层做。判据 _test/voice_call_check.py。 */
  window.VoiceCall.init({ send: sendTurn });

  /* 6.1) 面部表情识别（r87）：不可用即隐藏入口（禁伪装）；画面只在内存里过一遍，零上传零落盘。 */
  /* ── r116（老大纠正参照物：要的是**微信视频通话**，不是 r115 那个侧边栏）──────
   悬浮小窗：拖标题条移位、拖右下角改大小、点「全屏」升到整屏，整屏时角落那枚缩略图点回小窗。
   只管「窗口」这一件事 —— 开合的权威仍是 #face-hud.hidden（_test/face_check.py F10 按它断言），
   由 initFace 的 setFacePanel 统一驱动，这里不另存一份开合状态。
   ⚠️ 位置/尺寸只能走 CSSOM 逐属性（root.style.setProperty）：markup 内联 style 会被线上 CSP
   （style-src 'self'）拦成失效，且 _test/inline_style_check.py 对新增写法当场判红。 */
function initFacePip(deps) {
  const { win, bar, grip, mainVideo, miniVideo, modeBtn, closeBtn, miniBtn, root, onClose } = deps;
  const KEY = "peiliao.facepip.v1";
  const MIN_W = 200, MAX_W = 640;   // 200 而非 260：320 宽的手机上限是 vw-16=304，下限留不出余量就「拖不动」
  // 坏值（非数字/Infinity）回落默认，**越界则钳制** —— 两件事不能混成一个 clamp：
  // 把 0 当哨兵会被钳成 MIN_W（实测小窗被压成 260 宽、画面只剩 212×159），所以未量过一律用 null
  const sane = (v, d) => ((typeof v === "number" && isFinite(v)) ? v : d);
  let w = null, x = null, y = null, full = false;
  try {
    const s = JSON.parse(localStorage.getItem(KEY) || "null");
    if (s && typeof s === "object") { w = s.w; x = s.x; y = s.y; full = !!s.full; }
  } catch (e) { /* 隐私模式禁读：落回默认位，功能不受影响 */ }
  function place() {
    const vw = innerWidth, vh = innerHeight;
    // 手机默认只占屏宽 78%：满屏宽的小窗既拖不动也没意义（那是整屏态的活），留出可移的余量
    const defW = Math.min(vw >= 769 ? 360 : Math.max(MIN_W, Math.round(vw * 0.78)), vw - 16);
    w = Math.min(Math.max(sane(w, defW), MIN_W), Math.max(MIN_W, Math.min(MAX_W, vw - 16)));
    x = Math.min(Math.max(sane(x, vw - w - 18), 8), Math.max(8, vw - w - 8));
    // 按**实际渲染高度**钳底：只钳「顶边不出屏」会把窗体推到视口外，
    // 结果右下角手柄与隐私声明一起掉到屏外，用户既缩不了也关不掉（实测拖一次就复现）
    y = Math.min(Math.max(sane(y, 76), 8), Math.max(8, vh - win.offsetHeight - 8));
    root.style.setProperty("--pip-w", w + "px");
    root.style.setProperty("--pip-x", x + "px");
    root.style.setProperty("--pip-y", y + "px");
    try { localStorage.setItem(KEY, JSON.stringify({ w: w, x: x, y: y, full: full })); } catch (e) {}
  }
  place();
  /* 缩略图复用**同一条** MediaStream（一个流可挂多个 video 元素）；收回小窗时摘掉，
     别让已经停掉的流继续占着缩略图。 */
  function syncMini() {
    miniVideo.srcObject = full ? mainVideo.srcObject : null;
    // 挂上流 ≠ 开播：face-engine 只对主 video 调过 play()，缩略图不自己点就是一片黑（实测）
    if (full && miniVideo.srcObject) miniVideo.play().catch(() => {});
  }
  function setFull(on) {
    full = on;
    document.body.classList.toggle("pip-full", on);
    modeBtn.setAttribute("aria-label", on ? "返回悬浮小窗" : "全屏显示摄像头画面");
    syncMini();
    place();
  }
  modeBtn.addEventListener("click", () => setFull(!full));
  miniBtn.addEventListener("click", () => setFull(false));
  closeBtn.addEventListener("click", onClose);
  /* 拖标题条 = 移窗，拖右下角 = 改大小。按下落在 <button> 上就不拖（否则点关闭会顺手挪窗）。 */
  function drag(el, onMove) {
    el.addEventListener("pointerdown", (ev) => {
      if (full || (ev.target.closest && ev.target.closest("button"))) return;
      const sx = ev.clientX, sy = ev.clientY;
      el.setPointerCapture(ev.pointerId);
      win.classList.add("pip-dragging");
      const move = (e) => { onMove(e.clientX - sx, e.clientY - sy); place(); };
      const up = () => {
        el.removeEventListener("pointermove", move);
        el.removeEventListener("pointerup", up);
        el.removeEventListener("pointercancel", up);
        win.classList.remove("pip-dragging");
      };
      el.addEventListener("pointermove", move);
      el.addEventListener("pointerup", up);
      el.addEventListener("pointercancel", up);
    });
  }
  drag(bar, (dx, dy) => { x += dx; y += dy; });
  drag(grip, (dx) => { w += dx; });
  addEventListener("resize", place);
  return { syncMini: syncMini, setFull: setFull };
}

/* ── 表情面板渲染器（r103 从 initFace 拆出）──────────────────────────────
   为什么拆：initFace 当时已 194 行，超过 loc_guard 的 150 行上限（存量红）。
   真正的接缝不是"行数"，而是**职责**：这一块只做「把读数画到面板上 + 看门狗」，
   全是纯渲染与定时观察；摄像头开关生命周期是另一件事（stopFace/startFace）。
   r87 把两者塞进一个 IIFE 时，B 的看门狗定时器生命周期只能挂在 A 的作用域里
   —— 那是没拆干净的债，不是"风格偏好"。

   依赖靠参数显式传入（不读外层作用域）：这是拆分的全部意义 ——
   一旦它开始偷偷读外层的 faceOn/statePill，就等于拆了个假的。 */
function initFaceHud(deps) {
  const { FE, setStatus, paint, gl, hud, els, isOn, openedAt } = deps;
  const $ = (s) => document.querySelector(s);
  const PHASE_TEXT = {
    permission: "等待浏览器授权…（没看到弹窗？看地址栏左侧的相机图标）",
    model: "已获授权，正在加载表情模型（首次约 13MB）…",
    warmup: "正在识别…"
  };
  /* 看门狗（r87b/c）：开着摄像头但画面没人时标签不能停在初始态。
     3s 无读数 = 没看到人脸；2.5s 无更新 = 人脸离开。 */
  let lastReadAt = 0;

  function setPill(text, cls) {
    els.statePill.textContent = text;
    els.statePill.className = "face-hud-state " + (cls || "off");
  }
  function setSwitch(on) {
    els.switchEl.setAttribute("aria-checked", String(on));
    els.switchWord.textContent = on ? "已开启" : "已关闭";
    // r109：可见文字（已开启/已关闭）并入无障碍名——WCAG 2.5.3 要求可见标签是无障碍名的
    //   子串，固定 aria-label 对不上动态词（a11y A7 既存红，本轮顺手修）。
    //   ⚠️ 前缀必须短：a11y_check A7 的取数只截 aria-label 前 20 字符再比子串，
    //   长说明会把状态词挤出截断面（首版实测就是这么复红的）。
    els.switchEl.setAttribute("aria-label", "摄像头开关 · " + (on ? "已开启" : "已关闭"));
    els.dockBtn.setAttribute("aria-pressed", String(on));
  }
  function showStage(on) { els.hudVideo.hidden = !on; els.idleBox.hidden = on; }

  setInterval(() => {
    if (!isOn()) return;
    const st = FE.stats();
    const emo = $("#face-hud-emo");
    if (st.phase !== "running") {                  // 分阶段说人话，别让用户盯着一句"正在识别"
      const t = PHASE_TEXT[st.phase] || "正在准备…";
      emo.textContent = t;
      setStatus(t);
      setPill(st.phase === "permission" ? "授权中…" : "加载中…", "warn");
      return;
    }
    setPill("已开启", "on");
    if (st.samples === 0 && Date.now() - openedAt() > 3000) {
      emo.textContent = "没有看到人脸 —— 请正对摄像头，保证光线充足";
    } else if (st.samples > 0 && Date.now() - lastReadAt > 2500) {
      emo.textContent = "人脸离开了 —— 回到镜头前继续";
    }
  }, 600);

  function paintHud(view) {
    lastReadAt = Date.now();
    const hex = rgbHex(view.color);
    $("#face-hud-dot").dataset.bg = hex;
    // 独有三类走 FaceEngine.labelOf；margin 低时如实标「读数不稳」，不假装确定（r102）
    const base = FE.labelOf(view.emotion);
    /* r161 弱信号三态：weak ⇒ 「轻微 X（读数仅供参考）」；与 r113 质量门、r102 读数不稳并联 */
    const q = view.quality;
    const qReason = (q && !q.ok) ? q.reasons.map((r) => ({ lighting: "光线太暗或太亮", blur: "画面模糊",
      profile: "侧脸幅度大", "mouth-flat": "嘴部区域被遮挡" }[r] || r)).join("、") : "";
    const tails = [];
    if (view.weak) tails.push("读数仅供参考");
    if (qReason) tails.push(qReason + "，仅供参考");
    else if (view.confident === false && !view.weak) tails.push("读数不稳");
    /* r173：细分子维度（真笑/社交笑/担忧/紧绷/中性/微表情线索…）随主读数一起出。
       放 tails 里而不是另起一行：HUD 空间极小，多一行就会把主读数挤没。 */
    const subs = faceSubsText(view);
    if (subs) tails.push(subs);
    $("#face-hud-emo").textContent = (view.weak ? "轻微" : "") + base
      + (tails.length ? "（" + tails.join("；") + "）" : "");
    $("#face-hud-bar").dataset.w = Math.round((view.intensity || 0) * 100);
    $("#face-hud-bar").dataset.bg = hex;
    /* r172 C2：摄像头证据的逐次同意开关。默认关；每次点击都重新读 localStorage，
     * 不把状态缓存进内存 ⇒ 关掉后下一次询问立即生效，不存在「关不掉」的缓存态。 */
    const evBtn = $("#face-evidence");
    if (evBtn) {
      const paintEv = () => {
        const on = !!(window.ChatAgent && window.ChatAgent.faceEvidenceOn && window.ChatAgent.faceEvidenceOn());
        evBtn.setAttribute("aria-checked", on ? "true" : "false");
        const w = $("#face-evidence-word");
        if (w) w.textContent = on ? "本轮参考表情" : "不参考表情";
      };
      evBtn.addEventListener("click", () => {
        const on = !!(window.ChatAgent && window.ChatAgent.faceEvidenceOn && window.ChatAgent.faceEvidenceOn());
        if (on) {
          try { window.localStorage.removeItem("xinyu.faceEvidence.v1"); } catch (e) { /* 无痕模式本就存不住 */ }
        } else if (window.ChatAgent && window.ChatAgent.grantFaceEvidenceOnce) {
          window.ChatAgent.grantFaceEvidenceOnce();
        }
        paintEv();
      });
      paintEv();
    }
    const badge = $("#face-hud-smile");
    badge.hidden = false;
    badge.className = "face-smile-badge " + (view.smile ? "is-" + view.smile.kind : "is-none");
    badge.textContent = (view.smile && view.smile.occluded) ? "嘴部看不清（可能被遮挡），微笑判读暂停"
      : (view.smile && view.smile.masking) ? "社交性微笑 · 可能是强颜欢笑"
      : { duchenne: "真笑（眼周有参与）", social: "社交性微笑", none: "未检出微笑" }[(view.smile || {}).kind] || "—";
    paint(hud);
    if (gl) window.ThreeScene.setMistTint(view.color, view.intensity);
  }
  return { setPill, setSwitch, showStage, paintHud };
}

/* r117（pushgate-locfix）：initFace 两个自成一块的绑定从 IIFE 里外提（函数声明同层提升，无 TDZ）。
   gl/paint/faceChipHtml/$ 与本函数同在外层 IIFE 作用域，直接可见；initFace 的局部量走 deps。 */
function bindFaceScan(deps) {
  const { FE, probe, note, scanBtn, setStatus, paint } = deps;
  // A. 第二幕：扫描一次
  scanBtn.addEventListener("click", async () => {
    const v = $("#face-video");
    v.hidden = false;
    note.textContent = "正在准备表情模型（首次约 13MB，之后走缓存）…";
    scanBtn.disabled = true;
    setStatus("正在请求摄像头授权并加载模型…");
    const r = await FE.probeOnce({ video: v });
    scanBtn.disabled = false;
    v.hidden = true;
    if (!r.ok) { note.textContent = FE.reasonText(r.reason || "no-face"); setStatus(FE.reasonText(r.reason || "no-face")); return; }
    const box = document.createElement("div");
    box.className = "face-row";
    box.innerHTML = faceChipHtml(r.view);
    probe.insertBefore(box, note);
    paint(box);
    // 只染星雾底色（不点亮新星）：一次扫描不该在星图上留下"记忆"
    if (gl) window.ThreeScene.setMistTint(r.view.color, r.view.intensity);
    setTimeout(() => { if (window.ThreeScene) window.ThreeScene.setMistTint(null); }, 4000);
    note.textContent = "扫描完成 —— 画面没有保存，摄像头已关闭。";
    setStatus("扫描完成，摄像头已关闭");
  });
}

function faceDiagnoseReport(deps) {
  const { FE, setStatus, unavailable } = deps;
  /* 开局自检（r87d）：把"卡在哪一层"提前显示在状态行。 */
  return FE.diagnose().then((d) => {
    window.__XINYU_FACE_DIAG__ = d;
    if (d.devices === 0) {                  // 一个摄像头设备都没有：先别让用户点，直接说清
      unavailable("no-video-device");
      setStatus(FE.reasonText("no-video-device"));
      return;
    }
    if (d.permission === "denied") {
      setStatus("浏览器已阻止摄像头：点地址栏左侧锁形图标 → 摄像头 → 允许，再点开启（被记住的阻止不会再弹窗）");
    } else if (d.permission === "granted") {
      setStatus("摄像头权限：已授权 · 检测到 " + d.devices + " 个摄像头设备");
    } else if (d.devices > 0) {
      setStatus("检测到 " + d.devices + " 个摄像头设备，首次使用需在弹窗里点「允许」");
    }
  }).catch(() => { /* 自检失败不影响主链路 */ });
}

(function initFace() {
    const FE = window.FaceEngine;
    const probe = $("#face-probe"), scanBtn = $("#btn-face-scan"), dockBtn = $("#btn-face");
    const note = $("#face-note"), hud = $("#face-hud");
    const row = $("#face-row"), faceToggle = $("#face-toggle"), camToggle = $("#set-face-cam");
    const panelBtn = $("#btn-face-panel");   // r116：面板本体=悬浮小窗 #face-pip，坞里只留状态行
    // r109（老大拍板）：📷 与 🙂 只留一个——🙂 是唯一启停入口；📷 的总闸（彻底禁用+隐藏+记住）
    // 原样并入设置面板 #set-face-cam；row=坞内折叠行（面板的家），face-toggle=展开/收起面板的行按钮
    // 面板元素与状态声明前置：applyEnabled 在 boot 时就会读写它们（后置声明会踩 TDZ）
    const statePill = $("#face-hud-state"), switchEl = $("#face-switch"), switchWord = $("#face-switch-word");
    const idleBox = $("#face-hud-idle"), hudVideo = $("#face-hud-video");
    let faceOn = false, starting = false;
    /* 面板打开的时刻：看门狗据此区分「刚开还没出人脸」与「开着但人走了」 */
    let hudOpenedAt = 0;
    if (!FE || !probe || !dockBtn) return;
    // 状态行放在**对话坞里**（用户点的地方），第二幕那块 note 只讲第二幕自己的事
    const statusEl = $("#face-status");
    function setStatus(t) { if (statusEl) statusEl.textContent = t || ""; }
    window.__XINYU_FACE_UI__ = { state: "boot", reason: "" };   // 供 _test/ 取状态，禁靠猜

    function unavailable(reason) {
      window.__XINYU_FACE_UI__ = { state: "unavailable", reason: reason };
      scanBtn.hidden = true; dockBtn.hidden = true; panelBtn.hidden = true;
      row.hidden = true; setFacePanel(false);   // r115：入口全撤 + 抽屉不留空壳
      note.textContent = FE.reasonText(reason);
    }
    function setFacePanel(open) {
      hud.hidden = !open;
      document.body.classList.toggle("pip-open", open);
      if (open) pip.syncMini();   // 整屏态重开面板时把流补挂回角落缩略图
      if (faceToggle) faceToggle.setAttribute("aria-expanded", String(open));
      panelBtn.setAttribute("aria-expanded", String(open));
    }
    function ready() {
      window.__XINYU_FACE_UI__ = { state: "ready", reason: "" };
      scanBtn.hidden = false; dockBtn.hidden = false; panelBtn.hidden = false;
      // r109 入坞后：折叠行就位、面板默认收起（点行或 🙂 才展开）——不占常驻高度
      row.hidden = false; setFacePanel(false);
      setSwitch(false); setPill("已关闭", "off"); showStage(false);
      $("#face-hud-emo").textContent = "摄像头未开启";
    }

    /* 摄像头总闸（r87b，r109 搬进设置面板）：关=立即真停+隐藏坞内整块+记住；开=恢复（仍过能力探测）。 */
    function applyEnabled() {
      if (camToggle) camToggle.checked = FE.enabled();
      if (!FE.enabled()) {
        if (faceOn) stopFace();
        unavailable("cam-disabled");
        setStatus("摄像头已在总闸中停用（设置 → 允许心屿使用摄像头，可重新打开）");
        return;
      }
      const cap = FE.capability();
      if (!cap.ok) { unavailable(cap.reason); setStatus(FE.reasonText(cap.reason)); return; }
      ready();
      setStatus("");
      faceDiagnoseReport({ FE, setStatus, unavailable });
      note.textContent = "画面只在你本机的内存里过一遍 —— 不拍照、不上传、不留存。";
    }
    if (camToggle) camToggle.addEventListener("change", () => { FE.setEnabled(camToggle.checked); applyEnabled(); });
    if (faceToggle) faceToggle.addEventListener("click", () => setFacePanel(hud.hidden));   // 折叠行：只管开合抽屉，不碰摄像头
    // 本开关只控制"心屿用不用"；浏览器/系统层面的授权不在这里，也不能被网页改（安全设计如此）。
    // ⇒ 两件事必须说清，否则用户会把这个开关当成权限开关（老大实测就这么误会过）。

    /* 入口可见性只看**能不能用**（摄像头接口 + 安全上下文）与用户开关，不预载 13MB 模型：
       模型由 `whenReady` 在用户真点开时才拉（bridge 的 ensure()），否则每个访客每次打开页面
       都要先下 13MB —— 那是把"可选功能"做成"首屏税"。
       ⚠️ 首次调用**必须排在下方的 initFaceHud 解构之后**（r104 修，缺陷非本轮引入）：
       ready() 用的 setSwitch/setPill/showStage 是 initFaceHud 返回的 const，写在前面踩 TDZ；
       initFace 在顶层同步执行 ⇒ 一抛则 boot/开场/对话接线全不执行，表现是**整页打不开**。 */

    // A. 第二幕：扫描一次（绑定外提 bindFaceScan，见 initFace 上方）
    bindFaceScan({ FE, probe, note, scanBtn, setStatus, paint });

    // B. 第三幕：实时表情感知（开 = 真开摄像头；关 = 真停轨道）
    const { setPill, setSwitch, showStage, paintHud } = initFaceHud({
      FE, setStatus, paint, gl, hud,
      els: { statePill, switchEl, switchWord, dockBtn, hudVideo, idleBox },
      isOn: () => faceOn, openedAt: () => hudOpenedAt,
    });
    const pip = initFacePip({ win: $("#face-pip"), bar: $("#pip-bar"), grip: $("#pip-grip"),
      mainVideo: hudVideo, miniVideo: $("#pip-mini-video"), modeBtn: $("#btn-pip-mode"),
      closeBtn: $("#btn-pip-close"), miniBtn: $("#pip-mini"), root: document.documentElement,
      onClose: () => stopFace({ hide: true }) });
    panelBtn.addEventListener("click", () => setFacePanel(hud.hidden));   // 坞标题条的常驻键
    applyEnabled();   // 首次应用摄像头总闸状态（位置不能上移，理由见上方注释）
    /** 停：默认**保留面板**（开关回"已关闭"，面板留在原地给用户再开）
     *  opts.hide = 连面板一起收起（"收起"按钮 / 离开页面）。 */
    function stopFace(opts) {
      FE.stop(); faceOn = false; starting = false;
      setSwitch(false); setPill("已关闭", "off"); showStage(false);
      $("#face-hud-emo").textContent = "摄像头未开启";
      $("#face-hud-bar").dataset.w = 0; paint(hud);   // 强度条归零，别留着上一次的读数
      $("#face-hud-smile").hidden = true;
      if (opts && opts.hide) setFacePanel(false);   // r109：收起 = 停 + 折叠坞内面板
      if (gl) window.ThreeScene.setMistTint(null);
      setStatus("摄像头已关闭（指示灯灭）");
    }
    /* 反复点击必须有意义：启动中再点 = 取消（禁用会让"弹窗晾着"时按钮永远点不动）。 */
    async function startFace() {
      if (starting) { stopFace({}); setStatus("已取消摄像头启动"); return; }
      if (faceOn) return;
      starting = true;
      row.hidden = false; setFacePanel(true);   // r109：启动即展开坞内面板（预览+读数就在眼前）
      hudOpenedAt = Date.now();
      showStage(true);
      $("#face-hud-emo").textContent = "正在识别…";
      setPill("授权中…", "warn");
      setStatus("正在请求摄像头授权…");
      const ok = await FE.start({
        video: hudVideo,
        onRead: paintHud,
        onError: (reason) => {
          faceOn = false; starting = false;
          setSwitch(false); setPill("不可用", "warn"); showStage(false);
          note.textContent = FE.reasonText(reason);
          // 出错写在用户点的地方（对话坞）+ 附自检读数（权限/设备数），别只写第二幕那块要滚上去的说明
          setStatus(FE.reasonText(reason));
          FE.diagnose().then((d) => {
            window.__XINYU_FACE_DIAG__ = d;
            setStatus(FE.reasonText(reason) + "｜自检：权限=" + d.permission + "，设备=" + d.devices + " 个");
          }).catch(() => {});
        }
      });
      starting = false;
      faceOn = ok;
      setSwitch(ok);
      if (ok) { setPill("已开启", "on"); setStatus("表情感知已开启（画面仅本机处理）"); }
      else showStage(false);
    }
    // 侧边面板的开关（主控件）+ 对话坞的快捷图标：**同一个动作**，状态互相同步
    switchEl.addEventListener("click", () => { if (faceOn || starting) stopFace({}); else startFace(); });
    dockBtn.addEventListener("click", () => { if (faceOn || starting) stopFace({ hide: true }); else startFace(); });
    $("#btn-face-close").addEventListener("click", () => stopFace({ hide: true }));   // 收起 = 停 + 隐面板
    // 离开页面就停：摄像头指示灯必须灭，不能让页面在后台还开着镜头
    addEventListener("pagehide", () => { if (faceOn) stopFace(); });
  })();

  // 6) 语音（回复朗读 TTS + 语音输入 ASR）
  //    对标轮 r24 整体外提到 `src/js/voice.js`：行为零改动（同一套 DOM 与 localStorage 键），
  //    先摘这块是因为它与对话编排零耦合，能让剩余作用域只剩「编排 + 星图 + 曲线 + 窗口化 + 设置」。
  window.Voice.init();

  // 6.5) 数据主体权利 UI（r45 外提到 js/data-rights.js：披露翻转 / 清除回执 / 导出下载）
  window.DataRights.init({ beforeClear: function () {
    if (gl) { window.ThreeScene.cancelShow(); window.ThreeScene.douse(); }
    syncStars(); window.Chart.render();
    const pr = document.getElementById('probe-result');
    if (pr) pr.textContent = '星星已熄灭 —— 再和它说一句话，星雾会重新亮起来。';
  }, afterClear: function () {
    syncStars(); window.Chart.render();   // r65 拆槽后条数与回执不再同槽互覆
  } });

  // 7) 情绪曲线：r25 外提到 `src/js/chart.js`（行为零改动；判据=browser_check 的曲线计数断言）
  window.Chart.init();

  // J4：远端记忆（默认关闭）。开启且服务端可达时，用数据库权威副本覆盖本地后重建星图；
  // 未开启/不可达 → 走下面这行，行为与 v1 完全一致（确保既有回归不受影响）。
  if (window.MemoryStore.isRemote()) {
    window.MemoryStore.hydrate()
      .then(ok => { if (ok) { replayStars(); window.Chart.render(); } })
      .catch(() => { /* 服务端不可达 → 保持本地记忆 */ });
  }
  replayStars(); // 进页面先按本机记忆把星图重建出来
  startOpeningShow(); // r80：一键点亮默认打开 —— 每次加载播一次开场演示，播完回到上面这行的状态

  // 7) 设置面板（provider 预设 / 密钥录入 / 流式开关）
  //    r27 外提到 `src/js/settings.js`：行为零改动，判据 = `_test/settings_panel_check.py` S1–S8（含五类注入反例）。
  //    徽章刷新留在编排层，用 onSaved 回调注入，模块不反向依赖 app.js。
  window.Settings.init({ onSaved: refreshBadge });

  // 9) 深浅主题切换（r15）：默认深色；选择持久化到 peiliao.theme.v1
  (function () {
    const KEY = "peiliao.theme.v1";
    const btn = $("#btn-theme");
    if (!btn) return;   // 头部无切换按钮（旧页面缓存等）时静默跳过，不炸主链路
    function apply(t) {
      // r42 无障碍：图标是装饰（aria-hidden），文字与无障碍名各自独立，
      // 且可见文字必须是无障碍名的子串（WCAG 2.5.3 Label in Name，语音控制用户按可见文字下指令）。
      const light = t === "light";
      if (light) { document.documentElement.dataset.theme = "light"; }
      else { delete document.documentElement.dataset.theme; }
      const ico = $("#theme-ico"), word = $("#theme-word");
      if (ico) ico.setAttribute("href", light ? "#i-sun" : "#i-moon");   // r115：emoji 换 SVG 精灵，切的是 <use> 的引用
      if (word) word.textContent = light ? "浅色" : "深色";
      btn.setAttribute("aria-label", (light ? "浅色" : "深色") + "主题，点击切换");
    }
    let saved = "dark";
    try { saved = localStorage.getItem(KEY) || "dark"; } catch (e) {}
    apply(saved);
    btn.addEventListener("click", () => {
      const next = document.documentElement.dataset.theme === "light" ? "dark" : "light";
      try { localStorage.setItem(KEY, next); } catch (e) {}
      apply(next);
    });
  })();
})();
