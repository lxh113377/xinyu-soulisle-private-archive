# -*- coding: utf-8 -*-
"""kb_battery_count_audit.py -- 电池套数口径的机器判据（r178-KB31 立，r178-KB38 装两源比对腿）

为什么立：N21/N22 登记「电池套数口径在文案里漂移」（8 套 -> 9 套，文案里还散落七套/五套）。
根因是口径靠人工数：每轮 grep 一次、数一次、写一次，下一轮又漂。本件把它固化成常驻判据。

两把尺（同一件里，互不覆盖）：
  尺 A（下限）：从 run_all_suites.py 的 SUITES 表实数出**全部**判据前缀组，断言 >= 9。
     防的是「套件被删/没注册而没人发现」。
  尺 B（两源比对，r178-KB38 装）：从 README **当前版本段**抽出「X 套电池各自 ALL-GREEN」的 X，
     与 SUITES 表里**KB 判据组实数**比对，不等即红。防的是 N25 留的那条
     「文案数字与实数不一致」——这是真发生过的：文案写「十套」，实数 9 组。
作用域只限当前段：历史段按纪律保留当日值、不回填，扫全文件会恒红。
"""
import re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "_test" / "run_all_suites.py"
README = ROOT / "交付物" / "心理学知识库" / "README.md"
MIN_BATTERY = 9
KB_EXTRA = ("psych_kb_build", "psych_kb_integrity", "deploy_sync")


def _suites_block():
    """取 SUITES 表的完整内容。不能用 src.index("]", i) —— 条目里就有 [sys.executable,
    第一个 ] 会把表截成只剩第一条条目（实测：真面只数出 1 组）。改用下一个 def 行定位表尾。"""
    src = SRC.read_text(encoding="utf-8")
    i = src.index("SUITES = [") + len("SUITES = [")
    tail = src.index("\ndef ", i)
    return src[i:tail]


def _names(block):
    """从 SUITES 表块里取条目名。条目形如 ("name", [...])，逐行匹配，不用正则避转义坑。"""
    out = []
    for line in block.splitlines():
        line = line.strip()
        if line.startswith("(") and '", [' in line:
            out.append(line.split('"')[1])
    return out


def _groups_of(names):
    out = set()
    for n in names:
        out.add(n[:-len("_selftest")] if n.endswith("_selftest") else n)
    return out


def count_battery():
    """尺 A：SUITES 表里**全部**判据前缀组。"""
    return sorted(_groups_of(_names(_suites_block())))


def kb_groups():
    """尺 B 左侧：SUITES 表里的 **KB 判据组**（文案「X 套电池」的 X 指的就是这个）。
    KB 判据 = 名字以 kb_ 开头，或等于 psych_kb_build / psych_kb_integrity / deploy_sync。"""
    return sorted(g for g in _groups_of(_names(_suites_block()))
                  if g.startswith("kb_") or g in KB_EXTRA)


def current_section_text():
    """README 里**当前版本段**（最后一个 v2.x 段）的文本。
    作用域必须限定：历史段按纪律保留当日值、不回填，扫全文件恒红。"""
    txt = README.read_text(encoding="utf-8")
    idxs = [m.start() for m in re.finditer(r"^### v2\.\d+", txt, re.M)]
    if not idxs:
        return ""
    start = idxs[-1]
    nxt = txt.find("\n### ", start + 1)
    return txt[start: nxt if nxt != -1 else len(txt)]


CN_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7,
          "八": 8, "九": 9, "十": 10, "十一": 11, "十二": 12}


def _to_int(tok):
    """接受阿拉伯数字与中文数字。中文文档里「九套」比「9 套」自然，尺要适配真面措辞，
    不是让文案迁就尺（否则等于为了机器好看去改数据）。"""
    if tok.isdigit():
        return int(tok)
    return CN_NUM.get(tok)


def text_battery_count(text):
    """尺 B 右侧：文案里「X 套电池各自 ALL-GREEN」的 X。None = 没写。"""
    m = re.search(r"([0-9]+|[一二三四五六七八九十]+)\s*套电池各自 ALL-GREEN", text)
    return _to_int(m.group(1)) if m else None


def compare_faces():
    """两源比对。返回 (ok, detail, real, claimed)。
    文案没写 X 时不判红（本件只管数对不对，不管有没有写）。"""
    real = len(kb_groups())
    claimed = text_battery_count(current_section_text())
    if claimed is None:
        return True, "当前段未写「X 套电池各自 ALL-GREEN」，跳过比对", real, None
    ok = (claimed == real)
    return ok, "文案 %s 套 / 实数 %d 组" % (claimed, real), real, claimed


def main():
    groups = count_battery()
    kg = kb_groups()
    print("  尺 A：SUITES 表实数出的判据前缀组 %d 个" % len(groups))
    print("  尺 B：KB 判据组 %d 个：%s" % (len(kg), "、".join(kg)))
    print("  门阈值 MIN_BATTERY=%d" % MIN_BATTERY)
    okA = len(groups) >= MIN_BATTERY
    okB, detailB, _, _ = compare_faces()
    print("  尺 B 比对：" + detailB)
    if not okA:
        print("  尺 A 缺口（低于门阈值的前缀组）：%d 个" % (MIN_BATTERY - len(groups)))
    ok = okA and okB
    print("KB-BATTERY-COUNT-AUDIT-" + ("PASS" if ok else "FAIL")
          + ": 尺 A 实数 %d 组（门阈值 %d）%s ｜ 尺 B %s" % (
              len(groups), MIN_BATTERY, "OK" if okA else "红", "OK" if okB else "红"))
    return 0 if ok else 1


def _run_with_override(add=None, min_battery=None, text_count=None, sync_text=False):
    """变异腿用：纯文本改写 SUITES 表名 / 门阈值 / 伪造文案数，再走同一套判定，不动 src。
    sync_text=True 时把文案数也按加组后的实数同步（腿 3 用：它只想证「尺 A 是下限」，
    不该被尺 B 咬——加了组却不改文案，尺 B 反把自证腿拖红，那是腿的构造问题，不是判据坏）。"""
    names = _names(_suites_block())
    if add:
        names.append(add)
    groups = _groups_of(names)
    kg = set(g for g in groups if g.startswith("kb_") or g in KB_EXTRA)
    cap = min_battery if min_battery is not None else MIN_BATTERY
    okA = len(groups) >= cap
    if text_count is not None:
        okB = (text_count == len(kg))
    elif sync_text:
        okB = (len(kg) == len(kg))
    else:
        claimed = text_battery_count(current_section_text())
        # 文案没写数（None）时不算红——本件只管数对不对，不管有没有写。
        okB = (claimed is None) or (claimed == len(kg))
    return (0 if (okA and okB) else 1), "实数 %d 组 / KB %d 组 / 门阈值 %d" % (len(groups), len(kg), cap)


def selftest():
    real = len(kb_groups())
    # 腿 1：真面 PASS
    rc1, d1 = _run_with_override()
    # 腿 2：门阈值抬到 n+1（真面 n < n+1）=> 红。证明尺 A 是下限判据、且敏感。
    n = len(count_battery())
    rc2, d2 = _run_with_override(min_battery=n + 1)
    # 腿 3：加一组 kb_fake_battery（n+1 >= 9）=> 不红。自证腿：判据是「>=」不是「==」。
    rc3, d3 = _run_with_override(add="kb_fake_battery", sync_text=True)
    # 腿 4：伪造文案数 real+1 => 红。证明尺 B 真在比对两源，不是写死常量。
    rc4, d4 = _run_with_override(text_count=real + 1)
    legs = [
        ("真面（尺 A + 尺 B）", rc1, d1),
        ("变异腿：门阈值抬到 n+1（真面 n < n+1）", rc2, d2),
        ("自证腿：加一组 kb_fake_battery（不红，判据是下限）", rc3, d3),
        ("变异腿：伪造文案数 real+1（尺 B 必须红）", rc4, d4),
    ]
    allok = (rc1 == 0 and rc2 != 0 and rc3 == 0 and rc4 != 0)
    for name, rc, d in legs:
        print("  " + ("OK  " if rc == 0 else "FAIL") + " " + name + "  （" + d + "）")
    print("KB-BATTERY-COUNT-AUDIT-SELFTEST-" + ("PASS" if allok else "FAIL")
          + ": " + str(len(legs)) + " 腿（真面绿 + 抬阈值红 + 加组绿 + 伪造文案数红 = 两把尺都咬合）")
    return 0 if allok else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    sys.exit(main())
