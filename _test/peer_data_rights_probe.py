# -*- coding: utf-8 -*-
"""对标 r44 探针：**数据主体权利与留存治理**（16 仓 + self，两通道同尺）。

七维里「适用场景 / 可扩展性」此前量过功能与工程面，但**"用户数据归谁、能不能带走、能不能删干净"**
这一格从来没进过观测窗（✅ 实测 `grep -l "导出|可携|删除权|留存" 交付物/对标分析报告-*.md` 在 r44 前 = 0 命中）。
对心屿尤其要紧：存的是情绪记录与原话对话，按个保法口径属**敏感个人信息**。

通道 A 文件树：隐私/数据文档（privacy / GDPR / 个保 / 数据处理）、迁移工具（flyway/alembic/prisma/django
                migrations 等，**没迁移工具 = schema 一变用户数据就悬空**）、导出/删除出口命名件
通道 B README：隐私政策链接、数据导出/删除说明、留存期承诺
取不到的仓记 BLIND 并点名原因，禁与 0 混同；self 与 peers 同一组正则。
用法：python _test/peer_data_rights_probe.py [--json out.json] [--self-only] [--selftest]
退出码：0=分母齐 1=有 BLIND 或桩未过 2=无 token
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
from benchmark_metrics import PEERS, ROOT

NOISE = re.compile(r"(^|/)(node_modules|vendor|dist|build|target|\.venv|venv|site-packages|\.git/)/", re.I)
# 隐私件必须是**文档类扩展名**：首版收 `[-\w.]*` 把 `src/privacy_filter.js` 也算成隐私政策件
# ——那是个源码文件。桩的反例②当场抓住（R263：是判据口径错，不改桩）。
PRIVACY = re.compile(r"(^|/)(privacy[-\w.]*)?\.(md|html?|txt|pdf|rst)$", re.I)
MIGRATION = re.compile(r"(^|/)(db/migrate/|migrations/|flyway/|alembic\.ini|alembic/|dbschema/"
                       r"|prisma/migrations/|alembic/versions/|meta/versions/.*\.py$)", re.I)
EXPORT = re.compile(r"(export[-\w.]*(data|json|csv)|data[-_]?(export|portability)|delete[-\w.]*account"
                    r"|erase[-\w.]*|/api/(v\d/)?(export|delete[-_]me|me/export))", re.I)
DOC_RX = {
    "privacy_link": re.compile(r"(privacy polic|隐私政策|数据处理协议|data processing agreement)", re.I),
    "export_doc": re.compile(r"(export (my |your )?data|download (my|your) data|数据导出|导出数据"
                             r"|data portability|可携权)", re.I),
    "delete_doc": re.compile(r"(delete my account|erasure|删除账户|注销|删除我的数据|right to be forgotten)", re.I),
    "retention_doc": re.compile(r"(retention (period|policy)|留存期|保存期限|data retention)", re.I),
}


def classify(paths):
    f = lambda rx: sorted(p for p in paths if rx.search(p) and not NOISE.search(p))
    return {"privacy_docs": f(PRIVACY), "migration": f(MIGRATION), "export": f(EXPORT)}


def api(path, token, accept="application/vnd.github+json"):
    req = urllib.request.Request("https://api.github.com/" + path,
                                 headers={"User-Agent": "xinyu-datarights-probe", "Accept": accept})
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            return (json.loads(r.read().decode("utf-8", "replace")) if "raw" not in accept
                    else r.read().decode("utf-8", "replace")), ""
    except Exception as e:
        return None, "http=%s" % getattr(e, "code", type(e).__name__)


def readme_flags(txt):
    return {k: len(rx.findall(txt)) for k, rx in DOC_RX.items() if rx.search(txt)}


SKIP = ("/.git/", "node_modules/", ".codebuddy/", "_shots/", "target/", "server/data/",
        ".wrangler/", "web_raw/", "video_raw/")


def probe_repo(slug, token):
    data, err = api("repos/%s/git/trees/HEAD?recursive=1" % slug, token)
    if data is None:
        return {}, err
    if data.get("truncated"):
        return {}, "truncated"
    paths = [t.get("path", "") for t in data.get("tree", []) if t.get("type") == "blob"]
    row = {"tree": classify(paths)}
    rtxt, rerr = api("repos/%s/readme" % slug, token, "application/vnd.github.raw+json")
    row["readme"] = readme_flags(rtxt) if isinstance(rtxt, str) else {}
    row["readme_err"] = rerr if not isinstance(rtxt, str) else ""
    return row, ""


def probe_self():
    paths = []
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        r = str(p.relative_to(ROOT)).replace("\\", "/")
        if not any(x in "/" + r for x in SKIP):
            paths.append(r)
    fp = ROOT / "README.md"
    return {"tree": classify(paths),
            "readme": readme_flags(fp.read_bytes().decode("utf-8", "replace") if fp.exists() else ""),
            "readme_err": ""}


FIXTURE = [
    ("docs/privacy.md", "privacy_docs", "正例①隐私文档"),
    ("db/migrate/20240101_init.sql", "migration", "正例②rails 迁移"),
    ("alembic/versions/a1_init.py", "migration", "正例③alembic"),
    ("src/api/data_export.py", "export", "正例④导出出口"),
    ("node_modules/gdpr/index.js", "", "反例①依赖目录不得算"),
    ("src/privacy_filter.js", "", "反例②源码文件名含 privacy 子串但非政策件"),
    ("dist/export-bundle.js", "", "反例③构建产物不算"),
]


def run_selftest():
    ok, fail, n = 0, [], 0
    for path, bucket, note in FIXTURE:
        cls = classify([path])
        hit = bool(cls[bucket]) if bucket else not any(cls[k] for k in cls)
        n += 1
        if hit:
            ok += 1
        else:
            fail.append("%s (%s)" % (note, path))
    d = readme_flags("See our Privacy Policy. You can download your data or delete my account."
                     " Retention period: 90 days.")
    n += 1
    if all(k in d for k in ("privacy_link", "export_doc", "delete_doc", "retention_doc")):
        ok += 1
    else:
        fail.append("README 正样本未被读全：%s" % sorted(d))
    n += 1
    if not readme_flags("A lovely chatbot."):
        ok += 1
    else:
        fail.append("普通 README 必须零命中")
    n += 1
    if all(not v for v in classify([]).values()):
        ok += 1
    else:
        fail.append("零输入异常")
    for x in fail:
        print("  DATARIGHTS-SELFTEST-FAIL " + x)
    print("DATARIGHTS-SELFTEST: %d/%d（路径 %d｜README 2｜边界 1）" % (ok, n, len(FIXTURE)))
    return 0 if ok == n else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="")
    ap.add_argument("--self-only", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return run_selftest()
    token = os.environ.get("GITHUB_TOKEN") or subprocess.run(
        ["gh", "auth", "token"], capture_output=True, text=True).stdout.strip()
    if not token:
        print("DATARIGHTS-ENV: 无 GitHub token ⇒ 不采数、不判绿")
        return 2
    rows, blind = {}, []
    for p in ([] if a.self_only else PEERS):
        slug = p["repo"]
        row, err = probe_repo(slug, token)
        if err:
            blind.append("%s(%s)" % (slug, err))
            print("[%-3s] %-36s BLIND %s" % (p["tier"], slug, err))
            continue
        rows[slug] = {"tier": p["tier"], **row}
        t = row["tree"]
        print("[%-3s] %-36s 隐私件=%-2d 迁移=%-3d 导出/删除件=%-2d README=%s%s"
              % (p["tier"], slug, len(t["privacy_docs"]), len(t["migration"]), len(t["export"]),
                 ",".join("%s:%d" % (k, v) for k, v in sorted(row["readme"].items())) or "none",
                 "｜README取数失败" if row.get("readme_err") else ""))
    st = probe_self()
    rows["__self__"] = st
    t = st["tree"]
    print("[self] %-36s 隐私件=%-2d 迁移=%-3d 导出/删除件=%-2d README=%s"
          % ("心屿 SoulIsle", len(t["privacy_docs"]), len(t["migration"]), len(t["export"]),
             ",".join("%s:%d" % (k, v) for k, v in sorted(st["readme"].items())) or "none"))
    print("-" * 118)
    n = len(rows) - (0 if a.self_only else 1)
    if n:
        c = lambda pred: sum(1 for k, v in rows.items() if k != "__self__" and pred(v))
        print("peers：有隐私/数据文档 %d/%d ｜ 有迁移工具 %d/%d ｜ 有导出或删除命名件 %d/%d ｜"
              " README 写明导出 %d/%d、删除 %d/%d、留存期 %d/%d"
              % (c(lambda v: v["tree"]["privacy_docs"]), n,
                 c(lambda v: v["tree"]["migration"]), n,
                 c(lambda v: v["tree"]["export"]), n,
                 c(lambda v: v["readme"].get("export_doc")), n,
                 c(lambda v: v["readme"].get("delete_doc")), n,
                 c(lambda v: v["readme"].get("retention_doc")), n))
    usable = n - len(blind)
    print("应测 %s 仓 ｜ 计入分母 %s ｜ BLIND %d ｜ 恒等式：%s"
          % (n, usable, len(blind), "OK" if usable + len(blind) == n else "FAIL"))
    if blind:
        print("  BLIND：" + "; ".join(blind))
    if a.json:
        Path(a.json).write_bytes(json.dumps(
            {"repos": rows, "blind": blind, "denominator": n, "usable": usable,
             "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")},

            ensure_ascii=False, indent=1).encode("utf-8"))
        print("快照 -> " + a.json)
    return 0 if a.self_only else (1 if blind or usable + len(blind) != n else 0)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
