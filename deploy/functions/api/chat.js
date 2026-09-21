/* 心屿 · Cloudflare Pages Function：/api/chat
 * 作用：前端同源代理转发 DeepSeek（OpenAI 兼容），密钥隔离在服务端 env，绝不进前端源码。
 * env: DEEPSEEK_KEY(必填) / DEEPSEEK_BASE(默认 https://api.deepseek.com/v1) / DEEPSEEK_MODEL(默认 deepseek-chat)
 */
export async function onRequestPost(context) {
  const { request, env } = context;
  const key = env.DEEPSEEK_KEY;
  const base = env.DEEPSEEK_BASE || "https://api.deepseek.com/v1";
  const model = env.DEEPSEEK_MODEL || "deepseek-chat";
  if (!key) return Response.json({ error: "no-key" }, { status: 500 });

  let payload;
  try { payload = await request.json(); }
  catch { return Response.json({ error: "bad-json" }, { status: 400 }); }

  const upstream = await fetch(base.replace(/\/$/, "") + "/chat/completions", {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: "Bearer " + key },
    body: JSON.stringify({ model, messages: payload.messages || [], temperature: payload.temperature ?? 0.85, max_tokens: payload.max_tokens ?? 220 })
  });
  const data = await upstream.json().catch(() => ({ error: "upstream-nonjson" }));
  return Response.json(data, { status: upstream.status });
}
