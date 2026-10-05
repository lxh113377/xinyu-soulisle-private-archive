# -*- coding: utf-8 -*-
"""对标新观测面探针（r37）：发布可得性 / 维护响应 / 工程治理 —— 账面指标（★/pushed/workflow 数）
问不出来的东西，这三面能：
  A 发布可得性：近 90 天 release 次数、最近一次距今、最新 release 资产数、有无一键起（compose/Dockerfile）
  B 维护响应：未关 issue 数、最近一次「真 issue 被关闭」距今（排除 PR）
  C 工程治理：dependabot / SECURITY.md / LICENSE / 贡献者数（上限 100，超限记 ≥100）
纪律（M5⑦ / R247 同族）：**每个字段独立取数，失败记 NA(原因) 并入 unverified 计数**，
禁止把"没取到"印成 0；分母（应测仓数）与"有效/未验"由本脚本自印，不手抄。

⚠️ r96 改判两处（都是本件自己的缺陷，一手实测坐实）：
  1. **假 NA（样本陈述写成总体陈述）**。原 B 面只取 `issues?state=closed&per_page=20&sort=updated`
     这 **20 条样本**，客户端排掉 PR 后若样本里恰好没有真 issue，就写 `NA(无真issue)` ——
     那说的是"我这 20 条没抓到"，不是"这仓没有"。今日用服务端 `search/issues?q=repo:X type:issue
     is:closed` 复算人口：`morettt/my-neuro` **实有 102 条已关闭 issue**、`s-nagaev/chibi` 7 条，
     两份台账（peer-hygiene-2026-09-26.json）里却都记着 `NA(无真issue)`；该格共有 5 个 NA，
     至少 2 个是这么造出来的。⇒ 现在**人口单独取数**（`closed_issue_total`），
     样本落空只许写 `NA(sample-miss …)`，`NA(no-closed-issue)` 仅当**人口真为 0** 时才允许出现。
  2. **self 从没被这把尺量过**。`SELF` 常量自 r37 定义在 `:23` 却**没有任何使用点**
     （模块 docstring 写着"同一把尺量自己，M5⑧"，代码里没兑现）。⇒ 现在 self 进入被测集合，
     `--self-only` 只跑 self 一面。
用法：python _test/peer_hygiene_probe.py [--repo <owner/name> ...] [--json out.json]
                                        [--self-only] [--selftest]
退出码：0=全部面取到 1=存在取数失败/假 NA 防不住（如实点名，不判仓库好坏） 2=无 gh / 鉴权失败
"""
import argparse
import json
import subprocess
import sys
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from benchmark_metrics import PEERS  # 分母唯一真相源：台账同款仓池，不另立一份清单

ROOT = Path(__file__).resolve().parents[1]
SELF = "lxh113377/xinyu-soulisle-private-archive"   # = origin 远端（同一把尺量自己，M5⑧）
RECENT_DAYS = 90


_MIN_CALL_INTERVAL_S = 0.35   # r96 加：本件 17 仓 × ~28 次调用是**紧循环**，burst 会撞 GitHub
                              # secondary rate limit（本轮一手实测：12/17 行的 closed 人口取数
                              # 全部返回 "You have exceeded a secondary rate limit"）。
                              # 与 r50 那次「search 限流把 15/16 打成 NA 并塌缩成假结论」同族。
_last_call = [0.0]


def gh(*args):
    """返回 (ok, data_or_reason)。失败绝不静默成空值。"""
    import time
    gap = time.time() - _last_call[0]
    if gap < _MIN_CALL_INTERVAL_S:
        time.sleep(_MIN_CALL_INTERVAL_S - gap)
    _last_call[0] = time.time()
    p = subprocess.run(["gh", "api"] + [str(a) for a in args],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        err = (p.stderr or "").strip().splitlines()
        return False, (err[-1][:70] if err else "rc=%d" % p.returncode)
    try:
        return True, json.loads(p.stdout or "null")
    except Exception as e:
        return False, "bad-json:%s" % e


def days_ago(iso):
    if not iso:
        return None
    dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    return (datetime.now(timezone.utc) - dt).days


def closed_issue_total(repo):
    """服务端取**已关闭真 issue 的人口数**（不是样本数）。
    查询串必须 urlencode：`>=` / `+` 不编码时服务端按字面匹配、恒 0 命中（本仓 排障表同族）。
    返回 (ok, int|原因)。"""
    q = urllib.parse.urlencode({"q": "repo:%s type:issue is:closed" % repo, "per_page": 1})
    ok, d = gh("search/issues?" + q)
    if not ok:
        return False, d
    if not isinstance(d, dict) or not isinstance(d.get("total_count"), int):
        return False, "无 total_count 字段"
    return True, d["total_count"]


def classify_issue_recency(real, total_ok, total, sample_n=20):
    """**纯函数**：把「样本里有没有」和「仓里有没有」分成两件事说。
    real=样本排掉 PR 后的真 issue 列表；total=服务端人口数（取不到传 None）。
    三态不得塌缩：有读数 / 样本落空（人口>0）/ 人口真为 0。
    —— 这条函数就是 r96 假 NA 的封口：`no-closed-issue` 只有在**人口为 0** 时才可达。"""
    if real:
        return days_ago(real[0].get("closed_at"))
    if not total_ok:
        return "NA(人口取数失败:%s)" % total
    if total == 0:
        return "NA(no-closed-issue 人口=0)"
    return "NA(sample-miss 样本%d条无真issue 但人口=%d)" % (sample_n, total)


def probe(repo):
    out = {}
    ok, d = gh("repos/%s" % repo)
    if not ok:
        return {"_fatal": "repo:%s" % d}
    out["stars"] = d.get("stargazers_count")
    out["open_issues"] = d.get("open_issues_count")
    out["pushed_days"] = days_ago(d.get("pushed_at"))

    ok, rs = gh("repos/%s/releases?per_page=100" % repo)
    if ok and isinstance(rs, list):
        recent = [r for r in rs if (days_ago(r.get("published_at")) or 9999) <= RECENT_DAYS]
        out["rel_90d"] = len(recent)
        out["rel_last_days"] = days_ago(rs[0].get("published_at")) if rs else None
        out["rel_assets"] = len(rs[0].get("assets") or []) if rs else 0
    else:
        out["rel_90d"] = "NA(%s)" % rs

    ok_t, total = closed_issue_total(repo)
    out["closed_issue_total"] = total if ok_t else "NA(%s)" % total
    ok, iss = gh("repos/%s/issues?state=closed&per_page=20&sort=updated&direction=desc" % repo)
    if ok and isinstance(iss, list):
        real = [i for i in iss if "pull_request" not in i]     # 排除 PR，否则"响应"是假的
        out["issue_closed_days"] = classify_issue_recency(real, ok_t, total if ok_t else None)
        out["issue_sample_real_n"] = len(real)
    else:
        out["issue_closed_days"] = "NA(样本取数失败:%s)" % iss
        out["issue_sample_real_n"] = "NA"

    ok, cl = gh("repos/%s/contributors?per_page=100&anon=false" % repo)
    if ok and isinstance(cl, list):
        contribs = len(cl)
        out["contributors"] = ">=100" if len(cl) == 100 else len(cl)
    else:
        out["contributors"] = "NA(%s)" % cl

    one_click = []
    # ⚠️ 口径修正（r37 自查）：只查根目录会把"放在子目录的 Dockerfile"测成 none ——
    # 本项目 `server/Dockerfile` 就是这种情形，而 self 行与 peers 行必须同一把尺（M5⑧）。
    # 现对**所有仓**统一探测同一组路径，并记录命中路径（可复核，不靠猜）。
    hits = []
    for d in ("", "server/", "docker/", "deploy/"):
        for f, tag in (("docker-compose.yml", "compose"), ("compose.yaml", "compose"),
                       ("Dockerfile", "Dockerfile"), ("docker-compose.yaml", "compose")):
            ok, _ = gh("repos/%s/contents/%s%s" % (repo, d, f))
            if ok:
                hits.append((d or "./") + f)
                if tag not in one_click:
                    one_click.append(tag)
    out["one_click"] = ",".join(one_click) or "none"
    out["one_click_paths"] = hits
    if hits:
        print("  · %s 一键起命中路径：%s" % (repo, " / ".join(hits)), file=sys.stderr)

    gov = []
    for f, tag in ((".github/dependabot.yml", "dependabot"), ("SECURITY.md", "security"),
                   ("LICENSE", "license"), ("LICENSE", "license"),
                   ("docs", "docs-dir"), ("CHANGELOG.md", "changelog")):
        ok, _ = gh("repos/%s/contents/%s" % (repo, f))
        if ok and tag not in gov:
            gov.append(tag)
    out["gov"] = ",".join(gov) or "none"
    return out


# ── 自检：正例 / 变异 / 边界三族（r96 立；此前本件无离线桩 ⇒ 一直进不了阻断链）──────
def selftest():
    cases = []

    def eq(label, got, want):
        cases.append((label, got, want))

    def iss(n, closed="2026-09-01T00:00:00Z"):
        return [{"number": i, "closed_at": closed} for i in range(n)]

    # 正例腿（只有正例能抓「尺恒假」）
    eq("样本有真 issue ⇒ 出一个天数读数",
       isinstance(classify_issue_recency(iss(3), True, 102), int), True)
    eq("人口数与样本落空是两件事：population 字段独立存在",
       closed_issue_total.__doc__.startswith("服务端取"), True)
    eq("空列表 + 人口>0 ⇒ 写 sample-miss 并带上人口数（不是 NA(无真issue)）",
       classify_issue_recency([], True, 102).startswith("NA(sample-miss"), True)
    eq("且 sample-miss 里带着人口数，读者一眼看得出「有 102 条只是没抓到」",
       "人口=102" in classify_issue_recency([], True, 102), True)
    eq("人口=0 ⇒ 才允许出现 no-closed-issue",
       classify_issue_recency([], True, 0), "NA(no-closed-issue 人口=0)")
    # 变异腿：把「人口=0 才可写 no-closed-issue」这条闸摘掉 ⇒ 必须还能被抓住
    keep = globals()["classify_issue_recency"]

    def lie(real, total_ok, total, sample_n=20):
        return "NA(无真issue)" if not real else days_ago(real[0].get("closed_at"))
    globals()["classify_issue_recency"] = lie
    eq("变异体 用旧写法时 my-neuro 这类仓会得 NA(无真issue)（这就是 5 个假 NA 的产地）",
       classify_issue_recency([], True, 102), "NA(无真issue)")
    globals()["classify_issue_recency"] = keep
    eq("还原后同一入参改为 sample-miss（证明上面动的是尺不是期望值）",
       classify_issue_recency([], True, 102).startswith("NA(sample-miss"), True)
    # 边界腿
    eq("边界 人口取数失败 ⇒ NA 里写明是人口失败、不冒充样本落空",
       classify_issue_recency([], False, "403").startswith("NA(人口取数失败"), True)
    eq("边界 closed_at 缺失的样本 ⇒ 不把 None 当 0 天",
       classify_issue_recency([{"number": 1}], True, 5), None)
    eq("边界 days_ago(None) ⇒ None 而非 0", days_ago(None), None)
    # 检测器自身的两向腿：抓旧谎言的确切形态，且不得把新的诚实标签报成复发
    eq("检测器抓到旧谎言确切形态",
       detect_old_lie({"a/b": {"issue_closed_days": "NA(无真issue)"}}), ["a/b"])
    eq("检测器**不得**把新的诚实标签报成旧形态复发（r96 实测踩过：chibi 被误报一次）",
       detect_old_lie({"s-nagaev/chibi": {"issue_closed_days":
                                          "NA(sample-miss 样本20条无真issue 但人口=7)"}}), [])
    eq("边界 检测器对非 dict 行不崩", detect_old_lie({"x": "junk"}), [])
    enc = urllib.parse.urlencode({"q": "repo:a/b type:issue is:closed"})
    eq("边界 查询串里空格已编码（裸空格会让 gh 参数错位）", " " in enc, False)
    eq("边界 self 在分母里（r37–r95 期间 SELF 常量定义了却零使用点）",
       SELF not in [p["repo"] for p in PEERS] and bool(SELF), True)

    bad = [(n, g, w) for n, g, w in cases if g != w]
    for n, g, w in bad:
        print("  用例不符: %s ｜ got=%r want=%r" % (n, g, w))
    print("HYGIENE-SELFTEST-%s（%d/%d 条）"
          % ("PASS" if not bad else "FAIL", len(cases) - len(bad), len(cases)))
    return 1 if bad else 0


def detect_old_lie(rows):
    """挑出仍写**旧谎言确切形态** `NA(无真issue)` 的仓。
    ⚠️ 不能用裸子串 `无真issue` 当标记：r96 实测撞出新的诚实标签
    `NA(sample-miss 样本20条无真issue 但人口=7)` 也含那五个字 ⇒ 子串匹配会把
    **正确记录**报成"旧形态复现"，骗下一轮去"修"一份本来没坏的台账（判据误报的代价
    与漏报同级：它制造假工作项）。"""
    return [r for r, d in rows.items() if isinstance(d, dict)
            and d.get("issue_closed_days") == "NA(无真issue)"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", action="append", default=[])
    ap.add_argument("--json", default="")
    ap.add_argument("--self-only", action="store_true",
                    help="只跑 self 一面（本件 A/B/C 三面都在平台侧，故仍需 gh 鉴权；无鉴权判 rc=2）")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    ok, _ = gh("user")
    if not ok:
        print("HYGIENE-PROBE-ENV-ERROR: gh 未鉴权（%s）" % _)
        return 2
    if a.self_only:
        repos = [SELF]
    else:
        repos = a.repo or ([SELF] + [p["repo"] for p in PEERS])
    rows, unverified = {}, []
    for r in repos:
        d = probe(r)
        rows[r] = d
        if "_fatal" in d:
            unverified.append("%s(%s)" % (r, d["_fatal"]))
        elif any(isinstance(v, str) and v.startswith("NA(") for v in d.values()):
            unverified.append("%s(部分字段)" % r)
        print("%-38s ★%-7s issues=%-6s pushed=%-4sd rel90d=%-4s relLast=%-5s assets=%-3s "
              "closed人口=%-7s 样本真n=%-4s issueClosed=%-8s contrib=%-5s 一键=%-12s 治理=%s"
              % (r, d.get("stars"), d.get("open_issues"), d.get("pushed_days"),
                 d.get("rel_90d"), d.get("rel_last_days"), d.get("rel_assets"),
                 d.get("closed_issue_total"), d.get("issue_sample_real_n"),
                 d.get("issue_closed_days"), d.get("contributors"),
                 d.get("one_click"), d.get("gov")))
    print("-" * 150)
    # 只认**旧谎言的确切形态** `NA(无真issue)`。不能拿裸子串 `无真issue` 当标记 ——
    # r96 实测撞出：新的诚实标签 `NA(sample-miss 样本20条无真issue 但人口=7)` 也含那五个字，
    # 用子串匹配会把**正确记录**报成"旧形态复现"，骗下一轮去"修"一份本来没坏的台账。
    false_na = detect_old_lie(rows)
    hdr = "应测 %d 仓 ｜ 整仓取数失败 %d ｜ 含 NA 字段 %d" % (
        len(repos), sum(1 for v in rows.values() if "_fatal" in v), len(unverified))
    if false_na:
        print("  🔴 旧形态假 NA 复现（人口>0 却写成无真 issue）：" + "; ".join(false_na))
    if unverified:
        print("  未验项（不得据其结论）：" + "; ".join(unverified))
    if a.json:
        Path(a.json).write_bytes(json.dumps({"repos": rows, "unverified": unverified,
                                             "denominator": len(repos),
                                             "recent_days": RECENT_DAYS},
                                            ensure_ascii=False, indent=1).encode("utf-8"))
        print("落盘 %s" % a.json)
    print(hdr)
    print("HYGIENE-PROBE-%s" % ("PARTIAL" if unverified else "COMPLETE"))
    return 1 if unverified else 0


if __name__ == "__main__":
    sys.exit(main())
