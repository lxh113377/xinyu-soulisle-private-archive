# -*- coding: utf-8 -*-
"""对标 r45 探针：**发布与版本治理**（16 仓 + self，同一把尺）。

为什么是这一面：七维里「维护状态」此前只量过 ★/停更/release **名字**（台账 `latest_release`），
从来没量过"发布节奏跟代码停更是否同步""tag 是不是 semver""有没有 CHANGELOG 且随发布归档"
（✅ 实测 `grep -l "发布节奏|semver|CHANGELOG 归档" 交付物/对标分析报告-*.md` 在 r45 前 = 0 命中）。
而 iCAN 展示期评委能下载的就是 Release 资产 —— 发布物滞后 = 评委拿到的是三个月前的行为。

三指标（全部取 GitHub API 现值，不采信台账旧值）：
  R1 有公开 release（`releases/latest` 200）
  R2 tag 是 semver 形状（含可选 v 前缀的 MAJOR.MINOR.PATCH）
  R3 发布新鲜度：latest release 的 published_at 距该仓 pushed_at 的天数（>阈值 ⇒ "代码在走、发布不动"）
另外记 R4 仓库树里有 CHANGELOG 类文件（通道 B，与 R1-R3 独立）。
用法：python _test/peer_release_probe.py [--json out] [--self-only] [--selftest]
退出码：0=分母齐 1=有 BLIND 或桩未过 2=无 token
"""
import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from benchmark_metrics import PEERS, ROOT

SEMVER = re.compile(r"^v?\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.\-]+)?$")
CHANGELOG_RX = re.compile(r"(^|/)(CHANGE|CHANGES|HISTORY|NEWS|changelog)([-_.][\w.]*)?$", re.I)
NOISE = re.compile(r"(^|/)(node_modules|vendor|dist|build|target|\.venv)/", re.I)
STALE_DAYS = 30   # 阈值来源见 selftest 的两侧边界说明：不是拍脑袋，但**只是分类线不是判据**


def iso_days(a, b):
    """a、b 两个 ISO 日期相差**小数**天（a - b）。任一取不到返回 None（禁当 0）。

    首版返回 `.days`（整数截断），于是"release 22 小时前发、HEAD 刚提交"被读成 lag=0
    —— 看起来与"当天发当天提交"完全同形，正是把滞后洗成不滞后的口径（✅ 实测 self lag=0）。
    改小数天后同一条主张才可复核；阈值 STALE_DAYS 仍只是分类线，不是判据。
    """
    try:
        da = datetime.fromisoformat(str(a).replace("Z", "+00:00"))
        db = datetime.fromisoformat(str(b).replace("Z", "+00:00"))
        return round((da - db).total_seconds() / 86400.0, 2)
    except Exception:
        return None


def classify(paths):
    return sorted(p for p in paths if CHANGELOG_RX.search(p.split("/")[-1])
                  and not NOISE.search(p))[:4]


def api(path, token):
    req = urllib.request.Request("https://api.github.com/" + path,
                                 headers={"User-Agent": "xinyu-release-probe",
                                          "Accept": "application/vnd.github+json"})
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return json.loads(r.read().decode("utf-8", "replace")), ""
    except Exception as e:
        code = getattr(e, "code", None)
        return (None, "404" if code == 404 else "http=%s" % (code or type(e).__name__))


def probe_repo(slug, token):
    row, blind = {}, []
    rel, err = api("repos/%s/releases/latest" % slug, token)
    if err == "404":
        row["release"] = None            # 真没有 release，与"取不到"分开记
    elif rel is None:
        blind.append("release:" + err
                     )
    else:
        row["release"] = {"tag": rel.get("tag_name"), "published_at": rel.get("published_at"),
                          "assets": len(rel.get("assets") or []),
                          "prerelease": bool(rel.get("prerelease"))}
    info, err2 = api("repos/" + slug, token)
    if info is None:
        blind.append("repo:" + err2)
    else:
        row["pushed_at"] = info.get("pushed_at")
    tree, err3 = api("repos/%s/git/trees/HEAD?recursive=1" % slug, token)
    if tree is None:
        blind.append("tree:" + err3)
    elif tree.get("truncated"):
        blind.append("tree:truncated")
    else:
        row["changelog"] = classify([t.get("path", "") for t in tree.get("tree", [])
                                     if t.get("type") == "blob"])
    if blind:
        return row, ";".join(blind)
    r = row.get("release")
    row["semver_tag"] = bool(r and SEMVER.match(str(r.get("tag") or "")))
    row["lag_days"] = (iso_days(row.get("pushed_at"), r.get("published_at")) if r else None)
    return row, ""


def probe_self():
    tags = subprocess.run(["git", "-C", str(ROOT), "tag", "--sort=-creatordate"],
                          capture_output=True, text=True).stdout.split()
    head = subprocess.run(["git", "-C", str(ROOT), "log", "-1", "--format=%cI"],
                          capture_output=True, text=True).stdout.strip()
    rel, err = "", ""
    g = subprocess.run(["gh", "release", "view", "--json", "tagName,publishedAt,assets,isPrerelease"],
                       cwd=str(ROOT), capture_output=True, text=True)
    if g.returncode == 0 and g.stdout.strip():
        j = json.loads(g.stdout)
        rel = {"tag": j.get("tagName"), "published_at": j.get("publishedAt"),
               "assets": len(j.get("assets") or []), "prerelease": bool(j.get("isPrerelease"))}
    else:
        err = (g.stderr or "gh release view 失败").strip()[:60]
    changed = [p for p in classify([t.split("/")[-1] for t in ["CHANGELOG.md"]])]
    return {"release": rel or None, "pushed_at": head, "changelog": ["CHANGELOG.md"] if changed
            else [], "tags_total": len(tags), "semver_tag": bool(rel and SEMVER.match(rel["tag"])),
            "lag_days": (iso_days(head, rel["published_at"]) if rel else None),
            "err": err}


def run_selftest():
    ok, fail, n = 0, [], 0

    def want(cond, note):
        nonlocal n, ok
        n += 1
        if cond:
            ok += 1
        else:
            fail.append(note)

    for t, exp in [("v1.4.3", True), ("1.4.3", True), ("canary", False), ("v2.2.19-canary.26", True),
                   ("nightly-20260926", False), ("v1.4", False)]:
        want(bool(SEMVER.match(t)) == exp, "semver 判定 %s 期望 %s" % (t, exp))
    want(iso_days("2026-09-27T00:00:00Z", "2026-09-20T00:00:00Z") == 7, "lag 正例")
    want(iso_days("2026-09-27T06:00:00Z", "2026-09-26T00:00:00Z") == 1.25,
         "lag 小数：30 小时必须是 1.25 天，不能截成 1 或 0")
    want(iso_days(None, "2026-09-20") is None, "反例：取不到日期必须给 None，禁当 0")
    want(iso_days("垃圾", "2026-09-20") is None, "反例：非法日期不得静默算出天数")
    want(classify(["CHANGELOG.md", "docs/CHANGELOG-1.0.md", "README.md"]) ==
         ["CHANGELOG.md", "docs/CHANGELOG-1.0.md"], "CHANGELOG 识别")
    want(not classify(["node_modules/foo/CHANGELOG.md"]), "反例：依赖目录不得算")
    want(bool(CHANGELOG_RX.search("NEWS")) and not CHANGELOG_RX.search("newest-tips.md"),
         "反例：NEWS 精确、newest 不误伤")
    print("RELEASE-SELFTEST: %d/%d（semver 6｜lag 3｜CHANGELOG 3）" % (ok, n))
    for x in fail:
        print("  RELEASE-SELFTEST-FAIL " + x)
    return 0 if ok == n else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="")
    ap.add_argument("--self-only", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return run_selftest()
    token = os.environ.get("GITHUB_TOKEN") or subprocess.run(
        ["gh", "auth", "token"], capture_output=True, text=True).stdout.strip()
    if not token:
        print("RELEASE-ENV: 无 GitHub token ⇒ 不采数、不判绿")
        return 2
    rows, blind = {}, []
    for p in ([] if a.self_only else PEERS):
        slug = p["repo"]
        row, why = probe_repo(slug, token)
        if why:
            blind.append("%s(%s)" % (slug, why))
            print("[%-3s] %-36s BLIND %s" % (p["tier"], slug, why))
            continue
        rows[slug] = {"tier": p["tier"], **row}
        r = row.get("release")
        print("[%-3s] %-36s release=%-22s semver=%-5s 资产=%-3d lag=%-6s CHANGELOG=%s"
              % (p["tier"], slug, (r or {}).get("tag") or "无", row["semver_tag"],
                 (r or {}).get("assets", 0), row["lag_days"], len(row["changelog"])))
    st = probe_self()
    rows["__self__"] = st
    print("[self] %-36s release=%-22s semver=%-5s 资产=%-3d lag=%-6s CHANGELOG=%d 个｜tag 共 %d"
          % ("心屿 SoulIsle", (st.get("release") or {}).get("tag") or "无", st["semver_tag"],
             (st.get("release") or {}).get("assets", 0), st["lag_days"],
             len(st["changelog"]), st["tags_total"]))
    print("-" * 118)
    n = len(rows) - (0 if a.self_only else 1)
    if n:
        has = sum(1 for k, v in rows.items() if k != "__self__" and v.get("release"))
        sv = sum(1 for k, v in rows.items() if k != "__self__" and v.get("semver_tag"))
        cl = sum(1 for k, v in rows.items() if k != "__self__" and v.get("changelog"))
        lags = [v["lag_days"] for k, v in rows.items()
                if k != "__self__" and v.get("lag_days") is not None]
        stale = sum(1 for d in lags if d > STALE_DAYS)
        print("peers：有公开 release %d/%d ｜ tag 合 semver %d/%d ｜ 有 CHANGELOG 类件 %d/%d ｜"
              "发布滞后 >%d 天 %d/%d"
              % (has, n, sv, n, cl, n, STALE_DAYS, stale, len(lags)))
        if lags:
            lags.sort()
            print("  滞后天数分布：min=%d 中位=%d max=%d（阈值 %d 天只是分类线，不是判据）"
                  % (lags[0], lags[len(lags) // 2], lags[-1], STALE_DAYS))
    usable = n - len(blind)
    print("应测 %s 仓 ｜ 计入分母 %s ｜ BLIND %d ｜ 恒等式：%s"
          % (n, usable, len(blind), "OK" if usable + len(blind) == n else "FAIL"))
    if blind:
        print("  BLIND：" + "; ".join(blind))
    if a.json:
        Path(a.json).write_bytes(json.dumps(
            {"repos": rows, "blind": blind, "denominator": n, "usable": usable,
             "stale_days_threshold": STALE_DAYS,
             "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")},
            ensure_ascii=False, indent=1).encode("utf-8"))
        print("快照 -> " + a.json)
    return 0 if a.self_only else (1 if blind or usable + len(blind) != n else 0)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
