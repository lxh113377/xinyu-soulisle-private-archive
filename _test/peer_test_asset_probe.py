# -*- coding: utf-8 -*-
"""对标 r41 探针：**测试资产与质量内建**（16 仓 + self，双通道同尺）。

为什么是这一面：台账连续三轮（r38/r40/本轮首跑）零实质漂移，账面（★/停更/wf/文档件）、
行尾确定性、发布可得性、安全能力、性能维都已量过。剩下一件**账面完全看不见、而我们自己的
AGENTS.md 决策 #1 把它当成选 Java 的三条理由之一**的东西：`in-build 单测`。
实测 `find server/src -name '*Test*.java'` = **0**、`pom.xml` 无 junit/surefire 依赖
⇒ 「36 条评测可做成 JUnit」这句话从 2026-09-20 挂到现在没有产物支撑（同族：文案先行、代码未追）。

与既有三面对比（不重复、互补）：
  · r38 `peer_capability_safety_probe` 量"产品做了什么"，其中 `is_tool()` 把 test/check 一律**排除**
    —— 那是为了不给自己凭空加能力位，本件反过来：**test 就是要量的对象**。
  · 本件必须区分两类件，否则结论会被我自己的 `_test/` 带外判据灌水：
    类 1 `in_build_tests`  语言规范测试根下的用例（`src/test/java/**`、`tests/**`、`__tests__/**`、
                            `*_test.go`、`*.spec.*`/`*.test.*`）⇒ `mvn/npm/pytest` 一跑就判
    类 2 `out_of_band`     仓库内的带外回归脚本（`_test/*_check.py` 这类），我们这一面很强，
                            但它**不参与构建**：构建产物可以带缺陷出厂而构建自身不报警。

双通道纪律（承 r38 M5⑦⑧⑨）：
  通道 A = 默认分支递归文件树（truncated 必查，被截断的仓其"零命中"不作数）
  通道 B = README 正文（覆盖率徽章 / 测试章节 / 测试命令）——与 A 独立，给 A 的零结论做第二通道
  未取到一律记 NA(原因)，禁止与 0 混同；self 与 peers 用同一组正则，不搞双标。
用法：python _test/peer_test_asset_probe.py [--json out.json] [--self-only] [--selftest]
退出码：0=分母齐且无 NA 1=存在 NA 或 selftest 未过 2=无 GitHub token（环境）
"""
import argparse
import base64
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from benchmark_metrics import PEERS, ROOT   # 分母唯一真相源 = 台账池（不另立清单）

# ---------- 通道 A：文件树 ----------
# in-build 单测：按语言规范测试根/后缀。刻意**不含**裸 `test/` 目录名以外的宽匹配，
# 否则 `dataset/test.json`、`latest.min.js`（含 "test" 子串）会灌出假阳性。
IN_BUILD = [
    # Java 侧按 **surefire 默认命名约定**判（`Test*` / `*Test` / `*Tests` / `*TestCase`）——
    # 首版写成 `src/test/java/.+\.java$` 会把 `Constants.java`、`TestDataFactory.java` 这类
    # 测试根下的**非运行件**算成用例；按"构建真的会跑它"来定义才是本面对的真实口径。
    (re.compile(r"(^|/)src/test/(java|kotlin)/(?:.+/)?(?:Test[^/]*|[^/]*(?:Test|Tests|TestCase|IT))"
                r"\.(java|kt)$"), "java"),
    # ⚠ 这条**不含** java/kt/scala：JVM 侧只认上一条的 surefire 命名约定。首版把 java 也放进来，
    # 于是 `src/test/java/com/x/Constants.java` 被算成用例（`(^|/)tests?/` 命中 `src/test/`，
    # 扩展名又收 java）—— 反例⑨当场抓到，属"修一条判据时另一条同义规则从侧面兜住"的形态。
    (re.compile(r"(^|/)(__tests__|tests?)/.+\.(ts|tsx|js|jsx|mjs|py|go|rs|rb|php|vue|svelte)$"), "dir"),
    (re.compile(r"\.(test|spec)\.(ts|tsx|js|jsx|mjs|cjs|py|java|kt|go|rs|rb|php|vue|svelte)$"), "suffix"),
    (re.compile(r"(^|/)test_.+\.(py)$"), "py"),
    (re.compile(r".+_test\.go$"), "go"),
]
# 覆盖率/质量内建配置件（一次命中即算，不数条）
COVERAGE_CFG = re.compile(
    r"(^|/)(jacoco\.xml|\.coveragerc|pytest\.ini|setup\.cfg|tox\.ini|codecov\.yml|codecov\.yaml"
    r"|coverage\.config\.(js|ts|mjs)|vitest\.config\.(ts|js|mjs)|jest\.config\.(js|ts|mjs|json)"
    r"|\.nycrc|karma\.conf\.js)$", re.I)
# CI workflow 里"名字像跑测试"的（弱信号，仅作样本，不参与计数结论）
CI_TESTISH = re.compile(r"(^|/)\.github/workflows/.*(test|ci|check|quality).*\.ya?ml$", re.I)
# 排除物：依赖目录与构建产物（`node_modules/vitest/dist/test.js` 会让任何 JS 项目"有测试"）
NOISE = re.compile(r"(^|/)(node_modules|vendor|dist|build|target|\.venv|venv|site-packages"
                   r"|\.git/|packagemanager|cache)/", re.I)
# 测试**目录里的非用例**件（首跑实测 r38 对手 `chibi` 的 80 件里首条就是 `tests/__init__.py`
# —— 包标记被算成单测，同类还有 pytest 的夹具与常量件；不修会给 peers 灌水，也使"件数"失真）
NOT_A_TEST = re.compile(r"(^|/)(__init__|conftest|__main__|constants?|fixtures?|shared|utils)"
                        r"\.(py|ts|js)$", re.I)


def is_testish(p):
    if NOISE.search(p) or NOT_A_TEST.search(p):
        return False
    return any(rx.search(p) for rx, _tag in IN_BUILD)


def classify_tree(paths):
    """paths: [相对路径] -> dict(in_build, by_lang, coverage_cfg, ci_testish, out_of_band)"""
    ib, langs = [], {}
    for p in paths:
        if not is_testish(p):
            continue
        ib.append(p)
        for rx, tag in IN_BUILD:
            if rx.search(p):
                langs[tag] = langs.get(tag, 0) + 1
                break
    cfg = [p for p in paths if COVERAGE_CFG.search(p) and not NOISE.search(p)]
    ci = [p for p in paths if CI_TESTISH.search(p)]
    oob = [p for p in paths if re.search(r"(^|/)_?tests?_?/.*\.(py|sh|js)$", p)
           and not NOISE.search(p) and p not in ib]
    return {"in_build": len(ib), "in_build_samples": sorted(ib)[:3], "langs": langs,
            "coverage_cfg": sorted(cfg)[:6], "ci_testish_wf": sorted(ci)[:4],
            "out_of_band": len(oob), "out_of_band_samples": sorted(oob)[:3]}


def api(path, token):
    req = urllib.request.Request("https://api.github.com/" + path,
                                 headers={"User-Agent": "xinyu-test-asset-probe",
                                          "Accept": "application/vnd.github+json"})
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            return json.loads(r.read().decode("utf-8", "replace")), ""
    except Exception as e:
        return None, "http=%s" % getattr(e, "code", type(e).__name__)


def probe_repo(slug, token):
    data, err = api("repos/%s/git/trees/HEAD?recursive=1" % slug, token)
    if data is None:
        return {}, False, err
    paths = [t.get("path", "") for t in data.get("tree", []) if t.get("type") == "blob"]
    return classify_tree(paths), bool(data.get("truncated")), ""


# ---------- 通道 B：README ----------
DOC_RX = {
    "cov_badge": re.compile(r"codecov|coveralls|sonarcloud|coverage[-_/]?badge|badge/coverage", re.I),
    "test_cmd": re.compile(r"(npm (test|run test)|pnpm test|yarn test|pytest\b|mvn (test|-q test)"
                           r"|cargo test|go test\.?|\.\/(run|make) test|gradle test)", re.I),
    "test_doc": re.compile(r"(#+\s*(testing|tests|test suite|单元测试|测试|qa)|contributing.*test)", re.I),
}


def probe_readme(slug, token):
    data, err = api("repos/%s/readme" % slug, token)
    if data is None:
        return {}, err
    try:
        txt = base64.b64decode(data.get("content") or "").decode("utf-8", "replace")
    except Exception as e:
        return {}, "decode:%s" % e
    out = {}
    for k, rx in DOC_RX.items():
        m = rx.findall(txt)
        if m:
            out[k] = "%d 处｜样本 %r" % (len(m), (m[0] if isinstance(m[0], str) else str(m[0]))[:48])
    return out, ""


# ---------- self：同一把尺跑工作树 ----------
SKIP_PARTS = ("/.git/", "node_modules/", ".codebuddy/", "_shots/", "target/", "server/data/",
              "web_raw/", "video_raw/")


def self_paths():
    out = []
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        r = str(p.relative_to(ROOT)).replace("\\", "/")
        if any(x in "/" + r for x in SKIP_PARTS):
            continue
        out.append(r)
    return out


def probe_self():
    return classify_tree(self_paths())


def self_readme():
    fp = ROOT / "README.md"
    txt = fp.read_text("utf-8", errors="replace") if fp.exists() else ""
    out = {}
    for k, rx in DOC_RX.items():
        m = rx.findall(txt)
        if m:
            out[k] = "%d 处｜样本 %r" % (len(m), (m[0] if isinstance(m[0], str) else str(m[0]))[:48])
    return out


# ---------- selftest：证明判据非恒真（正例 + 反例 + 边界，双向） ----------
FIXTURE = [
    # (path, expect_in_build, note)
    ("server/src/test/java/com/xinyu/soulisle/engine/EmotionEngineTest.java", True, "J 侧规范测试根"),
    ("src/js/__tests__/chat.test.js", True, "JS __tests__ 规范"),
    ("tests/test_lexicon.py", True, "Python tests/ 规范"),
    ("pkg/handler_test.go", True, "Go _test.go 规范"),
    ("a/b/foo.spec.ts", True, "后缀式 spec"),
    ("node_modules/vitest/dist/test.js", False, "反例①：依赖目录不得算"),
    ("src/main/resources/static/latest.min.js", False, "反例②：'latest' 含 test 子串"),
    ("data/dataset/test.json", False, "反例③：数据文件名为 test 的普通 json"),
    ("docs/test.md", False, "反例④：文档不是用例"),
    ("target/surefire-reports/TEST-Foo.xml", False, "反例⑤：构建产物报告不是用例"),
    ("_test/browser_check.py", False, "反例⑥：带外判据不计 in-build"),
    ("tests/__init__.py", False, "反例⑦：包标记不是用例（chibi 首跑实测灌水的头一条）"),
    ("tests/conftest.py", False, "反例⑧：pytest 夹具不是用例"),
    ("src/test/java/com/x/Constants.java", False, "反例⑨：规范测试根下的常量件不是用例"),
]


def run_selftest():
    ok = 0
    fail = []
    for path, want, note in FIXTURE:
        got = classify_tree([path])["in_build"] == 1
        if got == want:
            ok += 1
        else:
            fail.append("%s want=%s got=%s" % (note, want, got))
    # 边界 A：零输入不得判绿（防"分母空 = 全过"）
    empty = classify_tree([])
    if empty["in_build"] == 0 and empty["langs"] == {}:
        ok += 1
    else:
        fail.append("边界A 零输入异常")
    # 边界 B：混合集计数必须等于逐条之和（防去重/漏计）
    allp = [f[0] for f in FIXTURE]
    total = classify_tree(allp)["in_build"]
    if total == sum(1 for f in FIXTURE if f[1]):
        ok += 1
    else:
        fail.append("边界B 计数 %s != 期望 %s" % (total, sum(1 for f in FIXTURE if f[1])))
    n = len(FIXTURE) + 2
    for x in fail:
        print("  SELFTEST-FAIL " + x)
    print("TESTASSET-SELFTEST: %d/%d" % (ok, n))
    return 0 if ok == n else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="")
    ap.add_argument("--self-only", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return run_selftest()
    token = os.environ.get("GITHUB_TOKEN") or ""
    if not token:
        r = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True)
        token = r.stdout.strip()
    if not token:
        print("TESTASSET-ENV: 无 GitHub token（gh auth token 失败）⇒ 不采数、不判绿")
        return 2

    rows, na = {}, []
    for p in ([] if a.self_only else PEERS):
        slug, tier = p["repo"], p["tier"]
        tree, trunc, err1 = probe_repo(slug, token)
        doc, err2 = probe_readme(slug, token)
        rows[slug] = {"tier": tier, "tree": tree, "readme": doc, "truncated": trunc,
                      "err": [e for e in (err1, err2) if e]}
        if err1 or err2:
            na.append("%s(%s)" % (slug, "+".join(x for x in (err1, err2) if x)))
        elif trunc:
            na.append("%s(树被截断⇒零命中不可信)" % slug)
        print("[%-3s] %-36s in_build=%-4d 覆盖配置=%-3d wf带测试名=%-2d 带外件=%-4d README=%s%s"
              % (tier, slug, tree.get("in_build", -1), len(tree.get("coverage_cfg", [])),
                 len(tree.get("ci_testish_wf", [])), tree.get("out_of_band", -1),
                 ",".join(sorted(doc)) or ("none" if not err2 else "NA"),
                 "｜截断" if trunc else ""))
    st = probe_self()
    sd = self_readme()
    rows["__self__"] = {"tree": st, "readme": sd}
    print("[self] %-36s in_build=%-4d 覆盖配置=%-3d 带外件=%-4d README=%s"
          % ("心屿 SoulIsle", st["in_build"], len(st["coverage_cfg"]),
             st["out_of_band"], ",".join(sorted(sd)) or "none"))
    print("-" * 124)
    n = len(rows) - 1
    if n:
        ib = sum(1 for k, v in rows.items() if k != "__self__" and v["tree"].get("in_build", 0) > 0)
        cov = sum(1 for k, v in rows.items() if k != "__self__" and v["tree"].get("coverage_cfg"))
        print("peers：有 in-build 单测 %d/%d ｜ 有覆盖率/测试框架配置 %d/%d" % (ib, n, cov, n))
        for k, v in sorted(rows.items(), key=lambda x: -x[1]["tree"].get("in_build", 0)):
            if k == "__self__":
                continue
            t = v["tree"]
            if t.get("in_build"):
                print("   %-36s %5d 件 %s" % (k, t["in_build"], t["in_build_samples"][:1]))
    if na:
        print("  NA/截断：" + "; ".join(na))
    print("应测 %s 仓 ｜ NA/截断 %d ｜ self in_build=%d"
          % (n if not a.self_only else 0, len(na), st["in_build"]))
    if a.json:
        Path(a.json).write_bytes(json.dumps(
            {"repos": rows, "na": na, "denominator": n,
             "ts": subprocess.run(["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"],
                                  capture_output=True, text=True).stdout.strip()},
            ensure_ascii=False, indent=1).encode("utf-8"))
        print("快照 -> " + a.json)
    if a.self_only:
        return 0
    return 1 if na else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
