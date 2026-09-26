# -*- coding: utf-8 -*-
"""被测服务前置探针（对标轮 r35 新增）—— 把"服务没起"与"代码有缺陷"分开报。

为什么要有它（r35 一手实测）：本机 jar 在跑判据的中途掉了，电池一次报出 5 条红
（api_contract / settings_panel / settings_panel_selftest / offline_shell / ci_status），
每条的失败面都不一样（Playwright 的 `net::ERR_CONNECTION_REFUSED`、urllib 的 `WinError 10061`、
以及"降级链路本该绿"的误读）—— 归因花了三轮命令才定到"8123 没人监听"这一件事上。
一条前置探针就能把这句话放在收口行里说清。

判据：
  P1 探 `GET /api/health` 期望 200 且 `status=UP` ⇒ PASS（rc=0）
  P2 连不上 / 非 200 / 取不到 JSON ⇒ **rc=2（环境未验）**，明写"不得把这些红读成代码缺陷"
     为什么是 2 不是 1：与本项目 rc 约定一致（1=判红、2=环境），使聚合器收口行落在
     `ENV-UNVERIFIED` 而不是 `RED(判红)` —— 崩溃与判红与环境三分，是本轮的自有不变量。

用法：python _test/server_preflight.py [URL]   默认 http://127.0.0.1:8123
"""
import json
import sys
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

BASE = next((a for a in sys.argv[1:] if not a.startswith("--")), "http://127.0.0.1:8123")


def main() -> int:
    url = BASE.rstrip("/") + "/api/health"
    try:
        with urllib.request.urlopen(url, timeout=8) as resp:
            code = resp.getcode()
            body = resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, OSError) as err:
        print("PREFLIGHT-ENV: 被测服务不可达 %s（%s）" % (url, type(err).__name__))
        print("  ⇒ 依赖它的套件（api_contract / settings_panel / offline_shell / browser_check / j2 / j4 …）")
        print("    本轮全部算**未验**，不得把这些红读成代码缺陷。修法：先把 fat jar 起在 8123")
        print("    （工作目录=项目根；`java -jar server/target/soulisle-server.jar --server.port=8123`）")
        return 2
    if code != 200:
        print("PREFLIGHT-ENV: %s 返回 http=%s（期望 200）" % (url, code))
        return 2
    try:
        data = json.loads(body)
    except ValueError:
        print("PREFLIGHT-ENV: /api/health 不是合法 JSON（前 80 字符：%s）" % body[:80])
        return 2
    if data.get("status") != "UP" or not data.get("indexFound"):
        print("PREFLIGHT-FAIL: status=%s indexFound=%s webRoot=%s ⇒ 服务在但不自证源命中"
              % (data.get("status"), data.get("indexFound"), data.get("webRoot")))
        return 1
    print("PREFLIGHT-PASS: %s status=UP webRoot=%s（前端与 vendor 均命中）"
          % (url, data.get("webRoot")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
