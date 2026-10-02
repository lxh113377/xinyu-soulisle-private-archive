# -*- coding: utf-8 -*-
"""r94 一次性搬移脚本：把 `docker_image_sim_check.main()` 的 try 体整体下移到 `_simulate()`。

为什么用脚本而不是手抄 124 行：整块移动 + 缩进重排是机械操作，手抄会引入错字；
脚本做完后由 `py_compile` + `git diff` 人审 + `--selftest` + 全量电池四道验。
"""
import io
from pathlib import Path

P = Path("_test/docker_image_sim_check.py")
lines = P.read_text(encoding="utf-8").readlines() if False else P.read_text(encoding="utf-8").splitlines(keepends=True)


def find(pred, start=0):
    for i in range(start, len(lines)):
        if pred(lines[i]):
            return i
    raise SystemExit("not found")


i_main = find(lambda s: s.startswith("def main() -> int:"))
i_try = find(lambda s: s.rstrip() == "    try:", i_main)
i_fin = find(lambda s: s.rstrip() == "    finally:", i_try)
print("main@%d try@%d finally@%d" % (i_main + 1, i_try + 1, i_fin + 1))

body = lines[i_try + 1:i_fin]
print("try 体 %d 行（%d..%d）" % (len(body), i_try + 2, i_fin))


def dedent4(s):
    if not s.strip():
        return s
    for _ in range(4):
        if s.startswith(" "):
            s = s[1:]
    return s


new_fn = []
new_fn.append("def _simulate(tmp, java, copies, envs, workdir, ignores, fails):\n")
new_fn.append('    """r94：由 `main()` 的 try 体整体下移而来（main 原 167 行 > loc_guard 的 150 行门）。\n')
new_fn.append("\n")
new_fn.append("    搬移的是**整块**，不是挑几行：try 体内无 `return`/`raise`，只往 `fails` 里追加，\n")
new_fn.append("    故语义等价于原来那段（依赖全部显式入参，不靠闭包捕获）。\n")
new_fn.append('    """\n')
for s in body:
    new_fn.append(dedent4(s))
if not new_fn[-1].endswith("\n"):
    new_fn[-1] += "\n"
new_fn.append("\n")
new_fn.append("\n")

call = "        _simulate(tmp, java, copies, envs, workdir, ignores, fails)\n"

out = (lines[:i_main] + new_fn + lines[i_main:i_try + 1] + [call] + lines[i_fin:])
P.write_text("".join(out), encoding="utf-8")
print("written; new file lines = %d" % len(out))
