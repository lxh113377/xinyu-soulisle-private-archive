# -*- coding: utf-8 -*-
"""对标 r47 探针：**移动端与触屏支持的结构性证据**（16 仓 + self，双通道）。

⚠️ 先说这面的**天花板**（诚实边界，别拿结构证据冒充几何证据）：
  对手的真实触控几何（目标是否 ≥44px、窄屏是否横向溢出、输入框会不会触发 iOS 聚焦缩放）
  **静态取不到** —— 那要把页面渲进真视口。我们自己的 `_test/mobile_check.py` 能实测，
  对手不能。所以本探针只出**结构与声明面**读数，报告里对应的结论一律标 ⚠️/❌，
  禁止写"对手的移动端体验比我们差"这种没有取数面的话（M5⑫）。

它仍然有区分度，因为这三件事是可复核的制度差异：
  ① 有没有 viewport meta、**是否禁缩放**（禁缩放 = 主动牺牲低视力用户，是一个决策不是疏忽）
  ② CSS 里有没有按**指针类型**适配（`(pointer:` / `(hover:`）而不是只按宽度断点 ——
     这正是 r47 我们自己的修法：要大目标的是手指不是窄屏
  ③ 有没有 PWA/移动壳（manifest + service worker / android / ios）

通道 A = git tree + 取两个文件正文（最浅的 HTML、最大的 CSS）
通道 B = README 正文的移动相关声明
未取到一律 NA(原因)，禁与 0 混同；self 与 peers 同一组正则。
用法：python _test/peer_mobile_probe.py [--json out.json] [--self-only] [--selftest]
退出码：0=分母齐且无 NA 1=存在 NA 或 selftest 未过 2=无 GitHub token
"""
import argparse
import base64
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from benchmark_metrics import PEERS, ROOT   # 分母唯一真相源 = 台账池

VIEWPORT_RE = re.compile(r"<meta[^>]+name=[\"']viewport[\"'][^>]*>", re.I)
NOSCALE_RE = re.compile(r"user-scalable\s*=\s*no|maximum-scale\s*=\s*1(\.0)?\b", re.I)
DEVICE_W_RE = re.compile(r"width=device-width", re.I)
MEDIA_RE = re.compile(r"@media[^{]*", re.I)
POINTER_RE = re.compile(r"@media[^{]*\(\s*(pointer|hover)\s*:", re.I)
TOUCH_TGT_RE = re.compile(r"(min-width|min-height)\s*:\s*(4[4-9]|[5-9]\d)px")
MANIFEST_RE = re.compile(r"(^|/)(manifest\.(webmanifest|json)|manifest\.json)$", re.I)
SW_RE = re.compile(r"(^|/)(sw|service[-_]?worker)[^/]*\.js$", re.I)
MOBILE_DIR = re.compile(r"(^|/)(android|ios|capacitor\.config\.json|expo\.po?j?son|pubspec\.yaml)$", re.I)
NOISE = re.compile(r"(^|/)(node_modules|\.venv|venv|dist/build|vendor/)/", re.I)

DOC_RX = {
    "mobile_claim": re.compile(r"(responsive|mobile[- ]?friendly|\bPWA\b|\biOS\b|\bAndroid\b"
                               r"|移动端|移动适配|自适应|手机)", re.I),
    "install_cmd": re.compile(r"(add to home screen|安装到桌面|installable|apk|\bIPA\b)", re.I),
}


def api(path, token, raw=False):
    req = urllib.request.Request("https://api.github.com/" + path,
                                 headers={"User-Agent": "xinyu-mobile-probe",
                                          "Accept": "application/vnd.github+json"})
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            d = r.read()
            return (d if raw else json.loads(d.decode("utf-8", "replace"))), ""
    except Exception as e:
        return None, "http=%s" % getattr(e, "code", type(e).__name__)


def classify_tree(paths, sizes=None):
    """结构面：viewport 候选 / PWA 与移动壳 / CSS 与媒体查询密度（路径级）。

    ⚠️ 两处首跑实测缺陷的修正：
      · `cssx?` 是想当然的后缀（没有 `.cssx` 这种文件），真缺陷是它**匹配不到任何 CSS** ⇒
        `mq=-1` 被当成"0 条媒体查询"参与结论。
      · 选 CSS 首版按**路径深度**取，名为 `css_largest` 实为"最浅的那个"，于是抓到的是
        reset/normalize 之类小文件，真正带断点的样式表根本没进读数。改为按 tree 给的
        blob `size` 取最大（名字与取数终于一致）。
    """
    sizes = sizes or {}
    html = [p for p in paths if re.search(r"\.html?$", p) and not NOISE.search(p)]
    css = [p for p in paths if re.search(r"\.css$", p, re.I) and not NOISE.search(p)]
    return {"html": len(html), "css": len(css),
            "html_shallow": sorted(html, key=lambda x: (x.count("/"), x))[:1],
            "css_largest": sorted(css, key=lambda x: (-sizes.get(x, 0), x))[:1],
            "manifest": [p for p in paths if MANIFEST_RE.search(p)][:2],
            "sw": [p for p in paths if SW_RE.search(p)][:2],
            "mobile_shell": [p for p in paths if MOBILE_DIR.search(p)][:2]}


def classify_css(text):
    """CSS 内容面：媒体查询总数 / 按指针类型适配数 / ≥44px 目标声明数。"""
    mq = MEDIA_RE.findall(text or "")
    return {"media": len(mq),
            "pointer_aware": len(POINTER_RE.findall(text or "")),
            "target44": len(TOUCH_TGT_RE.findall(text or "")),
            "css_bytes": len(text or "")}


def classify_html(text):
    m = VIEWPORT_RE.search(text or "")
    return {"has_viewport": bool(m),
            "device_width": bool(m and DEVICE_W_RE.search(m.group(0))),
            "scales_disabled": bool(m and NOSCALE_RE.search(m.group(0))),
            "viewport_meta": (m.group(0)[:120] if m else "")}


def classify_readme(text):
    out = {}
    for k, rx in DOC_RX.items():
        hits = rx.findall(text or "")
        if hits:
            out[k] = "%d 处｜样本 %r" % (len(hits), (hits[0] if isinstance(hits[0], str)
                                                  else str(hits[0]))[:40])
    return out


def verdict(h, c, t, doc):
    """把结构与声明证据折成一条（几何面一律标未测）。"""
    if not h or not h.get("html"):
        return "无 HTML 入口(非 Web 面)"
    if h.get("manifest") and h.get("sw"):
        return "viewport+PWA 全套"
    if c.get("pointer_aware"):
        return "按指针类型适配"
    if h.get("device_width") and c.get("media"):
        return "viewport+宽度断点"
    if h.get("device_width"):
        return "仅 viewport(CSS 面未证)"
    if h.get("has_viewport"):
        return "有 viewport 但无 device-width"
    return "无 viewport"


def probe_repo(slug, token):
    tree, trunc, errA = {}, False, ""
    d, e = api("repos/%s/git/trees/HEAD?recursive=1" % slug, token)
    if d is None:
        return {}, False, {}, {}, e or "tree-fail", {}
    blobs = [x for x in d.get("tree", []) if x.get("type") == "blob"]
    paths = [x.get("path", "") for x in blobs]
    sizes = {x.get("path", ""): int(x.get("size") or 0) for x in blobs}
    trunc = bool(d.get("truncated"))
    tree = classify_tree(paths, sizes)
    html, css, errs = {}, {}, []

    def get_blob(path):
        b, e2 = api("repos/%s/contents/%s" % (slug, path), token)
        if b is None:
            errs.append("%s:%s" % (path, e2))
            return ""
        try:
            return base64.b64decode(b.get("content") or "").decode("utf-8", "replace")
        except Exception as ex:
            errs.append("%s:decode:%s" % (path, ex))
            return ""
    if tree["html_shallow"]:
        html = classify_html(get_blob(tree["html_shallow"][0]))
    if tree["css_largest"]:
        css = classify_css(get_blob(tree["css_largest"][0]))
    else:
        errs.append("css:NA(仓内无 CSS 件)")
    rd, e3 = api("repos/%s/readme" % slug, token)
    doc = {}
    if rd is not None:
        try:
            doc = classify_readme(base64.b64decode(rd.get("content") or "").decode("utf-8", "replace"))
        except Exception as ex:
            errs.append("readme:%s" % ex)
    else:
        errs.append("readme:%s" % e3)
    return tree, trunc, html, css, "; ".join(errs), doc


# ---------------- self：同一把尺跑工作树 ----------------
SKIP = ("/.git/", "node_modules/", ".codebuddy/", "_shots/", "target/", "server/data/",
        "web_raw/", "video_raw/", "archive/")


def self_blobs():
    for pat in ("src/**/*.html", "src/css/*.css", "src/*.webmanifest", "src/**/*.js",
                "deploy/**/*.html", "deploy/**/*.css", "README.md"):
        for p in sorted(ROOT.glob(pat)):
            if p.is_file():
                yield str(p.relative_to(ROOT)).replace("\\", "/"), p


def probe_self():
    paths = []
    blobs = {}
    for rel, p in self_blobs():
        if any(x in "/" + rel for x in SKIP):
            continue
        paths.append(rel)
        try:
            blobs[rel] = p.read_text("utf-8", errors="replace")
        except Exception:
            blobs[rel] = ""
    t = classify_tree(paths)
    h = classify_html(blobs.get(t["html_shallow"][0], "") if t["html_shallow"] else "")
    c = classify_css(blobs.get(t["css_largest"][0], "") if t["css_largest"] else "")
    doc = classify_readme(blobs.get("README.md", ""))
    return t, h, c, doc, paths


# ---------------- selftest：正例 + 反例 + 边界 ----------------
def selftest():
    ok, fail = 0, []
    cases = [
        ("正例：标准 viewport",
         '<meta name="viewport" content="width=device-width, initial-scale=1.0">', True, False),
        ("反例①：禁缩放必须被抓（这是主动决策）",
         '<meta name="viewport" content="width=device-width, initial-scale=1, user-scalable=no">',
         True, True),
        ("反例②：maximum-scale=1 同义禁缩放",
         '<meta name="viewport" content="width=device-width, maximum-scale=1">', True, True),
        ("反例③：maximum-scale=5 不得判成禁缩放",
         '<meta name="viewport" content="width=device-width, maximum-scale=5">', True, False),
        ("反例④：缺 viewport",
         "<head><title>x</title></head>", False, False),
    ]
    for name, meta, want_vp, want_noscale in cases:
        h = classify_html(meta)
        if h["has_viewport"] == want_vp and h["scales_disabled"] == want_noscale:
            ok += 1
        else:
            fail.append("%s -> %s" % (name, h))
    css = ("@media(max-width:768px){a{}} @media (pointer:coarse){button{min-height:48px}} "
           "@media (hover:none){b{}} @media screen and (min-width:44px){c{}}")
    c = classify_css(css)
    if c["media"] == 4 and c["pointer_aware"] == 2 and c["target44"] == 2:
        ok += 1
    else:
        fail.append("CSS 计数失真：%s（应 media=4 pointer=2 target44=2）" % c)
    # 边界 A：空 CSS 不得报"已按指针适配"
    z = classify_css("")
    if z["media"] == 0 and z["pointer_aware"] == 0:
        ok += 1
    else:
        fail.append("边界A 空 CSS 非零：%s" % z)
    # 边界 B：无 HTML 入口时必须给"非 Web 面"而不是"无 viewport"（二者语义不同，禁混同）
    v = verdict(classify_tree(["README.md"]), {}, {}, {})
    if v == "无 HTML 入口(非 Web 面)":
        ok += 1
    else:
        fail.append("边界B 无入口被误判：%s" % v)
    # 边界 C：tree 分类器不得把 node_modules 里的 html 算成入口
    t = classify_tree(["node_modules/x/index.html", "public/app.html"])
    if t["html"] == 1 and t["html_shallow"][0] == "public/app.html":
        ok += 1
    else:
        fail.append("边界C 噪声未排除：%s" % t)
    # 边界 D：**按大小**取 CSS（首版按深度取，抓到 reset 小文件、漏掉真样式表）
    t2 = classify_tree(["public/reset.css", "src/styles/app-desktop.css", "src/a.css"],
                       sizes={"public/reset.css": 900, "src/styles/app-desktop.css": 88_000,
                              "src/a.css": 120})
    if t2["css_largest"][0] == "src/styles/app-desktop.css":
        ok += 1
    else:
        fail.append("边界D 未按 blob size 取最大 CSS：%s" % t2["css_largest"])
    # 边界 E：`.cssx` 这类不存在的后缀不得被当成有效 CSS 面（首版 `\.cssx?` 的教训反向钉住）
    t3 = classify_tree(["src/legacy.cssx", "src/real.css"])
    if t3["css"] == 1 and t3["css_largest"][0] == "src/real.css":
        ok += 1
    else:
        fail.append("边界E CSS 后缀面失准：%s" % t3)
    n = len(cases) + 6
    for x in fail:
        print("  SELFTEST-FAIL " + x)
    print("MOBILE-PEER-SELFTEST: %d/%d" % (ok, n))
    return 0 if ok == n else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="")
    ap.add_argument("--self-only", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    token = os.environ.get("GITHUB_TOKEN") or ""
    if not token:
        token = subprocess.run(["gh", "auth", "token"], capture_output=True,
                               text=True).stdout.strip()
    if not token:
        print("MOBILEPEER-ENV: 无 GitHub token ⇒ 不采数、不判绿")
        return 2
    rows, na, out_of_scope = {}, [], []
    for p in ([] if a.self_only else PEERS):
        slug, tier = p["repo"], p["tier"]
        t, trunc, h, c, err, doc = probe_repo(slug, token)
        rows[slug] = {"tier": tier, "tree": t, "html": h, "css": c, "readme": doc,
                      "truncated": trunc, "err": err}
        if not t or not t.get("html"):
            # 范围判定必须在 err 之前：`css:NA` 是我自己塞进 errs 的，让"非 Web 仓"被它抢先判成
            # "取数失败"就是拿顺序冒充语义（同族：把 NA 并入 0）
            if err and not t:
                na.append("%s(%s)" % (slug, err[:60]))
            else:
                out_of_scope.append(slug)
        elif err:
            na.append("%s(%s)" % (slug, err[:60]))
        elif not t.get("css"):
            na.append("%s(有 HTML 入口但仓内无 CSS 件⇒CSS 轴未取到)" % slug)
        elif trunc:
            na.append("%s(树被截断⇒零命中不可信)" % slug)
        print("[%-3s] %-33s vp=%-5s 禁缩放=%-5s mq=%-3d 指针适配=%-2d ≥44声明=%-2d PWA=%-5s 壳=%-4s %s%s"
              % (tier, slug, h.get("has_viewport", "NA"), h.get("scales_disabled", "NA"),
                 c.get("media", -1), c.get("pointer_aware", -1), c.get("target44", -1),
                 bool(t.get("manifest")), bool(t.get("mobile_shell")),
                 verdict(t, h, c, doc), "｜截断" if trunc else ""))
    st, sh, sc, sd, spaths = probe_self()
    rows["__self__"] = {"tree": st, "html": sh, "css": sc, "readme": sd}
    print("[self] %-33s vp=%-5s 禁缩放=%-5s mq=%-3d 指针适配=%-2d ≥44声明=%-2d PWA=%-5s 壳=%-4s %s"
          % ("心屿 SoulIsle", sh.get("has_viewport"), sh.get("scales_disabled"),
             sc.get("media"), sc.get("pointer_aware"), sc.get("target44"),
             bool(st.get("manifest")), bool(st.get("mobile_shell")), verdict(st, sh, sc, sd)))
    print("-" * 120)
    n = len(rows) - 1
    if n:
        vps = sum(1 for k, v in rows.items() if k != "__self__" and v["html"].get("has_viewport"))
        nos = sum(1 for k, v in rows.items() if k != "__self__" and v["html"].get("scales_disabled"))
        ptr = sum(1 for k, v in rows.items() if k != "__self__" and v["css"].get("pointer_aware"))
        pwa = sum(1 for k, v in rows.items() if k != "__self__" and v["tree"].get("manifest"))
        htmls = sum(1 for k, v in rows.items() if k != "__self__" and v["tree"].get("html"))
        print("peers：有 HTML 入口 %d/%d ｜ 有 viewport %d ｜ **禁缩放 %d** ｜ 按指针类型适配 %d ｜ 有 manifest %d"
              % (htmls, n, vps, nos, ptr, pwa))
    blind = len(na)
    oos = len(out_of_scope)
    # 恒等式按**轴**成立：total = 可用 + 未取到(NA) + 范围外(非 Web)。三者不并入彼此的 0。
    tot = n if not a.self_only else 0
    print("应测 %d ｜ 可用 %d ｜ NA/截断 %d ｜ 范围外(非 Web 面) %d ｜ 恒等式：%s"
          % (tot, tot - blind - oos, blind, oos,
             "OK" if (tot - blind - oos) + blind + oos == tot else "不成立"))
    if out_of_scope:
        print("  范围外（无 HTML 入口，CSS 轴不适用）：" + "; ".join(out_of_scope))
    if na:
        print("  NA/截断：" + "; ".join(na))
    if a.json:
        Path(a.json).write_bytes(json.dumps(
            {"repos": rows, "na": na, "denominator": n, "blind": blind,
             "out_of_scope": out_of_scope, "usable": n - blind - len(out_of_scope),
             "ceiling_note": "本探针只出结构与声明证据；对手触控几何未测，不得据此下体验结论",
             "ts": subprocess.run(["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"],
                                  capture_output=True, text=True).stdout.strip()},
            ensure_ascii=False, indent=1).encode("utf-8"))
        print("快照 -> " + a.json)
    if a.self_only:
        return 0
    return 1 if na else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
