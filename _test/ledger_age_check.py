# -*- coding: utf-8 -*-
r"""ledger_age_check.py — 对标台账的**龄期**尺（r96 立）。

本件只做一件没人做的事：**龄期**。不碰「哪一份是最新」与「内容是否过时」——那两件事归
`bench_rollup.py` 所有（`_latest()` 按 mtime 选最新、`is_stale` 按内容判过时）。
同一事实只许一处判，所以本件的判据词全程用 `AGE`/`OVER-FUSE`，**刻意避开 `stale`**。

为什么必须新立（一手实测，非推测）：
  1. r95 报告 §1 八维总览里维度 1/5 的 peers 列写着「16 仓同址尺」，但底层 peer 台账按文件名日期
     有 **12/15 族已 8–9 天没重采**（2026-09-26/27），而 `.ci/contract.json` 自己声明
     `refresh_days=7`。⇒ 报告里的「现测」二字名不副实，而此前**没有任何一把尺盯台账的龄**。
  2. **龄期取哪个源会直接改变裁决**：同一批台账 mtime 全是 2026-09-28（一次批量重写留下的痕），
     文件名日期是 09-26/27。按 mtime 算龄=7 ⇒ 恰在 fuse 线内 ⇒ 全绿；按文件名算龄=8/9 ⇒ 超 fuse。
     **判据取数源一换，红绿就翻面**，而这件事此前没人记账。⇒ 本件以**文件名日期**为权威
     （探针写盘时把采集日刻进文件名），并把「mtime 最新 vs 文件名最新」的分歧单独计一列，不藏。
  3. 交叉腿：`_latest()` 按 mtime 选「最新一份」。一旦有人 `git checkout` 或搬卷，mtime 会
     **整体刷新** ⇒「最新」静默换成旧的一份，rollup 据此渲染的整行读数都跟着错，而 rollup 自己
     看不出（它只信 mtime）。⇒ 本件把这条对账做成常驻判据。

阈值不拍脑袋：FUSE **读 `.ci/contract.json` 的 `refresh_days`**（本仓唯一已入库、且已被
`ci_contract_check` 结构门盯着的「对端数据多久必须重采」声明），不在本件里抄一份数字。
读不到 ⇒ `UNVERIFIED`（**禁止回落到一个像样的默认值**：那会让 12 族超龄台账被读成都新鲜）。

用法：
  python _test/ledger_age_check.py                        # 默认 peer-*.json，fuse 取自契约
  python _test/ledger_age_check.py --only hygiene         # 只验某族（三拍 runbook 的回读腿）
  python _test/ledger_age_check.py --fuse-days 999        # 演习：显式放宽 ⇒ 必须转绿（证尺咬在被检对象上）
  python _test/ledger_age_check.py --json out.json        # 机读台账（裸 LF）
  python _test/ledger_age_check.py --selftest             # 判据桩（正例/变异/边界三族）
退出码：0=无超 fuse 且无分歧且恒等式成立
        1=存在超 fuse / 无日期可判 / 最新分歧 / 恒等式不成立（如实点名，不判数据好坏）
        2=fuse 取不到 / 目录不存在 / 无可判台账 ⇒ UNVERIFIED，**绝不判绿**
"""
import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIR = "交付物/对标数据"
DEFAULT_PATTERN = "peer-*.json"
# 取数不全的台账（r96 一手：12 探针同轮 burst 重采撞 GitHub secondary rate limit，
# hygiene 12/17 行、community 6/16 行拿到的是 NA）。** degraded 不得冒充基线 ** ⇒ 挪进本目录，
# 两个读它的判据（bench_rollup 的 `glob("peer-*.json")` 与本件的 glob）都是**非递归**的，天然看不见。
# 但"看不见"不等于"不存在"⇒ 本件专门数一次并印出来（盲区不得读成零）。
PARTIAL_DIRNAME = "_partial"
CONTRACT = ".ci/contract.json"

# 文件名尾部的采集日期：`peer-a11y-2026-09-27.json` → 族名 `peer-a11y`、日期 2026-09-27。
# 分隔符 `-` 与 `.` 都认（`benchmark-metrics-r95.2026-10-04.json` 用 `.`）；锚定 `.json` 之前，
# 所以中间出现的数字段不会被误当日期。sub 时连同分隔符一起剥 ⇒ 族名干净。
TRAIL_DATE_RE = re.compile(r"[-.](\d{4})-(\d{2})-(\d{2})(?=\.json$)")
TS_KEYS = ("taken_at", "ts", "generated_at", "as_of")


def read_fuse(repo_root, rel=CONTRACT):
    """契约 → refresh_days(int)。任何一步取不到一律返回 (None, 原因)，**不回落默认值**。"""
    p = Path(repo_root) / rel
    if not p.is_file():
        return None, "契约文件不存在(%s)" % rel
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:                                    # noqa: BLE001 —— 原因要能读出来
        return None, "契约解析失败(%s)" % type(e).__name__
    if not isinstance(data, dict):
        return None, "契约正文不是对象"
    v = data.get("refresh_days")
    if isinstance(v, bool) or not isinstance(v, int) or v <= 0:
        return None, "契约无合法 refresh_days（取到 %r）" % (v,)
    return v, "读自 %s" % rel


def parse_named_date(name):
    """文件名 → date；取不到返回 None（**不返回 date.min 这类假值**）。"""
    m = TRAIL_DATE_RE.search(name)
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:                                        # 2026-13-45 这种形状
        return None


def stem_of(name):
    """族名 = 先剥尾部日期段（**必须在带 .json 的完整名上做**，日期正则的 lookahead 靠它锚定），
    再剥后缀。若先切后缀，lookahead `(?=\\.json$)` 就永不命中 ⇒ 日期留在族名里、一族被拆成多族。"""
    stripped = TRAIL_DATE_RE.sub("", name)
    return stripped[:-len(".json")] if stripped.endswith(".json") else stripped


def parse_iso_ts(s):
    """JSON 里的 ISO 串 → date；取不到返回 None。各探针字段名不统一，故按候选键找。"""
    if not isinstance(s, str):
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def inner_date(path):
    """回落腿：读 JSON 正文的时间戳。返回 (date|None, 命中键或原因)。"""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:                                    # noqa: BLE001
        return None, "正文不可读(%s)" % type(e).__name__
    if not isinstance(data, dict):
        return None, "正文不是对象"
    for k in TS_KEYS:
        if k in data:
            d = parse_iso_ts(data[k])
            if d:
                return d, "正文键 " + k
            return None, "键 %s 的值解析不出日期" % k
    return None, "无候选时间戳键(%s)" % "/".join(TS_KEYS)


def evaluate(members, fuse, today):
    """**纯函数**：一族成员 → 一行裁决。members = [(name, date|None, date_src, mtime_epoch)]。
    抽成纯函数是为了让"族聚合 / 最新择取 / 分歧判定"这三件事可被自测覆盖，
    而不必往受管根造台账文件，也不读本机状态当夹具。"""
    dated = [m for m in members if m[1] is not None]
    by_name = max(dated, key=lambda m: m[1]) if dated else None
    by_mtime = max(members, key=lambda m: m[3])
    # 交叉腿的**前提**是 mtime 真的携带信息。CI/全新 clone 下 `actions/checkout` 把每个文件都写成
    # 同一时刻 ⇒ 全族 mtime 相同 ⇒ "mtime 最新"只是并列时的任意选择，与文件名最新不一致**不代表数据旧**。
    # r96 一手：这条腿在 CI 上把整个判据判红（run 37281131793），而本地永远看不到。
    # 处置=**逐条降档而非整判据降档**（R311）：龄期照判，只把这一腿降为"本维未验"，
    # 并由 selftest 的反例腿证明"mtime 有区分度时它仍然咬"。
    mtime_uniform = len({m[3] for m in members}) <= 1
    stem = stem_of(members[0][0])
    if by_name is None:
        return {"stem": stem, "files": len(members), "state": "UNDATEd", "age_days": None,
                "newest": None, "why": members[0][2], "latest_by_mtime": by_mtime[0]}
    row = {"stem": stem, "files": len(members), "newest": by_name[0],
           "named_date": str(by_name[1]), "age_source": by_name[2],
           "age_days": (today - by_name[1]).days,
           "state": "OVER-FUSE" if (today - by_name[1]).days > fuse else "WITHIN",
           "latest_by_mtime": by_mtime[0]}
    if by_mtime[0] != by_name[0]:
        if mtime_uniform:
            row["divergence_unverified"] = (
                "mtime 全族同值（%d 个成员同一 mtime）⇒ 本腿无区分度、记未验"
                % len(members))
        else:
            row["divergence"] = "mtime 最新=%s ≠ 文件名最新=%s" % (by_mtime[0], by_name[0])
    return row


def scan(dir_path, pattern, fuse, today):
    """IO 腿：目录 → 按族聚合 → 逐族 evaluate。"""
    fams = {}
    for f in sorted(Path(dir_path).glob(pattern)):
        if not f.is_file():
            continue
        d = parse_named_date(f.name)
        src = "文件名"
        if d is None:
            d, src = inner_date(f)
        fams.setdefault(stem_of(f.name), []).append((f.name, d, src, f.stat().st_mtime))
    return [evaluate(fams[s], fuse, today) for s in sorted(fams)]


# ── 自检：正例 / 变异 / 边界三族。缺任一族即本件不合格（只测拒绝侧会让新能力永久隐身）──
def resolve_fuse(args_fuse, repo_root, rel=CONTRACT):
    """阈值解析：**`0` 是合法覆盖值，不得被当"没传"**（本件第一版写的 `if a.fuse_days`
    让 `--fuse-days 0` 静默回落成契约的 7 ⇒ 演习腿量不到东西，红因还被记成"契约没刷新"）。"""
    if args_fuse is not None:
        return args_fuse, "调用方显式覆盖 --fuse-days"
    return read_fuse(repo_root, rel)


def count_partials(dir_path):
    """被排除的 degraded 台账数（挪进 `_partial/` 的那些）。**返回 (n, 文件名列表)**。
    为什么必须印出来：`peer-*.json` 是非递归 glob ⇒ 子目录里的东西"不计入"，
    而"不计入"极易被读成"没有"。盲区要单独成一个态，不得与零混同。"""
    p = Path(dir_path) / PARTIAL_DIRNAME
    if not p.is_dir():
        return 0, []
    names = sorted(x.name for x in p.glob("*.json"))
    return len(names), names


# ── r101 第二面：件内 NA（按位置数），补「按文件位置判 degraded」的口径缺口 ──────────────
# 立因（r100 §2.5 登记、r101 落地）：上面那条 degraded 只在文件被**挪进 `_partial/`** 时计数，
# 所以「龄 0 天但取数不全」的件在它眼里是新鲜基线 ⇒ **按日期新鲜 ≠ 按取数完整**。
# 一手实测（本轮）：`peer-memory-2026-10-08.json` 顶层声明 `usable=17 blind=0 denominator=17
# na=[]`，而件内 `repos[*].edge[*]` 有 5 处 `"NA(` ⇒ 声明与内容分叉，而对标报告 peers 列就从这里取数。
DECL_KEYS = ("blind", "na", "unverified")     # 顶层**声明位**；数内容时排除它们，否则把声明本身再数一遍
NA_PREFIXES = ("NA", "NA(")                  # 只认这两个哨兵；`"n/a"`（不适用）不算"没取到"


def _leaf_na(node, top_level):
    """递归数出非声明位里带 NA 哨兵的叶子串个数。键大小写敏感，值按 strip 后前缀匹配。"""
    n = 0
    if isinstance(node, dict):
        for k, v in node.items():
            if top_level and k in DECL_KEYS:
                continue
            n += _leaf_na(v, False)
    elif isinstance(node, list):
        for v in node:
            n += _leaf_na(v, False)
    elif isinstance(node, str):
        s = node.strip()
        if s == "NA" or s.startswith("NA("):
            n += 1
    return n


def declared_na(d):
    """顶层声明的 NA 数 → (int or None, 形状名)。

    形状**按键形自动识别**，不写「族→形状」硬表：本仓实测五类 schema 且不统一
    （A usable/blind/denominator、A′ blind 是 list、B unverified 且无 ts、C rows+na、
    D counted/peers_expected 无 denominator）。硬表第一次新增族就漏，漏了就静默当"完整"。
    认不出 ⇒ 返回 None，由调用方判 `NA-UNKNOWN`（未知不等于零）。"""
    if "blind" in d and "usable" in d and "denominator" in d:
        b = d.get("blind")
        return (b if isinstance(b, int) and not isinstance(b, bool) else len(b or [])), "A"
    if "unverified" in d:
        return len(d.get("unverified") or []), "B"
    if "na" in d:
        return len(d.get("na") or []), "C"
    if "counted" in d and "peers_expected" in d:
        return max(0, int(d.get("peers_expected") or 0) - int(d.get("counted") or 0)), "D"
    return None, "unknown"


def na_census(d):
    """单份台账 → (状态, 声明数, 件内数, 形状)。四态 CLEAR/DECLARED/DIVERGE/UNKNOWN。"""
    if not isinstance(d, dict):
        return "NA-UNKNOWN", None, None, "not-a-dict"
    dec, kind = declared_na(d)
    if dec is None:
        return "NA-UNKNOWN", None, None, kind
    found = _leaf_na(d, True)
    if found > dec:
        return "NA-DIVERGE", dec, found, kind
    if found == 0 and dec == 0:
        return "NA-CLEAR", dec, found, kind
    return "NA-DECLARED", dec, found, kind


NA_DIVERGE_WAIVED = {
    # 豁免必须**机器可读 + 带到期条件**（在册反例：注释式豁免等于没人认领的余量）。
    "peer-memory": {
        "reason": "探针把字段级 NA 只写进 repos[*].edge，不进 blind/na 声明 ⇒ 声明 blind=0 "
                  "与件内 5 处 NA 分叉（r101 一手实测）",
        "expiry": "peer_memory_probe.py 把字段级 NA 计入声明位 + 下一次错峰真采两件同时成立",
        "entered": "2026-10-09"},
}


def na_rollup(census, waived=None):
    """汇总 (分叉族, 未知族, 红因列表)。豁免只压**已登记且确在分叉里**的族：
      · 豁免名单里有而现读没分叉 ⇒ 死豁免判红（在册规矩：声明式名册要双向差集）；
      · 现读分叉而名单没有 ⇒ 判红并点名。
    返回 (diverge_unwaived, unknown, reds, waived_hits)。"""
    waived = NA_DIVERGE_WAIVED if waived is None else waived
    diverge = sorted(f for f, (st, _d, _f, _k) in census.items() if st == "NA-DIVERGE")
    unknown = sorted(f for f, (st, _d, _f, _k) in census.items() if st == "NA-UNKNOWN")
    hits = sorted(f for f in diverge if f in waived)
    reds = ["件内 NA 与声明分叉且未豁免 %d 族：%s"
            % (len([f for f in diverge if f not in waived]),
               "、".join("%s(声明%s/件内%s)" % (f, census[f][1], census[f][2])
                         for f in diverge if f not in waived)) or "无"] \
        if [f for f in diverge if f not in waived] else []
    stale = sorted(f for f in waived if f not in diverge)
    if stale:
        reds.append("豁免名单里的死项 %d 条（现读没分叉却还挂着 ⇒ 下次真分叉会被它吞掉）：%s"
                    % (len(stale), "、".join(stale)))
    return [f for f in diverge if f not in waived], unknown, reds, hits


def selftest():
    cases = []

    def eq(label, got, want):
        cases.append((label, got, want))

    T = date(2026, 10, 5)

    # 正例腿（只有正例能抓「尺恒假」）
    eq("文件名尾部日期取得对", parse_named_date("peer-a11y-2026-09-27.json"), date(2026, 9, 27))
    eq("点分隔的日期段也认（benchmark-metrics-r95.2026-10-04.json）",
       parse_named_date("benchmark-metrics-r95.2026-10-04.json"), date(2026, 10, 4))
    eq("族名剥离日期段与连分隔符", stem_of("peer-quality-tooling-2026-10-03.json"),
       "peer-quality-tooling")
    eq("族名不剥中间的 r 号段", stem_of("benchmark-metrics-r95.2026-10-04.json"),
       "benchmark-metrics-r95")
    eq("ISO 带 Z 的时间戳能落成日期", parse_iso_ts("2026-10-05T02:11:09Z"), date(2026, 10, 5))
    eq("fuse 从本仓契约真读出来（是个 int，不是抄的）",
       isinstance(read_fuse(str(ROOT))[0], int), True)
    eq("显式覆盖生效：--fuse-days 3 ⇒ 3", resolve_fuse(3, str(ROOT))[0], 3)
    eq("边界 --fuse-days 0 是合法覆盖值，不得被当没传而回落契约的 7（第一版实测踩过）",
       resolve_fuse(0, str(ROOT))[0], 0)
    eq("没传覆盖 ⇒ 走契约（两分支各只干自己的事）",
       resolve_fuse(None, str(ROOT))[1][:3], "读自 ")
    # 同族两版 + 一族单版：聚合、最新择取、龄期三件事必须在一条正例里同时成立
    fam2 = [("peer-repro-2026-09-27.json", date(2026, 9, 27), "文件名", 100.0),
            ("peer-repro-2026-10-03.json", date(2026, 10, 3), "文件名", 200.0)]
    r2 = evaluate(fam2, 7, T)
    eq("同族两文件聚成一行（不是一文件一行）", r2["files"], 2)
    eq("族名取自成员", r2["stem"], "peer-repro")
    eq("最新一份按文件名日期取", r2["newest"], "peer-repro-2026-10-03.json")
    eq("龄期按最新一份算（旧那份不拖累）", r2["age_days"], 2)
    eq("mtime 最新与文件名最新一致 ⇒ 不写分歧列", "divergence" in r2, False)
    r3 = evaluate([("peer-a11y-2026-09-27.json", date(2026, 9, 27), "文件名", 50.0)], 7, T)
    eq("8 天 > fuse 7 ⇒ 超龄点名（这就是把 12 族抓出来的那一挡）", r3["state"], "OVER-FUSE")

    # 变异腿（把解析器/判据摘掉后读数必须变，证明这条闸在咬而不是恒真）
    keep = TRAIL_DATE_RE
    globals()["TRAIL_DATE_RE"] = re.compile(r"[-.](9999)-(99)-(99)(?=\.json$)")
    eq("变异体 摘掉日期正则 ⇒ None 而不是造一个假日期（不可解析必须显式失败）",
       parse_named_date("peer-a11y-2026-09-27.json"), None)
    eq("变异体 摘掉正则后族名也不剥日期（证明族名与日期共用同一条尺）",
       stem_of("peer-a11y-2026-09-27.json"), "peer-a11y-2026-09-27")
    globals()["TRAIL_DATE_RE"] = keep
    eq("还原后重新取到日期（证明上面动的是尺、不是期望值）",
       parse_named_date("peer-a11y-2026-09-27.json"), date(2026, 9, 27))
    eq("变异体 非法日期 2026-13-45 ⇒ None（不得回落到 1 月 1 日）",
       parse_named_date("peer-x-2026-13-45.json"), None)
    eq("变异体 非日期串 ⇒ None（不得读成 0 龄）", parse_iso_ts("not-a-date"), None)
    # 把 mtime 换成与文件名不同的那份 ⇒ 分歧列必须出现（否则交叉腿是恒假的）
    div = evaluate([("peer-x-2026-09-27.json", date(2026, 9, 27), "文件名", 1.0),
                    ("peer-x-2026-09-26.json", date(2026, 9, 26), "文件名", 999.0)], 7, T)
    eq("交叉腿真在作用：mtime 指向旧版 ⇒ 必须记分歧", div.get("divergence", "")[:9],
       "mtime 最新=peer-x-2026-09-26.json"[:9])
    eq("交叉腿的另一半：文件名最新仍优先当权威（不跟着 mtime 走）",
       div["newest"], "peer-x-2026-09-27.json")
    # r96 CI 一手：全新 clone 下全族 mtime 同值 ⇒ 交叉腿无区分度，只能降为"未验"，
    # 且**只降这一条**（龄期照判红）。下面两条腿一正一反，缺任一条这个降档就等于关门禁。
    uni = evaluate([("peer-u-2026-09-27.json", date(2026, 9, 27), "文件名", 777.0),
                    ("peer-u-2026-09-26.json", date(2026, 9, 26), "文件名", 777.0)], 7, T)
    eq("mtime 全族同值 ⇒ 本腿降未验且不写 divergence（不凭 checkout 产物判红）",
       "divergence" in uni, False)
    eq("降档只降这一条：同值时超 fuse 照样判 OVER-FUSE", uni["state"], "OVER-FUSE")
    eq("反例：mtime 有区分度时同输入必须仍判分歧（证明降档不是大赦）",
       "divergence" in div, True)

    # 边界腿
    eq("边界 无日期可判 ⇒ UNDATEd 且 age 为 None（不得写成 0 天）",
       evaluate([("peer-y.json", None, "无候选时间戳键", 1.0)], 7, T)["age_days"], None)
    eq("边界 龄恰等 fuse ⇒ 按严格 > 判线内（阈值语义=7 天内重采算新鲜）",
       evaluate([("peer-z-2026-09-28.json", date(2026, 9, 28), "文件名", 1.0)], 7, T)["state"],
       "WITHIN")
    eq("边界 龄 fuse+1 ⇒ 超", (T - date(2026, 9, 27)).days > 7, True)
    eq("边界 日期在未来 ⇒ 龄为负数，按 > fuse 判线内（不假装它是 0）",
       (T - date(2026, 10, 9)).days > 7, False)
    eq("边界 契约不在 ⇒ None 且带原因（绝不回落成 7 或 0）",
       read_fuse(str(ROOT / "_no_such_dir_"))[0], None)
    n_par, names = count_partials(ROOT / DEFAULT_DIR)
    eq("degraded 台账被单独计数（个数与现读列名一致，不是硬编码）",
       n_par == len(names), True)
    eq("排除面不得与「没有这个目录」同形：目录不在 ⇒ 0 且不报错",
       count_partials(ROOT / "_no_such_dir_")[0], 0)

    # ── r101 件内 NA 面（四态 + 豁免语义 + 形状自动识别，正反双向） ──
    eq("NA 四态 干净件（声明 0 且件内无 NA）⇒ CLEAR",
       na_census({"usable": 2, "blind": 0, "denominator": 2})[0], "NA-CLEAR")
    eq("NA 四态 声明 5 条且都在声明位里 ⇒ DECLARED（声明位不得再数第二遍）",
       na_census({"usable": 11, "blind": 5, "denominator": 16,
                  "na": ["A(http=403 NA)", "B NA(x)", "C NA", "D NA", "E NA"]}),
       ("NA-DECLARED", 5, 0, "A"))
    eq("NA 四态 blind 是 list 的 A′ 形状也认（len 作声明数）",
       na_census({"usable": 1, "blind": ["X NA("], "denominator": 2})[1], 1)
    eq("NA 四态 声明 0 而件内 5 处 ⇒ DIVERGE（peer-memory 的一手形状）",
       na_census({"usable": 17, "blind": 0, "denominator": 17,
                  "repos": {str(i): {"edge": ["NA(nothing)"]} for i in range(5)}}),
       ("NA-DIVERGE", 0, 5, "A"))
    eq("NA 四态 键形认不出 ⇒ UNKNOWN（未知绝不读成「取数完整」）",
       na_census({"something_else": 1})[0], "NA-UNKNOWN")
    eq("NA 四态 件不是 dict ⇒ UNKNOWN 而不是 0 处",
       na_census(["not", "a", "dict"])[0], "NA-UNKNOWN")
    eq("哨兵口径 \"n/a\"（不适用）不得算「没取到」⇒ 仍 CLEAR",
       na_census({"usable": 1, "blind": 0, "denominator": 1,
                  "self": {"note": "n/a", "path": "a/n/a/b"}})[0], "NA-CLEAR")
    _c_1 = {"peer-mem": ("NA-DIVERGE", 0, 5, "A")}
    eq("豁免语义① 名单清空 ⇒ 分叉必须回到红名单（证明豁免不是装饰）",
       na_rollup(_c_1, waived={})[0], ["peer-mem"])
    eq("豁免语义② 登记且确在分叉 ⇒ 压住判红但 hits 照点（不折成「没分叉」）",
       na_rollup(_c_1, waived={"peer-mem": {"expiry": "x"}})[3], ["peer-mem"])
    _r3 = na_rollup(_c_1, waived={"other-family": {"expiry": "x"}})
    eq("豁免语义③ 名单挂在不分叉的族上 ⇒ 该族的分叉照判红（豁免不跨族生效）", _r3[0], ["peer-mem"])
    eq("豁免语义④ 死项必须出声（现读没分叉却挂着 ⇒ 下次真分叉会被它吞）",
       any("死项" in x for x in _r3[2]), True)
    _real = {}
    for _p in sorted((ROOT / DEFAULT_DIR).glob("peer-*-*.json")):
        try:
            _real[_p.name.split("-2026")[0]] = na_census(json.loads(_p.read_text(encoding="utf-8")))
        except Exception:                                      # noqa: BLE001
            continue
    eq("真面自证 在册豁免的每一项当前确实分叉（probe 修好后这条转红 ⇒ 提醒摘牌）",
       sorted(k for k in NA_DIVERGE_WAIVED if _real.get(k, ("",))[0] != "NA-DIVERGE"), [])

    bad = [(n, g, w) for n, g, w in cases if g != w]
    for n, g, w in bad:
        print("  用例不符: %s ｜ got=%r want=%r" % (n, g, w))
    print("LEDGER-AGE-SELFTEST-%s（%d/%d 条）"
          % ("PASS" if not bad else "FAIL", len(cases) - len(bad), len(cases)))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=DEFAULT_DIR)
    ap.add_argument("--pattern", default=DEFAULT_PATTERN)
    ap.add_argument("--fuse-from", default=CONTRACT)
    ap.add_argument("--fuse-days", type=int, default=None,
                    help="演习用显式覆盖阈值（不改契约本体）")
    ap.add_argument("--only", default="", help="只保留族名含此子串的族")
    ap.add_argument("--json", default="")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()

    fuse, fuse_why = resolve_fuse(a.fuse_days, ROOT, a.fuse_from)
    if fuse is None:
        print("LEDGER-AGE-UNVERIFIED: fuse 取不到（%s）⇒ 不判绿，先修取数面" % fuse_why)
        return 2

    d = Path(a.dir)
    if not d.is_dir():
        print("LEDGER-AGE-UNVERIFIED: 目录不存在(%s)" % a.dir)
        return 2
    today = datetime.now().astimezone().date()
    rows = scan(d, a.pattern, fuse, today)
    if a.only:
        rows = [r for r in rows if a.only in r["stem"]]
    if not rows:
        print("LEDGER-AGE-UNVERIFIED: %s 在 %s 下无可判台账（取数面为空 ≠ 没有超龄）"
              % (a.pattern, a.dir))
        return 2

    within = [r for r in rows if r["state"] == "WITHIN"]
    over = [r for r in rows if r["state"] == "OVER-FUSE"]
    und = [r for r in rows if r["state"] == "UNDATEd"]
    div = [r for r in rows if r.get("divergence")]
    div_unv = [r for r in rows if r.get("divergence_unverified")]
    for r in rows:
        print("%-26s 龄=%-6s 状态=%-10s 版本数=%-3s 最新=%s%s%s"
              % (r["stem"],
                 ("%d天" % r["age_days"]) if r["age_days"] is not None else "-",
                 r["state"], r["files"], r["newest"] or "-",
                 ("  ⚠" + r["divergence"]) if r.get("divergence") else "",
                 ("  ℹ" + r["divergence_unverified"]) if r.get("divergence_unverified") else ""))
    identity_ok = len(within) + len(over) + len(und) == len(rows)
    # r101 第二面：逐族读**最新那一份**的内容，数件内 NA 位置并与顶层声明对账。
    census, census_unread = {}, []
    for r in rows:
        if not r.get("newest"):
            census[r["stem"]] = ("NA-UNKNOWN", None, None, "无最新件可判")
            continue
        p = Path(d) / r["newest"]
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:                                  # noqa: BLE001
            census_unread.append("%s(%s)" % (r["stem"], type(e).__name__))
            census[r["stem"]] = ("NA-UNKNOWN", None, None, "件不可解析")
            continue
        census[r["stem"]] = na_census(data)
    na_div, na_unknown, na_reds, na_waived = na_rollup(census)
    na_counts = {}
    for _f, (st, _de, _fo, _k) in census.items():
        na_counts[st] = na_counts.get(st, 0) + 1
    n_par, par_names = count_partials(d)
    print("-" * 104)
    print("fuse=%d天(%s) 取数=%s 基准日=%s｜族 %d 个：线内 %d｜超 fuse %d｜无日期可判 %d｜"
          "恒等式 %d+%d+%d==%d：%s｜mtime⇄文件名分歧 %d（另有 %d 族本腿未验）｜已排除 degraded 台账 %d 份"
          % (fuse, fuse_why, a.pattern, today, len(rows), len(within), len(over), len(und),
             len(within), len(over), len(und), len(rows),
             "成立" if identity_ok else "不成立", len(div), len(div_unv), n_par))
    if n_par:
        print("  ⚠ degraded（取数不全，按「坏一半不算重采」挪入 %s/，不得当基线用；重采前提=%s）: %s"
              % (PARTIAL_DIRNAME, "python _test/<probe>.py --json …（错峰单跑，勿 burst）",
                 "; ".join(par_names)))
    if over:
        print("  超 fuse（报告的「现测」不得把这些读数当本轮实测引用）: "
              + "; ".join("%s(%d天)" % (r["stem"], r["age_days"]) for r in over))
    if und:
        print("  无日期可判（不得读成「没有超龄」）: " + "; ".join(r["stem"] for r in und))
    print("  件内 NA 四态：%s（读件 %d 份，不可解析 %d）"
          % ("｜".join("%s=%d" % kv for kv in sorted(na_counts.items())) or "无",
             len(census), len(census_unread)))
    if na_waived:
        print("  ⚠ 分叉已豁免（名单机器可读、带 expiry，现读仍**照点数**不折零）：%s"
              % "; ".join("%s[声明%s/件内%s] expiry=%s"
                          % (f, census[f][1], census[f][2], NA_DIVERGE_WAIVED[f]["expiry"])
                          for f in na_waived))
    if na_unknown:
        print("  NA-UNKNOWN（形状认不出或件读不动 ⇒ 整尺判未验，绝不读成「取数完整」）: "
              + "; ".join("%s[%s]" % (f, census[f][3]) for f in na_unknown))
    if a.json:
        Path(a.json).write_bytes(json.dumps(
            {"today": str(today), "fuse_days": fuse, "fuse_source": fuse_why,
             "dir": str(a.dir), "pattern": a.pattern, "identity_ok": identity_ok,
             "excluded_partial": {"count": n_par, "files": par_names, "dirname": PARTIAL_DIRNAME},
             "counts": {"within": len(within), "over_fuse": len(over), "undated": len(und),
                        "divergence": len(div), "divergence_unverified": len(div_unv),
                        "na_by_state": na_counts, "na_diverge": na_div,
                        "na_diverge_waived": na_waived, "na_unknown": na_unknown,
                        "na_unreadable": census_unread,
                        "total": len(rows)},
             "na_census": {f: list(v) for f, v in sorted(census.items())},
             "rows": rows}, ensure_ascii=False, indent=1).encode("utf-8"))
        print("落盘 %s" % a.json)
    red = bool(over) or bool(und) or bool(div) or not identity_ok or bool(na_div) or bool(na_reds)
    if red:
        for x in na_reds:
            print("  红因=" + x)
        print("LEDGER-AGE-FAIL（peer 台账 %d 族：≤fuse %d｜超 fuse %d｜无日期可判 %d｜分歧 %d｜"
              "NA分叉=%d(waived %d)｜恒等式 %s）"
              % (len(rows), len(within), len(over), len(und), len(div), len(na_div) + len(na_waived),
                 len(na_waived), "成立" if identity_ok else "不成立"))
        return 1
    if na_unknown:
        print("LEDGER-AGE-UNVERIFIED（龄期面全绿，但件内 NA 有 %d 族认不出形状/读不动 ⇒ "
              "整尺不得记 PASS，也不得记成 0 分叉）" % len(na_unknown))
        return 2
    print("LEDGER-AGE-PASS（peer 台账 %d 族：≤fuse %d｜超 fuse %d｜无日期可判 %d｜分歧 %d｜"
          "NA分叉=%d(waived %d)｜恒等式 %s）"
          % (len(rows), len(within), len(over), len(und), len(div), len(na_div), len(na_waived),
             "成立" if identity_ok else "不成立"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
