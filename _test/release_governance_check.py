# -*- coding: utf-8 -*-
"""发布治理判据（r45 新增，双通道同尺）——盯「版本在动、内容没切版」这一族。

为什么是这一面：r45 对标 16 仓的发布治理，实测 **有公开 release 11/16、tag 合 semver 11/16、
有 CHANGELOG 类件只有 4/16、发布滞后 >30 天 4/11**（min=0 中位=9 max=261）。账面看我们自己很好：
`lag=0.56 天`、semver 合规、CHANGELOG 在册。**这个读数骗过了我第一版判据** —— lag 量的是
「最新 release ↔ 最后一次 push」，而真相是 `v1.4.3`(09-26 11:57) 之后已经堆了 **44 个 commit /
11 个 feat**（r40c/r40d/r41/r42/r43/r44/r45 整轮的功能增量），全躺在 `CHANGELOG [Unreleased]` 的
20 条 bullet 里没有切版。⇒ **滞后指标只看两端时间，看不见中间增量**，这就是本件要补的形状。

五条判据（R1/R2/R3 阻断，R4 只报，R5 明确不重复造）：
  R1 距上次切版的 feat 增量 ≤ CEILING（5）。超了就是「攒了够多能力却还在用旧版本号对外」。
     取 5 而非 0：0 会让每轮对标都必先切版才能推进，把判据变成拦路的闸门（advisory 不拦、
     阻断要留真实余量）。当前值与上限一起印进行里，余量可见。
  R2 CHANGELOG `[Unreleased]` ⇄ git 增量 **双向**对账：
     a) 有 feat 却零 bullet ⇒ 功能变更没进 changelog（对外承诺与仓库不符）
     b) 有 bullet 却 `tag..HEAD` 零 commit ⇒ 写了没提交（文案先行同族）
     c) **逐轮点名**：commit 里出现过的轮次号 `rNN` 必须在 `[Unreleased]` 段里出现。
        这条是首跑被自己打的补丁 —— R2a 只看 bullet 数非零，而 `[Unreleased]` 里躺着 r39/r40 的
        20 条旧 bullet，**r41(单测)/r42(无障碍)/r43(可复现)/r44(数据权利) 四轮一条没记**却照样"过"。
        计数型判据被存量掩盖 = 恒真风险的又一形态，故改成按轮次集合求差。取数面上只对
        commit 正文里**确实存在**的 `rNN` 求差，无轮次号的提交不新增要求（不误伤）。
  R3 最新 tag 必须能在 CHANGELOG 里找到对应段（`## [x.y.z]`）⇒ 发出去的版本有说明
  R4 发布滞后天数：**只报不拦**。墙钟判据会在「零提交」的情况下自己从绿翻红，
     那是时间的颜色不是代码的颜色，进默认链就是误报源（本机既有铁律：默认链禁墙钟断言）。
  R5 版本三源对账（tag == pom == 文档）**已由 `repo_config_check.py` G12 负责**，本件不重复实现
     ——同义判据两处各写一份，改一处漏一处（r41 实测过这个形态）。

取数面：`git` 决定的一切（commit 数、feat 数、tag）；浅克隆拿不到 tag 时回落 `ls-remote`，
两边都拿不到 ⇒ **rc=2 UNVERIFIED**，禁止把「读不到」判成「违规」（R-ENUM / fail-open）。
用法：python _test/release_governance_check.py [--ceiling 5] [--json] [--selftest]
退出码：0=在限内 1=判红 2=取不到权威源（未验证，不算过）
"""
import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
CEILING = 5                      # R1：距上次切版允许的 feat 数上限（见 docstring 的取值理由）
FEAT_RE = re.compile(r"^feat(\(|:)", re.I)
UNREL_HDR = re.compile(r"^## \[Unreleased\]", re.M)


def git(*args):
    r = subprocess.run(["git", "-C", str(ROOT)] + list(args),
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return (r.stdout or "").strip(), r.returncode


def latest_tag():
    """两个通道，都失败才认未取到：浅克隆的工作树没有 tag，但 origin 上有。"""
    t, rc = git("describe", "--tags", "--abbrev=0")
    if rc == 0 and t:
        return t, "describe"
    out, rc = git("ls-remote", "--tags", "origin")
    if rc != 0 or not out:
        return "", "none"
    names = [ln.split("/")[-1] for ln in out.splitlines()
             if ln.strip() and not ln.rstrip().endswith("^{}")]
    sem = [n for n in names if re.match(r"^v?\d+\.\d+\.\d+$", n)]
    if not sem:
        return "", "none"
    key = lambda n: [int(x) for x in re.findall(r"\d+", n)]
    return max(sem, key=key), "ls-remote"


def commits_since(tag):
    if not tag:
        return [], ""
    out, rc = git("log", "--format=%s\x01%aI", tag + "..HEAD")
    if rc != 0:
        return None, "log-fail"
    return [ln.split("\x01") for ln in out.splitlines() if ln.strip()], ""


def repo_slug():
    url, rc = git("remote", "get-url", "origin")
    if rc != 0:
        return ""
    m = re.search(r"[:/]([^/:]+/[^/]+?)(?:\.git)?$", url.strip())
    return m.group(1) if m else ""


def gh_err_text(rc, stderr):
    """从 gh 的输出里挑那句人读错误：实测它打在**末行**（前面是 JSON 分片噪声）。纯函数，可自证。"""
    lines = [x for x in (stderr or "").strip().splitlines() if x.strip()]
    return "gh-rc%d[%s]" % (rc, (lines[-1] if lines else "无输出")[:120])


def compare_via_gh(tag):
    """第三通道：CI 的 actions/checkout 默认浅克隆**不带 tag**，本地 `git log tag..HEAD` 会直接失败。
    那样这条闸在受理面上就永远是 rc=2 惰性态（装了不等于在用），故走 GitHub compare API 补上。
    返回 (rows|None, err)；rows 与 commits_since 同构 = [(subject, committer-iso)]。"""
    slug = repo_slug()
    if not slug:
        return None, "no-slug"
    try:
        p = subprocess.run(["gh", "api", "repos/%s/compare/%s...HEAD" % (slug, tag)],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=45)
    except (OSError, subprocess.SubprocessError) as e:
        return None, "gh:%s" % type(e).__name__
    if p.returncode != 0:
        # 失败分支不许丢证据：只报 rc 会让下一轮再来一次"猜 rc=4 是什么"（CI 首跑就吃过这个）。
        return None, gh_err_text(p.returncode, p.stderr or p.stdout or "")
    try:
        d = json.loads(p.stdout)
        return [(c["commit"]["message"].splitlines()[0],
                 (c["commit"].get("committer") or {}).get("date") or "")
                for c in d.get("commits") or []], ""
    except Exception as e:
        return None, "gh-parse:%s" % type(e).__name__


def resolve_commits(log_rows, log_err, tag, fallback=None):
    """通道择优的纯函数。fallback 可注入（selftest 据此不打真 gh，也不靠本机状态判分支）。"""
    if log_err == "" and log_rows is not None:
        return log_rows, "git-log"
    rows, gerr = (fallback or compare_via_gh)(tag)
    if rows is not None:
        return rows, "gh-compare"
    return None, "log=%s gh=%s" % (log_err or "ok", gerr)


def unreleased_section(md_text):
    m = UNREL_HDR.search(md_text)
    if not m:
        return None
    rest = md_text[m.end():]
    nxt = re.search(r"^## ", rest, re.M)
    return rest[:nxt.start()] if nxt else rest


def rounds_in(text):
    return set(re.findall(r"(?<![A-Za-z0-9])r(\d{2,3})", text or ""))


# R2c 的分母：只有"会进 release note"的变更类型才要求登记。
# 首跑实测：r38 被判漏记，而 `## [1.4.3]` 段标题本身写着「对标轮 r38 续」—— 功能早已随版发布，
# tag 之后只剩它的 `chore(台账)` / `docs(收口)` 两条尾巴。把 docs/chore 也要求登记 = 判据口径错，
# 不是产品缺陷；收窄到 feat/fix/perf/refactor 后 r38 自然消失，r41-r44 四条 feat 仍然咬住。
NOTE_WORTHY = re.compile(r"^(feat|fix|perf|refactor)(\(|:)", re.I)


def unreleased_bullets(md_text):
    """只数 [Unreleased] 到下一个 `## ` 之间的 `- ` 行；跨段计数会把历史版本算进来（分母虚高）。"""
    sec = unreleased_section(md_text)
    return None if sec is None else len(re.findall(r"^- ", sec, re.M))


def tag_section_present(md_text, tag):
    v = tag.lstrip("v")
    return bool(re.search(r"^## \[?v?" + re.escape(v) + r"\]?", md_text, re.M))


def judge(tag, commits, bullets, md_text, ceiling=CEILING):
    """纯函数：输入全是已解析好的读数（含 CHANGELOG 正文），故 selftest 不碰 git、不碰本机状态。"""
    bad, warn, notes = [], [], []
    if not tag:
        return ["R0 取不到最新 tag（describe 与 ls-remote 双否）⇒ 本件无权威源，不判绿"], [], []
    if commits is None:
        return ["R0 `git log tag..HEAD` 取数失败 ⇒ 分母不可证"], [], []
    feats = [c for c in commits if FEAT_RE.match(c[0])]
    n, c = len(commits), len(feats)
    notes.append("tag=%s commits=%d feats=%d unreleased=%s" % (tag, n, c,
                 "NA" if bullets is None else bullets))
    if c > ceiling:
        bad.append("R1 距 %s 已攒 %d 个 feat（上限 %d）⇒ 该切版了；对外仍挂旧版本号" % (tag, c, ceiling))
    if bullets is None:
        bad.append("R2 CHANGELOG 缺 `## [Unreleased]` 段 ⇒ 增量无处登记")
    else:
        if c > 0 and bullets == 0:
            bad.append("R2a 有 %d 个 feat 但 [Unreleased] 零条 bullet ⇒ 功能变更没写进 changelog" % c)
        if bullets > 0 and n == 0:
            bad.append("R2b [Unreleased] 有 %d 条 bullet 而 %s..HEAD 零 commit ⇒ 写了没提交（文案先行）"
                       % (bullets, tag))
        sec_rounds = rounds_in(unreleased_section(md_text))
        subj = " ".join(s for s, _d in commits if NOTE_WORTHY.match(s))
        miss = sorted(rounds_in(subj) - sec_rounds, key=int)
        if miss:
            bad.append("R2c 这些轮次有 feat/fix 级提交却没进 [Unreleased]：%s ⇒ 计数非零会被旧轮次"
                       " bullet 掩盖，只有逐轮点名才看得见漏记的那几轮"
                       % ",".join("r" + x for x in miss))
    if not tag_section_present(md_text, tag):
        bad.append("R3 已发布的 %s 在 CHANGELOG 里没有对应版本段 ⇒ 发出去的版本无说明" % tag)
    days = lag_days(commits)
    if days is not None:
        warn.append("R4(只报) 距上次切版 %.1f 天、%d 个 commit" % (days, n))
    return bad, warn, notes


def lag_days(commits):
    """HEAD committer date − 该 tag 之后无发布时间戳可取，故按 HEAD 提交时间近似（只报不拦）。"""
    if not commits:
        return None
    iso = commits[0][1] if commits[0][1] else ""
    try:
        d = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except Exception:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return max(0.0, (datetime.now(timezone.utc) - d).total_seconds() / 86400.0)


# ---------------- selftest：正例 + 五条反例 + 边界，证明判据非恒真 ----------------
def selftest():
    ok, fail = 0, []
    good = "## [Unreleased]\n### Added\n- 一条\n\n## [1.5.0] - 2026-09-27\n- 历史\n"
    cases = [
        # (name, tag, commits, bullets, md, expect_bad)
        ("正例：3 commit/1 feat 且已登记", "v1.5.0",
         [("feat: a", "2026-09-27T10:00:00+08:00"), ("docs: b", "x"), ("fix: c", "x")], 4, good, False),
        ("反例①：feat 超上限", "v1.5.0",
         [("feat: f%d" % i, "x") for i in range(7)], 7, good, True),
        ("反例②：有 feat 零 bullet", "v1.5.0", [("feat: f", "x")], 0, good, True),
        ("反例③：有 bullet 零 commit", "v1.5.0", [], 5, good, True),
        ("反例④：tag 无版本段", "v1.9.9", [("feat: f", "x")], 1, good, True),
        ("反例⑤：缺 Unreleased 段", "v1.5.0", [("feat: f", "x")], None, good, True),
        # R2c：bullet 数非零也挡不住漏记 —— 存量 bullet 会把没写的那几轮盖过去（首跑实测形态）
        ("反例⑥：旧轮次 bullet 掩盖新轮次漏记", "v1.5.0",
         [("feat(r41): 单测", "x"), ("feat(r42): 无障碍", "x"), ("docs(r40): 旧", "x")],
         9, "## [Unreleased]\n- r40 的旧条目\n- 还有一条 r40\n\n## [1.5.0]\n- 历史\n", True),
        ("正例②：逐轮点名全在册", "v1.5.0",
         [("feat(r41): 单测", "x"), ("feat(r42): 无障碍", "x")],
         2, "## [Unreleased]\n- r41 补单测\n- r42 补无障碍\n\n## [1.5.0]\n- 历史\n", False),
        # 反向守卫 R2c 的分母：docs/chore 尾巴不该被要求登记（首跑就是这条把我自己的口径错抓出来）
        ("正例③：docs/chore 尾巴免登记", "v1.4.3",
         [("feat(r38): 护栏", "x"), ("chore(r38 台账): 刷新", "x"), ("docs(r38 收口): 报告", "x")],
         3, "## [Unreleased]\n- r38 的说明\n\n## [1.4.3] - r38 续\n- 历史\n", False),
    ]
    for name, tag, commits, bullets, md, want in cases:
        bad, _w, _n = judge(tag, commits, bullets, md)
        got = bool(bad)
        if got == want:
            ok += 1
        else:
            fail.append("%s want_bad=%s got=%s bad=%s" % (name, want, got, bad))
    # 边界 A：取不到 tag 必须走"不判绿"，且不得静默返回空问题
    bad, _w, _n = judge("", [], 0, good)
    if bad and "R0" in bad[0]:
        ok += 1
    else:
        fail.append("边界A 无 tag 未走 R0：%s" % bad)
    # 边界 B：bullet 计数只算 [Unreleased] 段，不得把历史版本行扫进来
    n = unreleased_bullets("## [Unreleased]\n- a\n- b\n\n## [1.4.3]\n- x\n- y\n- z\n")
    if n == 2:
        ok += 1
    else:
        fail.append("边界B 段内计数得 %s（应为 2）" % n)
    # 边界 C：bullet=0 且 commit=0（刚切完版）必须是干净的，防判据自己咬住空档期
    bad, _w, _n = judge("v1.5.0", [], 0, good)
    if not bad:
        ok += 1
    else:
        fail.append("边界C 刚切版被误判红：%s" % bad)
    # 边界 D：提交通道择优必须双向 —— 本地可用时不得去调外部 API，本地失败时才回落
    rows, chan = resolve_commits([("feat: x", "y")], "", "v1.5.0",
                                 fallback=lambda t: (_ for _ in ()).throw(AssertionError("不该被调用")))
    if chan == "git-log":
        ok += 1
    else:
        fail.append("边界D 本地可用却走了 %s" % chan)
    rows2, chan2 = resolve_commits(None, "log-fail", "v1.5.0",
                                   fallback=lambda t: ([("feat(r9): 靠 API 拿到", "z")], ""))
    if chan2 == "gh-compare" and rows2 and rows2[0][0].startswith("feat"):
        ok += 1
    else:
        fail.append("边界E 浅克隆态未回落到 gh-compare：%s/%s" % (chan2, rows2))
    rows3, chan3 = resolve_commits(None, "log-fail", "v1.5.0", fallback=lambda t: (None, "no-gh"))
    if rows3 is None and "no-gh" in chan3:
        ok += 1
    else:
        fail.append("边界F 双通道皆否却没留证据：%s" % chan3)
    # 边界 G：gh 失败原因必须把"人读那一行"带出来（用本机实测的 401 原文形状，不是编的）
    real401 = '{\n  "message": "Bad credentials",\n  "documentation_url": "https://docs.github.com/rest",\n  "status": "401"\n}\ngh: Bad credentials (HTTP 401)'
    e = gh_err_text(1, real401)
    if "HTTP 401" in e and e.startswith("gh-rc1["):
        ok += 1
    else:
        fail.append("边界G 未取到末行人读错误：%s" % e)
    if gh_err_text(4, "") == "gh-rc4[无输出]":
        ok += 1
    else:
        fail.append("边界H 空输出未留 rc：%s" % gh_err_text(4, ""))
    total = len(cases) + 8
    for x in fail:
        print("  SELFTEST-FAIL " + x)
    print("RELEASE-GOV-SELFTEST: %d/%d" % (ok, total))
    return 0 if ok == total else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ceiling", type=int, default=CEILING)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    md = ROOT / "CHANGELOG.md"
    if not md.exists():
        print("RELEASE-GOV-UNVERIFIED: 读不到 CHANGELOG.md ⇒ 不判绿")
        return 2
    md_text = md.read_text("utf-8", errors="replace")
    tag, src = latest_tag()
    log_rows, log_err = commits_since(tag)
    commits, chan = resolve_commits(log_rows, log_err, tag)
    bullets = unreleased_bullets(md_text)
    bad, warn, notes = judge(tag, commits, bullets, md_text, a.ceiling)
    for w in warn:
        print("   ℹ️ " + w)
    if a.json:
        print(json.dumps({"tag": tag, "tag_source": src, "commit_channel": chan,
                          "commits": len(commits or []),
                          "feats": len([c for c in (commits or []) if FEAT_RE.match(c[0])]),
                          "unreleased_bullets": bullets, "notes": notes, "problems": bad},
                         ensure_ascii=False))
    for b in bad:
        print("  · FAIL " + b)
    if not tag or commits is None:
        print("RELEASE-GOV-UNVERIFIED: 权威源缺失（tag 通道=%s 提交通道=%s）⇒ 不算通过" % (src, chan))
        return 2
    n, c = len(commits), len([x for x in commits if FEAT_RE.match(x[0])])
    if bad:
        print("RELEASE-GOV-FAIL: %d 项（%s｜feats=%d/%d unreleased=%s 提交通道=%s）"
              % (len(bad), tag, c, a.ceiling, bullets, chan))
        return 1
    print("RELEASE-GOV-PASS: %s 之后 feats=%d（上限 %d 余量 %d）｜commits=%d unreleased_bullets=%s"
          "｜提交通道=%s R3 版本段在册｜R4 滞后只报不拦"
          % (tag, c, a.ceiling, max(0, a.ceiling - c), n, bullets, chan))
    return 0


if __name__ == "__main__":
    sys.exit(main())
