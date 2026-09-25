# -*- coding: utf-8 -*-
"""CI 受理面体检：把「CI 红」先分成 环境级 / 代码级 两类（对标轮 r29）

起因（实测，不猜）：r28 把判据电池挂上 CI 后，我连续三次去查 `gh run`，看到 4 个 job 全红。
真因写在 run 的 ANNOTATIONS 里：**runner 从未启动**（"recent account payments have failed or
your spending limit needs to increased"），每个 job 只花 3 秒、日志根本不存在。
如果按"CI 红 ⇒ 我改坏了"去归因，会把三个正确结论（编译/依赖/环境画像修复）全部推翻重来。

判据：
  K1 取最近 N 次 main push 的 run（默认 3 次），逐条分类：success / code-fail / env-blocked / in_progress
  K2 「所有 job 都在 <15s 内失败」+ annotation 命中账单/配额/无 runner 关键词 ⇒ 判 ENV-BLOCKED（rc=2，不判代码红）
  K3 出现代码级失败（有真日志）⇒ rc=1 并打印 job 名，由人去看 step
  K4 全绿 ⇒ rc=0
  --selftest：喂合成 payload 做双向断言（账单事件必须判 ENV、真失败必须判 CODE、全绿必须判 PASS、
              把"账单事件"改成普通失败时必须翻判 CODE —— 否则分类器恒真）

用法：python _test/ci_status_check.py [--limit N] [--selftest]
前置：`gh` 可用且已登录（不可用 = 环境异常 rc=2，与"CI 红"分开报）
"""
import argparse
import json
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

ENV_PAT = re.compile(r"account payments|spending limit|no runner|could not be scheduled|runner availability", re.I)
FAST_S = 15


def classify(runs):
    """runs: [{id, conclusion, status, jobs:[{name,conclusion,duration_s}], annotations:[str]}] ⇒ (verdict, reasons)"""
    out = []
    for r in runs:
        if r.get("status") != "completed":
            out.append((r["id"], "IN_PROGRESS", "仍在跑，不作结论"))
            continue
        concl = r.get("conclusion")
        if concl == "success":
            out.append((r["id"], "PASS", "全绿"))
            continue
        jobs = r.get("jobs") or []
        ann = " ; ".join(r.get("annotations") or [])
        fast = bool(jobs) and all((j.get("duration_s") or 0) < FAST_S for j in jobs)
        if fast and ENV_PAT.search(ann):
            why = f"runner 未启动（账单/配额类），全部 job {max((j.get('duration_s') or 0) for j in jobs):.0f}s 内失败"
            out.append((r["id"], "ENV_BLOCKED", why + " ⇒ 不判代码红"))
        else:
            bad = [j["name"] for j in jobs if j.get("conclusion") not in (None, "success")]
            out.append((r["id"], "CODE_FAIL", "有真日志的失败 job：" + ", ".join(bad[:4]) or "(未取到 job 名)"))
    return out


def gh_json(args):
    cmd = ["gh", "run", "list", "--branch", "main", "--limit", str(args.limit),
           "--json", "databaseId,conclusion,status,headSha,displayTitle"]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
    if p.returncode != 0:
        return None, (p.stderr or p.stdout or "gh 调用失败").strip()[:200]
    runs = []
    for r in json.loads(p.stdout or "[]"):
        j = subprocess.run(["gh", "run", "view", str(r["databaseId"]), "--json", "jobs"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
        jobs = []
        if j.returncode == 0:
            for x in (json.loads(j.stdout or "{}").get("jobs") or []):
                sec = None
                if x.get("startedAt") and x.get("completedAt"):
                    from datetime import datetime
                    fmt = "%Y-%m-%dT%H:%M:%SZ"
                    sec = (datetime.strptime(x["completedAt"], fmt) - datetime.strptime(x["startedAt"], fmt)).total_seconds()
                jobs.append({"name": x.get("name"), "conclusion": x.get("conclusion"), "duration_s": sec})
        runs.append({"id": r["databaseId"], "conclusion": r.get("conclusion"), "status": r.get("status"),
                     "sha": (r.get("headSha") or "")[:7], "title": (r.get("displayTitle") or "")[:40], "jobs": jobs,
                     "annotations": []})
    return runs, None


def annotations_of(run_id):
    """从 `gh run view <id>` 的 ANNOTATIONS 段取原文。
    r29 实测：账单/配额类原因**只出现在这里**（job 没启动 ⇒ 没有 step 日志可 grep），
    所以受理面分类必须先读这一段的全文，而不是 tail 一个窗口。"""
    v = subprocess.run(["gh", "run", "view", str(run_id)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=90)
    if v.returncode != 0 or "ANNOTATIONS" not in (v.stdout or ""):
        return []
    return [ln.strip() for ln in v.stdout.split("ANNOTATIONS", 1)[1].splitlines() if ln.strip()]


def selftest():
    runs = [
        {"id": 1, "status": "completed", "conclusion": "failure",
         "jobs": [{"name": "A", "conclusion": "failure", "duration_s": 3}, {"name": "B", "conclusion": "failure", "duration_s": 3}],
         "annotations": ["The job was not started because recent account payments have failed or your spending limit needs to be increased."]},
        {"id": 2, "status": "completed", "conclusion": "failure",
         "jobs": [{"name": "browser", "conclusion": "failure", "duration_s": 220}],
         "annotations": []},
        {"id": 3, "status": "completed", "conclusion": "success", "jobs": [], "annotations": []},
    ]
    v = {rid: kind for rid, kind, _ in classify(runs)}
    bad = []
    if v[1] != "ENV_BLOCKED":
        bad.append(f"账单事件被判成 {v[1]}（应为 ENV_BLOCKED）⇒ 会把环境问题当回归去改代码")
    if v[2] != "CODE_FAIL":
        bad.append(f"真失败被判成 {v[2]}（应为 CODE_FAIL）")
    if v[3] != "PASS":
        bad.append(f"全绿被判成 {v[3]}")
    # 反向：把账单措辞换成普通错误，必须翻判 CODE_FAIL（否则分类器只是在读"3 秒"这一个特征）
    runs2 = [dict(runs[0], annotations=["Some unrelated step error"]) | {"jobs": runs[0]["jobs"]}]
    v2 = classify(runs2)[0]
    if v2[1] != "CODE_FAIL":
        bad.append(f"去掉账单措辞后仍被判 {v2[1]} ⇒ 分类器恒判 ENV")
    import os
    old = os.environ.get("GITHUB_ACTIONS")
    os.environ["GITHUB_ACTIONS"] = "true"
    argv_backup = sys.argv[1:]
    sys.argv = [sys.argv[0]]          # 关键：不把 --selftest 传下去，否则 selftest→main→selftest 无限递归
    inside = None
    try:
        inside = main()
    finally:
        sys.argv = [sys.argv[0]] + argv_backup
        if old is None:
            os.environ.pop("GITHUB_ACTIONS", None)
        else:
            os.environ["GITHUB_ACTIONS"] = old
    if inside != 0:
        bad.append(f"在 CI 内部本判据未 SKIP（返回 {inside}）⇒ 会让 CI 用自己给自己判红")
    if bad:
        print("SELFTEST-FAIL: " + " ; ".join(bad))
        return 1
    print("SELFTEST-PASS: ENV/CODE/PASS 三态判定正确，且去掉账单措辞后立刻翻判 CODE（分类器非恒真）")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=3)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    import os
    if os.environ.get("GITHUB_ACTIONS"):
        print("CI-STATUS-SKIP: 本判据在 CI 内部是自指（这一步的结论就是受理面本身）⇒ 只在本地/收尾时核验")
        return 0
    runs, err = gh_json(a)
    if runs is None:
        print(f"CI-STATUS-ENV-ERROR: gh 不可用 ⇒ 受理面无法核验（不判代码红）：{err}")
        return 2
    for r in runs:
        r["annotations"] = annotations_of(r["id"])
    rows = classify(runs)
    for rid, kind, why in rows:
        print(f"  run {rid}: {kind:12s} {why}")
    # 结论只取**最近一次 run**（历史红会被后来者盖过，拿历史当现值就是"沿用旧数字"）
    latest = rows[0] if rows else None
    env = [k for _, k, _ in rows if k == "ENV_BLOCKED"]
    code = [k for _, k, _ in rows if k == "CODE_FAIL"]
    pend = [k for _, k, _ in rows if k == "IN_PROGRESS"]
    head = [r for r in runs if r.get("sha")]
    verdict = latest[1] if latest else "NO_RUN"
    npass = sum(1 for _, k, _ in rows if k == "PASS")
    print(f"\n最近 {len(rows)} 次 main push：PASS {npass} / CODE_FAIL {len(code)} / "
          f"ENV_BLOCKED {len(env)} / 进行中 {len(pend)}")
    print(f"HEAD 最近一次 run 判定 = {verdict}（sha={head[0]['sha'] if head else '-'}）；更早的仅作上下文")
    if verdict == "CODE_FAIL":
        print("CI-STATUS-RED: 代码级失败，必须看 step 日志（gh run view <id> --log-failed）")
        return 1
    if verdict in ("ENV_BLOCKED", "IN_PROGRESS", "NO_RUN"):
        print("CI-STATUS-PENDING: 受理面未取到有效结论（账单/配额、排队或无 run）⇒ 本轮不得声称「CI 已验」")
        return 2
    if verdict == "PASS":
        print("CI-STATUS-PASS")
        return 0
    print(f"CI-STATUS-PENDING: 未知判定 {verdict}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
