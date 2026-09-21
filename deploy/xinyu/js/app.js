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
  let showTimer = null;
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
  function pushMsg(who, text, tag) {
    const d = document.createElement("div");
    d.className = "msg " + who;
    d.textContent = text;
    if (tag) { const t = document.createElement("span"); t.className = "tag"; t.textContent = tag; d.appendChild(t); }
    log.appendChild(d);
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
    try {
      const r = await window.ChatAgent.respond(text);
      thinking.remove();
      const modeLabel = { model: "在线大模型生成", fallback: "大模型暂不可用 · 离线共情模板", offline: "离线共情模板", guard: "安全转介策略" }[r.mode];
      pushMsg("ai", r.reply, `${modeLabel}${r.path ? " · 情绪双路：" + r.path : ""}${r.latency ? " · " + r.latency + "ms" : ""} · 情绪：${window.EmotionEngine.labelOf(r.emotion)}`);
      // 记住这条情绪 → 点亮一簇星（一个瞬间 = 1~8 颗，强度越高越多）
      const lexLex = window.EmotionEngine.scan(text);
      const sec = window.EmotionEngine.secondaryOf(lexLex.all, r.emotion);
      let applied = null;
      if (gl) {
        if (r.emotion === "crisis") window.ThreeScene.setCrisis();
        else applied = window.ThreeScene.setEmotion(window.EmotionEngine.colorOf(r.emotion), r.intensity || 0.5,
          sec && window.EmotionEngine.colorOf(sec));
      }
      syncStars();
      renderReadout({ all: lexLex.all, emotion: r.emotion, intensity: r.intensity, secondary: sec,
        appliedSecondary: applied, path: r.path ? "双路情绪 · " + r.path : "词典快判" });
      drawChart();
    } catch (err) {
      thinking.remove();
      pushMsg("ai", "刚才我走神了一下（网络不稳定）。你可以再发一次，或点右上角「模型设置」检查连接。", "友好错误态");
    }
  });

  // 6) 语音输入（Web Speech API，zh-CN；不支持则隐藏按钮）
  (function voiceInit() {
    const btn = $("#btn-voice");
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { btn.style.display = "none"; return; }
    const rec = new SR();
    rec.lang = "zh-CN";
    rec.interimResults = true;
    rec.continuous = false;
    let listening = false;
    btn.addEventListener("click", () => {
      if (listening) { rec.stop(); return; }
      listening = true;
      btn.classList.add("recording");
      btn.textContent = "●";
      rec.start();
    });
    rec.onresult = (e) => {
      let t = "";
      for (const res of e.results) t += res[0].transcript;
      $("#chat-input").value = t.slice(0, 500);
    };
    rec.onend = rec.onerror = () => {
      listening = false;
      btn.classList.remove("recording");
      btn.textContent = "🎤";
    };
  })();

  // 7) 情绪曲线（折线=强度，色点=情绪类别，图例=6情绪分布计数）
  function drawChart() {
    const cv = $("#mood-chart");
    const ctx = cv.getContext("2d");
    const data = window.MemoryStore.all();
    ctx.clearRect(0, 0, cv.width, cv.height);
    $("#chart-count").textContent = data.length ? `本机已记录 ${data.length} 条情绪（仅存于此浏览器）` : "还没有记录 — 聊几句就有了";
    if (!data.length) {
      ctx.fillStyle = "#8a93b2"; ctx.font = "14px sans-serif"; ctx.textAlign = "center";
      ctx.fillText("暂无数据", cv.width / 2, cv.height / 2);
      return;
    }
    const W = cv.width, H = cv.height, pad = 26;
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
    dlg.showModal();
  });
  dlg.addEventListener("close", () => {
    if (dlg.returnValue !== "save") return;
    window.ChatAgent.setCfg({
      base: $("#set-base").value.trim(),
      key: $("#set-key").value.trim(),
      model: $("#set-model").value.trim()
    });
    refreshBadge();
  });
})();
