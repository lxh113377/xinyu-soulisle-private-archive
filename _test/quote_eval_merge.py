# -*- coding: utf-8 -*-
"""quote_eval_merge.py — 分块跑批的明细合并 + 总读数重算（r134 立，r171 随量尺改版）

为什么需要：正式验收跑批在共享机器上会被并行会话的资源断言打断（r134 实测后台进程
被静默杀死 3 次），且单次命令有超时上限 ⇒ 60 例拆成若干前台块跑，每块各自
落一份明细。本件把多份明细的 rows 合并后交回 `quote_eval._judge_and_report` 重算
总读数——**不新写第二套汇总逻辑**（判据唯一来源仍是 quote_eval.py 本体；配对差值、
分层分母、效果门全在被调函数里算，本件只负责拼接 rows）。

r171 两条改版：① 明细文件名带 `--detail` 出口，**缺省不再写 r134/r171 的正式明细面**
（合并产物若覆盖被合并的输入面，下一次复算就是在读自己的输出）；② rows 的 stage 标签
原样透传（分层靠它），旧 r134 明细没有该字段 ⇒ 由 quote_eval 计入「无标签」并 WARN，
不静默当成承载面。

用法：
  python _test/quote_eval_merge.py _test/_shots/quotes_eval_detail_r171_c1.json \
      _test/_shots/quotes_eval_detail_r171_c2.json ... [--out 合并明细路径] \
      [--detail 汇总文件名.json]
退出码：与 quote_eval 同语义（0=效果门过 1=主对照效果门红 2=输入面缺失）
"""
import argparse
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "_test"))

DEFAULT_PARTS = ["_test/_shots/quotes_eval_detail_r134_c%d.json" % i for i in range(1, 7)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("parts", nargs="*", default=None, help="明细 JSON 路径（缺省用 r134 c1-c6）")
    ap.add_argument("--out", default=None, help="合并明细写出路径（缺省打屏幕）")
    ap.add_argument("--detail", default="quotes_eval_detail_merged.json",
                    help="交给 quote_eval 落盘的汇总文件名（落在 _test/_shots/，默认不顶替任何正式轮次明细）")
    args = ap.parse_args()
    parts = [Path(p) for p in (args.parts or DEFAULT_PARTS)]
    missing = [str(p) for p in parts if not p.exists()]
    if missing:
        print("QUOTE-EVAL-MERGE-UNVERIFIED: 缺明细 %s ⇒ 不判绿" % "、".join(missing))
        return 2

    rows, seen = [], set()
    for p in parts:
        d = json.loads(p.read_text(encoding="utf-8"))
        for r in d.get("rows", []):
            key = (r.get("i"), r.get("case"))
            if key in seen:
                continue          # 同一用例被多块覆盖（对照重跑）时只取第一份
            seen.add(key)
            rows.append(r)
    if not rows:
        print("QUOTE-EVAL-MERGE-UNVERIFIED: 合并没有 rows ⇒ 不判绿")
        return 2
    for p in parts:
        if Path(args.detail).name == p.name or (args.out and Path(args.out) == p):
            print("QUOTE-EVAL-MERGE-UNVERIFIED: 汇总落点 %s 与被合并的输入面同名 ⇒ 拒绝"
                  % (args.out or args.detail))
            return 2

    import quote_eval as q
    print("合并 %d 份明细 → %d 例（去重后）" % (len(parts), len(rows)))
    rc = q._judge_and_report(42, rows, [], False,
                             ["product", "linguist", "peer"], 2, args.detail)
    if args.out:
        Path(args.out).write_text(json.dumps(
            {"seed": 42, "smoke": False, "judges": ["product", "linguist", "peer"],
             "reps": 2, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
        print("合并明细 -> %s" % args.out)
    return rc


if __name__ == "__main__":
    sys.exit(main())
