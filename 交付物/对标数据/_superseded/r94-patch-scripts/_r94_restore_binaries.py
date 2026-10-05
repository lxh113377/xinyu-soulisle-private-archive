# -*- coding: utf-8 -*-
"""r94 事故恢复：把被误当文本归一的**二进制**文件从 git 恢复。

事故经过（自述）：`_r94_eol.py` 第一版用 `git check-attr` 判二进制，但
`subprocess.run(text=True)` 按 locale 编码解码 stdout，而 git 输出 UTF-8
⇒ 中文路径解码成乱码 ⇒ key 与 rel 不匹配 ⇒ 二进制判定全部失效
⇒ 15 个 PNG/ZIP/PDF/MP4 被当文本做了 CRLF→LF 改写（= 损坏）。

两条教训（比修 bug 本身更值钱）：
1. **凡「按路径匹配子进程输出」的代码，必须显式 `encoding="utf-8"`**。
   本仓已有同族判据（`gh` 走绝对路径、`date -u` 跨平台），这是第三条同族坑。
2. **破坏性批量操作必须先跑 dry-run 打印清单**，或先在副本上试。
   本脚本当时是「直接改」，没有 dry-run ⇒ 一次手滑就改了 15 个交付物。
"""
import subprocess

BIN_EXT = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".zip", ".pdf", ".pptx",
           ".docx", ".mp4", ".webm", ".mov", ".mp3", ".jar", ".db", ".woff", ".woff2", ".ttf")

out = subprocess.run(["git", "-c", "core.quotepath=off", "status", "--porcelain"],
                     capture_output=True, text=True, encoding="utf-8", cwd=".").stdout
targets = []
for line in out.splitlines():
    if len(line) < 4:
        continue
    code, path = line[:2], line[3:].strip().strip('"')
    if code.strip() != "M":
        continue
    if path.lower().endswith(BIN_EXT):
        targets.append(path)

print("待恢复二进制 %d 个：" % len(targets))
for p in targets:
    print("  -", p)
if not targets:
    raise SystemExit(0)

# 逐个恢复：一次 `git checkout -- <all>` 会因任一 pathspec 不匹配而整体失败（实测），
# 所以这里逐件执行并单独报成败。
ok, fail = 0, []
for p in targets:
    r = subprocess.run(["git", "checkout", "--", p], capture_output=True, text=True,
                       encoding="utf-8", cwd=".")
    if r.returncode == 0:
        ok += 1
    else:
        fail.append((p, (r.stderr or "").strip()[:80]))
print("恢复成功 %d / %d" % (ok, len(targets)))
for p, e in fail:
    print("  失败:", p, "→", e)
