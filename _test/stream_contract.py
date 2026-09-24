# -*- coding: utf-8 -*-
"""M1 流式输出验收：`POST /api/chat` 的 SSE 直通 + 前端逐字渲染 + 回落不崩，三条判据。

前置：Java 服务端起在 8123（工作目录=项目根，且 env 里有 LLM_KEY/DEEPSEEK_KEY）：
  $env:JAVA_HOME='C:\\Program Files\\Eclipse Adoptium\\jdk-17.0.20.101-hotspot'
  $env:DEEPSEEK_KEY='<key>'
  java -jar server\\target\\soulisle-server.jar --server.port=8123
再跑：python _test/stream_contract.py

## 为什么三条缺一不可（防恒真）
  A 非流式契约不破：不带 stream 的请求必须仍是**整包 JSON**（AC-OBS-08「与 v1 1:1」的判据不能因加流式而失效）。
  B 流式真是流式：带 `stream:true` 必须回 `text/event-stream`，且**分片数 ≥2**
    （只数 content-type 会被"整包塞进一个 data: 帧"糊过去；分片数是"边生成边下发"的机器证据）。
  C 回落不冒充：代理不可达时必须落回**离线共情模板**，且标签里不得出现「逐字流式」
    ——否则就是"没有流式却装作有"，与项目「降级必须明示」红线同一条。
"""
import json
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

BASE = "http://127.0.0.1:8123"
API = BASE + "/api/chat"
MSG = [{"role": "system", "content": "你是心屿。"}, {"role": "user", "content": "今天被导师批评了，心情很低落"}]


def post(payload, timeout=90):
    req = urllib.request.Request(
        API, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        ct = r.headers.get("content-type") or ""
        raw = r.read().decode("utf-8", "replace")
        return r.status, ct, raw


def frames(raw):
    out = []
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            payload = line[5:].strip()
            if payload and payload != "[DONE]":
                out.append(payload)
    return out


def main():
    ok = True
    print("=== A 非流式契约（不带 stream）===")
    try:
        st, ct, raw = post({"messages": MSG, "temperature": 0.85, "max_tokens": 60})
    except Exception as e:
        print(f"🔴 A-FAIL 请求失败: {e}\n   检查 Java 服务端是否起在 8123")
        return 1
    is_json = "application/json" in ct
    has_choices = False
    try:
        j = json.loads(raw)
        has_choices = bool(j.get("choices")) and bool(j["choices"][0].get("message", {}).get("content"))
    except Exception:
        pass
    print(f"  status={st} content-type={ct!r} choices={has_choices}")
    if not (st == 200 and is_json and has_choices):
        print("  🔴 A-FAIL：非流式请求必须回整包 JSON 且含 choices[0].message.content")
        ok = False
    else:
        print("  ✅ A-PASS：v1 整包契约未破")

    print("=== B 流式（stream:true）===")
    try:
        st2, ct2, raw2 = post({"messages": MSG, "temperature": 0.85, "max_tokens": 60, "stream": True})
    except Exception as e:
        print(f"🔴 B-FAIL 请求失败: {e}")
        return 1
    fr = frames(raw2)
    texts = 0
    assembled = ""
    for f in fr:
        try:
            piece = json.loads(f)["choices"][0]["delta"].get("content") or ""
        except Exception:
            continue
        if piece:
            texts += 1
            assembled += piece
    print(f"  status={st2} content-type={ct2!r} data帧={len(fr)} 含内容帧={texts} 拼回字数={len(assembled)}")
    if not ("text/event-stream" in ct2 and texts >= 2 and len(assembled) > 5):
        print("  🔴 B-FAIL：要 event-stream + ≥2 个含 delta.content 的帧（分片数是'边生成边下发'的硬证据）")
        ok = False
    else:
        print(f"  ✅ B-PASS：真流式，样例前 40 字：{assembled[:40]!r}")

    print("=== C 前端逐字渲染 + 不可达回落（Playwright）===")
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        print(f"⚠️ C-SKIP playwright 不可用: {e}")
        return 0 if ok else 1

    errors = []

    def run(proxy):
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch()
            except Exception:
                browser = p.chromium.launch(channel="msedge")
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(BASE + "/index.html", wait_until="networkidle")
            page.evaluate("""(proxy) => {
              localStorage.setItem('peiliao.cfg.v1', JSON.stringify({
                proxy, base: 'http://127.0.0.1:18123/v1', key: 'invalid-key-for-test', model: 'x', stream: true
              }));
              localStorage.removeItem('peiliao.emotions.v1');
              localStorage.removeItem('peiliao.history.v1');
            }""", proxy)
            page.reload(wait_until="networkidle")
            page.wait_for_timeout(500)
            page.fill("#chat-input", "论文被拒了三次，感觉努力全白费")
            page.click("#chat-form button[type=submit]")
            page.wait_for_timeout(14000)
            msgs = page.eval_on_selector_all(".msg.ai", "els => els.map(e => e.textContent)")
            # 采样：生成过程中是否出现过「逐字生成中」气泡（流式的前端可见证据）
            had_stream = page.evaluate("() => !!window.__seenStreamingBubble")
            page.close()
            browser.close()
            return (msgs[-1] if msgs else ""), had_stream

    c_last, c_stream = run("/api/chat")
    d_last, d_stream = run("http://127.0.0.1:18123/api/chat")
    print("  C_LAST:", c_last[:150].replace("\n", " "))
    print("  D_LAST:", d_last[:150].replace("\n", " "))
    if "在线大模型生成" not in c_last:
        print("  🔴 C-FAIL：走 Java /api/chat 未命中在线生成")
        ok = False
    if "逐字流式" not in c_last:
        print("  🔴 C-FAIL：标签缺「逐字流式」→ 前端没走流式路径（B 已证服务端能流，疑在前端回落）")
        ok = False
    if "逐字流式" in d_last or "在线大模型生成" in d_last:
        print("  🔴 D-FAIL：不可达端点竟显示在线/流式 → 判据恒真")
        ok = False
    if "离线共情模板" not in d_last:
        print("  🔴 D-FAIL：不可达端点未回落离线模板")
        ok = False
    if errors:
        print("  🔴 JS 报错:", errors[:3])
        ok = False
    if ok:
        print("  ✅ C-PASS：在线走逐字流式，不可达落回离线模板且不冒充")
    print("STREAM-CONTRACT-PASS" if ok else "STREAM-CONTRACT-FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
