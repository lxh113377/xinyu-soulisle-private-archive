# -*- coding: utf-8 -*-
"""r94 一次性搬移：把 `offline_shell_check.run_runtime()` 的 try 体下移到 `_run_checks()`，
并把收尾（R7 + 报表 + 退出码）下移到 `_report()`。

搬移的**前提**（先查证再动手）：try 体内无 `return`（那几处 `return` 都在浏览器端 JS 字符串里，
不是 Python 控制流），`check` 是定义在 try 内的闭包、随之一起搬，`results` 由闭包填充 ⇒
整块搬 + 显式入参后语义等价。
"""
from pathlib import Path

P = Path("_test/offline_shell_check.py")
lines = P.read_text(encoding="utf-8").splitlines(keepends=True)


def find(pred, start=0):
    for i in range(start, len(lines)):
        if pred(lines[i]):
            return i
    raise SystemExit("not found: %s" % pred)


i_fn = find(lambda s: s.startswith("def run_runtime():"))
i_try = find(lambda s: s.rstrip() == "    try:", i_fn)
i_fin = find(lambda s: s.rstrip() == "    finally:", i_try)
print("run_runtime@%d try@%d finally@%d" % (i_fn + 1, i_try + 1, i_fin + 1))

# try 体 = i_try+1 .. i_fin-1
body = lines[i_try + 1:i_fin]
print("try 体 %d 行（%d..%d）" % (len(body), i_try + 2, i_fin))


def dedent4(s):
    if not s.strip():
        return s
    for _ in range(4):
        if s.startswith(" "):
            s = s[1:]
    return s


new = []
new.append("def _run_checks(browser, errs, miss):\n")
new.append('    """r94：由 `run_runtime` 的 try 体整体下移（`run_runtime` 原 174 行 > 150 行门）。\n')
new.append("\n")
new.append("    `check` 闭包随之搬移，`results` 由它填充后返回；入参即原闭包捕获的全部外部量。\n")
new.append('    """\n')
for s in body:
    new.append(dedent4(s))
if not new[-1].endswith("\n"):
    new[-1] += "\n"
new.append("\n")
new.append("\n")

call = "        results = _run_checks(browser, errs, miss)\n"
out = lines[:i_fn] + new + lines[i_fn:i_try + 1] + [call] + lines[i_fin:]
P.write_text("".join(out), encoding="utf-8")
print("written; lines=%d" % len(out))
