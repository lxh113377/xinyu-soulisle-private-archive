# -*- coding: utf-8 -*-
r"""佐证材料 PDF 提交前校验：存在性 / 体积 / 页数 / 可提取文本 / 公平性 / 隐私。

用法：
    python 交付物\AIC\佐证材料\_verify_evidence.py
可选：把最终 PDF 路径作为第一个参数传入。
"""
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
DEFAULT = os.path.join(BASE, "心屿MindIsle-AIC-佐证材料.pdf")
PDF = sys.argv[1] if len(sys.argv) > 1 else DEFAULT

# 也接受"已按团队编号改名"的最终件
if not os.path.exists(PDF):
    cands = [f for f in os.listdir(BASE)
             if f.lower().endswith(".pdf") and "佐证" in f]
    if cands:
        PDF = os.path.join(BASE, sorted(cands)[0])

MAX_BYTES = 10 * 1024 * 1024  # 官方对作品方案限 10M，佐证未明示，按同档从严
SCHOOL_KWS = ["江西科技", "指导教师", "校徽", "iCAN", "icAN"]
CONTACT_RE = re.compile(r"(1[3-9]\d{9})|([\w.+-]+@[\w-]+\.[\w.]+)")

fail = []


def check(ok, label, detail=""):
    print(("  [PASS] " if ok else "  [FAIL] ") + label + (f" — {detail}" if detail else ""))
    if not ok:
        fail.append(label)


print("佐证材料校验:", PDF)

if not os.path.exists(PDF):
    print("  [FAIL] 文件不存在 — 最终件应放在："
          r"c:\Users\37533\Desktop\workspace\项目\陪聊\交付物\AIC\佐证材料")
    sys.exit(1)

size = os.path.getsize(PDF)
check(size <= MAX_BYTES, "体积 ≤10M", f"{size/1024/1024:.2f} MB")

try:
    from pypdf import PdfReader
except ImportError:
    print("  [FAIL] 缺 pypdf，先 pip install pypdf")
    sys.exit(1)

r = PdfReader(PDF)
texts = [(p.extract_text() or "") for p in r.pages]
blob = "\n".join(texts)

check(len(r.pages) >= 1, "页数 ≥1", f"{len(r.pages)} 页")
check(len(blob.strip()) > 50, "文本可提取（非纯扫描图片；扫描件需先 OCR）",
      f"{len(blob.strip())} 字符")

hits = {k: blob.count(k) for k in SCHOOL_KWS if blob.count(k)}
check(not hits, "公平性：校名/Logo/指导教师/iCAN 0 命中", str(hits) if hits else "")

phones = sorted(set(CONTACT_RE.findall(blob)))
flat = [p or e for p, e in phones]
check(not flat, "隐私：手机号/邮箱 0 命中", str(flat[:5]) if flat else "")

need_note = ["心屿"]
miss = [k for k in need_note if k not in blob]
check(not miss, "含作品名标识", f"缺失 {miss}" if miss else "")

print("=== 结果:", "EVIDENCE-PASS" if not fail else f"EVIDENCE-FAIL（{len(fail)} 项）")
sys.exit(0 if not fail else 1)
