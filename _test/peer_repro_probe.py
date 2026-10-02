# -*- coding: utf-8 -*-
"""对标 r43 探针：**可复现构建与上手成本**（16 仓 + self，三通道同尺）。

为什么是这一面：老大点的七维里「可扩展性」此前只被 r24-r26 当成"插件市场做不做"讨论过，
**"别人拿到这份代码能不能跑起来"这一格从来没进过观测窗**
（✅ 本轮实测 `grep -l 可复现|干净克隆|lockfile 交付物/对标分析报告-*.md` = 0 命中）。
而它对本项目是**验收口径本身**：AGENTS.md 写着"本地实测 console 0 报错"，
可这条断言只在"我这台机器恰好有一份 .gitignore 掉的 demo-config.js"时才成立。

三通道（承 r38/r41/r42 的 M5⑦⑧⑨ 纪律）：
  通道 A 文件树：锁定/清单件（lockfile、`.env.example`、compose/devcontainer、Dockerfile）
                ⇒ "能不能在别的机器上重建"
  通道 B README：有没有可执行的快速上手（Quick Start 标题 + 代码块里的安装命令）
  通道 C 版本声明：依赖是**钉死**还是**浮动**（package.json deps 的精确版本比例 / requirements 是否 == 版本）
                —— A 的"有 lockfile"必须有 C 佐证，否则"有 lock 文件但依赖写 ^ 浮动"会被算成可复现。
用法：python _test/peer_repro_probe.py [--json out.json] [--self-only] [--selftest]
退出码：0=分母齐且无 NA 1=存在 NA 或 selftest 未过 2=无 GitHub token（环境）
"""
import argparse
import base64
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

NOISE = re.compile(r"(^|/)(node_modules|vendor|dist|build|target|\.venv|venv|site-packages"
                   r"|\.git/|cache|coverage)/", re.I)
LOCK_RX = re.compile(r"(^|/)(package-lock\.json|pnpm-lock\.yaml|yarn\.lock|bun\.lockb?"
                     r"|uv\.lock|poetry\.lock|Pipfile\.lock|cargo\.lock|go\.sum|composer\.lock"
                     r"|mix\.lock)$", re.I)
ENVX_RX = re.compile(r"(^|/)\.env(\.example|\.sample|\.template|\.local\.example)$", re.I)
RUNTIME_RX = re.compile(r"(^|/)(docker-compose[-\w.]*\.ya?ml|compose[-\w.]*\.ya?ml"
                        r"|devcontainer\.json|\.devcontainer/devcontainer\.json|Dockerfile)$", re.I)
GUIDE_RX = re.compile(r"(^|/)(docs/)?(quick[-_]?start|getting[-_]?started|install|setup)([-\w.]*)\.md$", re.I)
README_H = {
    "quickstart": re.compile(r"#+\s*(quick ?start|getting started|installation|install|快速开始|安装)", re.I),
    "codeblock": re.compile(r"```[a-zA-Z0-9]*\n"),
    "install_cmd": re.compile(r"(npm (i|install|ci)\b|pnpm (i|install)\b|yarn install|pip install"
                              r"|cargo build|go mod download|mvn (clean )?(package|install)|gradle"
                              r"|make (install|build)|docker(-compose)? up|docker build|\.\/(setup|bootstrap))", re.I),
    "env_doc": re.compile(r"(cp \.env\.example|\.env\.example|environment variable|环境变量)", re.I),
}
# 通道 C：只读 package.json 的 dependencies 段，算"精确版本"占比
PKG_DEP_BLOCK = re.compile(r'"(?:dependencies|devDependencies)"\s*:\s*\{(.*?)\}', re.S)
PKG_VER_LINE = re.compile(r'"([^"@][^"]*)"\s*:\s*"([^"]+)"')
PIN_STRICT = re.compile(r"^\d")                       # 以数字开头 = 精确钉版
REQUIREMENTS_PIN = re.compile(r"^\s*[A-Za-z0-9_.\-]+\s*==\s*[\d.]", re.M)


def classify_tree(paths):
    def f(rx):
        return sorted(p for p in paths if rx.search(p) and not NOISE.search(p))
    return {"locks": f(LOCK_RX), "envx": f(ENVX_RX), "runtime": f(RUNTIME_RX), "guides": f(GUIDE_RX)}


def readme_flags(txt):
    out = {}
    for k, rx in README_H.items():
        n = len(rx.findall(txt))
        if n:
            out[k] = n
    return out


def pin_ratio(pkg_json):
    """package.json 文本 -> (钉死数, 总数)。非 JS 仓返回 (None, 0) 表示不适用，禁并入 0。

    ⚠️ 逐条匹配走 finditer 走**整段**，不按行切：首版写 `for line in block.splitlines()`
    + 每行一次 `search`，于是**压缩成一行的 JSON**（peers 里极常见）只数到第一条依赖，
    `"1.2.3"` 与 `"^1.0.0"` 明明都在，却报 (1,1) —— 分母被静默缩小（M5⑦ 同族，
    这次是量别人家的钉版率时自己犯的）。
    """
    deps, tot = 0, 0
    for m in PKG_DEP_BLOCK.finditer(pkg_json):
        for vm in PKG_VER_LINE.finditer(m.group(1)):
            tot += 1
            if PIN_STRICT.match(vm.group(2).strip()):
                deps += 1
    return (deps, tot) if tot else (None, 0)


def api(path, token, accept="application/vnd.github+json"):
    req = urllib.request.Request("https://api.github.com/" + path,
                                 headers={"User-Agent": "xinyu-repro-probe", "Accept": accept})
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            body = r.read().decode("utf-8", "replace")
            return (json.loads(body) if accept.endswith("json") and "raw" not in accept
                    else body), ""
    except Exception as e:
        return None, "http=%s" % getattr(e, "code", type(e).__name__)


def probe_repo(slug, token):
    data, err = api("repos/%s/git/trees/HEAD?recursive=1" % slug, token)
    if data is None:
        return {}, "tree:" + err
    if data.get("truncated"):
        return {}, "tree:truncated(零命中不可信)"
    paths = [t.get("path", "") for t in data.get("tree", []) if t.get("type") == "blob"]
    row = {"tree": classify_tree(paths)}
    rtxt, rerr = api("repos/%s/readme" % slug, token, "application/vnd.github.raw+json")
    if rtxt is None:
        return row, "readme:" + rerr
    row["readme"] = readme_flags(rtxt if isinstance(rtxt, str) else "")
    # 通道 C：JS 仓读 package.json；Python 仓看 requirements 是否 ==钉版
    pkgs = [p for p in paths if p.endswith("package.json") and not NOISE.search(p)]
    reqs = [p for p in paths if re.search(r"(^|/)(requirements[^/]*\.txt|pyproject\.toml)$", p)]
    pinned, total, c_err = None, 0, []
    if pkgs:
        raw, e = api("repos/%s/contents/%s" % (slug, pkgs[0]), token)
        if raw is None:
            c_err.append("pkg:" + e)
        else:
            try:
                txt = base64.b64decode(raw.get("content") or "").decode("utf-8", "replace")
                pinned, total = pin_ratio(txt)
            except Exception as x:
                c_err.append("decode:%s" % x)
    elif reqs:
        raw, e = api("repos/%s/contents/%s" % (slug, reqs[0]), token)
        if raw is None:
            c_err.append("req:" + e)
        else:
            try:
                txt = base64.b64decode(raw.get("content") or "").decode("utf-8", "replace")
                eq = len(REQUIREMENTS_PIN.findall(txt))
                alln = len([l for l in txt.splitlines() if l.strip() and not l.startswith("#")])
                pinned, total = eq, alln
            except Exception as x:
                c_err.append("decode:%s" % x)
    row["pin"] = {"pinned": pinned, "total": total, "err": c_err}
    row["c_status"] = ("ok" if pinned is not None else
                       ("unverified:" + ";".join(c_err) if c_err else "not_applicable"))
    return row, ""


SKIP_PARTS = ("/.git/", "node_modules/", ".codebuddy/", "_shots/", "target/", "server/data/",
              "web_raw/", "video_raw/", ".wrangler/", ".venv/")


def self_paths():
    out = []
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        r = str(p.relative_to(ROOT)).replace("\\", "/")
        if any(x in "/" + r for x in SKIP_PARTS):
            continue
        out.append(r)
    return out


def probe_self():
    paths = self_paths()
    row = {"tree": classify_tree(paths), "pin": {"pinned": None, "total": 0, "err": []},
           "c_status": "not_applicable"}
    fp = ROOT / "README.md"
    row["readme"] = readme_flags(fp.read_bytes().decode("utf-8", "replace")) if fp.exists() else {}
    pkgs = [p for p in paths if p.endswith("package.json")]
    reqs = [p for p in paths if re.search(r"(^|/)(requirements[^/]*\.txt|pyproject\.toml)$", p)]
    pom = [p for p in paths if p.endswith("pom.xml")]
    if pkgs:
        d, t = pin_ratio((ROOT / pkgs[0]).read_bytes().decode("utf-8", "replace"))
        row["pin"], row["c_status"] = {"pinned": d, "total": t, "err": []}, ("ok" if d else "not_applicable")
    elif reqs:
        txt = (ROOT / reqs[0]).read_bytes().decode("utf-8", "replace")
        eq, alln = len(REQUIREMENTS_PIN.findall(txt)), len([l for l in txt.splitlines()
                                                           if l.strip() and not l.startswith("#")])
        row["pin"] = {"pinned": eq, "total": alln, "err": []}
        row["c_status"] = "ok" if alln else "not_applicable"
    elif pom:
        row["c_status"] = "jvm_pom(版本由 parent BOM 仲裁，无 lock 概念)"
    return row


FIXTURE = [
    ("package-lock.json", "locks", "正例①：npm lock"),
    ("pnpm-lock.yaml", "locks", "正例②：pnpm lock"),
    ("Cargo.lock", "locks", "正例③：cargo lock"),
    (".env.example", "envx", "正例④：环境样本"),
    ("docker-compose.yml", "runtime", "正例⑤：compose"),
    ("docs/quick-start.md", "guides", "正例⑥：快速上手专章"),
    ("node_modules/foo/package-lock.json", "", "反例①：依赖目录不得算"),
    ("dist/compose.yml", "", "反例②：构建产物不算"),
    ("src/lorem_setup.md", "", "反例③：文件名含 setup 但非 docs 专章"),
    ("README.md", "", "反例④：README 不进 guides"),
]
PIN_FIXTURE = [
    ('{"dependencies": {"a": "1.2.3", "b": "^1.0.0"}}', (1, 2), "混合：1 钉 1 浮动"),
    # 专属输入面：压缩成一行的 JSON —— 首版按行切分，这一条只数到 1 个分母（分母被静默缩小）
    ('{"dependencies":{"a":"1.2.3","b":"^1.0.0","c":"2.0.0"}}', (2, 3),
     "正例⑥：一行 JSON 也必须逐条数（首版在这里少数分母）"),
    ('{"dependencies": {"a": "~1.2", "b": "workspace:*"}}', (0, 2), "反例⑤：~ 与 workspace:* 都算浮动（进分母不进分子）"),
    ('{"devDependencies": {"x": "4.0.1"}, "dependencies": {"y": "4.0.0"}}', (2, 2), "两段都算"),
    ('{"dependencies": {}}', (None, 0), "反例⑥：空段必须给 None（不适用）而不是 0/0"),
    ('not json at all', (None, 0), "反例⑦：无命中必须为空"),
]


def run_selftest():
    ok, fail, n = 0, [], 0

    def want(cond, note):
        nonlocal n, ok
        n += 1
        if cond:
            ok += 1
        else:
            fail.append(note)

    for path, bucket, note in FIXTURE:
        cls = classify_tree([path])
        hit = bool(cls[bucket]) if bucket else not any(cls[k] for k in cls)
        want(hit, "%s (%s)" % (note, path))
    for txt, exp, note in PIN_FIXTURE:
        want(pin_ratio(txt) == exp, "%s 实得 %s 期望 %s" % (note, pin_ratio(txt), exp))
    # 边界 A：零输入不得判绿
    e = classify_tree([])
    want(all(not v for v in e.values()), "边界A 零输入应全空")
    # 边界 B：README 三 flag 必须能命中（否则"16 家都没写快速上手"是尺瞎）
    rf = readme_flags("# Quick Start\n```bash\nnpm ci\n```\n\n"
                      "Copy .env.example to .env and set the key.\n")
    want(rf.get("quickstart") and rf.get("codeblock") and rf.get("install_cmd") and rf.get("env_doc"),
         "边界B README 正样本未被读全：%s" % rf)
    want(not readme_flags("just prose, nothing runnable"), "边界C 普通 README 必须零命中")
    for x in fail:
        print("  REPRO-SELFTEST-FAIL " + x)
    print("REPRO-SELFTEST: %d/%d（路径 %d＝正%d/反%d｜钉版 %d｜边界 3）"
          % (ok, n, len(FIXTURE), sum(1 for f in FIXTURE if f[1]),
             sum(1 for f in FIXTURE if not f[1]), len(PIN_FIXTURE)))
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
        print("REPRO-ENV: 无 GitHub token ⇒ 不采数、不判绿")
        return 2
    rows, blind = {}, []
    for p in ([] if a.self_only else PEERS):
        slug = p["repo"]
        row, reason = probe_repo(slug, token)
        if reason:
            blind.append("%s(%s)" % (slug, reason))
            print("[%-3s] %-36s BLIND %s" % (p["tier"], slug, reason))
            continue
        rows[slug] = {"tier": p["tier"], **row}
        t, rd, pn = row["tree"], row["readme"], row["pin"]
        print("[%-3s] %-36s lock=%-2d envx=%-2d runtime=%-2d guide=%-2d README=%-28s 钉版=%s/%s (%s)"
              % (p["tier"], slug, len(t["locks"]), len(t["envx"]), len(t["runtime"]),
                 len(t["guides"]),
                 ",".join("%s:%d" % (k, v) for k, v in sorted(rd.items())) or "none",
                 pn["pinned"], pn["total"], row["c_status"]))
    st = probe_self()
    rows["__self__"] = st
    t, rd, pn = st["tree"], st["readme"], st["pin"]
    print("[self] %-36s lock=%-2d envx=%-2d runtime=%-2d guide=%-2d README=%-28s 钉版=%s/%s (%s)"
          % ("心屿 SoulIsle", len(t["locks"]), len(t["envx"]), len(t["runtime"]), len(t["guides"]),
             ",".join("%s:%d" % (k, v) for k, v in sorted(rd.items())) or "none",
             pn["pinned"], pn["total"], st["c_status"]))
    print("-" * 124)
    n = len(rows) - (0 if a.self_only else 1)
    if n:
        def cnt(pred):
            return sum(1 for k, v in rows.items() if k != "__self__" and pred(v))
        have_lock = cnt(lambda v: v["tree"]["locks"])
        have_env = cnt(lambda v: v["tree"]["envx"])
        have_rt = cnt(lambda v: v["tree"]["runtime"])
        have_qs = cnt(lambda v: v["readme"].get("quickstart") or v["tree"]["guides"])
        cok = [k for k, v in rows.items() if k != "__self__" and v["c_status"] == "ok"]
        tight = cnt(lambda v: v["pin"]["pinned"] is not None and v["pin"]["total"]
                    and v["pin"]["pinned"] / v["pin"]["total"] >= 0.9)
        print("peers：有 lockfile %d/%d ｜ 有 .env.example %d/%d ｜ 有 compose/Dockerfile %d/%d ｜"
              " 有可执行快速上手 %d/%d ｜ 钉版率≥90%% %d/%d（通道 C 可判 %d 家）"
              % (have_lock, n, have_env, n, have_rt, n, have_qs, n, tight, len(cok), len(cok)))
    usable = n - len(blind)
    print("应测 %s 仓 ｜ 计入分母 %s ｜ BLIND %d ｜ 恒等式 usable+blind==总数：%s"
          % (n, usable, len(blind), "OK" if usable + len(blind) == n else "FAIL"))
    if blind:
        print("  BLIND：" + "; ".join(blind))
    if a.json:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        Path(a.json).write_bytes(json.dumps(
            {"repos": rows, "blind": blind, "denominator": n, "usable": usable, "ts": ts},
            ensure_ascii=False, indent=1).encode("utf-8"))
        print("快照 -> " + a.json)
    return 0 if a.self_only else (1 if blind or usable + len(blind) != n else 0)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
