/* 公网版体验模式：密钥全部隔离在服务端 env，前端零密钥。
 * 双平台自适应（同一份产物两处可用）：
 *   · Cloudflare Pages  → 同源代理 /api/chat（Pages Function）
 *   · 腾讯云 CloudBase 静态托管（*.tcloudbaseapp.com）→ 云函数 HTTP 访问服务（跨域，绝对地址）
 */
try {
  var CB_API = 'https://qwer-d4gf2r76o8829463b.service.tcloudbase.com/api';
  var PROXY = location.hostname.indexOf('tcloudbaseapp.com') >= 0 ? CB_API : '/api/chat';
  var cur = JSON.parse(localStorage.getItem('peiliao.cfg.v1') || '{}');
  if (!cur.base && !cur.key && !cur.proxy) {
    localStorage.setItem('peiliao.cfg.v1', JSON.stringify({ proxy: PROXY }));
    window.__PEILIAO_DEMO__ = true;
  }
} catch (e) {}
