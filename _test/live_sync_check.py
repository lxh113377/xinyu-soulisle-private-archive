# -*- coding: utf-8 -*-
"""线上↔权威源逐字节新鲜度守卫：公网 Pages 内容与 deploy/xinyu 不一致即红。
判据设计：
  1) 生产别名 `/` 页面字节 == deploy/xinyu/index.html 字节（Pages 原样托管，实测相等）
  2) 线上缺失任何一个被跟踪的 js/css 资源（404 即漂移）
  3) ⚠️ 坑位固化：Pages 对 /index.html 返回 200 但空 body，必须抓 `/`
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
    for m in re.finditer(r'(?:src|href)="((?:js|css|manifest)[^"]+)"', htm):
        srcs.append(m.group(1))
    missing = []
    for s in sorted(set(srcs)):
        try:
            st, _ = fetch(BASE.rstrip("/") + "/" + s)
            ok = st == 200
        except Exception:
            ok = False
        if not ok:
            missing.append(s)
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
