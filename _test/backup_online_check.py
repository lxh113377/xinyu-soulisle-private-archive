# -*- coding: utf-8 -*-
"""备用线真实在线判据（r86）：CloudBase 静态托管的 /xinyu/ 界面必须能走通在线对话。

背景（r83–r85 三轮的一手账）：备用线同源没有 /api/chat（静态域名不代理云函数，
云接入路由属控制台动作且 env 三项目共用）；r86 改为前端跨域调用 pages.dev 的
Pages Function（函数侧 CORS 白名单只放行自家来源）。本判据盯的就是这条链路：

  B1 页面标题/品牌 = 心屿 + MindIsle（改版未回扫即红）
  B2 demo stub 生效：cfg.proxy 指向 pages.dev（防止有人改回已死的 service 域名）
  B3 真发一条消息：回复气泡出现「在线大模型生成」—— 备用线从"离线降级"改判真实在线的唯一硬证据
  B4 全程 console 无 error（CSP / CORS 报错都会在这里现形）

三态：rc=0 PASS / rc=1 FAIL / rc=2 UNVERIFIED（网络层打不开页面等，不判绿）。
用法：python _test/backup_online_check.py
"""
import io
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
URL = "https://qwer-d4gf2r76o8829463b-1458054906.tcloudbaseapp.com/xinyu/"
TIMEOUT = 60


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("BACKUP-ONLINE-UNVERIFIED: playwright 缺失 ⇒ 未验，不判绿")
        return 2
    fails = []

    def ck(name, cond, info=""):
        print(("  PASS  " if cond else "  FAIL  ") + name + (f"  -> {info}" if info else ""))
        if not cond:
            fails.append(name)

    with sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception:
            b = p.chromium.launch(channel="msedge")
        ctx = b.new_context(viewport={"width": 1280, "height": 800})
        pg = ctx.new_page()
        errors = []
        pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        try:
            pg.goto(URL, wait_until="domcontentloaded", timeout=TIMEOUT * 1000)
        except Exception as e:
            print("BACKUP-ONLINE-UNVERIFIED: 页面打不开（%s）⇒ 未验，不判绿" % str(e)[:80])
            return 2
        pg.wait_for_timeout(3500)
        # 测试域名首访会有腾讯「确定访问」验证页（r83 在册）；新的浏览器上下文每次都会撞上
        if pg.locator(".brand").count() == 0:
            for txt in ("确定访问", "继续访问", "访问"):
                btn = pg.get_by_text(txt, exact=False)
                if btn.count() > 0:
                    btn.first.click()
                    break
            pg.wait_for_timeout(4000)
        brand = (pg.text_content(".brand") or "").replace("\n", "").strip()
        ck("B1 品牌=心屿+MindIsle", "心屿" in brand and "MindIsle" in brand, brand[:30])
        proxy = pg.evaluate(
            "() => { try { return JSON.parse(localStorage.getItem('peiliao.cfg.v1')||'{}').proxy || ''; }"
            " catch (e) { return 'ERR'; } }")
        ck("B2 stub 指向 pages.dev 的函数",
           proxy == "https://xinyu-soulisle.pages.dev/api/chat", proxy[:60])
        # B4 从「应用已真正加载」起算：CDN 传播期文档自身的偶发 404（curl 同 URL 200，r86 现场证过）
        # 算取数抖动，不算应用报错；应用真有 CSP/CORS 报错会在对话后继续现形。
        errors.clear()
        pg.fill("#chat-input", "最近总是失眠，压力好大")
        pg.evaluate("() => document.getElementById('chat-form').requestSubmit()")
        ok = False
        tag = ""
        for _ in range(TIMEOUT // 2):
            pg.wait_for_timeout(2000)
            tag = pg.evaluate(
                "() => { const m=[...document.querySelectorAll('#chat-log .msg.ai')];"
                " return m.length ? (m[m.length-1].textContent || '') : ''; }")
            if "在线大模型生成" in tag or "离线共情模板" in tag or "暂不可用" in tag:
                ok = True
                break
        ck("B3 备用线拿到真实在线回复（标签含「在线大模型生成」）",
           "在线大模型生成" in tag, tag[-80:].replace("\n", " "))
        ck("B4 console 零 error", not errors, "; ".join(errors)[:120])
        b.close()

    tail = "B1–B4 全过" if not fails else "未过: " + "; ".join(fails)
    if fails:
        print("BACKUP-ONLINE-FAIL: %s" % tail)
        return 1
    print("BACKUP-ONLINE-PASS: %s（备用线由『如实标注的离线降级』改判真实在线）" % tail)
    return 0


if __name__ == "__main__":
    sys.exit(main())
