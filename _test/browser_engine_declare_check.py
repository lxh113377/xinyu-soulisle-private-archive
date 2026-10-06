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

r98 新增三条腿（起因：r96 §4 为下一轮写的验收标准 `统一入口 N/32 已接（N 单调升）`
**按构造不可达**——`wired_names()` 的分子定义为「同时含裸 `chromium.launch(` 且已 import
browser_engine 的文件」，一件接完就不再含前者、随即离开分母 ⇒ N 恒 ≈0，
**只有把迁移留在半成品状态才可能让 N 上升**。这把尺在奖励没做完的活。本轮修尺：）
  E2 取数面  由「子串 `chromium.launch(`」换成 **AST**（`Call` 且 `func.attr=="launch"`、
             `func.value` 是 `Attribute(attr=="chromium")`）。切换取证 = 两面**逐字同集**
             （r98 实测：子串 32 件 / AST 32 件，双向差集空，AST 面另有 62 个调用点）。
  E2b 余量有主  对 `起点名册 − 当前站点集` 的每件断言三条件齐：① 文件仍在盘
             ② AST 判明确实 import 了 browser_engine ③ AST 裸 launch 点数 == 0。
             封掉三种「假降」：删文件、改名躲分母、只 import 不删回退。
  E2c 接入即无残留  既是站点又已 import 的件（= 半接入残留）必须为 0。
  「已接入数」改为 `len(起点名册) − len(当前站点集)` —— 仍从现读推导，不写常量。
  名册缺失 ⇒ E2b 判 UNVERIFIED 并 rc=2（**不得**读成「没有需要核对的件」）。

用法：
  python _test/browser_engine_declare_check.py            # 静态档：零网络零浏览器（进电池）
  python _test/browser_engine_declare_check.py --machine  # 机器档：真起一次取本机面（CI / 人工轮次）
  python _test/browser_engine_declare_check.py --write-roster  # 生成/重定起点名册（只在迁移动手前跑）
  python _test/browser_engine_declare_check.py --census   # 逐件 defs 符号表对名册（迁移件的防「吞 def」验收腿）
  python _test/browser_engine_declare_check.py --selftest # 判据桩（正例/变异/边界三族）
退出码：0=各腿全过 1=任一腿红 2=分母为 0 / 名册缺失 / playwright 不可导入 / 面文件缺失 ⇒ UNVERIFIED，**不判绿**
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
if str(TEST_DIR) not in sys.path:
    sys.path.insert(0, str(TEST_DIR))
from browser_engine import short_face as be_short    # noqa: E402  唯一实现，本件不自写第二份截短逻辑
CONTRIB = ROOT / "CONTRIBUTING.md"
REQS = ROOT / "_test" / "requirements.txt"
SELF_NAMES = {"browser_engine_declare_check.py", "browser_engine.py"}
# 起点名册：r98 迁移动手**之前**生成的站点全集，E2b/E2c/--census 的对照物。
# 名字不带日期 ⇒ 不属于 ledger_age 的 `peer-*.json` 取数面，不与台账族名相撞。
ROSTER = ROOT / "交付物" / "对标数据" / "browser-engine-roster.json"

# E1 要求的四要素：三件套关键词 + 一条可执行的修复命令（缺任一即"声明了但照做仍起不来"）
E1_KEYS = (re.compile(r"playwright", re.I),
           re.compile(r"chromium", re.I),
           re.compile(r"msedge|\bedge\b", re.I),
           re.compile(r"playwright install|XINYU_CHROMIUM_PATH", re.I))
# E5 的违禁形态：**只扫 CONTRIBUTING 这一个产出面**，禁把"标准库"这种普通词当违禁词
E5_BANNED = re.compile(r"无需 pip|不需要 pip|no pip install|仅标准库")


def launch_points(tree):
    """AST 现读 `*.chromium.launch(...)` 的调用点数（r98 起 sites 的取数口径）。"""
    n = 0
    for x in ast.walk(tree):
        if isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute) and x.func.attr == "launch":
            v = x.func.value
            if isinstance(v, ast.Attribute) and v.attr == "chromium":
                n += 1
    return n


def defs_of(tree):
    """本件的函数符号表（qualname 排序）——迁移件的「Edit 吞 def 行而 py_compile 全过」对账面。"""
    out = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.append(node.qualname if hasattr(node, "qualname") else node.name)
    return sorted(out)


def imports_browser_engine(tree):
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and (n.module or "").endswith("browser_engine"):
            return True
        if isinstance(n, ast.Import):
            for al in n.names:
                if (al.name or "").endswith("browser_engine"):
                    return True
    return False


def read_sources(dir_path):
    """`{文件名: 原文}`，排除 SELF_NAMES。读不到的件登记为 None —— 不许静默消失。"""
    out = {}
    for p in sorted(dir_path.glob("*.py")):
        if p.name in SELF_NAMES:
            continue
        try:
            out[p.name] = p.read_text(encoding="utf-8")
        except Exception:                                     # noqa: BLE001
            out[p.name] = None
    return out


def scan_sources(sources):
    """核心取数：`({站点名: {launch_points, defs, imports_be}}, [隐身件清单])`。

    夹具一律走这个纯函数 + 内存字典（同 `ledger_age_check.py:121-123` 的取舍）：
    本机禁用磁盘直删（lessons-p0 2026-10-01 铁律），selftest 若造临时件就得删、不删就留垃圾
    ⇒ 从源头不造文件。解析失败件进 `broken` 由 E2d 点名，**禁止 `except: continue`**。"""
    cur, broken = {}, []
    for name, txt in sorted(sources.items()):
        if txt is None:
            broken.append(name)
            continue
        try:
            tree = ast.parse(txt)
        except Exception:                                     # noqa: BLE001
            broken.append(name)
            continue
        pts = launch_points(tree)
        if pts:
            cur[name] = {"launch_points": pts, "defs": defs_of(tree),
                         "imports_be": imports_browser_engine(tree)}
    return cur, broken


def scan_dir(dir_path):
    return scan_sources(read_sources(dir_path))


def launch_sites(dir_path):
    """含裸 `chromium.launch()` 调用点的 .py 清单（分母从现读，不手抄）。

    更正注 r98：本函数 r96 版用子串 `"chromium.launch(" in txt` 取数。换成 AST 的取证是
    「两面逐字同集」——r98 实测子串 32 件 / AST 32 件、双向差集为空、零解析失败件。
    换成 AST 不是风格偏好：子串面在字面量/注释里出现该串时会**虚增**分母，而分母是棘轮的腿。"""
    return sorted(scan_dir(dir_path)[0])


def wired_names(sources, sites):
    """这些站点里**仍含裸 launch 却又已 import** 的（= 半接入残留，E2c 要求为 0）。

    更正注 r98：r96 把它当「已接入数」印进门面行，而它的定义决定了**接完一件就离开分母、
    不可能被它计数** ⇒ r96 §4 写的「N 单调升」按构造不可达。现改名为「半接入残留」，
    「已接入数」另由 `len(起点名册) − len(当前站点集)` 现读推导。"""
    out = []
    for name in sites:
        txt = sources.get(name)
        if txt is None:
            continue
        try:
            tree = ast.parse(txt)
        except Exception:                                     # noqa: BLE001
            continue
        if imports_browser_engine(tree):
            out.append(name)
    return out


def load_roster(path=None):
    """读起点名册。缺失/空/形状不符 ⇒ 返回 (None, 原因)，调用方必须判 UNVERIFIED 而非跳过。"""
    p = Path(path) if path else ROSTER
    if not p.is_file():
        return None, "名册缺失(%s) ⇒ E2b 无对照物，不得读成「没有站点要核对」" % p.name
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:                                     # noqa: BLE001
        return None, "名册不可解析(%s)" % type(e).__name__
    sites = data.get("sites") if isinstance(data, dict) else None
    if not isinstance(sites, dict) or not sites:
        return None, "名册 sites 为空或形状不符 ⇒ 空名册不构成核对"
    return data, str(p)


def e2b(roster_sites, cur, sources):
    """离开站点集的件必须三条件齐：仍在盘 ∧ import 了统一入口 ∧ AST 裸 launch 点数==0。

    这条封的是三种「假降」：删文件、改名躲分母、只 import 不删回退。
    返回红因清单（空=绿）。件是否"在盘"看 `sources` 里有没有它（None=读不到，同等于不在）。"""
    bad = []
    for name in sorted(set(roster_sites) - set(cur)):
        txt = sources.get(name)
        if txt is None:
            bad.append("%s(文件不在了——删除/改名不等于接入)" % name)
            continue
        try:
            tree = ast.parse(txt)
        except Exception as e:                                 # noqa: BLE001
            bad.append("%s(解析失败 %s)" % (name, type(e).__name__))
            continue
        pts = launch_points(tree)
        if pts:
            bad.append("%s(已离开分母却仍存 %d 处裸 launch)" % (name, pts))
            continue
        if not imports_browser_engine(tree):
            bad.append("%s(裸 launch 归零但没引统一入口)" % name)
    return bad


ALLOWED_DROP = ("launch",)   # 迁移**有意**删掉的那个手写 helper；别的符号消失就是事故


def census(roster_sites, cur, sources, allow_drop=ALLOWED_DROP):
    """逐件 defs 符号表对名册 ⇒ 迁移件的合法形态是「只少 `launch`，其余零差」。

    为什么不放宽成"少一个也算过"：本仓一手指代价是 `Edit` 吞掉 `def` 行而
    `py_compile`/`--selftest` 全过（memory/AGENTS.md 排障手册，r90 两次）。
    多删/少删都点名，且**新增**符号也点名（防止把两段代码缝成一个函数）。"""
    rows = []
    for name in sorted(set(roster_sites) - set(cur)):
        want = list(roster_sites[name].get("defs") or [])
        try:
            got = defs_of(ast.parse(sources[name]))
        except Exception:                                      # noqa: BLE001
            got = None
        missing = sorted(set(want) - set(got or []) - set(allow_drop)) if got is not None else ["<解析失败>"]
        added = sorted(set(got or []) - set(want)) if got is not None else []
        rows.append({"file": name, "defs_want": want, "defs_now": got,
                     "dropped": sorted(set(want) - set(got or [])) if got is not None else [],
                     "missing": missing, "added": added,
                     "same": (got is not None and not missing and not added)})
    return rows


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


def run_static(baseline, roster_path=None):
    """E1 / E2 / E2b / E2c / E5。返回 (rows, red_list, ctx)。

    ctx = {sites, cur, wired, roster_ok, adopted, n_un, denom_ok}；`roster_ok=False` 时
    主流程必须 rc=2（名册缺失 ⇒ E2b 失明，不得读成「全部已接入」）。"""
    rows, red = [], []
    sources = read_sources(TEST_DIR)
    ct = CONTRIB.read_text(encoding="utf-8") if CONTRIB.is_file() else ""
    ok1, miss1 = e1_contrib_declares(ct)
    rows.append(["E1 回退被声明", "PASS" if ok1 else "RED",
                 "四要素齐" if ok1 else "缺=%s" % ",".join(miss1)])
    if not ok1:
        red.append("E1")

    cur, broken = scan_sources(sources)
    if not cur:
        rows.append(["E2 唯一实现（棘轮）", "UNVERIFIED",
                     "分母为 0：AST 现读没有任何 launch 站点（调用点归零 ≠ 全部已接入）"])
        return rows, red, {"denom_ok": False}
    sites = sorted(cur)
    n_un = len(sites)
    half = wired_names(sources, sites)
    rs, why = load_roster(roster_path)
    roster_ok = rs is not None
    adopted = (len(rs["sites"]) - n_un) if roster_ok else None
    if n_un > baseline:
        rows.append(["E2 唯一实现（棘轮）", "RED",
                     "未接入 %d > 基线 %d ⇒ 上升了（新增的站点必须走 browser_engine）；"
                     "清单见 --json" % (n_un, baseline)])
        red.append("E2")
    else:
        rows.append(["E2 唯一实现（棘轮）", "PASS",
                     "回退余量 %d（基线 %d，只降不升）" % (n_un, baseline)])
    if not roster_ok:
        rows.append(["E2b 余量有主", "UNVERIFIED", why])
    else:
        bad = e2b(rs["sites"], cur, sources)
        rows.append(["E2b 余量有主", "RED" if bad else "PASS",
                     ("红因=%s" % "；".join(bad)) if bad
                     else "已接 %d/%d 件逐件三条件齐（在册 ∧ import ∧ 裸 launch==0）"
                          % (adopted, len(rs["sites"]))])
        if bad:
            red.append("E2b")
    rows.append(["E2c 接入即无残留", "RED" if half else "PASS",
                 ("半接入残留=%s（既含裸 launch 又已 import ⇒ 迁移没做完）" % ",".join(half))
                 if half else "半接入残留 0 件"])
    if half:
        red.append("E2c")
    if broken:
        rows.append(["E2d 取数面无隐身件", "RED", "读不到/解析失败被跳过=%s" % ",".join(broken)])
        red.append("E2d")

    rt = REQS.read_text(encoding="utf-8") if REQS.is_file() else ""
    ok5, why5 = e5_contrib_deps(ct, rt)
    rows.append(["E5 依赖面不虚报", "PASS" if ok5 else "RED", why5])
    if not ok5:
        red.append("E5")
    return rows, red, {"sites": sites, "cur": cur, "sources": sources, "wired": half,
                       "roster_ok": roster_ok, "adopted": adopted, "n_un": n_un,
                       "denom_ok": True, "roster_n": len(rs["sites"]) if roster_ok else 0}


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
    src_real = read_sources(TEST_DIR)
    eq("半接入残留只能是 sites 的子集",
       set(wired_names(src_real, sites)) <= set(sites), True)
    # ── r98 新腿①：换尺取证 = 与**被替换掉的旧子串规则**独立复算交叉，不是拿新尺自比新尺 ──
    ast_face = set(scan_sources(src_real)[0])

    def old_substring_face():
        return {p.name for p in sorted(TEST_DIR.glob("*.py"))
                if p.name not in SELF_NAMES
                and "chromium.launch(" in p.read_text(encoding="utf-8", errors="replace")}

    eq("取数面切换等价：AST 集 ⇄ 旧子串集 对称差为空（两把尺各自独立复算）",
       ast_face ^ old_substring_face(), set())
    COMMENT_ONLY = "def f():\n    # chromium.launch( 只是注释\n    pass\n"
    eq("变异体 旧子串规则确实会虚增分母（夹具：注释里写该串的子串面会认）",
       "chromium.launch(" in COMMENT_ONLY, True)
    eq("  同一夹具 AST 面判零（证明 AST 那条不是恒真）",
       launch_points(ast.parse(COMMENT_ONLY)), 0)
    eq("名册缺失 ⇒ load_roster 返回 (None, 原因)，不得返回空名册当「无需核对」",
       load_roster(str(TEST_DIR / "__no_such_roster__.json"))[0], None)
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

    # ── r98 新腿②：E2b/E2c/census/门面行。夹具走内存字典，不往受管根造文件 ──
    FX = {
        "done_ok.py": "from browser_engine import launch as be_launch\n"
                      "def run(pw):\n    b, face = be_launch(pw, label='x')\n    return b\n",
        "half.py": "from browser_engine import launch as be_launch\n"
                   "def run(pw):\n    return pw.chromium.launch(channel='msedge')\n",
        "noreentry.py": "def run(pw):\n    return None\n",
        "still_site.py": "def run(pw):\n    return pw.chromium.launch()\n",
    }
    FX_ROSTER = {n: {"launch_points": 1, "defs": ["run"], "imports_be": False}
                 for n in ("done_ok.py", "half.py", "noreentry.py", "still_site.py", "gone.py")}
    fx_cur, fx_broken = scan_sources(FX)
    fx_bad = e2b(FX_ROSTER, fx_cur, FX)
    eq("E2b 正例：接完的件（在册 ∧ import ∧ 裸 launch==0）不进红因",
       any("done_ok" in x for x in fx_bad), False)
    eq("E2b 反例一：靠**删文件**离开分母必须点名（删除/改名不等于接入）",
       any("gone.py" in x and "文件不在" in x for x in fx_bad), True)
    eq("E2b 反例二：裸 launch 归零却没引统一入口（改名躲分母）必须点名",
       any("noreentry" in x and "没引统一入口" in x for x in fx_bad), True)
    eq("E2c 反例：只 import 不删回退的半接入件必须被现读抓到",
       wired_names(FX, sorted(fx_cur)) == ["half.py"], True)
    eq("E2c 正例：真接完的件不在半接入名单里（不是恒抓）",
       "done_ok.py" in wired_names(FX, sorted(fx_cur)), False)
    keep_e2b = globals()["e2b"]
    globals()["e2b"] = lambda rs_, cu, so: [
        "%s(仍存裸 launch)" % n for n in sorted(set(rs_) - set(cu))
        if so.get(n) and launch_points(ast.parse(so[n]))]
    eq("变异体 摘掉「文件必须在盘」一条件 ⇒ gone.py 消失被放行（证明那条腿在咬）",
       any("gone.py" in x for x in globals()["e2b"](FX_ROSTER, fx_cur, FX)), False)
    globals()["e2b"] = keep_e2b
    eq("还原后同一输入重新判红（证明上面动的是尺不是期望值）",
       any("gone.py" in x and "文件不在" in x for x in keep_e2b(FX_ROSTER, fx_cur, FX)), True)
    FX2 = dict(FX)
    FX2["defs_lost.py"] = "from browser_engine import launch as be_launch\n" \
                          "def run(pw):\n    return be_launch(pw)\n"
    FX_ROSTER2 = dict(FX_ROSTER)
    FX_ROSTER2["defs_lost.py"] = {"launch_points": 1, "defs": ["run", "vanished_helper"],
                                  "imports_be": False}
    fx2_cur, _ = scan_sources(FX2)
    cs = {r["file"]: r["same"] for r in census(FX_ROSTER2, fx2_cur, FX2)}
    eq("census 正例：defs 未变的迁移件判零差", cs.get("done_ok.py"), True)
    eq("census 反例：def 被吞掉的件必须被点名（py_compile 拦不住的那一形）",
       cs.get("defs_lost.py"), False)
    MIG = "from browser_engine import launch as be_launch\ndef main(pw):\n    return be_launch(pw)\n"
    MIG_ROSTER = {"m1.py": {"launch_points": 1, "defs": ["launch", "main"], "imports_be": False},
                  "m2.py": {"launch_points": 1, "defs": ["launch", "main", "lost_buddy"],
                            "imports_be": False}}
    cs3 = {r["file"]: r["same"] for r in census(MIG_ROSTER, {}, {"m1.py": MIG, "m2.py": MIG})}
    eq("census 合法形态：只删掉手写 launch helper 不算漂移（否则第一件迁移就 self-ban）",
       cs3.get("m1.py"), True)
    eq("census 反例：连 launch 以外少了一个符号 ⇒ 必须点名", cs3.get("m2.py"), False)
    eq("变异体 取消 allow_drop ⇒ 合法迁移件也被判漂移（证明豁免窄到只有一个符号）",
       census(MIG_ROSTER, {}, {"m1.py": MIG}, allow_drop=())[0]["same"], False)
    vctx = {"n_un": 24, "adopted": 8, "roster_n": 32, "denom_ok": True}
    vline = build_verdict([], vctx, 32, " 本机面=msedge(channel)(154.0.4258.53)")
    eq("门面行同时带基线/起点/已接/核对态（r96 那行只能印 0/32 且永远升不动）",
       ("回退余量 24" in vline and "起点 32 已接 8" in vline
        and "名册核对=OK" in vline), True)
    eq("门面行不写成 `N/M` 分数（会被读成「M 项已接完 M 项」）", "/32" in vline, False)
    eq("门面行在电池截断线内 ⇒ 不带自曝标记", verdict_overflow(vline), False)
    vlong = build_verdict([], vctx, 32, " 本机面=" + "chromium" * 18)
    eq("变异体 输入撑破 110 时行内必须自曝（不静默截尾）", verdict_overflow(vlong), True)
    eq("  还原成常规输入后同一判据回绿（证明上面量的是尺不是夹具）",
       verdict_overflow(build_verdict([], vctx, 32, " 本机面=msedge(channel)(154)")), False)
    eq("名册缺失时门面行标「核对=缺失」而不是把已接数伪装成 0",
       "名册核对=缺失" in build_verdict([], {"n_un": 32, "adopted": None, "denom_ok": True},
                                       32, ""), True)

    bad = [(n, g, w) for n, g, w in cases if g != w]
    for n, g, w in bad:
        print("  用例不符: %s ｜ got=%r want=%r" % (n, g, w))
    print("BROWSER-ENGINE-SELFTEST-%s（%d/%d 条）"
          % ("PASS" if not bad else "FAIL", len(cases) - len(bad), len(cases)))
    return 1 if bad else 0


FOLD_LIMIT = 110       # run_all_suites.py:804 的 `line[:110]` —— 超出的部分在受理面上不存在
OVER_MARK = "｜⚠行宽超电池截断线"


def build_verdict(red, ctx, baseline, face_line):
    """门面行：电池只留末条判定行并按 `line[:110]` 截断 ⇒ 身份必须落进这一行的前 110 字符。

    不做"聪明折叠"（截掉谁都是静默丢读数）：超线就**在行内自曝**，由 main 把 E6 判红，
    逼人把文案改短 —— 与本仓「身份/档位必须落在被电池保留的那一行里」同一条纪律。"""
    head = "BROWSER-ENGINE-%s: 回退余量 %d（基线 %d" % (
        "FAIL" if red else "PASS", ctx.get("n_un", 0), baseline)
    ad = ctx.get("adopted")
    if ad is None:
        head += "）｜名册核对=缺失"
    else:
        head += "｜起点 %d 已接 %d，名册核对=%s）" % (
            ctx.get("roster_n", 0), ad, "红" if "E2b" in red else "OK")
    line = (head + "｜E1 %s｜E5 %s%s"
            % ("红" if "E1" in red else "绿", "红" if "E5" in red else "绿", face_line)
            + ("" if not red else " 红因=%s" % ",".join(sorted(red))))
    if len(line) > FOLD_LIMIT:
        line += OVER_MARK
    return line


def verdict_overflow(line):
    return OVER_MARK in line


def write_roster(path):
    cur, broken = scan_dir(TEST_DIR)
    if broken:
        print("  拒写名册：解析失败件=%s ⇒ 名册会带着隐身件出生" % ",".join(broken))
        return 1
    payload = {"written_by": "browser_engine_declare_check.py --write-roster",
               "face": "AST(*.chromium.launch())", "site_count": len(cur),
               "call_points": sum(v["launch_points"] for v in cur.values()), "sites": cur}
    tgt = Path(path)
    tgt.parent.mkdir(parents=True, exist_ok=True)
    tgt.write_bytes(json.dumps(payload, ensure_ascii=False, indent=1).encode("utf-8"))
    back = json.loads(tgt.read_bytes().decode("utf-8"))
    ok = sorted(back["sites"]) == sorted(cur)
    print("BROWSER-ENGINE-ROSTER-%s: %s｜站点 %d 件｜调用点 %d 处｜载回对账=%s"
          % ("WRITTEN" if ok else "FAIL", tgt.name, payload["site_count"],
             payload["call_points"], "OK" if ok else "不符"))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--machine", action="store_true", help="真起一次浏览器取本机面（E3/E4）")
    ap.add_argument("--baseline", type=int, default=24,
                    help="E2 棘轮上界：仍含裸 chromium.launch 的站点数"
                         "（r96 立 32 → r98 迁移 8 件后下调到实测余量 24，只降不升）")
    ap.add_argument("--json", default="")
    ap.add_argument("--roster", default="", help="覆盖起点名册路径（selftest/演习用）")
    ap.add_argument("--write-roster", action="store_true",
                    help="按现读生成起点名册（只应在迁移动手之前跑）")
    ap.add_argument("--census", action="store_true",
                    help="逐件 defs 符号表对名册：迁移件的防「Edit 吞 def 行」验收腿")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.write_roster:
        return write_roster(a.roster or ROSTER)

    rows, red, ctx = run_static(a.baseline, a.roster or None)
    if not ctx.get("denom_ok", True):
        print("BROWSER-ENGINE-UNVERIFIED: E2 分母为 0（AST 现读没有 launch 站点 ≠ 全部已接入）")
        return 2
    if a.census:
        rs, why = load_roster(a.roster or None)
        if rs is None:
            print("BROWSER-ENGINE-UNVERIFIED: %s" % why)
            return 2
        rows2 = census(rs["sites"], ctx["cur"], ctx["sources"])
        drift = [r for r in rows2 if not r["same"]]
        for r in rows2:
            if r["same"]:
                what = ("零差" if not r["dropped"]
                        else "只删 %s（迁移有意删的那个手写 helper）" % ",".join(r["dropped"]))
            else:
                what = "漂移 少=%s 多=%s" % (r["missing"], r["added"])
            print("  %-28s defs %s" % (r["file"], what))
        print("-" * 100)
        print("BROWSER-ENGINE-CENSUS-%s: 核对 %d 件｜defs 漂移 %d 件%s"
              % ("FAIL" if drift else "PASS", len(rows2), len(drift),
                 "" if not drift else " ⇒ 按 memory/AGENTS.md 排障手册把被吞行按原字恢复"))
        return 1 if drift else 0

    face_line = ""
    if a.machine:
        face, note = run_machine()
        if face is None:
            rows.append(["E3/E4 机器面", "UNVERIFIED", note])
            print("BROWSER-ENGINE-UNVERIFIED: %s" % note)
            return 2
        ok4 = note.startswith("OK")
        rows.append(["E3/E4 机器面", "PASS" if ok4 else "RED",
                     "本机面=%s ｜ %s" % (face, note)])
        if not ok4:
            red.append("E4")
        face_line = " 本机面=%s" % be_short(face)
    if not ctx.get("roster_ok", True):
        print("BROWSER-ENGINE-UNVERIFIED: 起点名册不可用 ⇒ E2b 失明，不得读成「全部已接入」")
        for r in rows:
            print("  %-22s %-11s %s" % (r[0], r[1], r[2]))
        return 2
    for r in rows:
        print("  %-22s %-11s %s" % (r[0], r[1], r[2]))
    print("-" * 100)
    line = build_verdict(red, ctx, a.baseline, face_line)
    if verdict_overflow(line):
        red = sorted(set(red) | {"E6行宽"})
        line = build_verdict(red, ctx, a.baseline, face_line)
    print(line)
    if a.json:
        Path(a.json).write_bytes(json.dumps(
            {"baseline": a.baseline, "sites": ctx["sites"], "half_wired": ctx["wired"],
             "roster_n": ctx["roster_n"], "adopted": ctx["adopted"],
             "unmigrated": ctx["n_un"], "rows": rows, "red": red,
             "machine_face": face_line.strip(), "verdict_line_len": len(line)},
            ensure_ascii=False, indent=1).encode("utf-8"))
    return 1 if red else 0


if __name__ == "__main__":
    sys.exit(main())
