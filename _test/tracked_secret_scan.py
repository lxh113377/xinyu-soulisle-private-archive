# -*- coding: utf-8 -*-
"""跟踪文件密钥形态扫描（对标轮 r35 新增）—— 与 CI 密钥门禁**同一把尺**，且本地也跑。

为什么要有这个文件（r35 一手实测归因）：
  CI 的密钥门禁原先把正则**内联**在 `.github/workflows/ci.yml` 里，扫 `git ls-files`；
  本地电池只有 `public_check`（扫交付副本）。于是"某个被跟踪的脚本里写了密钥形态字面量"
  这一类缺陷**只在 CI 暴露** —— 实测 `_test/pdf_leak_scan.py` 的自测样本串（`sk-` + 24 位）
  让同步守卫 job 连红多轮，而本机 37 条套件全绿。
  这正是 consulting 口径 M5(6)「同一判断只有一处实现 ⇒ 改宽一份另一份不跟上」的形态。
  修法 = 把判定收进本文件这一处，CI 与本地电池都调它，正则不再散落。

判据：
  T1 分母非空：`git ls-files` 必须列出文件（列不到 ⇒ 扫描在读空气，判红不判绿）
  T2 命中即红：任一被跟踪文件含密钥形态 ⇒ 逐条打印 路径:行号 并 rc=1
  T3 对照组（--selftest）：拼接出来的样本必须被抓到 / 正则文本自身与短串不得自伤 / 空输入零命中

用法：python _test/tracked_secret_scan.py [--selftest]
"""
import re
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]

# 与 CI 完全一致的一条正则。注意：本行文本自身不会命中它（`sk-` 后面紧跟的是 `[`，不是字母数字）。
KEY_RE = re.compile(r"sk-[A-Za-z0-9]{20,}")


def scan_text(text):
    """纯函数：返回命中行号列表（1 起）。"""
    return [i for i, line in enumerate(text.splitlines(), 1) if KEY_RE.search(line)]


def tracked_files():
    """被 git 跟踪的文件清单（NUL 分隔，兼容中文路径）。

    一律以仓库根为基准：`cwd` 不在仓库根时相对路径全部读不到 —— 若放任不管，
    本判据会把 215 个文件全报"读不到"然后打印 PASS（**假绿**，正是它要防的那类）。
    """
    out = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z"],
                         capture_output=True, check=True).stdout
    return [p.decode("utf-8", errors="replace") for p in out.split(b"\x00") if p]


def run_scan(paths):
    """T1+T2：返回 [(path, lineno)] 命中清单；paths 为空由调用方判红，不在这里兜。"""
    hits = []
    unreadable = 0
    for rel in paths:
        try:
            text = (ROOT / rel).read_bytes().decode("utf-8", errors="replace")
        except OSError:
            unreadable += 1
            print("  SKIP 读不到 %s" % rel)
            continue
        for ln in scan_text(text):
            hits.append((rel, ln))
    # 覆盖率自证：可读数 + 不可读数 == 分母，且不可读占比过高即视为扫描失效
    if unreadable and unreadable * 2 > len(paths):
        return hits, ("覆盖面失效：读不到 %d/%d 个文件 ⇒ 不得据此判绿" % (unreadable, len(paths)))
    return hits, None


def main() -> int:
    paths = tracked_files()
    if not paths:
        print("SECRET-SCAN-UNVERIFIED: git ls-files 返回 0 个文件 ⇒ 分母为空，不得据此判绿（R247）")
        return 1
    hits, blind = run_scan(paths)
    if blind:                                    # 覆盖面失效与"检出密钥"是两回事，报红时不许混成一句
        print("SECRET-SCAN-UNVERIFIED: " + blind)
        return 2
    for rel, ln in hits:
        print("  HIT %s:%d" % (rel, ln))
    if hits:
        print("SECRET-SCAN-FAIL: %d 处密钥形态落在被跟踪文件里，禁止入库" % len(hits))
        print("  修法：改成拼接构造（\"sk-\" + \"...\"）或从环境读取，**禁止把命中的文件加进排除名单**")
        return 1
    print("SECRET-SCAN-PASS（跟踪文件 %d 个，0 命中；正则与 CI 同源）" % len(paths))
    return 0


def selftest() -> int:
    """判据非恒真自证：两侧都要有样本（能抓该抓的、别抓不该抓的）。"""
    bad = []
    canary = "sk-" + "abcdefghij" + "1234567890" + "QRST"       # 拼接 ⇒ 本文件不自伤
    if not scan_text("demo %s\n" % canary):
        bad.append("对照组失败：拼接出的 24 位密钥未被抓到 ⇒ 判据恒绿")
    if scan_text(KEY_RE.pattern):
        bad.append("正则文本自身被判命中 ⇒ 每条治理文档都会被误伤")
    if scan_text("sk-abc 太短不算密钥"):
        bad.append("短串被误判 ⇒ 判据过敏")
    if scan_text(""):
        bad.append("零输入被判命中（形状异常）")
    if not scan_text("Bearer sk-" + "Z" * 40):
        bad.append("40 位密钥漏抓 ⇒ 判据只认恰好 20 位的形态")
    # 覆盖面分支（防"全部读不到 ⇒ 0 命中 ⇒ PASS"这条假绿通道）
    _, blind_ok = run_scan(["README.md", "_test/tracked_secret_scan.py"])
    if blind_ok:
        bad.append("正常清单被判覆盖面失效（判据过敏）：%s" % blind_ok)
    _, blind_bad = run_scan(["no/such/file-a", "no/such/file-b"])
    if not blind_bad:
        bad.append("全部文件读不到却没报覆盖面失效 ⇒ 假绿通道敞开")
    if bad:
        print("SELFTEST-FAIL: " + " ; ".join(bad))
        return 1
    print("SELFTEST-PASS: 该抓的都抓到（拼接样本 / 40 位长串），该放的都放行（正则文本 / 短串 / 空输入）")
    return 0


if __name__ == "__main__":
    sys.exit(selftest() if "--selftest" in sys.argv[1:] else main())
