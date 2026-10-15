#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本机引擎选路 + 降级判据（J9–J14）

验的是**浏览器里真的换引擎了**，而不是「我写了段代码看起来对」：

  J9  默认态：engine=webspeech，且**一条 /api/asr 请求都不许发**（零探测红线）
  J10 开启态：engine=local，且 /api/asr 真的被调用（引擎不是摆设）
  J11 本机返回的文本会进 pending 并最终提交给模型（链路闭环）
  J12 本机 503 → **当场回落 Web Speech**，且 inspect().fellBack=true、engine=webspeech
  J13 降级后界面如实改文案（不得让人以为还在用本机）
  J14 全程零 pageerror

音频是**桩**：注入合成 PCM（先 600ms 有声、再 600ms 静音）驱动切块。
真麦克风音质归人测，本套件只声明结构与选路，不谎称验过真实拾音。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # _test/（browser_engine 在那）
from browser_engine import launch  # noqa: E402  唯一 launch 实现（走 sync API）
from playwright.sync_api import sync_playwright  # noqa: E402  要 sync API，不是裸 playwright

BASE = "http://127.0.0.1:8123"

# 注入的桩：AudioContext + ScriptProcessor，可用 window.__feed(frames, rms) 驱动
STUB = r"""
window.__asrCalls = [];
window.__feedQueue = [];
(function () {
  const SR = 16000;
  function FakeBuffer(n, amp) {
    this.length = n; this.sampleRate = SR; this.numberOfChannels = 1;
    const d = new Float32Array(n);
    for (let i = 0; i < n; i++) d[i] = amp * Math.sin(i / 7);
    this.getChannelData = () => d;
  }
  class FakeScriptProcessor {
    constructor() { this.onaudioprocess = null; }
    connect() {} disconnect() {}
    fire(amp) {
      if (!this.onaudioprocess) return;
      const ev = { inputBuffer: new FakeBuffer(4096, amp), sampleRate: SR, playbackTime: 0 };
      this.onaudioprocess(ev);
    }
  }
  class FakeAudioContext {
    constructor() { this.sampleRate = SR; this.state = "running"; this.destination = {}; }
    createMediaStreamSource() { return { connect() {}, disconnect() {} }; }
    createScriptProcessor() { const p = new FakeScriptProcessor(); window.__proc = p; return p; }
    close() { this.state = "closed"; }
  }
  window.AudioContext = FakeAudioContext;
  window.__proc = null;
  // 麦克风桩：必须给，否则 asr-local 的 start() 判「不支持」→ 立刻 onerror →
  // voice-call 当场回落 Web Speech ⇒ 测到的 engine 永远是 webspeech，
  // 会误判成「开启态没切到本机引擎」（实测踩过：桩缺一条，结论完全反过来）。
  window.__gumCalls = [];
  try {
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: {
        getUserMedia: function (c) {
          window.__gumCalls.push(c);
          return Promise.resolve({ getTracks: function () { return [{ stop() {} }]; } });
        }
      }
    });
  } catch (e) { /* 只读环境：下面再看 */ }
  // 连续投喂 amp（0=静音，0.3=有声），n 帧
  window.__feed = (amp, n) => { for (let i = 0; i < n; i++) window.__proc && window.__proc.fire(amp); };
  // 原生 fetch 包一层，记下所有 /api/asr 请求
  const rf = window.fetch ? window.fetch.bind(window) : null;
  window.fetch = function (u, o) {
    const url = String(u && u.url ? u.url : u);
    if (/\/api\/asr/.test(url)) {
      window.__asrCalls.push(url);
      if (window.__asrFail) return Promise.resolve({ ok: false, json: () => Promise.resolve({ error: "asr-unavailable" }) });
      if (/\/status/.test(url)) return Promise.resolve({ ok: true, json: () => Promise.resolve({ ready: true, enabled: true }) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({
        text: window.__asrText || "我今天有点睡不着", engine: "qwen3-asr-0.6b",
        inferMs: 300, audioSeconds: 0.6, source: "local" }) });
    }
    return rf ? rf(u, o) : Promise.reject(new Error("no fetch"));
  };
  // 桩语音合成，避免真实发声
  window.speechSynthesis = { speak() {}, cancel() {}, getVoices: () => [], addEventListener() {} };
  window.SpeechSynthesisUtterance = function () {};
})();
"""


def main() -> int:
    with sync_playwright() as _pw:
        try:
            browser, face = launch(_pw, label="asr-switch")
        except Exception as e:                      # noqa: BLE001
            print(f"J-SWITCH-UNVERIFIED 浏览器起不来（{type(e).__name__}: {e}）—— 没测到不得判绿")
            return 2
        return run_legs(browser)


def run_legs(browser):
    npass = nfail = 0
    legs = {}

    def leg(key, name, cond, detail=""):
        nonlocal npass, nfail
        legs[key] = bool(cond)
        if cond:
            npass += 1
        else:
            nfail += 1
        print(f"{key} {'PASS' if cond else 'FAIL'}  {name}" + (f" ({detail})" if detail else ""))

    ctx = browser.new_context()
    ctx.add_init_script(STUB)
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))

    try:
        page.goto(BASE, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_function("() => window.VoiceCall && window.VoiceCall.supported && window.EmotionEngine",
                               timeout=30000)

        # ── J9 默认态：零探测 ────────────────────────────────────────────
        page.evaluate("() => { try { localStorage.removeItem('peiliao.asrlocal.v1'); } catch (e) {} }")
        page.reload(wait_until="domcontentloaded")
        page.wait_for_function("() => window.VoiceCall && window.VoiceCall.supported", timeout=30000)
        page.click("#btn-call")
        page.wait_for_function("() => window.VoiceCall.isCalling()", timeout=15000)
        page.wait_for_timeout(900)
        ins = page.evaluate("() => window.VoiceCall.inspect()")
        calls = page.evaluate("() => window.__asrCalls || []")
        leg("J9", "默认态 engine=webspeech", ins.get("engine") == "webspeech", str(ins.get("engine")))
        leg("J9", "默认态零 /api/asr 请求（红线）", len(calls) == 0, f"calls={len(calls)}")
        # ⚠ 必须用导出的 endCall()（不是 end —— 那是别的名字）。
        #   不结束通话的话第二阶段 startCall 会因 state!=="idle" 提前返回，
        #   rec 仍是上一阶段的识别器 ⇒ engine 读出来是 webspeech，会误判成
        #   「开启态没切到本机引擎」（实测踩过：判据自己的 bug，不是被审代码的 bug）。
        page.evaluate("() => window.VoiceCall.endCall()")
        page.wait_for_function("() => !window.VoiceCall.isCalling()", timeout=10000)
        page.wait_for_timeout(300)

        # ── J10/J11 开启态：真走本机 ──────────────────────────────────────
        page.evaluate("() => { try { localStorage.setItem('peiliao.asrlocal.v1', '1'); } catch (e) {} }")
        page.reload(wait_until="domcontentloaded")
        page.wait_for_function("() => window.VoiceCall && window.VoiceCall.supported", timeout=30000)
        page.evaluate("() => { window.__asrCalls = []; window.__asrText = '我今天有点睡不着'; }")
        # 探针：包一层 pickRecognizer + 记 buildRec 时序，看 startCall 那一刻选了什么
        page.evaluate("""() => {
            window.__trace = [];
            const U = window.VoiceCall._unit;
            const orig = U.pickRecognizer;
            window.__vcRec = null;
            window.VoiceCall._unit.pickRecognizer = function () {
                const r = orig.apply(this, arguments);
                window.__trace.push('pick->' + (r ? (r._engine || '?') : 'null')
                    + ' alts=' + (r ? r.maxAlternatives : '-')
                    + ' AsrLocal=' + (window.AsrLocal ? window.AsrLocal.isEnabled() : 'NA'));
                return r;
            };
        }""")
        page.click("#btn-call")
        page.wait_for_function("() => window.VoiceCall.isCalling()", timeout=15000)
        page.wait_for_timeout(600)
        ins = page.evaluate("() => window.VoiceCall.inspect()")
        diag = page.evaluate("""() => ({
            ls: (function(){ try { return localStorage.getItem('peiliao.asrlocal.v1'); } catch(e){ return 'ERR'; } })(),
            mod: !!window.AsrLocal,
            en: window.AsrLocal ? window.AsrLocal.isEnabled() : 'NA',
            pick: (function(){ try { const r = window.VoiceCall._unit.pickRecognizer(); return r ? (r._engine||'?') : 'null'; } catch(e){ return 'THROW:'+e; } })(),
            st: window.VoiceCall.inspect().state,
            alts: window.VoiceCall.inspect().alts,
            scripts: Array.from(document.scripts).map(s=>s.src).filter(u=>u.indexOf('asr-local')>=0)
        })""")
        print("       [DIAG]", json.dumps(diag, ensure_ascii=False))
        tr = page.evaluate("() => window.__trace || []")
        print("       [TRACE]", json.dumps(tr, ensure_ascii=False))
        leg("J10", "开启态 engine=local", ins.get("engine") == "local", str(ins.get("engine")))

        # 驱动音频：600ms 有声 + 600ms 静音 ⇒ 触发切块
        page.evaluate("() => { window.__feed(0.3, 24); window.__feed(0.0, 24); }")
        page.wait_for_timeout(1500)
        calls = page.evaluate("() => window.__asrCalls || []")
        # 前端打的是 /api/asr?dialect=…（Java 端点），/transcribe 是 Python 那一层的路径 ——
        # 拿 /transcribe 去筛前端请求会一条都数不到（实测踩过，是判据自己的错）。
        trans = [c for c in calls if "/api/asr" in c and "dialect=" in c]
        leg("J10", "/api/asr 真被调用（引擎不是摆设）", len(trans) >= 1, f"n={len(trans)}")
        leg("J10", "请求带 dialect 参数", bool(trans) and "dialect=" in trans[0], trans[0] if trans else "-")

        # pending 会被 shouldCommit(620ms) 清空，所以这条要么在提交前读、要么读整轮产物。
        # 这里读整轮（metric.user）才是稳定的证据，pending 只作辅助输出。
        page.evaluate("() => { window.__feed(0.3, 8); window.__feed(0.0, 8); }")
        page.wait_for_function("() => !!window.VoiceCall.inspect().metrics.user", timeout=20000)
        ins2 = page.evaluate("() => window.VoiceCall.inspect()")
        leg("J11", "本机文本进入整轮（user 非空且来自本机）",
            bool(ins2.get("metrics", {}).get("user")) and "睡不着" in ins2["metrics"]["user"],
            repr(ins2.get("metrics", {}).get("user")))

        # ── J12/J13 降级 ────────────────────────────────────────────────
        page.evaluate("() => { window.__asrFail = true; }")
        page.evaluate("() => { window.__feed(0.3, 20); window.__feed(0.0, 20); }")
        page.wait_for_timeout(2500)
        ins3 = page.evaluate("() => window.VoiceCall.inspect()")
        leg("J12", "本机 503 后 fellBack=true", ins3.get("fellBack") is True, str(ins3.get("fellBack")))
        leg("J12", "已回落 Web Speech（engine=webspeech）", ins3.get("engine") == "webspeech", str(ins3.get("engine")))
        pill = page.evaluate("() => { const p = document.querySelector('#call-state'); return p ? p.textContent : ''; }")
        leg("J13", "界面如实改文案（不得仍写「本机识别」）",
            "本机识别" not in (pill or ""), repr(pill))

        leg("J14", "全程零 pageerror", len(errors) == 0, "; ".join(errors[:2]))
    finally:
        try:
            browser.close()
        except Exception:
            pass

    print(f"\nJ-SWITCH: {npass} passed, {nfail} failed")
    ok = nfail == 0
    print("J-SWITCH-PASS" if ok else "J-SWITCH-FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())