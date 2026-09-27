/* 心屿 · 数据主体权利 UI（r45 从 app.js 外提）
 * 三件事：披露语随模式翻转 / 清除带回执并复核 / 导出打包下载。
 * 与对话编排零耦合，故外提——app.js 当时因这块顶穿单文件字节预算（16,815/14,390）。
 * 判据 = _test/data_rights_check.py（D1-D4）。
 */
window.DataRights = (function () {
  const REMOTE_TXT = "情绪与对话会同步到**本演示实例的服务端**（为的是跨设备也记得你），可随时一键清除并当场核验归零，也可打包导出带走。";
  const LOCAL_TXT = "所有情绪与对话**只留在本机浏览器**（不上传），可随时一键清除。";

  function el(id) { return document.getElementById(id); }

  /** 披露语必须跟着真实模式走；两态互斥，不存在"永远说不上传"的那一版 */
  function syncDisclosure() {
    const lead = el("data-disclosure");
    if (lead) lead.textContent = "你在心屿说过的每一句话，都会成为它星雾里的一颗星星。"
      + (window.MemoryStore.isRemote() ? REMOTE_TXT : LOCAL_TXT);
  }

  function receipt(r) {
    const bits = [r.local ? "本机已清除" : "本机清除失败"];
    if (r.removed === null && !r.error) bits.push("未连服务端（无需服务端清除）");
    else if (r.verified === true) bits.push("服务端已删 " + r.removed + " 条，复核为 0");
    else if (r.verified === false) bits.push("服务端复核未归零：" + r.error);
    else bits.push("服务端清除失败：" + (r.error || "无回执"));
    return bits.join(" ｜ ");
  }

  function download(bundle) {
    const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "xinyu-my-data-" + bundle.sessionId + ".json";
    document.body.appendChild(a);
    a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 0);
  }

  function init(hooks) {
    const h = hooks || {};
    syncDisclosure();
    const count = el("chart-count");
    const say = function (t) { if (count) count.textContent = t; };
    const btnClear = el("btn-clear");
    if (btnClear) btnClear.addEventListener("click", function () {
      if (h.beforeClear) h.beforeClear();
      say("正在清除…");
      window.MemoryStore.clear().then(function (r) {
        // 回执写自己的槽：#probe-result 是情绪探针读数位，会被探针渲染覆写（r44 实测）
        say(receipt(r));
        // 计数刷新必须在清除**之后**：beforeClear 里那次 syncStars 量到的还是清除前的条数，
        // 于是"清除失败/成功"两种回执都配着一个旧数字（r60 实测：界面 1 ⇄ 数据源 0）。
        if (h.afterClear) h.afterClear();
        syncDisclosure();
      });
    });
    const btnExport = el("btn-export");
    if (btnExport) btnExport.addEventListener("click", function () {
      say("正在打包…");
      window.MemoryStore.exportAll().then(function (b) {
        const n = (b.source.local || []).length
          + ((b.source.server && b.source.server.emotions) || []).length;
        download(b);
        say("已导出 " + n + " 条记录" + (b.error ? "（服务端部分失败）" : ""));
      });
    });
    return { syncDisclosure: syncDisclosure };
  }

  return { init: init, syncDisclosure: syncDisclosure };
})();
