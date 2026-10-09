#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""JS 语法守卫（r67 新增）—— 逐文件 `node --check`，双份副本同验。

为什么这一面此前没人量：97 道电池里没有任何静态语法判据（更正注 r101：97 是 r67 当日值，而"没有任何"
这句现已不成立 —— 本件自己就在电池里，条数由 `repo_config_check.battery_count()` 现算、本文件不抄数；
G20 就是为这类**陈旧排除性声称**立的。原始取证保留：`grep -l "node --check" _test/*.js/py` 当时实测 0 命中），
20 个 `src/js/*.js` 的语法错误只能被浏览器判据**间接**发现 —— 而浏览器判据一崩，
报出来的是"某个断言超时"，不是"哪个文件的第几行parse 不掉"。对标侧 peers 有 linter 配置仅 2/16
（分母取本轮 counted=16），所以本件不是去追"业界都有 lint"，而是把**最低成本的那一半**（可解析性）
钉住：零依赖、零构建、不吃 `size_budget` 关键路径（判据不在 src/ 里）。

覆盖面 = 语法与严格模式可解析性（含 ESM 之外的经典脚本与模块两种目标）。
不覆盖面 = 代码风格 / 未定义变量 / 死代码 / 任何 lint 规则 ⇒ **不得对外宣称"lint 已就位"**，
门面行逐字携带这句话，就是防止后来人把这条守卫读成 linter。

用法：python _test/js_syntax_check.py [--selftest]
退出码：0=全过 1=有文件 parse 不掉（点名文件与行） 2=环境未验证（node 不可用 ⇒ 不判绿）
"""
import argparse
import shutil
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
FACES = ("src/js", "deploy/xinyu/js")


def js_files(root=ROOT):
    """两面的全部 .js（按盘面枚举，禁手抄清单——抄来的清单正是漏文件的成因）。"""
    out = []
    for face in FACES:
        d = Path(root) / face
        if not d.is_dir():
            continue
        out.extend(sorted(d.glob("*.js")))
    return out


ESM_RE = re.compile(r"^(?:\s{0,4})(?:import|export)[\s*{]", re.M)


def check_one(path):
    """返回 (ok, detail, kind)。`--check` 只判可解析性，不产生副作用。

    ⚠️ r68 实测（node v24.16）：`node --check` 对**含 ESM 语法的 `.js`** 静默返回 0，
    连语法真坏的文件也放行——`import x from "y";` + `function oops( {` 的 .js → rc=0，
    同内容改名 `.mjs` → 抓到错。⇒ 摘掉本分支后 selftest 的「坏 ESM 仍须点名」腿当场翻红（变异已验）。
    所以这不是"防误报"，是**防守卫静默空转**：ESM 形态一律落到临时 `.mjs` 再检。
    """
    src = Path(path).read_text("utf-8", errors="replace")
    kind = "module" if ESM_RE.search(src) else "script"
    target = str(path)
    tmp = None
    if kind == "module":
        with tempfile.NamedTemporaryFile("wb", suffix=".mjs", delete=False) as fh:
            fh.write(src.encode("utf-8"))
            tmp = Path(fh.name)
        target = str(tmp)
    try:
        r = subprocess.run(["node", "--check", target], capture_output=True, timeout=60)
    finally:
        if tmp:
            tmp.unlink(missing_ok=True)
    err = (r.stderr or b"").decode("utf-8", errors="replace").strip()
    return r.returncode == 0, err.splitlines()[-1] if err else "", kind


def _label(path):
    """仓内给相对路径，仓外（selftest 的临时件）给绝对路径。
    `Path.relative_to` 对仓外路径直接抛 ValueError，会让 selftest 崩在打印上而非给出结论。"""
    try:
        return str(Path(path).relative_to(ROOT))
    except ValueError:
        return str(path)


def check_files(paths):
    """纯驱动器：输入=文件清单，输出=(通过数, 失败明细)。selftest 直接打它。"""
    fails = []
    ok = 0
    kinds = {"script": 0, "module": 0}
    for p in paths:
        try:
            good, detail, kind = check_one(p)
        except OSError as e:
            fails.append("%s :: 读取失败(保守按 script 判，不静默跳过) %s" % (_label(p), str(e)[:80]))
            kinds["script"] += 1
            continue
        kinds[kind] = kinds.get(kind, 0) + 1
        if good:
            ok += 1
        else:
            fails.append("%s[%s] :: %s" % (_label(p), kind, detail[:150]))
    return ok, fails, kinds


def selftest():
    bad = []
    if shutil.which("node") is None:
        print("JS-SYNTAX-UNVERIFIED selftest 需要 node，本机未找到")
        return 2
    with tempfile.TemporaryDirectory() as td:
        good = Path(td) / "ok.js"
        good.write_text("const a = 1;\nif (a) { console.log(a); }\n", encoding="utf-8")
        broken = Path(td) / "bad.js"
        broken.write_text("function oops( {\n", encoding="utf-8")
        unterminated = Path(td) / "unterminated.js"
        unterminated.write_text("const s = \"abc\n", encoding="utf-8")
        # 反例①：语法真错必须被点名（红因落在被测文件上，不是环境错）
        okn, fails, _k = check_files([broken])
        if okn != 1 - 1 or not fails or "bad.js" not in fails[0]:
            bad.append("反例①未咬：坏文件没被点名 ok=%d fails=%s" % (okn, fails))
        # 反例②：未闭合字符串同判（同一守卫的第二种真实失效形态）
        ok2, f2, _k2 = check_files([unterminated])
        if ok2 != 0 or not f2:
            bad.append("反例②未咬：未闭合字符串被判通过")
        # 正例：合规文件必须通过（否则得到一条永红判据）
        ok3, f3, _k3 = check_files([good])
        if ok3 != 1 or f3:
            bad.append("正例失败：合规文件被判红 %s" % f3)
        # r68 专属用例①：含顶层 import 的 .js 必须 PASS（旧写法在此必判红＝项目一转模块守卫先杀人）
        esm = Path(td) / "esm.js"
        esm.write_text(chr(10).join(["export const z = 1;", ""]) , encoding="utf-8")
        okE, fE, kE = check_files([esm])
        if okE != 1 or fE:
            bad.append("ESM 误判：含 import 的 .js 被判红（CommonJS 目标解析）%s" % fE)
        if kE.get("module") != 1:
            bad.append("ESM 未识别：kind 计数没把它归进 module ⇒ 临时 .mjs 那条路没走，等于没修 %s" % kE)
        # r68 专属用例②：坏掉的 module 件仍必须 FAIL 并点名（防把"绕过检查"当成修法）
        badesm = Path(td) / "badesm.js"
        badesm.write_text(chr(10).join(["export const z = 1;", "function oops( {", ""]), encoding="utf-8")
        okB, fB, kB = check_files([badesm])
        if okB != 0 or not fB or "badesm.js" not in fB[0] or "module" not in fB[0]:
            bad.append("ESM 反向腿未咬：语法真坏的 module 件没被点名 ok=%d fails=%s" % (okB, fB))
        # 边界：零文件不得判"通过"（零输入没有分母）
        ok4, f4, _k4 = check_files([])
        if ok4 != 0:
            bad.append("零输入给出非零通过数 %d" % ok4)
    n = len(js_files())
    if n < 20:
        bad.append("覆盖面可疑缩小：只枚举到 %d 个 js 文件（FACES=%s 拼错即静默少测）" % (n, list(FACES)))
    total = 7   # r68 加两条 ESM 专属用例（含 import 的 .js 不得误判／坏 module 件仍须点名）
    for x in bad:
        print("  SELFTEST-FAIL " + x)
    print("JS-SYNTAX-SELFTEST: %d/%d（坏文件点名 + 未闭合字符串 + 合规正例 + 零输入 + 枚举下限 + ESM 不误判 + 坏 ESM 仍红）"
          % (total - len(bad), total))
    return 0 if not bad else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if shutil.which("node") is None:
        print("JS-SYNTAX-UNVERIFIED node 不可用 ⇒ 本判据未验证，不记通过")
        return 2
    files = js_files()
    if not files:
        print("JS-SYNTAX-UNVERIFIED 枚举到 0 个 js 文件（分母为空不判绿）")
        return 2
    ok, fails, kinds = check_files(files)
    line = ("JS-SYNTAX-%s: 两面 %d 个 js 逐文件 node --check 通过 %d 失败 %d"
            % ("PASS" if not fails else "FAIL", len(files), ok, len(fails)))
    line += ("｜覆盖面=语法与严格模式可解析性(script/module 双目标，module 走临时 .mjs)；"
             "不覆盖面=风格/未定义变量/lint 规则（禁读作 linter 已就位）"
             "｜script=%d module=%d｜FACES=%s"
             % (kinds.get("script", 0), kinds.get("module", 0), ",".join(FACES)))
    for f in fails:
        print("  · FAIL " + f)
    print(line)
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
