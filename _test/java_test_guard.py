# -*- coding: utf-8 -*-
"""r41 in-build 测试资产守卫：把「构建自带门禁」这件事从"我今天跑了 mvn test"变成常驻判据。

为什么需要（对标定出来的真差距）：2026-09-27 实测 16 个参照仓里 **9 家有 in-build 单测**
（连 ★1 的 Java 同栈垂类 MoodChat 都有 Spring 脚手架），我方 `server/src` 下 JUnit 用例数
实测为 **0**，而 AGENTS.md 决策 #1 把「强类型 + 可单测（36 条评测可做成 JUnit）」列为选 Java 的
三条真实理由之一 ⇒ 那句话从 2026-09-20 挂到 09-27 没有产物支撑（同族：文案先行、代码未追）。

本件**不**跑 mvn（腾讯云镜像实测会 514 Frequency Capped，把第三方限速接进阻断链=天天假红），
也**不**复刻跨端对账（那是 engine_consistency_check 的活，复刻就长成 M5⑥「同一判断两处实现」）。
它盯的是四件**会让 in-build 门禁静默失效**的事：
  T1 用例真的存在：surefire 命名约定下的测试文件数与 @Test 数各达下限（零输入绝不判绿）
  T2 依赖真的在位：pom 声明 spring-boot-starter-test 且 scope=test
  T3 前提真的成立：surefire workingDirectory 指到仓库根（词表 SSOT 按 ./src/ 解析，
     不指则所有加载词表的用例在构建期以"路径不存在"红 —— 那是**前提**，不是可选项）
  T4 接线真的没断：ci.yml 的 java-build job 里 `mvn ... package` 那一步**不得带 -DskipTests**
     （带了这个 in-build 门禁就在受理面上静默消失，而本地看还是"CI 全绿"）
  T5 分母非空：main 侧类数 > 0（扫错目录会让 T1 的"0 用例"看起来完全正常）

退出码：0=JAVA-TEST-GUARD-PASS 1=判红 2=环境不可达（无 pom/无 ci.yml ⇒ 记 UNVERIFIED，不判绿）
用法：python _test/java_test_guard.py [--selftest] [--json]
"""
import argparse
import json
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_MAIN = ROOT / "server" / "src" / "main" / "java"
SRC_TEST = ROOT / "server" / "src" / "test" / "java"
POM = ROOT / "server" / "pom.xml"
CIYML = ROOT / ".github" / "workflows" / "ci.yml"

# 下限 = 09-27 实测值向下取整留出余量（无余量的地板等于冻结增长：加用例不会红，删用例会红）
FILE_FLOOR = 3
METHOD_FLOOR = 24

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
JACOCO_MINIMUM = re.compile(r"<minimum>\s*(0?\.\d+|1(?:\.0+)?)\s*</minimum>")
JACOCO_CHECK_AT_VERIFY = re.compile(r"<phase>verify</phase>[\s\S]{0,240}?<goal>check</goal>")
MVN_VERIFY = re.compile(r"mvn[^\n]*\bverify\b")


def check_coverage_gate(pom_text):
    """T6 覆盖率门本体：jacoco 在位 ∧ 有 check 目标 ∧ 有合法 <minimum> 数值。

    只写 `prepare-agent`/`report` 的仓**量得到但不会拦** ⇒ 不算门（与 r75 同址尺同一口径：
    "存在性 ≠ 行为"，必须能让构建失败）。
    """
    if not JACOCO_PLUGIN.search(pom_text or ""):
        return False, "pom 里没有 jacoco-maven-plugin"
    if not JACOCO_CHECK_GOAL.search(pom_text):
        return False, "jacoco 只有 report（量得到、不拦人）⇒ 缺 check 目标"
    m = JACOCO_MINIMUM.search(pom_text)
    if not m:
        return False, "check 目标在但没有 <minimum> 数值"
    return True, "LINE 阈值 %s" % m.group(1)


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


def evaluate(test_root, main_root, pom_text, yml_text):
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
    return rows, all(r[1] for r in rows), st


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
    rows, ok, st = evaluate(SRC_TEST, SRC_MAIN, _read(POM), _read(CIYML))
    for name, passed, val in rows:
        print("  %-26s %s  %s" % (name, "OK  " if passed else "FAIL", val))
    detail = "；".join("%s=%s" % (r[0].split()[0], r[2]) for r in rows)
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
            "<configuration><rules><rule><limits><limit>"
            "<counter>LINE</counter><minimum>0.35</minimum>"
            "</limit></limits></rule></rules></configuration></execution></plugin>")
BAD_POM_NODEP = ("<workingDirectory>${project.basedir}/..</workingDirectory>"
                 "<artifactId>jacoco-maven-plugin</artifactId><goal>check</goal><minimum>0.35</minimum>")
BAD_POM_NOWD = ("<artifactId>spring-boot-starter-test</artifactId><scope>test</scope>"
                "<artifactId>jacoco-maven-plugin</artifactId><goal>check</goal><minimum>0.35</minimum>")
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
        tr, mr, pom, ci = _fixture(tmp, FILE_FLOOR + 1, 8)  # 4 件 x 8 = 32 > 下限 24
        cases.append(("正例：下限齐 + 依赖在位 + 未跳测", evaluate(tr, mr, pom, ci)[1], True))

        tr2, mr2, _, _ = _fixture(str(Path(tmp) / "f2"), 0, 0)
        Path(tr2).mkdir(parents=True, exist_ok=True)
        cases.append(("反例①：零用例不得判绿", evaluate(tr2, mr2, pom, ci)[1], False))

        tr3, mr3, _, _ = _fixture(str(Path(tmp) / "f3"), FILE_FLOOR + 1, 1)   # 4 文件 x 1 @Test = 4 < 25
        cases.append(("反例②：文件够但用例数不足", evaluate(tr3, mr3, pom, ci)[1], False))

        tr4, mr4, _, _ = _fixture(str(Path(tmp) / "f4"), FILE_FLOOR, 7)
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
        ok_gate, why_gate = check_coverage_gate(pom)
        ok_chain, why_chain = check_gate_on_chain(ci)
        cases.append(("点名A：合规 pom 的 T6 必须真过（值=%s）" % why_gate, ok_gate, True))
        cases.append(("点名B：合规 CI 的 T7 必须真过（值=%s）" % why_chain, ok_chain, True))
        cases.append(("点名C：package-only CI 的 T7 必须单独为假（不许靠别的行凑绿）",
                      check_gate_on_chain(BAD_CI_PACKAGE)[0], False))
        cases.append(("点名D：report-only pom 的 T6 必须单独为假",
                      check_coverage_gate(BAD_POM_REPORTONLY)[0], False))

        # 边界：命名约定必须与 surefire 一致，否则"看起来有用例"是假的
        bad = Path(tmp) / "naming" / "com"
        bad.mkdir(parents=True, exist_ok=True)
        (bad / "Helper.java").write_text("@Test void a() { assertTrue(true); }", "utf-8")
        st = scan_tests(Path(tmp) / "naming", mr)
        cases.append(("边界①：非 surefire 命名不得计数", st["files"] == [], True))

        # 边界②：真实仓库若被改名，判据必须报"取不到"而不是"没有"（由 main() 的 rc=2 承担）
        cases.append(("边界②：pom 文本为空时 T2 必判红",
                      evaluate(tr, mr, "", ci)[1], False))

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
