# -*- coding: utf-8 -*-
"""r94：给 `eol_parity_check.selftest()` 补「未入库面」四条腿。

补的是本轮亲手踩出来的盲区：门只查已跟踪面 ⇒ 新写文件在入库前不可见
⇒ 表现为「提交前绿、提交后红」。补腿时按本仓规矩：正例 + 反例 + 零输入，
且**反例必须证明「不误伤」**（未入库的 LF 文本与 binary 都要放行）。
"""
from pathlib import Path

P = Path("_test/eol_parity_check.py")
src = P.read_text(encoding="utf-8")

OLD = '''    _, st0 = audit([], reader_with({}), fake_bin)
    if st0["total"] != 0:
        bad.append("零输入却算出非零分母")'''

NEW = '''    _, st0 = audit([], reader_with({}), fake_bin)
    if st0["total"] != 0:
        bad.append("零输入却算出非零分母")

    # ── r94：未入库面（`git ls-files` 不含它们，r94 前完全不可见）──
    def rd(payloads):
        return lambda rel: payloads[rel]

    PNG = b"\\x89PNG\\r\\n\\x1a\\n"
    u_cases = [
        ("未入库 + CRLF ⇒ 必须点名（入库后就是「工作树 != blob」的红）",
         {"n.py": b"x\\r\\ny\\r\\n"}, ["n.py"]),
        ("未入库 + LF ⇒ 不得误报（提前红成噪声，门就没人看了）",
         {"n.py": b"x\\ny\\n"}, []),
        ("未入库 + 声明 binary 且含 0D0A ⇒ 放行（绝不能去动二进制）",
         {"n.png": PNG}, []),
        ("未入库 + 取不到字节 ⇒ 计入 missing 且不判红（分母仍闭合）",
         {"gone.py": None}, []),
    ]
    for name, payloads, expect in u_cases:
        e2u, stu = audit_untracked(list(payloads), reader=rd(payloads), bin_check=fake_bin)
        hit = [x for x in expect if any(x in m for m in e2u)]
        if expect and len(hit) != len(expect):
            bad.append("未入库面违规样本漏报：%s -> %s" % (name, e2u[:1]))
        if not expect and e2u:
            bad.append("未入库面合规样本被误判：%s -> %s" % (name, e2u[:1]))
        if stu["text"] + stu["binary"] + stu["missing"] != stu["total"]:
            bad.append("未入库面分母不闭合：%s（%s）" % (name, stu))
    _, stu0 = audit_untracked([], reader=rd({}), bin_check=fake_bin)
    if stu0["total"] != 0:
        bad.append("未入库面零输入却算出非零分母")'''

assert OLD in src
src = src.replace(OLD, NEW, 1)

OLD_P = '''    print("EOL-PARITY-SELFTEST-PASS: %d 类样本各归各位（合规文本放行 / 工作树 CRLF 判红 / "
          "binary 的 0D0A 放行与不要求 / 未声明 binary 的 0D0A 判红 / 仓库侧 CRLF 判红）"
          "+ 零输入分母为 0" % len(cases))'''
NEW_P = '''    print("EOL-PARITY-SELFTEST-PASS: %d 类已跟踪样本 + %d 类未入库样本各归各位"
          "（合规文本放行 / 工作树 CRLF 判红 / binary 的 0D0A 放行与不要求 / 未声明 binary 判红 /"
          " 仓库侧 CRLF 判红 / 未入库+CRLF 判红 / 未入库+LF 放行）+ 两面零输入分母为 0"
          % (len(cases), len(u_cases)))'''
assert OLD_P in src
src = src.replace(OLD_P, NEW_P, 1)

P.write_text(src, encoding="utf-8")
print("selftest 已补 %d 条未入库面腿" % 4)
