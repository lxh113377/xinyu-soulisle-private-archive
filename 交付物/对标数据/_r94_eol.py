# -*- coding: utf-8 -*-
"""r94：工作树字节归一（CRLF → LF）——**自包含 + 默认 dry-run** 版。

本脚本有前两版：第一版逐文件调 check-attr（慢到被使用者打断）；第二版批量但**没显式编码**，
`text=True` 按 locale 解码 git 的 UTF-8 输出 ⇒ 中文路径乱码 ⇒ 二进制判定失效
⇒ **15 个 PNG/ZIP/PDF/MP4 被当文本改写**（已全部从 git 恢复）。事故复盘见
`交付物/对标数据/_r94_restore_binaries.py` 的 docstring。

本版三条硬规矩（每条都对应一次真实事故）：
1. **凡「按路径匹配子进程输出」的代码必须显式 `encoding="utf-8"`**（事故 2 的根因）。
2. **默认 dry-run，改盘要显式 `--apply`**（事故 2 的放大器：当时是直接改，没有清单）。
3. **内容兜底**：前 8KB 含 NUL 一律当二进制，即便 git 属性没声明 ——
   属性表会漏，字节不会；而「改坏二进制」是**不可逆的交付物损坏**。
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NUL = b"\0"
APPLY = "--apply" in sys.argv[1:]

TEXT_EXT = (".py", ".md", ".json", ".js", ".mjs", ".ts", ".html", ".css", ".yml", ".yaml",
            ".txt", ".sh", ".ps1", ".java", ".xml", ".csv", ".svg", ".gitattributes")


def git_z(*args):
    out = subprocess.run(["git", "-c", "core.quotepath=off", *args, "-z"],
                         capture_output=True, cwd=str(ROOT), check=True).stdout
    return [x.decode("utf-8") for x in out.split(NUL) if x]


def looks_binary(path: Path) -> bool:
    """内容兜底：前 8KB 见 NUL 即二进制（属性表会漏，字节不会）。"""
    with path.open("rb") as fh:
        return NUL in fh.read(8192)


def main():
    tracked = git_z("ls-files")
    untracked = git_z("ls-files", "--others", "--exclude-standard")
    print("模式：%s｜扫描面：已跟踪 %d + 未入库 %d" % ("APPLY" if APPLY else "DRY-RUN",
                                                  len(tracked), len(untracked)))
    n, skipped = 0, 0
    for rel in sorted(set(tracked) | set(untracked)):
        f = ROOT / rel
        if not f.is_file():
            continue
        if not rel.lower().endswith(TEXT_EXT):     # 第一道闸：只碰文本类扩展名
            skipped += 1
            continue
        if looks_binary(f):                        # 第二道闸：内容含 NUL ⇒ 绝不碰
            skipped += 1
            continue
        b = f.read_bytes()
        if b"\r\n" not in b:
            continue
        n += 1
        print("  %s %-58s CRLF %d 处" % ("归一" if APPLY else "待归一", rel, b.count(b"\r\n")))
        if APPLY:
            f.write_bytes(b.replace(b"\r\n", b"\n"))
    print("共 %s %d 个文件（按扩展名/内容闸跳过 %d 个）"
          % ("归一" if APPLY else "**待**归一", n, skipped))
    if not APPLY and n:
        print("提示：这是 dry-run；确认清单无误后加 --apply 真改。")


if __name__ == "__main__":
    main()
