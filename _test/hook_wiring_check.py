# -*- coding: utf-8 -*-
"""交付面在位闸的「接线回执」（r83）——管的是钩子本身，不是交付件。

为什么需要它（一手代价，不是假想需求）
------------------------------------------------
r82 入场实测 `git status` 有 7 条 ` D`（含 22,954,501 B 参赛成片），补上的「入库件在位」腿
**只在电池/CI 里跑**，而丢失是在两次提交之间发生的 ⇒ 那一轮 7 件是会话开场才看见的。
本轮把它接到 `pre-commit`（`_test/hooks/pre-commit`）。但「装了钩子」这件事本身会漂：
`.git/hooks/` 不在 git 跟踪面里，别人 clone 完不装就等于没装，改了源副本不重装就是两套语法。
**没有接线回执的门禁等于半成品**（本仓既有纪律），所以本件量三件事：
  W1 源在位：`_test/hooks/pre-commit` 存在、非空、`sh -n` 解析得动（解析不了 ⇒ 钩子根本不会跑）
  W2 副本 == 源：`.git/hooks/pre-commit` 按字节等于源（漂了就是「装的是旧的那份」）
  W3 钩子真会拦：`--drill` 用一次真注入（删一件已入库交付件 → 跑钩子 → 必须 rc=1 且点名该路径 → 复原）

fail-open 是设计而非缺陷：判据取不到数（rc=2）或找不到解释器时，钩子**放行并报警**。
理由是共享工作树里有并行会话 —— 工具故障没有资格拦下别人的提交（那会逼他人为不属于他的红收口）。
CI（新克隆）里 W2 记 `未验` 而不是红：那面上没有任何人有权 `git config`/装钩子。

退出码：0=接线齐 1=判红（源坏 / 副本漂 / 演习没咬人）2=未验（无 .git / 无 sh / CI）
用法：python _test/hook_wiring_check.py [--install] [--drill] [--selftest]
"""
import hashlib
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_HOOK = ROOT / "_test" / "hooks" / "pre-commit"
INVENTORY = ROOT / "_test" / "deliverable_inventory_check.py"
CHECKLIST_REL = "交付物/提交包/提交清单与验收状态.md"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:12]


def git_dir(root=None):
    """返回 .git 目录（worktree 也认），取不到给 None（调用方按未验处理，禁判绿）。"""
    r = subprocess.run(["git", "-C", str(root or ROOT), "rev-parse", "--git-dir"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        return None
    p = Path(r.stdout.strip())
    return p if p.is_absolute() else (root or ROOT) / p


def hook_verdict(rc: int) -> str:
    """纯函数：判据退出码 → 钩子动作。三态之外一律 CRASH（r82 实测把硬崩判成「环境未验」= 通行证）。"""
    if rc == 0:
        return "pass"
    if rc == 1:
        return "block"
    if rc == 2:
        return "unverified"
    return "crash"


def install_plan(src_bytes, installed_bytes, ci=False):
    """纯函数：返回 (action, bad, unver)。
    action: install / ok / drift / missing / unver
    「该不该红」与「取没取到数」分开判，禁把取不到读成通过。
    """
    bad, unver = [], []
    if src_bytes is None:
        return "missing", ["钩子源不存在: _test/hooks/pre-commit"], unver
    if not src_bytes.startswith(b"#!/"):
        return "missing", ["钩子源没有 shebang ⇒ git 不会执行它"], unver
    if len(src_bytes) < 200:
        return "missing", ["钩子源短得不像一份能跑的检查（%d B）⇒ 疑被截断" % len(src_bytes)]
    if installed_bytes is None:
        if ci:
            return "unver", bad, ["CI 面（新克隆）：本地钩子无处可装 ⇒ W2 未验，不判绿也不判红"]
        return "missing", ["已跟踪的钩子没装到 .git/hooks/pre-commit ⇒ 这一面其实没接线"], unver
    if installed_bytes != src_bytes:
        return "drift", ["装在 .git 里的钩子与跟踪源不同字节（源 sha=%s 装=%s）⇒ 改源没重装"
                         % (sha(src_bytes), sha(installed_bytes))], unver
    return "ok", bad, unver


def read_bytes(p):
    try:
        return Path(p).read_bytes()
    except Exception:
        return None


GIT_BASH_CANDIDATES = (r"C:\Program Files\Git\usr\bin\bash.exe",
                       r"C:\Program Files\Git\bin\bash.exe")
WSL_LAUNCHER_MARKS = ("\\system32\\bash.exe", "\\windowsapps\\bash.exe")


def sh_exe():
    """挑一个能把 POSIX 脚本跑起来的解释器（r85 修复：原实现会把 WSL 启动器当选）。

    实测根因（2026-09-30 23:xx 电池当场红出来的，不是推断）：本机 `shutil.which("sh")` = **None**，
    于是回退到 `shutil.which("bash")` = `C:\\Windows\\system32\\bash.EXE` —— 那是 **WSL 启动器**，
    它不吃 `C:\\...` 形态的路径（反斜杠被当转义吃掉 ⇒ 实参变成 `C:Users37533...` ⇒ rc=127），
    于是 W1（源解析不过）与 selftest 的 ⑪⑫（端到端删件腿 / 复原腿）**三条一起红**。
    红因不是钩子坏了 —— 钩子源与副本 W2 仍逐字节相等 —— 是**喂给解释器的路径形态不对**。

    处置两条，都不放宽判据：① 优先 Git 自带 bash（吃 Windows 路径，本机两处均在位）；
    ② 只剩 WSL 启动器时才把路径转成 `/mnt/<盘符>/...`（见 `path_for_sh`）。解析不过仍旧判红。
    """
    for p in GIT_BASH_CANDIDATES:
        if os.path.isfile(p):
            return p
    return shutil.which("sh") or shutil.which("bash")


def is_wsl_launcher(exe):
    low = (exe or "").lower()
    return any(m in low for m in WSL_LAUNCHER_MARKS)


def path_for_sh(exe, p):
    """把路径转成该解释器吃得下的形态：WSL 启动器要 `/mnt/c/...`，其余照原样（Git bash 吃 `C:\\...`）。

    刻意做成纯函数并可注入 —— 判据自己得先证明"路径形态"这件事被真的处理过，
    否则它和 r84 那条「看 CI 的眼瞎了」同族：把环境形态问题报成被检对象坏了。
    """
    s = str(p)
    if not is_wsl_launcher(exe):
        return s
    m = re.match(r"^([A-Za-z]):[\\/](.*)$", s)
    if not m:
        return s
    return "/mnt/%s/%s" % (m.group(1).lower(), m.group(2).replace("\\", "/"))


def check() -> int:
    ci = bool(os.environ.get("CI"))
    bad, unver, notes = [], [], []

    # W1 源在位 + 解析得动
    src = read_bytes(SRC_HOOK)
    if src is None:
        bad.append("W1 钩子源不存在：%s" % SRC_HOOK.relative_to(ROOT))
    else:
        exe = sh_exe()
        if exe is None:
            unver.append("W1 本机没有 sh/bash ⇒ 没验证钩子能不能解析（未验）")
        else:
            r = subprocess.run([exe, "-n", path_for_sh(exe, SRC_HOOK)], capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
            if r.returncode != 0:
                bad.append("W1 钩子源解析不过（sh -n rc=%d）：%s" % (r.returncode, (r.stderr or "").strip()[:200]))
            else:
                notes.append("W1 源 %d B、sh -n 通过" % len(src))

    # W2 副本 == 源
    gd = git_dir()
    installed = read_bytes(gd / "hooks" / "pre-commit") if gd else None
    if gd is None:
        unver.append("W2 取不到 .git 目录 ⇒ 副本对账未验（禁把「没量到」读成「都装好了」）")
    action, b2, u2 = install_plan(src, installed, ci=ci)
    bad += b2
    unver += u2
    if action == "ok":
        notes.append("W2 副本 == 源（sha=%s）" % sha(src))
    elif action == "missing" and gd is None:
        unver.append("W2 无 .git ⇒ 未验")
        bad = [x for x in bad if not x.startswith("已跟踪的钩子没装")]

    # W3 拦截面（不做真注入；真注入走 --drill，避免在共享工作树里动别人的面）
    inv = read_bytes(INVENTORY)
    if inv is None:
        bad.append("W3 被拦判据不存在：%s" % INVENTORY.relative_to(ROOT))
    else:
        for token in (b"tracked_missing_check", b"committed_blobs", b"parse_ls_tree"):
            if token not in inv:
                bad.append("W3 判据里找不到 %s ⇒ 钩子调的是一个不再提供该腿的对象" % token.decode())
        if not any(t in inv for t in (b"DELIVERABLE-INVENTORY-UNVERIFIED",)):
            bad.append("W3 判据不再回 UNVERIFIED 三态 ⇒ 钩子的 fail-open 前提失效")
        else:
            notes.append("W3 判据三态在位（pass/block/unverified）")

    for n in notes:
        print("  · " + n)
    for b in bad:
        print("  ✗ " + b)
    for u in unver:
        print("  ? " + u)
    tail = "源=%s 装=%s 未验=%d" % ("在位" if src else "缺失",
                                  ("一致" if action == "ok" else action) , len(unver))
    if bad:
        print("HOOK-WIRING-FAIL: %d 条接线缺口（%s）" % (len(bad), tail))
        return 1
    if unver:
        print("HOOK-WIRING-UNVERIFIED: 零缺口但 %d 项未验（%s）" % (len(unver), tail))
        return 2
    print("HOOK-WIRING-PASS: pre-commit 源与副本同字节、sh -n 通过、被拦判据三态在位（%s）" % tail)
    return 0


def install() -> int:
    """把跟踪源装进 .git/hooks/pre-commit，并**读回**证明装的 == 声明的。"""
    gd = git_dir()
    if gd is None:
        print("HOOK-INSTALL-UNVERIFIED: 取不到 .git 目录（不在仓库里？）")
        return 2
    src = read_bytes(SRC_HOOK)
    if src is None:
        print("HOOK-INSTALL-FAIL: 源不存在 %s" % SRC_HOOK)
        return 1
    dst = gd / "hooks" / "pre-commit"
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        cur = dst.read_bytes()
        if cur == src:
            print("HOOK-INSTALL-PASS: 已一致，未改写（sha=%s）" % sha(src))
            return 0
        bak = dst.with_name("pre-commit.bak-%s" % sha(cur))
        bak.write_bytes(cur)
        print("HOOK-INSTALL: 原有钩子与源不同，已备份到 %s" % bak.name)
    dst.write_bytes(src)
    os.chmod(dst, 0o755)
    back = dst.read_bytes()
    if back != src:
        print("HOOK-INSTALL-FAIL: 写后回读不等（写=%s 读=%s）" % (sha(src), sha(back)))
        return 1
    print("HOOK-INSTALL-PASS: 装好并读回一致 sha=%s｜复算 python _test/hook_wiring_check.py" % sha(src))
    return 0


def drill() -> int:
    """真注入演习：删掉一件「已入库、且没写进清单声明面」的交付件 ⇒ 钩子必须 rc=1 且点名它。
    任何一步失败都在 finally 里按字节复原并复验（演习不得留下脏树，哪怕判红）。
    """
    exe, gd = sh_exe(), git_dir()
    if exe is None or gd is None:
        print("HOOK-DRILL-UNVERIFIED: 缺 sh 或 .git ⇒ 演习跑不了（未验）")
        return 2
    # 靶子直接复用被拦判据自己的取数面（不在这里另写一套 git 解析：
    # 裸 `ls-tree --name-only` 会把 CJK 路径转义成 "\344\272\244..."，那种串根本不是路径）。
    sys.path.insert(0, str(ROOT / "_test"))
    try:
        import deliverable_inventory_check as inv
    except Exception as exc:
        print("HOOK-DRILL-UNVERIFIED: 载不进被拦判据 %s ⇒ 演习没打到靶（不算过）" % type(exc).__name__)
        return 2
    entries, skipped = inv.committed_blobs()
    if not entries:
        print("HOOK-DRILL-UNVERIFIED: HEAD 入库面取到 0 条（skipped=%d）⇒ 没靶子" % skipped)
        return 2
    declared = set()
    if inv.CHECKLIST.is_file():
        declared = set(inv.declared_paths(inv.table_rows(inv.CHECKLIST.read_text(encoding="utf-8"))))
    cands = [(p, s) for (p, s) in entries
             if p not in declared and (ROOT / p).is_file() and s > 0]
    if not cands:
        print("HOOK-DRILL-UNVERIFIED: 找不到「已入库但未声明」的可删样本（入库 %d 条 / 声明 %d 条）"
              "⇒ 演习没打到靶（不算过）" % (len(entries), len(declared)))
        return 2
    victim, _vsz = min(cands, key=lambda ps: ps[1])
    hook = gd / "hooks" / "pre-commit"
    if not hook.is_file():
        print("HOOK-DRILL-FAIL: 钩子没装（先 --install）")
        return 1
    before = (ROOT / victim).read_bytes()
    print("HOOK-DRILL: 靶=%s（%d B，未写进声明面）" % (victim, len(before)))
    try:
        (ROOT / victim).unlink()
        p = subprocess.run([exe, path_for_sh(exe, hook)], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", cwd=str(ROOT))
        out = (p.stdout or "") + (p.stderr or "")
        if p.returncode == 0:
            print("HOOK-DRILL-FAIL: 删掉一件未声明的入库交付件后钩子仍 rc=0 ⇒ 不咬人")
            return 1
        if p.returncode != 1:
            print("HOOK-DRILL-FAIL: 期望 rc=1，实得 rc=%d（CRASH 或未验也算没接线）" % p.returncode)
            print(out[-400:])
            return 1
        if victim not in out:
            print("HOOK-DRILL-FAIL: 拦下了却没点名被删件 ⇒ 红因不可归因（%s）" % victim)
            return 1
        print("  ✓ 拦截并点名：%s" % victim)
    finally:
        (ROOT / victim).write_bytes(before)
    if (ROOT / victim).read_bytes() != before:
        print("HOOK-DRILL-FAIL: 复原后字节不等 ⇒ 演习动了真件")
        return 1
    p2 = subprocess.run([exe, path_for_sh(exe, hook)], capture_output=True, text=True,
                        encoding="utf-8", errors="replace", cwd=str(ROOT))
    if p2.returncode != 0:
        print("HOOK-DRILL-FAIL: 复原后钩子仍不绿 ⇒ 判据或钩子有存量红：%s" % ((p2.stdout or "") + (p2.stderr or ""))[-400:])
        return 1
    print("HOOK-DRILL-PASS: 删⇒拦（rc=1 且点名）／复原⇒绿（rc=0），树按字节复原（sha=%s）" % sha(before))
    return 0


def selftest() -> int:
    """判据非恒真自证：每个正例都配一个「应当红」的反例。"""
    bad = []

    def ck(name, cond):
        print("  %s %s" % ("OK " if cond else "BAD", name))
        if not cond:
            bad.append(name)

    src = b"#!/bin/sh\n" + b"x" * 400
    ck("①源与副本同字节 ⇒ ok", install_plan(src, src)[0] == "ok")
    ck("②副本漂了一个字节 ⇒ drift（改源没重装必须红）",
       install_plan(src, src + b" ")[0] == "drift")
    ck("③源在副本不在 ⇒ missing", install_plan(src, None)[0] == "missing")
    ck("④同样「不在」但在 CI ⇒ unver 且零红（新克隆没人能装）",
       (lambda a: a[0] == "unver" and not a[1])(install_plan(src, None, ci=True)))
    ck("⑤源缺失 ⇒ missing 且判红（不许静默当没接线）",
       install_plan(None, src)[0] == "missing" and len(install_plan(None, src)[1]) == 1)
    ck("⑥没有 shebang ⇒ 判红（git 不会执行它）",
       install_plan(b"echo hi" + b"x" * 400, None)[0] == "missing")
    ck("⑦源被截断成一行 ⇒ 判红（副本再一致也不绿）",
       install_plan(b"#!/bin/sh\necho ok\n", None)[0] == "missing")
    ck("⑧零输入（源与副本都取不到）⇒ 绝不 ok", install_plan(None, None)[0] != "ok")
    ck("⑨rc 三态映射", hook_verdict(0) == "pass" and hook_verdict(1) == "block"
       and hook_verdict(2) == "unverified")
    ck("⑩硬崩不并入未验（r82 那条通行证）", hook_verdict(3221225773) == "crash")

    # 端到端反向腿：在临时 git 仓里装**真钩子源**，删一件已入库件 ⇒ 必须 rc=1。
    # 这里能跑通是因为钩子按 `git rev-parse --show-toplevel` 定位根，不依赖本仓的清单内容。
    import tempfile
    exe = sh_exe()
    tmp = None
    if exe is None:
        print("  ?  端到端腿未跑（本机没有 sh/bash）⇒ 记未验，不得算进通过腿数")
    else:
        tmp = Path(tempfile.mkdtemp(prefix="xinyu-hook-selftest-")) / "repo"
        try:
            (tmp / "_test" / "hooks").mkdir(parents=True)
            (tmp / CHECKLIST_REL).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(SRC_HOOK, tmp / "_test" / "hooks" / "pre-commit")
            shutil.copyfile(INVENTORY, tmp / "_test" / INVENTORY.name)
            (tmp / CHECKLIST_REL).write_text("# 夹具清单\n\n| 件 | 路径 |\n|---|---|\n", encoding="utf-8")
            (tmp / "交付物" / "提交包" / "ghost.txt").write_text("在位证明\n", encoding="utf-8")
            for c in (["init", "-q"], ["-c", "user.email=t@t", "-c", "user.name=t", "add", "-A"],
                      ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "fixture"]):
                subprocess.run(["git"] + c, cwd=str(tmp), capture_output=True, text=True)
            installed = tmp / ".git" / "hooks" / "pre-commit"
            installed.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(tmp / "_test" / "hooks" / "pre-commit", installed)
            os.chmod(installed, 0o755)
            ghost = tmp / "交付物" / "提交包" / "ghost.txt"
            ghost.unlink()
            hit = subprocess.run([exe, path_for_sh(exe, installed)], cwd=str(tmp),
                                 capture_output=True, text=True, encoding="utf-8", errors="replace")
            ck("⑪端到端反向腿：删掉入库件 ⇒ 钩子 rc=1（真跑出来的，不是推断的）",
               hit.returncode == 1 and "ghost.txt" in (hit.stdout + hit.stderr))
            ghost.write_text("在位证明\n", encoding="utf-8")
            ok = subprocess.run([exe, path_for_sh(exe, installed)], cwd=str(tmp),
                                capture_output=True, text=True, encoding="utf-8", errors="replace")
            ck("⑫复原后台闸必须自证取到数（rc=0 或 2，不许 1）", ok.returncode in (0, 2))
        finally:
            shutil.rmtree(tmp.parent, ignore_errors=True)

    # ⑬–⑮：r85 修的那条「解释器吃哪种路径形态」必须自己被钉住，否则下次环境再漂一次
    #        它又会回来，而红因仍然会写成像"钩子坏了"（本仓已有三次同族：CSP 闸看不见 CSP /
    #        ci_watch 分不清取数失败与没有 run / 清单路径被当成声明件）。
    ck("⑬WSL 启动器必须收 /mnt/<盘符>/ 形态（反斜杠不得被当转义吃掉）",
       path_for_sh(r"C:\Windows\System32\bash.EXE", r"C:\repo\_test\hooks\pre-commit")
       == "/mnt/c/repo/_test/hooks/pre-commit")
    ck("⑭Git bash 照原样收 Windows 路径（不得画蛇添足地转换）",
       path_for_sh(r"C:\Program Files\Git\usr\bin\bash.exe", r"C:\repo\x") == r"C:\repo\x")
    ck("⑮只有真 WSL 启动器才转换（`bash` 这串不得误命中）",
       (not is_wsl_launcher(r"C:\tools\bash.exe")) and is_wsl_launcher(r"C:\Windows\system32\bash.EXE"))

    n = (12 + 3) if exe else (10 + 3)
    if bad:
        print("HOOK-WIRING-SELFTEST-FAIL: %d/%d 未过（%s）" % (len(bad), n, "；".join(bad)))
        return 1
    print("HOOK-WIRING-SELFTEST-PASS: %d 腿全过（含「副本漂一字节必须红」「CI 不判红」「硬崩不并入未验」"
          "与端到端删件真被拦四向）" % n)
    return 0


if __name__ == "__main__":
    argv = sys.argv[1:]
    if "--selftest" in argv:
        sys.exit(selftest())
    if "--install" in argv:
        sys.exit(install())
    if "--drill" in argv:
        sys.exit(drill())
    sys.exit(check())
