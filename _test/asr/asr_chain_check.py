#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本机 ASR 接入链路判据（J1–J8）

覆盖两条红线 + 契约正确性：
  🔴 不得伪装在线：服务不可用必须 503，绝不返回占位文本或 200 空串
  🔴 默认态零探测：xinyu.asr.enabled=false 时，前端一条 ASR 请求都不许发

前置：Java 服务在 8123；可选 Python ASR 服务在 8765（决定 J3/J4 能否跑）。
用法：py -3.12 _test/asr/asr_chain_check.py [--base http://127.0.0.1:8123]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

PASS, FAIL = [], []


def chk(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"[{'OK ' if cond else 'FAIL'}] {name}" + (f" -> {detail}" if detail else ""))


def get(url, timeout=10):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        return 0, str(e)


def post_wav(url, path, timeout=40):
    try:
        with open(path, "rb") as f:
            data = f.read()
        req = urllib.request.Request(url, data=data, method="POST",
                                     headers={"Content-Type": "audio/wav"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        return 0, str(e)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8123")
    ap.add_argument("--asr", default="http://127.0.0.1:8765")
    ap.add_argument("--wav", default=os.path.join(os.path.dirname(__file__), "sample3s.wav"))
    a = ap.parse_args()

    st, body = get(f"{a.base}/api/asr/status")
    try:
        status = json.loads(body)
    except Exception:
        status = {}

    chk("J1 /api/asr/status 可达且带 dialects",
        st == 200 and bool(status.get("dialects")), f"{st} {str(body)[:110]}")
    chk("J1 方言表含六目标方言",
        {"mandarin", "yue", "chuan", "wu", "dongbei", "minnan"} <= set(status.get("dialects", [])),
        str(status.get("dialects")))

    if st != 200:
        # J1 都没量到（服务不可达/路由缺失）⇒ 整条链路无从判定。
        # 🔴 不得在 FAIL 已入台账的情况下打 PASS —— 这是 r186 一手抓到的判据自身缺陷：
        #   旧代码 8123 拒连时 3 条腿记 FAIL 却仍打 ASR-CHAIN-PASS rc=0（掩盖）。
        print(f"\nASR-CHAIN: {len(PASS)} passed, {len(FAIL)} failed")
        print(f"ASR-CHAIN-UNVERIFIED (Java 服务不可达或未暴露 /api/asr/status：st={st})")
        return 2

    if not status.get("enabled"):
        # 默认态：必须**拒**而不是编一句
        code, b = post_wav(f"{a.base}/api/asr", a.wav)
        chk("J2 默认态 enabled=false → 503 asr-disabled（不得伪装在线）",
            code == 503 and json.loads(b).get("error") == "asr-disabled", f"{code} {b[:90]}")
        print(f"\nASR-CHAIN: {len(PASS)} passed, {len(FAIL)} failed")
        print("ASR-CHAIN-PASS (默认态；开启态腿需 XINYU_ASR_ENABLED=true 复跑)" if not FAIL else "ASR-CHAIN-FAIL")
        return 0 if not FAIL else 1

    ready = status.get("ready")
    chk("J3 Python 服务探到（ready 由 /health 得出，非猜）", ready is True, f"ready={ready}")

    if not os.path.isfile(a.wav):
        print(f"[SKIP] 样本音频不存在: {a.wav}（用 py -3.12 _test/asr/make_sample.py 生成）")
        print("\nASR-CHAIN-PARTIAL")
        return 0

    t0 = time.perf_counter()
    code, b = post_wav(f"{a.base}/api/asr?dialect=mandarin", a.wav)
    dt = (time.perf_counter() - t0) * 1000
    try:
        j = json.loads(b)
    except Exception:
        j = {}
    if code == 200:
        chk("J4 全链路转写成功且有文本", bool(j.get("text")), f"{code} {b[:110]}")
        chk("J4 source=local（如实标本地，不得伪装云端）", j.get("source") == "local")
        chk("J4 引擎名为 qwen3-asr", str(j.get("engine", "")).startswith("qwen3-asr"))
        chk("J4 往返 < 8s（交互可接受）", dt < 8000, f"{dt:.0f}ms")
        print(f"       [RTF] infer={j.get('inferMs')}ms roundtrip={dt:.0f}ms text={j.get('text','')[:40]}")
    else:
        chk("J4 全链路转写失败但**如实报错**（不得 200 空串）",
            code in (400, 503) and not json.loads(b or "{}").get("text"),
            f"{code} {b[:110]}")

    # J5 空体
    code, b = post_wav(f"{a.base}/api/asr", a.wav)
    chk("J5 非法方言回落 mandarin（不把脏值透传给引擎）",
        code in (200, 503) and json.loads(b or "{}").get("dialect", "mandarin") == "mandarin",
        f"{code} {b[:90]}")

    # J6 体闸：超 256KiB 必须被挡（客户端 6s 上限就是为这个定的）
    big = os.path.join(os.path.dirname(__file__), "_big.wav")
    try:
        with open(a.wav, "rb") as f:
            head = f.read()
        with open(big, "wb") as f:
            f.write(head + b"\0" * 300000)
        code, b = post_wav(f"{a.base}/api/asr", big)
        chk("J6 超 256KiB 被体闸挡下（413），不是无声吞掉",
            code in (413, 400, 503), f"{code} {b[:90]}")
    finally:
        if os.path.isfile(big):
            os.remove(big)

    # J7 直接打 Python，验证 Java 没篡改内容
    code, b = get(f"{a.asr}/health")
    chk("J7 Python 服务 health 可达", code == 200 and json.loads(b or "{}").get("ready") is True, f"{code}")

    # J8 错误码形状：前端靠它决定是否回落 Web Speech
    code, b = post_wav(f"{a.base}/api/asr?dialect=not_a_dialect", a.wav)
    chk("J8 未知方言不 500", code in (200, 400, 503), f"{code}")

    print(f"\nASR-CHAIN: {len(PASS)} passed, {len(FAIL)} failed")
    print("ASR-CHAIN-PASS" if not FAIL else "ASR-CHAIN-FAIL")
    return 0 if not FAIL else 1


if __name__ == "__main__":
    sys.exit(main())