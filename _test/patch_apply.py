# -*- coding: utf-8 -*-
"""结构化补丁器（r25 造）：让「改文件」这件事本身有判据，不再靠每轮记得住。

为什么存在（同族坑连续三轮复发，实测留痕）：
  r23  判据阈值 `done >= 8`，真实操作 11 条 ⇒ 永远绿；
  r24  `cp ... 2>/dev/null` 把 index.html 复制进 js/ ⇒ stderr 被吞，deploy_sync 才抓到；
  r25  `str.replace("4_355", ...)` 锚点与文件实际 `4355` 不匹配 ⇒ **未命中却打印"已登记"**。
三条同根：**把"命令没报错"当成"事情生效了"**。`str.replace` 不命中时静默返回原串，是这类事故最典型的载体。

用法：
  python _test/patch_apply.py --file <路径> --find <旧串> --repl <新串> [--count N] [--expect-count N] [--dry-run]
  python _test/patch_apply.py --selftest            # 自证判据非恒真（三类必失败样本）
约束：命中数必须 == 期望数（默认 1），**锚点 0 命中直接失败**，替换后再读回断言"新内容在、旧内容不在"；
      写前先备份到系统临时目录（不改仓库、不留散落物），失败即回滚。退出码 0=成功 1=拒绝/失败 2=用法或环境错。
"""
import argparse
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")


def apply_patch(path, find, repl, expect_count=1, count=-1, dry=False, quiet=False):
    """返回 (rc, 说明)。任何一步不满足都**不写盘**（或写后回滚）。"""
    p = Path(path)
    if not p.exists():
        return 2, f"文件不存在：{p}"
    try:
        original = p.read_text("utf-8")
    except Exception as e:
        return 2, f"读取失败：{e}"
    hits = original.count(find)
    if hits == 0:
        return 1, f"锚点 0 命中 ⇒ 补丁不会生效（这正是 r25 那次静默失败）：{find[:60]!r}"
    if hits != expect_count:
        return 1, f"锚点命中 {hits} 次，期望 {expect_count} 次 ⇒ 拒绝盲改（歧义锚点）"
    new = original.replace(find, repl, count if count > 0 else -1)
    if new == original:
        return 1, "替换后内容与原文完全相同 ⇒ 视为无效补丁（禁止打印'已修改'）"
    if repl not in new:
        return 1, "替换结果里找不到新串（内部不一致，拒绝写盘）"
    # 只在「repl 本身不含锚点」时才对残留旧锚点报红 —— 插入型补丁（repl 里合法保留原句）不该被拦，
    # 这条判据第一版写死了，dogfood 第一个真活就被自己的工具误拒（README 加一行命令）。
    if find not in repl and find in new:
        return 1, "单次替换后旧锚点仍在且新串不含锚点 ⇒ 可能只改了副本，拒绝"
    if dry:
        return 0, f"[dry-run] 可替换 {hits} 处，字节 {len(original)} → {len(new)}（未写盘）"
    bak = Path(tempfile.gettempdir()) / f"patch_apply_{p.name}.{datetime.now():%Y%m%d%H%M%S}.bak"
    shutil.copy2(p, bak)
    try:
        p.write_text(new, "utf-8")
        back = p.read_text("utf-8")          # 读回复验：写成功 ≠ 内容对
        if back != new:
            shutil.copy2(bak, p)
            return 1, f"写后读回不一致 ⇒ 已回滚（备份 {bak.name}）"
    except Exception as e:
        shutil.copy2(bak, p)
        return 1, f"写入异常已回滚：{e}（备份 {bak.name}）"
    if not quiet:
        print(f"PATCH-OK {p.name} 命中 {hits} 处，备份 {bak.name}")
    return 0, f"命中 {hits} 处；备份 {bak}"


def selftest():
    """在临时目录造样本，证明三类失败一定被拦住、正常路径一定通过。"""
    d = Path(tempfile.mkdtemp(prefix="patch_apply_stub_"))
    f = d / "t.txt"
    f.write_text("alpha 4355 beta\n", "utf-8")
    bad = []
    rc, _ = apply_patch(f, "4_355", "X", quiet=True)
    if rc != 1:
        bad.append(f"①锚点不匹配未被拦（rc={rc}）⇒ 判据恒绿")
    if "4_355" in f.read_text("utf-8") or "X" in f.read_text("utf-8"):
        bad.append("①场景下文件被改动了（应完全不动）")
    rc, _ = apply_patch(f, "a", "Z", quiet=True)
    if rc != 1:
        bad.append(f"②歧义锚点多命中未被拦（rc={rc}）")
    rc, _ = apply_patch(f, "4355", "4355", quiet=True)
    if rc != 1:
        bad.append(f"③替换前后相同未被拦（rc={rc}）")
    rc, _ = apply_patch(f, "4355", "3969", quiet=True)
    if rc != 0 or "3969" not in f.read_text("utf-8"):
        bad.append(f"④正常路径失败（rc={rc}）")
    rc2, _ = apply_patch(f, "beta", "beta-tail", quiet=True)   # 插入型：repl 合法包含锚点（第一版被误拒的真场景）
    if rc2 != 0:
        bad.append("⑥插入型补丁被误拒 ⇒ 判据过严（真事故：README 加一行命令时被自己工具拦下）")
    rc, _ = apply_patch(d / "nope.txt", "x", "y", quiet=True)
    if rc != 2:
        bad.append(f"⑤文件不存在应 rc=2（实际 {rc}）")
    print("SELFTEST-PASS: 锚点失配/歧义/同义/插入/正常/缺失 六类行为均正确" if not bad
          else "SELFTEST-FAIL: " + "; ".join(bad))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file")
    ap.add_argument("--find")
    ap.add_argument("--repl")
    ap.add_argument("--count", type=int, default=-1)
    ap.add_argument("--expect-count", type=int, default=1)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest())
    if not a.file or a.find is None or a.repl is None:
        print("用法错误：--file/--find/--repl 必填（或用 --selftest）")
        sys.exit(2)
    rc, msg = apply_patch(a.file, a.find, a.repl, a.expect_count, a.count, a.dry_run)
    print(("OK  " if rc == 0 else "FAIL") + " " + msg)
    sys.exit(rc)


if __name__ == "__main__":
    main()
