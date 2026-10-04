# -*- coding: utf-8 -*-
r"""peer_maintenance_probe.py — 「维护状态」维的同址尺：**30 天提交率**（r95 立）。

为什么新立这一把尺（不是重复造轮子）：
  · 已有 `peer_hygiene_probe.py` 测的是 ★ / pushed_at / open_issues / release 90 天 / 贡献者数 ——
    全部是**状态快照**，问不出「近期到底动了多少」。
  · 而 A-project-better 的取证铁律补条五明写：「成熟度横比要取**同口径的 30 天窗口**，且窗口不足时
    禁止横比」。★ 数与提交数会打架，一手持读数：
      `SillyTavern/SillyTavern` ★34,083 / 30 天 **9** 次提交；
      `morettt/my-neuro`     ★1,387 / 30 天 **58** 次提交（★ 是它的 1/25，提交是它的 6.4 倍）。
    ⇒ **★ 数不是维护度的代理**。不量提交率就没法把这一格说清楚。
  · 本仓自身也必须被同一把尺量（M5⑧）：self 侧走 `git rev-list`，不走 API。

三条硬纪律（都是本轮一手踩出来的）：
  1. **分页 Link 头必须按 `page=(\d+)` 正则取，不能按固定字段序**。GitHub 实测 Link 是
     `<...?page=1&per_page=1>; rel="prev", <...?page=840&per_page=1>; rel="last"` ——
     `rel="last"` 出现在 `page` **之后**，任何"取 rel 前的 page"或"split('>')[0]"写法都会得到
     `1&per_page=1` 而 `int()` 抛错。第一版就死在这里：14/16 仓取数失败、异常被 except 吞掉后
     打印成 ERR，而 ERR 行既没进 unverified 计数也没影响分母 ⇒ **读数静默塌成 0**（补条七形态①）。
  2. **必须双腿交叉验证**（补条七 a）：分页法 vs `search/commits` 计数，两腿不等即该格判
     「不可用」，**不取平均、不择优、不猜哪个对**。本轮实测 3 仓抽验：2 仓逐字相等、
     1 仓差 1（搜索索引滞后）⇒ 该仓这一格降为 unverified。
  3. **self 的窗口可能不满 30 天**：本仓首个 commit = 2026-09-21，历史仅 ~14 天 ⇒ 30 天提交数
     无横比资格（补条五）。本件把 `history_days` 一并印出，让读的人自己判断，而不是把一个
     "14 天 314 次"写成"月更 314 次"。

用法：
  python _test/peer_maintenance_probe.py --json 交付物/对标数据/peer-maintenance-YYYY-MM-DD.json
  python _test/peer_maintenance_probe.py --self-only     # 只量本地 git 面，零网络
  python _test/peer_maintenance_probe.py --selftest      # 判据桩（含 Link 解析变异腿）
退出码：0=全部取到 1=存在取数失败/双腿不一致（如实点名，不判仓库好坏） 2=无 gh / 鉴权失败
"""
import argparse
import json
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from benchmark_metrics import PEERS  # 分母唯一真相源：台账同款仓池，不另立一份清单

ROOT = Path(__file__).resolve().parents[1]
SELF_DIR = ROOT
WINDOW_DAYS = 30
# 分页 Link 取数：按正则取**所有** page 值再取最大，不依赖字段序（纪律 1）
PAGE_RE = re.compile(r"[?&]page=(\d+)")
REL_LAST_RE = re.compile(r'rel="last"')

_TOKEN = {"cached": None}


def gh_json(url):
    """走 urllib + gh 的 token（gh api 的 --jq 会吐裸字符串，那不是合法 JSON，本仓排障表已记）。
    返回 (ok, data_or_reason)。失败绝不静默成空值/0。"""
    if _TOKEN["cached"] is None:
        p = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=60)
        _TOKEN["cached"] = (p.stdout or "").strip() if p.returncode == 0 else ""
    hdr = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if _TOKEN["cached"]:
        hdr["Authorization"] = "Bearer " + _TOKEN["cached"]
    try:
        req = urllib.request.Request(url, headers=hdr)
        with urllib.request.urlopen(req, timeout=60) as r:
            return True, {"json": json.loads(r.read().decode()), "link": r.headers.get("Link", "")}
    except Exception as e:                                   # noqa: BLE001 —— 失败要带原因，不许吞
        return False, "%s:%s" % (type(e).__name__, str(e)[:70])


def parse_link_pages(link):
    """纯函数：Link 头 → 最大页号（None = 无 rel=last，即结果不足一页）。
    纪律 1 的落点：正则取全部 `page=N` 再取 max；**不按字段序、不 split('>')**。"""
    if not link or not REL_LAST_RE.search(link):
        return None
    pages = [int(x) for x in PAGE_RE.findall(link)]
    return max(pages) if pages else None


def commits_via_pages(repo, since_iso):
    """腿 1：`/commits?since=` + 分页 Link。返回 (ok, n_or_reason, via)。"""
    url = "https://api.github.com/repos/%s/commits?since=%s&per_page=1" % (repo, since_iso)
    ok, d = gh_json(url)
    if not ok:
        return False, d, "-"
    body = d["json"]
    last = parse_link_pages(d["link"])
    if last is None:
        return True, len(body), "single-page(len)"
    return True, last, "link-rel-last"


def commits_via_search(repo, since_date):
    """腿 2（独立取数路径）：`search/commits` 的 total_count。
    ⚠️ 查询串必须 urlencode：`+` 不编码成 `%20` 时服务端按字面匹配，恒 0 命中（补条七形态②）。"""
    q = urllib.parse.urlencode({"q": "repo:%s committer-date:>=%s" % (repo, since_date), "per_page": 1})
    ok, d = gh_json("https://api.github.com/search/commits?" + q)
    if not ok:
        return False, d
    return True, d["json"].get("total_count")


def reconcile(n1, n2):
    """双腿对账：相等=已验；不等=不可用（不取平均、不择优）。返回 (verdict, 说明)。"""
    if n1 is None or n2 is None:
        return "unverified", "单腿取数失败"
    if int(n1) == int(n2):
        return "verified", "两腿逐字相等"
    return "unverified", "两腿不等（分页法=%s / search法=%s）⇒ 该格不可用，不取平均" % (n1, n2)


def self_face(since_iso):
    """self 侧：同一把尺量自己，但走 git 面（零网络、逐条可复算）。
    同时算出**历史跨度** —— 跨度不足 WINDOW_DAYS 时，30 天读数无横比资格（纪律 3）。"""
    def g(*a):
        p = subprocess.run(["git", *a], cwd=str(SELF_DIR), capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=120)
        return p.returncode, (p.stdout or "").strip()
    rc, n = g("rev-list", "--count", "--since=" + since_iso, "HEAD")
    n = int(n) if rc == 0 and n.isdigit() else None
    rc, oldest = g("log", "--reverse", "--format=%cI", "--max-parents=0")
    hist = None
    if rc == 0 and oldest:
        try:
            d0 = datetime.fromisoformat(oldest.splitlines()[0].replace("Z", "+00:00"))
            hist = (datetime.now(timezone.utc) - d0).days
        except ValueError:
            hist = None
    rc, tags = g("tag", "--list")
    return {"commits_30d": n, "history_days": hist,
            "tags": len([t for t in tags.split() if t]),
            "window_full": bool(hist is not None and hist >= WINDOW_DAYS),
            "rate_per_day": (round(n / WINDOW_DAYS, 2) if n is not None else None)}


def probe(repo, since_iso, since_date):
    ok1, n1, via = commits_via_pages(repo, since_iso)
    ok2, n2 = commits_via_search(repo, since_date)
    verdict, why = reconcile(n1 if ok1 else None, n2 if ok2 else None)
    out = {"commits_30d_paged": n1 if ok1 else "NA(%s)" % n1,
           "commits_30d_search": n2 if ok2 else "NA(%s)" % n2,
           "via": via, "verdict": verdict, "why": why,
           "rate_per_day": round(n1 / WINDOW_DAYS, 2) if ok1 and n1 else 0.0}
    if not (ok1 and ok2):
        out["verdict"] = "unverified"
    return out


# ── 自检：Link 解析的四种形态 + 两腿对账的三种裁决 + 查询串编码陷阱 ────────────
def selftest():
    cases = []

    def eq(label, got, want):
        cases.append((label, got, want))

    # Link 解析：纪律 1 的正反两面都在这儿
    eq("Link 无 rel=last ⇒ None（结果不足一页）",
       parse_link_pages('<https://x?page=2&per_page=1>; rel="next"'), None)
    eq("Link 有 rel=last 且 page 在前 ⇒ 取到末页",
       parse_link_pages('<https://x?page=1&per_page=1>; rel="prev", '
                        '<https://x?page=840&per_page=1>; rel="last"'), 840)
    eq("Link 里 page= 被 & 夹住（第一版 int() 抛错处）⇒ 不抛错且取对",
       parse_link_pages('<https://x?page=3&per_page=1>; rel="last"'), 3)
    eq("Link 字段序颠倒（rel 在前 page 在后）⇒ 仍取到末页",
       parse_link_pages('<https://x?per_page=1&page=57>; rel="last"'), 57)
    eq("Link 空串 ⇒ None", parse_link_pages(""), None)
    eq("Link 有 rel=last 但无 page ⇒ None（不得回落到 1）",
       parse_link_pages('<https://x?per_page=1>; rel="last"'), None)
    # 两腿对账
    eq("两腿相等 ⇒ verified", reconcile(12, 12)[0], "verified")
    eq("两腿不等 ⇒ unverified（不取平均）", reconcile(12, 11)[0], "unverified")
    eq("单腿失败 ⇒ unverified", reconcile(None, 11)[0], "unverified")
    # 查询串编码（补条七形态②）：查询词里的 **`+` 字面量** 必须编码成 `%2B`，
    # 否则服务端按字面匹配、恒 0 命中；`>=` 也必须编码。一手：`gh search repos "openemr+openemr"`
    # 实测 total_count=0，0 结果看着像「该主题无同类项目」，实际是查询串错了。
    enc = urllib.parse.urlencode({"q": "repo:a/b committer-date:>=2026-09-05", "per_page": 1})
    eq("查询词里的 >= 已编码", "%3E%3D" in enc, True)
    enc_plus = urllib.parse.urlencode({"q": 'repo:a/b "openemr+openemr"'})
    eq("查询词里的裸 + 已编码成 %2B（否则服务端按字面匹配、恒 0 命中）", "%2B" in enc_plus, True)
    eq("编码后不再残留裸 + 在引号内", 'repo:a/b "openemr+openemr"' in enc_plus, False)
    # 变异体：把正则换成永不匹配 ⇒ 末页必塌成 None（证明这条识别真在作用）
    keep = PAGE_RE
    globals()["PAGE_RE"] = re.compile(r"(?!x)x")
    eq("变异体 摘掉 page 正则后末页塌成 None（不得仍取到 840）",
       parse_link_pages('<https://x?page=1&per_page=1>; rel="prev", '
                        '<https://x?page=840&per_page=1>; rel="last"'), None)
    globals()["PAGE_RE"] = keep
    # 变异体：对账判据摘掉「不等」这一支 ⇒ 差 1 也放行（证明它不是恒真）
    eq("变异体 两腿差 1 仍判 unverified（防止被改成取平均）",
       reconcile(2, 1)[0], "unverified")

    bad = [(n, g, w) for n, g, w in cases if g != w]
    for n, g, w in bad:
        print("  用例不符: %s ｜ got=%r want=%r" % (n, g, w))
    print("PEER-MAINT-SELFTEST-%s（%d/%d 条）"
          % ("PASS" if not bad else "FAIL", len(cases) - len(bad), len(cases)))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", action="append", default=[])
    ap.add_argument("--json", default="")
    ap.add_argument("--self-only", action="store_true", help="只量本地 git 面（零网络），用于自证与离线复核")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()

    now = datetime.now(timezone.utc)
    since_dt = now - timedelta(days=WINDOW_DAYS)
    since_iso = "%04d-%02d-%02dT00:00:00Z" % (since_dt.year, since_dt.month, since_dt.day)
    since_date = "%04d-%02d-%02d" % (since_dt.year, since_dt.month, since_dt.day)

    me = self_face(since_iso)
    print("[self %s] 30d=%s (%s/日) 历史跨度=%s天 窗口满=%s tags=%d"
          % (SELF_DIR.name, me["commits_30d"], me["rate_per_day"], me["history_days"],
             "是" if me["window_full"] else "否（窗口不足，暂不横比）", me["tags"]))
    if a.self_only:
        return 0

    ok, why = gh_json("https://api.github.com/user")
    if not ok:
        print("PEER-MAINT-ENV-ERROR: gh 未鉴权/不可达（%s）" % why)
        return 2
    repos = a.repo or [p["repo"] for p in PEERS]
    rows, bad = {}, []
    for r in repos:
        d = probe(r, since_iso, since_date)
        rows[r] = d
        if d["verdict"] != "verified":
            bad.append("%s(%s)" % (r, d["why"]))
        print("%-40s 30d=%-7s search=%-7s %-6s 率=%-6s %s"
              % (r, d["commits_30d_paged"], d["commits_30d_search"], d["via"],
                 d["rate_per_day"], d["verdict"]))
    print("-" * 110)
    print("应测 %d 仓 ｜ 两腿一致 %d ｜ 不可用 %d ｜ self 历史跨度 %s 天（窗口满=%s）"
          % (len(repos), len(repos) - len(bad), len(bad), me["history_days"],
             "是" if me["window_full"] else "否 ⇒ self 的 30d 读数**无横比资格**，只作自身趋势"))
    if bad:
        print("  不可用格（不得据其排名）: " + "; ".join(bad))
    if a.json:
        p = Path(a.json)
        p.write_bytes(json.dumps({"window_days": WINDOW_DAYS, "taken_at": now.isoformat(),
                                  "self": me, "peers": rows, "unverified": bad,
                                  "denominator": len(repos)},
                                 ensure_ascii=False, indent=1).encode("utf-8"))
        print("落盘 %s" % p)
    print("PEER-MAINT-%s" % ("PARTIAL" if bad else "COMPLETE"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())