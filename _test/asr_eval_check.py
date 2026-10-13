# -*- coding: utf-8 -*-
"""心屿 · 粤语 ASR 评测判据（B3）

把「跑一遍评测集」变成可回滚的二元判据：**引擎坏了必须判红，而不是只留下一行读数**。

门禁口径（为什么卡繁简归一而不是严格 CER）：
  · 严格 CER 里含着 **23 个百分点的繁简书写差异**（CV 的参考文本是繁体、SenseVoice 输出简体）。
    那不是识别错误，卡它等于卡"引擎必须用繁体回答"，会把优化引向错误方向。
  · 粤字归一只隔离了 0.5 个百分点（係→系 这类在 CV 粤语文本里占比很小）。
  · ⇒ 卡 **cer_simp（繁简归一）**，它最接近"到底听没听对"。
  当前实测（300 条）：auto 档 11.02% / yue 档 10.82%。门限取 0.25：给改进留空间，
  也保证"引擎明显退化"（如 >25%）一定被抓到。改门限要连这段理由一起改。

用法：python _test/asr_eval_check.py [--limit 40] [--url ...] [--selftest]
  服务没起 ⇒ rc=2 UNVERIFIED（没测到不判绿，与 asr_sidecar_check 同族）
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

GATE_CER_SIMP = 0.25
GATE_SER_SIMP = 0.95          # SER 是"整句全对率"，粤语口语里同音字多，95% 已很松
BASELINE = os.path.join(HERE, "asr_eval_baseline.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--url", default="http://127.0.0.1:8321")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        # 判据自身不恒真，验两条：
        #   ① 服务不可达 ⇒ 必须 UNVERIFIED(rc=2)，不能是 PASS（否则"没测到"被当成"通过"）
        #   ② 门限被改成不可能达到的值 ⇒ 必须 FAIL(rc=1)，不能是 PASS（否则门限是装饰）
        import subprocess
        me = os.path.abspath(__file__)
        r1 = subprocess.run([sys.executable, me, "--url", "http://127.0.0.1:1", "--limit", "1"],
                            capture_output=True, text=True, timeout=180)
        ok1 = r1.returncode == 2 and "ASR-EVAL-UNVERIFIED" in (r1.stdout + r1.stderr)
        # ② 用一个指向"永远返回空文本"的桩：CER 会爆 ⇒ 必须 FAIL
        import threading
        from http.server import BaseHTTPRequestHandler, HTTPServer

        class EmptyText(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_POST(self):
                n = int(self.headers.get("Content-Length") or 0)
                if n:
                    self.rfile.read(n)
                body = b'{"text":"","seconds":1.0,"decodeMs":1.0}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass

        srv = HTTPServer(("127.0.0.1", 0), EmptyText)
        port = srv.server_address[1]
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        r2 = subprocess.run([sys.executable, me, "--url", "http://127.0.0.1:%d" % port,
                             "--limit", "3"], capture_output=True, text=True, timeout=180)
        srv.shutdown()
        ok2 = r2.returncode == 1 and "ASR-EVAL-FAIL" in (r2.stdout + r2.stderr)
        print("ASR-EVAL-SELFTEST-%s ①不可达→UNVERIFIED:%s ②空文本→FAIL:%s"
              % ("PASS" if (ok1 and ok2) else "FAIL", ok1, ok2))
        return 0 if (ok1 and ok2) else 1

    if not os.path.isfile(os.path.join(HERE, "asr_eval_manifest.jsonl")):
        print("ASR-EVAL-UNVERIFIED 评测清单缺失（先跑 ml/build_asr_eval_set.py）")
        return 2

    import asr_cantonese_eval as ev
    sys.argv = ["asr_cantonese_eval.py", "--limit", str(args.limit), "--url", args.url,
                "--save", os.path.join(HERE, "_eval_last.json")]
    try:
        rc = ev.main()
    except SystemExit as e:
        rc = e.code
    if rc == 2:
        return 2
    if rc not in (0, 1):
        print("ASR-EVAL-UNVERIFIED 评测器异常退出 rc=%s" % rc)
        return 2

    last = json.load(open(os.path.join(HERE, "_eval_last.json"), encoding="utf-8"))
    cer_s = last["cer_simp"]
    ser_s = last["ser_simp"]
    ok = cer_s <= GATE_CER_SIMP and ser_s <= GATE_SER_SIMP
    print("ASR-EVAL-%s n=%d 繁简归一CER=%.2f%%(门限%.0f%%) SER=%.2f%%(门限%.0f%%)"
          % ("PASS" if ok else "FAIL", last["n"], cer_s * 100, GATE_CER_SIMP * 100,
             ser_s * 100, GATE_SER_SIMP * 100))

    # 与入库基线对比（有基线才比；没有就只报本次读数，不算失败）
    if os.path.isfile(BASELINE):
        base = json.load(open(BASELINE, encoding="utf-8"))
        d = (cer_s - base["cer_simp"]) * 100
        print("  对比入库基线(n=%d)：繁简归一CER %+.2f 个百分点" % (base["n"], d))
        if d > 5.0:
            print("  ⚠ 比入库基线差 5 个百分点以上 —— 排查是引擎退化还是口径变化")
    return 0 if ok else 1


if __name__ == "__main__":
    from check_instrument import install_excepthook
    install_excepthook("ASR-EVAL")
    raise SystemExit(main())
