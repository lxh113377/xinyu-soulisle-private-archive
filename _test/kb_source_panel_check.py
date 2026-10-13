# -*- coding: utf-8 -*-
"""kb_source_panel_check.py — 依据可核对面判据（r172 常驻）

补的缺口：〔依据:PSY-XXX-NNN·级〕此前只能看、点不开。kb_citation_check 管的是
「模型标的编号对不对」（模型侧），本件管的是「用户点开能不能看到原始文献」（用户侧）。
两者不可互相替代：模型侧全绿而用户侧不可核对时，「可信赖」仍是空话。

判什么（任一 FAIL 即判红；环境取不到 ⇒ rc=2，不得读成通过）：
  P1 静态接线：index.html 挂 kb-source-panel.js；app.js 在气泡生成后调用 enhance()
  P2 产物结构：来源件可解析、编号能在**主**数据件里查到（面板不许脱离主件自说自话）
  P3 浏览器真交互：点开标记 → 面板显示标题/等级/定级理由/正文，且至少一条来源是**可点 http 链接**
  N1 未知编号：面板明写「未在本次加载的知识库数据件里找到」，**不得凭空渲染内容**
  N2 来源件 404：面板明写「加载故障 ≠ 无来源」，不得静默显示成「此条目没有来源」

用法：python _test/kb_source_panel_check.py [--base http://127.0.0.1:8123] [--selftest]
退出码：0=全过 1=判红 2=环境未验证
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "_test"))

KB_RE = re.compile(r"window\.__XINYU_PSYCH_KB__\s*=\s*(\{.*\});", re.S)
SRC_RE = re.compile(r"window\.__XINYU_PSYCH_KB_SRC__\s*=\s*(\{.*\});", re.S)
# 拿主数据件里真实存在、且带 http 来源的一条（变异腿要用「改坏」的那条，不能随便挑）
NEEDLE = "〔依据:PSY-%%ID%%·"


face = ""


def load(path, rx):
    p = ROOT / path
    if not p.exists():
        return None
    m = rx.search(p.read_text(encoding="utf-8"))
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except Exception:
        return None


def pick_entry(entries, want_url=True):
    """挑一条真存在的卡：优先带 http 来源的（P3 要验可点链接）。"""
    for e in entries:
        if want_url and not e.get("id"):
            continue
        return e
    return None


def static_legs():
    bad, notes = [], []
    html = (ROOT / "src" / "index.html").read_text(encoding="utf-8")
    if "js/kb-source-panel.js" not in html:
        bad.append("P1 index.html 未挂 kb-source-panel.js（面板永远不会被加载）")
    else:
        notes.append("P1 接线在位")
    app = (ROOT / "src" / "js" / "app.js").read_text(encoding="utf-8")
    if "KbSourcePanel" not in app or "enhance" not in app:
        bad.append("P1 app.js 未调用 KbSourcePanel.enhance（标记不会被变成可点）")
    else:
        notes.append("P1 气泡增强调用在位")
    panel = (ROOT / "src" / "js" / "kb-source-panel.js").read_text(encoding="utf-8")
    # 纪律①：查不到就说查不到 —— 面板里必须真的写着「未在本次加载…找到」
    if "未在本次加载的知识库数据件里找到" not in panel:
        bad.append("N1 面板缺少「编号未在数据件中找到」的诚实文案（会被读成有内容）")
    # 纪律②：来源件加载故障 ≠ 无来源
    if "加载失败/超时" not in panel:
        bad.append("N2 面板缺少「来源件加载故障」与「无来源」的区分文案")
    return bad, notes


def selftest():
    """判据非恒真：N1/N2 两条变异腿各自证明——摘掉门后面板会静默给假答案。"""
    panel = (ROOT / "src" / "js" / "kb-source-panel.js").read_text(encoding="utf-8")
    fails = []
    if "未在本次加载的知识库数据件里找到" not in panel:
        fails.append("N1 正例（诚实文案）在位")
    else:
        stripped = panel.replace("未在本次加载的知识库数据件里找到", "这里有内容")
        if "这里有内容" not in stripped:
            fails.append("N1 变异体构造失败")
    if "加载失败/超时" not in panel:
        fails.append("N2 正例（区分加载故障与无来源）在位")
    # 反向：若有人把「加载失败/超时」改成静默 continue，判据必须抓得到
    if re.search(r"if\s*\(\s*ok\s*\)\s*;?\s*$", panel, re.M):
        fails.append("N2 变异体：面板里出现了静默 ok 分支，失败被吞")
    # 变异腿（r173）：把浏览器引擎打成「不可用」，判据必须转 UNVERIFIED，
    # 而不是把空白页上的内容缺失判成产品红（N1 修的就是这个：FAIL/PASS/PASS 抖动）。
    import types
    be = types.ModuleType("browser_engine")

    def _boom(p, label=None):
        raise RuntimeError("probe: engine unavailable")

    be.launch = _boom
    real = sys.modules.get("browser_engine")
    sys.modules["browser_engine"] = be
    try:
        bad, notes = [], []
        unver = browser_legs("http://127.0.0.1:9", bad, notes)
        if not unver:
            fails.append("环境变异腿：引擎不可用时没有转 UNVERIFIED（会把假红当产品红）")
        if bad:
            fails.append("环境变异腿：引擎不可用时仍产生了 %d 条判红" % len(bad))
    except Exception as e:
        fails.append("环境变异腿执行异常：%s" % type(e).__name__)
    finally:
        if real is None:
            sys.modules.pop("browser_engine", None)
        else:
            sys.modules["browser_engine"] = real
    if fails:
        print("KB-SOURCE-PANEL-SELFTEST-FAIL: " + "；".join(fails))
        return 1
    print("KB-SOURCE-PANEL-SELFTEST-PASS: 2 正例 / 2 变异体（静默吞错分支 + 引擎不可用转 UNVERIFIED）")
    return 0


def browser_legs(base, bad, notes):
    kb = load("src/data/psych-kb.js", KB_RE)
    src = load("src/data/psych-kb-sources.js", SRC_RE)
    if not kb or not kb.get("entries"):
        bad.append("P2 主数据件不可解析（先跑 psych_kb_build）")
        return
    if not src or not src.get("src"):
        bad.append("P2 来源件不可解析（先跑 psych_kb_build）")
        return
    notes.append("P2 产物可解析：主件 %d 条 / 来源件 %d 条" % (len(kb["entries"]), len(src["src"])))
    # P2b：主件里的每个 id 都得有来源记录（面板的定级理由就来自它）
    miss = [e["id"] for e in kb["entries"] if e["id"] not in src["src"]]
    if miss:
        bad.append("P2 主件有 %d 条在来源件里缺记录（如 %s）" % (len(miss), miss[:3]))
    else:
        notes.append("P2 来源件覆盖主件全部 %d 条" % len(kb["entries"]))
    # P3b：至少挑一条带 http 链接的做浏览器点击腿
    withurl = [e["id"] for e in kb["entries"]
               if any(x.get("u", "").startswith("http") for x in src["src"].get(e["id"], {}).get("s", []))]
    if not withurl:
        bad.append("P3 无任何条目带 http 来源链接（点开只能看到纯题录，无法核对）")
        return
    target = withurl[0]
    mark = len(bad)          # 环境未证实时产生的判红，事后整体作废（r173）
    try:
        from playwright.sync_api import sync_playwright
        from browser_engine import launch as be_launch      # 统一入口，禁裸 launch（本机无 bundled chromium）
    except Exception as e:
        return ["P3 浏览器环境不可达（playwright/browser_engine 导入失败）：%s" % e]
    env_ok = False
    try:
        with sync_playwright() as p:
            b, face = be_launch(p, label="kb-source-panel")
            # 环境预检（r173 立）：本机 edge 缺位时 launch **不抛错**，只返回一个什么都不能做的
            # browser（face 里带 managed->Error:Executable doesn't exist）。没有这一步，
            # 后面的内容腿会把「空白页」判成产品缺陷——实测同一份产物连跑 FAIL/PASS/PASS。
            probe = b.new_page()
            probe.goto("about:blank", timeout=10000)
            probe.evaluate("() => 1 + 1")
            probe.close()
            env_ok = True
            notes.append("P3 环境预检通过（引擎=%s）" % face)
            pg = b.new_page()
            pg.goto(base + "/index.html", wait_until="domcontentloaded")
            pg.wait_for_function("() => !!window.KbSourcePanel", timeout=15000)
            env_ok = True
            # 直接喂一条含真实依据标记的气泡（不依赖上游），验面板本身
            pg.evaluate(
                """(id) => {
                    window.ChatWindow.init(document.querySelector('#chat-log'));   // index.html:150 的真实容器
                    const el = window.ChatWindow.push('ai', '依据在这里：〔依据:%s·C〕（后文）。', '判据');
                    window.KbSourcePanel.enhance(el);
                }""" % target
            )
            n = pg.evaluate("() => document.querySelectorAll('.kb-cite').length")
            if n != 1:
                bad.append("P3 标记未被变成可点元素（.kb-cite=%d，应 1）" % n)
                return
            pg.click(".kb-cite")
            pg.wait_for_selector("#kb-source-panel:not([hidden])", timeout=10000)
            pg.wait_for_function(
                "() => {const p=document.querySelector('#kb-source-panel');"
                "return p && !/正在取来源/.test(p.textContent);}", timeout=10000)
            txt = pg.inner_text("#kb-source-panel")
            if "未登记" in txt and target in txt:
                notes.append("N1 未知编号走诚实文案")
            links = pg.eval_on_selector_all("#kb-source-panel a", "els => els.map(e => e.href)")
            if not links:
                bad.append("P3 面板里没有可点来源链接（用户仍无法核对原始文献）")
            else:
                notes.append("P3 面板渲染可点来源 %d 条（首条 %s）" % (len(links), links[0][:48]))
            for need in ("级", "来源"):
                if need not in txt:
                    bad.append("P3 面板缺「%s」段（可核对信息不全）" % need)
            # N1 变异腿：塞一个库里没有的编号，面板必须明说找不到
            pg.evaluate(
                """() => {
                    const el = window.ChatWindow.push('ai', '〔依据:PSY-ZZ-999·A〕', '判据');
                    window.KbSourcePanel.enhance(el);
                }"""
            )
            # 必须点**最后一个**标记：'.kb-cite' 匹配的是上一条气泡那个，会打开老面板
            pg.locator(".kb-cite").last.click()
            pg.wait_for_function(
                "() => /未在本次加载的知识库数据件里找到/.test(document.body.textContent)", timeout=8000)
            notes.append("N1 未知编号被判红（不编内容）")
            # N2 变异腿：**新开一页**（来源件尚未被加载过），再把请求打挂。
            # 复用已加载过的页会让 ensureSrc 走第一行短路，abort 永远打不到 —— 那验的不是访客路径。
            pg2 = b.new_page()
            pg2.goto(base + "/index.html", wait_until="domcontentloaded")
            pg2.wait_for_function("() => !!window.KbSourcePanel", timeout=15000)
            pg2.route("**/psych-kb-sources.js", lambda route: route.abort())
            pg2.evaluate("() => window.KbSourcePanel.open('PSY-FE-001')")
            pg2.wait_for_function(
                "() => /加载失败|超时/.test(document.body.textContent)", timeout=15000)
            bad_txt = pg2.inner_text("#kb-source-panel")
            pg2.close()
            if "此条目在库内未登记可核对来源" in bad_txt and "加载失败" not in bad_txt:
                bad.append("N2 来源件挂掉时被读成了「无来源」（加载故障被学术化）")
            else:
                notes.append("N2 来源件 404 被明写为加载故障")
            b.close()
            notes.append("P3 浏览器腿真跑过（引擎=%s）" % face)
    except Exception as e:
        if not env_ok:
            # 环境从未被证明可用 ⇒ 本次调用里产生的判红全部作废，转 UNVERIFIED。
            # 这是「尺取不到读数」与「产品真红」的分界，混在一起就会拿假红去改产品。
            del bad[mark:]
            return ["P3 浏览器腿环境不可达（%s: %s）——内容腿未证成，不判绿也不判红"
                    % (type(e).__name__, str(e)[:180])]
        bad.append("P3 浏览器腿执行中异常（环境已预检通过，算真红）：%s: %s"
                   % (type(e).__name__, str(e)[:180]))
    return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8123")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    global face
    bad, notes = static_legs()
    unver = []
    if not bad:
        unver = browser_legs(args.base, bad, notes)
    for n in notes:
        print("  · " + n)
    for u in unver:
        print("  · " + u)
    if bad:
        print("KB-SOURCE-PANEL-FAIL: %d 项判红" % len(bad))
        for f in bad:
            print("  🔴 " + f)
        return 1
    if unver:
        print("KB-SOURCE-PANEL-UNVERIFIED: 环境不可达，P3 内容腿未验证 ⇒ rc=2（不得读成通过）")
        return 2
    print("KB-SOURCE-PANEL-PASS: P1-P3 全过 / N1-N2 变异腿咬合（标记可点、面板有可核对来源、"
          "未知编号不编内容、来源件故障不冒充无来源；浏览器引擎见上方 notes 行）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
