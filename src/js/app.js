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

  // 2) 滚动叙事
  window.ScrollStory.init(
    (t) => { if (gl) window.ThreeScene.setScrollProgress(t); },
    (act) => { if (act === 4) drawChart(); }
  );

  // 3) 引擎徽章
  function refreshBadge() {
    const b = $("#mode-badge");
    if (window.ChatAgent.isOnline()) { b.textContent = "● 在线 AI"; b.classList.remove("offline"); }
    else { b.textContent = "● 离线共情模板"; b.classList.add("offline"); }
    $("#chat-engine").textContent = "引擎：" + (window.ChatAgent.isOnline() ? "在线大模型（OpenAI 兼容）" : "离线共情模板引擎");
  }
  refreshBadge();

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
  /** 星雾配色说明文案：有次情绪时标注「双色星雾」。secondRGB 必须是渲染实际采用的颜色
   *  （ThreeScene 为保证两色可分辨，可能已把次色沿色相环旋开），否则色点与星雾对不上。 */
  function mistText(main, second, secondRGB) {
    const L = window.EmotionEngine.labelOf;
    const rgbSec = secondRGB || (second ? window.EmotionEngine.colorOf(second) : null);
    return second
      ? `星雾配色：<b style="color:${rgbHex(window.EmotionEngine.colorOf(main))}">${L(main)}</b> 主 ＋ <b style="color:${rgbHex(rgbSec)}">${L(second)}</b> 辅（双色星雾）`
      : `星雾配色：<b style="color:${rgbHex(window.EmotionEngine.colorOf(main))}">${L(main)}</b> 单色`;
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

  /** 第二幕「它记住了你」读数面板：情绪 chips + 双路路径 + 星雾配色 */
  function renderReadout(view) {
    const E = window.EmotionEngine;
    const crisis = view.emotion === "crisis";
    const chips = view.all.slice(0, 3).map(x => {
      const c = E.colorOf(x.emotion);
      const hex = rgbHex(c);
      const pct = Math.round(Math.min(1, x.score) * 100);
      return `<span class="emotion-chip"><i class="dot" style="background:${hex}"></i>${E.labelOf(x.emotion)}<span class="intensity-bar"><i style="width:${pct}%;background:${hex}"></i></span></span>`;
    }).join("") || `<span class="emotion-chip">未检测到明显情绪词，按平静处理</span>`;
    $("#probe-result").innerHTML =
      (crisis ? `<div class="emotion-chip" style="border-color:#ff7a7a;color:#ff9a9a"><i class="dot" style="background:#ff5566"></i>检测到危机信号 — 已启用安全转介策略</div>` : "") +
      chips +
      `<p class="muted" style="margin-top:8px">${view.path || "词典快判"}：${E.labelOf(view.emotion)}（强度 ${Math.round((view.intensity || 0) * 100)}%）</p>` +
      `<p class="muted" id="probe-mist">${mistText(view.emotion, view.secondary, view.appliedSecondary)}</p>`;
  }

  // 4.5) 一键点亮：六种情绪各点一簇（仅演示，不写入记忆）；再点一次回到「我的记忆」
  let showMode = false;
  let showTimer = null; // 声明前置：点击回调里读写它，禁止先用后声明
  $("#btn-lightshow").addEventListener("click", () => {
    if (!gl) return;
    showMode = !showMode;
    if (showMode) {
      const { palette, duration } = window.ThreeScene.lightShow(180);
      $("#btn-lightshow").textContent = "↺ 回到我的记忆";
      $("#probe-result").innerHTML = `<p class="muted">正在清屏，重新点亮六种情绪…（按 Esc 或点一下画面退出）</p>`;
      document.body.classList.add("showtime");   // 隐藏全部 UI，只留背景星雾
      // 播放结束**不跳回**：继续停在清屏画面欣赏，唯一退出口是右下角按钮
      showTimer = setTimeout(() => {
        $("#probe-result").innerHTML =
          `<p class="muted" style="margin-bottom:8px">六种情绪已由内向外点亮成六圈（仅演示，不会写进你的记忆；想清空再点「↺ 回到我的记忆」）：</p>` +
          palette.map(p => `<span class="emotion-chip"><i class="dot" style="background:${rgbHex(p.color)}"></i>${p.label}</span>`).join("");
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
    $("#btn-lightshow").textContent = "✨ 一键点亮";
    $("#probe-result").textContent = "已回到你的真实记忆 —— 继续和它说话，星雾会按你的情绪继续亮。";
  }

  // 右下角按钮：只恢复 UI，**保留**刚点亮的星雾；滚动欣赏不会被打断
  $("#btn-exit-show").addEventListener("click", () => {
    document.body.classList.remove("showtime");
  });

  // 底部对话坞折叠：点标题按钮切换；点叙事区自动收起（避免坞长期遮住幕内按钮）
  function setDock(open) {
    $("#chat-dock").classList.toggle("open", open);
    $("#btn-dock").textContent = open ? "收起 ▾" : "展开 ▴";
    $("#btn-dock").setAttribute("aria-expanded", String(open));
  }
  $("#btn-dock").addEventListener("click", () => setDock(!$("#chat-dock").classList.contains("open")));
  $("#story").addEventListener("click", (e) => { if (!e.target.closest("#chat-dock")) setDock(false); });

  // 5) 对话（刷新后恢复历史，多轮上下文不丢）
  const log = $("#chat-log");
  /* 对话窗口化（对标 LobeChat 的 react-virtuoso 思路，零依赖版）：
   * 长会话（评委连续演示 / 长期自用）会让 #chat-log 的 DOM 单调增长，滚动与重排成本随之上升。
   * 这里只保留最近 RENDER_MAX 条在 DOM 里，被折叠的最旧若干条缓存在 trimmedBuf，
   * 点「展开较早」可分批放回 —— 完整历史始终在 ChatAgent.getHistory() 与本机存储里，不受影响。 */
  const RENDER_MAX = 60, TRIM_BATCH = 20;
  const trimmedBuf = [];
  /* 折叠配额：默认 = RENDER_MAX。点「展开较早」时临时抬高（否则刚放回就被同一条上限裁掉，
   * 展开等于没展开）；用户再发新消息时回落，保证 DOM 上界长期受控。 */
  let quota = RENDER_MAX;
  function setTag(el, tag) {
    let t = el.querySelector(".tag");
    if (!t) { t = document.createElement("span"); t.className = "tag"; el.appendChild(t); }
    t.textContent = tag;
  }
  function setBody(el, text) {
    const s = el.querySelector(".msg-text");
    if (s) s.textContent = text; else el.textContent = text;
  }
  function nodeToItem(d) {
    return { who: d.classList.contains("user") ? "user" : "ai",
      text: d.querySelector(".msg-text") ? d.querySelector(".msg-text").textContent : d.textContent,
      tag: d.querySelector(".tag") ? d.querySelector(".tag").textContent : "" };
  }
  function foldHint() {
    let hint = log.querySelector(".log-fold");
    if (!hint) {
      hint = document.createElement("div");
      hint.className = "log-fold";
      const b = document.createElement("button");
      b.type = "button";
      b.className = "ghost-btn tiny";
      b.id = "btn-expand-log";
      b.addEventListener("click", expandLog);
      hint.appendChild(b);
      log.insertBefore(hint, log.firstChild);
    }
    hint.firstChild.textContent = `↑ 展开较早记录（已折叠 ${trimmedBuf.length} 条）`;
  }
  function trimLog() {
    const nodes = log.querySelectorAll(".msg");
    if (nodes.length <= quota) return;
    const over = nodes.length - quota;
    for (let i = 0; i < over; i++) {
      trimmedBuf.push(nodeToItem(nodes[i]));
      nodes[i].remove();
    }
    foldHint();
  }
  /** 分批放回：取最近折叠的 TRIM_BATCH 条按原时间顺序前插，并临时抬高配额（下一步新消息会收回） */
  function expandLog() {
    const back = trimmedBuf.splice(-TRIM_BATCH, TRIM_BATCH);
    if (!back.length) return;
    const fold = log.querySelector(".log-fold");
    if (fold) fold.remove();
    quota += back.length;
    const frag = document.createDocumentFragment();
    for (const it of back) frag.appendChild(makeMsgNode(it.who, it.text, it.tag));
    const first = log.querySelector(".msg");
    if (first) log.insertBefore(frag, first); else log.appendChild(frag);
    if (trimmedBuf.length) foldHint();
  }
  function makeMsgNode(who, text, tag) {
    const d = document.createElement("div");
    d.className = "msg " + who;
    const s = document.createElement("span");
    s.className = "msg-text";
    s.textContent = text;
    d.appendChild(s);
    if (tag) setTag(d, tag);
    return d;
  }
  function pushMsg(who, text, tag) {
    quota = RENDER_MAX;                       // 新消息 → 窗口收回默认档（展开是临时查看，不是永久扩容）
    const d = makeMsgNode(who, text, tag);
    log.appendChild(d);
    trimLog();
    log.scrollTop = log.scrollHeight;
    return d;
  }
  const hist = window.ChatAgent.getHistory();
  if (hist.length) {
    for (const h of hist.slice(-20)) pushMsg(h.role === "user" ? "user" : "ai", h.content, h.role === "assistant" ? "上次会话记录" : "");
    pushMsg("ai", "欢迎回来，我们接着聊。刚才说到哪儿了？", "上下文已恢复");
  } else {
    pushMsg("ai", "你好，我是心屿。今天过得怎么样？说什么都行，我会先听懂你的情绪，再陪你聊。", "在线 AI · 共情模式");
  }

  $("#chat-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const input = $("#chat-input");
    const text = input.value.trim();
    if (!text) return;
    input.value = "";
    pushMsg("user", text);
    const thinking = pushMsg("ai", "心屿正在感受你的话…", "");
    thinking.classList.add("thinking");
    /* 流式：首个增量到达时才把 thinking 换成正式气泡并逐字覆写；
     * 上游/代理不支持流式时 onDelta 永不触发，收尾按整包一次性渲染（与旧行为一致）。 */
    let bubble = null;
    const onDelta = (full) => {
      if (bubble) { setBody(bubble, full); log.scrollTop = log.scrollHeight; return; }
      window.__seenStreamingBubble = true;   // 供 _test/stream_contract.py 断言「确实出现过逐字气泡」
      thinking.remove();
      bubble = pushMsg("ai", full, "逐字生成中…");
      bubble.classList.add("streaming");
    };
    try {
      const r = await window.ChatAgent.respond(text, onDelta);
      if (bubble) bubble.remove(); else thinking.remove();
      const modeLabel = { model: "在线大模型生成", fallback: "大模型暂不可用 · 离线共情模板", offline: "离线共情模板", guard: "安全转介策略" }[r.mode];
      // 情绪识别来源必须如实标注：后端 /api/emotion 与本地词典是两套实现，界面不得含糊
      const emoSrcLabel = r.emoSrc === "backend" ? " · 情绪:后端" : "";
      const aiMsg = pushMsg("ai", r.reply,
        `${modeLabel}${r.streamed ? " · 逐字流式" : ""}${r.path ? " · 情绪双路：" + r.path : ""}${emoSrcLabel}${r.latency ? " · " + r.latency + "ms" : ""} · 情绪：${window.EmotionEngine.labelOf(r.emotion)}`);
      aiMsg.dataset.emotion = r.emotion;
      window.Voice.speak(r.reply);   // 朗读开关打开时同步播出（失败静默，绝不影响主链路）
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
        appliedSecondary: applied, path: r.path ? "双路情绪 · " + r.path : "词典快判" });
      drawChart();
    } catch (err) {
      thinking.remove();
      pushMsg("ai", "刚才我走神了一下（网络不稳定）。你可以再发一次，或点右上角「模型设置」检查连接。", "友好错误态");
    }
  });

  // 6) 语音（回复朗读 TTS + 语音输入 ASR）
  //    对标轮 r24 整体外提到 `src/js/voice.js`：行为零改动（同一套 DOM 与 localStorage 键），
  //    先摘这块是因为它与对话编排零耦合，能让剩余作用域只剩「编排 + 星图 + 曲线 + 窗口化 + 设置」。
  window.Voice.init();

  // 7) 情绪曲线（折线=强度，色点=情绪类别，图例=6情绪分布计数）
  function drawChart() {
    const cv = $("#mood-chart");
    const ctx = cv.getContext("2d");
    // HiDPI：CSS 像素逻辑绘制 + setTransform 缩放，高分屏曲线不再发虚；布局宽变化时同步画布
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const vw = cv.clientWidth || 560, vh = 220;
    if (cv.width !== Math.round(vw * dpr) || cv.height !== Math.round(vh * dpr)) {
      cv.width = Math.round(vw * dpr); cv.height = Math.round(vh * dpr);
    }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const data = window.MemoryStore.all();
    ctx.clearRect(0, 0, vw, vh);
    $("#chart-count").textContent = data.length ? `本机已记录 ${data.length} 条情绪（仅存于此浏览器）` : "还没有记录 — 聊几句就有了";
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
    // 图例：6 情绪分布
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
  $("#btn-clear").addEventListener("click", () => {
    window.MemoryStore.clear();
    if (gl) { window.ThreeScene.cancelShow(); window.ThreeScene.douse(); }   // 星星同步熄灭
    syncStars();
    $("#probe-result").textContent = "星星已熄灭 —— 再和它说一句话，星雾会重新亮起来。";
    drawChart();
  });
  // 视口/布局变化时曲线按新 CSS 宽重绘（防抖，避免拖动期高频重算；无数据时跳过）
  let chartResizeTimer = 0;
  addEventListener("resize", () => {
    clearTimeout(chartResizeTimer);
    chartResizeTimer = setTimeout(() => { if (window.MemoryStore.all().length) drawChart(); }, 200);
  });

  // J4：远端记忆（默认关闭）。开启且服务端可达时，用数据库权威副本覆盖本地后重建星图；
  // 未开启/不可达 → 走下面这行，行为与 v1 完全一致（确保既有回归不受影响）。
  if (window.MemoryStore.isRemote()) {
    window.MemoryStore.hydrate()
      .then(ok => { if (ok) { replayStars(); drawChart(); } })
      .catch(() => { /* 服务端不可达 → 保持本地记忆 */ });
  }
  replayStars(); // 进页面先按本机记忆把星图重建出来

  // 7) 设置面板
  const dlg = $("#dlg-settings");
  $("#btn-settings").addEventListener("click", () => {
    const c = window.ChatAgent.getCfg();
    $("#set-base").value = c.base; $("#set-model").value = c.model; $("#set-key").value = "";
    $("#set-stream").checked = c.stream !== false;
    $("#set-provider").value = "";
    dlg.showModal();
  });
  // 快捷预设：选一家就把 base+model 填进输入框（Key 仍需用户自己填，前端永不代存他人密钥）
  $("#set-provider").addEventListener("change", (e) => {
    const v = e.target.value;
    if (!v) return;
    const [base, model] = v.split("|");
    $("#set-base").value = base;
    $("#set-model").value = model;
  });
  dlg.addEventListener("close", () => {
    if (dlg.returnValue !== "save") return;
    // Key 留空 = 不改：输入框恒不回显旧 Key，空输入若直接覆盖会把已存 Key 洗掉；
    // proxy 由运行环境持有，对话框不展示，合并写入予以保留
    const patch = {
      base: $("#set-base").value.trim(),
      model: $("#set-model").value.trim(),
      stream: $("#set-stream").checked
    };
    const keyInput = $("#set-key").value.trim();
    if (keyInput) patch.key = keyInput;
    window.ChatAgent.setCfg(patch);
    refreshBadge();
  });

  // 9) 深浅主题切换（r15）：默认深色；选择持久化到 peiliao.theme.v1
  (function () {
    const KEY = "peiliao.theme.v1";
    const btn = $("#btn-theme");
    if (!btn) return;   // 头部无切换按钮（旧页面缓存等）时静默跳过，不炸主链路
    function apply(t) {
      if (t === "light") { document.documentElement.dataset.theme = "light"; btn.textContent = "☀ 浅色"; }
      else { delete document.documentElement.dataset.theme; btn.textContent = "☾ 深色"; }
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
