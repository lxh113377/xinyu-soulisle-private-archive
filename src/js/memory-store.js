/* 心屿 · 情绪记忆存储
 * 默认：仅本机 localStorage（离线可用，v1 行为不变）。
 * J4（可选）：`cfg.remote === true` 时把服务端数据库当**权威副本** —— 写入时同步推送、
 *   启动时用服务端数据覆盖本地；服务端不可达则完全回落到 localStorage，功能不受影响。
 */
window.MemoryStore = (function () {
  const KEY = "peiliao.emotions.v1";
  const CFG_KEY = "peiliao.cfg.v1";
  const SID_KEY = "peiliao.session.v1";
  let mem = null; // localStorage 不可用时的内存降级

  function cfg() {
    try { return JSON.parse(localStorage.getItem(CFG_KEY) || "{}"); } catch { return {}; }
  }
  /** 远端记忆开关：默认关闭（现有回归全部依赖本地存储，不能被动改变行为） */
  function isRemote() { return cfg().remote === true; }
  function sessionId() {
    try {
      let s = localStorage.getItem(SID_KEY);
      if (!s) {
        s = "s-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 8);
        localStorage.setItem(SID_KEY, s);
      }
      return s;
    } catch { return "s-ephemeral"; }
  }
  function api(path, opts) { return fetch("/api/memory" + path, opts); }
  const JSON_HEADERS = { "Content-Type": "application/json" };

  function load() {
    if (mem) return mem;
    try { return (mem = JSON.parse(localStorage.getItem(KEY) || "[]")); }
    catch { mem = []; return mem; }
  }
  function persist() {
    try { localStorage.setItem(KEY, JSON.stringify(mem)); } catch { /* 内存态 */ }
  }
  function record(entry) {
    const arr = load();
    arr.push({ ts: Date.now(), ...entry });
    if (arr.length > 500) arr.splice(0, arr.length - 500);
    persist();
    if (isRemote()) {
      try {
        api("/emotion", {
          method: "POST", headers: JSON_HEADERS,
          body: JSON.stringify({
            sessionId: sessionId(), emotion: entry.emotion, intensity: entry.intensity || 0.5,
            secondary: entry.secondary || null, text: entry.text || ""
          })
        }).catch(() => { /* 推送失败不影响本地 */ });
      } catch { /* 忽略 */ }
    }
  }
  /** 对话消息同步（J4 chat_message 表）；与情绪记录一样是「本地先写、远端尽力而为」 */
  function pushMessage(role, content) {
    if (!isRemote()) return;
    try {
      api("/message", {
        method: "POST", headers: JSON_HEADERS,
        body: JSON.stringify({ sessionId: sessionId(), role, content })
      }).catch(() => {});
    } catch { /* 忽略 */ }
  }
  function all() { return load().slice(); }
  function clear() {
    mem = [];
    try { localStorage.removeItem(KEY); } catch { /* 忽略 */ }
    if (isRemote()) {
      try { api("/" + encodeURIComponent(sessionId()), { method: "DELETE" }).catch(() => {}); } catch { /* 忽略 */ }
    }
  }
  /** 用服务端权威副本覆盖本地；返回 true 表示确实取到了数据（供调用方决定是否重绘星图） */
  function hydrate() {
    if (!isRemote()) return Promise.resolve(false);
    return api("/emotions?limit=500&sessionId=" + encodeURIComponent(sessionId()))
      .then(r => (r.ok ? r.json() : Promise.reject(new Error("HTTP " + r.status))))
      .then(list => {
        if (!Array.isArray(list) || !list.length) return false;
        mem = list.map(x => ({
          ts: Date.parse(x.createdAt) || Date.now(),
          emotion: x.emotion,
          intensity: x.intensity,
          secondary: x.secondary || undefined,
          text: x.text
        }));
        persist();
        return true;
      });
  }

  return { record, all, clear, hydrate, pushMessage, isRemote, sessionId };
})();
