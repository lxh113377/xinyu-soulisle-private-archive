# -*- coding: utf-8 -*-
"""后台测量的「退出码回执」包装件（r84 · 落地 07 台账 R77-01 的包装器侧）。

要拦的形态（本仓两次一手代价，07 台账在册）
------------------------------------------------
把一条测量丢到后台跑时，调度层的回执长这样：`completed (exit code 0)`，
而**被等对象的真 rc 只在你重定向出去的那个日志文件里**。r82 撞过一次（`PEERS_RC=1`，
peers 尺在收口处崩，漂移一条都没落进台账），r83 又撞一次（同一条 `run_all_suites` 的
退出码死在管道里）。两次都是「拿调度器的绿当判据的绿」。

它做什么
------------------------------------------------
1. 用 `subprocess.run(...).returncode` **直取**被包对象的退出码（不经任何管道），
   stdout+stderr 一起落到 `<out>.log`，并在**末尾追加一行 `NAME_RC=<rc>`**；
2. 往 stdout 只印一行门面收据：`RUN-LOGGED <name> rc=<rc> out=<绝对路径> bytes=<n>`，
   —— 值折进含判据词的那一行本身（本仓 CI 折叠日志只留末条判定行，明细进不去）；
3. 日志写不进（路径不可建）⇒ 判 `rc=2 UNVERIFIED`，**绝不回 0**（零输入/零落盘不判绿）。

用法
------------------------------------------------
    python _test/run_logged.py --name peers -- python _test/benchmark_metrics.py --cap-channel
    python _test/run_logged.py --name battery --out C:/tmp/b.log -- python _test/run_all_suites.py --exclude-llm
    python _test/run_logged.py --selftest
退出码：与被包对象**同码**（转发原样），另加 2 = 未验证（无法落盘 / 参数非法时由 main 直接判）。
"""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def log_path(name, out=None):
    """默认落 `%TEMP%/xinyu-bg-<name>.log`；显式 --out 优先。返回 Path 或 None（不可建）。"""
    import tempfile
    if out:
        p = Path(out)
        base = p if p.parent.exists() or str(p.parent) == "" else None
        if base is None:
            try:
                base.parent.mkdir(parents=True, exist_ok=True)
            except Exception:
                return None
            return base
        return p
    try:
        d = Path(tempfile.gettempdir())
        return d / ("xinyu-bg-%s.log" % name)
    except Exception:
        return None


def receipt_line(name, rc, path, nbytes):
    """门面收据：判定词与全部数值必须同一行（CI 只留末条判定行的形状）。"""
    return "RUN-LOGGED %s rc=%s bytes=%s out=%s" % (name, rc, nbytes, path)


def run_logged(name, argv, out=None, timeout=None):
    """跑一条命令并把**真退出码**写进日志尾行。返回 (rc, 收据行)。"""
    if not argv:
        return 2, "RUN-LOGGED-UNVERIFIED %s 没有要跑的命令 ⇒ 零输入不判绿" % name
    p = log_path(name, out)
    if p is None:
        return 2, "RUN-LOGGED-UNVERIFIED %s 落点建不出来 ⇒ 未验（不得当跑过了）" % name
    try:
        r = subprocess.run(argv, cwd=str(ROOT), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        rc = r.returncode                       # ← 直取，不经管道
        body = (r.stdout or "") + ("\n" if r.stdout and r.stderr else "") + (r.stderr or "")
    except Exception as e:                      # 起不来/超时也算一个真退出码，不许静默
        rc = 127
        body = "%s: %s" % (type(e).__name__, e)
    try:
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(body.rstrip("\n") + "\n")
            f.write("%s_RC=%s\n" % (name.upper(), rc))
        nbytes = len(p.read_bytes())
    except Exception as e:
        return 2, "RUN-LOGGED-UNVERIFIED %s 日志写失败（%s）⇒ 未验" % (name, type(e).__name__)
    return rc, receipt_line(name, rc, str(p), nbytes)


def selftest():
    """判据非恒真自证：每条正例配一条应当红的反向腿。"""
    import tempfile
    bad = []

    def ck(n, c):
        print("  %s %s" % ("OK " if c else "BAD", n))
        if not c:
            bad.append(n)

    d = Path(tempfile.mkdtemp(prefix="xinyu-runlogged-"))
    good, line = run_logged("t_good", [sys.executable, "-c", "print('hi')"], out=str(d / "g.log"))
    ck("①成功命令转发 rc=0 且行里带 bytes 与 out", good == 0 and "bytes=" in line and "out=" in line)
    body = (d / "g.log").read_text(encoding="utf-8")
    ck("②尾行是真退出码回执 %r" % body.splitlines()[-1:], body.splitlines()[-1] == "T_GOOD_RC=0")

    fail, _l2 = run_logged("t_bad", [sys.executable, "-c",
                                      "import sys;sys.stderr.write('boom\\n');sys.exit(3)"],
                           out=str(d / "b.log"))
    tail = (d / "b.log").read_text(encoding="utf-8").splitlines()[-1]
    ck("③失败命令必须转发非零（不是 0）%s/%s" % (fail, tail), fail == 3 and tail == "T_BAD_RC=3")
    ck("④stderr 也落进日志（原因不许丢）", "boom" in (d / "b.log").read_text(encoding="utf-8"))

    nz, line_nz = run_logged("t_nochild", [sys.executable, "-c", "pass"], out=str(d / "n.log"))
    (d / "n.log").write_text("被改过\n", encoding="utf-8")
    ck("⑤回读按字节而不是按回执（改过就该看出来）",
       not (d / "n.log").read_text(encoding="utf-8").endswith("T_NOCHILD_RC=0\n"))
    _rc6, line6 = run_logged("t_empty", [], out=str(d / "e.log"))
    ck("⑥零输入判未验，不得回 0", line6.startswith("RUN-LOGGED-UNVERIFIED"))
    # ⑦ 落点写不下去（父路径是个文件）⇒ 必须走 run_logged 的未验出口。
    #    ⚠️ 本腿第一版写成「断言 log_path 给 None」——实测不过：log_path 只问父目录在不在，
    #    文件也算"在"，坏点在**写的那一步**而不是取路径那一步。断言要打的是实际契约。
    blocker = d / "blocker.log"
    blocker.write_text("占位\n", encoding="utf-8")
    rc7, line7 = run_logged("t_nowrite", [sys.executable, "-c", "pass"],
                            out=str(blocker / "impossible.log"))
    ck("⑦落点写不下去 ⇒ rc=2 未验（不得回 0）%s" % line7[:40],
       rc7 == 2 and line7.startswith("RUN-LOGGED-UNVERIFIED"))
    missing, _l8 = run_logged("t_missing", [str(d / "definitely-not-here.exe")], out=str(d / "m.log"))
    ck("⑧起不来的命令给非零且落盘（127 类），不静默", missing != 0 and (d / "m.log").exists())

    import shutil
    shutil.rmtree(d, ignore_errors=True)
    if bad:
        print("RUN-LOGGED-SELFTEST-FAIL: %d 腿未过（%s）" % (len(bad), "；".join(bad)))
        return 1
    print("RUN-LOGGED-SELFTEST-PASS: 8 腿全过（转发真 rc／stderr 落盘／零输入与落点坏都判未验）")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="cmd")
    ap.add_argument("--out", default="")
    ap.add_argument("--timeout", type=float, default=None)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    cmd = list(a.cmd or [])
    if cmd and cmd[0] == "--":
        cmd = cmd[1:]
    rc, line = run_logged(a.name, cmd, a.out or None, a.timeout)
    print(line)
    return rc


if __name__ == "__main__":
    sys.exit(main())
