/* 心屿 · 依据可核对面（r172）
 *
 * 解决的缺口：气泡里的〔依据:PSY-XXX-NNN·级〕此前只能"看"，点不开、查不到原始文献——
 * 证据溯源只走到模型侧（模型标的编号会被核对/更正/打未查证），没走到用户侧。
 * 本模块把最后一公里接上：点开 = 卡片标题/等级/定级理由/摘要/正文 + 逐条来源题录与可点 URL。
 *
 * 三条硬纪律（与既有反臆造机制同族）：
 *   ① 查不到就说查不到：编号不在数据件里 → 明写「该编号未在库内登记」，不编内容；
 *   ② 来源件加载失败 → 明写「来源件加载失败」，**不静默当成"无来源"**（那会让加载故障被读成学术结论）；
 *   ③ 只读不改：面板不改写气泡正文，标记形态由 chat-agent 的 verifyCitations 独占，本层不碰。
 *
 * 加载形态：来源件与 psych-kb.js 同走懒加载（328 KB，只在用户点开时才拉，不占首屏）。
 * 独立成文件而非塞进 chat-agent.js：chat-agent.js 已在逐文件预算边缘（28,919/28,800），
 * 新增功能不该挤占注入面的预算。
 */
(function (global) {
  "use strict";

  var CITE_RE = /〔依据[:：]\s*([^〕·]+?)\s*·\s*([^〕]*?)〕/g;
  var loadState = null;   // null=未开始 / Promise / false=失败

  function ensureSrc(waitMs) {
    if (global.__XINYU_PSYCH_KB_SRC__) return Promise.resolve(true);
    if (!loadState) {
      loadState = new Promise(function (resolve) {
        var el = document.createElement("script");
        el.src = "data/psych-kb-sources.js";
        el.async = true;
        el.onload = function () { resolve(!!global.__XINYU_PSYCH_KB_SRC__); };
        el.onerror = function () { resolve(false); };
        document.head.appendChild(el);
      });
    }
    var ms = waitMs == null ? 2500 : waitMs;
    var timer = 0;
    return Promise.race([loadState, new Promise(function (r) { timer = setTimeout(function () { r(false); }, ms); })])
      .then(function (ok) { clearTimeout(timer); return ok; });
  }

  function findEntry(id) {
    var KB = global.__XINYU_PSYCH_KB__;
    if (!KB || !KB.entries) return null;
    var key = String(id || "").trim().toUpperCase();
    for (var i = 0; i < KB.entries.length; i++) {
      if (String(KB.entries[i].id).toUpperCase() === key) return KB.entries[i];
    }
    return null;
  }

  /* ── 面板 ─────────────────────────────────────────────────────────── */
  function ensurePanel() {
    var p = document.querySelector("#kb-source-panel");
    if (p) return p;
    p = document.createElement("div");
    p.id = "kb-source-panel";
    p.className = "kb-panel";
    p.hidden = true;
    p.setAttribute("role", "dialog");
    p.setAttribute("aria-label", "依据可核对");
    var close = document.createElement("button");
    close.type = "button";
    close.className = "kb-panel-close";
    close.textContent = "×";
    close.addEventListener("click", function () { closePanel(); });
    var body = document.createElement("div");
    body.className = "kb-panel-body";
    p.appendChild(close);
    p.appendChild(body);
    document.body.appendChild(p);
    return p;
  }

  function closePanel() {
    var p = document.querySelector("#kb-source-panel");
    if (p) p.hidden = true;
  }

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c];
    });
  }

  /* 正文按 URL 段切，URL 做成真链接；非 http 的一律当纯文本（防 javascript: 伪协议） */
  function renderSources(items) {
    if (!items || !items.length) {
      return '<p class="kb-panel-warn">此条目在库内未登记可核对来源 —— 请按「未查证」对待。</p>';
    }
    return "<ol class=\"kb-panel-src\">" + items.map(function (it) {
      var u = String(it.u || "");
      var safe = /^https?:\/\//i.test(u);
      return "<li>" + esc(it.l || "") +
        (safe ? ' <a href="' + esc(u) + '" target="_blank" rel="noopener noreferrer">' + esc(u) + "</a>" : "") +
        "</li>";
    }).join("") + "</ol>";
  }

  function renderBody(body, id, srcMap, srcOk) {
    var e = findEntry(id);
    if (!e) {
      body.innerHTML = '<p class="kb-panel-warn">编号 ' + esc(id) +
        " 未在本次加载的知识库数据件里找到（可能被判为「未查证」并更正过）。这里不编内容。</p>";
      return;
    }
    var rec = srcOk && srcMap ? srcMap[String(e.id).toUpperCase()] : null;
    body.innerHTML =
      '<p class="kb-panel-head"><span class="kb-panel-id">' + esc(e.id) + '</span>' +
      '<span class="kb-panel-lv lv-' + esc(e.level) + '">' + esc(e.level) + " 级</span></p>" +
      "<h3>" + esc(e.title) + "</h3>" +
      (rec && rec.r ? '<p class="kb-panel-reason"><b>为什么定这个级：</b>' + esc(rec.r) + "</p>" : "") +
      '<p class="kb-panel-sum">' + esc(e.summary) + "</p>" +
      '<p class="kb-panel-content">' + esc(e.content) + "</p>" +
      "<h4>来源（可点开核对）</h4>" +
      (srcOk ? renderSources(rec ? rec.s : null)
             : '<p class="kb-panel-warn">来源件加载失败/超时 —— 这是**加载故障**，不等于「此条没有来源」，请勿据此降低对它的信任。</p>');
  }

  function open(id) {
    var p = ensurePanel();
    var body = p.querySelector(".kb-panel-body");
    var e = findEntry(id);
    p.hidden = false;
    if (!e) {
      renderBody(body, id, null, false);
      return;
    }
    body.innerHTML = '<p class="kb-panel-loading">正在取来源…</p>';
    ensureSrc().then(function (ok) {
      var map = ok ? ((global.__XINYU_PSYCH_KB_SRC__ || {}).src || null) : null;
      renderBody(body, id, map, ok);
    });
  }

  /* ── 把气泡正文里的〔依据:…〕变成可点 ─────────────────────────────── */
  function enhance(bubble) {
    if (!bubble || typeof bubble.querySelector !== "function") return 0;
    var host = bubble.querySelector(".msg-text") || bubble;
    if (!host || host.dataset.kbCiteBound === "1") return 0;
    host.dataset.kbCiteBound = "1";
    var text = host.textContent || "";
    CITE_RE.lastIndex = 0;
    if (!CITE_RE.test(text)) return 0;
    CITE_RE.lastIndex = 0;
    host.textContent = "";
    var last = 0, m, n = 0;
    while ((m = CITE_RE.exec(text)) !== null) {
      if (m.index > last) host.appendChild(document.createTextNode(text.slice(last, m.index)));
      var s = document.createElement("span");
      s.className = "kb-cite";
      s.setAttribute("role", "button");
      s.setAttribute("tabindex", "0");
      s.dataset.kbId = String(m[1] || "").trim();
      s.dataset.kbLv = String(m[2] || "").trim();
      s.textContent = m[0];
      host.appendChild(s);
      last = m.index + m[0].length;
      n++;
    }
    if (last < text.length) host.appendChild(document.createTextNode(text.slice(last)));
    host.addEventListener("click", function (ev) {
      var t = ev.target && ev.target.closest ? ev.target.closest(".kb-cite") : null;
      /* stopPropagation 是**必需**的，不是保险：下面 document 上还有一个「点外部关闭」监听器。
       * 不拦的话同一次点击会先打开面板、再冒泡到 document 把它关掉（面板开了 0 帧）。 */
      if (t) { ev.preventDefault(); ev.stopPropagation(); open(t.dataset.kbId); }
    });
    host.addEventListener("keydown", function (ev) {
      if (ev.key !== "Enter" && ev.key !== " ") return;
      var t = ev.target && ev.target.closest ? ev.target.closest(".kb-cite") : null;
      if (t) { ev.preventDefault(); open(t.dataset.kbId); }
    });
    return n;
  }

  document.addEventListener("click", function (ev) {
    var p = document.querySelector("#kb-source-panel");
    if (!p || p.hidden) return;
    if (p.contains(ev.target)) return;
    /* 兜底：事件源若是依据标记就不关。即便上面 host 的 stopPropagation 被误删，
     * 这一道也能挡住「开→立刻关」这个次序陷阱（两道互为对照，不是冗余）。 */
    if (ev.target && ev.target.closest && ev.target.closest(".kb-cite")) return;
    closePanel();
  });
  document.addEventListener("keydown", function (ev) {
    if (ev.key === "Escape") closePanel();
  });

  global.KbSourcePanel = { enhance: enhance, open: open, close: closePanel, ensureSrc: ensureSrc };
})(window);