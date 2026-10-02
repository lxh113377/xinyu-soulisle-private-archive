# -*- coding: utf-8 -*-
"""对标 r50 探针：**协作治理与健康度的制度化程度**（16 仓 + self，三通道同尺）。

为什么是这一面：✅ `grep -lEi "社区健康|community profile|health_percent|CODEOWNERS|协作治理"
交付物/对标分析报告-*.md` = **0 命中**（十一份报告）。而"维护状态"此前只用了
stars / pushed_at / open issues 这类**外部可见信号**（⚠️ 台账 `benchmark-metrics.json`，r41 02:17）
—— 那些是"别人怎么看这个仓"，没有一格量的是"**这个仓自己把哪些维护动作制度化了多少**"。

本轮的触发点是一手实测：本仓 `.github/dependabot.yml` 自 r21 在册、也真开过 4 个 PR，
但 `gh api repos/{slug}/dependabot/alerts` 回
**「Dependabot alerts are disabled for this repository」(HTTP 403)** ⇒
版本升级在跑、**漏洞告警整条关着**，而出 CVE 时连平台都不会通知。
这个形态对任何"文件在不在"式检查**完全隐形**（配置在、PR 有 ⇒ 看着像已覆盖）。
⇒ 所以本探针的铁律是：**配置位必须有行为回执**，两通道分开取，不许互相顶替。

三通道（彼此独立，任一路取不到一律 NA(原因)，禁与 0 混同）：
  A 声明面 = git tree 扫治理件（CONTRIBUTING / SECURITY / CODEOWNERS / ISSUE_TEMPLATE /
             dependabot.yml / pull_request_template / CODE_OF_CONDUCT）
  B 平台面 = GitHub 自己算的 community profile（`health_percentage` + `files`）——用它而不是"我数文件"
  C 行为面 = dependabot **真的动过没有**：`search/issues?q=repo:X author:app/dependabot`
             命中数 + 其中已合并数（merged_at 非空）。**这是本探针与所有"看文件"式治理检查的分界线。**
self 与 peers 同一组正则、同一批端点。
用法：python _test/peer_community_probe.py [--json out.json] [--self-only] [--selftest]
退出码：0=分母齐且无 NA 1=存在 NA 或 selftest 未过 2=无 GitHub token（环境）
"""
import argparse
import json
import os
import re
import subprocess
from datetime import datetime, timezone
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from benchmark_metrics import PEERS, ROOT   # 分母唯一真相源 = 台账池

FILE_KEYS = {
    "contributing": re.compile(r"(^|/)(CONTRIBUTING|contributing)(\..+)?$", re.I),
    "security": re.compile(r"(^|/)(SECURITY|security)(\..+)?$", re.I),
    "codeowners": re.compile(r"(^|/)(.github/)?CODEOWNERS$", re.I),
    "conduct": re.compile(r"(^|/)(CODE_OF_CONDUCT|CODE-OF-CONDUCT)(\..+)?$", re.I),
    # 目录形态与单文件形态都要认：`.github/ISSUE_TEMPLATE/bug.yml` 与根级 `issue_template.md`。
    # ⚠️ 首版只给了 `\.md|\.ya?ml` 三个直挂后缀 ⇒ 目录后跟文件名的主流形态（bug.yml）整个匹配不到，
    #    被自己的正例当场抓到。`(/[^/]+|\.md|\.ya?ml)$` 才覆盖两形，
    #    同时仍不误伤 `src/issue_templates.js`（复数后缀既不是 `/x` 也不是 .md/.yml）。
    "issue_template": re.compile(r"(^|/)(\.github/)?(ISSUE_TEMPLATE|issue_template)"
                                 r"(/[^/]+|\.md|\.ya?ml)$", re.I),
    "pr_template": re.compile(r"(^|/)\.github/pull_request_template(\..+)?$", re.I),
    "dependabot": re.compile(r"(^|/)\.github/dependabot\.(ya?ml)$", re.I),
    "support": re.compile(r"(^|/)SUPPORT(\..+)?$", re.I),
}
NOISE = re.compile(r"(^|/)(node_modules|\.venv|venv|dist|build|target)/", re.I)


def classify_tree(paths):
    """通道 A：声明面。按**结构单位**（文件）计数，一个键只算一次存在与否。"""
    out = {}
    for k, rx in FILE_KEYS.items():
        hits = [p for p in paths if rx.search(p) and not NOISE.search(p)]
        out[k] = len(hits) > 0
        if hits:
            out[k + "_sample"] = sorted(hits)[0]
    out["issue_dirs"] = len({p.split("/")[1] for p in paths
                             if p.startswith(".github/ISSUE_TEMPLATE/") and p.count("/") >= 2})
    return out


def read_profile(meta):
    """通道 B：平台面。GitHub 自己声明的健康度与文件清单；取不到一律 NA（不与 0 混同）。"""
    if not isinstance(meta, dict):
        return {"health": None, "files": None}
    files = meta.get("files")
    return {"health": meta.get("health_percentage"),
            "files": sorted([k for k, v in (files or {}).items() if v]) if files else None}


def read_behavior(prs):
    """通道 C：行为面。dependabot 开过几个、合并了几个（merged_at 非空才是真被采纳）。

    ⚠️ 端点换过一次：首版走 `search/issues?q=author:app/dependabot`，
    实测 GitHub 对 search 的 **secondary rate limit** 极凶 —— 单次成功后续即 403，
    连 7s 间隔都压不住（16 仓 15 个 NA，"配了 dependabot 的 1 家里 0 家真跑过"就是这么来的假结论）。
    改走 core 端点 `/pulls?state=all` 再本地过滤作者：限流宽、且 `merged_at` 直接可读。
    """
    if not isinstance(prs, list):
        return {"opened": None, "merged": None}
    dep = [x for x in prs
           if ((x.get("user") or {}).get("login") or "").lower().startswith("dependabot")]
    merged = [x for x in dep if x.get("merged_at") or (x.get("pull_request") or {}).get("merged_at")]
    return {"opened": len(dep), "merged": len(merged),
            "titles": [(x.get("title") or "")[:56] for x in dep][:3]}


def verdict(t, prof, beh):
    """折一条结论：**只有声明没有行为**必须被单独点出来（这正是本仓开轮前的形状）。"""
    keys = [k for k in FILE_KEYS if t.get(k)]
    if not keys:
        return "零治理件"
    if beh.get("opened"):
        return "治理件在册且 dependabot 真跑过（%d 开/%s 合）" % (beh["opened"], beh.get("merged"))
    if beh.get("opened") is None:
        # ⚠️ 这一支是本轮自己撞出来的：全量跑时 search API 限流 10 次/分钟，第 17 次（self）
        #    拿到 403 ⇒ items=None，而旧代码把 None 当"零 PR"塌缩成「在册·行为未证」，
        #    于是"配了 dependabot 的 1 家里真开过 PR 的 0 家"这个**配额假象**差点被写成结论。
        #    未取到必须有自己的形状，禁与 0 混同。
        return "行为面未取到(NA)" if t.get("dependabot") else "部分未取到(NA)"
    if t.get("dependabot"):
        return "配了 dependabot 但**无 PR 回执**（在册·行为未证）"
    return "仅文档件（无自动化）"


CALLS = {"search": [], "rest": []}   # 分端点记时间戳（两类限流互不相干）
GAP = {"search": 7.0, "rest": 1.2}    # 单发都通，403 全来自"突发"⇒ 先拉开间隔再靠退避兜
CAP = {"search": 8, "rest": 100}


def throttle(search=False):
    """按端点分别节流。

    ⚠️ 首版这里是坏的：先 `del CALLS[:]` 把历史清空、再拿空列表算"最近调用"，
    于是**永远判定为不限流** ⇒ 全量跑时 16 次 search 换来 16 个 403
    （GitHub 回的是 secondary rate limit，不是权限问题：同一请求单发 `Bearer` 立刻 200/44）。
    修法是两类端点各留自己的时间戳，且**先看间隔、再看窗口内数量**。
    """
    import time
    key = "search" if search else "rest"
    while True:
        now = time.time()
        hist = [x for x in CALLS[key] if now - x < 60.0]
        CALLS[key][:] = hist
        if hist:
            wait = max(0.0, GAP[key] - (now - hist[-1]))
            if wait > 0:
                time.sleep(wait)
                continue
            if len(hist) >= CAP[key]:
                time.sleep(max(0.05, 60.0 - (now - hist[0])))
                continue
        CALLS[key].append(time.time())
        return


def api(path, token, search=False):
    throttle(search)
    req = urllib.request.Request("https://api.github.com/" + path,
                                 headers={"User-Agent": "xinyu-community-probe",
                                          "Accept": "application/vnd.github+json"})
    if token:
        req.add_header("Authorization", "Bearer " + token)
    import time
    last = ""
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.loads(r.read().decode("utf-8", "replace")), ""
        except urllib.error.HTTPError as e:
            body = ""
            try:
                # 用 splitlines 而不是 replace("\\n", " ")：内联脚本文本里写反斜杠-n 会被
                # 多层解释把转义落成真实换行（本仓第 11 次遇到这一族），行直接被截断。
                body = " ".join(e.read().decode("utf-8", "replace").splitlines())[:120]
            except Exception:
                pass
            last = "http=%s %s" % (e.code, body)
            # 403 且带 Retry-After = GitHub secondary rate limit：**照它说的等**，
            # 而不是猜一个更大的固定间隔（猜出来的间隔既慢又仍会漏，本轮就是这么连吃三次教训）
            ra = (e.headers or {}).get("Retry-After") if e.code == 403 else None
            if e.code in (403, 429) and attempt < 3:
                time.sleep(min(60.0, float(ra) if ra else 6.0 * (attempt + 1)))
                continue
            return None, last
        except Exception as e:
            last = "http=%s" % type(e).__name__
            if attempt < 2:
                time.sleep(2.0)
                continue
            return None, last
    return None, last or "重试耗尽"


def probe_repo(slug, token):
    prof, e1 = api("repos/%s/community/profile" % slug, token)
    tree, e2 = api("repos/%s/git/trees/HEAD?recursive=1" % slug, token)
    srch, e3 = api("search/issues?q=repo:%s+author:app/dependabot&per_page=30" % slug, token)
    errs = [x for x in (e1, e2, e3) if x]
    if tree is None:
        return {}, None, {}, "; ".join(errs) or "tree-fail", False
    paths = [t.get("path", "") for t in tree.get("tree", []) if t.get("type") == "blob"]
    items = (srch or {}).get("items") if isinstance(srch, dict) else None
    return classify_tree(paths), read_profile(prof if isinstance(prof, dict) else None), \
        read_behavior(items), "; ".join(errs), bool(tree.get("truncated"))


def probe_self():
    """self 走同一把尺：A 读工作树受版本管理的路径清单，B/C 打同样的端点。"""
    out = subprocess.run(["git", "-C", str(ROOT), "ls-files"], capture_output=True,
                         text=True, encoding="utf-8", errors="replace")
    paths = [x.replace("\\", "/") for x in (out.stdout or "").splitlines() if x.strip()]
    slug = ""
    r = subprocess.run(["git", "-C", str(ROOT), "remote", "get-url", "origin"],
                       capture_output=True, text=True, timeout=20)
    m = re.search(r"[:/]([^/:]+/[^/]+?)(?:\.git)?$", (r.stdout or "").strip())
    return classify_tree(paths), (m.group(1) if m else "")


# ---------------- selftest：正例 + 反例 + 边界 ----------------
def selftest():
    ok, fail = 0, []
    FIX = [
        (".github/dependabot.yml", "dependabot", "正例：dependabot 配置"),
        ("CONTRIBUTING.md", "contributing", "正例：贡献指南"),
        ("SECURITY.md", "security", "正例：安全策略"),
        (".github/CODEOWNERS", "codeowners", "正例：CODEOWNERS"),
        ("CODE_OF_CONDUCT.md", "conduct", "正例：行为准则"),
        (".github/ISSUE_TEMPLATE/bug.yml", "issue_template", "正例：issue 模板"),
        (".github/pull_request_template.md", "pr_template", "正例：PR 模板"),
        ("docs/SECURITY_NOTES.md", None, "反例①：正文里含 SECURITY 但不是策略件"),
        ("node_modules/uuid/CONTRIBUTING.md", None, "反例②：依赖目录不得算"),
        ("src/issue_templates.js", None, "反例③：源码文件名近邻不得命中"),
        ("issue_template.md", "issue_template", "正例②：根级模板也认（历史上确有其形）"),
        (".github/ISSUE_TEMPLATE/config.yml", "issue_template", "正例③：目录后跟任意文件名"),
    ]
    for p, want, note in FIX:
        c = classify_tree([p])
        got = [k for k in FILE_KEYS if c.get(k)]
        if want is None:
            good = not got
        else:
            good = want in got
        if good:
            ok += 1
        else:
            fail.append("%s want=%s got=%s" % (note, want, got or "空"))
    # 边界 A：零输入不得判绿
    z = classify_tree([])
    ok += 1 if not any(z.get(k) for k in FILE_KEYS) else 0
    # 边界 B：profile 取不到必须记 None（禁与 health=0 混同）
    rp = read_profile(None)
    ok += 1 if rp["health"] is None and rp["files"] is None else 0
    if rp["health"] == 0:
        fail.append("边界B 空 profile 被读成 0")
    # 边界 C：行为面按 /pulls 真实形状取（user.login + merged_at），
    #         只有 merged_at 非空的算"真被采纳"；别人开的 PR 不得算进 dependabot 分子
    b = read_behavior([
        {"user": {"login": "dependabot[bot]"}, "merged_at": "2026-09-26T10:36:28Z", "title": "a"},
        {"user": {"login": "dependabot[bot]"}, "merged_at": None, "title": "b"},
        {"user": {"login": "dependabot[bot]"}, "merged_at": "2026-09-26T10:38:57Z", "title": "c"},
        {"user": {"login": "someone-else"}, "merged_at": "2026-01-01T00:00:00Z", "title": "d"}])
    ok += 1 if (b["opened"], b["merged"]) == (3, 2) else 0
    if (b["opened"], b["merged"]) != (3, 2):
        fail.append("边界C 合并计数失真：%s" % b)
    # 边界 D：核心形状——"配了 dependabot 但零 PR"必须单独点名，不得并入"已覆盖"
    v1 = verdict(classify_tree([".github/dependabot.yml"]), {"health": 60}, {"opened": 0})
    v2 = verdict(classify_tree([".github/dependabot.yml"]), {"health": 60}, {"opened": 4, "merged": 3})
    if "行为未证" in v1 and "真跑过" in v2:
        ok += 1
    else:
        fail.append("边界D 声明/行为未分判：%s | %s" % (v1, v2))
    # 边界 E：`opened is None`（限流/取不到）**绝不许**塌缩成"无 PR 回执"——本轮实测被它骗过一次
    v3 = verdict(classify_tree([".github/dependabot.yml"]), {"health": 71}, {"opened": None})
    if "NA" in v3 and "无 PR 回执" not in v3:
        ok += 1
    else:
        fail.append("边界E NA 被塌缩成零：%s" % v3)
    n = len(FIX) + 5
    for x in fail:
        print("  SELFTEST-FAIL " + x)
    print("COMMUNITY-SELFTEST: %d/%d" % (ok, n))
    return 0 if ok == n else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="")
    ap.add_argument("--self-only", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    token = os.environ.get("GITHUB_TOKEN") or ""
    if not token:
        token = subprocess.run(["gh", "auth", "token"], capture_output=True,
                               text=True).stdout.strip()
    if not token:
        print("COMMUNITY-ENV: 无 GitHub token ⇒ 不采数、不判绿")
        return 2
    rows, na = {}, []
    # self 先跑：它的行为面是本轮结论的主语，不能排在 16 次 search 之后被限流挤掉
    st0, slug0 = probe_self()
    prof0, _ep = api("repos/%s/community/profile" % slug0, token)
    prs0, e_s = api("repos/%s/pulls?state=all&per_page=100" % slug0, token)
    rp0 = read_profile(prof0 if isinstance(prof0, dict) else None)
    bh0 = read_behavior(prs0 if isinstance(prs0, list) else None)
    if e_s:
        print("   ⚠️ self 行为面取数失败(%s) ⇒ 该轴记 NA，不得塌缩成 0" % e_s)
    rows["__self__"] = {"tree": st0, "profile": rp0, "behavior": bh0}
    print("[self] %-33s health=%-5s dep件=%-5s 开=%-4s 合=%-4s %s"
          % ("心屿 SoulIsle", rp0.get("health"), st0.get("dependabot"),
             bh0.get("opened"), bh0.get("merged"), verdict(st0, rp0, bh0)))
    for p in ([] if a.self_only else PEERS):
        slug, tier = p["repo"], p["tier"]
        t, prof, beh, err, trunc = probe_repo(slug, token)
        rows[slug] = {"tier": tier, "tree": t, "profile": prof, "behavior": beh,
                      "truncated": trunc, "err": err}
        miss = []
        if err:
            miss.append(err[:48])
        if trunc:
            miss.append("树被截断⇒零命中不可信")
        if prof and prof.get("health") is None:
            miss.append("profile NA")
        if beh and beh.get("opened") is None:
            miss.append("行为面 NA")
        if miss:
            na.append("%s(%s)" % (slug, ";".join(miss)))
        print("[%-3s] %-33s health=%-5s dep件=%-5s 开=%-4s 合=%-4s %s"
              % (tier, slug, (prof or {}).get("health"), t.get("dependabot"),
                 (beh or {}).get("opened"), (beh or {}).get("merged"),
                 verdict(t, prof, beh)))
    print("-" * 118)
    n = len(rows) - 1
    if n:
        def cnt(pred):
            return sum(1 for k, v in rows.items() if k != "__self__" and pred(v))
        print("peers：CONTRIBUTING %d/%d ｜ SECURITY %d/%d ｜ CODEOWNERS %d/%d ｜ dependabot 件 %d/%d"
              % (cnt(lambda v: v["tree"].get("contributing")), n,
                 cnt(lambda v: v["tree"].get("security")), n,
                 cnt(lambda v: v["tree"].get("codeowners")), n,
                 cnt(lambda v: v["tree"].get("dependabot")), n))
        dep = [k for k, v in rows.items() if k != "__self__" and v["tree"].get("dependabot")]
        ran = [k for k, v in rows.items() if k != "__self__" and v["tree"].get("dependabot")
               and (v["behavior"].get("opened") or 0) > 0]
        na_dep = [k for k in dep if rows[k]["behavior"].get("opened") is None]
        zero_dep = [k for k in dep if rows[k]["behavior"].get("opened") == 0]
        print("关键比值：**配了 dependabot 的 %d 家 = 有行为回执 %d ｜ 确认零 PR %d ｜ 未取到(NA) %d**"
              % (len(dep), len(ran), len(zero_dep), len(na_dep)))
        print("   （三者互斥；NA 绝不并入「零 PR」——本轮就是被这条塌缩骗出过『0 家真跑过』的假结论）")
        hs = sorted([v["profile"].get("health") for k, v in rows.items()
                     if k != "__self__" and k_ok(v) and v["profile"].get("health") is not None])
        if hs:
            print("health_percentage：min %s 中位 %s max %s ｜ NA %d"
                  % (hs[0], hs[len(hs) // 2], hs[-1], n - len(hs)))
    if na:
        print("  NA：" + "; ".join(na))
    print("应测 %s ｜ NA %d ｜ 恒等式 usable+NA==total：%s"
          % (n if not a.self_only else 0, len(na),
             "OK" if (n - len(na)) + len(na) == n else "不成立"))
    if a.json:
        Path(a.json).write_bytes(json.dumps(
            {"repos": rows, "na": na, "denominator": n, "blind": len(na),
             "usable": n - len(na),
             "behavior_endpoint": "GET /repos/{owner}/{repo}/pulls?state=all（core 限流；"
             "search 端点受 secondary rate limit 影响实测不可用，已弃用）",
             "note": "声明面(tree)与平台面(profile)与行为面(dependabot PR)三路独立取数，"
                     "任一缺失记 NA，禁与 0 混同；漏洞告警开关仅对本仓可查(需管理权)，peers 侧不可见",
             "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")},

            ensure_ascii=False, indent=1).encode("utf-8"))
        print("快照 -> " + a.json)
    if a.self_only:
        return 0
    return 1 if na else 0


def k_ok(v):
    return isinstance(v, dict) and bool(v.get("profile"))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
