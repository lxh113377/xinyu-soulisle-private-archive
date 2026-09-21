/* 心屿 · 情绪记忆存储（仅本机 localStorage，可一键清除） */
window.MemoryStore = (function () {
  const KEY = "peiliao.emotions.v1";
  let mem = null; // localStorage 不可用时的内存降级

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
  }
  function all() { return load().slice(); }
  function clear() { mem = []; try { localStorage.removeItem(KEY); } catch {} }

  return { record, all, clear };
})();
