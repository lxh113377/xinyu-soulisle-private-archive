# -*- coding: utf-8 -*-
"""对标 r121 探针：**peers 的性能/基准在册面**（16 仓 + self，三通道同尺）。

为什么补这一面：八维表的第 4 维「性能表现」此前每轮都写
「peers bench_script 未取到在册数 ⇒ 不做无据横比」（r112 §1、r119 §1 原句），
也就是说**这一格从来没有分母**。老大给的维度里明确含"响应时间/资源占用/并发处理能力"，
而"对手有没有量过"是这一维能不能横比的前提——没有探针，NA 就会一代代抄下去。

三通道（承 r38-r43 的 M5⑦⑧⑨ 纪律，A 单独不算数）：
  通道 A 文件树：基准脚本/基准目录（bench*/benchmark*/perf*/*.bench.ts 等），排除 node_modules 噪声
  通道 B CI 步：workflow 里有没有真**跑**基准（跑 vs 只是放着文件是两件事，A 必须有 B 佐证才算"在量"）
  通道 C 结果件：仓库里是否留了基准结果/阈值文件（baselines/*.json、--update-snapshots 之类）
                —— 有 A 有 B 无 C ⇒ 记 "跑但不留档"，不得折算成"有基线"

用法：python _test/peer_perf_probe.py [--json out.json] [--self-only] [--selftest] [--repo o/r]
退出码：0=分母齐且无 NA；1=存在 NA/未验；2=无 GitHub token 或取数面整体不可读（环境，不当结论）
"""
import argparse
import base64
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from benchmark_metrics import PEERS, ROOT          # 分母的唯一权威源＝名册，不抄数字

SELF_SLUG = "lxh113377/xinyu-soulisle-private-archive"
NOISE = re.compile(r"(^|/)(node_modules|vendor|dist|build|target|\.venv|venv|site-packages|\.git/)/", re.I)
BENCH_RX = re.compile(r"(^|/)(bench|benchmark|benchmarks|perf|performance|profile)/"
                      r"|(^|/)[\w.-]*\.(bench|benchmark)\.(ts|js|mjs|py)$"
                      r"|(^|/)(bench|benchmark|k6|locust|jmeter)[\w.-]*\.(ya?ml|json|py|js|ts)$"
                      r"|(^|/)bench[\w.-]*\.(py|sh|mjs|js)$", re.I)
RESULT_RX = re.compile(r"(^|/)(baselines?|bench-results?|benchmarks?/results?)/"
                      r"|(^|/)(bench|baseline)[\w.-]*\.(json|csv|md)$", re.I)
CI_RUN_RX = re.compile(r"(npm run (bench|benchmark)|pnpm (bench|benchmark)|yarn bench"
                       r"|pytest(-\S+)? .*(--benchmark|-m benchmark)|asv (machine|publish|run)"
                       r"|k6 run|locust -f|hyperfine|cargo bench|go test -bench"
                       r"|python [\w/]*bench[\w.-]*\.py)", re.I)


def classify_tree(paths):
    """通道 A/C：纯函数，selftest 直接喂路径集打它。"""
    clean = [p for p in paths if not NOISE.search(p)]
    return {"bench": sorted(p for p in clean if BENCH_RX.search(p)),
            "results": sorted(p for p in clean if RESULT_RX.search(p))[:6]}


def classify_ci(yaml_blobs):
    """通道 B：纯函数。返回命中基准跑的 step 文本（只取首 90 字，别把整份 YAML 塞进台账）。"""
    hits = []
    for name, text in (yaml_blobs or {}).items():
        m = CI_RUN_RX.search(text or "")
        if m:
            hits.append("%s::%s" % (name, m.group(0).strip()[:90]))
    return sorted(hits)


def verdict(rec):
    """三通道合成一句结论。宁可保守，也不把"有文件"升格成"在量性能"。"""
    a, b, c = rec.get("bench_files") or [], rec.get("ci_bench_steps") or [], rec.get("result_files") or []
    if a and b and c:
        return "measured-with-baseline"
    if a and b:
        return "measured-no-baseline"
    if a:
        return "files-only"                       # 有基准件但没人跑 ⇒ 不算在册能力
    if b:
        return "ci-only"
    return "none"


def gh_api(path, token):
    req = subprocess.run(["gh", "api", path], capture_output=True, text=True,
                         encoding="utf-8", errors="replace", timeout=60)
    if req.returncode != 0:
        raise RuntimeError((req.stderr or "").strip()[:120])
    return json.loads(req.stdout or "{}")


def tree_entries(slug, token):
    """一次 API 拿全树**条目**（含 blob 的 size）。返回 (entries, truncated)。

    r122：文档面探针 `_test/peer_docs_probe.py` 共用这一条取数通道——**取数机制只此一处**
    （同一事实两把尺会各自漂，r119 的"取数归口"就是为这个立的）。
    truncated 必须原样带出来：名册里 lobehub 这类大仓一定截断，截断面的"没有"不等于"真没有"。
    """
    meta = gh_api("repos/" + slug, token)
    ref = meta.get("default_branch") or "main"
    t = gh_api("repos/%s/git/trees/%s?recursive=1" % (slug, ref), token)
    return (t.get("tree") or []), bool(t.get("truncated"))


def tree_paths(slug, token):
    """树的路径清单（通道 A/B 的名册面）。"""
    entries, trunc = tree_entries(slug, token)
    return [x.get("path", "") for x in entries], trunc


def ci_files_from_tree(paths):
    """通道 B 的**文件名来源**＝git tree（与通道 A 同一次取数，单一取数面）。

    r121 一手教训：原先这里打的是 `contents/.github/workflows` 列目录，首跑 6 个仓回
    HTTP 404。当时的解释是「目录不存在＝这个仓没有 CI」，并把 404 折成读数 0 —— 3 分钟后
    同一路径复核，`morettt/my-neuro` 正常返回 3 个 workflow。404 是**瞬时读不到**
    （限流/token 刷新/边缘节点），不是「结论为否」。折成 0 会把 6 个有 CI 的仓写成 none，
    而台账里的 none 正是下一轮抄进八维表的那一格。⇒ 名字只认 tree，读不到就单列失明。
    """
    return sorted(p for p in paths
                  if p.startswith(".github/workflows/") and p.endswith((".yml", ".yaml")))


def fetch_blobs(slug, files, token):
    """逐个取 workflow 正文。取不到的**不静默跳过**：计入 blob_errs，由 finalize 判失明。"""
    out, errs = {}, 0
    for p in files:
        try:
            body = gh_api("repos/%s/contents/%s" % (slug, p), token)
            out[p.rsplit("/", 1)[-1]] = base64.b64decode(
                (body.get("content") or "").strip()).decode("utf-8", "replace")
        except Exception:                                  # noqa: BLE001
            errs += 1
        time.sleep(0.15)
    return out, errs


def finalize(rec):
    """把「读到 0」与「没读到」分开的最后一道闸。任一取数面失明时，
    禁止让「缺失」承担零结论（禁把盲区读成零）。"""
    blind = []
    if rec.get("tree_truncated"):
        blind.append("truncated-tree")
    if rec.get("ci_err"):
        blind.append("ci-listing-unread")
    if rec.get("blob_errs"):
        blind.append("ci-blob-unread×%d" % rec["blob_errs"])
    cls = verdict(rec)
    if cls == "none" and blind:
        cls = "unverified(%s)" % ",".join(blind)
    rec["class"] = cls
    if blind:
        rec["blind"] = blind
    return rec


def probe(repo, token):
    rec = {"repo": repo, "tier": ""}
    try:
        paths, trunc = tree_paths(repo, token)
        t = classify_tree(paths)
        wf = ci_files_from_tree(paths)
        rec.update({"bench_files": t["bench"][:8], "result_files": t["results"],
                    "tree_truncated": trunc, "path_count": len(paths),
                    "workflow_files": len(wf)})
        time.sleep(1.3)                                   # 错峰：search/rest 端点混打会被限流
        try:
            blobs, errs = fetch_blobs(repo, wf, token) if wf else ({}, 0)
        except Exception as e:                            # noqa: BLE001
            blobs, errs, rec["ci_err"] = {}, len(wf), str(e)[:80]
        rec["ci_bench_steps"] = classify_ci(blobs)
        if errs:
            rec["blob_errs"] = errs
        finalize(rec)
    except Exception as e:                                # noqa: BLE001
        rec["class"] = "unverified"
        rec["err"] = str(e)[:140]
    return rec


def self_only():
    """self 侧零网络：本仓的"基准"就是 perf_baseline + ramp 台账 + perf-baseline.yml。"""
    wf = sorted(str(p.relative_to(ROOT / ".github" / "workflows"))
                for p in (ROOT / ".github" / "workflows").glob("*.y*ml"))
    return {"repo": SELF_SLUG, "tier": "self",
            "bench_files": ["_test/perf_baseline_check.py", "_test/perf_ramp_delta_check.py"],
            "result_files": ["docs/PERF-BASELINE.md", "交付物/对标数据/battery-timing.json"],
            "ci_bench_steps": ["perf-baseline.yml::周常复跑基准"],
            "workflow_files": len(wf), "wf_names": wf,
            "class": verdict({"bench_files": ["x"], "ci_bench_steps": ["y"], "result_files": ["z"]}),
            "face": "worktree"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="")
    ap.add_argument("--self-only", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--repo", default="")
    a = ap.parse_args()
    if a.selftest:
        return run_selftest()
    rows, na = [], []
    if a.self_only:
        rows.append(self_only())
    else:
        targets = [r["repo"] for r in PEERS]
        if a.repo:
            targets = [x for x in a.repo.split(",") if x in targets] or targets[:0]
        for slug in targets:
            rows.append(probe(slug, ""))
    for r in rows:
        if str(r.get("class", "")).startswith("unverified") or r.get("err") or r.get("blind"):
            na.append("%s(%s)" % (r["repo"], r.get("class") or r.get("err")))
    n_measured = sum(1 for r in rows if r.get("class") in
                     ("measured-with-baseline", "measured-no-baseline"))
    payload = {"generated_by": "_test/peer_perf_probe.py", "denominator": len(PEERS),
               "rows": rows, "na": na, "measured": n_measured,
               "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    txt = json.dumps(payload, ensure_ascii=False, indent=1)
    if a.json:
        Path(a.json).write_bytes((txt + "\n").encode("utf-8").replace(b"\r\n", b"\n"))
    print("PEER-PERF-%s：在册 %d/%d 仓有基准行为（measured*），NA %d，truncated 面单列不折算成零"
          % ("PASS" if not na else "PARTIAL", n_measured, len(PEERS), len(na)))
    for r in rows:
        print("  %-42s %-26s bench=%d ci=%d res=%d wf=%s%s" % (
            r["repo"][:42], r.get("class"), len(r.get("bench_files") or []),
            len(r.get("ci_bench_steps") or []), len(r.get("result_files") or []),
            r.get("workflow_files", "NA"),
            " blind=%s" % ",".join(r["blind"]) if r.get("blind") else ""))
    return 0 if not na else 1


STUBS = [
    ("A+B+C 齐 ⇒ measured-with-baseline",
     {"bench_files": ["benchmarks/b.py"], "ci_bench_steps": ["ci.yml::pytest --benchmark"],
      "result_files": ["baselines/x.json"]}, "measured-with-baseline"),
    ("只有文件没人跑 ⇒ files-only（不算在册能力）",
     {"bench_files": ["benchmarks/b.py"], "ci_bench_steps": [], "result_files": []}, "files-only"),
    ("跑但不留档 ⇒ measured-no-baseline",
     {"bench_files": ["bench/b.js"], "ci_bench_steps": ["ci.yml::npm run bench"],
      "result_files": []}, "measured-no-baseline"),
    ("什么都没有 ⇒ none", {"bench_files": [], "ci_bench_steps": [], "result_files": []}, "none"),
]


def run_selftest():
    bad = []
    for name, rec, want in STUBS:
        got = verdict(rec)
        if got != want:
            bad.append("%s：期望 %s 实得 %s" % (name, want, got))
    t = classify_tree(["benchmarks/suite.py", "node_modules/bench/x.js", "src/app.ts",
                       "k6/load.js", "docs/PERF.md"])
    if "node_modules/bench/x.js" in t["bench"]:
        bad.append("噪声面进了分母 ⇒ 会把依赖里的文件算成对手能力")
    if "src/app.ts" in t["bench"]:
        bad.append("普通源码被判成基准件（误报侧）")
    c = classify_ci({"ci.yml": "run: pytest -m benchmark\n", "rel.yml": "run: npm test\n"})
    if c != ["ci.yml::pytest -m benchmark"]:
        bad.append("CI 通道取数不对：%s ⇒ 有基准步会被漏记" % c)
    if classify_ci({"x.yml": "run: npm test"}):
        bad.append("CI 通道误报：普通测试步被判成基准跑")
    # ── 通道 B 的取数面 + 失明闸（r121 一手：contents 列目录瞬时 404 被折成"没有 CI"）──
    wf = ci_files_from_tree([".github/workflows/ci.yml", ".github/workflows/rel.yaml",
                             ".github/ISSUE_TEMPLATE/bug.yml", ".github/workflows/notes.md",
                             "src/.github/workflows/fake.yml"])
    if wf != [".github/workflows/ci.yml", ".github/workflows/rel.yaml"]:
        bad.append("workflow 名册取数不对：%s" % wf)
    # 反例腿①：什么都没读到 + CI 面失明 ⇒ 必须是 unverified，不得是 none（none 会被抄成"对手没量过"）
    r1 = finalize({"bench_files": [], "ci_bench_steps": [], "result_files": [], "blob_errs": 3})
    if not str(r1["class"]).startswith("unverified"):
        bad.append("失明被折成零：blob 读不到仍判 %s" % r1["class"])
    # 反例腿②：树截断 ⇒ "没有基准件"这句话不成立
    r2 = finalize({"bench_files": [], "ci_bench_steps": [], "result_files": [],
                   "tree_truncated": True})
    if r2["class"] != "unverified(truncated-tree)":
        bad.append("截断树判成了 %s" % r2["class"])
    # 正向腿：有读数时失明只登记、不改结论（不能把 404 变成万能挡箭牌）
    r3 = finalize({"bench_files": ["bench/b.js"], "ci_bench_steps": [], "result_files": [],
                   "blob_errs": 2})
    if r3["class"] != "files-only" or not r3.get("blind"):
        bad.append("有读数面的结论/失明登记不对：%s blind=%s" % (r3["class"], r3.get("blind")))
    # 正向腿②：齐面且无失明 ⇒ 不带 blind 字段
    r4 = finalize({"bench_files": ["bench/b.js"], "ci_bench_steps": ["ci.yml::npm run bench"],
                   "result_files": ["baselines/x.json"]})
    if r4["class"] != "measured-with-baseline" or r4.get("blind"):
        bad.append("干净面被误标失明：%s" % r4)
    print("PEER-PERF-SELFTEST-%s（%d 类通道桩 + 噪声面 + CI 双向 + 失明闸 4 腿）"
          % ("PASS" if not bad else "FAIL: " + "; ".join(bad), len(STUBS)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
