# -*- coding: utf-8 -*-
"""r94 第三件：给 `eol_parity_check` 补「未入库面」。

盲区（一手）：本门扫描面 = `git ls-files` ⇒ **未跟踪的新文件完全不在门内**。
现象是「提交前绿、提交后红」：工作树里新写的脚本是 CRLF，提交时 git 归一为 LF 存入 blob，
于是提交后立刻变成「工作树字节 != blob 字节」的红。此前我把这个当成"归一忘了"，
直到发现提交前跑是绿的，才定位到门本身有个时间窗盲区。

修法（与 r93 给 `disclaimer_forensics_lint` 做过的双面分母同手法）：
① 扫描面显式扩为两路：`已跟踪`（原有逻辑，有 blob 可比）+ `未入库`（新增，只查工作树含 CRLF）；
② 门面行分别印两个分母与合计 ——「门没查它」这件事必须显式，不能靠读者自己发现；
③ `--selftest` 补三条腿：未入库+CRLF 必红 / 未入库+LF 不红 / 未入库+binary 不红。

**默认判红，不给逃生开关**：未入库文件一旦带 CRLF，入库后必红；提前红是机制化。
给开关等于给「习惯性绕过一次」留入口（本仓已多次吃过「配了开关但没生效」的亏）。
"""
from pathlib import Path

P = Path("_test/eol_parity_check.py")
src = P.read_text(encoding="utf-8")

FN = '''
def audit_untracked(paths, reader=None, bin_check=None):
    """未入库文件（`git ls-files --others --exclude-standard`）：**没有 blob 可比**，只查 CRLF。

    为什么必须单独一路（r94 一手）：`git ls-files` 不含未跟踪文件 ⇒ 刚写完、还没入库的脚本
    在本门下**完全不可见**。而它入库后，工作树那份若是 CRLF，就立刻变成「工作树字节 != blob
    字节」的红 —— 表现为「提交前绿、提交后红」，很容易被误读成「归一忘了」。

    为什么不并入 `audit()`：并进去会让 `wt != blob` 那条判据拿 `b""`（未入库文件没有 blob）
    去比，**必然不等** ⇒ 每个新文件都假红。`dirty` 也救不了：未跟踪文件在 `status --porcelain`
    里是 `??`，而 `main()` 组 dirty 时明确排除了 `??`。
    """
    read = reader or (lambda rel: (ROOT / rel).read_bytes() if (ROOT / rel).is_file() else None)
    binlike = bin_check or is_binary
    bad, n_text, n_bin, n_miss = [], 0, 0, 0
    for rel in paths:
        wt = read(rel)
        if wt is None:
            n_miss += 1
            continue
        if binlike(rel):
            n_bin += 1
            continue
        n_text += 1
        if b"\\r\\n" in wt:
            bad.append("未入库文件工作树含 CRLF（入库后即成「工作树 != blob」的红）：%s" % rel)
    return bad, {"text": n_text, "binary": n_bin, "total": len(paths), "missing": n_miss}


'''

ANCHOR = "def selftest() -> int:"
assert ANCHOR in src
src = src.replace(ANCHOR, FN.lstrip("\n") + ANCHOR, 1)

# main：取未跟踪面并入
# ⚠️ 插入点必须在 `try/except` **之外**（第一版插在 `try:` 块里 ⇒ SyntaxError:
#    expected 'except' or 'finally' block —— 脚本化改码时最容易踩的一类：锚点选在了语法块内部）。
OLD_P = '''    if not paths:
        print("EOL-PARITY-ENV: git ls-files 返回 0 个文件 ⇒ 分母为空，不得据此判绿（R247）")
        return 2'''
NEW_P = '''    if not paths:
        print("EOL-PARITY-ENV: git ls-files 返回 0 个文件 ⇒ 分母为空，不得据此判绿（R247）")
        return 2
    # r94：第二路扫描面 = 未入库文件（ls-files 不含它们）。零个也照走，让门面行的分母可复算。
    untracked = git_z("ls-files", "--others", "--exclude-standard")'''
assert OLD_P in src
src = src.replace(OLD_P, NEW_P, 1)

OLD_CALL = '''    e2, st = audit(paths, dirty=dirty)
    bad += e2'''
NEW_CALL = '''    e2, st = audit(paths, dirty=dirty)
    bad += e2
    e2u, stu = audit_untracked(untracked)
    bad += e2u'''
assert OLD_CALL in src
src = src.replace(OLD_CALL, NEW_CALL, 1)

OLD_PASS = '''    print("EOL-PARITY-PASS（text=%d binary=%d total=%d；工作树字节 == blob 字节 ⇒ 与机器无关）"
          % (st["text"], st["binary"], st["total"]))'''
NEW_PASS = '''    print("EOL-PARITY-PASS（已跟踪：text=%d binary=%d total=%d｜未入库：text=%d binary=%d 取不到=%d"
          "；工作树字节 == blob 字节 ⇒ 与机器无关）"
          % (st["text"], st["binary"], st["total"], stu["text"], stu["binary"], stu["missing"]))'''
assert OLD_PASS in src
src = src.replace(OLD_PASS, NEW_PASS, 1)

# E4 分母闭合也要带上未入库面
OLD_E4 = '''    if st["text"] + st["binary"] != st["total"]:
        bad.append("E4 分母不闭合：text %d + binary %d != total %d"
                   % (st["text"], st["binary"], st["total"]))'''
NEW_E4 = '''    if st["text"] + st["binary"] != st["total"]:
        bad.append("E4 分母不闭合：text %d + binary %d != total %d"
                   % (st["text"], st["binary"], st["total"]))
    if stu["text"] + stu["binary"] + stu["missing"] != stu["total"]:
        bad.append("E4b 未入库面分母不闭合：text %d + binary %d + 取不到 %d != total %d"
                   % (stu["text"], stu["binary"], stu["missing"], stu["total"]))'''
assert OLD_E4 in src
src = src.replace(OLD_E4, NEW_E4, 1)

P.write_text(src, encoding="utf-8")
print("eol_parity_check.py 已扩为双面")
