# -*- coding: utf-8 -*-
"""验收导出的 PDF：页数、关键内容、合规。"""
from pypdf import PdfReader

PDF = r"c:\Users\37533\Desktop\workspace\项目\陪聊\交付物\AIC\心屿MindIsle_AIC参赛方案.pdf"
r = PdfReader(PDF)
texts = [(p.extract_text() or "") for p in r.pages]
blob = "\n".join(texts)

print("页数:", len(r.pages), "(期望 24)")
print("=== 合规扫描 ===")
for kw in ["iCAN", "江西科技", "指导教师", "校徽", "8 人"]:
    print(f"   {kw!r}: {blob.count(kw)}")

need = [
    "本次参赛交付范围", "三级共识路由", "可验证的证据", "对照 AIC 赛题2",
    "98.6%（72/73）", "92.2%", "26.6 ms", "101 用例全绿",
    "三级共识情绪路由", "PACE 主动陪伴引擎", "路线图",
]
print("=== 关键内容 ===")
miss = [k for k in need if k not in blob]
print("   缺失:", miss if miss else "无")

print("=== 后 4 页文字抽样 ===")
for i in (20, 21, 22, 23):
    t = texts[i].replace("\n", " ")[:110]
    print(f"   p{i+1}: {t}")

imgs = sum(len(p.images) for p in r.pages)
print("=== 内嵌背景图总数:", imgs, "(24 页各 1 张底图，期望 ≥20)")
