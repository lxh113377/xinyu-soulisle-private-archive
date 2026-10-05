# -*- coding: utf-8 -*-
r"""browser_engine_declare_check.py — 浏览器面的**声明与唯一实现**门（r96 立）。

它盯五件事（每条腿都有名字，红因点名到腿）：
  E1 回退必须被声明  —— 本仓判据在受管 Chromium 起不来时回退系统 Edge（29 个套件各自手写），
      而 `CONTRIBUTING.md` 此前对 playwright/chromium/msedge **零提及** ⇒ 新人 clone 后看到"全绿"
      会以为本机跑的就是受理面那个浏览器。本机实测：`chromium.launch()` 抛
      `Executable doesn't exist at …chromium_headless_shell-1223…`（缓存里只有 1228/1243，
      而 playwright 1.60.0 要 1223），回退 Edge 154.0.4258.53 能通。
  E2 唯一实现（棘轮）—— AST 扫 `_test/*.py`，凡出现 `chromium.launch(` 的文件必须引
      `browser_engine`。**本轮不一次改完 29 个文件**（批量 Edit 撞本仓排障手册那条
      「吞 def 行而 py_compile / --selftest 全过」），改为把未接入数钉成**只许降不许升**的上界：
      新增套件想再手写一份回退 ⇒ 计数上升 ⇒ 当场红。这样"还没改"不会被读成"没有这件事"。
  E3 机器面折进判据词 —— `--machine` 真起一次，把**这台浏览器的身份**写进含判据词的那一行。
      不能靠各套件"顺手多打一行"：电池对每个套件只留末条判定行
      （`run_all_suites.VERDICT_RE`），中途打印的身份行系统性进不了 CI。
  E4 面文件一致性 —— `browser_engine.record()` 落的最近一条必须与 E3 现算同引擎
      （防"套件说 chromium、日志里其实是 Edge"）。
  E5 CONTRIBUTING 的依赖面不得虚报 —— 原文 `:17` 写「仅标准库，无需 pip 安装」，
      而 `_test/requirements.txt` 列着 playwright/PyYAML/pypdf/Pillow，G11 还要求跑判据的
      CI job 装这份清单 ⇒ 新人照 CONTRIBUTING 做 clone 后**第一批浏览器判据全 import 失败**。
      这条比引擎版本坑更致命，同笔修。

用法：
  python _test/browser_engine_declare_check.py            # 静态档：零网络零浏览器（进电池）
  python _test/browser_engine_declare_check.py --machine  # 机器档：真起一次取本机面（CI / 人工轮次）
  python _test/browser_engine_declare_check.py --selftest # 判据桩（正例/变异/边界三族）
退出码：0=五腿全过 1=任一腿红 2=分母为 0 / playwright 不可导入 / 面文件缺失 ⇒ UNVERIFIED，**不判绿**
"""
import argparse
import ast
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_DIR = ROOT / "_test"
CONTRIB = ROOT / "CONTRIBUTING.md"
REQS = ROOT / "_test" / "requirements.txt"
SELF_NAMES = {"browser_engine_declare_check.py", "browser_engine.py"}

# E1 要求的四要素：三件套关键词 + 一条可执行的修复命令（缺任一即"声明了但照做仍起不来"）
E1_KEYS = (re.compile(r"playwright", re.I),
           re.compile(r"chromium", re.I),
           re.compile(r"msedge|\bedge\b", re.I),
           re.compile(r"playwright install|XINYU_CHROMIUM_PATH", re.I))
# E5 的违禁形态：**只扫 CONTRIBUTING 这一个产出面**，禁把"标准库"这种普通词当违禁词
E5_BANNED = re.compile(r"无需 pip|不需要 pip|no pip install|仅标准库")


def launch_sites(dir_path):
    """含 `chromium.launch(` 的 .py 清单（分母从现读，不手抄）。"""
    out = []
    for p in sorted(dir_path.glob("*.py")):
        if p.name in SELF_NAMES:
            continue
        try:
            txt = p.read_text(encoding="utf-8")
        except Exception:                                     # noqa: BLE001
            continue
        if "chromium.launch(" in txt:
            out.append(p.name)
    return out


def wired_names(dir_path, sites):
    """这些站点里，已经**真的**引到统一入口的（AST 判 import，不靠 grep 子串）。"""
    wired = []
    for name in sites:
        p = dir_path / name
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except Exception:                                     # noqa: BLE001
            continue
        for n in ast.walk(tree):
            if isinstance(n, ast.ImportFrom) and (n.module or "").endswith("browser_engine"):
                wired.append(name)
                break
            if isinstance(n, ast.Import):
                for al in n.names:
                    if (al.name or "").endswith("browser_engine"):
                        wired.append(name)
                        break
                else:
                    continue
                break
    return wired


def e1_contrib_declares(text):
    """返回 (ok, 缺什么)。四要素齐才算"声明"。"""
    miss = [pat.pattern for pat in E1_KEYS if not pat.search(text or "")]
    return (not miss), miss


def e5_contrib_deps(text, req_text):
    """返回 (ok, 说明)。虚报"无需 pip"即红；requirements 有内容时必须被引用到。

    窄豁免：含 `更正注` 的行**不判**——本仓规矩是"被推翻的原文保留 + 加更正注"
    （见 memory/AGENTS.md 架构决策约定），于是治理文档**必然**要逐字引用那句错话。
    按 R236 的正解是白名单排除法，**不是**为了让门变绿而删掉自曝的那句原文。
    残余风险如实登记在 r96 报告 §5：有人可写「更正注」三字来规避 E5，故豁免只按**行**生效、
    且 selftest 里两向各一条腿（带豁免/不带豁免）。"""
    pkgs = [ln.strip() for ln in (req_text or "").splitlines()
            if ln.strip() and not ln.strip().startswith("#")]
    scannable = chr(10).join(ln for ln in (text or "").splitlines() if "更正注" not in ln)
    if E5_BANNED.search(scannable):
        return False, "CONTRIBUTING 含「无需 pip/仅标准库」类断言，而清单实有 %d 个依赖" % len(pkgs)
    if pkgs and "requirements.txt" not in (text or ""):
        return False, "清单列了 %d 个依赖但 CONTRIBUTING 未指向 _test/requirements.txt" % len(pkgs)
    return True, "依赖 %d 个已指向清单" % len(pkgs)


def read_face_file():
    """读 browser_engine 落的面文件（路径与 browser_engine.face_file() 同源，不重造）。"""
    sys.path.insert(0, str(TEST_DIR))
    try:
        import browser_engine                                  # noqa: F401,WPS433
        p = browser_engine.face_file()
    except Exception as e:                                     # noqa: BLE001
        return None, "取面文件路径失败(%s)" % type(e).__name__
    if not p.is_file():
        return None, "面文件不存在(%s)——静态档不要求它，机器档要求" % p
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:                                     # noqa: BLE001
        return None, "面文件不可解析(%s)" % type(e).__name__
    if not isinstance(data, list) or not data:
        return None, "面文件为空（不得读成「没有回退发生过」）"
    return data[-1], str(p)


def run_static(baseline):
    """E1 / E2 / E5。返回 (rows, red_list, denom_ok)。"""
    rows, red = [], []
    ct = CONTRIB.read_text(encoding="utf-8") if CONTRIB.is_file() else ""
    ok1, miss1 = e1_contrib_declares(ct)
    rows.append(["E1 回退被声明", "PASS" if ok1 else "RED",
                 "四要素齐" if ok1 else "缺=%s" % ",".join(miss1)])
    if not ok1:
        red.append("E1")

    sites = launch_sites(TEST_DIR)
    wired = wired_names(TEST_DIR, sites)
    if not sites:
        rows.append(["E2 唯一实现（棘轮）", "UNVERIFIED", "分母为 0：没有任何 launch 站点可数"])
        return rows, red, False
    n_un = len(sites) - len(wired)
    if n_un > baseline:
        rows.append(["E2 唯一实现（棘轮）", "RED",
                     "未接入 %d > 基线 %d ⇒ 上升了（新增的站点必须走 browser_engine）；"
                     "清单见 --json" % (n_un, baseline)])
        red.append("E2")
    else:
        rows.append(["E2 唯一实现（棘轮）", "PASS",
                     "未接入统一入口 %d/%d（基线 %d，只降不升）已接入 %d"
                     % (n_un, len(sites), baseline, len(wired))])

    rt = REQS.read_text(encoding="utf-8") if REQS.is_file() else ""
    ok5, why5 = e5_contrib_deps(ct, rt)
    rows.append(["E5 依赖面不虚报", "PASS" if ok5 else "RED", why5])
    if not ok5:
        red.append("E5")
    return rows, red, True


def run_machine():
    """E3 / E4：真起一次，取这台机器的实际面。"""
    sys.path.insert(0, str(TEST_DIR))
    try:
        from playwright.sync_api import sync_playwright
        import browser_engine
    except Exception as e:                                     # noqa: BLE001
        return None, "playwright/browser_engine 不可导入(%s)" % type(e).__name__
    try:
        with sync_playwright() as pw:
            browser, face = browser_engine.launch(pw, label="declare_check")
            ver = getattr(browser, "version", "unknown")
            browser.close()
    except Exception as e:                                     # noqa: BLE001
        return None, "三档浏览器全起不来(%s)" % str(e).splitlines()[0][:90]
    last, path = read_face_file()
    if last is None:
        return face, "面文件读不到(%s)" % path
    if last.get("engine") not in face:
        return face, "面文件最近一条=%s ≠ 本次现算=%s" % (last.get("engine"), face)
    return face, "OK（面文件 %s 最近一条一致，label=%s）" % (path, last.get("label"))


def selftest():
    cases = []

    def eq(label, got, want):
        cases.append((label, got, want))

    GOOD = ("## 浏览器判据\nplaywright 自带 Chromium 版本不匹配时本仓回退 msedge，"
            "修复：`playwright install chromium` 或 set XINYU_CHROMIUM_PATH=...\n"
            "依赖见 _test/requirements.txt\n")
    # 正例腿
    eq("合格 CONTRIBUTING 过 E1", e1_contrib_declares(GOOD)[0], True)
    eq("合格文本过 E5", e5_contrib_deps(GOOD, "playwright==1.60.0\nPyYAML\n")[0], True)
    sites = launch_sites(TEST_DIR)
    eq("分母从现读：站点数 > 0（为 0 时主流程判 UNVERIFIED 而不是绿）", len(sites) > 0, True)
    eq("本件自己不算进分母（判据不给自己加站点）", "browser_engine_declare_check.py" in sites, False)
    eq("已接入者被 AST 认出或未被认出都只能是 sites 的子集",
       set(wired_names(TEST_DIR, sites)) <= set(sites), True)
    # 变异腿
    eq("变异体 E1 摘掉 msedge 关键词 ⇒ 只写 chromium 的文本也判绿（证明这条在咬）",
       e1_contrib_declares("playwright 与 chromium 都装了")[0], False)
    keep = globals()["E1_KEYS"]
    globals()["E1_KEYS"] = (re.compile(r"playwright", re.I),)
    eq("变异体 只留 playwright 一个关键词 ⇒ 未声明回退的文本漏报",
       e1_contrib_declares("装了 playwright")[0], True)
    globals()["E1_KEYS"] = keep
    eq("还原后同一文本重新判否（证明上面动的是尺不是期望值）",
       e1_contrib_declares("装了 playwright")[0], False)
    eq("E5 抓到虚报：写「无需 pip」必须红",
       e5_contrib_deps("回归脚本仅标准库，无需 pip 安装", "playwright\n")[0], False)
    eq("E5 抓到指向缺失：有清单但不提 requirements.txt 也红",
       e5_contrib_deps("装了 playwright 和 msedge 与 chromium，用 playwright install 修",
                       "playwright\n")[0], False)
    # 边界腿
    eq("边界 空文本 ⇒ E1 红（不是「没东西可查所以过」）", e1_contrib_declares("")[0], False)
    eq("边界 依赖清单为空 ⇒ E5 放行（本仓无依赖时不该要求指向清单）",
       e5_contrib_deps(GOOD, "")[0], True)
    eq("边界 E5 违禁词不误伤「标准库」单独出现（只在配 无需 pip 时算虚报）",
       bool(E5_BANNED.search("本件用 Python 标准库实现")), False)
    NL = chr(10)
    eq("边界 豁免按行生效：带「更正注」的那句自曝原文不判红",
       e5_contrib_deps("更正注：原写 仅标准库，无需 pip 安装" + NL
                       + "依赖见 _test/requirements.txt" + NL, "playwright" + NL)[0], True)
    eq("变异体 把「更正注」三字摘掉 ⇒ 同一句必须判红（证明豁免是窄的、不是大赦）",
       e5_contrib_deps("原写 仅标准库，无需 pip 安装" + NL
                       + "依赖见 _test/requirements.txt" + NL, "playwright" + NL)[0], False)

    bad = [(n, g, w) for n, g, w in cases if g != w]
    for n, g, w in bad:
        print("  用例不符: %s ｜ got=%r want=%r" % (n, g, w))
    print("BROWSER-ENGINE-SELFTEST-%s（%d/%d 条）"
          % ("PASS" if not bad else "FAIL", len(cases) - len(bad), len(cases)))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--machine", action="store_true", help="真起一次浏览器取本机面（E3/E4）")
    ap.add_argument("--baseline", type=int, default=32,
                    help="E2 棘轮上界：未接入 browser_engine 的 launch 站点数"
                         "（r96 两条独立腿各算一次 = 32 / 34-2=32，只降不升）")
    ap.add_argument("--json", default="")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()

    rows, red, denom_ok = run_static(a.baseline)
    sites = launch_sites(TEST_DIR)
    wired = wired_names(TEST_DIR, sites)
    face_line = ""
    if a.machine:
        face, note = run_machine()
        if face is None:
            rows.append(["E3/E4 机器面", "UNVERIFIED", note])
            print("BROWSER-ENGINE-UNVERIFIED: %s" % note)
            return 2
        rows.append(["E3/E4 机器面", "RED" if note != "OK" and not note.startswith("OK")
                     else "PASS", "本机面=%s ｜ %s" % (face, note)])
        if not note.startswith("OK"):
            red.append("E4")
        face_line = " 本机面=%s" % face
    if not denom_ok:
        print("BROWSER-ENGINE-UNVERIFIED: E2 分母为 0（没有 launch 站点可数 ≠ 全部已接入）")
        return 2
    un = len(sites) - len(wired)
    for r in rows:
        print("  %-22s %-11s %s" % (r[0], r[1], r[2]))
    print("-" * 100)
    print("BROWSER-ENGINE-%s: 统一入口 %d/%d 已接（基线 %d，只降不升）｜E1 %s｜E5 %s%s"
          % ("FAIL" if red else "PASS", len(wired), len(sites), a.baseline,
             "红" if "E1" in red else "绿", "红" if "E5" in red else "绿", face_line)
          + ("" if not red else " 红因=%s" % ",".join(red)))
    if a.json:
        Path(a.json).write_bytes(json.dumps(
            {"baseline": a.baseline, "sites": sites, "wired": wired,
             "unmigrated": un, "rows": rows, "red": red, "machine_face": face_line.strip()},
            ensure_ascii=False, indent=1).encode("utf-8"))
    return 1 if red else 0


if __name__ == "__main__":
    sys.exit(main())
