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
    (act) => { if (act === 4) window.Chart.render(); }
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
  //    窗口化（DOM 上界 60 / 折叠配额 / 展开较早）r26 外提到 `src/js/chat-window.js`；
  //    判据 = `ux_guards_check.py` U2a–U2f（浏览器实跑行为，不是源码 grep，搬错即红）。
  const CW = window.ChatWindow;
  CW.init("#chat-log", { history: () => window.ChatAgent.getHistory() });

  $("#chat-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const input = $("#chat-input");
    const text = input.value.trim();
    if (!text) return;
    input.value = "";
    CW.push("user", text);
    const thinking = CW.push("ai", "心屿正在感受你的话…", "");
    thinking.classList.add("thinking");
    /* 流式：首个增量到达时才把 thinking 换成正式气泡并逐字覆写；
     * 上游/代理不支持流式时 onDelta 永不触发，收尾按整包一次性渲染（与旧行为一致）。 */
    let bubble = null;
    const onDelta = (full) => {
      if (bubble) { CW.update(bubble, full); return; }
      window.__seenStreamingBubble = true;   // 供 _test/stream_contract.py 断言「确实出现过逐字气泡」
      thinking.remove();
      bubble = CW.push("ai", full, "逐字生成中…");
      bubble.classList.add("streaming");
    };
    try {
      const r = await window.ChatAgent.respond(text, onDelta);
      if (bubble) bubble.remove(); else thinking.remove();
      const modeLabel = { model: "在线大模型生成", fallback: "大模型暂不可用 · 离线共情模板", offline: "离线共情模板", guard: "安全转介策略" }[r.mode];
      // 情绪识别来源必须如实标注：后端 /api/emotion 与本地词典是两套实现，界面不得含糊
      const emoSrcLabel = r.emoSrc === "backend" ? " · 情绪:后端" : "";
      const aiMsg = CW.push("ai", r.reply,
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
      window.Chart.render();
    } catch (err) {
      thinking.remove();
      CW.push("ai", "刚才我走神了一下（网络不稳定）。你可以再发一次，或点右上角「模型设置」检查连接。", "友好错误态");
    }
  });

  // 6) 语音（回复朗读 TTS + 语音输入 ASR）
  //    对标轮 r24 整体外提到 `src/js/voice.js`：行为零改动（同一套 DOM 与 localStorage 键），
  //    先摘这块是因为它与对话编排零耦合，能让剩余作用域只剩「编排 + 星图 + 曲线 + 窗口化 + 设置」。
  window.Voice.init();

  $("#btn-clear").addEventListener("click", () => {
    window.MemoryStore.clear();
    if (gl) { window.ThreeScene.cancelShow(); window.ThreeScene.douse(); }   // 星星同步熄灭
    syncStars();
    $("#probe-result").textContent = "星星已熄灭 —— 再和它说一句话，星雾会重新亮起来。";
    window.Chart.render();
  });
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
