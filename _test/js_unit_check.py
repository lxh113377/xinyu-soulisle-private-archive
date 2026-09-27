# -*- coding: utf-8 -*-
"""JS 侧单元测试执行判据（对标轮 r58）：把「我们有测试」这句话拆成两端各自的回执。

动机（本轮对标的实测起点）：`peer_quality_tooling_probe.py --self-only` 量出
本仓 **js 测试文件 0 个**，而 Java 侧有 4 个测试类 / 30 个用例并在 CI 真跑。
README 写着「判据清单全文见 docs/quality-gates.md」，读者会自然把"有单测"当成全仓事实——
它只对 Java 半边成立。本件补的就是 JS 那半边，并把条数钉进一行。

为什么还要这层 Python 包装（而不是把 .mjs 直接挂进电池）：
  1) **电池折叠只留最后一条含判据词的行**（r40b 的教训）：`node --test` 的汇总行是
     `ℹ pass 7`——既不含 PASS/FAIL 也不含总数，进 CI 就等于"没数"。判据行必须自带计数。
  2) 分母要由**文件枚举**得出，而不是"跑了一个文件"：新增 .test.mjs 必须自动进面，
     一个都不在时应判 UNVERIFIED 而不是 PASS。
  3) node 缺失/异常输出要有独立状态，不能把"没跑到"读成"跑过了"。

用法：python _test/js_unit_check.py [--dir _test/js] [--selftest]
退出码：0=全过 1=有用例红或计数不自洽 2=没跑到（无测试文件 / node 不可用 / 输出不可解析）
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COUNT_RX = re.compile(r"^.?\s*(tests|pass|fail|cancelled|skipped|todo)\s+(\d+)", re.M)


def parse_counts(text):
    """从 node --test 的输出里取计数。**按形状取，不取最后一行**（stderr 警告会挤掉汇总行）。"""
    out = {}
    for k, v in COUNT_RX.findall(text or ""):
        if k not in out:                      # 同名取首个（node 的汇总块在最前）
            out[k] = int(v)
    return out


def assess(files, rc, stdout, stderr):
    """纯函数：返回 (verdict, code)。code: 0 绿 / 1 红 / 2 未验证。"""
    if not files:
        return "JS-UNIT-UNVERIFIED: `_test/js` 下没有 *.test.mjs ⇒ 零分母不得判绿", 2
    text = (stdout or "") + "\n" + (stderr or "")
    c = parse_counts(text)
    if "tests" not in c:
        return ("JS-UNIT-UNVERIFIED: node 退出码 %s 且输出取不到 tests 计数（node 不可用或格式变了）"
                "｜文件 %d 个｜stdout 首行=%s" % (rc, len(files), text.strip().splitlines()[:1]), 2)
    n, p, f = c.get("tests", 0), c.get("pass", 0), c.get("fail", 0)
    other = sum(v for k, v in c.items() if k in ("cancelled", "skipped", "todo"))
    if n == 0:
        return "JS-UNIT-UNVERIFIED: tests=0 ⇒ 没有任何用例被执行，不算通过", 2
    if p + f + other != n:
        return ("JS-UNIT-FAIL: 计数不自洽 tests=%d 而 pass=%d+fail=%d+其它=%d=%d"
                " ⇒ 汇总被截或有用例没被 accounting" % (n, p, f, other, p + f + other)), 1
    if f or rc != 0:
        first = ""
        m = re.search(r"^# (fail|AssertionError|Error)[^\n]*", text, re.M)
        if m:
            first = "｜" + m.group(0)[:120]
        return "JS-UNIT-FAIL: %d/%d 用例红（fail=%d, node rc=%s）%s" % (f, n, f, rc, first), 1
    return ("JS-UNIT-PASS: %d 用例全过（文件 %d 个：%s）｜跨 realm 归一在位"
            % (n, len(files), ",".join(x.name for x in files[:4])), 0)


STUBS = [
    ("正向 7/7", ["a.test.mjs"], 0, "ℹ tests 7\nℹ pass 7\nℹ fail 0\nℹ cancelled 0\nℹ skipped 0\nℹ todo 0\n", "", 0),
    ("反向 有红", ["a.test.mjs"], 1, "ℹ tests 7\nℹ pass 6\nℹ fail 1\n", "# fail 1\nAssertionError: x", 1),
    ("零分母", [], 0, "ℹ tests 0\nℹ pass 0\nℹ fail 0\n", "", 2),
    ("tests=0 不得绿", ["a.test.mjs"], 0, "ℹ tests 0\nℹ pass 0\nℹ fail 0\n", "", 2),
    ("计数不自洽", ["a.test.mjs"], 0, "ℹ tests 7\nℹ pass 5\nℹ fail 0\n", "", 1),
    ("输出取不到计数", ["a.test.mjs"], 127, "node: not found\n", "", 2),
    ("stderr 挤掉汇总仍可解析", ["a.test.mjs"], 0, "ℹ tests 2\nℹ pass 2\nℹ fail 0\n",
     "(node:1234) Warning: something\n", 0),
]


def _mk(names):
    return [Path(n) for n in names]


def selftest():
    bad = []
    for name, files, rc, out, err, want in STUBS:
        got = assess(_mk(files), rc, out, err)
        if got[1] != want:
            bad.append("%s：期望 rc=%d 实得 %d（%s）" % (name, want, got[1], got[0][:60]))
    # 恒绿守卫：判据若对"全红输出"也给绿，上面的反向腿会抓到；这里再钉一条更裸的
    if assess(_mk(["a.test.mjs"]), 1, "ℹ tests 3\nℹ pass 0\nℹ fail 3\n", "")[1] == 0:
        bad.append("判据恒绿：3/3 全红仍判通过")
    if parse_counts("no numbers here") != {}:
        bad.append("parse_counts 在无关文本上凭空造出计数")
    print("JS-UNIT-SELFTEST-%s（%d 类桩 + 恒绿守卫）" % ("PASS" if not bad else "FAIL: " + "; ".join(bad), len(STUBS)))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="_test/js")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    d = ROOT / a.dir
    files = sorted(d.glob("*.test.mjs")) if d.is_dir() else []
    if not files:
        verdict, code = assess(files, 0, "", "")
        print(verdict)
        return code
    try:
        r = subprocess.run(["node", "--test", *[str(f) for f in files]],
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=180, cwd=str(ROOT))
        rc, so, se = r.returncode, r.stdout, r.stderr
    except (OSError, subprocess.TimeoutExpired) as e:
        print("JS-UNIT-UNVERIFIED: node 不可用或超时（%s）⇒ 不得记为通过" % type(e).__name__)
        return 2
    verdict, code = assess(files, rc, so, se)
    if a.json:
        print(json.dumps({"verdict": verdict, "rc": code, "files": [f.name for f in files],
                          "counts": parse_counts(so + se)}, ensure_ascii=False))
    else:
        print(verdict)
    if code != 0:
        for ln in (so or "").splitlines():
            if ln.startswith("# fail") or "AssertionError" in ln or ln.startswith("not ok"):
                print("  · " + ln.strip()[:160])
    return code


if __name__ == "__main__":
    sys.exit(main())
