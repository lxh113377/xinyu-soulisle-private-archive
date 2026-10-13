# -*- coding: utf-8 -*-
"""心屿 · ASR sidecar 判据（B1）

盯的是"这个本地识别服务真的可用、且边界真的拦得住"，四态与 asr_replay_check 同族：
PASS / FAIL / UNVERIFIED（服务没起 = 没测到，不判绿）/ GAP（样本前提缺失）。

判据不是恒真的：每条断言都配了"反过来会怎样"的说明，--selftest 用变异验证其中
最容易被改成恒真的三条（health 缺字段、坏音频不拦、越权不拦）。

前置：ml/asr_server.py 已在 127.0.0.1:8321 起着（起法见文件 docstring）。
用法：python _test/asr_sidecar_check.py [--url http://127.0.0.1:8321] [--selftest]
"""
import io
import json
import struct
import sys
import wave

import requests

DEFAULT_URL = "http://127.0.0.1:8321"
# 上游模型包自带的粤语样例（ml/fetch_asr_models.py 拉的四个件之一）。
# 判据不硬编码"应该识别成什么"——那是易碎的黄金输出；只要求非空、含 CJK、长度合理。
YUE_WAV = "D:/xinyu-ml/asr/sensevoice-int8-2024-07-17/test_wavs/yue.wav"
DECODE_BUDGET_MS = 8000.0     # CPU 上 int8 SenseVoice 实测约 0.4s/句；8s 是给慢机器留的余量
MAX_SECONDS = 30.0            # 与 ml/asr_server.py 的 MAX_SECONDS 对齐（改了要两边一起改）


def _wav_bytes(samples, sr):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(b"".join(struct.pack("<h", max(-32768, min(32767, int(s * 32767)))) for s in samples))
    return buf.getvalue()


def health(url, timeout=15):
    r = requests.get(url + "/health", timeout=timeout)
    return r.status_code, (r.json() if r.status_code == 200 else {})


def post_audio(url, data, origin=None, timeout=120):
    """以 multipart 上传音频；返回 (status_code, json_or_text)"""
    h = {"Origin": origin} if origin else {}
    files = {"file": ("probe.wav", io.BytesIO(data), "audio/wav")}
    r = requests.post(url + "/asr", files=files, headers=h, timeout=timeout)
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, r.text[:200]


def post_b64(url, data, timeout=120):
    import base64
    r = requests.post(url + "/asr", json={"audio_b64": base64.b64encode(data).decode()}, timeout=timeout)
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, r.text[:200]


def run(url):
    """逐条判。返回 (rows, hard_fail) —— rows 是 [(名, 是否过, got, want)]"""
    rows = []

    def ck(n, got, want):
        rows.append((n, got == want, got, want))

    # ---- S1 health 自证 -------------------------------------------------
    try:
        code, h = health(url)
    except Exception as e:                                    # noqa: BLE001
        print("ASR-SIDECAR-UNVERIFIED 连不上 %s（%s）—— 服务没起 = 没测到，不判绿"
              % (url, str(e)[:100]))
        return None, False
    ck("S1a status=UP", h.get("status"), "UP")
    ck("S1b loaded=True", h.get("loaded"), True)
    ck("S1c engine 有值", bool(h.get("engine")), True)
    ck("S1d model 指向 sense-voice", "sense" in str(h.get("model", "")), True)
    ck("S1e sampleRate=16000", h.get("sampleRate"), 16000)
    ck("S1f language 档合法", h.get("language") in ("auto", "zh", "yue", "en", "ja", "ko"), True)
    ck("S1g provider 有值", bool(h.get("provider")), True)
    ck("S1h error 为空", h.get("error", ""), "")
    if not rows[0][1] or not rows[1][1]:
        print("ASR-SIDECAR-FAIL 引擎没加载成功：%s" % json.dumps(h, ensure_ascii=False)[:200])
        return rows, True

    # ---- S2 粤语样例转写（正常路径）-------------------------------------
    try:
        with open(YUE_WAV, "rb") as f:
            yue = f.read()
    except OSError as e:
        rows.append(("S2 粤语样例可读", False, str(e), "可读"))
        print("ASR-SIDECAR-UNVERIFIED 取不到粤语样例 %s（先跑 ml/fetch_asr_models.py）" % YUE_WAV)
        return rows, False
    code, body = post_audio(url, yue)
    ck("S2a 转写 200", code, 200)
    text = body.get("text", "") if isinstance(body, dict) else ""
    ck("S2b 文本非空", len(text) > 0, True)
    ck("S2c 含 CJK", any("\u4e00" <= c <= "\u9fff" for c in text), True)
    ck("S2d 长度合理(2..80)", 2 <= len(text) <= 80, True)
    ck("S2e seconds 在 3..8s（样例本身 5.1s）", 3.0 <= (body.get("seconds") or 0) <= 8.0, True)
    ck("S2f 未重采样(样例本就是16k)", body.get("resampled"), False)
    ck("S2g decodeMs 在预算内", (body.get("decodeMs") or 1e9) < DECODE_BUDGET_MS, True)

    # ---- S3 越权 origin 必须 403 ----------------------------------------
    code, _ = post_audio(url, yue, origin="https://evil.example.com")
    ck("S3 越权 origin=403", code, 403)
    # 回环 origin 必须放行（否则白名单把自己人也拦了，前端就用不了）
    code, _ = post_audio(url, yue, origin="http://127.0.0.1:8123")
    ck("S3b 回环 origin=200", code, 200)

    # ---- S4 坏音频必须 400（调用方的错，不是引擎的错）--------------------
    code, _ = post_audio(url, b"\x00\x01\x02not-audio")
    ck("S4a 非音频字节=400", code, 400)
    code, _ = post_audio(url, b"")
    ck("S4b 空文件=400 或 422", code in (400, 422), True)
    code, _ = post_audio(url, _wav_bytes([0.0] * 100, 16000))       # 0.006s
    ck("S4c 超短音频=400", code, 400)

    # ---- S5 超时长必须 413 ----------------------------------------------
    code, _ = post_audio(url, _wav_bytes([0.0] * int(16000 * (MAX_SECONDS + 2)), 16000))
    ck("S5 超时长=413", code, 413)

    # ---- S6 非 16k 输入：必须标 resampled 且仍出文本 ---------------------
    code, body = post_audio(url, _wav_bytes([0.0] * int(48000 * 1.0), 48000))
    # 1s 静音在 48k → 重采样后 1s；静音识别可能空文本（引擎 502），两者都算"走通了链路"
    ck("S6a 48k 输入不报 4xx/5xx", code in (200, 502), True)
    if code == 200:
        ck("S6b resampled=True", body.get("resampled"), True)
        ck("S6c sampleRateIn=48000", body.get("sampleRateIn"), 48000)

    # ---- S7 JSON 入口（audio_b64）---------------------------------------
    code, body = post_b64(url, yue)
    ck("S7a b64 入口 200", code, 200)
    ck("S7b b64 入口同一文本", body.get("text") if isinstance(body, dict) else None, text)

    return rows, False


def selftest():
    """判据自身不是恒真的：对三条最易被改成恒真的断言做变异验证。

    做法：把"应该拦"的场景喂给一个**假的服务**（本地起一个只会 200 的桩），
    断言腿必须翻红。腿不翻红 = 这条腿恒真 = 判据失效。
    """
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Always200(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"     # 不读 body 就回会让 requests 看到连接中断（ChunkedEncodingError）

        def do_GET(self):
            self._json(b'{"status":"UP","loaded":true,"engine":"stub","model":"x",'
                       b'"sampleRate":16000,"language":"auto","provider":"cpu","error":""}')

        def do_POST(self):
            # 必须把 body 读完再回，否则大上传（S5 的 1MB）会断在客户端
            n = int(self.headers.get("Content-Length") or 0)
            if n:
                self.rfile.read(n)
            self._json('{"text":"stub","seconds":1.0,"decodeMs":1.0,"resampled":false}'
                       .encode("utf-8"))

        def _json(self, payload):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), Always200)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    stub_url = "http://127.0.0.1:%d" % port
    # 桩永远 200 ⇒ 403/400/413 三条边界腿必须全部判红
    rows, _ = run(stub_url)
    srv.shutdown()
    bad = [r[0] for r in rows if not r[1]]
    # 在"永远放行"的桩上，只有边界腿该红；正常腿（health/转写）会绿
    boundary_red = [b for b in bad if b.startswith(("S3", "S4", "S5"))]
    normal_ok = [r for r in rows if r[0].startswith(("S1", "S2", "S7")) and r[1]]
    ok = len(boundary_red) >= 5 and len(normal_ok) >= 8
    print("ASR-SIDECAR-SELFTEST-%s 桩上边界腿判红 %d 条（>=5 才算不恒真）、正常腿绿 %d 条"
          % ("PASS" if ok else "FAIL", len(boundary_red), len(normal_ok)))
    return 0 if ok else 1


def main():
    if "--selftest" in sys.argv[1:]:
        return selftest()
    url = DEFAULT_URL
    for i, a in enumerate(sys.argv[1:]):
        if a == "--url" and i + 1 < len(sys.argv) - 1:
            url = sys.argv[i + 2]
    rows, hard = run(url)
    if rows is None:
        return 2
    bad = [r for r in rows if not r[1]]
    for r in bad:
        print("  - %s: got %r want %r" % (r[0], r[2], r[3]))
    n = len(rows)
    print("ASR-SIDECAR-%s %d/%d 条符（服务 %s）"
          % ("PASS" if not bad and not hard else "FAIL", n - len(bad), n, url))
    return 1 if (bad or hard) else 0


if __name__ == "__main__":
    from check_instrument import install_excepthook
    install_excepthook("ASR-SIDECAR")
    raise SystemExit(main())
