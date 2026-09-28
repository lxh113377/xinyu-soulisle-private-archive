# -*- coding: utf-8 -*-
"""r41 in-build 测试资产守卫：把「构建自带门禁」这件事从"我今天跑了 mvn test"变成常驻判据。

为什么需要（对标定出来的真差距）：2026-09-27 实测 16 个参照仓里 **9 家有 in-build 单测**
（连 ★1 的 Java 同栈垂类 MoodChat 都有 Spring 脚手架），我方 `server/src` 下 JUnit 用例数
实测为 **0**，而 AGENTS.md 决策 #1 把「强类型 + 可单测（36 条评测可做成 JUnit）」列为选 Java 的
三条真实理由之一 ⇒ 那句话从 2026-09-20 挂到 09-27 没有产物支撑（同族：文案先行、代码未追）。

本件**不**跑 mvn（腾讯云镜像实测会 514 Frequency Capped，把第三方限速接进阻断链=天天假红），
也**不**复刻跨端对账（那是 engine_consistency_check 的活，复刻就长成 M5⑥「同一判断两处实现」）。
它盯的是下面这些**会让 in-build 门禁静默失效**的事（条数以本列表为准，标题不抄数字——
在别处抄过一次"四件"，加到 T7 时这行就没人回来改，成了文档自己的假账）：
  T1 用例真的存在：surefire 命名约定下的测试文件数与 @Test 数各达下限（零输入绝不判绿）
  T2 依赖真的在位：pom 声明 spring-boot-starter-test 且 scope=test
  T3 前提真的成立：surefire workingDirectory 指到仓库根（词表 SSOT 按 ./src/ 解析，
     不指则所有加载词表的用例在构建期以"路径不存在"红 —— 那是**前提**，不是可选项）
  T4 接线真的没断：ci.yml 的 java-build job 里 `mvn ... package` 那一步**不得带 -DskipTests**
     （带了这个 in-build 门禁就在受理面上静默消失，而本地看还是"CI 全绿"）
  T5 分母非空：main 侧类数 > 0（扫错目录会让 T1 的"0 用例"看起来完全正常）
  T6 覆盖率门本体在位：jacoco + check 目标 + **LINE 与 BRANCH 两路阈值**（r77 起缺一路即判红；
     只守 LINE 会放行"三元表达式另一半从没走过"——r76 的门就是 91.93% 行覆盖配 83.11% 分支覆盖）
  T7 门在链上：check 绑 verify 相位且 CI 真的跑 `mvn verify`（写成 package 则这道门一次也不会执行）

退出码：0=JAVA-TEST-GUARD-PASS 1=判红 2=环境不可达（无 pom/无 ci.yml ⇒ 记 UNVERIFIED，不判绿）
用法：python _test/java_test_guard.py [--selftest] [--json]
"""
import argparse
import json
import re
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_MAIN = ROOT / "server" / "src" / "main" / "java"
SRC_TEST = ROOT / "server" / "src" / "test" / "java"
POM = ROOT / "server" / "pom.xml"
CIYML = ROOT / ".github" / "workflows" / "ci.yml"

# 下限 = 09-27 实测值向下取整留出余量（无余量的地板等于冻结增长：加用例不会红，删用例会红）
# r77 随实测抬尺：现测 11 件 / 82 用例 ⇒ 取 8 / 70（余量 3 件 / 12 用例）。
# 抬之前是 3 / 24 —— 那是"反空不反缩"的下限，删掉一半用例也不会红，起不到棘轮作用。
FILE_FLOOR = 8
METHOD_FLOOR = 70

# surefire 默认命名约定：Test* / *Test / *Tests / *TestCase（与 maven-surefire 文档一致）
SUREFIRE_NAME = re.compile(r"(?:^|/)(?:Test[^/]*|[^/]*(?:Test|Tests|TestCase))\.java$")
TEST_ANN = re.compile(r"^\s*@Test\b", re.M)
ASSERTISH = re.compile(r"\b(?:assert[A-Z]\w*|fail\s*\(|assertThrows|assertDoesNotThrow)")


def _read(p):
    return p.read_text("utf-8", errors="replace") if p.exists() else ""


def scan_tests(test_root, main_root):
    """纯函数：只吃路径，便于 --selftest 用合成夹具喂正反例（不碰真实仓库）。"""
    files = []
    methods = 0
    no_assert = []
    if test_root.exists():
        for p in sorted(test_root.rglob("*.java")):
            rel = str(p.relative_to(test_root)).replace("\\", "/")
            if not SUREFIRE_NAME.search("/" + rel):
                continue
            body = _read(p)
            n = len(TEST_ANN.findall(body))
            methods += n
            files.append(rel)
            if n and not ASSERTISH.search(body):
                no_assert.append(rel)
    main_classes = len(list(main_root.rglob("*.java"))) if main_root.exists() else -1
    return {"files": files, "methods": methods, "no_assert": no_assert,
            "main_classes": main_classes}


def check_pom(pom_text):
    has_dep = bool(re.search(r"spring-boot-starter-test", pom_text)) \
        and bool(re.search(r"<scope>test</scope>", pom_text))
    has_workdir = bool(re.search(r"<workingDirectory>\$\{project\.basedir\}/\.\.</workingDirectory>",
                                 pom_text))
    return has_dep, has_workdir


def check_ci_wiring(yml_text):
    """java-build job 的 package 步骤不得带 -DskipTests；找不到该步 = 门禁没接线。"""
    m = re.search(r"^  java-build:(.*?)^  [a-z0-9-]+:\s*$", yml_text, re.S | re.M)
    if not m:
        return False, "java-build job 未找到"
    block = m.group(1)
    runs = re.findall(r"mvn[^\n]*", block)
    pkg = [r for r in runs if "package" in r or "verify" in r or "test" in r]
    if not pkg:
        return False, "java-build 里没有任何 mvn 构建步"
    skipped = [r for r in pkg if "skipTests" in r or "maven.test.skip" in r]
    if skipped:
        return False, "构建步带跳测: " + skipped[0].strip()
    return True, pkg[0].strip()[:60]


JACOCO_PLUGIN = re.compile(r"<artifactId>jacoco-maven-plugin</artifactId>")
JACOCO_CHECK_GOAL = re.compile(r"<goal>check</goal>")
JACOCO_CHECK_AT_VERIFY = re.compile(r"<phase>verify</phase>[\s\S]{0,240}?<goal>check</goal>")
MVN_VERIFY = re.compile(r"mvn[^\n]*\bverify\b")


JACOCO_LIMIT = re.compile(r"<limit>\s*<counter>(\w+)</counter>.*?"
                          r"<minimum>\s*(0?\.\d+|1(?:\.0+)?)\s*</minimum>.*?</limit>", re.S | re.M)


def check_coverage_gate(pom_text):
    """T6 覆盖率门本体：jacoco 在位 ∧ 有 check 目标 ∧ **LINE 与 BRANCH 两路阈值都在**。

    只写 `prepare-agent`/`report` 的仓**量得到但不会拦** ⇒ 不算门（与 r75 同址尺同一口径：
    "存在性 ≠ 行为"，必须能让构建失败）。

    r77 补 BRANCH 这一路的理由（一手）：r76 的门只量 LINE，报的是 91.93%，
    而同一批代码的分支覆盖只有 **83.11%** —— 一行 `a ? b : c` 在 LINE 里是 1 行，
    在行为上是 2 个分支。只守 LINE 的门会放行"整段三元表达式从没走过另一半"这种洞，
    而本项目最要命的那几处（危机短路、上游回落、鉴权放行/拦截）恰好全是三元与 `&&` 短路。
    """
    text = pom_text or ""
    if not JACOCO_PLUGIN.search(text):
        return False, "pom 里没有 jacoco-maven-plugin"
    if not JACOCO_CHECK_GOAL.search(text):
        return False, "jacoco 只有 report（量得到、不拦人）⇒ 缺 check 目标"
    limits = {counter: minimum for counter, minimum in JACOCO_LIMIT.findall(text)}
    if not limits:
        return False, "check 目标在但没有 <minimum> 数值"
    missing = [c for c in ("LINE", "BRANCH") if c not in limits]
    if missing:
        return False, "覆盖率门缺 %s 阈值（只有 LINE 不构成门：一行三元算 1 行却有 2 个分支，r77）" \
            % "/".join(missing)
    return True, "LINE %s / BRANCH %s" % (limits["LINE"], limits["BRANCH"])


def check_gate_on_chain(yml_text):
    """T7 门必须在链上：check 绑 verify 相位，CI 若仍跑 `package` 则这道门**永远不会执行**。

    这条与 r41 的「CI 不得 -DskipTests」同族——那次是门禁被跳过，这次是门禁相位不触发；
    两者都会让"本地全绿 + CI 也绿 + 门其实没装"同时成立。
    """
    m = re.search(r"^  java-build:(.*?)^  [a-z0-9-]+:\s*$", yml_text or "", re.S | re.M)
    if not m:
        return False, "java-build job 未找到"
    block = m.group(1)
    if MVN_VERIFY.search(block):
        return True, "CI 跑 verify（覆盖率门会被触发）"
    return False, "CI 未跑 verify ⇒ jacoco check（绑 verify 相位）永不执行"


# ---------------- T8 覆盖率读数（r78：把"具名缺口清单"接进阻断链） ----------------
# 动因（r77 报告 §3 建议 7）：门只报总比值，"还剩哪 4 个方法/哪 46 条指令没碰"从来没有名单，
# 于是下一轮要么盲补、要么干脆不补。**没有名单的缺口指标等于没有指标。**
JACOCO = ROOT / "server" / "target" / "site" / "jacoco" / "jacoco.xml"
COUNTER_FLOORS = {"LINE": 0.90, "BRANCH": 0.90, "METHOD": 0.90}


def _parse_jacoco(xml_text):
    """载具是**本机 mvn 生成**的 jacoco.xml；只拒 `<!ENTITY`（实体定义＝膨胀/外带的那一矢量），**允许 DOCTYPE**。

    两条一手代价写在这里：
    ① 不拒实体的话，畸形读数会让解析器抛错并被 except 吞成"未验"，一个坏 XML 就悄悄变成不红不绿；
    ② 但 DOCTYPE **不能**一起拒 —— 真件首行实测就是
       `<?xml …?><!DOCTYPE report PUBLIC "-//JACOCO//DTD Report 1.1//EN" "report.dtd">`，
       第一版连 DOCTYPE 一起拒 ⇒ 守卫把**真读数**判成未验（r78 落地当场撞上）。
       门禁拒绝真话，就是在逼下一轮虚报（同「Gate shape must admit the honest value」）。
    """
    if "<!ENTITY" in xml_text.upper():
        raise ValueError("jacoco.xml 含实体声明 ⇒ 拒解析（正常产物理应没有）")
    return ET.fromstring(xml_text)


def read_counters(xml_text):
    """纯函数：jacoco.xml → {counter 类型: (missed, covered)}。

    **只取 `<report>` 直属的 counter**——r77 一手代价：按"逐类求和 + 再加一次 missed"算分母
    造出一条假 drift（296/346 vs 真实 246/296），差点据此去"更正"一份本来写对了的报告。
    """
    out = {}
    for c in _parse_jacoco(xml_text).findall("counter"):
        m, cv = int(c.get("missed")), int(c.get("covered"))
        out[c.get("type")] = (m, cv)
    return out


def top_gaps(xml_text, k=3):
    """具名清单：还带着未覆盖分支/行的类，按 missed 分支降序，最多 k 条。"""
    root = _parse_jacoco(xml_text)
    rows = []
    for cls in root.iter("class"):
        mb = mc = ml = 0
        for c in cls.findall("counter"):
            if c.get("type") == "BRANCH":
                mb, mc = int(c.get("missed")), int(c.get("covered"))
            elif c.get("type") == "LINE":
                ml = int(c.get("missed"))
        if mb or ml:
            rows.append((mb, ml, mc, cls.get("name").split("/")[-1]))
    rows.sort(reverse=True)
    return ["%s(分支漏%d/%d·行漏%d)" % (r[3], r[0], r[0] + r[2], r[1]) for r in rows[:k]]


def jacoco_fresh(xml_path, src_root):
    """产物新鲜度：读数不得早于被测源码最新一次改动（否则那是"上一轮的现状"）。"""
    try:
        newest = max((p.stat().st_mtime for p in Path(src_root).rglob("*.java")), default=0)
    except OSError:
        return False
    try:
        return xml_path.stat().st_mtime >= newest
    except OSError:
        return False


def check_coverage_counters(counters, fresh):
    """返回 (状态, 是否判红, 值)。状态 ∈ {ok, red, unverified}；unverified 既不绿也不红。"""
    if not counters or not fresh:
        return ("unverified", False,
                "jacoco.xml %s ⇒ 未验（没跑过 mvn test / 产物比源码旧，禁止拿旧读数当现状）"
                % ("取不到" if not counters else "陈旧"))
    bad = []
    for name, floor in COUNTER_FLOORS.items():
        if name not in counters:
            return ("unverified", False, "jacoco 里没有 %s counter ⇒ 未验" % name)
        m, cv = counters[name]
        ratio = cv / (m + cv) if (m + cv) else 0.0
        if ratio < floor:
            bad.append("%s %.2f%%<%.0f%%" % (name, ratio * 100, floor * 100))
    vals = " ".join("%s=%.2f%%" % (n, counters[n][1] / (counters[n][0] + counters[n][1]) * 100)
                    for n in COUNTER_FLOORS if (counters[n][0] + counters[n][1]))
    if bad:
        return ("red", True, "低于下限：" + "、".join(bad) + "｜现读 " + vals)
    return ("ok", False, vals + "｜下限 " + "/".join("%d%%" % (f * 100) for f in COUNTER_FLOORS.values()))


def evaluate(test_root, main_root, pom_text, yml_text, jacoco_text=None, jacoco_fresh_flag=True,
             gaps=None):
    """返回 (rows, ok)。rows = [(判据, 通过?, 值/原因)]"""
    st = scan_tests(test_root, main_root)
    has_dep, has_workdir = check_pom(pom_text)
    wired, why = check_ci_wiring(yml_text)
    gate_ok, gate_why = check_coverage_gate(pom_text)
    chain_ok, chain_why = check_gate_on_chain(yml_text)
    rows = [
        ("T1a 测试文件数", len(st["files"]) >= FILE_FLOOR,
         "%d 件（下限 %d，余量 %d）" % (len(st["files"]), FILE_FLOOR, len(st["files"]) - FILE_FLOOR)),
        ("T1b @Test 数", st["methods"] >= METHOD_FLOOR,
         "%d 个（下限 %d，余量 %d）" % (st["methods"], METHOD_FLOOR, st["methods"] - METHOD_FLOOR)),
        ("T1c 零断言用例类", not st["no_assert"], st["no_assert"] or "无"),
        ("T2 starter-test 依赖", has_dep, "spring-boot-starter-test + scope=test"),
        ("T3 surefire workingDirectory", has_workdir, "须指向 ${project.basedir}/.. （词表 SSOT 前提）"),
        ("T4 CI 接线未断", wired, why),
        ("T5 分母非空", st["main_classes"] > 0, "main 侧 java 类 %d 个" % st["main_classes"]),
        ("T6 覆盖率门（jacoco check + 阈值）", gate_ok, gate_why),
        ("T7 覆盖率门在链上（CI 跑 verify）", chain_ok, chain_why),
    ]
    cov_state, gap_txt = "unverified", ""
    try:
        counters = read_counters(jacoco_text) if jacoco_text else {}
        gap_txt = "；".join(top_gaps(jacoco_text)) if counters else ""
        cov_state, cov_red, cov_val = check_coverage_counters(counters, jacoco_fresh_flag)
    except Exception as e:                      # 畸形读数不许静默变成"未验"再变成绿
        cov_state, cov_red, cov_val = "unverified", False, "jacoco 读数失败：%s" % str(e)[:70]
    rows.append(("T8 覆盖率读数 + 具名缺口", not cov_red,
                 cov_val + ("｜还带缺口的类：" + gap_txt if gap_txt else "")))
    return rows, all(r[1] for r in rows), st, cov_state


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return run_selftest()

    for p, name in ((POM, "pom.xml"), (CIYML, "ci.yml")):
        if not p.exists():
            print("JAVA-TEST-GUARD-UNVERIFIED: 取不到 %s ⇒ 不判绿" % name)
            return 2
    jtext, jfresh = "", True
    if JACOCO.exists():
        try:
            jtext = JACOCO.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            jtext = ""
            print("  ⚠️ jacoco.xml 读不动：%s" % str(e)[:60])
        jfresh = jacoco_fresh(JACOCO, SRC_MAIN)
    rows, ok, st, cov_state = evaluate(SRC_TEST, SRC_MAIN, _read(POM), _read(CIYML),
                                       jacoco_text=jtext, jacoco_fresh_flag=jfresh)
    for name, passed, val in rows:
        print("  %-26s %s  %s" % (name, "OK  " if passed else "FAIL", val))
    detail = "；".join("%s=%s" % (r[0].split()[0], r[2]) for r in rows)
    if ok and cov_state == "unverified":
        print("JAVA-TEST-GUARD-UNVERIFIED: 其余判据绿，但 T8 取不到/读数陈旧 ⇒ 覆盖率现状未验"
              "（跑 `mvn -B -f server/pom.xml test` 后复算；不判红也不判绿）")
        return 2
    if ok:
        t6 = next((r for r in rows if r[0].startswith("T6")), ("T6", False, "未取到"))
        t7 = next((r for r in rows if r[0].startswith("T7")), ("T7", False, "未取到"))
        print("JAVA-TEST-GUARD-PASS（in-build 单测 %d 件 / %d 用例，CI java-build 构建步未跳测，"
              "覆盖率门 %s｜%s｜链上 %s）" % (len(st["files"]), st["methods"],
                                        "在位" if t6[1] else "缺", t6[2],
                                        "是" if t7[1] else "否"))
        if a.json:
            print(json.dumps({"files": st["files"], "methods": st["methods"]}, ensure_ascii=False))
        return 0
    print("JAVA-TEST-GUARD-FAIL: %s ｜ 全量：%s" % (
        ", ".join(r[0] for r in rows if not r[1]), detail))
    return 1


# ---------------- 双向自证（正反例都必须在夹具里成立） ----------------
GOOD_POM = ("<dependency><artifactId>spring-boot-starter-test</artifactId>"
            "<scope>test</scope></dependency>"
            "<workingDirectory>${project.basedir}/..</workingDirectory>"
            "<plugin><artifactId>jacoco-maven-plugin</artifactId>"
            "<execution><phase>verify</phase><goals><goal>check</goal></goals>"
            "<configuration><rules><rule><limits>"
            "<limit><counter>LINE</counter><minimum>0.35</minimum></limit>"
            "<limit><counter>BRANCH</counter><minimum>0.35</minimum></limit>"
            "</limits></rule></rules></configuration></execution></plugin>")
# r77：只守 LINE 的门是"半个门"——夹具里单独造一个 LINE-only 的 pom，用来证明 T6 真的在看 BRANCH 那一路
BAD_POM_LINEONLY = GOOD_POM.replace(
    "<limit><counter>BRANCH</counter><minimum>0.35</minimum></limit>", "")
BAD_POM_NODEP = ("<workingDirectory>${project.basedir}/..</workingDirectory>"
                 "<plugin><artifactId>jacoco-maven-plugin</artifactId>"
                 "<execution><phase>verify</phase><goals><goal>check</goal></goals>"
                 "<configuration><rules><rule><limits>"
                 "<limit><counter>LINE</counter><minimum>0.35</minimum></limit>"
                 "<limit><counter>BRANCH</counter><minimum>0.35</minimum></limit>"
                 "</limits></rule></rules></configuration></execution></plugin>")
BAD_POM_NOWD = ("<dependency><artifactId>spring-boot-starter-test</artifactId>"
                "<scope>test</scope></dependency>"
                "<plugin><artifactId>jacoco-maven-plugin</artifactId>"
                "<execution><phase>verify</phase><goals><goal>check</goal></goals>"
                "<configuration><rules><rule><limits>"
                "<limit><counter>LINE</counter><minimum>0.35</minimum></limit>"
                "<limit><counter>BRANCH</counter><minimum>0.35</minimum></limit>"
                "</limits></rule></rules></configuration></execution></plugin>")
# r75 新增三条反例：它们都长得像"装了覆盖率门"，缺一件就让这道门永远不会拦人
BAD_POM_NOJACOCO = ("<dependency><artifactId>spring-boot-starter-test</artifactId>"
                    "<scope>test</scope></dependency>"
                    "<workingDirectory>${project.basedir}/..</workingDirectory>")
BAD_POM_REPORTONLY = ("<dependency><artifactId>spring-boot-starter-test</artifactId><scope>test</scope></dependency>"
                      "<workingDirectory>${project.basedir}/..</workingDirectory>"
                      "<artifactId>jacoco-maven-plugin</artifactId>"
                      "<goals><goal>prepare-agent</goal><goal>report</goal></goals>")
BAD_POM_NOTHRESH = ("<artifactId>spring-boot-starter-test</artifactId><scope>test</scope>"
                    "<workingDirectory>${project.basedir}/..</workingDirectory>"
                    "<artifactId>jacoco-maven-plugin</artifactId>"
                    "<phase>verify</phase><goals><goal>check</goal></goals>")
GOOD_CI = ("  java-build:\n    steps:\n      - run: mvn -B -ntp -f server/pom.xml verify\n  live-sync:\n")
BAD_CI_SKIP = ("  java-build:\n    steps:\n      - run: mvn -B -ntp -f server/pom.xml verify"
               " -DskipTests\n  live-sync:\n")
BAD_CI_NOJOB = "  other:\n    steps: []\n"
# 相位陷阱（r75 一手）：CI 仍跑 package ⇒ jacoco 的 check（绑 verify）一次也不会执行，
# 而 pom 里那道门看着齐全、本地 `mvn test` 也全绿。这条反例专门钉"门禁在不在链上"。
BAD_CI_PACKAGE = ("  java-build:\n    steps:\n      - run: mvn -B -ntp -f server/pom.xml package\n  live-sync:\n")

# T8 夹具（r78）：三路 counter 齐且过下限 / BRANCH 掉到 50% / "陷阱件"——类内 counter 故意与总 counter 不一致，
# 用来钉住"分母只许取 <report> 直属 counter"这条 r77 学来的口径（当年把 246/296 算成 296/346）。
GOOD_JACOCO = ('<report>'
               '<counter type="LINE" missed="5" covered="95"/>'
               '<counter type="BRANCH" missed="10" covered="90"/>'
               '<counter type="METHOD" missed="4" covered="96"/>'
               '<class name="com/x/Big"><counter type="BRANCH" missed="6" covered="94"/>'
               '<counter type="LINE" missed="5" covered="95"/></class>'
               '<class name="com/x/Small"><counter type="BRANCH" missed="4" covered="40"/></class>'
               '</report>')
BAD_JACOCO = ('<report>'
              '<counter type="LINE" missed="5" covered="95"/>'
              '<counter type="BRANCH" missed="50" covered="50"/>'
              '<counter type="METHOD" missed="4" covered="96"/>'
              '<class name="com/x/Big"><counter type="BRANCH" missed="50" covered="50"/></class>'
              '</report>')
TRAP_JACOCO = ('<report>'
               '<counter type="BRANCH" missed="10" covered="90"/>'
               '<class name="com/x/Trap"><counter type="BRANCH" missed="40" covered="40"/></class>'
               '<class name="com/x/Trap2"><counter type="BRANCH" missed="9" covered="81"/></class>'
               '</report>')


def _fixture(tmp, n_files, n_methods_each, main_classes=8, pom=None, ci=None):
    tr = Path(tmp) / "test" / "com" / "x"
    tr.mkdir(parents=True, exist_ok=True)
    (Path(tmp) / "main" / "com").mkdir(parents=True, exist_ok=True)
    for i in range(main_classes):
        (Path(tmp) / "main" / "com" / ("C%d.java" % i)).write_text("class C%d{}" % i, "utf-8")
    for i in range(n_files):
        body = "\n".join("@Test\n  void m%d() { assertEquals(1, 1); }" % j
                         for j in range(n_methods_each))
        (tr / ("Foo%dTest.java" % i)).write_text(
            "class Foo%dTest {\n  %s\n}\n" % (i, body), "utf-8")
    return (Path(tmp) / "test"), (Path(tmp) / "main"), \
        (pom if pom is not None else GOOD_POM), \
        (ci if ci is not None else GOOD_CI)


def run_selftest():
    cases = []
    with tempfile.TemporaryDirectory() as tmp:
        tr, mr, pom, ci = _fixture(tmp, FILE_FLOOR + 1, 12)  # 9 件 x 12 = 108 ≥ 下限 70（且件数也过）
        cases.append(("正例：下限齐 + 依赖在位 + 未跳测", evaluate(tr, mr, pom, ci)[1], True))

        tr2, mr2, _, _ = _fixture(str(Path(tmp) / "f2"), 0, 0)
        Path(tr2).mkdir(parents=True, exist_ok=True)
        cases.append(("反例①：零用例不得判绿", evaluate(tr2, mr2, pom, ci)[1], False))

        tr3, mr3, _, _ = _fixture(str(Path(tmp) / "f3"), FILE_FLOOR + 1, 1)   # 9 件 x 1 @Test = 9 < 下限 70
        cases.append(("反例②：文件够但用例数不足", evaluate(tr3, mr3, pom, ci)[1], False))

        # tr4 是"其余维度反例"的共用夹具：它自己必须是**全绿对照**，否则下面每一条的红
        # 都可能来自用例数不足而不是被审那一维（r77 抬下限后这条尤其重要，见点名E）
        tr4, mr4, _, _ = _fixture(str(Path(tmp) / "f4"), FILE_FLOOR, 10)
        cases.append(("点名E：tr4 共用夹具配合规 pom/CI 必须为真（不真则下方反例的红无法归因）",
                      evaluate(tr4, mr4, GOOD_POM, GOOD_CI)[1], True))
        cases.append(("反例③：pom 缺 starter-test", evaluate(tr4, mr4, BAD_POM_NODEP, ci)[1], False))
        cases.append(("反例④：pom 缺 workingDirectory", evaluate(tr4, mr4, BAD_POM_NOWD, ci)[1], False))
        cases.append(("反例⑤：CI 构建步带 -DskipTests", evaluate(tr4, mr4, pom, BAD_CI_SKIP)[1], False))
        cases.append(("反例⑥：CI 里没有 java-build job", evaluate(tr4, mr4, pom, BAD_CI_NOJOB)[1], False))
        cases.append(("反例⑦：main 侧扫空（分母为 0）",
                      evaluate(tr4, Path(str(Path(tmp) / "f4")) / "nomine", pom, ci)[1], False))
        # r75 覆盖率门：四形反例 + 两条单独点名（防"整体绿但这两行本来就恒真"）
        cases.append(("反例⑧：pom 根本没有 jacoco", evaluate(tr4, mr4, BAD_POM_NOJACOCO, ci)[1], False))
        cases.append(("反例⑨：jacoco 只有 prepare-agent/report（量得到、不拦人）",
                      evaluate(tr4, mr4, BAD_POM_REPORTONLY, ci)[1], False))
        cases.append(("反例⑩：有 check 目标但没有 <minimum> 阈值",
                      evaluate(tr4, mr4, BAD_POM_NOTHRESH, ci)[1], False))
        cases.append(("反例⑪：CI 仍跑 package ⇒ verify 相位的 check 永不执行",
                      evaluate(tr4, mr4, pom, BAD_CI_PACKAGE)[1], False))
        # r77：只守 LINE 的门放行"三元表达式另一半从没走过"，所以缺 BRANCH 必须单独判红
        cases.append(("反例⑫：pom 只有 LINE 阈值（缺 BRANCH 那一路）",
                      evaluate(tr4, mr4, BAD_POM_LINEONLY, ci)[1], False))
        ok_gate, why_gate = check_coverage_gate(pom)
        ok_chain, why_chain = check_gate_on_chain(ci)
        cases.append(("点名A：合规 pom 的 T6 必须真过（值=%s）" % why_gate, ok_gate, True))
        cases.append(("点名B：合规 CI 的 T7 必须真过（值=%s）" % why_chain, ok_chain, True))
        cases.append(("点名C：package-only CI 的 T7 必须单独为假（不许靠别的行凑绿）",
                      check_gate_on_chain(BAD_CI_PACKAGE)[0], False))
        cases.append(("点名D：report-only pom 的 T6 必须单独为假",
                      check_coverage_gate(BAD_POM_REPORTONLY)[0], False))
        # 红因点名：缺 BRANCH 的那条必须**因为 BRANCH** 而红，不能只是"整体为假"
        lineonly_ok, lineonly_why = check_coverage_gate(BAD_POM_LINEONLY)
        cases.append(("点名F：LINE-only pom 的 T6 为假且红因点名 BRANCH（实际=%s）" % lineonly_why,
                      (not lineonly_ok) and ("BRANCH" in lineonly_why), True))
        good_ok, good_why = check_coverage_gate(GOOD_POM)
        cases.append(("点名G：合规 pom 的 T6 回执必须同时带两路阈值（实际=%s）" % good_why,
                      good_ok and ("LINE" in good_why and "BRANCH" in good_why), True))

        # 边界：命名约定必须与 surefire 一致，否则"看起来有用例"是假的
        bad = Path(tmp) / "naming" / "com"
        bad.mkdir(parents=True, exist_ok=True)
        (bad / "Helper.java").write_text("@Test void a() { assertTrue(true); }", "utf-8")
        st = scan_tests(Path(tmp) / "naming", mr)
        cases.append(("边界①：非 surefire 命名不得计数", st["files"] == [], True))

        # 边界②：真实仓库若被改名，判据必须报"取不到"而不是"没有"（由 main() 的 rc=2 承担）
        cases.append(("边界②：pom 文本为空时 T2 必判红",
                      evaluate(tr, mr, "", ci)[1], False))

        # ---------------- T8 覆盖率读数（r78）：正反例 + 盲区 + 变异 + 分母口径回归锁 ----------------
        cases.append(("T8 正例：三路 counter 齐且过下限",
                      evaluate(tr4, mr4, GOOD_POM, GOOD_CI, GOOD_JACOCO, True)[1], True))
        cases.append(("T8 正例状态=ok",
                      evaluate(tr4, mr4, GOOD_POM, GOOD_CI, GOOD_JACOCO, True)[3], "ok"))
        bad_rows, bad_ok, _, bad_state = evaluate(tr4, mr4, GOOD_POM, GOOD_CI, BAD_JACOCO, True)
        cases.append(("T8 反例①：BRANCH 50% 必须判红", bad_ok, False))
        cases.append(("T8 反例①：红因必须点名 BRANCH",
                      any(r[0].startswith("T8") and "BRANCH" in r[2] for r in bad_rows), True))
        _, ok_blank, _, st_blank = evaluate(tr4, mr4, GOOD_POM, GOOD_CI, "", True)
        cases.append(("T8 反例②：取不到读数不得判红也不得判绿（须 unverified）",
                      (st_blank, ok_blank), ("unverified", True)))
        _, _, _, st_stale = evaluate(tr4, mr4, GOOD_POM, GOOD_CI, GOOD_JACOCO, False)
        cases.append(("T8 反例③：产物比源码旧必须落 unverified（禁拿旧读数当现状）",
                      st_stale, "unverified"))
        cases.append(("T8 具名缺口：必须点出带缺口的类名（按 missed 分支降序）",
                      top_gaps(GOOD_JACOCO),
                      ["Big(分支漏6/100·行漏5)", "Small(分支漏4/44·行漏0)"]))
        # 分母口径回归锁（r77 一手：逐类求和再加一次 missed ⇒ 246/296 被算成 296/346）
        cases.append(("T8 口径锁：分母只取 <report> 直属 counter，类内 counter 不得混进总分母",
                      read_counters(TRAP_JACOCO)["BRANCH"], (10, 90)))
        _g = globals()
        _orig_floors = dict(_g["COUNTER_FLOORS"])
        try:
            _g["COUNTER_FLOORS"] = {"LINE": 0.0, "BRANCH": 0.0, "METHOD": 0.0}
            _, mut_ok, _, mut_state = evaluate(tr4, mr4, GOOD_POM, GOOD_CI, BAD_JACOCO, True)
        finally:
            _g["COUNTER_FLOORS"] = _orig_floors
        cases.append(("T8 变异腿：阈值归零后同一份坏读数必须变绿（否则阈值这条腿没咬在被审对象上）",
                      (mut_ok, mut_state), (True, "ok")))

        # 硬化边界（r78 一手：第一版连 DOCTYPE 一起拒，把**真读数**判成未验 ⇒ 门禁拒绝真话＝逼下一轮虚报）
        cases.append(("T8 边界①：真件形状（带 DOCTYPE）必须读得动",
                      read_counters('<!DOCTYPE report PUBLIC "-//JACOCO//DTD Report 1.1//EN" "report.dtd">'
                                    + GOOD_JACOCO)["BRANCH"], (10, 90)))
        try:
            read_counters('<!ENTITY x "y">' + GOOD_JACOCO)
            cases.append(("T8 边界②：含 <!ENTITY 必须拒解析", "没抛", "抛")),
        except ValueError:
            cases.append(("T8 边界②：含 <!ENTITY 必须拒解析", "抛", "抛"))

    n_ok = 0
    for name, got, want in cases:
        if got == want:
            n_ok += 1
        else:
            print("  SELFTEST-FAIL %s want=%s got=%s" % (name, want, got))
    print("JAVA-TEST-GUARD-SELFTEST: %d/%d" % (n_ok, len(cases)))
    return 0 if n_ok == len(cases) else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
