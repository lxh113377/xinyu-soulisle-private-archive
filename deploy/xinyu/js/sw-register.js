/* 只读离线壳注册（r28 建，r54 外提）：仅在 http(s) 下注册（file:// 无 SW），失败静默 ——
 * 离线壳是增益，不能成为主链路的新故障点。
 *
 * 为什么从 index.html 的内联块挪到这个文件（r54）：这是**能不能开严格 CSP 的前置**。
 * 全站只有这一个内联 <script>，留着它就只能写 script-src 'unsafe-inline'，
 * 等于把 CSP 最有价值的一条指令作废。
 *
 * ⚠️ 相对路径不能照抄：内联脚本里 "sw.js" 按**文档** URL 解析，外提成 js/sw-register.js 后
 * 按脚本自身 URL 解析会变成 /js/sw.js（404 且 scope 非法），而 .catch(()=>{}) 会把它咽成静默无操作
 * —— 症状是"离线壳悄悄没了"，不是报错。故显式以 document.baseURI 为基，保持与内联版逐字同语义。
 */
if ("serviceWorker" in navigator && location.protocol.startsWith("http")) {
  addEventListener("load", () => {
    navigator.serviceWorker.register(new URL("sw.js", document.baseURI).href, { scope: "./" })
      .catch(() => {});
  });
}
