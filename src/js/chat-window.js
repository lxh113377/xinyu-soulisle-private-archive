/* 心屿 · 对话窗口化（DOM 上界守卫）
 *
 * 对标轮 r26 从 `app.js` 外提（第三刀）。前两刀挑的是"与编排零耦合"的模块（语音、曲线），
 * 这一刀不同：窗口化**被对话主流程调用**（提交/流式/历史恢复都要往日志里塞气泡），
 * 所以它的接口设计目标是"把 DOM 细节关在模块内"，而不是"把状态搬出去"。
 *
 * 思路对标 LobeChat 的 react-virtuoso（长列表虚拟化），但本项目零构建、零依赖，故自写轻量版：
 * 只保留最近 RENDER_MAX 条在 DOM 里，被折叠的最旧若干条缓存在 trimmedBuf，
 * 点「展开较早」可分批放回 —— 完整历史始终在 ChatAgent.getHistory() 与本机存储里，不受影响。
 *
 * 两条原实现约束原样保留（不得在迁移中"顺手优化"）：
 *   1) 折叠配额 quota 点「展开较早」时**临时抬高**，否则刚放回就被同一条上限再裁掉（展开等于没展开）；
 *      用户再发新消息时回落默认档 —— 展开是临时查看，不是永久扩容。
 *   2) 每次 push 后滚到底部；流式增量（update）同样跟手，否则逐字生成会滚出视口。
 *
 * 判据：`_test/ux_guards_check.py` U2a–U2f（连发 90 条 → .msg ≤60 / 折叠提示标条数 /
 * 上下文未被截断 / 展开真放回且顺序在前 / 新消息后收回上界 / 全程无 JS 异常）。
 */
window.ChatWindow = (function () {
  const RENDER_MAX = 60, TRIM_BATCH = 20;
  let log = null;
  const trimmedBuf = [];
  let quota = RENDER_MAX;   // 折叠配额，默认 = RENDER_MAX，展开时临时抬高

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
  function toBottom() { if (log) log.scrollTop = log.scrollHeight; }
  /** 塞一条气泡并维护窗口上界；返回 DOM 节点，调用方可继续加 class / dataset */
  function push(who, text, tag) {
    if (!log) return null;
    quota = RENDER_MAX;                       // 新消息 → 窗口收回默认档（展开是临时查看，不是永久扩容）
    const d = makeMsgNode(who, text, tag);
    log.appendChild(d);
    trimLog();
    toBottom();
    return d;
  }
  /** 覆写已有气泡正文并跟手滚动（流式逐字生成走这里） */
  function update(el, text) {
    setBody(el, text);
    toBottom();
  }
  /** 绑定日志容器并按需恢复上次会话（历史在 ChatAgent 与本机存储里，这里只重建渲染） */
  function init(root, opts) {
    log = typeof root === "string" ? document.querySelector(root) : root;
    if (!log) return false;
    const o = opts || {};
    const hist = (typeof o.history === "function") ? o.history() : (o.history || []);
    if (hist.length) {
      for (const h of hist.slice(-20)) {
        push(h.role === "user" ? "user" : "ai", h.content, h.role === "assistant" ? "上次会话记录" : "");
      }
      push("ai", "欢迎回来，我们接着聊。刚才说到哪儿了？", "上下文已恢复");
    } else {
      push("ai", "你好，我是心屿。今天过得怎么样？说什么都行，我会先听懂你的情绪，再陪你聊。", "本机开场白 · 未经大模型");
    }
    return true;
  }

  return { init, push, update, setTag, toBottom };
})();
