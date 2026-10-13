#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""公网友号线「上游账户态」直读探针（r171）。

**为什么要单独一条**：2026-10-13 实测公网 `/api/chat` 回 **402 Insufficient Balance** ——
线上评委打开就是「离线共情模板」。这件事原本只在两处 41 秒/60 秒的浏览器判据里露出来
（`public_check` 的 `PUBLIC-ONLINE-FAIL`、`backup_online` 的 `B3 未过`），
而两处报出来的文字都像"页面/链路坏了"，真因（账户没钱）要人点开 console 才看得见。
本件只做一件事：**一次 POST，按 HTTP 状态码判档**，30 秒内给出一条人能抄进台账的读数。

词汇单源：判档函数直接 `import classify` 自 `_test/backup_online_check.py`，
本件不另立一套状态码到档位的映射（同一事实两处判 ⇒ 迟早分叉，本仓 r70/r101 都栽过）。

五档与处置（词汇单源＝`backup_online_check.classify`）：
  OK            2xx 且响应体带 choices        ⇒ 在线可用
  BILLING       402 / 429                     ⇒ **外部账户态**，只有充值或换 Key 能修；不记产品红
  EDGE-POLICY   CF `error code: 1010/1014/1015/1016/1020` ⇒ **本机 IP 被边缘策略拦** ⇒ 这一面在本地不可判
  UPSTREAM-5XX  5xx                           ⇒ 上游服务侧故障，非本仓代码
  UNKNOWN/LINK  其余形状错或 console 报链路错  ⇒ 这才归本仓查（rc=1）

⚠️ 本件**不打本地实例**（本地 fat jar 无 Key ⇒ 恒回 `no-key`，那是配置不是缺陷）。
默认只打公网主推线与备用线共用的那个函数地址；离线环境/无网 ⇒ rc=2 未验，不判红也不判绿。

退出码：0=UPSTREAM-STATE-OK 1=LINK 类缺陷 2=BILLING/5XX/取不到（未验或外部依赖，不是产品红）
"""
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from backup_online_check import classify, PROXY   # 判档词汇单源，不在这里重写

ENDPOINT = PROXY
BODY = json.dumps({"messages": [{"role": "user", "content": "在吗"}],
                   "max_tokens": 4, "temperature": 0.3}).encode("utf-8")
TIMEOUT = 25


def probe(url=ENDPOINT, timeout=TIMEOUT):
    """打一次线上函数：返回 (status, body_snippet, transport_err)。状态取 HTTP 码，不猜文案。"""
    req = urllib.request.Request(url, data=BODY, method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()[:400].decode("utf-8", "replace")
            return r.status, raw, None
    except urllib.error.HTTPError as e:
        return e.code, (e.read() or b"")[:400].decode("utf-8", "replace"), None
    except Exception as exc:
        return 0, "", "%s: %s" % (type(exc).__name__, str(exc)[:90])


def grade_of(status, body):
    """把「响应体是否真是 choices」折成标签后，连同响应体一起交给 classify。
    本件**不自己判档** —— 词汇唯一在 `backup_online_check.classify`。"""
    looks_ok = '"choices"' in (body or "")
    tag = "在线大模型生成" if (status and 200 <= status < 300 and looks_ok) else ""
    return classify(status, tag, [], body)


def run() -> int:
    status, body, terr = probe()
    if terr:
        print("UPSTREAM-STATE-UNVERIFIED: 打不到 %s（%s）⇒ 网络层未通，不判红也不判绿"
              % (ENDPOINT, terr))
        return 2
    grade, why = grade_of(status, body)
    snippet = (body or "").replace("\n", " ")[:90]
    if grade == "OK":
        print("UPSTREAM-STATE-OK: HTTP %s｜在线链路可用（%s）" % (status, why))
        return 0
    if grade == "BILLING":
        print("UPSTREAM-STATE-UNVERIFIED: %s｜响应体片段=%r" % (why, snippet))
        print("   这是**外部账户态**，不是本仓代码缺陷，也不是环境未验：评委此刻打开线上会落"
              "「离线共情模板」。处置只有充值或换 Key（须老大）；复算：python _test/upstream_state_probe.py")
        print("   ⚠️ 禁止为让这条读数转绿去放宽 `public_check`/`backup_online` 的 B3 ——"
              " 那等于把「线上当前拿不到在线回复」这条事实从账面上抹掉。")
        return 2
    if grade == "EDGE-POLICY":
        print("UPSTREAM-STATE-UNVERIFIED: %s｜HTTP %s 片段=%r" % (why, status, snippet))
        print("   取证口径：**本机 IP 被边缘策略拦截 ≠ 线上不可用**。浏览器判据（带完整头/cookie）"
              "走的是同一条链，其读数才是线上态；本件只在能直连时给结论。")
        print("   复算（带外，换网络或让浏览器判据来跑）：python _test/public_check.py")
        return 2
    if grade == "UPSTREAM-5XX":
        print("UPSTREAM-STATE-UNVERIFIED: %s｜片段=%r ⇒ 上游服务侧故障，非本仓代码" % (why, snippet))
        return 2
    print("UPSTREAM-STATE-FAIL: %s｜片段=%r ⇒ 响应形状不符（无 choices 又不是计费/边缘策略/5XX），归本仓查"
          % (why, snippet))
    return 1


def selftest() -> int:
    """判档必须有牙：各档喂专属输入，且反向腿防「恒判 OK」「恒判未验」「把计费洗成未验」。"""
    bad = []
    cases = [(200, '{"choices":[{"message":{"content":"我在"}}]}', "OK"),
             (402, '{"error":{"message":"Insufficient Balance"}}', "BILLING"),
             (429, "", "BILLING"),
             (503, "<html>bad gateway</html>", "UPSTREAM-5XX"),
             (403, "error code: 1010", "EDGE-POLICY"),
             (200, "error code: 1015", "EDGE-POLICY"),
             (404, "not found", "UNKNOWN"),
             (0, "", "UNKNOWN")]
    for st, body, want in cases:
        got, why = grade_of(st, body)
        if got != want:
            bad.append("HTTP %s → %s（应 %s）%s" % (st, got, want, why[:40]))
    # 反向腿①：全 200 且带 choices 必须 OK —— 防「恒判未验」把真可用报成不可用
    if grade_of(200, '{"choices":[]}')[0] != "OK":
        bad.append("反向腿①失效：可用样本没判成 OK")
    # 反向腿②：402 绝不能判成 OK —— 防「恒判绿」，那正是本件要防的事的反面
    if grade_of(402, '{"choices":[{"message":{"content":"我在"}}]}')[0] == "OK":
        bad.append("反向腿②失效：402 被判成可用（假绿）")
    # 反向腿③：200 但没有 choices（函数坏了/返回空体）不得判 OK
    if grade_of(200, '{"error":"no-key"}')[0] == "OK":
        bad.append("反向腿③失效：无 choices 的 200 被判成可用")
    # 反向腿④（关键）：CF 品牌的**计费页**必须仍是 BILLING —— 若按"响应里出现 cloudflare 字样"
    # 判边缘策略，就会把「账户没钱」悄悄降级成「本机不可判」，那是把真红洗成未验（比假红更坏）
    if grade_of(402, "Cloudflare Page: {\"error\":\"Insufficient Balance\"}")[0] != "BILLING":
        bad.append("反向腿④失效：CF 品牌的 402 被降级成未验 ⇒ 计费事实被抹")
    print("UPSTREAM-STATE-SELFTEST-%s（%d 档判位 + 4 条反向腿；判档词汇与 backup_online 同源）"
          % ("PASS" if not bad else "FAIL: " + "; ".join(bad), len(cases)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(selftest() if "--selftest" in sys.argv else run())
