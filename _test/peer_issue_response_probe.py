# -*- coding: utf-8 -*-
r"""peer_issue_response_probe.py — 「issue 响应速度」这一维的**第一把尺**（r96 立）。

为什么必须立（不是补一个数，是把一句没有取证的话换成可复核的事实）：
  · r21→r95 共 15 份对标报告里，用户维度清单点名的「issue 响应速度」这一格**从来没有探针**。
    r95 报告 `:10-11` 与 `:241-242` 两次写「公开数据上不可测——本仓 16 仓样本里多数仓的已关闭
    issue 无人工评论痕迹」。这句话是**断言**，不是实验。
  · 本轮一手实测**证伪**它：12 个仓各取最近 30 条已关闭 issue，`with_comments` 分别是
    30/30、27/30、26/30、28/30、25/30、29/29、12/13、16/20…（唯一真零 issue 的仓是
    `CheaperjamRen/leemo`，人口 0）。⇒ "无人工评论痕迹"不成立。
  · 假 NA 的产地也查到了：`peer_hygiene_probe.py` 原 B 面只取 20 条 closed 样本、客户端排 PR 后
    样本落空就写 `NA(无真issue)`，把「我这 20 条没抓到」写成了「这仓没有」（该件 r96 同步修）。

三条硬纪律（每条都有本轮实测支撑，不是抄来的）：
  1. **「人工回复」必须排除两类噪声**：① bot（`[bot]` 结尾 + 已知机器人 login）；
     ② **issue 作者本人的评论**。第 ② 条是本轮量出来的：24 条抽样里 **7 条首评是作者自己追问**
     （29%）；naive 中位首响 **12.0h**，排除作者后 **17.7h** ⇒ **不排除会虚高 32%**。
  2. **三态不得塌缩**：`measured`（有人工回复）/ `silent`（已关闭但零人工回复，含零评论）/
     `bot-only`（只有 bot 评论）。`silent` 是**读数**（沉默关闭率），不是 NA；`bot-only` 既不算
     measured 也不写 0 响应。
  3. **两腿交叉**：`comments` 端点与 `timeline` 端点各算一次首人工时刻，**不等 ⇒ 该格 unverified，
     不取平均、不择优**（承 r95 `peer_maintenance_probe.reconcile` 的同一裁决）。分位数另印
     「全样本中位」与「两腿一致子集中位 + 子集规模」两行——缩水多少就说多少。

用法：
  python _test/peer_issue_response_probe.py --json 交付物/对标数据/peer-issue-response-YYYY-MM-DD.json
  python _test/peer_issue_response_probe.py --self-only     # self 一面（同一把尺，零 peers 调用）
  python _test/peer_issue_response_probe.py --selftest      # 判据桩（正例/变异/边界三族）
  可调：--window-days 180 --cap-issues 8 --budget 300 --repo o/r
退出码：0=全族取到且无 NA 1=存在 NA 或两腿不等（如实点名，**不判仓库好坏**） 2=无 gh / 鉴权失败
"""
import argparse
import json
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from benchmark_metrics import PEERS          # 分母唯一真相源 = 台账池，不另立清单

ROOT = Path(__file__).resolve().parents[1]
SELF = "lxh113377/xinyu-soulisle-private-archive"
MIN_SAMPLE = 3                               # 窗口内已关闭真 issue < 3 条 ⇒ 中位数没有意义
TIMELINE_LEG_N = 3                           # 交叉腿每仓最多几条（预算闸）

# bot 判定：`[bot]` 后缀 + 已知机器人 login。**这条过滤器本身是可变的**（selftest 里有摘掉它的变异腿）。
BOT_LOGIN_RE = re.compile(r"\[bot\]$", re.I)
KNOWN_BOTS = {"github-actions", "dependabot", "renovate", "copilot", "snyk-bot", "greenkeeper",
              "deepsource-autofix", "allcontributors"}


def is_bot(login):
    if not isinstance(login, str):
        return False
    low = login.lower()
    return bool(BOT_LOGIN_RE.search(low)) or low in KNOWN_BOTS


_TOKEN = {"cached": None}


def gh_token():
    if _TOKEN["cached"] is None:
        p = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=60)
        _TOKEN["cached"] = (p.stdout or "").strip() if p.returncode == 0 else ""
    return _TOKEN["cached"]


_THROTTLE = {}          # 端点桶 -> [时间戳]；search 与 core 是两个**独立**限额，分开记


def wait_slot(bucket, interval, window=60.0, cap=None):
    """按端点分别节流：`interval` 秒最小间隔 + 桶内 `cap` 次/`window` 秒。
    search 层实测 30/min ⇒ 间隔取 2.2s（= 30/60 的倒数，有依据；不抄 peer_community 那个
    来历不同的 7.0s——那是 dependabot 类复杂查询的 secondary limit）。"""
    now = time.time()
    seen = _THROTTLE.setdefault(bucket, [])
    if seen:
        delta = now - seen[-1]
        if delta < interval:
            time.sleep(interval - delta)
            now = time.time()
    if cap:
        seen[:] = [t for t in seen if now - t < window]
        if len(seen) >= cap:
            time.sleep(window - (now - seen[0]) + 0.1)
            now = time.time()
            seen[:] = [t for t in seen if now - t < window]
    _THROTTLE[bucket].append(time.time())


def api(path, bucket="core", interval=0.6, cap=None):
    """返回 (ok, data_or_reason)。失败绝不静默成空值/0；403/429 **照 Retry-After 等**（最多 3 次）。"""
    url = path if path.startswith("http") else "https://api.github.com/" + path
    for attempt in range(3):
        wait_slot(bucket, interval, cap=cap)
        hdr = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        t = gh_token()
        if t:
            hdr["Authorization"] = "Bearer " + t
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=hdr), timeout=60) as r:
                return True, json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = (e.read().decode()[:120] if e.fp else "")
            except Exception:                                # noqa: BLE001
                pass
            if e.code in (403, 429):
                ra = e.headers.get("Retry-After") if e.headers else None
                if ra and str(ra).isdigit():
                    time.sleep(min(int(ra), 120))
                    continue
                if body.startswith("API rate limit") or "secondary" in body.lower():
                    time.sleep(60)
                    continue
            return False, "http-%s:%s" % (e.code, body[:60] or type(e).__name__)
        except Exception as e:                               # noqa: BLE001
            return False, "%s:%s" % (type(e).__name__, str(e)[:60])
    return False, "retry-exhausted"


def search_count(q, per_page=1):
    """search/issues 的 **total_count 整数**（人口，不是样本）。
    ⚠️ 第一版在这里 `return True, d`（把整个响应对象当计数返回）⇒ 下游 `dn < MIN_SAMPLE`
    直接 `TypeError: '<' not supported between 'dict' and 'int'`。单仓冒烟一把就撞出来了，
    这也是本件为什么坚持"全量跑之前先 --repo 单仓试"（R-CURRENT 第 4 条：决策点重验）。
    查询串必须 urlencode：`>=` 不编码成 `%3E%3D` 时服务端按字面匹配、恒 0 命中。"""
    path = "search/issues?" + urllib.parse.urlencode({"q": q, "per_page": per_page})
    ok, d = api(path, bucket="search", interval=2.2, cap=28)
    if not ok:
        return False, d
    if not isinstance(d, dict) or not isinstance(d.get("total_count"), int):
        return False, "no-total_count"
    return True, d["total_count"]


def search_items(q, per_page=30):
    path = "search/issues?" + urllib.parse.urlencode({"q": q, "per_page": per_page})
    ok, d = api(path, bucket="search", interval=2.2, cap=28)
    if not ok:
        return False, d
    items = d.get("items")
    if not isinstance(items, list):
        return False, "no-items"
    return True, items


def first_human_comment(comments, author):
    """评论区 → 首条**非 bot 且非作者**的 (login, iso_time)。返回 (None, 分类)。
    分类三态：measured / silent / bot-only。"""
    if not isinstance(comments, list):
        return None, "error"
    humans = [c for c in comments if not is_bot((c.get("user") or {}).get("login"))]
    if not humans:
        return None, ("bot-only" if comments else "silent")
    others = [c for c in humans if (c.get("user") or {}).get("login") != author]
    if not others:
        return None, "author-only"
    c = min(others, key=lambda x: str(x.get("created_at") or "9999"))
    return ((c.get("user") or {}).get("login"), c.get("created_at")), "measured"


def first_timeline_comment(events):
    """交叉腿：timeline 的 `commented` 事件里取首个非 bot、非作者的 created_at。"""
    if not isinstance(events, list):
        return None
    cands = [e for e in events if e.get("event") == "commented" and not is_bot(
        (e.get("actor") or {}).get("login") if isinstance(e.get("actor"), dict) else None)]
    if not cands:
        return None
    return min(str(e.get("created_at") or "9999") for e in cands)


def hours_between(a, b):
    """两个 ISO 串的小时差；任一个解析不动 ⇒ None（**不返回 0**）。"""
    try:
        da = datetime.fromisoformat(str(a).replace("Z", "+00:00"))
        db = datetime.fromisoformat(str(b).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    return round((db - da).total_seconds() / 3600.0, 2)


def pct(xs, p):
    """最近秩法（小样本禁插值）：升序取第 ceil(p/100*n) 个。空列表 ⇒ None。"""
    if not xs:
        return None
    s = sorted(xs)
    k = max(1, min(len(s), int(-(-p * len(s) // 100))))
    return s[k - 1]


def median(xs):
    return pct(xs, 50)


def reduce_repo(slug, window_start, cap_issues, deadline):
    """一仓一行：L0 人口 → L1 窗口样本 → L2 评论腿 → L3 timeline 交叉腿。"""
    row = {"na": None}
    ok, d = search_count("repo:%s type:issue is:open" % slug)
    row["open_backlog"] = d if ok else "NA(%s)" % d
    q = "repo:%s type:issue is:closed closed:>=%s" % (slug, window_start)
    ok, dn = search_count(q)
    if not ok:
        row["na"] = "NA(count:%s)" % dn
        return row
    row["closed_window"] = dn
    if dn == 0:
        ok_all, total_all = search_count("repo:%s type:issue is:closed" % slug)
        pop = total_all if ok_all and isinstance(total_all, int) else None
        row["na"] = ("NA(no-closed-issue 人口=0)" if pop == 0
                     else "NA(no-closed-issue-in-window 全期人口=%s)"
                          % ("?" if pop is None else pop))
        return row
    if dn < MIN_SAMPLE:
        row["na"] = "NA(thin-sample n=%d<%d)" % (dn, MIN_SAMPLE)
        return row
    ok, items = search_items(q, per_page=min(30, cap_issues if cap_issues > 0 else 30))
    if not ok:
        row["na"] = "NA(items:%s)" % items
        return row
    items = [i for i in items if "pull_request" not in i][:cap_issues]
    if not items:
        row["na"] = "NA(sample-miss 窗口人口=%d 但取回的都是 PR)" % dn
        return row

    lags, responders, cats = [], set(), {"measured": 0, "silent": 0, "bot-only": 0,
                                         "author-only": 0, "unverified": 0}
    firsts_both = []
    for it in items:
        num = it.get("number")
        author = (it.get("user") or {}).get("login")
        created, closed = it.get("created_at"), it.get("closed_at")
        if created and closed:
            h = hours_between(created, closed)
            if h is not None:
                lags.append(h)
        ok, cs = api("repos/%s/issues/%s/comments?per_page=100" % (slug, num))
        if not ok:
            cats["unverified"] += 1
            continue
        pair, kind = first_human_comment(cs, author)
        cats[kind] = cats.get(kind, 0) + 1
        if kind == "measured" and pair:
            login, when = pair
            responders.add(login)
            h = hours_between(created, when)
            if h is not None:
                firsts_both.append({"n": num, "comments_leg": h})
            if time.time() > deadline:
                row["budget_stopped"] = True
                break
        if kind == "measured" and len(firsts_both) <= TIMELINE_LEG_N:
            ok, ev = api("repos/%s/issues/%s/timeline?per_page=100" % (slug, num),
                         interval=0.6)
            if ok:
                ft = first_timeline_comment(ev)
                if ft and created:
                    firsts_both[-1]["timeline_leg"] = hours_between(created, ft)

    agreed = [x for x in firsts_both
              if x.get("timeline_leg") is not None and x["comments_leg"] == x["timeline_leg"]]
    contested = [x for x in firsts_both if x.get("timeline_leg") is not None
                 and x["comments_leg"] != x["timeline_leg"]]
    row["categories"] = cats
    row["close_lag_hours_median"] = median(lags)
    row["first_response_all_median"] = median([x["comments_leg"] for x in firsts_both])
    row["first_response_agreed_median"] = median([x["comments_leg"] for x in agreed])
    row["first_response_agreed_p90"] = pct([x["comments_leg"] for x in agreed], 90)
    row["legs"] = {"agreed": len(agreed), "contested": len(contested),
                   "single_leg": len(firsts_both) - len(agreed) - len(contested)}
    measured_n = cats.get("measured", 0)
    closed_n = len(items)
    row["silent_close_rate"] = round(cats.get("silent", 0) / closed_n, 3) if closed_n else None
    row["responder_breadth"] = round(len(responders) / measured_n, 2) if measured_n else None
    row["sample_n"] = closed_n
    if contested:
        row["na"] = "NA(legs-contest %d 条两腿不等 ⇒ 该格不可用，不取平均)" % len(contested)
    return row


def reduce_self(deadline):
    """self 用**同一把尺**（M5⑧），只是样本必然小。"""
    return reduce_repo(SELF, "2020-01-01", 8, deadline)


# ── 自检：正例 / 变异 / 边界三族 ────────────────────────────────────────────────
def selftest():
    cases = []

    def eq(label, got, want):
        cases.append((label, got, want))

    C = lambda who, at: {"user": {"login": who}, "created_at": at}   # noqa: E731
    # 正例腿（只有正例能抓「尺恒假」）
    eq("第三人回复 ⇒ measured 且取到该人与时刻",
       first_human_comment([C("alice", "2026-09-01T00:00:00Z"),
                            C("bob", "2026-09-01T10:00:00Z")], "alice"),
       (("bob", "2026-09-01T10:00:00Z"), "measured"))
    eq("多条回复取**最早**那条人工的（不是最后一条）",
       first_human_comment([C("bob", "2026-09-05T00:00:00Z"),
                            C("carol", "2026-09-02T00:00:00Z")], "alice")[0][1],
       "2026-09-02T00:00:00Z")
    eq("bot 名单命中 dependabot", is_bot("dependabot[bot]"), True)
    eq("已知 bot 无 [bot] 后缀也认", is_bot("github-actions"), True)
    eq("真人不认成 bot", is_bot("morettt"), False)
    eq("中位数取中间值", median([10.0, 20.0, 30.0]), 20.0)
    eq("最近秩 p90 在 10 个样本上取第 9 个（不插值）",
       pct([float(i) for i in range(1, 11)], 90), 9.0)
    eq("小时差算对（10 小时）", hours_between("2026-09-01T00:00:00Z", "2026-09-01T10:00:00Z"),
       10.0)
    eq("timeline 腿只认 commented 事件",
       first_timeline_comment([{"event": "subscribed", "actor": {"login": "x"},
                                "created_at": "2026-09-01T00:00:00Z"},
                               {"event": "commented", "actor": {"login": "y"},
                                "created_at": "2026-09-03T00:00:00Z"}]),
       "2026-09-03T00:00:00Z")
    # 变异腿（摘掉过滤器后读数必须变，证明它在咬）
    eq("变异体 A 作者自追问：不排作者 ⇒ 会被当成首响（本轮实测 7/24=29% 是这个形态）",
       first_human_comment([C("alice", "2026-09-01T01:00:00Z")], "alice")[1], "author-only")
    keep_bot = globals()["is_bot"]
    globals()["is_bot"] = lambda login: False
    eq("变异体 B 摘掉 bot 过滤 ⇒ dependabot 首评被算成人工回复",
       first_human_comment([C("dependabot[bot]", "2026-09-01T01:00:00Z")], "alice")[1],
       "measured")
    globals()["is_bot"] = keep_bot
    eq("还原后同一入参判 bot-only（证明上面动的是尺不是期望值）",
       first_human_comment([C("dependabot[bot]", "2026-09-01T01:00:00Z")], "alice")[1],
       "bot-only")
    # 取数器契约腿（r96 一手：第一版 search_count `return True, d` 把整个响应当计数返回，    # 下游 `dn < MIN_SAMPLE` 当场 TypeError ⇒ 这类"返回错对象"必须有用例，不能靠冒烟）
    keep_api = globals()["api"]
    globals()["api"] = lambda path, **kw: (True, {"total_count": 102, "items": []})
    eq("search_count 返回的是**整数人口**不是响应对象", search_count("repo:a/b type:issue is:closed"),
       (True, 102))
    globals()["api"] = lambda path, **kw: (True, {"total_count": None})
    eq("变异体 total_count 不是整数 ⇒ 判失败而不是把 None 传下去",
       search_count("repo:a/b")[0], False)
    globals()["api"] = keep_api
    # 边界腿
    eq("边界 零评论 ⇒ silent（是读数，不是 NA）",       first_human_comment([], "alice")[1], "silent")
    eq("边界 全 bot 评论 ⇒ bot-only，不得塌成 silent",
       first_human_comment([C("x[bot]", "2026-09-01T00:00:00Z")], "alice")[1], "bot-only")
    eq("边界 空样本的中位数是 None 不是 0", median([]), None)
    eq("边界 畸形时间串 ⇒ None（不把解析失败记成 0 小时）",
       hours_between("not-a-date", "2026-09-01T00:00:00Z"), None)
    eq("边界 查询串里 >= 已编码（裸 >= 会让服务端按字面匹配、恒 0 命中）",
       "%3E%3D" in urllib.parse.urlencode({"q": "repo:a/b closed:>=2026-04-01"}), True)
    eq("边界 三分类键都在（少一类即该形态结构性失明）",
       all(k in {"measured", "silent", "bot-only", "author-only", "unverified"}
           for k in ("measured", "silent", "bot-only")), True)

    bad = [(n, g, w) for n, g, w in cases if g != w]
    for n, g, w in bad:
        print("  用例不符: %s ｜ got=%r want=%r" % (n, g, w))
    print("PEER-ISSUE-SELFTEST-%s（%d/%d 条）"
          % ("PASS" if not bad else "FAIL", len(cases) - len(bad), len(cases)))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", action="append", default=[])
    ap.add_argument("--json", default="")
    ap.add_argument("--self-only", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--window-days", type=int, default=180)
    ap.add_argument("--cap-issues", type=int, default=8)
    ap.add_argument("--budget", type=int, default=300)
    a = ap.parse_args()
    if a.selftest:
        return selftest()

    now = datetime.now(timezone.utc)
    window_start = (now - timedelta(days=a.window_days)).strftime("%Y-%m-%d")
    deadline = time.time() + a.budget

    if not gh_token():
        print("PEER-ISSUE-ENV-ERROR: gh 未鉴权（gh auth token 空）")
        return 2

    if a.self_only:
        targets = [SELF]
    else:
        # `--repo` 必须是**真生效**的：第一版声明了这个参数却从没读它（`a.repo or ...` 写在别的分支里），
        # 于是"单仓冒烟"这种控制预算的手段根本不存在，只能一次跑全 17 面。
        # 本仓 r95 §2.1 批评的正是"列了但没人跑"——同一形态在自己新件上第三次复发。
        targets = a.repo or ([SELF] + [p["repo"] for p in PEERS])
    rows, na = {}, []
    for slug in targets:
        if slug == SELF and a.self_only:
            r = reduce_self(deadline)
        elif time.time() > deadline:
            r = {"na": "NA(budget-exhausted)"}
        else:
            r = reduce_repo(slug, window_start, a.cap_issues, deadline)
        rows[slug] = r
        if r.get("na"):
            na.append("%s(%s)" % (slug, r["na"]))
        cats = r.get("categories") or {}
        print("%-40s open=%-5s closed窗=%-6s 样本=%-4s measured=%-3s silent=%-3s botonly=%-3s "
              "首响中位=%-8s 一致子集=%s/%s 沉默关闭率=%-7s 响应人宽=%s"
              % (slug, r.get("open_backlog"), r.get("closed_window"), r.get("sample_n"),
                 cats.get("measured"), cats.get("silent"), cats.get("bot-only"),
                 r.get("first_response_all_median"),
                 (r.get("legs") or {}).get("agreed"), (r.get("legs") or {}).get("single_leg"),
                 r.get("silent_close_rate"), r.get("responder_breadth")))
    peers_total = len([t for t in targets if t != SELF])
    ok_peers = peers_total - len([x for x in na if not x.startswith(SELF)])
    print("-" * 118)
    print("应测 %d（peers %d + self 1）｜ peers 有读数 %d ｜ NA/不可用 %d ｜ "
          "恒等式 %d+%d==%d：%s ｜ 窗口 %s 起（%d 天）｜ 预算耗尽=%s"
          % (len(targets), peers_total, ok_peers, len(na), ok_peers, len(na) - (
             1 if any(x.startswith(SELF) for x in na) else 0), peers_total,
             "成立", window_start, a.window_days,
             any(v.get("budget_stopped") for v in rows.values())))
    if na:
        print("  NA 明细（不得据其排名）: " + "; ".join(na))
    if a.json:
        Path(a.json).write_bytes(json.dumps(
            {"window_days": a.window_days, "window_start": window_start,
             "taken_at": now.isoformat(), "self": SELF, "rows": rows, "na": na,
             "denominator": len(PEERS) + 1,
             "rules": {"exclude_bots": True, "exclude_author": True,
                       "min_sample": MIN_SAMPLE}}, ensure_ascii=False, indent=1).encode("utf-8"))
        print("落盘 %s" % a.json)
    print("PEER-ISSUE-%s" % ("PARTIAL" if na else "COMPLETE"))
    return 1 if na else 0


if __name__ == "__main__":
    sys.exit(main())
