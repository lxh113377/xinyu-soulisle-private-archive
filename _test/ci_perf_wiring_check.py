# -*- coding: utf-8 -*-
"""CI 性能步接线判据（r91）：把「性能表现」这一维从**只在本地有数**变成**在受理面上有门**。

动因（本轮实测，不是愿望）：对标尺 `doc_perf` 的 7 格里 self 已经 5 真 2 假，两假恰好是
`ci_perf_step` 与 `published_numbers`——而这两格在 16 个参照仓里是 **0/16**（全行业共同缺失）。
r91 把 `_test/perf_baseline_check.py` 接进 `.github/workflows/perf-baseline.yml`、把实测数字
写进 README，于是两格翻真。但**翻真那一刻就是它开始漂移的那一刻**：

  · workflow 文件可以是空的（文件名照样被 RE_CI_PERF 认成"有性能步"）；
  · workflow 可以起了 jar 却不等 `/api/health` 就绪 ⇒ perf 判据 rc=2「未验证」，
    一个永远未验的门 = 假门（本地跑是绿，CI 那条线其实一次也没量到）；
  · README 的数字可以是随手写的（r41/r52 在册教训：断言不等于读数）。

所以本件盯五条（C-IPW-1..5），且**正则与采集器同源**（从 `benchmark_metrics` import，
不内联复刻——内联复刻就是"两把尺各说各话"的同族坑，见 `tracked_secret_scan` 的既有做法）。

退出码：0=CIPW-PASS 1=判红 2=取数面不可达（未验，不得当通过）
用法：python _test/ci_perf_wiring_check.py [--selftest]
"""
import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "_test"))

WF_DIR = ROOT / ".github" / "workflows"
README = ROOT / "README.md"
PERF_DOC = ROOT / "docs" / "PERF-BASELINE.md"
PERF_JUDGE = "_test/perf_baseline_check.py"
# 预算必须与 perf_baseline_check.BUDGETS 的 p95 上限同族；这里取最紧的一档做数量级护栏
P95_BUDGET_MS = 400.0
# 两处数字允许相差的倍数：本机 p95 每次跑都会抖（本轮 28.6ms，上轮 30.2ms），
# 但**数量级分叉**（README 写 12ms、基线文档写 300ms）一定是有一边在编 ⇒ 必须红。
MAX_RATIO = 3.0
RE_P95_NUM = re.compile(r"[Pp]95\s*[=＝:：]\s*(\d+(?:\.\d+)?)\s*ms")


def _import_same_source():
    """同源正则：拿不到采集器就报未验（宁可未验，也不内联一把第二尺）。"""
    try:
        import benchmark_metrics as bm
    except Exception as e:
        return None, "import benchmark_metrics 失败: %s" % e
    rx = getattr(bm, "RE_CI_PERF", None)
    fn = getattr(bm, "doc_perf_text_class", None)
    if rx is None or fn is None:
        return None, "benchmark_metrics 缺 RE_CI_PERF / doc_perf_text_class"
    return (rx, fn), ""


def _read(p):
    try:
        return p.read_text(encoding="utf-8")
    except OSError:
        return None


def find_perf_workflow(rx_ci_perf):
    """返回 (相对路径, 正文)；找不到返回 (None, None)。"""
    if not WF_DIR.is_dir():
        return None, None
    for p in sorted(WF_DIR.glob("*.y*ml")):
        rel = str(p.relative_to(ROOT)).replace("\\", "/")
        if rx_ci_perf.search(rel):
            return rel, _read(p)
    return None, None


def p95_numbers(text):
    return [float(x) for x in RE_P95_NUM.findall(text or "")]


def evaluate(readme_text, perf_doc_text, wf_rel, wf_text, rx_ci_perf, doc_fn):
    """纯函数：五条判据。返回 (red 列表, 证据 dict)。"""
    red, ev = [], {}

    # C-IPW-1：存在一个**名字真被同源正则认下**的性能 workflow（防"文件在但名字不匹配"的假有）
    if not wf_rel:
        red.append("C-IPW-1 没有 workflow 文件名命中 RE_CI_PERF ⇒ ci_perf_step 在 self 侧仍是假")
        return red, ev
    if not (wf_text or "").strip():
        red.append("C-IPW-1 %s 正文为空 ⇒ 文件名冒充性能步（尺只看名字会全绿）" % wf_rel)
        return red, ev
    ev["wf"] = wf_rel

    # C-IPW-2：正文真调用了性能判据本体
    if PERF_JUDGE not in wf_text:
        red.append("C-IPW-2 %s 未调用 %s ⇒ 有 workflow 无性能判定" % (wf_rel, PERF_JUDGE))
    else:
        ev["judge_call"] = PERF_JUDGE

    # C-IPW-3：真起了服务且等 /api/health 就绪 —— 否则 perf 判据必然 rc=2「未验证」，
    #          而"未验证"在聚合视图里极易被读成"没红"
    has_start = "java -jar" in wf_text
    has_wait = re.search(r"api/health", wf_text) is not None and re.search(
        r"for i in|until |seq 1", wf_text) is not None
    if not has_start:
        red.append("C-IPW-3 %s 没有 `java -jar` 起服 ⇒ 被测对象不存在" % wf_rel)
    if not has_wait:
        red.append("C-IPW-3 %s 未等 /api/health 就绪 ⇒ 判据恒 rc=2 未验（假门）" % wf_rel)
    if has_start and has_wait:
        ev["readiness"] = "java -jar + 等 health"

    # C-IPW-4：README 侧 published_numbers 翻真，**且**数字有出处（不许裸数字）
    pub = doc_fn(readme_text or "")[0].get("published_numbers")
    if not pub:
        red.append("C-IPW-4 README 未被同源尺判成 published_numbers ⇒ 对标该格仍是假")
    else:
        ev["published"] = True
    if "docs/PERF-BASELINE.md" not in (readme_text or ""):
        red.append("C-IPW-4 README 有性能数字却未引用 docs/PERF-BASELINE.md ⇒ 读者无法复算口径")

    # C-IPW-5：README 数字与基线文档数字不得数量级分叉（防一处改了另一处留在上一轮）
    r_nums, d_nums = p95_numbers(readme_text), p95_numbers(perf_doc_text)
    if not r_nums:
        red.append("C-IPW-5 README 里取不到 p95 数字 ⇒ 无从对账（要么没写，要么写法换了而本件没跟上）")
    elif not d_nums:
        red.append("C-IPW-5 docs/PERF-BASELINE.md 里取不到 p95 数字 ⇒ 基线面失联")
    else:
        r, d = r_nums[0], d_nums[0]
        ev["p95"] = "README=%.1fms BASELINE=%.1fms" % (r, d)
        if r > P95_BUDGET_MS or d > P95_BUDGET_MS:
            red.append("C-IPW-5 有数字超出预算 %.0fms（README=%.1f / BASELINE=%.1f）⇒ 不是抖动量级"
                       % (P95_BUDGET_MS, r, d))
        ratio = max(r, d) / min(r, d)
        if ratio > MAX_RATIO:
            red.append("C-IPW-5 两处 p95 相差 %.1f 倍 > %.1f ⇒ 数量级分叉，必有一边不是本轮实测"
                       % (ratio, MAX_RATIO))
    return red, ev


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    same, err = _import_same_source()
    if same is None:
        print("CIPW-UNVERIFIED: %s ⇒ 不判绿" % err)
        return 2
    rx_ci_perf, doc_fn = same
    wf_rel, wf_text = find_perf_workflow(rx_ci_perf)
    readme, perf_doc = _read(README), _read(PERF_DOC)
    if readme is None or perf_doc is None:
        print("CIPW-UNVERIFIED: 取不到 README.md / docs/PERF-BASELINE.md ⇒ 不判绿")
        return 2
    red, ev = evaluate(readme, perf_doc, wf_rel, wf_text, rx_ci_perf, doc_fn)
    if red:
        for x in red:
            print("  FAIL", x)
        print("CIPW-FAIL: %d 条接线/对账不成立" % len(red))
        return 1
    print("CIPW-PASS: %s 真跑 %s（%s）｜README published_numbers 在册且引用基线文档｜%s"
          % (ev.get("wf"), PERF_JUDGE, ev.get("readiness"), ev.get("p95")))
    return 0


def selftest():
    """自证判据不恒绿：五类篡改各必须红，且合规样本必须绿（防为消红把规则砍成恒假）。"""
    same, err = _import_same_source()
    if same is None:
        print("SELFTEST-FAIL: 同源正则取不到（%s）" % err)
        return 1
    rx_ci_perf, doc_fn = same

    good_wf = (
        "      - name: 起 fat jar 并跑性能基线\n"
        "        run: |\n"
        "          java -jar server/target/soulisle-server.jar --server.port=8123 &\n"
        "          for i in $(seq 1 40); do\n"
        "            if curl -sf http://127.0.0.1:8123/api/health > /dev/null; then break; fi\n"
        "          done\n"
        "          python _test/perf_baseline_check.py --json /tmp/perf.json\n"
    )
    good_readme = ("# T\n## ✅ 验证\n> **性能**：实测 P95=28.6ms（预算 400ms）、吞吐 1013.9 rps；"
                   "口径见 [docs/PERF-BASELINE.md](docs/PERF-BASELINE.md)。\n")
    good_doc = "# PERF\n- 结果：`PERF-BASELINE-PASS` —— p95=28.6ms，吞吐 1013.9 rps。\n"
    wf_rel = ".github/workflows/perf-baseline.yml"
    if not rx_ci_perf.search(wf_rel):
        print("SELFTEST-FAIL: 合规 workflow 名 %s 竟不被 RE_CI_PERF 认下 ⇒ 判据与采集器已失同源" % wf_rel)
        return 1

    def red_of(rm=good_readme, doc=good_doc, rel=wf_rel, wf=good_wf):
        return evaluate(rm, doc, rel, wf, rx_ci_perf, doc_fn)[0]

    cases = []
    cases.append(("正例：合规全套必须绿", red_of(), 0))
    cases.append(("反例①：删掉 workflow（文件名都没了）", red_of(rel=None, wf=None) or ["x"], 1))
    cases.append(("反例②：workflow 正文空（文件名冒充）", red_of(wf="   "), 1))
    cases.append(("反例③：workflow 不调性能判据", red_of(wf=good_wf.replace(PERF_JUDGE, "_test/noop.py")), 1))
    cases.append(("反例④：起了 jar 但不等 health（恒未验的假门）",
                  red_of(wf=good_wf.replace("for i in $(seq 1 40); do", "sleep 1")), 1))
    cases.append(("反例⑤：README 删掉性能数字（published_numbers 退回假）",
                  red_of(rm=good_readme.replace("P95=28.6ms", "p95 在预算内")), 1))
    cases.append(("反例⑥：README 留数字但抽掉基线文档引用（读者无法复算）",
                  red_of(rm=good_readme.replace("[docs/PERF-BASELINE.md](docs/PERF-BASELINE.md)", "见文档")), 1))
    cases.append(("反例⑦：两处 p95 数量级分叉（README 28.6ms vs 基线 300ms）",
                  red_of(doc=good_doc.replace("p95=28.6ms", "p95=300.0ms")), 1))
    cases.append(("反例⑧：数字超出预算（基线写 900ms）",
                  red_of(doc=good_doc.replace("p95=28.6ms", "p95=900.0ms")), 1))
    cases.append(("反例⑨：基线文档取不到 p95（基线面失联）",
                  red_of(doc="# PERF\n- 结果：PASS。\n"), 1))

    bad = []
    for name, got, want in cases:
        got_n = len(got) if isinstance(got, list) else got
        if (got_n > 0) != (want > 0):
            bad.append("%s（期望%s，实得%s）" % (name, "红" if want else "绿", "红" if got_n else "绿"))
    # 恒真守护：零输入不得被判绿（违反"取不到=未验"这条铁律）
    if not evaluate("", "", None, None, rx_ci_perf, doc_fn)[0]:
        bad.append("零输入被判绿 ⇒ 判据恒真")
    if bad:
        print("SELFTEST-FAIL: " + "; ".join(bad))
        return 1
    print("CIPW-SELFTEST-PASS: %d 条用例（1 正例 + 9 反例 + 零输入恒真守护）" % (len(cases) + 1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
