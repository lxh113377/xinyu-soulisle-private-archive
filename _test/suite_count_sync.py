# -*- coding: utf-8 -*-
"""suite_count_sync.py — 把 README 的电池套件数改到与代码现读值一致（幂等；判据仍只在 G4 一处）

为什么要有它：`全量电池（N 套件）` 这行数字已经**因手抄过期两次**——r117 一次（150→152），
r123 我写下 157、随后被他人提交 `f9c7ee6` 加两条套件顶成过期（现读 159）。G4 只能报"不一致"，
改文档这一步没有工具，就只有第三次。本件把"改那一行"变成一条命令，**不新增第二把尺**：
分母复用 `repo_config_check.battery_count()`，门禁也仍由 G4 独家判（本件的 --check 只是报告）。

口径纪律（照 r123 立的规）：
  · 取数面＝工作树（`_test/run_all_suites.py` 的实际内容），与 G4 的工作树腿同面；
  · 字节级改写：只在**恰好一处**匹配时替换那一段，替换后先断言"剥掉匹配段的两侧字节逐字相同"，
    越界即拒绝落盘（防把整行/整段吞掉——同族事故已第十几种形态）；
  · 行尾一个字节都不动（不 read_text/write_text，直接按 bytes 处理，避开 EOL-PARITY 那 48 项旧账）。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
PAT = re.compile(("全量电池（(\\d+) 套件）").encode("utf-8"))


def battery_count():
    """分母从代码现读，复用 G4 的同一个解析器；取不到一律 None（禁 0 顶替）。"""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import repo_config_check as RC
        return RC.battery_count()
    except Exception:
        return None


def sync_bytes(raw, want):
    """纯函数：(原文字节, 目标条数) → (新字节, 结论)。结论只有 aligned/changed/unverified 三态。"""
    if want is None:
        return raw, "unverified(count=None)"
    hits = PAT.findall(raw)
    if len(hits) != 1:
        return raw, "unverified(match=%d)" % len(hits)
    cur = int(hits[0])
    if cur == int(want):
        return raw, "aligned"
    new = PAT.sub(("全量电池（%d 套件）" % int(want)).encode("utf-8"), raw, count=1)
    if PAT.sub(b"<#>", raw, 1) != PAT.sub(b"<#>", new, 1):
        return raw, "unverified(改动越界)"
    return new, "changed(%d->%d)" % (cur, int(want))


def selftest():
    bad = []
    good = "前文\n全量电池（157 套件）＝ 判据清单\n后文\n".encode("utf-8")
    out, why = sync_bytes(good, 159)
    if why != "changed(157->159)" or "159" not in out.decode("utf-8"):
        bad.append("①不一致没被改对：%s" % why)
    out2, why2 = sync_bytes(out, 159)
    if why2 != "aligned" or out2 != out:
        bad.append("②幂等失效：再跑一次应 aligned 且字节不动（%s）" % why2)
    zero = "没有那行\n".encode("utf-8")
    o3, w3 = sync_bytes(zero, 159)
    if not w3.startswith("unverified(match=0)") or o3 != zero:
        bad.append("③匹配 0 处被当成「改 0 次」通过：%s" % w3)
    two = "全量电池（157 套件）\n全量电池（160 套件）\n".encode("utf-8")
    o4, w4 = sync_bytes(two, 159)
    if not w4.startswith("unverified(match=2)") or o4 != two:
        bad.append("④多处匹配没拒绝（会挑错行）：%s" % w4)
    o5, w5 = sync_bytes(good, None)
    if not w5.startswith("unverified(count=None)") or o5 != good:
        bad.append("⑤分母取不到被折成 0 顶替：%s" % w5)
    wide = "全量电池（157 套件）与全量电池（157 套件）混排\n".encode("utf-8")
    o6, w6 = sync_bytes(wide, 159)
    if not w6.startswith("unverified(match=2)"):
        bad.append("⑥同行两处也须拒：%s" % w6)
    raw = README.read_bytes() if README.exists() else b""
    if raw:
        o7, w7 = sync_bytes(raw, battery_count())
        if w7.startswith("unverified"):
            bad.append("⑦真 README 应可判（现报 %s）⇒ 声称行形状或分母取数变了" % w7)
        else:
            import hashlib
            a = PAT.sub(b"<#>", raw, 1)
            b = PAT.sub(b"<#>", o7, 1)
            if a != b:
                bad.append("⑧越界：非数字部分字节被改（sha %s vs %s）"
                           % (hashlib.sha256(a).hexdigest()[:8], hashlib.sha256(b).hexdigest()[:8]))
    print("SELFTEST-%s（%d 类改写桩 + 越界守卫 + 真 README 双腿）"
          % ("PASS" if not bad else "FAIL: " + "; ".join(bad), 6))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="改写那一行（默认只报告）")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    want = battery_count()
    if want is None:
        print("SUITE-COUNT-UNVERIFIED: 读不到电池 SUITES 条数 ⇒ 不得据此改文档，也不得据此判绿")
        return 2
    if not README.exists():
        print("SUITE-COUNT-UNVERIFIED: README.md 取不到")
        return 2
    raw = README.read_bytes()
    new, why = sync_bytes(raw, want)
    if why.startswith("unverified"):
        print("SUITE-COUNT-UNVERIFIED: %s（电池现读 %d 条）⇒ 不落笔，先修取数面" % (why, want))
        return 2
    if why == "aligned":
        print("SUITE-COUNT-PASS: README 声称 == 电池现读（%d 套件）｜门禁由 repo_config G4 独家判" % want)
        return 0
    if not a.apply:
        print("SUITE-COUNT-DRIFT: %s｜正解=python _test/suite_count_sync.py --apply（改完复跑 G4 确认）" % why)
        return 1
    README.write_bytes(new)
    back, why2 = sync_bytes(README.read_bytes(), want)
    if why2 != "aligned" or back != new:
        print("SUITE-COUNT-FAIL: 写完载回不是 aligned（%s）⇒ 落盘未确认，不得报成已修" % why2)
        return 1
    print("SUITE-COUNT-APPLIED: %s ⇒ 已落盘并载回确认（bytes=%d）｜记得复跑 repo_config G4" % (why, want))
    return 0


if __name__ == "__main__":
    sys.exit(main())
