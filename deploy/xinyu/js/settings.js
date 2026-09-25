/* 心屿 · 模型设置面板（对话框 + provider 预设 + 密钥录入）
 *
 * 对标轮 r27 从 `app.js` 外提（第四刀，行为零改动）。
 * 这是四刀里唯一**直接碰密钥输入框**的模块，所以动刀前先补了行为判据
 * `_test/settings_panel_check.py`（S1–S8 + 五类注入反例）——没有行为判据就说"零改动"，等于没人能证明没改坏。
 *
 * 三条不能改的密钥安全语义（原实现约束，逐条有判据盯着）：
 *   1) Key 输入框**恒不回显**已存密钥（S1）；
 *   2) Key 留空保存 = **不改**，直接覆盖会把已存 Key 洗掉（S3）；
 *   3) `proxy` 由运行环境持有、对话框不展示，合并写入时保留（S6 取消一字不改）。
 *
 * 依赖注入而非反向依赖：面板保存后要刷新引擎徽章，但徽章归编排层所有，
 * 故 `init({ onSaved })` 由 app.js 传回调进来，模块不认识 `refreshBadge`。
 */
window.Settings = (function () {
  const $ = (s) => document.querySelector(s);

  function fillFromCfg() {
    const c = window.ChatAgent.getCfg();
    $("#set-base").value = c.base; $("#set-model").value = c.model; $("#set-key").value = "";
    $("#set-stream").checked = c.stream !== false;
    $("#set-provider").value = "";
  }
  function open() {
    fillFromCfg();
    $("#dlg-settings").showModal();
  }
  /** @param {{onSaved?: function}} opts onSaved：保存并写入配置后回调（刷新徽章等编排层副作用） */
  function init(opts) {
    const dlg = $("#dlg-settings");
    if (!dlg) return false;                       // 页面无对话框（旧缓存等）时静默跳过，不炸主链路
    const o = opts || {};
    const btn = $("#btn-settings");
    if (btn) btn.addEventListener("click", open);
    // 快捷预设：选一家就把 base+model 填进输入框（Key 仍需用户自己填，前端永不代存他人密钥）
    const prov = $("#set-provider");
    if (prov) prov.addEventListener("change", (e) => {
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
      if (o.onSaved) o.onSaved();
    });
    return true;
  }

  return { init, open };
})();
