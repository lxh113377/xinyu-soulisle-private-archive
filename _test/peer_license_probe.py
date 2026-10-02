# -*- coding: utf-8 -*-
"""对标 r46 探针：**许可与供给链合规**（16 仓 + self，双通道同尺）。

为什么是这一面：r45 量完"东西怎么交出去"（release/版本），漏了**交出去的东西的权利归属**。
本项目直接 vendored 四个第三方文件对外发布，而仓库根 `LICENSE` 自称 MIT 且被 GitHub 采信
（`gh api repos/{slug}` 实测 `license.spdx_id=MIT`）⇒ 整仓被声明成 MIT，而实际含
两个 GreenSock 标准许可文件与一个 MPL-2.0 文件。这不是文档美观问题，是**对外错误声明许可**。

与既有面的边界（不重复）：
  · r45 `peer_release_probe` 量"发不发版、多久发一次"—— 不看 LICENSE 内容。
  · r41 `peer_test_asset_probe` 量测试资产  —— 不看许可。
  · 本件量的是：**许可声明是否可信 + vendored 代码有没有随附归属件**。

关键指标（不是"有没有 LICENSE"，那个几乎人人都有、无区分度）：
  **有 vendored 第三方代码的家里，同时带 NOTICE / THIRD-PARTY / ATTRIBUTION 类归属件的 proportion**
  —— 这正是缺口所在的那一格，也是评委/下游最容易复核的一条。

双通道：
  通道 A = GitHub 自己检测的 license 字段（REST `repos/{slug}` 的 `license.spdx_id`）
           ⇒ 用平台的检测而不是"仓库里有 LICENSE 文件就算合规"，避免自证。
  通道 B = 默认分支递归文件树：LICENSE 类件 / 归属类件 / vendored 目录与文件计数（truncated 必查）
  未取到一律 NA(原因)，禁与 0 混同；self 与 peers 同一组正则，不搞双标。
用法：python _test/peer_license_probe.py [--json out.json] [--self-only] [--selftest]
退出码：0=分母齐且无 NA 1=存在 NA 或 selftest 未过 2=无 GitHub token（环境）
"""
import argparse
import json
import os
import re
import subprocess
from datetime import datetime, timezone
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from benchmark_metrics import PEERS, ROOT   # 分母唯一真相源 = 台账池（不另立清单）

# ---------- 通道 B 的分类器（纯函数，selftest 直接打它） ----------
LICENSE_FILE = re.compile(r"(^|/)(LICENSE|LICENCE|COPYING|Open[._-]Source|LICENSES?/.+)$", re.I)
# 归属类件：只认业界通行名，不自造宽匹配。
# ⚠ 扩展名必须白名单：首版写成 `(\..+)?` 于是 `notice.html`（业务页面）被算成归属件 ——
# 被自己的反例④当场抓到，属"给可选后缀开任意匹配"的通用形态。
_DOC_EXT = r"(?:\.(?:md|markdown|txt|rst|adoc))?"
NOTICE_FILE = re.compile(
    r"(^|/)(NOTICES?|THIRD[-_]PARTY[-_](?:NOTICES|LICENSES)|ATTRIBUTIONS?|CREDITS"
    r"|OPEN[-_]?SOURCE[-_]?LICENSES?)(?:[-_][A-Za-z0-9]+)?" + _DOC_EXT + r"$", re.I)
VENDOR_DIR = re.compile(r"(^|/)(vendor|vendors|third[-_]party|thirdparty|third[-_]party_licenses?)/", re.I)
# 依赖目录**不算** vendored 一手资产：node_modules 是安装产物，每仓都有，纳进来分母就废了
NOISE = re.compile(r"(^|/)(node_modules|\.venv|venv|site-packages|dist|build|target|\.git/)/", re.I)
SRC_EXTS = re.compile(r"\.(js|ts|mjs|cjs|css|py|java|kt|go|rs|php|rb|woff2?|ttf|json)$", re.I)


def classify_tree(paths):
    """paths: [相对路径] -> dict。只统计"仓库自己带出去的第三方代码"，安装产物不算。"""
    lic = [p for p in paths if LICENSE_FILE.search(p) and not NOISE.search(p)]
    notice = [p for p in paths if NOTICE_FILE.search(p) and not NOISE.search(p)]
    vend = [p for p in paths if VENDOR_DIR.search(p) and not NOISE.search(p)
            and SRC_EXTS.search(p)]
    root_lic = [p for p in lic if "/" not in p]
    return {"license_files": len(lic), "root_license": bool(root_lic),
            "license_samples": sorted(lic)[:3],
            "notice_files": len(notice), "notice_samples": sorted(notice)[:3],
            "vendored": len(vend), "vendored_samples": sorted(vend)[:3]}


def verdict(lic_files, root_license, notice_files, vendored, spdx):
    """把两通道折成一条结论（self 与 peers 共用，禁两套尺）。"""
    if spdx in (None, "", "no-api"):
        spdx = "NA"
    if not lic_files:
        return "无 LICENSE 件"
    if vendored and not notice_files:
        return "有 vendored 无归属件"
    if vendored and notice_files:
        return "有 vendored 且带归属件"
    return "仅 LICENSE（无 vendored）"


# ---------- GitHub API ----------
def api(path, token):
    req = urllib.request.Request("https://api.github.com/" + path,
                                 headers={"User-Agent": "xinyu-license-probe",
                                          "Accept": "application/vnd.github+json"})
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            return json.loads(r.read().decode("utf-8", "replace")), ""
    except Exception as e:
        return None, "http=%s" % getattr(e, "code", type(e).__name__)


def probe_repo(slug, token):
    meta, err1 = api("repos/%s" % slug, token)
    spdx = "NA"
    if meta is not None:
        spdx = ((meta.get("license") or {}).get("spdx_id")) or "none"
        if spdx == "NOASSERTION":
            spdx = "custom/none"
    tree, err2 = api("repos/%s/git/trees/HEAD?recursive=1" % slug, token)
    if tree is None:
        return {}, False, "+".join(x for x in (err1, err2) if x) or "tree-fail", spdx
    paths = [t.get("path", "") for t in tree.get("tree", []) if t.get("type") == "blob"]
    return classify_tree(paths), bool(tree.get("truncated")), \
        "+".join(x for x in (err1,) if x), spdx


# ---------- self：同一把尺跑工作树 ----------
SKIP = ("/.git/", "node_modules/", ".codebuddy/", "_shots/", "target/", "server/data/",
        "web_raw/", "video_raw/", "archive/")


def self_paths():
    out = []
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        r = str(p.relative_to(ROOT)).replace("\\", "/")
        if any(x in "/" + r for x in SKIP):
            continue
        out.append(r)
    return out


LOCAL_SPDX_CMD = ["gh", "api", "--jq", ".license.spdx_id"]


def self_spdx():
    """通道 A 的 self 侧：既看 GitHub 怎么标我们，也看本地 LICENSE 自己怎么说。"""
    txt = (ROOT / "LICENSE").read_text("utf-8", errors="replace") if (ROOT / "LICENSE").exists() else ""
    first = txt.strip().splitlines()[0] if txt.strip() else ""
    local = "MIT" if first.lower().startswith("mit license") else ("Apache" if "Apache License" in txt else "unknown")
    try:
        r = subprocess.run(LOCAL_SPDX_CMD + ["repos/" + self_slug()], capture_output=True,
                           text=True, timeout=40)
        remote = (r.stdout or "").strip() or "NA"
    except Exception:
        remote = "NA"
    return local, remote


def self_slug():
    try:
        r = subprocess.run(["git", "remote", "get-url", "origin"], cwd=str(ROOT),
                           capture_output=True, text=True, timeout=20)
        m = re.search(r"[:/]([^/:]+/[^/]+?)(?:\.git)?$", (r.stdout or "").strip())
        return m.group(1) if m else ""
    except Exception:
        return ""


def probe_self():
    return classify_tree(self_paths())


# ---------- selftest：正例 + 反例 + 边界，证明分类器非恒真 ----------
FIX = [
    ("LICENSE", "license", "仓库根 LICENSE"),
    ("LICENSES/MIT.txt", "license", "LICENSES 目录（REUSE 风格）"),
    ("NOTICE", "notice", "Apache 式归属件"),
    ("THIRD-PARTY-NOTICES.md", "notice", "dotnet 式命名"),
    ("docs/ATTRIBUTIONS.md", "notice", "致谢件在子目录也算"),
    ("vendor/three.min.js", "vendored", "前端 vendored"),
    ("src/vendor/gsap.min.js", "vendored", "带路径前缀的 vendor"),
    ("third_party/axe/axe.min.js", "vendored", "third_party 目录"),
    ("node_modules/three/build/three.js", "none", "反例①：安装产物不是 vendored 一手资产"),
    ("dist/bundle.js", "none", "反例②：构建产物"),
    ("src/js/app.js", "none", "反例③：自家源码"),
    ("notice.html", "none", "反例④：业务页面不该被当成归属件（首版任意后缀中招，实测抓到）"),
    ("README.md", "none", "反例⑤：普通文档"),
    ("vendors.csv", "none", "反例⑥：vendors/ 是目录不是文件后缀"),
    ("notes.md", "none", "反例⑦：NOTIC 前缀近邻不得误命中"),
    ("credits/index.html", "none", "反例⑧：目录名叫 credits 而文件是页面"),
    ("NOTICE", "notice", "正例：无扩展名原件"),
    ("open-source-licenses.md", "notice", "正例：连字符式命名"),
]


def run_selftest():
    ok, fail = 0, []
    for p, want, note in FIX:
        c = classify_tree([p])
        got = ("license" if c["license_files"] else "") + ("notice" if c["notice_files"] else "") \
            + ("vendored" if c["vendored"] else "")
        if want == "none":
            good = got == ""
        else:
            good = want in got and (got == want or (want == "license" and got == "licensenotice"))
        if good:
            ok += 1
        else:
            fail.append("%s want=%s got=%r" % (note, want, got or "空"))
    # 边界 A：零输入不得判绿（防"分母空 = 全过"）
    e = classify_tree([])
    ok += 1 if (e["license_files"] == 0 and not e["root_license"] and e["vendored"] == 0) else 0
    if e["license_files"] or e["vendored"]:
        fail.append("边界A 零输入非空")
    # 边界 B：verdict 的区分度 —— 有 vendored 无归属件 必须与 有归属件 不同判
    v1 = verdict(1, True, 0, 4, "MIT")
    v2 = verdict(1, True, 2, 4, "MIT")
    if v1 != v2 and "无归属件" in v1:
        ok += 1
    else:
        fail.append("边界B verdict 无区分度：%s / %s" % (v1, v2))
    # 边界 C：GitHub 把自定义许可标成 NOASSERTION 时不得算成"无 LICENSE 件"
    v3 = verdict(3, True, 0, 0, "custom/none")
    if "无 LICENSE" not in v3:
        ok += 1
    else:
        fail.append("边界C NOASSERTION 被误判成无 LICENSE：%s" % v3)
    n = len(FIX) + 3
    for x in fail:
        print("  SELFTEST-FAIL " + x)
    print("LICENSE-SELFTEST: %d/%d" % (ok, n))
    return 0 if ok == n else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="")
    ap.add_argument("--self-only", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return run_selftest()
    token = os.environ.get("GITHUB_TOKEN") or ""
    if not token:
        r = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True)
        token = r.stdout.strip()
    if not token:
        print("LICENSE-ENV: 无 GitHub token ⇒ 不采数、不判绿")
        return 2
    rows, na = {}, []
    for p in ([] if a.self_only else PEERS):
        slug, tier = p["repo"], p["tier"]
        c, trunc, err, spdx = probe_repo(slug, token)
        if err or not c:
            na.append("%s(%s)" % (slug, err or "tree 空"))
        elif trunc:
            na.append("%s(树被截断⇒零命中不可信)" % slug)
        vd = c.get("vendored", -1)
        rows[slug] = {"tier": tier, "spdx": spdx, "tree": c, "truncated": trunc}
        print("[%-3s] %-34s license件=%-3d vendored=%-5d 归属件=%-3d spdx=%-12s %s%s"
              % (tier, slug, c.get("license_files", -1), vd, c.get("notice_files", -1), spdx,
                 verdict(c.get("license_files", 0), c.get("root_license", False),
                         c.get("notice_files", 0), vd, spdx), "｜截断" if trunc else ""))
    st = probe_self()
    loc, rem = self_spdx()
    rows["__self__"] = {"tree": st, "spdx_local": loc, "spdx_remote": rem}
    print("[self] %-34s license件=%-3d vendored=%-5d 归属件=%-3d spdx本地=%s spdx远端=%s ⇒ %s"
          % ("心屿 SoulIsle", st["license_files"], st["vendored"], st["notice_files"], loc, rem,
             verdict(st["license_files"], st["root_license"], st["notice_files"], st["vendored"], rem)))
    print("-" * 122)
    n = len(rows) - 1
    if n:
        withv = [v for k, v in rows.items() if k != "__self__" and v["tree"].get("vendored", 0) > 0]
        withv_notice = [v for v in withv if v["tree"].get("notice_files", 0) > 0]
        mit = sum(1 for k, v in rows.items() if k != "__self__" and v.get("spdx") == "MIT")
        none = sum(1 for k, v in rows.items() if k != "__self__" and v.get("spdx") in ("none", "NA"))
        print("peers：带 vendored 的 %d/%d ｜ 其中带归属件 %d/%d ｜ GitHub 检测 MIT %d ｜ 检测不出 %d"
              % (len(withv), n, len(withv_notice), len(withv), mit, none))
        for k, v in sorted(((k, v) for k, v in rows.items() if k != "__self__"),
                           key=lambda x: -x[1]["tree"].get("vendored", 0)):
            t = v["tree"]
            if t.get("vendored"):
                print("   %-34s vendored=%-5d 归属件=%-2d 样本=%s"
                      % (k, t["vendored"], t["notice_files"], t["vendored_samples"][:1]))
    if na:
        print("  NA/截断：" + "; ".join(na))
    print("应测 %s 仓 ｜ NA/截断 %d ｜ self 归属件=%d"
          % (n if not a.self_only else 0, len(na), st["notice_files"]))
    if a.json:
        Path(a.json).write_bytes(json.dumps(
            {"repos": rows, "na": na, "denominator": n,
             "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")},

            ensure_ascii=False, indent=1).encode("utf-8"))
        print("快照 -> " + a.json)
    if a.self_only:
        return 0
    return 1 if na else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
