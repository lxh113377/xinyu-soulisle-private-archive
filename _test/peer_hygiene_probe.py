# -*- coding: utf-8 -*-
"""对标新观测面探针（r37）：发布可得性 / 维护响应 / 工程治理 —— 账面指标（★/pushed/workflow 数）
问不出来的东西，这三面能：
  A 发布可得性：近 90 天 release 次数、最近一次距今、最新 release 资产数、有无一键起（compose/Dockerfile）
  B 维护响应：未关 issue 数、最近一次「真 issue 被关闭」距今（排除 PR）
  C 工程治理：dependabot / SECURITY.md / LICENSE / 贡献者数（上限 100，超限记 ≥100）
纪律（M5⑦ / R247 同族）：**每个字段独立取数，失败记 NA(原因) 并入 unverified 计数**，
禁止把"没取到"印成 0；分母（应测仓数）与"有效/未验"由本脚本自印，不手抄。
用法：python _test/peer_hygiene_probe.py [--repo <owner/name> ...] [--json out.json]
退出码：0=全部面取到 1=存在取数失败（如实点名，不判仓库好坏） 2=无 gh / 鉴权失败
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from benchmark_metrics import PEERS  # 分母唯一真相源：台账同款仓池，不另立一份清单

ROOT = Path(__file__).resolve().parents[1]
SELF = "lxh113377/xinyu-soulisle-private-archive"   # = origin 远端（同一把尺量自己，M5⑧）
RECENT_DAYS = 90


def gh(*args):
    """返回 (ok, data_or_reason)。失败绝不静默成空值。"""
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

    ok, iss = gh("repos/%s/issues?state=closed&per_page=20&sort=updated&direction=desc" % repo)
    if ok and isinstance(iss, list):
        real = [i for i in iss if "pull_request" not in i]     # 排除 PR，否则"响应"是假的
        out["issue_closed_days"] = days_ago(real[0].get("closed_at")) if real else "NA(无真issue)"
    else:
        out["issue_closed_days"] = "NA(%s)" % iss

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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", action="append", default=[])
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    ok, _ = gh("user")
    if not ok:
        print("HYGIENE-PROBE-ENV-ERROR: gh 未鉴权（%s）" % _)
        return 2
    repos = a.repo or [p["repo"] for p in PEERS]
    rows, unverified = {}, []
    for r in repos:
        d = probe(r)
        rows[r] = d
        if "_fatal" in d:
            unverified.append("%s(%s)" % (r, d["_fatal"]))
        elif any(isinstance(v, str) and v.startswith("NA(") for v in d.values()):
            unverified.append("%s(部分字段)" % r)
        print("%-38s ★%-7s issues=%-6s pushed=%-4sd rel90d=%-4s relLast=%-5s assets=%-3s "
              "issueClosed=%-6s contrib=%-5s 一键=%-12s 治理=%s"
              % (r, d.get("stars"), d.get("open_issues"), d.get("pushed_days"),
                 d.get("rel_90d"), d.get("rel_last_days"), d.get("rel_assets"),
                 d.get("issue_closed_days"), d.get("contributors"),
                 d.get("one_click"), d.get("gov")))
    print("-" * 150)
    hdr = "应测 %d 仓 ｜ 整仓取数失败 %d ｜ 含 NA 字段 %d" % (
        len(repos), sum(1 for v in rows.values() if "_fatal" in v), len(unverified))
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
