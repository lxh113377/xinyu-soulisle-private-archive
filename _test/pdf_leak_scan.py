# -*- coding: utf-8 -*-
"""PDF 文本层泄露复扫（R242：二进制产物须抽文本后再扫）。

为什么存在：交付物 PDF 会被反复重渲染（改图/改文案），而"盲审无敏感信息"是**状态性断言**——
上一次通过不代表这一次通过。Edge 的 `--no-pdf-header-footer` 若被谁去掉，页脚就会把
`file:///C:/Users/<用户名>/...` 印进每一页（2026-09-24 实测发生过）。故固化为判据。

用法：
  python _test/pdf_leak_scan.py [pdf 路径]        # 默认扫交付物 PDF
  python _test/pdf_leak_scan.py --selftest        # 三要素自证（正例 / 违规样本 / 边界）
退出码：0=CLEAN，1=命中或输入不可信，2=文件不存在
"""
import re
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PDF = ROOT / "交付物" / "提交包" / "心屿SoulIsle-应用方案.pdf"

PATTERNS = {
    "本机绝对路径 file://": r"file://",
    "Windows 家目录/用户名": r"(?i)C:[/\\]{1,3}Users",
    "真实密钥形态": r"sk-[A-Za-z0-9]{20,}",
    # 必须"本地部分首尾是字母数字 + 域名每段 ≥2 字符 + 带点 TLD"：
    # 字体子集名（`c-@g.Bk`、`%@P`）这类二进制噪声曾把干净件判红（r32 实测两轮误报）
    "邮箱": r"[A-Za-z0-9](?:[A-Za-z0-9._%+-]{0,38}[A-Za-z0-9])?@(?:[A-Za-z0-9-]{2,60}\.)+[A-Za-z]{2,}",
    "手机号": r"(?<![0-9])1[3-9][0-9]{9}(?![0-9])",
    # 注：**不设"校名/院系"模式**。Edge 打印把中文编成字形 ID，`(...)` 里根本没有汉字，
    # 这条模式在本判据上永远零命中 = 假覆盖；校名由截图目检负责（提交清单红线里逐张记）。
}


def pdf_visible_text(raw: bytes) -> str:
    """解 FlateDecode 流，抽出 `(...)` 里的可见文本片段（不依赖第三方 PDF 库）。"""
    parts = []
    for m in re.finditer(rb"stream\r?\n(.*?)endstream", raw, re.S):
        body = m.group(1)
        try:
            parts.append(zlib.decompress(body).decode("latin-1", errors="replace"))
        except Exception:
            # 非压缩流也扫（对象字典、明文文本都在里面）
            parts.append(body.decode("latin-1", errors="replace"))
    blob = "\n".join(parts)
    return " ".join(re.findall(r"\((?:[^()\\]|\\.)*\)", blob))


def scan(shown: str):
    """返回 {名称: 命中样本[]}；输入为空由调用方判不可信，不在此处返回"干净"。"""
    out = {}
    for name, pat in PATTERNS.items():
        hits = re.findall(pat, shown)
        if hits:
            out[name] = sorted({str(h)[:28] for h in hits})[:4]
    return out


def main(argv):
    if "--selftest" in argv:
        return selftest()
    p = Path(argv[0]) if argv else DEFAULT_PDF
    if not p.exists():
        print(f"PDF-SCAN-MISSING: {p}")
        return 2
    raw = p.read_bytes()
    shown = pdf_visible_text(raw)
    print(f"目标 {p.name}  {len(raw):,d}B -> 可抽文本 {len(shown):,d}B")
    if len(shown) < 2000:
        # 抽不到文本 = 扫描没输入，绝不能记 CLEAN（零输入不得记 PASS）
        print(f"PDF-SCAN-UNVERIFIED: 可抽文本仅 {len(shown)}B（<2000）⇒ 抽取失效，不得据此判 CLEAN")
        return 1
    hits = scan(shown)
    for name in PATTERNS:
        mark = "命中" if name in hits else "零命中"
        print(f"  {mark:<6} {name}" + (f"  {hits[name]}" if name in hits else ""))
    if hits:
        print("PDF-LEAK-FAIL: 交付 PDF 文本层含敏感形态 ⇒ 禁止提交，先修渲染参数或重截图")
        return 1
    print("PDF-LEAK-CLEAN（输入非空已证：可抽文本 %d B）" % len(shown))
    return 0


def selftest():
    """三要素：正例（干净流）/ 违规样本（各类敏感串必须被抓）/ 边界（空输入不得判 CLEAN）。"""
    def mkpdf(texts):
        body = " ".join("(%s) Tj" % t for t in texts).encode("latin-1")
        return b"%PDF-1.4\n1 0 obj\n<<>>\nstream\n" + zlib.compress(body) + b"\nendstream\n%%EOF"

    clean = mkpdf(["Xinyu SoulIsle application plan", "emotion engine dual path", "crisis hotline 12356",
                   "%@P %V@8 +@-- +@L c-@g.Bk"])   # 字体二进制里的噪声串：必须不误报（r32 实测误报源）
    dirty = mkpdf(["plan text", "file:///C:/Users/someone/x.html", "sk-abcdefghij1234567890QRST",
                   "someone@corp.cn", "13800001234"])
    bad = []
    cs = scan(pdf_visible_text(clean))
    if cs:
        bad.append(f"正例被误报（判据过敏）：{cs}")
    ds = scan(pdf_visible_text(dirty))
    for must in ("本机绝对路径 file://", "真实密钥形态", "邮箱", "手机号", "Windows 家目录/用户名"):
        if must not in ds:
            bad.append(f"违规样本漏报：{must}")
    if scan(""):
        bad.append("零输入被判出命中（形状异常）")
    # 反向：危机热线 12356 不是手机号；`%@P` 不是邮箱 —— 防判据随手抓数字/抓噪声
    if re.findall(PATTERNS["手机号"], "hotline 12356"):
        bad.append("危机热线 12356 被误判为手机号")
    if re.findall(PATTERNS["邮箱"], "%@P +@-- a@b c-@g.Bk"):
        bad.append("字体噪声串被误判为邮箱")
    print("SELFTEST-PASS: 正例零误报（含字体噪声串）/ 违规样本 5 类全抓 / 零输入不判命中 / "
          "12356 与 %@P 不被误抓" if not bad else "SELFTEST-FAIL: " + "; ".join(bad))
    return 0 if not bad else 1


if __name__ == "__main__":
    # 注意：--selftest 必须在过滤前判，否则"过滤掉所有 --* 参数"会让自测永远进不去（r32 实测踩过）
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    sys.exit(main([a for a in sys.argv[1:] if not a.startswith("--")]))
