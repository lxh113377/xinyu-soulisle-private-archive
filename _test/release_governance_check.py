# -*- coding: utf-8 -*-
"""发布治理判据（r45 新增，双通道同尺）——盯「版本在动、内容没切版」这一族。

为什么是这一面：r45 对标 16 仓的发布治理，实测 **有公开 release 11/16、tag 合 semver 11/16、
有 CHANGELOG 类件只有 4/16、发布滞后 >30 天 4/11**（min=0 中位=9 max=261）。账面看我们自己很好：
`lag=0.56 天`、semver 合规、CHANGELOG 在册。**这个读数骗过了我第一版判据** —— lag 量的是
「最新 release ↔ 最后一次 push」，而真相是 `v1.4.3`(09-26 11:57) 之后已经堆了 **44 个 commit /
11 个 feat**（r40c/r40d/r41/r42/r43/r44/r45 整轮的功能增量），全躺在 `CHANGELOG [Unreleased]` 的
20 条 bullet 里没有切版。⇒ **滞后指标只看两端时间，看不见中间增量**，这就是本件要补的形状。

七条判据（R1/R2/R3/R6/R7 阻断，R4 只报，R5 明确不重复造）：
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
     c′) **登记 ≠ 提及**（r90 一手）：旧口径拿整段文本 `rounds_in(unreleased_section(...))` 当"已登记"，
        于是**别人散文里提一句 `r91` 就把漏记那一轮喂绿**——本轮真实发生：我在披露 bullet 里
        写了"红因归 r91"，R2c 当场从红转绿。现按本仓惯例只认**该轮自己的 `### ` 小节标题**为登记，
        纯正文提及改记 `R2c(口径)` 告警（可见但不冒充判定）。真面实测差集只多咬住确实没写小节的那一轮。
  R3 最新 tag 必须能在 CHANGELOG 里找到对应段（`## [x.y.z]`）⇒ 发出去的版本有说明
  R6 CHANGELOG 的 `### ` 段落标题集对上一版**只增不减**（r71 落地）。
     动因是 r70 我自己的一手代价：拿"既有条目行的前缀"当 Edit 锚点、替换文本里没把原表头回写
     ⇒ 一整条 `### Fixed（r69 · …）` 静默消失，`git diff --numstat` 的 20/1 才被看见，靠的是人眼。
     本仓纪律＝「补更正注不删原文」，标题留着才是下一轮对账的锚，故有意改名也必须把原标题留下。
     取数面**两个基准都要看**：`HEAD` 管"还没提交的吞行"（出事那一层在本机），
     `HEAD~1` 管"已经提交的吞行"（CI/干净克隆里 worktree==HEAD，只看 HEAD 会恒等而看不见失效）；
     两个基准都取不到（浅克隆/首提交）⇒ 记 `R6(未验)` 并**不得记为通过**（零输入不判绿）。
  R7 一个版本号在 CHANGELOG 里只许有一个 `## [x.y.z]` 段（r90 落地）。
     动因是 r90 盘面：`## [1.7.0]` 出现两次（57 行装切版后补记、102 行装主文），
     而 R3 只问「最新 tag 有没有对应段」⇒ 重复段全程无感，「v1.7.0 的发布说明是哪一段」
     在产物里没有唯一答案。正文取不到 ⇒ 记 `R7(未验)` 不判绿。
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

# 归属轮次的口径（r101 一手代价）：提交 `fix(r101 收口): … + r102 入口建卷` 里那个 r102 是
# **对下一轮的引用**，不是这条提交的归属轮 —— 旧口径把整条标题扫出的 rNNN 都当归属，于是
# R2c 判红点名一个还没有任何提交的轮次。与 r90 那条「散文提及不算登记」同族，只是这次
# 提及长在标题里。括号（scope）才是本仓写归属轮的位置。
SCOPE_RE = re.compile(r"^(?:feat|fix|perf|refactor)\(([^)]*)\)", re.I)


def commit_rounds(subjects):
    """返回 (归属轮次集合, 仅提及轮次集合)。

    只在「标题带 scope 且 scope 里确实有轮号」时才把 scope 外的轮号降为提及；
    无 scope（`fix: …`）或有 scope 但 scope 里没有轮号（`fix(收口): … r102 …`）一律沿用旧口径
    按整条标题判 —— 收窄只作用于写规范的提交，不给偷懒写法开后门（不放宽）。
    """
    owned, mentioned = set(), set()
    for s in subjects:
        m = SCOPE_RE.match(s)
        own = rounds_in(m.group(1)) if m else set()
        if own:
            owned |= own
            mentioned |= rounds_in(s) - own
        else:
            owned |= rounds_in(s)
    return owned, mentioned


def unreleased_bullets(md_text):
    """只数 [Unreleased] 到下一个 `## ` 之间的 `- ` 行；跨段计数会把历史版本算进来（分母虚高）。"""
    sec = unreleased_section(md_text)
    return None if sec is None else len(re.findall(r"^- ", sec, re.M))


def heading_rounds(md_text):
    """[Unreleased] 段内 **`### ` 小节标题**里出现的轮次号集合（R2c 的"已登记"口径）。

    为什么不能用整段文本（r90 一手实测的假绿）：`rounds_in(unreleased_section(...))` 扫的是全部字符，
    于是**别人散文里提一句 "r91" 就把 r91 那一轮喂绿了**。本轮真实发生：并行会话提交了 `feat(r91 …)`
    却尚未写它的 `###` 小节，而我在 CHANGELOG 的披露 bullet 里写了"红因归 r91"⇒ R2c 当场从红转绿。
    登记 = 为那一轮开一个小节（本仓惯例 `### Added（rNN · 主题）`），不是提到它。
    实测收窄后的差集只多咬住真正漏记的那一轮（见 selftest 边界 P/Q）。
    """
    sec = unreleased_section(md_text) or ""
    heads = [l for l in sec.splitlines() if l.startswith("### ")]
    return rounds_in("\n".join(heads))


def tag_section_present(md_text, tag):
    v = tag.lstrip("v")
    return bool(re.search(r"^## \[?v?" + re.escape(v) + r"\]?", md_text, re.M))


HEAD_LINE_RE = re.compile(r"(?m)^### .*$")


def heading_set(md_text):
    """CHANGELOG 的段落标题集（`### ` 整行）。R6 用它做「只增不减」的对照。"""
    return set(HEAD_LINE_RE.findall(md_text or ""))


VERSION_HEAD_RE = re.compile(r"(?m)^## \[?v?(\d+\.\d+\.\d+[^\]\s]*)\]?")


def duplicate_version_heads(md_text):
    """同一版本号出现 ≥2 个 `## [x.y.z]` 段 → {版本: [行号,…]}（空 dict=无重复）。

    立此判据的一手证据（r90 盘面）：`## [1.7.0] - 2026-09-30 …` 在 CHANGELOG 里出现**两次**
    （第 57 行装 r83 切版后的补记，第 102 行装切版主文）。R3 只问「最新 tag 有没有对应段」，
    重复段照样过 ⇒ 「v1.7.0 的发布说明是哪一段」这件事在产物里根本没有唯一答案。
    Keep a Changelog 的一版一段不是格式洁癖：Release notes / 依赖机器人 / 下一轮对账都按版本取数。
    """
    pos = {}
    for m in VERSION_HEAD_RE.finditer(md_text or ""):
        pos.setdefault(m.group(1), []).append(md_text.count("\n", 0, m.start()) + 1)
    return {k: v for k, v in pos.items() if len(v) > 1}


def judge(tag, commits, bullets, md_text, ceiling=CEILING, prev_bases=None):
    """纯函数：输入全是已解析好的读数（含 CHANGELOG 正文），故 selftest 不碰 git、不碰本机状态。

    `prev_bases`＝[(基准名, 该基准的 CHANGELOG 正文), …]（main 取 HEAD 与 HEAD~1 两面）。
    **取不到就必须不传**，R6 于是记「未验」而不是记「通过」——浅克隆里没有 HEAD~1，
    把「看不见」当成「没消失」就会造出一条在 CI 上永远绿的假腿。
    """
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
        subj = [s for s, _d in commits if NOTE_WORTHY.match(s)]
        req_rounds, stray_rounds = commit_rounds(subj)
        sec_rounds = rounds_in(unreleased_section(md_text))
        head_rounds = heading_rounds(md_text)
        miss = sorted(req_rounds - head_rounds, key=int)
        only_prose = sorted((head_rounds ^ sec_rounds) & req_rounds, key=int)
        stray = sorted(stray_rounds - head_rounds - req_rounds, key=int)
        if only_prose:
            warn.append("R2c(口径) 这些轮次只在散文/bullet 正文里被提到、没有自己的 `### ` 小节：%s"
                        " ⇒ 散文提及不算登记（r90 一手：我在披露里写了一句 r91 就把它喂绿了）"
                        % ",".join("r" + x for x in only_prose))
        if stray:
            warn.append("R2c(口径) 标题里提到、但不是本条提交归属轮次的轮号：%s"
                        " ⇒ 归属只认 `type(rNNN …)` 括号内的轮号；括号外提到别轮（如「r102 入口建卷」）"
                        "是引用不是记账，判红会让一个还没有提交的轮次背红因（r101 一手）"
                        % ",".join("r" + x for x in stray))
        if miss:
            bad.append("R2c 这些轮次有 feat/fix 级提交却没进 [Unreleased]（按 `### ` 小节标题认登记）：%s"
                      " ⇒ 计数非零会被旧轮次 bullet 掩盖，只有逐轮点名才看得见漏记的那几轮"
                      % ",".join("r" + x for x in miss))
    if not tag_section_present(md_text, tag):
        bad.append("R3 已发布的 %s 在 CHANGELOG 里没有对应版本段 ⇒ 发出去的版本无说明" % tag)
    days = lag_days(commits)
    if days is not None:
        warn.append("R4(只报) 距上次切版 %.1f 天、%d 个 commit" % (days, n))
    # R6：CHANGELOG 段落标题集对上一版**只增不减**（r70 一手代价：拿既有条目行当 Edit 锚点、
    #     替换文本里没把它回写 ⇒ 一整条 `### Fixed（r69 · …）` 静默消失，靠人眼看 numstat 才抓到）。
    #     有意改写标题在本仓不是理由——纪律是「补更正注不删原文」，标题留着才是下一轮对账的锚。
    # R6：CHANGELOG 段落标题集对上一版**只增不减**（r70 一手代价：拿既有条目行当 Edit 锚点、
    #     替换文本里没把它回写 ⇒ 一整条 `### Fixed（r69 · …）` 静默消失，靠人眼看 numstat 才抓到）。
    #     有意改写标题在本仓不是理由——纪律是「补更正注不删原文」，标题留着才是下一轮对账的锚。
    #     两个基准面各管一段窗口：HEAD 管「还没提交的吞行」（本机＝出事那一层），
    #     HEAD~1 管「已经提交的吞行」（CI/干净克隆里 worktree==HEAD，只看 HEAD 会恒等而看不见失效）。
    if not prev_bases:
        warn.append("R6(未验) 取不到 CHANGELOG 的任何上一版基准（浅克隆/首提交）⇒ 段落完整性未验证，不得记为通过")
    else:
        cur_h = heading_set(md_text)
        lost_all, seen = [], set()
        for label, text in prev_bases:
            lost = sorted(heading_set(text) - cur_h)
            notes.append("R6[%s] 基准标题 %d 条｜消失 %d 条" % (label, len(heading_set(text)), len(lost)))
            for x in lost:
                if x not in seen:
                    seen.add(x)
                    lost_all.append((label, x))
        if lost_all:
            bad.append("R6 CHANGELOG 段落标题消失 %d 条：%s ⇒ 把原标题按原文加回去（本仓纪律＝补更正注不删原文）"
                       % (len(lost_all), " ; ".join("%s 缺 %s" % (lb, x[:52]) for lb, x in lost_all[:2])))
    # R7：一个版本号只许有一个 `## [x.y.z]` 段（r90 一手：v1.7.0 有两段，R3 对此完全无感）
    if not (md_text or "").strip():
        warn.append("R7(未验) CHANGELOG 正文取不到 ⇒ 版本段唯一性未验证，不得记为通过")
    else:
        dup = duplicate_version_heads(md_text)
        n_heads = len(set(VERSION_HEAD_RE.findall(md_text)))
        if dup:
            bad.append("R7 CHANGELOG 有 %d 个版本号出现重复段：%s ⇒ 合并成一段（`### ` 小标题与正文一条不删）"
                       % (len(dup), " ".join("%s@行%s" % (k, ",".join(map(str, v)))
                                             for k, v in sorted(dup.items()))))
        else:
            notes.append("R7 版本段唯一性 %d/%d（每个版本号各一段）" % (n_heads, n_heads))
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
# r94：用例表提到模块级（原在 selftest 内，占 23 行 ⇒ 函数 166 行越过 loc_guard 的 150 行函数长门）。
# 提到外面不是为好看：`good` 与用例表是**数据**，与断言逻辑同处一函数会让「门」逼人去拆断言。
_GOOD_MD = "## [Unreleased]\n### Added\n- 一条\n\n## [1.5.0] - 2026-09-27\n- 历史\n"
_CASES = [
        # (name, tag, commits, bullets, md, expect_bad)
        ("正例：3 commit/1 feat 且已登记", "v1.5.0",
         [("feat: a", "2026-09-27T10:00:00+08:00"), ("docs: b", "x"), ("fix: c", "x")], 4, _GOOD_MD, False),
        ("反例①：feat 超上限", "v1.5.0",
         [("feat: f%d" % i, "x") for i in range(7)], 7, _GOOD_MD, True),
        ("反例②：有 feat 零 bullet", "v1.5.0", [("feat: f", "x")], 0, _GOOD_MD, True),
        ("反例③：有 bullet 零 commit", "v1.5.0", [], 5, _GOOD_MD, True),
        ("反例④：tag 无版本段", "v1.9.9", [("feat: f", "x")], 1, _GOOD_MD, True),
        ("反例⑤：缺 Unreleased 段", "v1.5.0", [("feat: f", "x")], None, _GOOD_MD, True),
        # R2c：bullet 数非零也挡不住漏记 —— 存量 bullet 会把没写的那几轮盖过去（首跑实测形态）
        ("反例⑥：旧轮次 bullet 掩盖新轮次漏记", "v1.5.0",
         [("feat(r41): 单测", "x"), ("feat(r42): 无障碍", "x"), ("docs(r40): 旧", "x")],
         9, "## [Unreleased]\n- r40 的旧条目\n- 还有一条 r40\n\n## [1.5.0]\n- 历史\n", True),
        ("正例②：逐轮点名全在册", "v1.5.0",
         [("feat(r41): 单测", "x"), ("feat(r42): 无障碍", "x")],
         # 登记形态按本仓惯例＝**给那一轮开一个 `### ` 小节**（r90 口径收窄后，只有 bullet 正文提一句不算登记）
         2, "## [Unreleased]\n### Added（r41 · 单测）\n- 补单测\n### Added（r42 · 无障碍）\n- 补无障碍\n\n## [1.5.0]\n- 历史\n", False),
        # 反向守卫 R2c 的分母：docs/chore 尾巴不该被要求登记（首跑就是这条把我自己的口径错抓出来）
        ("正例③：docs/chore 尾巴免登记", "v1.4.3",
         [("feat(r38): 护栏", "x"), ("chore(r38 台账): 刷新", "x"), ("docs(r38 收口): 报告", "x")],
         3, "## [Unreleased]\n### Added（r38 · 护栏）\n- r38 的说明\n\n## [1.4.3] - r38 续\n- 历史\n", False),
]


def _st_scope_rounds(fail):
    """边界 S/T：R2c 的「归属轮次」口径（r101 一手代价，见 `commit_rounds` 的注释）。

    抽成模块级不是为好看：`selftest` 加上这两条就 166 行越过 loc_guard 的 150 行函数长门
    （本文件 r94 那次已经为同样的原因把用例表提出来过一次）。
    表驱动用例只能断言「有没有红」，这里要断言**红里点的是谁**：收窄若把真漏记也放掉、
    或把别轮混进红堆，只有点名才看得见（红集合 == 点名集合，成员判定不算）。
    """
    com = [("feat(r101 ①): 耦合尺被审面扩到跨函数返回值", "2026-10-09T01:00:00+08:00"),
           ("fix(r101 收口): 报告补同句取证 + r102 入口建卷", "2026-10-09T02:00:00+08:00")]
    reg = ("## [Unreleased]\n### Fixed（r101 · 收口）\n- 一条\n\n## [1.5.0] - 历史\n").splitlines(True)
    md_reg = "".join(reg)
    md_miss = md_reg.replace("### Fixed（r101 · 收口）", "### Fixed")
    n = 0
    bad, warn, _ = judge("v1.5.0", com, 1, md_reg)
    r2c = [x for x in bad if x.startswith("R2c")]
    st = [x for x in warn if x.startswith("R2c(口径)") and "r102" in x]
    n += 1
    got1 = 1 if (not r2c and len(st) == 1) else 0
    if not got1:
        fail.append("边界S 标题引用下一轮（r102）仍被判红，或该引用没被点名"
                    "（应零 R2c 红 + 恰一条 R2c(口径) 点名 r102）：bad=%s warn=%s" % (bad, warn))
    bad2, warn2, _ = judge("v1.5.0", com, 1, md_miss)
    r2c2 = [x for x in bad2 if x.startswith("R2c")]
    n += 1
    got2 = 1 if (len(r2c2) == 1 and "r101" in r2c2[0] and "r102" not in r2c2[0]) else 0
    if not got2:
        fail.append("边界T 真漏记的那一轮没咬住，或红里混进了被引用的下一轮（收窄变成了放宽）：%s/%s"
                    % (bad2, warn2))
    return got1 + got2, n


def selftest():
    ok, fail = 0, []
    for name, tag, commits, bullets, md, want in _CASES:
        bad, _w, _n = judge(tag, commits, bullets, md)
        got = bool(bad)
        if got == want:
            ok += 1
        else:
            fail.append("%s want_bad=%s got=%s bad=%s" % (name, want, got, bad))
    # 边界 A：取不到 tag 必须走"不判绿"，且不得静默返回空问题
    bad, _w, _n = judge("", [], 0, _GOOD_MD)
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
    bad, _w, _n = judge("v1.5.0", [], 0, _GOOD_MD)
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
    # 边界 I..L：R6「CHANGELOG 段落标题只增不减」——r70 我自己吞掉一条 r69 标题才立的这条规矩
    _NL = chr(10)
    PREV = _NL.join(["## [Unreleased]", "### Added（r70 · 甲）", "- 一条",
                     "### Fixed（r69 · 乙）", "- 两条", "", "## [1.5.0] - 历史", ""])
    CUR_OK = _NL.join(["## [Unreleased]", "### Added（r71 · 丙）", "- 新",
                      "### Added（r70 · 甲）", "- 一条", "### Fixed（r69 · 乙）", "- 两条",
                      "", "## [1.5.0] - 历史", ""])
    CUR_LOST = _NL.join(["## [Unreleased]", "### Added（r71 · 丙）", "- 新",
                        "### Added（r70 · 甲）", "- 一条", "", "## [1.5.0] - 历史", ""])
    COMMITS = [("feat(r71): 新", "2026-09-28T10:00:00+08:00")]
    _b, _w, _n = judge("v1.5.0", COMMITS, 3, CUR_OK, prev_bases=[("HEAD", PREV)])
    if not any("R6" in x for x in _b):
        ok += 1
    else:
        fail.append("边界I 正例（标题只增）被 R6 误判红：%s" % _b)
    _b2, _w2, _n2 = judge("v1.5.0", COMMITS, 3, CUR_LOST, prev_bases=[("HEAD", PREV)])
    if any("R6" in x for x in _b2) and "r69 · 乙" in " ".join(_b2):
        ok += 1
    else:
        fail.append("边界J 反例（吞掉一条标题）未咬或没点名标题：%s" % _b2)
    _b3, _w3, _n3 = judge("v1.5.0", COMMITS, 3, CUR_OK)
    if not any("R6" in x for x in _b3) and any("R6(未验)" in x for x in _w3):
        ok += 1
    else:
        fail.append("边界K 无基准面时把「看不见」当通过（应记 R6(未验) 且不判红）：bad=%s warn=%s" % (_b3, _w3))
    _b4, _w4, _n4 = judge("v1.5.0", COMMITS, 3, PREV, prev_bases=[("HEAD", PREV), ("HEAD~1", PREV)])
    if not any("R6" in x for x in _b4) and all("消失 0 条" in x for x in _n4 if x.startswith("R6")):
        ok += 1
    else:
        fail.append("边界L 同一基准（零改动）误报消失或读数没进 notes：bad=%s notes=%s" % (_b4, _n4))
    # 边界 M..O：R7「一个版本号只许一段」——r90 盘面实测 v1.7.0 有两段而 R3 全程无感
    r7_sites = 0
    r7_sites += 1
    _b5, _w5, _n5 = judge("v1.5.0", COMMITS, 3, CUR_OK, prev_bases=[("HEAD", PREV)])
    if not any("R7" in x for x in _b5) and any(x.startswith("R7 版本段唯一性 1/1") for x in _n5):
        ok += 1
    else:
        fail.append("边界M 正例（一版一段）被 R7 误判红或读数没进 notes：bad=%s notes=%s" % (_b5, _n5))
    r7_sites += 1
    CUR_DUP = CUR_OK + _NL + "## [1.5.0] - 历史（第二段）" + _NL + "### Fixed（补记）" + _NL
    _b6, _w6, _n6 = judge("v1.5.0", COMMITS, 4, CUR_DUP, prev_bases=[("HEAD", PREV)])
    _r7 = [x for x in _b6 if x.startswith("R7")]
    if len(_r7) == 1 and "1.5.0@行" in _r7[0] and "," in _r7[0].split("1.5.0@行")[1]:
        ok += 1
    else:
        fail.append("边界N 反例（同版本号两段）未咬或没点名版本与行号：bad=%s" % _b6)
    r7_sites += 1
    _b7, _w7, _n7 = judge("v1.5.0", COMMITS, 0, "")
    if not any("R7" in x for x in _b7) and any("R7(未验)" in x for x in _w7):
        ok += 1
    else:
        fail.append("边界O 正文取不到时把「看不见」当通过（应记 R7(未验) 且不判红）：bad=%s warn=%s" % (_b7, _w7))
    # 边界 P..R：R2c「散文提及不算登记」（r90 一手：我在披露 bullet 里写了 r91 就把他人漏记那一轮喂绿）
    r2_sites = 0
    COMMITS_91 = COMMITS + [("feat(r91): 又一件", "2026-10-02T02:00:00+08:00")]
    r2_sites += 1
    CUR_PROSE = _NL.join(["## [Unreleased]", "### Added（r71 · 丙）",
                          "- 本轮披露：红因归 r91（**只是提到，没给它开小节**）",
                          "### Added（r70 · 甲）", "- 一条", "### Fixed（r69 · 乙）", "- 两条",
                          "", "## [1.5.0] - 历史", ""])
    _bp, _wp, _np = judge("v1.5.0", COMMITS_91, 4, CUR_PROSE, prev_bases=[("HEAD", PREV)])
    _r2c = [x for x in _bp if x.startswith("R2c")]
    if len(_r2c) == 1 and "r91" in _r2c[0] and any(x.startswith("R2c(口径)") and "r91" in x for x in _wp):
        ok += 1
    else:
        fail.append("边界P 散文提及 r91 仍被当成登记（应 R2c 红 + R2c(口径) 告警）：bad=%s warn=%s" % (_bp, _wp))
    r2_sites += 1
    CUR_HEAD = CUR_PROSE.replace("### Added（r71 · 丙）", "### Added（r91 · 丁）\n\n### Added（r71 · 丙）")
    _bq, _wq, _nq = judge("v1.5.0", COMMITS_91, 5, CUR_HEAD, prev_bases=[("HEAD", PREV)])
    if not any(x.startswith("R2c") for x in _bq) and not any(x.startswith("R2c(口径)") for x in _wq):
        ok += 1
    else:
        fail.append("边界Q 给 r91 开了 `### ` 小节却仍判红（口径把合法登记当缺失）：%s/%s" % (_bq, _wq))
    r2_sites += 1
    _br, _wr, _nr = judge("v1.5.0", COMMITS, 3, CUR_OK, prev_bases=[("HEAD", PREV)])
    if not any(x.startswith("R2c") for x in _br) and not any(x.startswith("R2c(口径)") for x in _wr):
        ok += 1
    else:
        fail.append("边界R 未涉及新轮次的正例被 R2c 新口径误伤：%s/%s" % (_br, _wr))
    _so, _sn = _st_scope_rounds(fail)
    ok += _so
    r2_sites += _sn
    total = len(_CASES) + 12 + r7_sites + r2_sites
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
    prev_bases, prev_rc = [], []
    for label in ("HEAD", "HEAD~1"):
        txt, rc = git("show", "%s:CHANGELOG.md" % label)
        prev_rc.append("%s=%s" % (label, "ok" if (rc == 0 and txt.strip()) else "取不到"))
        if rc == 0 and txt.strip():
            prev_bases.append((label, txt))
    bad, warn, notes = judge(tag, commits, bullets, md_text, a.ceiling, prev_bases)
    for w in warn:
        print("   ℹ️ " + w)
    if a.json:
        print(json.dumps({"tag": tag, "tag_source": src, "commit_channel": chan,
                          "commits": len(commits or []),
                          "feats": len([c for c in (commits or []) if FEAT_RE.match(c[0])]),
                          "unreleased_bullets": bullets, "prev_bases": prev_rc,
                          "notes": notes, "problems": bad},
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
