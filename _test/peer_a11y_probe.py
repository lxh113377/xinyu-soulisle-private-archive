# -*- coding: utf-8 -*-
"""对标 r42 探针：**无障碍与制度化（a11y）**（16 仓 + self，三通道同尺）。

为什么是这一面：用户要的七维里，「功能覆盖/架构/性能/维护/文档/场景」前六维都进过观测窗
（r26 安全、r26 卫生、r27 测试资产、r36 行尾、r37 可得性、r40 性能），
`grep -l 无障碍` 在五份既有对标报告里 **0 命中** —— 这一维从来没被量过。
而它对本项目不是"合规加分项"：产品承诺是"情绪倾诉陪伴"，用语音控制、读屏、
或对动效敏感的人恰好是最需要它、也最容易被暗底星雾挡在门外的一批用户。

三通道（承 r38/r41 的 M5⑦⑧⑨ 纪律，互为独立证据）：
  通道 A 文件树：默认分支递归树里**以 a11y 命名**的构建件/专章（.pa11yci、lighthouserc、
                **/a11y*、**/accessibility*、WCAG*）⇒ 制度化"有地方放"
  通道 B README：正文里的无障碍声明（accessibility / a11y / WCAG / screen reader / 无障碍）
  通道 C 清单文件：真正**依赖了 a11y 工具库**（axe-core / jest-axe / cypress-axe / pa11y /
                eslint-plugin-jsx-a11y / lighthouse / @axe-core/* / axe-py / pa11y-ci）
                —— A 的零结论必须有 C 做第二通道，否则"没人做"与"我没数到"分不清。
                清单语言相关（JS 有 package.json，Python 有 requirements/pyproject，Java 多半没有）
                ⇒ `not_applicable` 单列，**禁止并入 0**。

两侧同尺：self 用同一组正则跑工作树与 README，不给自己开例外。
未取到一律记 NA(原因)；truncated 的仓其零命中不作数。
用法：python _test/peer_a11y_probe.py [--json out.json] [--self-only] [--selftest]
退出码：0=分母齐且无 NA 1=存在 NA 或 selftest 未过 2=无 GitHub token（环境）
"""
import argparse
import base64
import json
import os
import re
import subprocess
from datetime import datetime, timezone
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from benchmark_metrics import PEERS, ROOT

# ---------- 三通道判据 ----------
# 依赖目录与构建产物必须先排掉：否则 node_modules/axe-core 会让任何装了它的项目"有 a11y"，
# 而装了不用与没装是两件事（承 r37 M5⑪ 配置在册 vs 行为闭环）。
NOISE = re.compile(r"(^|/)(node_modules|vendor|dist|build|target|\.venv|venv|site-packages"
                   r"|\.git/|cache|coverage|\.next|\.nuxt)/", re.I)
# 通道 A：以 a11y 命名的件
A11Y_PATH = re.compile(
    r"(^|/)(\.?pa11yci[-\w.]*|lighthouserc[-\w.]*|\.lighthouserc[-\w.]*"
    r"|a11y[-\w.]*|[-\w.]*[-_]a11y[-\w.]*|accessibility[-\w.]*|[-\w.]*[-_]accessibility[-\w.]*"
    r"|wcag[-\w.]*)$", re.I)
# 通道 A 的反例护栏：这些名字里含 a11y/accessibility 子串但不是无障碍件。
# ⚠ `Accessibility.dll` **不是**我编的假想反例：首跑真实命中里就有它（opensoul 仓库带两个
# `apps/windows/src/OpenSoul/publish/Accessibility.dll`，那是 .NET 的 UI 自动化**框架程序集**，
# 与"这个产品做了无障碍"无关）。不挡掉就给对手凭空加一格能力（M5⑨"先归因语境再计数"）。
NOT_A11Y = re.compile(r"(accessibility[_.-]?(policy|hash|audit-log)|\.dll$|\.so$|\.dylib$"
                      r"|lazy|easy|release)", re.I)
# 通道 B：README 声明
README_RX = {
    "a11y_claim": re.compile(r"(accessib|a11y|WCAG|screen[- ]?reader|辅助功能|无障碍|可访问性)", re.I),
    "a11y_badge": re.compile(r"badge[/%-]?(accessibility|a11y|wcag)", re.I),
}
# 通道 C：清单里真的依赖了 a11y 工具。**只扫 JS/Py/Ruby/PHP 系清单**——
# JVM 侧没有通用的 axe/pa11y 依赖生态，把 `lighthouse` 这种通用词丢进 pom.xml 只会造出假命中
# （selftest 反例⑥专门钉这一点）。
SCAN_MANIFEST = re.compile(r"(^|/)(package\.json|requirements[^/]*\.txt|pyproject\.toml"
                           r"|setup\.py|Gemfile|composer\.json)$")
JVM_MANIFEST = re.compile(r"(^|/)(pom\.xml|build\.gradle(\.kts)?|settings\.gradle)$")
MANIFEST_RX = re.compile(
    r"(?:^|[\"\s=/])("
    r"@axe-core/[\w.-]+|axe-core|jest-axe|cypress-axe|@pa11y/[\w.-]+|pa11y-ci|pa11y"
    r"|eslint-plugin-jsx-a11y|eslint-plugin-vue-a11y|@vue-a11y/[\w.-]+|vue-a11y"
    r"|sveltejs-accessibility|react-axe|axe-puppeteer|puppeteer-axe|lighthouse"
    r"|@lhci/cli|axe-py|accessibility-checker)(?:[\"\s,]|$)")


def dep_hits(text):
    """清单正文 -> 命中的 a11y 库名集合（纯函数，selftest 直接打它）。"""
    return sorted({m.group(1) for m in MANIFEST_RX.finditer(text)})



def classify_tree(paths):
    """paths: [相对路径] -> dict(a11y_named, named_samples, manifests, jvm_manifests)"""
    named = [p for p in paths if A11Y_PATH.search(p.split("/")[-1])
             and not NOISE.search(p) and not NOT_A11Y.search(p)]
    manifests = sorted(p for p in paths if SCAN_MANIFEST.search(p) and not NOISE.search(p))
    jvm = sorted(p for p in paths if JVM_MANIFEST.search(p) and not NOISE.search(p))
    return {"a11y_named": len(named), "named_samples": sorted(named)[:4],
            "manifests": manifests[:4], "jvm_manifests": jvm[:2]}


def dep_status_of(row):
    """三态而非二态：ok / not_applicable（只有 JVM 清单）/ unverified（取了但失败）。"""
    if row["deps"]:
        return "ok"
    if row["dep_err"]:
        return "unverified:" + ";".join(row["dep_err"])
    if not row["manifest_count"]:
        return ("not_applicable(仅 JVM 清单)" if row["jvm_manifests"] else "not_applicable(无通用清单)")
    return "ok"



def api(path, token):
    req = urllib.request.Request("https://api.github.com/" + path,
                                 headers={"User-Agent": "xinyu-a11y-probe",
                                          "Accept": "application/vnd.github+json"})
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            return json.loads(r.read().decode("utf-8", "replace")), ""
    except Exception as e:
        return None, "http=%s" % getattr(e, "code", type(e).__name__)


def fetch_file(slug, path, token):
    data, err = api("repos/%s/contents/%s" % (slug, path), token)
    if data is None:
        return "", err
    try:
        raw = base64.b64decode(data.get("content") or "").decode("utf-8", "replace")
    except Exception as e:
        return "", "decode:%s" % e
    if len(raw) > 900_000:
        return raw[:900_000], ""
    return raw, ""


def probe_repo(slug, token):
    """-> (row, blind_reason) ；blind 非空表示该仓不可计入分母，须点名原因。"""
    data, err = api("repos/%s/git/trees/HEAD?recursive=1" % slug, token)
    if data is None:
        return {}, "tree:" + err
    if data.get("truncated"):
        return {}, "tree:truncated(零命中不可信)"
    paths = [t.get("path", "") for t in data.get("tree", []) if t.get("type") == "blob"]
    row = {"tree": classify_tree(paths)}

    rdata, rerr = api("repos/%s/readme" % slug, token)
    if rdata is None:
        row["readme"] = {}
        row["readme_err"] = rerr
    else:
        try:
            txt = base64.b64decode(rdata.get("content") or "").decode("utf-8", "replace")
        except Exception as e:
            txt, row["readme_err"] = "", "decode:%s" % e
        out = {}
        for k, rx in README_RX.items():
            m = rx.findall(txt)
            if m:
                first = m[0] if isinstance(m[0], str) else str(m[0])
                out[k] = "%d 处｜样本 %r" % (len(m), first[:40])
        row["readme"] = out

    # 通道 C：最多读两个清单，避免为一个大仓拉全量
    deps, derr = [], []
    for mp in row["tree"]["manifests"][:2]:
        raw, e = fetch_file(slug, mp, token)
        if e:
            derr.append("%s(%s)" % (mp.split("/")[-1], e))
            continue
        hits = dep_hits(raw)
        if hits:
            deps.append({"file": mp, "libs": hits[:6]})
    row["deps"] = deps
    row["dep_err"] = derr
    row["manifest_count"] = len(row["tree"]["manifests"])
    row["jvm_manifests"] = row["tree"]["jvm_manifests"]
    row["dep_status"] = dep_status_of(row)
    return row, ""


# ---------- self：同一把尺跑工作树 ----------
SKIP_PARTS = ("/.git/", "node_modules/", ".codebuddy/", "_shots/", "target/", "server/data/",
              "web_raw/", "video_raw/", ".wrangler/", ".venv/")


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
    paths = self_paths()
    t = classify_tree(paths)
    out = {"tree": t, "readme": {}, "deps": [], "dep_err": [], "dep_status": "ok",
           "manifest_count": 0, "jvm_manifests": []}
    fp = ROOT / "README.md"
    if fp.exists():
        txt = fp.read_bytes().decode("utf-8", "replace")
        for k, rx in README_RX.items():
            m = rx.findall(txt)
            if m:
                first = m[0] if isinstance(m[0], str) else str(m[0])
                out["readme"][k] = "%d 处｜样本 %r" % (len(m), first[:40])
    for mp in t["manifests"][:2]:
        f = ROOT / mp
        if not f.exists():
            continue
        hits = dep_hits(f.read_bytes().decode("utf-8", "replace"))
        if hits:
            out["deps"].append({"file": mp, "libs": hits[:6]})
    out["manifest_count"] = len(t["manifests"])
    out["jvm_manifests"] = t["jvm_manifests"]
    out["dep_status"] = dep_status_of(out)
    return out


# ---------- selftest：正例 / 反例 / 边界，双向 ----------
FIXTURE = [
    ("packages/ui/.pa11yci", True, "pa11y CI 配置"),
    ("lighthouserc.js", True, "lighthouse CI 配置"),
    ("docs/accessibility", True, "无障碍专章（无扩展名）"),
    ("src/styles/a11y.css", True, "a11y 样式件"),
    ("tests/a11y.spec.ts", True, "a11y 用例"),
    ("WCAG21-Checklist.md", True, "WCAG 清单"),
    ("node_modules/axe-core/axe.js", False, "反例①：依赖目录不得算"),
    ("dist/a11y-bundle.js", False, "反例②：构建产物不算源件"),
    ("src/utils/release-notes.md", False, "反例③：release 含 elease 子串不该命中"),
    ("src/pages/easy-mode.tsx", False, "反例④：easy 含 a11y? 不含，双保险"),
    ("docs/accessibility-policy.md", False, "反例⑤：合规声明页非工具件（存疑项，宁缺）"),
    ("apps/windows/src/OpenSoul/publish/Accessibility.dll", False,
     "反例⑩：.NET 框架程序集，首跑真实假阳性（opensoul），不挡则给对手凭空加一格"),
    ("vendor/a11y-shim.js", False, "反例⑪：vendor 目录一律不算源件"),
]
DEP_FIXTURE = [
    ('"axe-core": "^4.10.2"', "axe-core", "正例①：package.json 依赖 axe-core"),
    ('"devDependencies": {"jest-axe": "^9.0.0"}', "jest-axe", "正例②：jest-axe"),
    ('"eslint-plugin-jsx-a11y": "^8.9.0"', "eslint-plugin-jsx-a11y", "正例③：JSX a11y lint 插件"),
    ('"@axe-core/playwright": "^4.10.0"', "@axe-core/playwright", "正例④：scoped 包名要整名命中"),
    ('"lighthouse": "^12.0.0"', "lighthouse", "正例⑤：lighthouse 作为依赖"),
    ("<artifactId>lighthouse</artifactId>", None, "反例⑥：尖括号包裹不算 JS 清单依赖（挡 JVM 假命中）"),
    ("# axe mentioned in a comment", None, "反例⑦：行内裸词不得算依赖"),
    ("nothing to see here", None, "反例⑧：无命中必须为空"),
]


# 通道 B 的正样本：peers 首跑 16/16 README 全 `none`，若不先证明这条正则**会命中**，
# "0/16 家声明无障碍"就分不清是"对手都没写"还是"我这把尺是瞎的"（M5④）。
README_FIXTURE = [
    ("We take accessibility seriously.", "a11y_claim", "英文 accessibility"),
    ("遵循 WCAG 2.1 AA。", "a11y_claim", "WCAG 引用"),
    ("本站支持读屏（screen reader）。", "a11y_claim", "读屏"),
    ("项目已完成无障碍适配。", "a11y_claim", "中文无障碍"),
    ("[![a11y](https://img.shields.io/badge/accessibility-passing-green)]", "a11y_badge", "徽章"),
    ("This chat app is cute.", None, "反例⑨：普通 README 不得命中"),
    ("See ACCESSLOG.md for request trail.", None, "反例⑩：access 子串不是 accessibility"),
]


def readme_hits(txt):
    return sorted(k for k, rx in README_RX.items() if rx.search(txt))


def run_selftest():
    ok, fail = 0, []
    for path, want, note in FIXTURE:
        got = classify_tree([path])["a11y_named"] == 1
        if got == want:
            ok += 1
        else:
            fail.append("%s want=%s got=%s (%s)" % (note, want, got, path))
    for text, want, note in DEP_FIXTURE:
        hits = dep_hits(text)
        got = (want in hits) if want else (not hits)
        if got:
            ok += 1
        else:
            fail.append("%s want=%s hits=%s" % (note, want, hits))
    for text, want, note in README_FIXTURE:
        hits = readme_hits(text)
        got = (want in hits) if want else (not hits)
        if got:
            ok += 1
        else:
            fail.append("%s want=%s hits=%s" % (note, want, hits))
    # 边界 A：零输入不得判绿（防"分母空=全过"）
    e = classify_tree([])
    if e["a11y_named"] == 0 and e["manifests"] == []:
        ok += 1
    else:
        fail.append("边界A 零输入异常")
    # 边界 B：混合集计数 == 逐条之和（防去重/漏计）
    total = classify_tree([f[0] for f in FIXTURE])["a11y_named"]
    want_total = sum(1 for f in FIXTURE if f[1])
    if total == want_total:
        ok += 1
    else:
        fail.append("边界B 计数 %d != 期望 %d" % (total, want_total))
    # 边界 C：dep_status_of 三态不得塌成两态（JVM-only 必须是"不适用"而非"零命中"）
    three = [dep_status_of({"deps": [], "dep_err": [], "manifest_count": 0, "jvm_manifests": ["pom.xml"]}),
             dep_status_of({"deps": [], "dep_err": ["package.json(http=404)"], "manifest_count": 1,
                            "jvm_manifests": []}),
             dep_status_of({"deps": [{"file": "package.json", "libs": ["axe-core"]}],
                            "dep_err": [], "manifest_count": 1, "jvm_manifests": []})]
    if three[0].startswith("not_applicable") and three[1].startswith("unverified") and three[2] == "ok":
        ok += 1
    else:
        fail.append("边界C 三态塌陷 %s" % three)
    n = len(FIXTURE) + len(DEP_FIXTURE) + len(README_FIXTURE) + 3
    for x in fail:
        print("  A11Y-SELFTEST-FAIL " + x)
    # 计数一律现算，不手抄（V1.14.0 同源：手抄的条数一定会落后）
    print("A11Y-SELFTEST: %d/%d（路径 %d＝正%d/反%d｜依赖 %d＝正%d/反%d｜README %d＝正%d/反%d｜边界 3）"
          % (ok, n, len(FIXTURE), sum(1 for f in FIXTURE if f[1]),
             sum(1 for f in FIXTURE if not f[1]), len(DEP_FIXTURE),
             sum(1 for f in DEP_FIXTURE if f[1]), sum(1 for f in DEP_FIXTURE if not f[1]),
             len(README_FIXTURE), sum(1 for f in README_FIXTURE if f[1]),
             sum(1 for f in README_FIXTURE if not f[1])))
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
        print("A11Y-ENV: 无 GitHub token（gh auth token 失败）⇒ 不采数、不判绿")
        return 2

    rows, blind = {}, []
    for p in ([] if a.self_only else PEERS):
        slug, tier = p["repo"], p["tier"]
        row, reason = probe_repo(slug, token)
        if reason:
            blind.append("%s(%s)" % (slug, reason))
            print("[%-3s] %-36s BLIND %s" % (tier, slug, reason))
            continue
        rows[slug] = {"tier": tier, **row}
        t = row["tree"]
        print("[%-3s] %-36s 命名件=%-2d README=%-22s 清单=%d 依赖命中=%s (%s)"
              % (tier, slug, t["a11y_named"], ",".join(sorted(row["readme"])) or "none",
                 row["manifest_count"],
                 ";".join("%s:%s" % (d["file"].split("/")[-1], ",".join(d["libs"])) for d in row["deps"]) or "none",
                 row["dep_status"]))
    st = probe_self()
    rows["__self__"] = st
    print("[self] %-36s 命名件=%-2d README=%-22s 清单=%d 依赖命中=%s (%s)"
          % ("心屿 MindIsle", st["tree"]["a11y_named"], ",".join(sorted(st["readme"])) or "none",
             st["manifest_count"],
             ";".join(",".join(d["libs"]) for d in st["deps"]) or "none", st["dep_status"]))
    print("-" * 124)
    n = len(rows) - (0 if a.self_only else 1)
    if n:
        named = sum(1 for k, v in rows.items() if k != "__self__" and v["tree"]["a11y_named"] > 0)
        claim = sum(1 for k, v in rows.items() if k != "__self__" and v.get("readme"))
        depok = [k for k, v in rows.items() if k != "__self__" and v.get("dep_status") == "ok"]
        dephit = sum(1 for k in depok if rows[k]["deps"])
        na_dep = [k for k, v in rows.items() if k != "__self__" and v.get("dep_status") != "ok"]
        print("peers：有 a11y 命名件 %d/%d ｜ README 有无障碍声明 %d/%d ｜ 清单真依赖 a11y 库 %d/%d（不适用/未取到 %d 家：%s）"
              % (named, n, claim, n, dephit, len(depok), len(na_dep),
                 ",".join("%s(%s)" % (k.split("/")[-1], rows[k]["dep_status"]) for k in na_dep) or "-"))
        for k, v in sorted(rows.items(), key=lambda x: -x[1]["tree"]["a11y_named"]):
            if k == "__self__":
                continue
            if v["tree"]["a11y_named"] or v["deps"]:
                print("   %-36s 命名件=%d %s" % (k, v["tree"]["a11y_named"], v["tree"]["named_samples"][:2]))
    usable = n - len(blind)
    print("应测 %s 仓 ｜ 计入分母 %s ｜ BLIND %d ｜ 恒等式 usable+blind==总数：%s"
          % (n, usable, len(blind), "OK" if usable + len(blind) == n else "FAIL"))
    if blind:
        print("  BLIND 明细：" + "; ".join(blind))
    if a.json:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        Path(a.json).write_bytes(json.dumps(
            {"repos": rows, "blind": blind, "denominator": n, "usable": usable, "ts": ts},
            ensure_ascii=False, indent=1).encode("utf-8"))
        print("快照 -> " + a.json)
    if a.self_only:
        return 0
    return 1 if (blind or usable + len(blind) != n) else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
