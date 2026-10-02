# -*- coding: utf-8 -*-
"""J2 契约验收：`POST /api/chat` 与 v1 1:1，前端**零代码改动**（只改 localStorage 的 proxy 指向）即可切到 Spring Boot。

用法：先起 Java 服务端在 8123（工作目录=项目根）：
  $env:JAVA_HOME='C:\\Program Files\\Eclipse Adoptium\\jdk-17.0.20.101-hotspot'
  $env:DEEPSEEK_KEY='<key>'
  java -jar server\\target\\soulisle-server.jar --server.port=8123
再跑：python _test/j2_chat_contract.py

判据两条（含对照，避免恒真）：
  A 生效路径：proxy=/api/chat      → 气泡必须出现「在线大模型生成」（mode=model）
  B 对照组  ：proxy=不可达端点     → 必须回落「离线共情模板」，且**不得**出现「在线大模型生成」

r93 修**假绿**（本轮一手实测）：本脚本原本结尾只 `print`，**没有 sys.exit** ⇒ 无论
FAIL-A/FAIL-B2 命中与否，进程都 exit 0，电池把它记成 PASS（实测 2026-10-02：
A 腿已红「LLM 精判失败 → 词典兜底」，印出 `J2-CONTRACT-FAIL`，电池那行仍是 `rc=0`）。
「状态与事实相反」是判据最坏的一种坏法：不是漏报，是**主动报绿**。
现补：① 判红 ⇒ rc=1；② `errors` 非空也判红（原本只打印 JS_ERRORS 计数，从不参与判定）。
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8123/index.html"
TEXT = "今天被导师批评了，心情很低落"
errors = []


def run(browser, proxy):
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(BASE, wait_until="networkidle")
    # 关键：cfg 必须同时带 base+key，否则 demo-config.js 会判定「未配置」并用硬编码 Key 覆盖，
    # 对话就走了浏览器直连，proxy 根本没生效（实测踩过：A/B 两组都"在线"，判据恒真）。
    # 这里把直连凭据设成**无效值**，两组唯一差异只有 proxy ⇒ 单变量对照：
    #   A 在线 ⇒ 只可能来自 Java /api/chat；B 离线 ⇒ 证明判据非恒真。
    page.evaluate("""(proxy) => {
      localStorage.setItem('peiliao.cfg.v1', JSON.stringify({
        proxy,
        base: 'http://127.0.0.1:18123/v1', key: 'invalid-key-for-test', model: 'x'
      }));
      localStorage.removeItem('peiliao.emotions.v1');
      localStorage.removeItem('peiliao.history.v1');
    }""", proxy)
    page.reload(wait_until="networkidle")
    page.wait_for_timeout(600)
    online = page.evaluate("() => window.ChatAgent.isOnline()")
    page.fill("#chat-input", TEXT)
    page.click("#chat-form button[type=submit]")
    page.wait_for_timeout(10000)
    msgs = page.eval_on_selector_all(".msg.ai", "els => els.map(e => e.textContent)")
    page.close()
    return online, (msgs[-1] if msgs else "")


def main():
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception:
            browser = p.chromium.launch(channel="msedge")
        a_online, a_last = run(browser, "/api/chat")
        b_online, b_last = run(browser, "http://127.0.0.1:18123/api/chat")
        browser.close()

    print("A_ONLINE:", a_online)
    print("A_LAST  :", a_last[:220])
    print("B_ONLINE:", b_online)
    print("B_LAST  :", b_last[:220])

    ok = True
    if "在线大模型生成" not in a_last:
        print("FAIL-A: 走 Java /api/chat 应命中在线大模型（mode=model）")
        ok = False
    if "在线大模型生成" in b_last:
        print("FAIL-B: 对照组不可达端点不应命中在线 → 判据恒真")
        ok = False
    if "离线共情模板" not in b_last:
        print("FAIL-B2: 对照组应回落离线模板")
        ok = False
    print("JS_ERRORS:", len(errors))
    if errors:
        print("FAIL-C: 契约路径上出现 JS 报错 %d 条：%s" % (len(errors), errors[:3]))
        ok = False
    print("J2-CONTRACT-PASS" if ok else "J2-CONTRACT-FAIL")
    # r93：判据必须有真退出码（详见文件头「假绿」段）。裸跑完就是 exit 0 ⇒ 判红也报绿。
    return 0 if ok else 1


# r93：入口必须带 __main__ 守卫——`repo_config_check` G9 判「import 即执行」为违规。
# 本轮第一次补退出码时写成顶层 `sys.exit(...)`，当场被 G9 抓红（89 脚本扫出
# 「第 86 行顶层入口调用且无 __main__ 守卫」）。门禁自己抓住了新引入的回归，这正是它存在的意义。
if __name__ == "__main__":
    sys.exit(main())
