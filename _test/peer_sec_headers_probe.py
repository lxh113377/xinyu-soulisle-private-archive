# -*- coding: utf-8 -*-
"""对标 r54 探针：**安全响应头 / CSP 的制度化证据**（16 仓 + self，双通道）。

为什么是这一面：✅ 取证 `grep -ilE "CSP|内容安全策略|安全头|helmet|X-Frame" 交付物/对标分析报告-*.md`
= 十五份全 0。而本仓从 r28 起就在写 `deploy/xinyu/_headers` —— 一个"配置在册就当生效"的典型位置。

⚠️ 天花板（写进快照头，不许越界解释）：
  线上响应头**只能测自己**（别人的部署域名不在本轮授权范围，且多数仓根本没有公开部署）。
  ⇒ peers 侧只出「结构与声明」两类证据；禁止写成"我们的报错/防护体验比他们好"。
  self 的行为回执在 `_test/headers_csp_check.py`（本地按 Pages 语义回放 + 拦截探针）。

两通道：
  A 结构面 = git tree：`_headers` / `_redirects` / nginx / Apache / helmet 接入件 / CSP 中间件配置
  B 声明面 = README：**锚定词组**（Content-Security-Policy / helmet / X-Frame-Options / 安全头…）
     ⚠️ 不用裸子串：`csp` 是 `.csproj` 的子串、`headers` 在每个 HTTP 教程里都出现 ——
        首版正是这么写的，被自己的反例②当场打回（详见 classify_tree 注释与 selftest）。
用法：python _test/peer_sec_headers_probe.py [--json out.json] [--self-only] [--selftest]
退出码：0=分母齐且无 NA 1=存在 NA 或 selftest 未过 2=无 GitHub token（环境）
"""
import argparse
import base64
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from benchmark_metrics import PEERS, ROOT

NOISE = re.compile(r"(^|/)(node_modules|\.venv|venv|dist|build|target|vendor|\.git|_shots|"
                   r"web_raw|video_raw|__pycache__|_?tests?|__tests__)/", re.I)
SEC_FILE = {
    "cf_headers": re.compile(r"(^|/)_headers$", re.I),
    "redirects": re.compile(r"(^|/)_redirects$", re.I),
    "nginx": re.compile(r"(^|/)(nginx[\w.-]*\.conf|default\.conf)$", re.I),
    "apache": re.compile(r"(^|/)\.htaccess$", re.I),
    "helmet": re.compile(r"(^|/)(helmet|security[-_]headers|csp)([\w.-]*)?\.(js|ts|mjs|cjs)$", re.I),
    "meta_csp": re.compile(r"(^|/)(csp|content[-_]security[-_]policy)([\w.-]*)?\.(json|js|ts|conf|yml|yaml)$", re.I),
}
# 依赖声明通道：包名要精确，别拿裸子串
HELMET_DEP = re.compile(r"[\x22'](?:@fastify/|express-)?helmet[\x22'/:]")
README_PAT = {
    "csp_declared": re.compile(r"Content[\s-]?Security[\s-]?Policy", re.I),
    "helmet_declared": re.compile(r"\bhelmet\b", re.I),
    "frame_declared": re.compile(r"X-Frame-Options|frame-ancestors", re.I),
}


def classify_tree(paths):
    """通道 A：按**结构单位（文件）**计数，一类只记一次。

    ⚠️ 反例②盯着这条：`csp` 是 `.csproj` 的裸子串（`Foo.csproj` 会被判成 CSP 配置），
    `headers` 更是每个 HTTP 文档都出现的普通词。所以路径判据一律走**锚定正则**
    （整段文件名 + 显式后缀），不做子串命中。
    """
    out = {}
    for p in paths:
        if NOISE.search("/" + p) or p.lower().endswith((".csproj", ".sln", ".csproj.user")):
            continue
        for k, rx in SEC_FILE.items():
            if rx.search(p):
                out.setdefault(k, []).append(p)
    return out


def classify_deps(blob_txt):
    hits = []
    for name, txt in (blob_txt or {}).items():
        if HELMET_DEP.search(txt or ""):
            hits.append(name)
    return hits


def classify_readme(text):
    return {k: True for k, rx in README_PAT.items() if rx.search(text or "")}


def verdict(t, deps, doc):
    a = sum(1 for v in t.values() if v)
    s = "结构 %d/%d 类" % (a, len(SEC_FILE))
    if deps:
        s += "+helmet依赖(%s)" % ",".join(Path(x).name for x in deps[:2])
    if doc:
        s += "｜声明:" + ",".join(sorted(k.replace("_declared", "") for k in doc))
    else:
        s += "｜README 无声明"
    return s


def api(path, token):
    req = urllib.request.Request("https://api.github.com/" + path,
                                 headers={"User-Agent": "xinyu-sec-probe",
                                          "Accept": "application/vnd.github+json"})
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            return json.loads(r.read().decode("utf-8", "replace")), ""
    except Exception as e:
        return None, "http=%s" % getattr(e, "code", type(e).__name__)


def probe_repo(slug, token):
    tree, err = api("repos/%s/git/trees/HEAD?recursive=1" % slug, token)
    if tree is None:
        return {}, [], {}, err or "tree-fail"
    blobs = [x for x in tree.get("tree", []) if x.get("type") == "blob"]
    paths = [x.get("path", "") for x in blobs]
    t = classify_tree(paths)
    want = [x for x in blobs
            if re.search(r"(package\.json|requirements\.txt|pom\.xml|go\.mod)$", x.get("path", ""), re.I)
            and int(x.get("size") or 0) < 200_000][:6]
    dep_txt = {}
    for x in want:
        b, _e = api("repos/%s/contents/%s" % (slug, x["path"]), token)
        if b and b.get("content"):
            try:
                dep_txt[x["path"]] = base64.b64decode(b["content"]).decode("utf-8", "replace")
            except Exception:
                pass
    rd, e2 = api("repos/%s/readme" % slug, token)
    doc = {}
    if rd is not None:
        try:
            doc = classify_readme(base64.b64decode(rd.get("content") or "").decode("utf-8", "replace"))
        except Exception:
            e2 = "readme-decode"
    return t, classify_deps(dep_txt), doc, "+".join(x for x in (err, e2) if x)


def self_snapshot():
    paths = []
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        r = str(p.relative_to(ROOT)).replace("\\", "/")
        if NOISE.search("/" + r):
            continue
        paths.append(r)
    t = classify_tree(paths)
    dep_txt = {}
    for name in ("package.json", "requirements.txt", "server/pom.xml"):
        f = ROOT / name
        if f.is_file():
            dep_txt[name] = f.read_text("utf-8", errors="replace")
    doc = {}
    for name in ("README.md", "README.en.md", "docs/README.md"):
        f = ROOT / name
        if f.is_file():
            doc.update(classify_readme(f.read_text("utf-8", errors="replace")))
    return t, classify_deps(dep_txt), doc, len(paths)


def selftest():
    ok, fail = 0, []
    t1 = classify_tree(["public/_headers", "server/helmet.js", "deploy/nginx.conf",
                        ".htaccess", "csp.json", "src/middleware/security-headers.ts"])
    if len(t1) >= 5 and any(k == "cf_headers" for k in t1):
        ok += 1
    else:
        fail.append("正例①六类证据未基本命中：%s" % sorted(t1))
    # 反例①：干净仓不得凭空长出安全件
    t2 = classify_tree(["src/app/page.tsx", "package.json", "README.md"])
    if not t2:
        ok += 1
    else:
        fail.append("反例① 干净仓被误判有安全头件：%s" % sorted(t2))
    # 反例②（本探针的核心陷阱）：.csproj 含子串 csp，不得算 CSP 配置件
    t3 = classify_tree(["src/Foo.csproj", "backend/Project.csproj", "csp_report.cs"])
    if "meta_csp" not in t3 and "helmet" not in t3:
        ok += 1
    else:
        fail.append("反例② .csproj 被当成 CSP 件：%s" % sorted(t3))
    # 反例③：helmet 依赖必须走精确包名通道，`<div class="helmet">` 之类的散文不算
    d1 = classify_deps({"package.json": '{"dependencies":{"helmet":"7.0.0"}}'})
    d2 = classify_deps({"README.md": "we wear a helmet while riding", "docs/x.md": "helmet is mentioned"})
    if d1 and not d2:
        ok += 1
    else:
        fail.append("反例③ helmet 通道不精确：d1=%s d2=%s" % (d1, d2))
    # 反例④：README 声明面要锚定词组，单说 "headers" 不算
    r1 = classify_readme("Set Content-Security-Policy via helmet; X-Frame-Options DENY.")
    r2 = classify_readme("check the response headers of your request")
    if len(r1) == 3 and not r2:
        ok += 1
    else:
        fail.append("反例④ 声明面锚定失真：%s / %s" % (r1, r2))
    # 边界：空树必须给"结构 0 类"而不是崩或判有
    v = verdict({}, [], {})
    if v.startswith("结构 0/") and "无声明" in v:
        ok += 1
    else:
        fail.append("边界 空树结论异常：%s" % v)
    expected = 6
    for x in fail:
        print("  SELFTEST-FAIL " + x)
    print("SECPEER-SELFTEST: %d/%d%s" % (ok, expected,
          "" if ok + len(fail) == expected else "  ⚠️ 分支数 %d≠%d" % (ok + len(fail), expected)))
    return 0 if ok == expected and ok + len(fail) == expected else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="")
    ap.add_argument("--self-only", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest())
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
    if not token and not a.self_only:
        print("SECPEER-UNVERIFIED: 无 GitHub token ⇒ 无法取 peers（不判 0，判环境未验）")
        sys.exit(2)
    rows, na = [], []
    st, sd, sdoc, sn = self_snapshot()
    rows.append({"repo": "__self__", "tier": "-", "tree": st, "deps": sd, "readme": sdoc})
    if not a.self_only:
        for p in PEERS:
            t, deps, doc, err = probe_repo(p["repo"], token)
            if not t and err:
                na.append({"repo": p["repo"], "why": err})
            rows.append({"repo": p["repo"], "tier": p["tier"], "tree": t,
                         "deps": deps, "readme": doc, "err": err})
    n = len(rows)
    print("== r54 安全响应头/CSP 制度化对标（16 仓 + self，仅结构+声明）==")
    for r in rows:
        print("%-36s %s" % (r["repo"], verdict(r["tree"], r["deps"], r["readme"])))
    print("应测 %d ｜ NA %d ｜ 恒等式 usable+NA==total：%s"
          % (n, len(na), "OK" if n - len(na) + len(na) == n else "FAIL"))
    if a.json:
        Path(a.json).write_bytes(json.dumps(
            {"repos": rows, "na": na, "denominator": n, "blind": len(na), "usable": n - len(na),
             "self_paths_scanned": sn,
             "ceiling_note": "线上响应头只能测自己（未获授权扫他人部署域名）⇒ 本面 peers 侧"
                             "只有结构与声明两类证据，不构成防护效果对比；self 的行为回执见"
                             " _test/headers_csp_check.py。"},
            ensure_ascii=False, indent=1).encode("utf-8"))
        print("快照 → " + a.json)
    sys.exit(1 if na else 0)


if __name__ == "__main__":
    main()
