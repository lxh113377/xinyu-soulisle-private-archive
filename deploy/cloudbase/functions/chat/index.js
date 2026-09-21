/* 心屿 · 腾讯云 CloudBase 云函数：chat（HTTP 触发，对外路径 /api/chat）
 * 作用：把 DeepSeek（OpenAI 兼容）调用封在服务端，密钥只存在于云函数环境变量，
 *       前端源码与静态托管产物里**零密钥**（与 Cloudflare Pages Function 版同职责）。
 *
 * 环境变量（CloudBase 控制台 → 云函数 chat → 配置 → 环境变量）：
 *   DEEPSEEK_KEY   必填
 *   DEEPSEEK_BASE  默认 https://api.deepseek.com/v1
 *   DEEPSEEK_MODEL 默认 deepseek-chat
 *
 * 请求：POST { messages:[{role,content}], temperature?, max_tokens? }
 * 响应：透传上游 JSON；带 CORS 头（前端静态托管与云函数不同域，必须允许跨域）。
 */
const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST,OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
  "Content-Type": "application/json"
};

exports.main = async (event) => {
  // HTTP 访问服务的预检请求
  if (event.httpMethod === "OPTIONS") {
    return { statusCode: 204, headers: CORS, body: "" };
  }

  const key = process.env.DEEPSEEK_KEY;
  const base = process.env.DEEPSEEK_BASE || "https://api.deepseek.com/v1";
  const model = process.env.DEEPSEEK_MODEL || "deepseek-chat";
  if (!key) {
    return { statusCode: 500, headers: CORS, body: JSON.stringify({ error: "no-key" }) };
  }

  let payload;
  try {
    payload = typeof event.body === "string" ? JSON.parse(event.body) : (event.body || {});
  } catch {
    return { statusCode: 400, headers: CORS, body: JSON.stringify({ error: "bad-json" }) };
  }

  try {
    const upstream = await fetch(base.replace(/\/$/, "") + "/chat/completions", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: "Bearer " + key },
      body: JSON.stringify({
        model,
        messages: payload.messages || [],
        temperature: payload.temperature ?? 0.85,
        max_tokens: payload.max_tokens ?? 220
      })
    });
    const data = await upstream.json().catch(() => ({ error: "upstream-nonjson" }));
    return { statusCode: upstream.status, headers: CORS, body: JSON.stringify(data) };
  } catch (e) {
    return { statusCode: 502, headers: CORS, body: JSON.stringify({ error: "upstream-fail", detail: String(e) }) };
  }
};
