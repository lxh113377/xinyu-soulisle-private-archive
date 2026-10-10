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
    // r61 遮挡：见 CHANGELOG
    (act) => { if (act === 4) { window.Chart.render(); if (dockOpen()) setDock(false); } }
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
    const map = { duchenne: ["真笑（眼周有参与）", "is-duchenne"], social: ["社交性微笑", "is-social"], none: ["未检出微笑", "is-none"] };
    const one = map[s.kind] || map.none;
    const extra = s.masking ? " · 伴紧张线索，可能是强颜欢笑" : "";
    return `<span class="face-smile-badge ${one[1]}">${one[0]}${extra}</span>`;
  }
  function faceChipHtml(v) {
    const hex = rgbHex(v.color);
    const pct = Math.round((v.intensity || 0) * 100);
    // 低置信度（主次分贴太近）如实显示「读数不稳」，不假装确定（r102）
    const wobble = v.confident === false
      ? `<span class="face-wobble" title="主情绪与次情绪分数接近，这一帧的读数仅供参考">读数不稳</span>` : "";
    return `<span class="emotion-chip"><i class="dot" data-bg="${hex}"></i>表情：${window.FaceEngine.labelOf(v.emotion)}${wobble}`
      + `<span class="intensity-bar"><i data-w="${pct}" data-bg="${hex}"></i></span></span>` + smileBadgeHtml(v.smile);
  }
  function divergenceHtml(view) {
    const E = window.EmotionEngine, f = view.face;
    if (!f || !view.divergence) return "";
    // 表情侧可能报文本没有的类（惊讶/厌恶/轻蔑），用 family 归并后再比，
    // 否则「表情说轻蔑、文字说烦躁」会被渲染成"不一致"，而其实是同一族（r102）
    const fLabel = window.FaceEngine.labelOf(f.emotion);
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

  // 底部对话坞折叠：点标题按钮切换；点叙事区自动收起（避免坞长期遮住幕内按钮）
  const dockOpen = () => $("#chat-dock").classList.contains("open");
  function setDock(open) {
    $("#chat-dock").classList.toggle("open", open);
    $("#btn-dock").textContent = open ? "收起 ▾" : "展开 ▴";
    $("#btn-dock").setAttribute("aria-expanded", String(open));
  }
  $("#btn-dock").addEventListener("click", () => setDock(!dockOpen()));
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
      const aiMsg = CW.push("ai", r.reply,
        `${modeLabel}${r.streamed ? " · 逐字流式" : ""}${r.path ? " · 情绪双路：" + r.path : ""}${emoSrcLabel}${memLabel}${dropLabel}${r.latency ? " · " + r.latency + "ms" : ""} · 情绪：${window.EmotionEngine.labelOf(r.emotion)}${faceLabel}`);
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
        appliedSecondary: applied, path: r.path ? "双路情绪 · " + r.path : "词典快判",
        face: r.face || null, divergence: r.divergence || "" });
      window.Chart.render();
    } catch (err) {
      thinking.remove();
      CW.push("ai", "刚才我走神了一下（网络不稳定）。你可以再发一次，或点右上角「模型设置」检查连接。", "友好错误态");
    }
  });

  /* 6.1) 面部表情识别（r87）：不可用即隐藏入口（禁伪装）；画面只在内存里过一遍，零上传零落盘。 */
  (function initFace() {
    const FE = window.FaceEngine;
    const probe = $("#face-probe"), scanBtn = $("#btn-face-scan"), dockBtn = $("#btn-face");
    const note = $("#face-note"), hud = $("#face-hud"), camBtn = $("#btn-cam");
    // 面板元素与状态声明前置：applyEnabled 在 boot 时就会读写它们（后置声明会踩 TDZ）
    const statePill = $("#face-hud-state"), switchEl = $("#face-switch"), switchWord = $("#face-switch-word");
    const idleBox = $("#face-hud-idle"), hudVideo = $("#face-hud-video");
    let faceOn = false, starting = false;
    if (!FE || !probe || !dockBtn) return;
    // 状态行放在**对话坞里**（用户点的地方），第二幕那块 note 只讲第二幕自己的事
    const statusEl = $("#face-status");
    function setStatus(t) { if (statusEl) statusEl.textContent = t || ""; }
    window.__XINYU_FACE_UI__ = { state: "boot", reason: "" };   // 供 _test/ 取状态，禁靠猜

    function unavailable(reason) {
      window.__XINYU_FACE_UI__ = { state: "unavailable", reason: reason };
      scanBtn.hidden = true; dockBtn.hidden = true; hud.hidden = true;
      note.textContent = FE.reasonText(reason);
    }
    function ready() {
      window.__XINYU_FACE_UI__ = { state: "ready", reason: "" };
      scanBtn.hidden = false; dockBtn.hidden = false;
      // 侧边控制面板就位：面板本身是"开关的家"，所以默认可见（开关=已关闭，画面显示待开启）
      hud.hidden = false;
      setSwitch(false); setPill("已关闭", "off"); showStage(false);
      $("#face-hud-emo").textContent = "摄像头未开启";
    }

    /* 摄像头总闸（r87b）：关=立即真停+隐藏入口+记住；开=恢复入口（仍过能力探测）。按钮永远可见。 */
    function applyEnabled() {
      camBtn.setAttribute("aria-pressed", String(FE.enabled()));
      if (!FE.enabled()) {
        if (faceOn) stopFace();
        unavailable("cam-disabled");
        setStatus("摄像头已在开关中停用（点「📷 摄像头」可重新打开）");
        return;
      }
      const cap = FE.capability();
      if (!cap.ok) { unavailable(cap.reason); setStatus(FE.reasonText(cap.reason)); return; }
      ready();
      setStatus("");
      /* 开局自检（r87d）：把"卡在哪一层"提前显示在状态行。 */
      FE.diagnose().then((d) => {
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
      note.textContent = "画面只在你本机的内存里过一遍 —— 不拍照、不上传、不留存。";
    }
    camBtn.addEventListener("click", () => { FE.setEnabled(!FE.enabled()); applyEnabled(); });
    // 本开关只控制"心屿用不用"；浏览器/系统层面的授权不在这里，也不能被网页改（安全设计如此）。
    // ⇒ 两件事必须说清，否则用户会把这个开关当成权限开关（老大实测就这么误会过）。

    /* 入口可见性只看**能不能用**（摄像头接口 + 安全上下文）与用户开关，不预载 13MB 模型：
       模型由 `whenReady` 在用户真点开时才拉（bridge 的 ensure()），
       否则每个访客每次打开页面都要先下 13MB —— 那是把"可选功能"做成"首屏税"。 */
    applyEnabled();

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

    // B. 第三幕：实时表情感知（开 = 真开摄像头；关 = 真停轨道）
    /* 看门狗（r87b/c）：开着摄像头但画面没人时标签不能停在初始态。分阶段说人话 +
       按 stats() 读数新旧翻面（3s 无读数=没人脸；2.5s 无更新=人脸离开）。 */
    let hudOpenedAt = 0, lastReadAt = 0;
    const PHASE_TEXT = {
      permission: "等待浏览器授权…（没看到弹窗？看地址栏左侧的相机图标）",
      model: "已获授权，正在加载表情模型（首次约 13MB）…",
      warmup: "正在识别…"
    };
    /* 侧边面板的状态胶囊：实时显示真实状态（不是装饰）——开=绿、过程中=琥珀、关=灰 */
    function setPill(text, cls) { statePill.textContent = text; statePill.className = "face-hud-state " + (cls || "off"); }
    function setSwitch(on) {
      switchEl.setAttribute("aria-checked", String(on));
      switchWord.textContent = on ? "已开启" : "已关闭";
      dockBtn.setAttribute("aria-pressed", String(on));
    }
    function showStage(on) { hudVideo.hidden = !on; idleBox.hidden = on; }
    setInterval(() => {
      if (!faceOn) return;
      const st = FE.stats();
      const emo = $("#face-hud-emo");
      if (st.phase !== "running") {                      // 分阶段说人话，别让用户盯着一句"正在识别"
        const t = PHASE_TEXT[st.phase] || "正在准备…";
        emo.textContent = t;
        setStatus(t);
        setPill(st.phase === "permission" ? "授权中…" : "加载中…", "warn");
        return;
      }
      setPill("已开启", "on");
      if (st.samples === 0 && Date.now() - hudOpenedAt > 3000) {
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
      $("#face-hud-emo").textContent = view.confident === false ? base + "（读数不稳）" : base;
      $("#face-hud-bar").dataset.w = Math.round((view.intensity || 0) * 100);
      $("#face-hud-bar").dataset.bg = hex;
      const badge = $("#face-hud-smile");
      badge.hidden = false;
      badge.className = "face-smile-badge " + (view.smile ? "is-" + view.smile.kind : "is-none");
      badge.textContent = (view.smile && view.smile.masking) ? "社交性微笑 · 可能是强颜欢笑"
        : { duchenne: "真笑（眼周有参与）", social: "社交性微笑", none: "未检出微笑" }[(view.smile || {}).kind] || "—";
      paint(hud);
      if (gl) window.ThreeScene.setMistTint(view.color, view.intensity);
    }
    /** 停：默认**保留面板**（开关回"已关闭"，面板留在原地给用户再开）
     *  opts.hide = 连面板一起收起（"收起"按钮 / 离开页面）。 */
    function stopFace(opts) {
      FE.stop(); faceOn = false; starting = false;
      setSwitch(false); setPill("已关闭", "off"); showStage(false);
      $("#face-hud-emo").textContent = "摄像头未开启";
      $("#face-hud-bar").dataset.w = 0; paint(hud);   // 强度条归零，别留着上一次的读数
      $("#face-hud-smile").hidden = true;
      if (opts && opts.hide) hud.hidden = true;
      if (gl) window.ThreeScene.setMistTint(null);
      setStatus("摄像头已关闭（指示灯灭）");
    }
    /* 反复点击必须有意义：启动中再点 = 取消（禁用会让"弹窗晾着"时按钮永远点不动）。 */
    async function startFace() {
      if (starting) { stopFace({}); setStatus("已取消摄像头启动"); return; }
      if (faceOn) return;
      starting = true;
      hud.hidden = false;
      hudOpenedAt = Date.now(); lastReadAt = 0;
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
      if (ico) ico.textContent = light ? "☀" : "☾";
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
