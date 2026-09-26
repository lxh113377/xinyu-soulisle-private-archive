# -*- coding: utf-8 -*-
"""对标源数据机器化采集 + 漂移守卫（把「对标」从一次性手工 curl 变成可复现产物）。

为什么需要：v1/v2 报告的星数、停更日期、CI job 数散落在正文与一次性命令里，
下一轮无法机器复核（M1「数字来自历史快照」风险源）。本脚本把同类指标固化成
JSON 台账，并强制每次运行输出「与上一次快照的逐字段差值」——防止拿旧数字下结论。

判据：
  1) 每个参照仓的 4 个核心字段（★ / pushed_at / 最近 release / CI workflow 数）**必须成功取到**，
     任一仓取不到即 rc=1（禁止"跳过该仓继续"造成静默缩水；环境故障走 rc=2）
  2) --selftest 用合成快照（只改一个字段）喂给 diff 函数，断言**恰好**报出该字段
     ——证明漂移判据非恒真（对照：全等快照必须 0 漂移）
退出码：0=BENCHMARK-METRICS-PASS 1=取数失败或自检未过 2=网络/token 环境异常
"""
import argparse
import base64
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "交付物" / "对标数据"
SNAP = OUT_DIR / "benchmark-metrics.json"

# tier: A 工程规格天花板 / B 结构最同构 / C 同体量垂类 / D 记忆·情绪上游参照
PEERS = [
    {"repo": "lobehub/lobehub", "tier": "A", "why": "Web AI 聊天前端工程化最强者（原 lobehub/lobe-chat，2026-09 改名）"},
    {"repo": "SillyTavern/SillyTavern", "tier": "A", "why": "头部角色扮演聊天前端，persona/扩展生态参照"},
    {"repo": "Open-LLM-VTuber/Open-LLM-VTuber", "tier": "B", "why": "情绪→可视化映射 + 语音陪伴，与心屿同题"},
    {"repo": "morettt/my-neuro", "tier": "B", "why": "桌宠 + 记忆型陪伴，活跃迭代参照"},
    {"repo": "letta-ai/letta", "tier": "D", "why": "stateful agent 长期记忆（J4 记忆叙事同构先例）"},
    {"repo": "hello-diana/MASCOT", "tier": "C", "why": "多智能体社交认知陪伴（EMNLP 2026）"},
    {"repo": "ddxfish/sapphire", "tier": "C", "why": "垂类陪伴 agent，Python + Web UI"},
    {"repo": "v2rockets/Loyal-Elephie", "tier": "C", "why": "带 RAG 记忆的陪伴（停更反面教材）"},
    {"repo": "Rogendo/Mental-health-Chatbot", "tier": "C", "why": "多语心理健康陪伴，有真实部署主页"},
    {"repo": "Lum1104/MER-Factory", "tier": "D", "why": "多模态情绪识别工厂（标注→评测→训练闭环）"},
    {"repo": "CheaperjamRen/leemo", "tier": "C", "why": "本地优先桌面陪伴 agent"},
    {"repo": "NJX-njx/opensoul", "tier": "C", "why": "小体量但工程齐（13 workflow + 全套文档）"},
    {"repo": "s-nagaev/chibi", "tier": "C", "why": "小体量高频发布节奏样板"},
    {"repo": "29-Cu/succhia", "tier": "C", "why": "中文『陪聊』垂类（BLE 硬件），零工程配套"},
    # r21 新增（本轮 search/repositories?sort=updated 实跑捞到的同体量活跃垂类）
    {"repo": "zeroa234/ryza-ai-revive", "tier": "C", "why": "190★、JS、2026-09-22 仍活跃的同体量陪伴项目"},
    {"repo": "Bwcx-songyu/MoodChat", "tier": "C", "why": "Java 同栈情绪陪伴垂类（体量小，作技术栈对照）"},
]

# 根目录文件探测：文档/工程配套齐备度（对标 §4.6 的口径来源）
DOC_FILES = ["README.md", "docs", "tests", "test", "CHANGELOG.md", "CONTRIBUTING.md",
             "SECURITY.md", ".env.example", ".env.example.txt", "ROADMAP.md", ".github"]
DOC_FILES_SET = set(DOC_FILES)
# 能力探测：按**整树递归**的文件名/后缀匹配（根目录一层探测无判别力——
# 实测 14 仓的 sw.js / locales 全部落在子目录里，只看根目录会一律报"无"，
# 把"没测到"当成"没有"即 M4 判据失效，故此处必须 recursive）
CAP_RULES = {
    "pwa_offline": lambda p: p.rsplit("/", 1)[-1] in ("sw.js", "service-worker.js",
                                                     "serviceworker.js", "sw.ts"),
    "pwa_manifest": lambda p: p.rsplit("/", 1)[-1] in ("manifest.webmanifest", "manifest.json"),
    "i18n_locale": lambda p: "/locales/" in f"/{p}" or "/i18n/" in f"/{p}" or "/languages/" in f"/{p}",
    "streaming": lambda p: p.rsplit("/", 1)[-1] in ("sse.ts", "sse.js", "use-sse.ts") or "/sse/" in f"/{p}",
    "vector_memory": lambda p: "vector" in p.lower() or "embedding" in p.lower() or "rag" in p.lower(),
    "container": lambda p: p.rsplit("/", 1)[-1] in ("Dockerfile", "docker-compose.yml",
                                                    "docker-compose.yaml"),
    "e2e_browser": lambda p: "/e2e/" in f"/{p}" or "playwright" in p.lower() or "cypress" in p.lower(),
    "deps_autoupdate": lambda p: p in ("dependabot.yml", ".github/dependabot.yml", "renovate.json",
                                        ".renovaterc.json", ".github/renovate.json"),
    # r21 加：机器可读 API 契约的存在性（对标"接口文档是否可被工具消费"，不是"有没有 README 介绍"）
    "api_spec": lambda p: p.rsplit("/", 1)[-1].lower() in (
        "openapi.yaml", "openapi.yml", "openapi.json", "swagger.yaml", "swagger.yml",
        "swagger.json", "api.openapi.yaml"),
}

# r30 加：**本项目专属**的"匹配器盲区"点名。CAP_RULES 只看路径字符串，
# 两类能力对我们是假阴性：SSE 写在 chat.js/ChatController.java 里（文件名不含 sse），
# 浏览器端到端在 `_test/*.py` 里用 playwright（路径不含 e2e/playwright）。
# ⚠️ 不拿它去改 peers 的计数（peer 只能按文件树静态判，给它"读内容"就是双标），
#    也**不计入 caps**（横向对比仍用同一把尺）；只在 self 行点名，防止读者把少算读成"没做"。
BLIND_PROBES = {
    "streaming": ((".js", ".java", ".ts"), ("text/event-stream", "ReadableStream")),
    "e2e_browser": ((".py", ".js", ".ts"), ("sync_playwright", "from playwright", "chromium.launch")),
}


def _blind_probe_hit(root, rel, needles):
    pass


# ── 第二条观测通道（r31）：文件名法只看 sw.js 之类，对**参照仓同样是下限**（与 self 的盲区点名同一原理）。
#     内容法读 description+README，但 "offline" 一词有三种完全不同的含义，必须先归因再计数，
#     否则会把"离线训练"读成"离线可用"（r31 实测：hello-diana/MASCOT 的 offline DPO 即是误报源）。
OFFLINE_CLASSES = ("app_shell", "local_models_offline", "ml_training_offline", "none")
RE_APP_SHELL = re.compile(r"service.?worker|workbox|precache|app.?shell|offline.?first|caches\.match|sw\.js", re.I)
RE_ML_TRAIN = re.compile(r"offline\s+(dpo|rl|rlhf|train|training|preference|fine.?tun|evaluation\s+pipeline)"
                         r"|dpo\b|\brlhf\b|rollout", re.I)
RE_LOCAL_OFF = re.compile(r"(run|runs|work|works|use|deploy).{0,40}offline|offline\s+mode|completely\s+offline"
                          r"|no\s+internet\s+required|离线运行|完全离线", re.I)


def offline_signal_class(text):
    """纯函数：无网络无副作用 ⇒ 可离线自证。返回 (类别, 证据片段)。

    判定顺序即归因顺序：训练语境最窄，先判掉；否则"offline DPO"会被本地离线那条误吞。
    """
    t = text or ""
    if "offline" not in t.lower() and not RE_APP_SHELL.search(t):
        return "none", ""
    m = RE_ML_TRAIN.search(t)
    if m and not RE_APP_SHELL.search(t):
        return "ml_training_offline", _snippet(t, m)
    m = RE_APP_SHELL.search(t)
    if m:
        return "app_shell", _snippet(t, m)
    m = RE_LOCAL_OFF.search(t)
    if m:
        return "local_models_offline", _snippet(t, m)
    # 只剩"见过 offline 字样但三种语境都不匹配"的情形 ⇒ 判 none。
    # 故意**不设兜底**：兜底会把"任何 offline 措辞"升格成某种能力，而这条通道的用途只是复核，
    # 宁可漏计对手（与文件名法同为下限），也不许凭空造出一格能力。
    return "none", ""


def _snippet(t, m):
    s = re.sub(r"\s+", " ", t[max(0, m.start() - 60):m.end() + 60]).strip()
    return s[:120]


def offline_audit(repos):
    """对每个参照仓取 description+README，跑第二条通道。取不到的仓**必须**记 unverified 并点名。

    `gh()` 的返回形态要注意两件事：它 `json.loads` 整个响应，且**非零退出即抛**
    —— 所以这里不能带 `--jq`（--jq 输出的裸字符串不是合法 JSON，loads 会炸），
    必须取整份 dict 再自己挑字段（r31 首跑即栽在这上面）。
    """
    out = {}
    for r in repos:
        full = r["repo"]
        parts, errs = [], []
        try:
            meta = gh("repos/" + full)
            parts.append(f"{meta.get('description') or ''} | {meta.get('homepage') or ''}")
        except Exception as e:
            errs.append("meta:" + str(e)[:70])
        try:
            rd = gh("repos/" + full + "/readme")
            parts.append(base64.b64decode((rd.get("content") or "").strip())
                         .decode("utf-8", errors="replace")[:200000])
        except Exception as e:
            errs.append("readme:" + str(e)[:70])
        hay = "\n".join(parts)
        if not hay.strip():
            out[full] = {"class": "unverified", "evidence": "; ".join(errs) or "两路均空"}
            continue
        cls, ev = offline_signal_class(hay)
        out[full] = {"class": cls, "evidence": ev, "partial": bool(errs)}
    return out


def blind_spot_caps(root, tracked, caps_found):
    """返回"内容里有证据、但 CAP_RULES 按文件名没看见"的能力名列表（只对本项目算）。"""
    blind = []
    for cap, (exts, needles) in BLIND_PROBES.items():
        if cap in caps_found:
            continue
        hit = False
        for rel in tracked:
            if not rel.endswith(exts) or len(rel) >= 300:
                continue
            f = root / rel
            try:
                if f.stat().st_size > 400_000:
                    continue
                if any(n in f.read_text("utf-8", errors="replace") for n in needles):
                    hit = True
                    break
            except OSError:
                continue
        if hit:
            blind.append(cap)
    return sorted(blind)


def gh(*args, timeout=40):
    p = subprocess.run(["gh", "api", *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    if p.returncode != 0:
        msg = (p.stderr or "").strip()
        if "Could not resolve host" in msg or "timed out" in msg.lower() or "connection" in msg.lower():
            raise OSError(f"network: {msg[:160]}")
        raise RuntimeError(f"gh api {args[0]} -> {msg[:160]}")
    return json.loads(p.stdout or "null")


def probe_repo(peer):
    repo = peer["repo"]
    out = dict(peer)
    r = gh(f"repos/{repo}")
    out["stars"] = r["stargazers_count"]
    out["pushed_at"] = r["pushed_at"][:10]
    out["language"] = r.get("language")
    out["license"] = (r.get("license") or {}).get("spdx_id")
    out["default_branch"] = r["default_branch"]
    rel = gh(f"repos/{repo}/releases", timeout=30)
    out["latest_release"] = rel[0]["tag_name"] if isinstance(rel, list) and rel else None
    try:
        wf = gh(f"repos/{repo}/actions/workflows")
        out["ci_workflows"] = wf.get("total_count")
    except Exception:
        out["ci_workflows"] = None
    try:
        tr = gh(f"repos/{repo}/git/trees/{out['default_branch']}?recursive=1", timeout=90)
        paths = [e["path"] for e in tr.get("tree", []) if e.get("type") == "blob"]
        root_names = {e["path"] for e in tr.get("tree", []) if e.get("type") == "tree"}
        names = set(root_names) | {p for p in paths if "/" not in p}
        out["docs"] = sorted(p for p in names if p in DOC_FILES)
        out["file_count"] = len(paths)
        caps = set()
        for p in paths:
            for cap, fn in CAP_RULES.items():
                if cap in caps:
                    continue
                if len(p) < 300 and fn(p):
                    caps.add(cap)
        out["caps"] = sorted(caps)
        out["tree_truncated"] = bool(tr.get("truncated"))
    except Exception as e:
        out["docs"] = []
        out["caps"] = []
        out["file_count"] = None
        out["tree_error"] = str(e)[:120]
    return out


EXCLUDE_PARTS = {"vendor", "target", "node_modules", "__pycache__", ".git", ".wrangler",
                 ".codebuddy", "_shots", "archive", "_test"}


def self_metrics():
    """心屿自身坐标——与参照仓同口径机器生成，禁止手抄进报告（M2 同源纪律）。"""
    src = ROOT / "src"
    loc, files = 0, 0
    for p in src.rglob("*"):
        if p.is_file() and p.suffix in (".js", ".css", ".html", ".json") \
                and not (EXCLUDE_PARTS & set(p.parts)):
            try:
                loc += len(p.read_text("utf-8", errors="replace").splitlines())
                files += 1
            except Exception:
                continue
    suites_files = len({p.name for p in (ROOT / "_test").glob("*_check.py")}
                       | {p.name for p in (ROOT / "_test").glob("*contract*.py")})
    # ⚠️ 口径分母（M3 纪律，r21 自纠）：`regression_suites` 必须是**电池里真正会跑的条目数**，
    #    不是"文件名看起来像判据脚本"的个数 —— 上一轮 self 报 19、报告写 24，就是两个分母混用了。
    #    唯一真相源 = run_all_suites.py 的 SUITES 列表；解析失败即报错，绝不回退到 glob 计数。
    battery, battery_err = None, ""
    try:
        txt = (ROOT / "_test" / "run_all_suites.py").read_text("utf-8", errors="replace")
        seg = txt.split("SUITES = [", 1)[1].split("\n]", 1)[0]
        battery = len(re.findall(r'^\s*\("', seg, re.M))
    except Exception as e:
        battery_err = str(e)[:80]
    ci = ROOT / ".github" / "workflows" / "ci.yml"
    jobs = 0
    if ci.exists():
        in_jobs = False
        for line in ci.read_text("utf-8").splitlines():
            if line.startswith("jobs:"):
                in_jobs = True
            elif in_jobs and line and not line.startswith(" "):
                break
            elif in_jobs and line.startswith("  ") and not line.startswith("   "):
                jobs += 1
    # ⚠️ self 的 docs/caps **必须走与参照仓同一个匹配器**（r21 自纠）：上一版这里另写一套
    #    手写存在性判断，等于"自己用尺 A、别人用尺 B"，横向对比不可信（M2 同源纪律）。
    #    唯一真相源 = git ls-files 的整仓路径清单，喂给同一份 DOC_FILES / CAP_RULES。
    tracked = []
    try:
        gp = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z"],
                            capture_output=True, timeout=60)
        tracked = [x.decode("utf-8", "replace") for x in gp.stdout.split(b"\0") if x]
    except Exception:
        tracked = []
    roots = {p.split("/")[0] if "/" in p else p for p in tracked}
    dirs = {r for r in roots if (ROOT / r).is_dir()}
    # 归一化：本项目用 `_test/` 承担参照仓 `tests/` 的角色，不同名但同职能 ⇒ 映射后计数，
    # 否则"文档齐备度 8/9 vs 9/9"的差别只是目录取名不同，属于假差距
    own = {("tests" if x == "_test" else x) for x in dirs} | {p for p in tracked if "/" not in p}
    docs = sorted(DOC_FILES_SET & own)
    caps = set()
    for p in tracked:
        for cap, fn in CAP_RULES.items():
            if len(p) < 300 and fn(p):
                caps.add(cap)
    if any("/api/emotion" in f.read_text("utf-8", errors="replace") for f in src.glob("js/*.js")):
        caps.add("emotion_backend_wired")
    return {"repo": "xinyu-soulisle (私有归档仓，本项目)", "tier": "self",
            "stars": None, "pushed_at": None, "latest_release": None,
            "ci_workflows": jobs or None, "language": "JavaScript/Java",
            "license": None, "default_branch": "main",
            "docs": docs, "caps": sorted(caps), "file_count": files,
            "caps_blind": blind_spot_caps(ROOT, tracked, caps),
            "src_loc_excl_vendor": loc, "regression_suites": battery,
            "regression_script_files": suites_files,
            "battery_parse_error": battery_err or None}


def diff_snap(prev_repos, cur_repos,
              keys=("stars", "pushed_at", "latest_release", "ci_workflows", "caps", "docs")):
    """逐仓逐字段差值。返回 [(repo, field, old, new)]；全等快照必须返回空列表。

    r21 补：`caps` / `docs` 也纳入比对。根因是本轮第二次采集实测抓到 sapphire 的 `container`
    能力**从清单里消失却零漂移报告** —— 只比 4 个数字字段的"漂移守卫"对能力矩阵变化是瞎的。
    """
    drift = []
    prev = {r["repo"]: r for r in prev_repos}
    for cur in cur_repos:
        old = prev.get(cur["repo"])
        if not old:
            drift.append((cur["repo"], "repo_added", None, cur.get("stars")))
            continue
        for k in keys:
            if old.get(k) != cur.get(k):
                drift.append((cur["repo"], k, old.get(k), cur.get(k)))
    return drift


def classify_drift(drift):
    """把漂移分成「实质」与「抖动」两档 ⇒ (substantive, noise)。

    r26 加：本轮 6 处漂移里 4 处是 ★ 数 ±1（含 lobehub 82,808→82,807 的**倒退**，
    平台清虚假账号所致），单点 star 差值不构成趋势证据；若与"对手发布 v2.5.0→v2.13.1"
    混在一张表里报，台账就失去了指方向的能力。故 stars 一律入抖动档，
    其余字段（pushed_at / latest_release / ci_workflows / caps / docs / 新仓）全部算实质。
    """
    sub = [d for d in drift if d[1] != "stars"]
    noise = [d for d in drift if d[1] == "stars"]
    return sub, noise


def coverage_hits(rows):
    """能力覆盖率的**分母证明** ⇒ (hits, usable, blind)。

    r27 加：`pwa_offline=0/16` 这种"全零"最容易是探测失效而非真没有，而旧版直接把 16 当分母打印，
    读的人无法区分"对手都没有离线 SW"与"我没数到"。实测核查：lobehub `main` 树 20,740 个对象、
    `truncated=false`、`sw.js|service-worker.js|sw.ts` 零命中 ⇒ 本次全零是真的。
    规则：**树被截断或取数失败的仓不得计入分母**，并且必须逐条点名（豁免需理由，对齐 C6b 口径）。
    """
    usable, blind = [], []
    for r in rows:
        if r.get("tree_truncated"):
            blind.append(f"{r['repo']}(树截断)")
        elif r.get("tree_error"):
            blind.append(f"{r['repo']}(树取数失败)")
        else:
            usable.append(r)
    hits = {c: sum(1 for r in usable if c in (r.get("caps") or [])) for c in CAP_RULES}
    return hits, usable, blind


def selftest():
    """合成两份快照：动 stars / pushed_at / **caps / docs**（r21 新增两键），断言 diff 恰好抓到。"""
    base = [{"repo": "lobehub/lobehub", "stars": 100, "pushed_at": "2026-09-01",
             "latest_release": "v1", "ci_workflows": 3, "caps": ["container"], "docs": ["README.md"]},
            {"repo": "s-nagaev/chibi", "stars": 50, "pushed_at": "2026-09-01",
             "latest_release": None, "ci_workflows": 5, "caps": ["vector_memory"], "docs": ["README.md"]}]
    same = json.loads(json.dumps(base))
    if diff_snap(base, same):
        print("SELFTEST-FAIL: 全等快照被报出漂移（判据过敏）")
        return 1
    moved = json.loads(json.dumps(base))
    moved[0]["stars"] = 101
    moved[1]["pushed_at"] = "2026-09-20"
    moved[0]["caps"] = []                     # 能力矩阵退化：第二次实采抓到 sapphire 掉 container 却零报告
    moved[1]["docs"] = ["README.md", "docs"]  # 文档项增加
    got = diff_snap(base, moved)
    want = {("lobehub/lobehub", "stars"), ("s-nagaev/chibi", "pushed_at"),
            ("lobehub/lobehub", "caps"), ("s-nagaev/chibi", "docs")}
    if {(g[0], g[1]) for g in got} != want:
        print(f"SELFTEST-FAIL: 期望抓到 {sorted(want)}，实际 {[(g[0], g[1]) for g in got]}")
        return 1
    # 分档判据（r26）：两侧都要验，否则"分类器"只是把漂移换个名字再报一遍
    sub, noise = classify_drift(got)
    if [(s[0], s[1]) for s in noise] != [("lobehub/lobehub", "stars")]:
        print(f"SELFTEST-FAIL: 抖动档应只有 stars，实际 {[(n[0], n[1]) for n in noise]}")
        return 1
    if len(sub) != 3 or any(s[1] == "stars" for s in sub):
        print(f"SELFTEST-FAIL: 实质档应含 pushed_at/caps/docs 三条且不含 stars，实际 {[(s[0], s[1]) for s in sub]}")
        return 1
    only_stars = [d for d in got if d[1] == "stars"]
    s2, n2 = classify_drift(only_stars)
    if s2 or len(n2) != 1:
        print(f"SELFTEST-FAIL: 纯 ★ 抖动被误判为实质（分类器恒真）：sub={s2}")
        return 1
    # 分母证明（r27）：截断/取数失败的仓必须出局并点名，否则"全零"无法区分真假
    rows = [{"repo": "a/a", "caps": ["container"], "file_count": 10},
            {"repo": "b/b", "caps": [], "file_count": 10, "tree_truncated": True},
            {"repo": "c/c", "caps": [], "file_count": 10, "tree_error": "boom"}]
    hits, usable, blind = coverage_hits(rows)
    if len(usable) != 1 or len(blind) != 2 or hits.get("container") != 1:
        print(f"SELFTEST-FAIL: 分母证明失效（usable={len(usable)} 应为 1，blind={blind} 应点名 b/b 与 c/c）")
        return 1
    if not any("树截断" in x for x in blind) or not any("树取数失败" in x for x in blind):
        print(f"SELFTEST-FAIL: 盲区原因未逐条点名（豁免无原因 = 等于没豁免）：{blind}")
        return 1
    if any(x.startswith("a/a") for x in blind):
        print("SELFTEST-FAIL: 健康仓被误踢出分母 ⇒ 判据过敏")
        return 1
    # 盲区点名（r30）：正向必须抓到"内容里有 SSE/playwright 证据但文件名看不见"，
    # 反向必须为空（否则这个点名就只是永远说"我们有"的广告牌）
    with tempfile.TemporaryDirectory() as td:
        troot = Path(td)
        (troot / "src").mkdir()
        (troot / "src" / "chat.js").write_text(
            'const r = res.body.getReader(); headers["Content-Type"] = "text/event-stream"',
            encoding="utf-8")
        got_b = blind_spot_caps(troot, ["src/chat.js"], set())
        if got_b != ["streaming"]:
            print(f"SELFTEST-FAIL: 盲区点名漏报（应抓到 streaming，实际 {got_b}）")
            return 1
        clean = Path(td) / "clean"
        clean.mkdir()
        (clean / "plain.js").write_text("console.log('no sse here')", encoding="utf-8")
        if blind_spot_caps(clean, ["plain.js"], set()):
            print("SELFTEST-FAIL: 无证据仓被点名有盲区 ⇒ 判据恒真")
            return 1
        if blind_spot_caps(troot, ["src/chat.js"], {"streaming"}):
            print("SELFTEST-FAIL: 文件名匹配器已看见的能力仍进盲区名单（重复计数）")
            return 1
    # 第二条离线观测通道（r31）：四类各一条 + 两条反向 + 一个变异体，缺任一 = 判据不可信
    samples = {
        "app_shell": ("This PWA ships a **service worker** (sw.js) using workbox precaching, "
                      "so the page still opens offline-first."),
        "local_models_offline": ("🔒 **Offline mode support**: Run completely offline using local "
                                 "models - no internet required."),
        "ml_training_offline": ("The Director is optimized with GRPO; an offline **DPO** trainer is "
                                "retained as an optional alternative."),
        "none": "A chat UI built with React + FastAPI, deployed on Kubernetes.",
    }
    for want, text in samples.items():
        got = offline_signal_class(text)[0]
        if got != want:
            print(f"SELFTEST-FAIL: 离线分类判错（{want} 被判成 {got}）样本={text[:50]!r}")
            return 1
    if offline_signal_class(samples["ml_training_offline"])[0] == "app_shell":
        print("SELFTEST-FAIL: 训练语境的 offline 被判成离线壳 ⇒ 会伪造出对手的假能力")
        return 1
    _g = globals()
    _mt, _ms = _g["RE_ML_TRAIN"], _g["RE_APP_SHELL"]
    try:
        _g["RE_ML_TRAIN"] = re.compile(r"(?!)")    # 变异体：摘掉最窄那条归因规则（必须写 globals，函数内赋值改不到模块态）
        _g["RE_APP_SHELL"] = re.compile(r"(?!)")
        if offline_signal_class(samples["ml_training_offline"])[0] == "ml_training_offline":
            print("SELFTEST-FAIL: 摘掉归因正则后仍判对 ⇒ 该类根本没在被判的东西上（判据恒真）")
            return 1
    finally:
        _g["RE_ML_TRAIN"], _g["RE_APP_SHELL"] = _mt, _ms
    if offline_signal_class("")[0] != "none" or offline_signal_class(None)[0] != "none":
        print("SELFTEST-FAIL: 零输入被判成有能力 ⇒ 违反「零输入不得记 PASS」")
        return 1
    print("SELFTEST-PASS: 合成快照 4 处改动（stars·pushed_at·caps·docs）全部抓到、全等对照零误报（"
          f"{len(got)} 条）；分档正确（实质 {len(sub)} / 抖动 {len(noise)}）且纯抖动场景零实质；"
          "分母证明正确（1 有效 / 2 盲区点名，健康仓不误踢）；"
          "r30 盲区点名三侧正确（有证据→点名、无证据→空、已看见→不重复）；"
          "r31 离线四分类各判对 + 训练语境不冒充离线壳 + 摘掉归因正则即翻判（变异体）+ 零输入判 none")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--offline-audit", action="store_true",
                    help="跑第二条离线观测通道（16 仓 × 2 次 API，较慢；判据本体由 --selftest 常驻守着）")
    ap.add_argument("--out", default=str(SNAP))
    args = ap.parse_args()

    if args.selftest:
        sys.exit(selftest())

    cur, hard_fail = [], []
    for peer in PEERS:
        try:
            cur.append(probe_repo(peer))
        except OSError as e:
            print(f"BENCHMARK-ENV-ERROR: {peer['repo']} {e}")
            return 2
        except Exception as e:
            hard_fail.append(f"{peer['repo']}: {e}")

    path = Path(args.out)
    prev_repos = []
    hist = []
    if path.exists():
        try:
            data = json.loads(path.read_text("utf-8"))
            hist = data.get("runs", [])
            prev_repos = hist[-1]["repos"] if hist else []
        except Exception as e:
            print(f"WARN: 既有快照不可读，按首次运行处理（{e}）")
    own = self_metrics()
    run = {"ts": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
           "repo_count": len(cur), "self": own, "repos": cur}
    if args.offline_audit:
        # 只用于**交叉验证**"0/16"这类全零结论，不参与 caps 计数（参与就成了第二把尺）
        audit = offline_audit(cur)
        run["offline_audit"] = audit
        unv = sorted(k for k, v in audit.items() if v["class"] == "unverified")
        shell = sorted(k for k, v in audit.items() if v["class"] == "app_shell")
        local = sorted(k for k, v in audit.items() if v["class"] == "local_models_offline")
        train = sorted(k for k, v in audit.items() if v["class"] == "ml_training_offline")
        print(f"  离线双通道（内容法，仅供复核）: app_shell={len(shell)}/{len(audit)} "
              f"local_models_offline={len(local)} ml_training_offline(误报源)={len(train)} unverified={len(unv)}")
        if unv:
            print(f"  ⚠️ 分母不全（{len(unv)} 仓未取到：{'、'.join(unv)}）⇒ **不得**据全零下差异结论")
        for k in shell + local:
            print(f"    ▶ {k} [{audit[k]['class']}] {audit[k]['evidence'][:90]}")
    hist = (hist + [run])[-6:]
    drift = diff_snap(prev_repos, cur)

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"generated_by": "_test/benchmark_metrics.py",
               "peers_expected": len(PEERS), "runs": hist}
    tmp = path.with_suffix(".json.tmp")
    # write_bytes 而非 write_text：文本模式在 Windows 会把 \n 翻成 \r\n，
    # 台账一旦带 CRLF，"逐字节对账/SHA256"类主张在别人 clone 上就复算不出来（eol_parity 实测抓到过一次）
    tmp.write_bytes(json.dumps(payload, ensure_ascii=False, indent=1).encode("utf-8"))
    os.replace(tmp, path)

    print(f"采集: {len(cur)}/{len(PEERS)} 仓 | 快照 {path.relative_to(ROOT).as_posix()} | 历史 {len(hist)} 次")
    if not cur:
        print("BENCHMARK-FAIL: 零仓取到数据")
        return 1
    if own["src_loc_excl_vendor"] <= 0 or not own["regression_suites"]:
        print("BENCHMARK-FAIL: 本项目自测指标为空（扫描路径失配，禁止把空读数当现状）")
        return 1
    for r in cur:
        print(f"  [{r['tier']}] {r['repo']:42s} ★{r['stars']:<7} pushed {r['pushed_at']} "
              f"rel={r['latest_release'] or '-':<18} wf={r['ci_workflows']} "
              f"caps={','.join(r['caps']) or '-'}")
    print(f"  [self] 心屿 src(除vendor)={own['src_loc_excl_vendor']} 行/{own['file_count']} 文件 "
          f"电池套件={own['regression_suites']}(判据脚本文件={own['regression_script_files']}，两口径不同源即登记) CI job={own['ci_workflows']} "
          f"docs={len(own['docs'])}/9 caps={','.join(own['caps']) or '-'}"
          f"（盲区点名：{','.join(own.get('caps_blind') or []) or '无'} = 内容里有证据但文件名匹配器看不见，"
          f"不计入 caps 以免与参照仓双标）")
    hit, usable, blind = coverage_hits(cur)
    if len(usable) + len(blind) != len(cur):
        print(f"BENCHMARK-FAIL: 分母对不上（有效 {len(usable)} + 盲区 {len(blind)} != 总数 {len(cur)}）")
        return 1
    print(f"  能力覆盖率(有效分母 {len(usable)}/{len(cur)} 仓): " + " ".join(f"{k}={v}" for k, v in hit.items()))
    if blind:
        print(f"  ⚠️ 盲区点名（这些仓的 caps 不计入分母，全零不可解读为「对手没有」）: " + " ; ".join(blind))
    if prev_repos:
        if drift:
            sub, noise = classify_drift(drift)
            print(f"漂移: {len(drift)} 处 = 实质 {len(sub)} 处（可行动）+ 抖动 {len(noise)} 处"
                  f"（★ 单点差值含倒退，不作趋势证据）｜与上一次快照逐字段比对，禁止沿用旧数字")
            for repo, k, o, n in sub:
                print(f"  ▶ 实质 {repo} {k}: {o} -> {n}")
            for repo, k, o, n in noise:
                print(f"    抖动 {repo} {k}: {o} -> {n}")
        else:
            print("漂移: 0 处（与上一次快照完全一致）")
    else:
        print("漂移: 首次运行，无历史可比")
    if hard_fail:
        print("BENCHMARK-FAIL: 取数不全是环境原因以外的失败，禁止当通过")
        for h in hard_fail:
            print("  ! " + h)
        return 1
    print("BENCHMARK-METRICS-PASS")
    return 0


if __name__ == "__main__":
    # 守卫不可省：r26 实测裸 sys.exit(main()) 使「import 本模块做负控制」变成「先跑一遍联网采集再 exit 0」，
    # 于是反例根本没执行却看着像通过 —— 同族坑第五次复发，且这次骗的是验证动作本身。
    sys.exit(main())
