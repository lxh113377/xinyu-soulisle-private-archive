# -*- coding: utf-8 -*-
"""线上↔权威源逐字节新鲜度守卫：公网 Pages 内容与 deploy/xinyu 不一致即红。
判据设计：
  1) 生产别名 `/` 页面字节 == deploy/xinyu/index.html 字节（Pages 原样托管，实测相等）
  2) 页面**引用到的每个** js/css/vendor/data/manifest 资源：既要 200，也要**字节相等**
     （r36 前只查 200 ⇒ "公网与权威源逐字节同源"这句其实只由 index.html 一张图支撑）
  3) 分母从页面现读，不手抄清单；解析不到任何引用 ⇒ rc=2（空集不算通过）
  4) ⚠️ 坑位固化：Pages 对 /index.html 返回 200 但空 body，必须抓 `/`
退出码：0=LIVE-SYNC-PASS 1=漂移 2=网络/环境异常（不许把环境故障伪装成通过）
"""
import sys
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "https://xinyu-soulisle.pages.dev"
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
XINYU = ROOT / "deploy" / "xinyu"

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "xinyu-live-check"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.status, r.read()

def main():
    try:
        local = (XINYU / "index.html").read_bytes()
        status, body = fetch(BASE.rstrip("/") + "/")
    except Exception as e:
        print(f"LIVE-SYNC-ENV-ERROR: {e}")
        return 2

    if status != 200:
        print(f"LIVE-SYNC-FAIL: GET / -> {status}")
        return 1
    if len(body) == 0:
        print("LIVE-SYNC-FAIL: GET / 空 body（若打的是 /index.html 属已知坑，改抓 /）")
        return 1
    # r28：`.gitattributes` 是 `* text=auto` ⇒ 同一份内容在 Windows 工作区是 CRLF、Linux runner 检出是 LF。
    # 拿原始字节比会让「部署有没有跟进」这条判据在 CI 上恒红（本机永远看不见，因为两边都是 CRLF）。
    # 判据要问的是**内容是否同一份**：先比字节；不等再比"归一行尾"，并把「仅行尾差异」如实标出来。
    index_ok = body == local
    eol_only = (not index_ok) and body.replace(b"\r\n", b"\n") == local.replace(b"\r\n", b"\n")
    print(f"index.html bytes: live={len(body)} local={len(local)} equal={index_ok}"
          + ("｜仅行尾差异（CI 检出 LF vs 本机 CRLF），内容等价 ⇒ 判 PASS" if eol_only else ""))
    index_ok = index_ok or eol_only

    srcs = []
    try:
        htm = body.decode("utf-8", "replace")
    except Exception:
        htm = ""
    import re
    # 分母**从页面现读**，不手抄清单：页面引用了什么，就要求公网与权威源在什么上一致。
    # 前缀后必须跟 `/`（或整体匹配 manifest.webmanifest）：否则 `href="data:image/svg+xml,<svg…"`
    # 这类内联 data URI 会被当路径去取（变异测试实测抓到：四条断言全被这条假 URL 打断）
    for m in re.finditer(r'(?:src|href)="((?:js|css|vendor|data)/[^"?#]+|manifest\.webmanifest)', htm):
        srcs.append(m.group(1))
    if not srcs:
        # 抓不到任何引用 = 页面结构变了或正则失效，此时"零漂移"毫无意义（禁把空集当通过）
        print("LIVE-SYNC-ENV-ERROR: 页面未解析出任何 js/css/vendor/data/manifest 引用 ⇒ 判据失效")
        return 2
    missing, drift, eol_files, equal = [], [], [], 0
    for s in sorted(set(srcs)):
        try:
            st, ab = fetch(BASE.rstrip("/") + "/" + s)
        except Exception:
            missing.append(f"{s}(取数失败)")
            continue
        if st != 200:
            missing.append(f"{s}(http={st})")
            continue
        loc = XINYU / s
        if not loc.exists():
            drift.append(f"{s}(公网有、权威源无)")
            continue
        lb = loc.read_bytes()
        if ab == lb:
            equal += 1
        elif ab.replace(b"\r\n", b"\n") == lb.replace(b"\r\n", b"\n"):
            eol_files.append(s)   # 内容等价但字节不等 ⇒ 单独点名，不并入"相等"
        else:
            drift.append(f"{s}(live={len(ab)}B local={len(lb)}B)")
    n = len(set(srcs))
    print(f"资源字节对账：引用 {n} 项 | 逐字节相等 {equal} | 仅行尾差异 {len(eol_files)} | "
          f"缺失 {len(missing)} | 内容漂移 {len(drift)}")
    if eol_files:
        print(f"  ⚠️ 仅行尾差异（部署或检出侧行尾未对齐，r36 已钉 eol=lf，再出现须查部署链）：{eol_files}")
    if missing:
        print(f"LIVE-SYNC-FAIL: 线上缺资源/取数失败 {missing}")
        return 1
    if drift:
        print(f"LIVE-SYNC-FAIL: 线上内容与权威源不一致 {drift}")
        return 1
    if not index_ok:
        print("LIVE-SYNC-FAIL: 线上 index.html 与 deploy/xinyu/index.html 字节不一致（部署未跟进）")
        return 1
    if missing:
        print(f"LIVE-SYNC-FAIL: 线上缺资源 {missing}")
        return 1
    print("LIVE-SYNC-PASS")
    return 0

if __name__ == "__main__":
    sys.exit(main())   # 守卫：import 只取 BASE/比较函数，不应触发联网对账（R161 同族的 import-safe）
