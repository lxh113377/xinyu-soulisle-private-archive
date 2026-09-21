# -*- coding: utf-8 -*-
"""J4 熔断对照：服务端**没有** `/api/memory` 时，远端记忆必须"试一次就闭嘴"。

## 为什么需要这个对照组
`memory-store.js` 的承诺是：「远端不可用时熔断，本地存储照常，**且不制造持续网络噪音**」。
没有对照组就无法区分「熔断生效」与「碰巧只有一次请求」——
这类"机制存在但没接线"的假通过在本项目已复现多次（R238）。

## 做法（自包含，不依赖 Java 服务端）
用 `python -m http.server 8124 --directory src` 提供页面 ——
它只发静态文件，`/api/memory/**` 必然 404，正好模拟"公网版只有 /api/chat"的形态。

## 判据
  A 熔断生效：`/api/memory` 相关请求总数 ≤ 2（不是每说一句都重试）
  B 降级可用：`localStorage` 里仍写入情绪记录（本地存储没被远端逻辑破坏）
  C 提示干净：console 错误（排除脚本自注入的 18123 连接拒绝）**不超过 1 条**
"""
import io
import subprocess
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PORT = 8124
PAGE = f"http://127.0.0.1:{PORT}/index.html"
TEXT = "今天被导师批评了，心情很低落"


def main():
    server = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(PORT), "--directory", str(ROOT / "src")],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        time.sleep(2.5)
        mem_requests, console_errors = [], []
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch()
            except Exception:
                browser = p.chromium.launch(channel="msedge")
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.on("request", lambda r: mem_requests.append(r.url) if "/api/memory" in r.url else None)
            page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: console_errors.append(str(e)))

            page.goto(PAGE, wait_until="networkidle")
            page.evaluate("""() => {
              localStorage.setItem('peiliao.cfg.v1', JSON.stringify({
                remote: true,
                base: 'http://127.0.0.1:18123/v1', key: 'invalid', model: 'x'
              }));
              localStorage.setItem('peiliao.session.v1', 'j4-down-test');
              localStorage.removeItem('peiliao.emotions.v1');
              localStorage.removeItem('peiliao.history.v1');
            }""")
            page.reload(wait_until="networkidle")
            page.wait_for_timeout(800)

            # 连说三句：若熔断失效，每句都会重试 → 请求数会线性增长
            for _ in range(3):
                page.fill("#chat-input", TEXT)
                page.click("#chat-form button[type=submit]")
                page.wait_for_timeout(2500)

            local_count = page.evaluate(
                "() => JSON.parse(localStorage.getItem('peiliao.emotions.v1') || '[]').length")
            is_remote = page.evaluate("() => window.MemoryStore.isRemote()")
            page.close()
            browser.close()

        real_errors = [e for e in console_errors if "18123" not in e and "ERR_CONNECTION_REFUSED" not in e]
        # 本脚本做 2 次页面加载（首次 goto + 设完 cfg 后 reload），每次加载最多探测 1 次。
        # ⚠️ 判据口径（本轮校准，原写"≤1 条"是错的）：设计能给的保证是
        #    「探测失败次数**上界 = 页面加载次数**，不随对话增长」——
        #    浏览器对失败的 fetch 必然记一条 console 错误，无法压到 0；
        #    而公网版根本不设 remote ⇒ 真实公网是 0 条（public_check 已验证）。
        loads = 2
        print(f"MEM_API_REQUESTS(上界={loads}): {len(mem_requests)} -> {mem_requests[:4]}")
        print(f"LOCAL_RECORDS(须≥1): {local_count}")
        print(f"IS_REMOTE_AFTER_FUSE(须 False): {is_remote}")
        print(f"CONSOLE_ERRORS(排除18123, 上界={loads}): {len(real_errors)} -> {real_errors[:3]}")

        ok = True
        if len(mem_requests) > loads:
            print(f"FAIL-A: 熔断未生效 —— /api/memory 请求数 {len(mem_requests)} 超过页面加载次数 {loads}（随对话增长）")
            ok = False
        if local_count < 1:
            print("FAIL-B: 本地存储没写入 ⇒ 远端不可用时降级被破坏")
            ok = False
        if is_remote:
            print("FAIL-A2: 熔断后 isRemote() 仍为 True")
            ok = False
        if len(real_errors) > loads:
            print(f"FAIL-C: console 噪音 {len(real_errors)} 超过页面加载次数 {loads}")
            ok = False
        print("J4-FUSE-PASS" if ok else "J4-FUSE-FAIL")
        return 0 if ok else 1
    finally:
        server.terminate()


if __name__ == "__main__":
    sys.exit(main())
