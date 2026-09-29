#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""push 后的 CI 回执看守（把"看 CI"从人记得住，变成一条命令必跑）。

为什么要有它：本仓 51 条判据里有相当一部分只在 CI 才判得动（Linux runner / 无密钥豁免面 /
浅克隆无 tag 的 ls-remote 分支）。过去四轮都是"push 完就收工"，CI 结果靠下一轮想起来再查。
本脚本把那一环闭掉：**等结论 → 逐 job 点名 → 失败面自动抓日志原文 → 输出可直接执行的修复指令**。

退出码（与电池同族约定，别改语义）：
    0 = CI 全绿        1 = 有红（stdout 末尾给出红 job 与日志摘录 + 下一步指令）
    2 = 未验证（gh 不可用 / 无网络 / 超时没拿到结论 ⇒ 绝不当通过）

用法：
    python _test/ci_watch.py                      # 盯当前 HEAD
    python _test/ci_watch.py --sha <sha>          # 盯指定提交
    python _test/ci_watch.py --timeout 420        # 默认 300s
    python _test/ci_watch.py --selftest           # 桩：GREEN/RED/NO-RUN/TIMEOUT 四态
判据自证（防恒绿）：--selftest 用注入的假回执跑同一条判定函数，四态各须如期望。
"""
import argparse
import json
import subprocess
import sys
import time

VERDICT_LINES = 40


def sh(args, timeout=60):
    """返回 (rc, stdout, stderr)。

    ⚠️ stderr 必须带回来：r83 两次真推送后本工具都报「宽限 180s 后仍无 run 记录（）」，
    括号里那个空串就是被丢掉的 stderr —— 实际远端**有** run（`gh run list` 现读 216/217 两条），
    坏的是取数那一步。把「我没取到」印成「没有 run」= R247/⑤-b 那一族（读不动不得写成结论为否）。
    """
    try:
        r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout)
        return r.returncode, (r.stdout or ""), (r.stderr or "")
    except Exception as e:                                  # gh 缺失/网络异常都走这里
        return 127, "", "%s: %s" % (type(e).__name__, e)


def runs_for(sha):
    """返回 (rows|None, 说明, 取数是否失败)。第三项是分叉点：失败 ≠ 无 run。"""
    rc, out, err = sh(["gh", "run", "list", "--limit", "20", "--json",
                       "databaseId,headSha,status,conclusion"])
    if rc != 0:
        return None, "gh run list 取数失败 rc=%d｜stderr=%s" % (rc, (err or out).strip()[:200]), True
    try:
        rows = json.loads(out or "[]")
    except Exception as e:
        return None, "回执不是 JSON（%s）：%s" % (type(e).__name__, out[:120]), True
    hit = [r for r in rows if str(r.get("headSha", "")).startswith(sha)]
    return (hit or None), ("" if hit else "远端 list 取到 %d 条，没有该 sha 的 run" % len(rows)), False


def classify(rows):
    """纯函数：run 列表 → (状态, 说明)。状态 ∈ GREEN / PENDING / RED / NO_RUN。"""
    if not rows:
        return "NO_RUN", "远端没有这个提交的 run（分支未触发 / push 未落地）"
    st = {r.get("status") for r in rows}
    if "queued" in st or "in_progress" in st:
        return "PENDING", "仍有 run 未完成"
    bad = [r for r in rows if r.get("conclusion") not in ("success", "skipped")]
    if bad:
        return "RED", "；".join("run %s=%s" % (r.get("databaseId"), r.get("conclusion")) for r in bad)
    return "GREEN", "全部 run success（%d 条）" % len(rows)


def red_detail(run_id):
    _rc, out, _err = sh(["gh", "run", "view", str(run_id), "--json", "jobs",
                   "--jq", '[.jobs[] | select(.conclusion != "success") | .name + " => " + .conclusion] | join("\\n")'],
                  timeout=90)
    jobs = out.strip() or "(取不到 job 明细)"
    _rc2, log, _e2 = sh(["gh", "run", "view", str(run_id), "--log-failed"], timeout=180)
    tail = "\n".join((log or "").splitlines()[-VERDICT_LINES:])
    return jobs, (tail or "(--log-failed 无输出)")


def no_run_expired(now, first_seen, grace):
    """纯函数：`无 run 记录` 只有在宽限期之后才算结论。

    为什么必须有这道闸（首跑自抓）：刚 push 完的头几十秒里 GitHub **本来就还没登记 run**，
    把 NO_RUN 直接当终态 ⇒ 本工具第一次上岗就把一次正常推送报成 `UNVERIFIED`（实测 `2a20186`），
    属于"把没看到写成结论"的反面变体：看到空 ≠ 判完。宽限期后仍空才允许报未验证。
    """
    return (now - first_seen) > grace


def judge(sha, timeout, grace=180):
    t0 = time.time()
    deadline = t0 + timeout
    last = ""
    while time.time() < deadline:
        rows, why, failed = runs_for(sha)
        if failed:
            # 取数坏了就立刻如实报未验证：等宽限期只会把「我的 gh 不通」伪装成「GitHub 还没登记」，
            # 而后者会把人引去重推（无效动作），前者才是要修的那一半。
            print("CI-WATCH-UNVERIFIED | %s | %s ⇒ 取数失败不等于「没有 run」，更不得当通过"
                  % (sha[:8], why))
            return 2
        state, note = classify(rows)
        if state == "PENDING":
            last = note
            time.sleep(20)
            continue
        if state == "GREEN":
            print("CI-WATCH-GREEN | %s | %s" % (sha[:8], note))
            return 0
        if state == "NO_RUN":
            if no_run_expired(time.time(), t0, grace):
                print("CI-WATCH-UNVERIFIED | %s | 宽限 %ds 后仍无 run 记录（%s）⇒ 不得当通过；"
                  "若本机登记更慢，加大 --no-run-grace 或稍后重跑"
                  % (sha[:8], grace, why))
                return 2
            time.sleep(15)
            continue
        print("CI-WATCH-RED | %s | %s" % (sha[:8], note))
        for r in rows:
            if r.get("conclusion") in ("success", "skipped"):
                continue
            rid = r.get("databaseId")
            jobs, tail = red_detail(rid)
            print("  ── run %s 失败 job ──\n%s" % (rid, jobs))
            print("  ── 失败日志末 %d 行 ──\n%s" % (VERDICT_LINES, tail))
            print("  ── 下一步指令 ──\n"
                  "  1) 本地复跑：python _test/run_all_suites.py --exclude-llm（红名单以本地为准）\n"
                  "  2) 取该 run 的 annotations 原文：gh api repos/{owner}/{repo}/check-runs/<id>/annotations\n"
                  "  3) 判据带环境假设时按「先归因再降级」处理：换对账粒度定位首差，禁止抬 timeout 掩盖\n"
                  "  4) 修完必须重推并回到本命令复验，CI 绿才算收口")
        return 1
    print("CI-WATCH-UNVERIFIED | %s | 超时 %ds（%s）⇒ 未拿到结论，不得当通过" % (sha[:8], timeout, last))
    return 2


def selftest():
    bad = []
    cases = [
        ("GREEN", [{"status": "completed", "conclusion": "success"}], "GREEN"),
        ("PENDING", [{"status": "in_progress", "conclusion": ""}], "PENDING"),
        ("RED", [{"status": "completed", "conclusion": "failure", "databaseId": 1}], "RED"),
        ("NO_RUN", None, "NO_RUN"),
        ("混合(一绿一红)仍须判红", [{"status": "completed", "conclusion": "success"},
                                    {"status": "completed", "conclusion": "failure"}], "RED"),
        ("skipped 不算红", [{"status": "completed", "conclusion": "skipped"}], "GREEN"),
    ]
    for name, rows, want in cases:
        got, _note = classify(rows)
        if got != want:
            bad.append("%s：期望 %s 实得 %s" % (name, want, got))
    if classify([{"status": "completed", "conclusion": "success"}])[0] == "RED":
        bad.append("恒红")
    # NO_RUN 宽限期双向自证：窗口内不得结案（首跑就在这条上把一次正常推送报成未验证），
    # 窗口外必须结案（否则 run 永不出现时会一直等到超时）
    if no_run_expired(100.0, 60.0, 90):
        bad.append("宽限期内就结案 ⇒ 刚 push 的正常空窗被当成终态")
    if not no_run_expired(200.0, 60.0, 90):
        bad.append("宽限期外仍不结案 ⇒ NO_RUN 永不报警（run 一直不出现时静默）")
    # r83：`sh` 带回 stderr，且「取数失败」与「没有 run」必须是两条通道（两次真推都被报成后者）
    triple = sh([sys.executable, "-c", "import sys; sys.stderr.write('boom'); sys.exit(3)"])
    bad.append("sh 元数变了就必须同步改全部调用点") if len(triple) != 3 else None
    _rc3, _out3, _err3 = triple
    if not (_rc3 == 3 and "boom" in _err3):
        bad.append("stderr 没被带回来 ⇒ 失败原因仍会印成空括号")
    _rc4, _o4, _e4 = sh(["__definitely-not-a-command-xyz__"])
    if _rc4 != 127 or not _e4:
        bad.append("命令缺失一侧应给 127 且带原因（实得 rc=%s err=%r）" % (_rc4, _e4[:40]))
    _orig = globals()["runs_for"]
    try:
        globals()["runs_for"] = lambda s: (None, "gh run list 取数失败 rc=1｜stderr=boom", True)
        import io as _io
        import contextlib as _cl
        buf = _io.StringIO()
        with _cl.redirect_stdout(buf):
            rc_fail = judge("deadbeef", 5, grace=180)
        globals()["runs_for"] = lambda s: (None, "远端 list 取到 20 条，没有该 sha 的 run", False)
        buf2 = _io.StringIO()
        with _cl.redirect_stdout(buf2):
            # grace 给 -1 而不是 0：0 时同一 tick 可能 `now-t0 > 0` 为假 ⇒ 走 sleep(15) 撞穿 timeout，
            # 于是量到的是「超时」那条文案，测的就不是 NO_RUN 这一档了（本条第一次上线就是这么失配的）。
            rc_norun = judge("deadbeef", 5, grace=-1)
        got = buf.getvalue() + buf2.getvalue()
    finally:
        globals()["runs_for"] = _orig
    if rc_fail != 2 or "取数失败" not in got or "仍无 run 记录" in got.split("取数失败")[0]:
        bad.append("取数失败被并进「无 run」那一档（rc=%s）" % rc_fail)
    if rc_norun != 2 or "无 run 记录" not in got:
        bad.append("真「无 run」那一档反而不结案或文案错位（rc=%s）" % rc_norun)
    print("CI-WATCH-SELFTEST-%s（%d 态判定 + NO_RUN 宽限双向 + 恒红守卫 + 取数失败/无 run 分档 + stderr 带回）"
          % ("PASS" if not bad else "FAIL: " + "; ".join(bad), len(cases)))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sha", default="")
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--no-run-grace", type=int, default=180,
                    help="无 run 记录的容忍秒数（实测 90s 在本网络会误报：run 登记可晚于 90s）")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    sha = a.sha
    if not sha:
        rc, out, _err = sh(["git", "rev-parse", "HEAD"])
        if rc != 0:
            print("CI-WATCH-UNVERIFIED | 取不到 HEAD ⇒ 不判绿")
            return 2
        sha = out.strip()
    return judge(sha, a.timeout, a.no_run_grace)


if __name__ == "__main__":
    sys.exit(main())
