# -*- coding: utf-8 -*-
"""r94 步骤①：把 a11y 的键盘探针 JS 提到模块级 `_JS_KB`（单独一步，避免多段改写索引漂移）。"""
from pathlib import Path

P = Path("_test/a11y_check.py")
lines = P.read_text(encoding="utf-8").splitlines(keepends=True)

i0 = next(i for i, s in enumerate(lines) if 'kb = pg.evaluate("""' in s)
i1 = next(i for i in range(i0, len(lines)) if lines[i].strip() == '}""")')
print("JS 段 %d..%d（%d 行）" % (i0 + 1, i1 + 1, i1 - i0 + 1))

body = []
for s in lines[i0 + 1:i1]:
    body.append(s.rstrip("\n"))

i_main = next(i for i, s in enumerate(lines) if s.startswith("def main("))
const = ["# r94：键盘可达性探针的浏览器端脚本提到模块级（原在 `main` 内占 15 行，是该函数据\n",
         "# loc_guard 函数长门超标的原因之一）。搬的是**字符串常量**，无变量捕获，行为不变。\n",
         '_JS_KB = """() => {\n'] + body + ['}"""\n', '\n', '\n']

# ⚠️ 先做替换拿到新行表，再在新行表里找 `def main(` 插入常量 —— 上一版拿**旧** i_main 去切
# `lines[i1+1:i_main]`（i1 > i_main ⇒ 空切片），结果把 main 整段复制了一遍（571 行）。
new_lines = lines[:i0] + ['        kb = pg.evaluate(_JS_KB)\n'] + lines[i1 + 1:]
i_main2 = next(i for i, s in enumerate(new_lines) if s.startswith("def main("))
out = new_lines[:i_main2] + const + new_lines[i_main2:]
P.write_text("".join(out), encoding="utf-8")
print("written; lines=%d" % len(out))
