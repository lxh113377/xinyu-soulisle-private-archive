# -*- coding: utf-8 -*-
"""ledger_shape_check.py — 台账「NA 声明义务」的**全目录**普查（r126 立，对标改造二）

为什么现有的龄期尺不够：`ledger_age_check.py` 默认只扫 `peer-*.json`（18 族），而
`交付物/对标数据/` 里实有 **53 个 json 族**（eight-dims / perf-ramp×12 / benchmark-metrics /
battery-timing / timing-coupling …）。r122 我用一个自造键名 `blind_or_na` 把龄期尺整尺打成未验，
靠的正是"那族恰好在它扫的面里"——**不在它扫的面里的 35 族，同一个错犯上去没人会红**。
这就是「把现成的尺换到没人量的那一半」：本件不新造形状语法，**复用同一把尺的词汇**
（`ledger_age_check.declared_na` / `_leaf_na`），只把取数面换成全目录，并补一条义务判据：

  · 件内有 NA 痕迹（叶子命中 `NA(`/blind/na/unverified…）却没有顶层声明位 ⇒ **UNDECLARED-BLIND**（红）；
  · 件内既无声明位也无 NA 痕迹 ⇒ **ABSENT**（无义务，只点数，不判红）
    —— 这条分档是必须的：不分就会造出一条**永远绿不了**的尺（53 族里 35 族本就没有 NA 语义）。
  · 声明数 < 件内数 ⇒ **DIVERGE**（红，与龄期尺同一口径，不另立第二把尺）。

落点选择：本件是**报告型看守**（advisory 的判据本体，但红项照 rc=1 阻断电池），
它不替代龄期尺，也不替代 G8/G4——同一事实只在各自的尺上判一次：
龄期尺判"新不新"，本件判"形状认不认得、有没有如实声明"。

r127-S5 增第五条腿「族名归一撞名」（一手：我把探针输出写成 `peer_memory-2026-10-12.json`，
而族名是 `peer-memory`）：写错分隔符会长出一个**新族**（内容合法 ⇒ 分类落在 ABSENT，不红），
真族则停在旧样本上，而旧样本在 fuse 内 ⇒ 龄期尺照绿 ⇒ **改名＝台账静默过期且两把尺都不报**。
判据：族名把连字符/下划线/大小写归一后同键 ⇒ 必有一个拼法是错的，红并同时点名两种拼法。
`.partial` 后缀**不**参与归一：它是同一族的降级态，盘上确与正族并存（归一了会造出假的永红）。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "交付物" / "对标数据"
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ledger_age_check as LA          # noqa: E402  词汇唯一权威在尺子侧，本件不复制形状表

RED_STATES = ("UNDECLARED-BLIND", "DIVERGE", "UNREADABLE")


def classify(dec, found):
    """纯函数：(声明数|None, 件内 NA 数) → 状态串。"""
    if dec is None:
        return "UNDECLARED-BLIND" if found > 0 else "ABSENT"
    if found > dec:
        return "DIVERGE"
    if found == 0 and dec == 0:
        return "CLEAR"
    return "DECLARED"


def stem_key(stem):
    """族名归一：连字符/下划线/大小写差异视为同一族（r127-S5 一手事故＝ peer-memory 写成 peer_memory）。
    `.partial` 一律**不**剥：它是同一族的降级态且盘上确与正族并存，剥了会造出假的永红判据。"""
    return re.sub(r"[-_]", "", stem).lower()


def near_dup_groups(stems):
    """纯函数：族名列表 → 归一后撞名的组 [(key, [stems…])]（>1 个拼法才算）。
    同一族被两种拼法写开的后果是"真族静默过期、假族没人读"——两把现成的尺都不会红。"""
    g = {}
    for s in stems:
        g.setdefault(stem_key(s), []).append(s)
    return sorted((k, sorted(v)) for k, v in g.items() if len(v) > 1)


def census(dir_path, pattern="*.json"):
    """IO 腿：全目录 → 逐族最新件 → 状态。取件规则**委托 LA.scan(pattern)**，
    与龄期尺同一个「文件名日期优先、缺日期回落件内 ts」的选法，避免两把尺挑到不同份。
    分母只数 `*.json`：目录里还有 `.log/.rc/.md` 等伴生件，它们没有声明义务，
    混进来会把"我扫错了面"报成"104 族读不动"（本轮实测踩过一次）。"""
    fuse = LA.resolve_fuse(None, ROOT)[0]
    rows = LA.scan(dir_path, pattern, fuse, date.today())
    out = []
    for r in rows:
        stem = r["stem"]
        # 无文件名日期的族（如 benchmark-rollup-r93.json）在龄期尺那边进「无日期可判」桶，
        # 但**形状义务照判**：这里回落 mtime 最新件，不因为"没日期"就跳过形状检查。
        newest = r.get("newest") or r.get("latest_by_mtime")
        if not newest:
            out.append((stem, "UNREADABLE", 0, 0, "一族里定位不到任何成员件（%s）" % r.get("why", "")))
            continue
        try:
            d = json.loads((dir_path / newest).read_text("utf-8"))
        except (OSError, ValueError) as e:
            out.append((stem, "UNREADABLE", 0, 0, "%s: 最新件读不动(%s)" % (newest, type(e).__name__)))
            continue
        if not isinstance(d, dict):
            out.append((stem, "UNREADABLE", 0, 0, "%s: 顶层不是对象（%s）" % (newest, type(d).__name__)))
            continue
        dec, kind = LA.declared_na(d)
        found = LA._leaf_na(d, True)
        st = classify(dec, found)
        out.append((stem, st, dec if dec is not None else 0, found,
                    "%s shape=%s" % (newest, kind)))
    return out


def selftest():
    bad = []
    # ①-⑥ 分类腿（含 r122 那颗雷的形状）
    cases = [("DECLARED", (5, 5)), ("CLEAR", (0, 0)), ("DIVERGE", (0, 7)),
             ("UNDECLARED-BLIND", (None, 7)), ("ABSENT", (None, 0))]
    for want, (dec, found) in cases:
        if classify(dec, found) != want:
            bad.append("①分类失效 classify(%s,%s)=%s 应为 %s" % (dec, found, classify(dec, found), want))
    if classify(None, 0) != "ABSENT":
        bad.append("②无义务被误判成盲区 ⇒ 这条尺会永远绿不了")
    # 形状词汇腿：真尺认得四种，自造键名必须认不出（认得出就是本件在替违规背书）
    known = [({"blind": 5, "usable": 12, "denominator": 17}, 5, "A"),
             ({"blind": [{"repo": "x"}], "usable": 12, "denominator": 17}, 1, "A"),
             ({"unverified": ["a", "b"]}, 2, "B"),
             ({"rows": [{"repo": "r", "na": ["NA(x)"]}], "na": ["NA(y)"]}, 1, "C"),
             ({"peers_expected": 16, "counted": 14}, 2, "D")]
    for i, (d, want_n, want_k) in enumerate(known):
        got = LA.declared_na(d)
        if got[0] != want_n or got[1] != want_k:
            bad.append("③第 %d 种在册形状读数不符（应 %s/%s，实得 %s/%s）⇒ 词汇表被改动过，"
                       "本件的分类前提失效" % (i + 1, want_n, want_k, got[0], got[1]))
    mine = {"rows": [{"repo": "r", "na": ["NA(x)"]}], "blind_or_na": ["NA(x)"]}
    dec, _kind = LA.declared_na(mine)
    found = LA._leaf_na(mine, True)
    if dec is not None:
        bad.append("④变异体失效：自造键 `blind_or_na` 仍被认成合法声明 ⇒ r122 那颗雷没被钉住")
    if classify(dec, found) != "UNDECLARED-BLIND":
        bad.append("⑤r122 形状没被本尺点名（dec=%s found=%s 应判盲区）" % (dec, found))
    # 生产者契约腿：peer_docs 的 build_payload 是真产物，形状必须被尺认得
    try:
        import peer_docs_probe as PD
        payload = PD.build_payload([{"repo": "self（x）", "class": "4/4", "api_spec": 1},
                                    {"repo": "a/b", "class": "2/4", "na": ["NA(truncated-tree)"]}],
                                   ["NA(truncated-tree)"])
        if LA.declared_na(payload)[0] is None:
            bad.append("⑥生产者契约失效：peer_docs_probe 真产物的形状不被龄期尺认得")
        _dec, _f = LA.declared_na(payload)[0], LA._leaf_na(payload, True)
        if classify(_dec, _f) not in ("CLEAR", "DECLARED"):
            bad.append("⑥b 真产物按本尺应判有义务且不分叉，实得 %s（声明 %s／件内 %s）"
                       % (classify(_dec, _f), _dec, _f))
        mutant = dict(payload)
        mutant["blind_or_na"] = mutant.pop("na")
        if LA.declared_na(mutant)[0] is not None or classify(None, 1) != "UNDECLARED-BLIND":
            bad.append("⑦变异腿失效：把 `na` 换成 `blind_or_na` 后本尺竟照认/照绿")
    except Exception as e:
        bad.append("⑧契约腿没跑成（%s）⇒ 不得当成已验" % type(e).__name__)
    # ⑨-⑫ 族名归一撞名（r127-S5 一手事故的形状：peer-memory 被写成 peer_memory）
    # ⚠️ 夹具喂的必须是 **stem**（族名，去掉日期尾）——真面 census 交上来的就是 stem；
    # 首版我喂了整文件名（带 -2026-10-08），日期数字各异 ⇒ 归一后不同键 ⇒ 三条腿全假绿，
    # 靠端到端演习（临时目录真注入文件）当场对上才暴露。夹具形状必须等于真面形状。
    if near_dup_groups(["peer-memory", "peer-docs"]) != []:
        bad.append("⑨正例面失效：两个不同族的干净名单竟被判撞名")
    got = near_dup_groups(["peer-memory", "peer_memory"])
    if len(got) != 1 or got[0][1] != ["peer-memory", "peer_memory"]:
        bad.append("⑩反例失效：连字符⇄下划线的同族没被抓到（实得 %s）" % got)
    if near_dup_groups(["benchmark-metrics", "benchmark-metrics-r93", "benchmark-metrics.partial"]):
        bad.append("⑪边界失效：轮次后缀与 .partial 被误并成撞名（会在真面上造出假的永红判据）")
    if len(near_dup_groups(["Peer-Memory", "peer-memory"])) != 1:
        bad.append("⑫大小写腿失效：仅大小写不同的同族没被抓到")
    print("SELFTEST-%s（%d 类分类桩 + 在册形状词汇 5 桩 + 生产者契约与变异腿 + 撞名 4 腿）"
          % ("PASS" if not bad else "FAIL: " + "; ".join(bad), len(cases) + 2))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=str(DATA))
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    d = Path(a.dir)
    if not d.is_dir():
        print("LEDGER-SHAPE-UNVERIFIED: 取数目录取不到（%s）⇒ 不得读成「形状都合规」" % d)
        return 2
    rows = census(d)
    if not rows:
        print("LEDGER-SHAPE-UNVERIFIED: 目录里一份台账 json 都没扫到 ⇒ 空面不判绿")
        return 2
    counts = {}
    for _s, st, _dec, _f, _w in rows:
        counts[st] = counts.get(st, 0) + 1
    dups = near_dup_groups([r[0] for r in rows])
    red = [(s, st, dec, f, why) for s, st, dec, f, why in rows if st in RED_STATES]
    red += [(v[0], "NEAR-DUP", 0, 0,
             "族名归一后撞名：%s（两种拼法必有一错；后果＝真族静默过期而假族没人读）" % " / ".join(v))
            for _k, v in dups]
    if a.json:
        Path(a.json).write_bytes(json.dumps(
            {"generated_by": "_test/ledger_shape_check.py", "dir": str(d),
             "families": len(rows), "counts": counts, "near_dup": [list(v) for _k, v in dups],
             "red": [{"stem": s, "state": st, "declared": dec, "found": f, "why": w}
                     for s, st, dec, f, w in red]}, ensure_ascii=False, indent=1).encode("utf-8") + b"\n")
    line = ("LEDGER-SHAPE-%s 族 %d｜有义务 %d(CLEAR %d＋DECLARED %d＋DIVERGE %d)｜"
            "无义务 ABSENT %d｜盲区 %d｜读不动 %d｜撞名 %d 组"
            % ("FAIL" if red else "PASS", len(rows),
               counts.get("CLEAR", 0) + counts.get("DECLARED", 0) + counts.get("DIVERGE", 0),
               counts.get("CLEAR", 0), counts.get("DECLARED", 0), counts.get("DIVERGE", 0),
               counts.get("ABSENT", 0), counts.get("UNDECLARED-BLIND", 0),
               counts.get("UNREADABLE", 0), len(dups)))
    if red:
        for s, st, dec, f, why in red[:10]:
            print("- 红-" + st + ": " + "%s 声明 %s／件内 %d｜%s" % (s, dec, f, why))
    print(line)
    return 1 if red else 0


if __name__ == "__main__":
    sys.exit(main())
