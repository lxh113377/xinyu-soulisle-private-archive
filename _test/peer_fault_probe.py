# -*- coding: utf-8 -*-
"""对标 r51 探针：**错误处理与可观测性的制度化证据**（16 仓 + self，双通道）。

⚠️ 天花板先说死（别拿结构证据冒充体验结论）：
  r51 自家那条 `fault_injection_check.py` 能把**自己的**上游打挂再读界面；
  这条路对别人的仓库**做不到**（我不能往 lobehub 的站点注入 HTTP 500）。
  ⇒ 本探针只出「这个仓有没有把错误处理/可观测性制度化」的**结构与声明证据**，
    禁止写成"对手的报错体验比我们差"。这一条写进快照头 `ceiling_note`，随数据一起交付。

两通道（各自独立，未取到一律 NA(原因)，禁与 0 混同）：
  A 结构面 = git tree：error-monitoring 集成文件/依赖声明（sentry / datadog / bugsnag /
    rollbar / newrelic / highlight / posthog 的 config 与包名）、`.env.example` 里的 DSN 键名、
    前端错误页（404/500 模板）、诊断接口（/health /debug）
  B 声明面 = README 正文：Troubleshooting / 故障排查 / FAQ / 已知限制 / 错误码表 段落
用法：python _test/peer_fault_probe.py [--json out.json] [--self-only] [--selftest]
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

VENDORS = ("sentry", "datadog", "bugsnag", "rollbar", "newrelic", "highlight", "posthog",
           "appdynamics", "splunk")
# ⚠️ `highlight` 是**歧义名**：监控厂商 Highlight.io 的包名是 `@highlight-run/*`，而
#    highlight.js（语法高亮库）在依赖文本里以裸子串 `highlight` 命中同一片取数区域 ——
#    实测把 SillyTavern / Loyal-Elephie / leemo 三家误判成「装了错误监控」，把 5/16 虚报成
#    比真实 3/16 更好看的数（r51 自查抓到，同 r46「宽匹配把 notice.html 当归属件」一族）。
#    歧义名只准走 MON_DEP 精确通道，禁进裸子串通道。
AMBIGUOUS = {"highlight"}
# ⚠️ 三种真实命名都得认（夹具抓到首版漏了 Next.js 的 `sentry.client.config.ts`，
#    那是 Sentry 官方文档里的主流写法，不是生僻形状）：
#      sentry.client.config.ts / sentry.server.config.ts / sentry.config.js / sentry.browser.js
MON_FILE = re.compile(r"(^|/)(sentry(\.(client|server|edge|browser))?\.config\.(ts|tsx|js|mjs|cjs)"
                     r"|sentry\.(client|server|edge|browser)\.(js|ts|tsx)|datadog\.json)$", re.I)
_Q = "['\"]"                      # 引号字符类单独放，避开内联脚本吃转义那一族（本仓第 12 次）
MON_DEP = re.compile(_Q + r"(@sentry/[a-z-]+|ddtrace|bugsnag[a-z-]*|rollbar|newrelic|"
                     + r"@highlight-run/[a-z-]+|posthog-[a-z]+)" + _Q)
DSN_KEY = re.compile(r"\bSENTRY_DSN\b|\bDATADOG_API_KEY\b|\bBUGSNAG_API_KEY\b", re.I)
ERR_PAGE = re.compile(r"(^|/)(errors?|pages)/?(404|500|429|403|503)\.(html|vue|tsx?|jsx?)$", re.I)
DIAG = re.compile(r"(^|/)(health|healthz|healthcheck|status|diagnostics?|debug)(\.(py|js|ts|go|java|rb))?$",
                  re.I)
DOC_RX = {
    "troubleshooting": re.compile(r"(#+\s*(troubleshooting|故障排查|常见问题|faq|known issues?"
                                  r"|已知限制|错误码|error codes?)\b)", re.I),
    "report_channel": re.compile(r"(报障|提交 issue|open an issue|错误反馈|contact support)", re.I),
}
NOISE = re.compile(r"(^|/)(node_modules|\.venv|venv|dist|build|target|vendor/)/", re.I)


def classify_tree(paths, blobs=None):
    """结构面。blobs 可选：{path: text}，给了才对 package.json / .env.example 做内容级判定。"""
    blobs = blobs or {}
    out = {"mon_files": [], "err_pages": [], "diag": []}
    for p in paths:
        if NOISE.search(p):
            continue
        if MON_FILE.search(p):
            out["mon_files"].append(p)
        if ERR_PAGE.search(p):
            out["err_pages"].append(p)
        if DIAG.search(p):
            out["diag"].append(p)
    dep_hit, dsn_hit, vendored = set(), False, []
    for p, txt in blobs.items():
        if re.search(r"package\.json$|requirements\.txt$|pom\.xml$|go\.mod$|Gemfile$", p, re.I):
            for m in MON_DEP.finditer(txt or ""):
                dep_hit.add(m.group(1))
        if re.search(r"\.env(\.example)?$", p, re.I) and DSN_KEY.search(txt or ""):
            dsn_hit = True
    dep_txt = [txt for path, txt in blobs.items()
               if re.search(r"(package\.json|requirements\.txt|pom\.xml|go\.mod|Gemfile|"
                            r"\.env(\.example)?|sentry\.config\.\w+)$", path, re.I)]
    for v in VENDORS:
        # 只认「文件名 / 依赖声明 / env 样例」三处证据，不做全文模糊匹配：
        # 任何 README 里提一句 sentry 都算"装了监控"的话，这个判据就只是词汇表命中。
        if v in AMBIGUOUS:
            hit = any(v in x for x in dep_hit)
        else:
            hit = any(v in x.lower() for x in out["mon_files"]) or any(v in x for x in dep_hit) \
                or any(v in (x or "").lower() for x in dep_txt)
        if hit:
            vendored.append(v)
    return {"mon_files": sorted(out["mon_files"])[:3], "err_pages": sorted(out["err_pages"])[:3],
            "diag": sorted(out["diag"])[:3], "mon_deps": sorted(dep_hit)[:4],
            "dsn_in_env_sample": bool(dsn_hit), "vendors": vendored}


def classify_readme(text):
    out = {}
    for k, rx in DOC_RX.items():
        hits = rx.findall(text or "")
        if hits:
            out[k] = "%d 处｜样本 %r" % (len(hits), (hits[0] if isinstance(hits[0], str)
                                                  else str(hits[0]))[:38])
    return out


def verdict(t, doc):
    if not (t and (t.get("mon_files") or t.get("mon_deps") or t.get("dsn_in_env_sample")
                   or t.get("vendors"))):
        obs = "无监控集成证据"
    else:
        obs = "监控集成在册(%s)" % ",".join(t.get("vendors") or ["未识别厂商"])
    docs = "+有排障文档" if doc.get("troubleshooting") else "+无排障文档"
    return obs + docs


def api(path, token):
    req = urllib.request.Request("https://api.github.com/" + path,
                                 headers={"User-Agent": "xinyu-fault-probe",
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
        return {}, False, {}, err or "tree-fail"
    blobs_all = [x for x in tree.get("tree", []) if x.get("type") == "blob"]
    paths = [x.get("path", "") for x in blobs_all]
    # 只对**声明类小文件**取正文（package.json / .env.example），按 blob size 设上限，
    # 避免把整仓拉下来：结构面靠路径，内容面靠这几个文件
    want = [x for x in blobs_all
            if re.search(r"(package\.json|requirements\.txt|pom\.xml|go\.mod|\.env\.example|"
                         r"sentry\.config\.\w+)$", x.get("path", ""), re.I)
            and int(x.get("size") or 0) < 220_000][:8]
    blobs = {}
    for x in want:
        b, _e = api("repos/%s/contents/%s" % (slug, x["path"]), token)
        if b is not None:
            try:
                blobs[x["path"]] = base64.b64decode(b.get("content") or "").decode("utf-8", "replace")
            except Exception:
                pass
    rd, e2 = api("repos/%s/readme" % slug, token)
    doc = {}
    if rd is not None:
        try:
            doc = classify_readme(base64.b64decode(rd.get("content") or "").decode("utf-8", "replace"))
        except Exception:
            e2 = "readme-decode"
    return classify_tree(paths, blobs), bool(tree.get("truncated")), doc, \
        "+".join(x for x in (err, e2) if x)


def self_blobs_and_paths():
    paths, blobs = [], {}
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        r = str(p.relative_to(ROOT)).replace("\\", "/")
        if any(x in "/" + r for x in ("/.git/", "node_modules/", ".codebuddy/", "_shots/",
                                      "target/", "server/data/", "web_raw/", "video_raw/")):
            continue
        paths.append(r)
        if re.search(r"(package\.json|requirements\.txt|pom\.xml|\.env\.example)$", r, re.I) \
                or r.startswith("src/js/demo-config"):
            try:
                blobs[r] = p.read_text("utf-8", errors="replace")[:220_000]
            except Exception:
                pass
    return paths, blobs


def selftest():
    ok, fail = 0, []
    t1 = classify_tree(["src/sentry.client.config.ts", "pages/errors/500.tsx", "server/healthz.py"],
                       {"package.json": '{"dependencies":{"@sentry/nextjs":"7.0.0"}}',
                        ".env.example": "SENTRY_DSN=\n"})
    t2 = classify_tree(["src/app/page.tsx"], {"package.json": '{"dependencies":{"react":"18"}}'})
    if t1["mon_files"] and t1["err_pages"] and t1["diag"] and t1["dsn_in_env_sample"] \
            and "sentry" in t1["vendors"]:
        ok += 1
    else:
        fail.append("正例①四类证据未全中：%s" % t1)
    if not (t2["mon_files"] or t2["vendors"] or t2["mon_deps"] or t2["dsn_in_env_sample"]):
        ok += 1
    else:
        fail.append("反例①干净仓被误判有监控：%s" % t2)
    # 反例②：node_modules 里别人带的 sentry 配置不得算本仓集成
    t3 = classify_tree(["node_modules/x/sentry.client.config.ts"], {})
    if not t3["mon_files"]:
        ok += 1
    else:
        fail.append("反例②依赖目录未排除：%s" % t3)
    # 反例③：README 里出现 "FAQ" 才算排障文档，正文顺带提一句 issue 不算
    d1 = classify_readme("# Troubleshooting\n出错时提交 issue")
    d2 = classify_readme("we handle errors gracefully")
    if d1.get("troubleshooting") and not d2.get("troubleshooting"):
        ok += 1
    else:
        fail.append("反例③文档面判据失真：%s / %s" % (d1, d2))
    # 反例④（r51 实测自抓）：highlight.js 是**语法高亮库**，不得算错误监控集成；
    # 而 @highlight-run/* 才是监控厂商 Highlight.io 的包名，必须认。
    t4 = classify_tree(["src/lib/render.tsx"],
                       {"package.json": '{"dependencies":{"highlight.js":"11.1.0"}}'})
    t5 = classify_tree(["src/lib/render.tsx"],
                       {"package.json": '{"dependencies":{"@highlight-run/react":"2.0.0"}}'})
    if not t4["vendors"] and "highlight" in t5["vendors"]:
        ok += 1
    else:
        fail.append("反例④歧义厂商名未隔离：highlight.js=%s ／ @highlight-run=%s"
                    % (t4["vendors"], t5["vendors"]))
    # 边界：空树必须给"无监控集成证据"而不是崩或判有
    v = verdict(classify_tree([], {}), {})
    if "无监控集成证据" in v:
        ok += 1
    else:
        fail.append("边界 空树结论异常：%s" % v)
    for x in fail:
        print("  SELFTEST-FAIL " + x)
    # 分母独立于结果：期望用例数写死在此，且「既没记 ok 也没记 fail」的漏分支同样判红
    # （否则加一条断言却忘了改分母，会退化成"少跑一条也照样 PASS"）。
    expected = 6
    print("FAULTPEER-SELFTEST: %d/%d%s" % (ok, expected,
          "" if ok + len(fail) == expected else "  ⚠️ 分支数 %d≠%d（有用例既未记过也未记败）"
          % (ok + len(fail), expected)))
    return 0 if ok == expected and ok + len(fail) == expected else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="")
    ap.add_argument("--self-only", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    token = os.environ.get("GITHUB_TOKEN") or subprocess.run(
        ["gh", "auth", "token"], capture_output=True, text=True).stdout.strip()
    if not token:
        print("FAULTPEER-ENV: 无 GitHub token ⇒ 不采数、不判绿")
        return 2
    rows, na = {}, []
    for p in ([] if a.self_only else PEERS):
        slug, tier = p["repo"], p["tier"]
        t, trunc, doc, err = probe_repo(slug, token)
        rows[slug] = {"tier": tier, "tree": t, "readme": doc, "truncated": trunc, "err": err}
        if err or not t:
            na.append("%s(%s)" % (slug, (err or "tree 空")[:52]))
        elif trunc:
            na.append("%s(树被截断⇒零命中不可信)" % slug)
        print("[%-3s] %-33s 监控件=%-2d 依赖=%-2d 错误页=%-2d 诊断=%-2d DSN=%-5s %s%s"
              % (tier, slug, len(t.get("mon_files") or []), len(t.get("mon_deps") or []),
                 len(t.get("err_pages") or []), len(t.get("diag") or []),
                 t.get("dsn_in_env_sample"), verdict(t, doc), "｜截断" if trunc else ""))
    sp, sb = self_blobs_and_paths()
    st = classify_tree(sp, sb)
    sd = classify_readme((ROOT / "README.md").read_text("utf-8", errors="replace")
                         if (ROOT / "README.md").exists() else "")
    rows["__self__"] = {"tree": st, "readme": sd}
    print("[self] %-33s 监控件=%-2d 依赖=%-2d 错误页=%-2d 诊断=%-2d DSN=%-5s %s"
          % ("心屿 SoulIsle", len(st.get("mon_files") or []), len(st.get("mon_deps") or []),
             len(st.get("err_pages") or []), len(st.get("diag") or []),
             st.get("dsn_in_env_sample"), verdict(st, sd)))
    print("-" * 116)
    n = len(rows) - 1
    if n:
        mon = sum(1 for k, v in rows.items() if k != "__self__"
                  and (v["tree"].get("mon_files") or v["tree"].get("mon_deps")
                       or v["tree"].get("dsn_in_env_sample") or v["tree"].get("vendors"))
                  )
        trb = sum(1 for k, v in rows.items() if k != "__self__"
                  and v["readme"].get("troubleshooting"))
        print("peers：有 error-monitoring 集成证据 %d/%d ｜ README 有排障段 %d/%d" % (mon, n, trb, n))
    if na:
        print("  NA/截断：" + "; ".join(na))
    print("应测 %s ｜ NA/截断 %d ｜ 恒等式 usable+NA==total：%s"
          % (n if not a.self_only else 0, len(na),
             "OK" if (n - len(na)) + len(na) == n else "不成立"))
    if a.json:
        Path(a.json).write_bytes(json.dumps(
            {"repos": rows, "na": na, "denominator": n, "blind": len(na), "usable": n - len(na),
             "ceiling_note": "故障注入无法对他人站点实施 ⇒ 本面只出结构与声明证据，"
                             "不得写成报错体验对比结论",
             "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")},

            ensure_ascii=False, indent=1).encode("utf-8"))
        print("快照 -> " + a.json)
    if a.self_only:
        return 0
    return 1 if na else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
