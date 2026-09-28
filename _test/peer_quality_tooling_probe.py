# -*- coding: utf-8 -*-
"""对标 r58 探针：**质量工程制度化**（lint / 类型 / 单元可测性 / CI 里的执行位）（16 仓 + self，双通道）。

为什么是这一面：✅ 取证 `grep -ilE "eslint|prettier|vitest|jest|类型检查|单元测试" 交付物/对标分析报告-*.md`
= 十七份全 0。而本仓 r41 起就常年在 CI 跑 **30 个 JUnit 用例**——Java 侧有测试金字塔的一层，
**JS 侧一层都没有**（只有浏览器 E2E）。"我们有测试"这句话在两端成立程度完全不同，正是
[[对标结论：存在性 vs 行为]] 说的那类缺口。

⚠️ 天花板（写进快照头，不许越界解释）：
  本探针只出**结构化在册证据**（配置文件在不在、测试文件在不在、CI 有没有执行位）。
  ⇒ 不得据此声称"谁的代码质量更高""谁的缺陷更少"——覆盖率与缺陷率都不在本轮取数面内。
  self 的行为回执（真跑起来能过什么）在 `_test/js_unit_check.py` 与 Java 侧 `mvn test`。

**与 r54 探针的关键差异（这条最容易抄错）**：`peer_sec_headers_probe.py` 的 NOISE 排除
`_?tests?|__tests__|spec` 等目录——那对"安全头配置"是对的（测试里的 header 是夹具不是能力）。
**照抄到这里就会把被测对象本身滤掉**：单元测试文件恰好住在这些目录里。
⇒ 本件的 NOISE 只滤**依赖与产物**目录（node_modules/dist/build/target/.next/coverage），
   绝不滤测试目录。反例④专门钉这一点。

两通道：
  A 结构面 = git tree：linter/formatter 配置、tsconfig、测试框架配置、测试文件、CI 执行位
  B 声明面 = README：**锚定词组**（ESLint / Prettier / Vitest / Jest / Playwright / 单元测试）
     ⚠️ 不用裸子串：`jest` 是 `ajest` 的子串、`spec` 在每个 `*.spec.md` 里出现、
        `type` 更是遍地。一律整词 + 显式后缀。
用法：python _test/peer_quality_tooling_probe.py [--json out.json] [--self-only] [--selftest]
退出码：0=分母齐且无 NA 1=存在 NA 或 selftest 未过 2=无 GitHub token（环境）
"""
import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from benchmark_metrics import PEERS, ROOT

# ⚠ 见 docstring：这里**不滤**测试目录
NOISE = re.compile(r"(^|/)(node_modules|\.venv|venv|dist|build|target|\.next|coverage|\.git|_shots|"
                   r"__pycache__|vendor)/", re.I)

STRUCT = {
    # ⚠️ 首版写成 `\.[es]lintrc` —— `[es]` 只匹配**一个**字符，`.eslintrc.json` 恒不命中，
    #    是 --selftest 的正向桩当场抓出来的（r58）。写字符类时别把两个字母当成一个可选。
    "linter": re.compile(r"(^|/)(\.eslintrc(\.[\w-]+)?|eslint\.config\.(js|mjs|cjs|ts|json)"
                         r"|\.eslintignore)$"),
    "formatter": re.compile(r"(^|/)(\.[pm]rettierrc(\.\w+)?|prettier\.config\.(js|cjs|mjs|json)"
                            r"|biome\.jsonc?)$"),
    "typecheck": re.compile(r"(^|/)tsconfig([\w.-]*)?\.json$"),
    "js_test_cfg": re.compile(r"(^|/)(vitest|jest|karma|mocha|web-test-runner)(\.config)?\."
                              r"(js|ts|mjs|cjs|json)$|(^|/)jest\.config\.(js|ts|cjs|mjs)$"),
    "js_test_file": re.compile(r"(^|/)[\w./-]*\.(test|spec)\.(js|jsx|ts|tsx|mjs|cjs)$", re.I),
    "py_test_file": re.compile(r"(^|/)(test_[\w.-]+|[\w.-]+_test\.py|conftest\.py)$"),
    "java_test_file": re.compile(r"(^|/)[\w.-]+Test\.java$"),
}
CI_STEP = {
    "lint": re.compile(r"(eslint|biome|pnpm|npm|yarn)\s+(run\s+)?(lint|lint:fix|check)\b|\blint\b", re.I),
    "typecheck": re.compile(r"tsc\s+--noEmit|type-?check", re.I),
}
# 单测执行位**单独实现**（不塞进上面的合并正则）：一条命令行既要命中测试阶段、又要能排除
# `-DskipTests`。首版写成 `mvn[^\n]*\btest\b`，而本仓 CI 实跑的是 `mvn -B -ntp -f server/pom.xml package`
# —— surefire 在 package 阶段跑 ⇒ self 被误判成"CI 没有单测执行位"（r58 由 --self-only 真面当场暴露）。
UNIT_RX = re.compile(r"(\b(vitest|jest)\b\s+run|\bnode\s+--test\b|(npm|pnpm|yarn)\s+(run\s+)?test\b"
                     r"|pytest|\bmvn\b[^\n]*\b(test|package|verify)\b|\bgradle\b[^\n]*\btest\b|cargo\s+test)", re.I)
SKIP_RX = re.compile(r"-DskipTests|--skip[-_]tests?\b|-Dmaven\.test\.skip", re.I)


def unit_steps(text):
    """逐行判：命中测试阶段且**没有**跳过开关的行才算执行位。

    两道判断不是互为替身 —— 只查 UNIT_RX 会把 `-DskipTests` 的构建步算成跑了测试（虚报能力），
    只查 SKIP_RX 又认不出正常步。故必须同行联合，并由反例⑧钉住"整份 workflow 只有 skipTests"这一形态。
    """
    hits = []
    for ln in (text or "").splitlines():
        if SKIP_RX.search(ln):
            continue
        if UNIT_RX.search(ln):
            hits.append(ln.strip()[:70])
    return hits
README_PAT = {
    "linter_declared": re.compile(r"\bESLint\b|\bBiome\b", re.I),
    "typecheck_declared": re.compile(r"\bTypeScript\b|\btsc\b"),
    "unit_declared": re.compile(r"\bVitest\b|\bJest\b|\bpytest\b|\bJUnit\b|单元测试|单元測试"),
    "e2e_declared": re.compile(r"\bPlaywright\b|\bCypress\b|\bSelenium\b"),
}


def classify_tree(paths):
    """通道 A：按**结构单位（文件）**计数，一类只记一次；同时给测试文件计数。"""
    out, counts = {}, {}
    for p in paths:
        if NOISE.search("/" + p):
            continue
        for k, rx in STRUCT.items():
            if rx.search(p):
                out.setdefault(k, []).append(p)
                if k.endswith("test_file"):
                    counts[k] = counts.get(k, 0) + 1
    return out, counts


def classify_ci(blobs):
    out = {}
    for name, txt in (blobs or {}).items():
        if not re.search(r"\.ya?ml$", name):
            continue
        for k, rx in CI_STEP.items():
            if rx.search(txt or ""):
                out.setdefault(k, []).append(name)
        if unit_steps(txt):
            out.setdefault("unit", []).append(name)
    return out


def classify_readme(text):
    return {k: True for k, rx in README_PAT.items() if rx.search(text or "")}


def self_paths():
    r = subprocess.run(["git", "-C", str(ROOT), "ls-files"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return [x.strip() for x in r.stdout.splitlines() if x.strip()]


RETRY_WAITS = (0, 2, 5)          # 第 1/2/3 次尝试前的等待秒数（仅三次；配合下面的全局预算才有上界）
DEADLINE = [None]                # main() 里按 --budget 写入的绝对截止时刻；None = 不设限
CALL_TIMEOUT = 20                # 45s 会把一次抖动放大成几十分钟的整轮（r58 实测：16 仓跑了一小时）


def api(path, token):
    """带**有界重试**的取数：本机到 api.github.com 的链路是"按域名×时刻"时通时不通，
    单次 RemoteDisconnected/超时不代表该仓不存在 ⇒ 不重试就会把整面打成 NA（假盲区）。
    重试只针对传输层失败与 5xx/429；404 一就返回（那是真没有，不该重试）。
    """
    req = urllib.request.Request("https://api.github.com/" + path,
                                 headers={"User-Agent": "xinyu-quality-probe",
                                          "Accept": "application/vnd.github+json"})
    if token:
        req.add_header("Authorization", "Bearer " + token)
    last = "unknown"
    for wait in RETRY_WAITS:
        dl = DEADLINE[0]
        if dl is not None and time.time() > dl:
            return None, "budget-exhausted"
        if wait:
            time.sleep(wait)
        try:
            with urllib.request.urlopen(req, timeout=CALL_TIMEOUT) as r:
                return json.loads(r.read().decode("utf-8", "replace")), ""
        except urllib.error.HTTPError as e:
            last = "http=%s" % e.code
            if e.code == 404:
                return None, last
            if e.code in (403, 429):
                ra = e.headers.get("Retry-After")
                if ra and str(ra).isdigit():
                    time.sleep(min(int(ra), 20))
        except Exception as e:
            last = "http=%s" % type(e).__name__
    return None, last + "(x%d)" % len(RETRY_WAITS)


def token_of():
    r = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True)
    t = (r.stdout or "").strip()
    if t:
        return t
    return os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""


def tree_of(repo, token):
    default = ""
    j, err = api("repos/" + repo, token)
    if j:
        default = j.get("default_branch", "")
    if not default:
        return None, err or "no-default-branch"
    j, err = api("repos/%s/git/trees/%s?recursive=1" % (repo, default), token)
    if not j:
        return None, err
    return [t["path"] for t in j.get("tree", []) if t.get("type") == "blob"], j.get("truncated") is True


def readme_of(repo, token):
    for name in ("README.md", "readme.md", "README.rst", "README"):
        j, _ = api("repos/%s/contents/%s" % (repo, name), token)
        if j and j.get("content"):
            return base64.b64decode(j["content"]).decode("utf-8", "replace"), name
    return "", ""


def ci_blobs_of(repo, token):
    """工作流正文一律走 api.github.com 的 contents（base64），**不用 download_url**。

    实测根因（r58）：download_url 指向 objects.githubusercontent.com，本机对那个主机
    连不上也不报错——`urlopen(timeout=45)` 静默等满 45s 再抛。16 仓 × 若干 workflow
    ⇒ 全量跑挂了一小时以上，而 `api.github.com/rate_limit` 同期 0.6s 返回 200、配额 used=0。
    ⇒ 慢的不是对标对象，是我自己选的取数主机。换回同一主机后必须重测总耗时，别信"应该快了"。
    """
    out = {}
    j, _ = api("repos/%s/contents/.github/workflows" % repo, token)
    for item in (j if isinstance(j, list) else []):
        if item.get("type") != "file" or not re.search(r"\.ya?ml$", item.get("name", "")):
            continue
        c, _ = api("repos/%s/contents/%s" % (repo, item["path"]), token)
        if c and c.get("content"):
            out[item["name"]] = base64.b64decode(c["content"]).decode("utf-8", "replace")
    return out


def verdict(struct, counts, ci, doc):
    a = sorted(struct)
    s = "结构 %d/%d 类" % (len(a), len(STRUCT))
    if counts:
        s += "（js测试 %s py测试 %s java测试 %s）" % (counts.get("js_test_file", 0),
                                                  counts.get("py_test_file", 0),
                                                  counts.get("java_test_file", 0))
    s += "｜CI 执行位 " + (",".join(sorted(ci)) if ci else "无")
    s += "｜声明 " + (",".join(sorted(k.replace("_declared", "") for k in doc)) if doc else "无")
    return s


STUBS = [
    ("正向 linter 配置", ["src/App.tsx", ".eslintrc.json", "package.json"], {"linter"}, 0),
    ("正向 测试目录不被滤", ["tests/unit/a.test.js", "__tests__/b.spec.ts"], {"js_test_file"}, 2),
    ("正向 tsconfig 多份", ["tsconfig.json", "tsconfig.node.json"], {"typecheck"}, 0),
    ("反例 node_modules 不算能力", ["node_modules/eslint-config-x/index.js", "dist/.eslintrc.json",
                                     "coverage/lcov-report/app.js"], set(), 0),
    ("反例 文档里的名字不算结构", ["docs/jest.md", "README.md", "spec/flow.spec.md"], set(), 0),
    ("反例 裸子串不误伤", ["src/hypotenuse.js", "src/type-parser.ts", "src/myjest-util.js"], set(), 0),
    ("边界 空输入", [], set(), 0),
]


def selftest():
    bad = []
    for name, paths, want_keys, want_count in STUBS:
        st, counts = classify_tree(paths)
        got = set(st)
        if got != want_keys:
            bad.append("%s：期望 %s 实得 %s" % (name, sorted(want_keys) or "∅", sorted(got) or "∅"))
        tot = sum(counts.values())
        if tot != want_count:
            bad.append("%s：测试文件计数期望 %d 实得 %d" % (name, want_count, tot))
    if not unit_steps("run: mvn -B -ntp -f server/pom.xml package"):
        bad.append("unit_steps：`mvn package` 阶段（surefire 实际跑测试的地方）未被认成执行位 ⇒ self 会被误判无单测")
    if unit_steps("run: mvn -B -ntp -f server/pom.xml package -DskipTests"):
        bad.append("unit_steps：带 -DskipTests 的构建步被判成跑了测试 ⇒ 虚报能力")
    if unit_steps(""):
        bad.append("unit_steps 零输入却给出执行位 ⇒ 度量面失效（禁把空当有）")
    if not unit_steps("- run: mvn test\n- run: mvn -B package -DskipTests\n"):
        bad.append("unit_steps：同一 workflow 里混有 skipTests 步时，正常步也没被认出（逐行判断被整份吞掉）")
    ci = classify_ci({"ci.yml": "steps:\n  - run: pnpm lint\n  - run: mvn -B test\n"})
    if set(ci) != {"lint", "unit"}:
        bad.append("CI 执行位：期望 lint,unit 实得 %s" % sorted(ci))
    if classify_ci({"readme.md": "run: pnpm lint"}):
        bad.append("CI 通道越界：非 yaml 文件也被当成执行位")
    doc = classify_readme("本项目用 ESLint 跑 lint，Vitest 写单元测试")
    if set(doc) != {"linter_declared", "unit_declared"}:
        bad.append("声明面：期望 linter,unit 实得 %s" % sorted(doc))
    if classify_readme("we ship the type of thing ajest never sees"):
        bad.append("声明面误伤：裸子串 ajest/type 被当成声明")
    if classify_tree(["node_modules/jest/bin/jest.js"])[0]:
        bad.append("判据恒真：依赖目录里的 jest 仍被计入 ⇒ NOISE 失效")
    print("QUALITYPEER-SELFTEST-%s（%d 类桩 + 恒真守卫）" % ("PASS" if not bad else "FAIL: " + "; ".join(bad), len(STUBS)))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="",
                help="台账输出路径；缺省=当日件（必落盘）。传 '-' 才不落盘，且会印 NOLEDGER 声明读数不得据以改判")
    ap.add_argument("--self-only", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--budget", type=int, default=240,
                help="联网采集的总秒数上界（默认 240）；到点后剩余仓记 NA(budget-exhausted)，"
                     "不折叠成通过，也不让一次人工轮次挂成无限等")
    a = ap.parse_args()
    if not a.json:   # r66：旧行为"只印不写"使 stdout 结论与盘上台账可以互相矛盾（我据此误判过一次）
        a.json = str(ROOT / ("交付物/对标数据/peer-quality-tooling-%s.json"
                                % time.strftime("%Y-%m-%d")))
    if a.selftest:
        return selftest()
    DEADLINE[0] = time.time() + max(10, a.budget)
    t_start = time.time()
    token = token_of()
    rows = []
    sp = self_paths()
    st, ct = classify_tree(sp)
    ci = classify_ci({p.split("/")[-1]: Path(ROOT / p).read_text("utf-8", errors="replace")
                      for p in sp if p.startswith(".github/workflows/")})
    doc = classify_readme(Path(ROOT / "README.md").read_text("utf-8", errors="replace")
                          if (ROOT / "README.md").exists() else "")
    rows.append(("[self] 心屿 SoulIsle", st, ct, ci, doc, "n/a", len(sp)))
    if not a.self_only:
        if not token:
            print("QUALITYPEER-ENV: 无 GitHub token ⇒ 只出 self，不判 peers")
            return 2
        for ent in PEERS:
            repo = ent["repo"] if isinstance(ent, dict) else ent   # PEERS 名册是 dict（repo/tier/why），不是裸 slug
            paths, trunc = tree_of(repo, token)
            if paths is None:
                rows.append((repo, None, {}, {}, {}, "NA(" + str(trunc) + ")", 0))
                continue
            s2, c2 = classify_tree(paths)
            rb, _ = readme_of(repo, token)
            cb = ci_blobs_of(repo, token)
            rows.append((repo, s2, c2, classify_ci(cb), classify_readme(rb),
                         "truncated" if trunc else "ok", len(paths)))
    blind = [r[0] for r in rows if r[1] is None]
    print("-" * 118)
    for name, s_, c_, ci_, doc_, flag, n in rows:
        if s_ is None:
            print("[NA ] %-34s %s（树取不到 ⇒ 不计入分母，也不计入结论）" % (name, flag))
            continue
        print("[%-4s] %-34s %s" % ("HIT" if s_ or ci_ else "no", name,
                                   verdict(s_, c_, ci_, doc_) + ("｜" + flag if flag == "truncated" else "")))
    print("-" * 118)
    peers = [r for r in rows if not r[0].startswith("[self]")]
    okp = [r for r in peers if r[1] is not None]
    has_js = sum(1 for r in okp if r[2].get("js_test_file"))
    has_ci_unit = sum(1 for r in okp if "unit" in r[3])
    has_lint = sum(1 for r in okp if "linter" in r[1])
    has_type = sum(1 for r in okp if "typecheck" in r[1])
    print("peers：有 JS 测试文件 %d/%d ｜ CI 有单测执行位 %d/%d ｜ 有 linter 配置 %d/%d ｜ 有 tsconfig %d/%d"
          % (has_js, len(okp), has_ci_unit, len(okp), has_lint, len(okp), has_type, len(okp)))
    print("预算 %ds ｜ 已用 %.0fs ｜ budget 耗尽后停取 %s"
          % (a.budget, time.time() - t_start,
             "是" if any("budget-exhausted" in str(r[5]) for r in rows if r[1] is None) else "否"))
    print("应测 %d 仓 ｜ 计入分母 %d ｜ BLIND(NA) %d ｜ 恒等式：%s"
          % (len(peers), len(okp), len(blind),
             "OK" if len(okp) + len(blind) == len(peers) else "不成立⇒分母可疑"))
    if a.json and a.json != "-":   # '-' 必须在写之前拦住，否则会落出个名叫 - 的文件（r66 实踩过）
        payload = {"generated_by": "peer_quality_tooling_probe.py",
                   "ceiling": "只出结构化在册证据；不得据此比较代码质量/缺陷率（覆盖率不在取数面内）",
                   "noise_note": "本件 NOISE 故意不滤 tests 目录，否则会把被测对象滤掉",
                   "peers_expected": len(peers), "counted": len(okp), "na": blind,
                   "self": {"struct": sorted(rows[0][1]), "test_counts": rows[0][2],
                            "ci_steps": sorted(rows[0][3]), "declared": sorted(rows[0][4])},
                   "rows": [{"repo": n, "struct": sorted(s) if s else None, "counts": c,
                             "ci": sorted(x) if x else [], "declared": sorted(d), "flag": f,
                             "files": ln} for n, s, c, x, d, f, ln in rows]}
        Path(a.json).write_bytes(json.dumps(payload, ensure_ascii=False, indent=1).encode("utf-8"))
        raw = Path(a.json).read_bytes()   # 按字节回读：字符串长度口径在 Windows 会少算 CRLF
        print("快照 -> %s ｜ 台账指纹 sha256=%s bytes=%d"
              % (a.json, hashlib.sha256(raw).hexdigest()[:16], len(raw)))
    if a.json == "-":
        print("QUALITYPEER-NOLEDGER: 本次未落台账 ⇒ stdout 读数不得据以改判（r66 立的逃生门，禁当默认用）")
    return 1 if blind else 0


if __name__ == "__main__":
    sys.exit(main())
