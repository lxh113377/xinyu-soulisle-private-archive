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
# r70 修（同族：判据只能断言事实，不能断言事实的名字）：`"rag" in path` 是**裸子串**，
# 会被 `storage` / `coverage` / `average` / `barrier` 这类词白送一分。一手现场是本项目自己：
# self 的 `vector_memory=YES` 全部由 `_test/storage_resilience_check.py` 与
# `_test/plan_pdf_coverage_check.py` 两个文件名撑起来（`git ls-files` 里零个真 vector/embedding/独立 rag），
# 也就是总览表里被抄了十几轮的那格「同类标配＝向量记忆，我们也有」是**尺子造出来的**。
# 同一条规则也跑在 16 个参照仓的整树路径上 ⇒ 对手侧的 `vector_memory=9/16` 同样被抬高。
# 修法：`rag` 必须是**独立词元**（前后非字母数字）；`vector`/`embedding` 保持子串（无此类误伤词）。
RAG_TOKEN_RE = re.compile(r"(^|[^A-Za-z0-9])rag([^A-Za-z0-9]|$)")

# 能力探测：按**整树递归**的文件名/后缀匹配（根目录一层探测无判别力——
# 实测 14 仓的 sw.js / locales 全部落在子目录里，只看根目录会一律报"无"，
# 把"没测到"当成"没有"即 M4 判据失效，故此处必须 recursive）
CAP_RULES = {
    "pwa_offline": lambda p: p.rsplit("/", 1)[-1] in ("sw.js", "service-worker.js",
                                                     "serviceworker.js", "sw.ts"),
    "pwa_manifest": lambda p: p.rsplit("/", 1)[-1] in ("manifest.webmanifest", "manifest.json"),
    "i18n_locale": lambda p: "/locales/" in f"/{p}" or "/i18n/" in f"/{p}" or "/languages/" in f"/{p}",
    "streaming": lambda p: p.rsplit("/", 1)[-1] in ("sse.ts", "sse.js", "use-sse.ts") or "/sse/" in f"/{p}",
    "vector_memory": lambda p: ("vector" in p.lower() or "embedding" in p.lower()
                                or RAG_TOKEN_RE.search(p.lower()) is not None),
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

# r73 第二通道（流式 / 端到端）的四条归因正则。分开的理由与上面三条同源：
# "streaming" 一词至少有三种互不相干的含义（逐字输出 / 视音频直播 / Kafka 那类数据流），
# "playwright" 既可能是"有 e2e 测试"也可能是"用浏览器抓取当产品功能"——合并成一条正则就会互相冒充。
RE_SSE = re.compile(r"\b(sse|server[-\s]?sent events?|text/event-stream|streaming\s+(response|output|token)"
                    r"|token[-\s]?by[-\s]?token|stream\s+the\s+response|逐字|流式输出|流式响应)", re.I)
RE_MEDIA = re.compile(r"(live\s?stream|streaming\s+(video|audio|media|tts|voice)|video\s+streaming"
                      r"|\bhls\b|dynamic\s+adaptive\s+streaming|webrtc|直播|音视频流)", re.I)
RE_DATAINFRA = re.compile(r"(kafka|flink|spark streaming|data[-\s]?stream(ing)?|stream(ing)?\s+pipeline"
                          r"|event[-\s]?stream(ing)?\s+(platform|pipeline)|ETL)", re.I)
RE_E2E = re.compile(r"(\be2e\b|end[-\s]?to[-\s]?end\s+(test|suite|coverage)|visual\s+regression|浏览器回归"
                    r"|(playwright|cypress|selenium)[^\n]{0,60}?\b(test|tests|spec|runner|suite)\b"
                    r"|\b(test|tests|testing|ci)\b[^\n]{0,40}?\b(playwright|cypress|selenium)\b)", re.I)
RE_BROWSER_TOOL = re.compile(r"(scrap(e|er|ing)|web automation|browser automation|puppeteer"
                             r"|headless browser|爬虫|网页抓取)", re.I)


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


def cap_channel_class(text):
    """第二观测通道（r73）：从 description+README **正文**判两格能力，与文件名法并行但不改 caps。

    为什么要有它：`streaming` / `e2e_browser` 这两格在 self 侧长期是**盲区**
    （SSE 写在 `chat.js`/`ChatController.java` 里、端到端在 `_test/*.py` 用 playwright，
    文件名匹配器都看不见 ⇒ 只能靠 `caps_blind` 点名）。而 peers 侧这两格**一直只由文件名规则单独得出**，
    于是"对手 streaming=2/16"其实是**下限**却被读成现状。本通道用与 r31 离线通道同一套纪律补上这条不对称：
    只做复核与下限揭示，**不参与 caps 计数**（参与了就是"自己用尺 A、别人用尺 B"的反向版本）。
    归因顺序＝先窄后宽，且**不设兜底**：宁可漏计对手，也不凭一句"提到 streaming"造出一格能力。
    """
    t = text or ""
    low = t.lower()
    if not low.strip():
        return {"streaming": "none", "e2e_browser": "none", "evidence": {}, "fetched": False}
    ev = {}
    m = RE_SSE.search(t)
    if m:
        cls = "token_stream"
        ev["streaming"] = _snippet(t, m)
    elif RE_MEDIA.search(t):
        cls = "media_stream"
        ev["streaming"] = _snippet(t, RE_MEDIA.search(t))
    elif RE_DATAINFRA.search(t):
        cls = "data_infra"
        ev["streaming"] = _snippet(t, RE_DATAINFRA.search(t))
    else:
        cls = "none"
    m = RE_E2E.search(t)
    if m:
        cls2 = "test_e2e"
        ev["e2e_browser"] = _snippet(t, m)
    elif RE_BROWSER_TOOL.search(t):
        cls2 = "browser_tool_feature"
        ev["e2e_browser"] = _snippet(t, RE_BROWSER_TOOL.search(t))
    else:
        cls2 = "none"
    return {"streaming": cls, "e2e_browser": cls2, "evidence": ev, "fetched": True}


def cap_channel_audit(repos):
    """对每个参照仓取 description+homepage+README，跑第二通道；取不到必须记 unverified 并点名。"""
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
            out[full] = {"streaming": "unverified", "e2e_browser": "unverified",
                         "evidence": {}, "unverified": "; ".join(errs) or "两路均空"}
            continue
        c = cap_channel_class(hay)
        c["partial"] = bool(errs)
        if errs:
            c["partial_errors"] = "; ".join(errs)
        out[full] = c
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


def git_ls_tree(rev="HEAD"):
    """rev 的文件清单（git 面）。失败即抛——**禁止静默退回工作树面**（那等于把两台机器的读数混进同一格）。"""
    r = subprocess.run(["git", "-C", str(ROOT), "ls-tree", "-r", "--name-only", rev],
                       capture_output=True, timeout=60)
    if r.returncode != 0:
        raise RuntimeError("ls-tree %s 失败：%s" % (rev, (r.stderr or b"").decode("utf-8", "replace")[:100]))
    return [x.decode("utf-8", "replace") for x in (r.stdout or b"").split(b"\n") if x]


def git_blob(path, rev="HEAD"):
    r = subprocess.run(["git", "-C", str(ROOT), "show", "%s:%s" % (rev, path)],
                       capture_output=True, timeout=60)
    if r.returncode != 0:
        raise RuntimeError("show %s:%s 失败" % (rev, path))
    return (r.stdout or b"").decode("utf-8", "replace")


def summarize_self_paths(paths):
    """纯函数：git 面的路径清单 → (src 文件数, 判据脚本文件名集)。

    拆成纯函数是为了让 selftest 能用**合成人口**驱动它（含一件未跟踪的形状），
    而不是去动真实工作树——判据要能证明"未入库的件不计数"，又不能靠往仓里塞临时件来证明。
    """
    exts = (".js", ".css", ".html", ".json")
    src_files = [p for p in paths
                 if p.startswith("src/") and p.rsplit("/", 1)[-1].endswith(exts)
                 and not (EXCLUDE_PARTS & set(p.split("/")))]
    scripts = {p.rsplit("/", 1)[-1] for p in paths
               if p.startswith("_test/") and (p.endswith("_check.py") or "contract" in p.rsplit("/", 1)[-1])}
    return len(src_files), src_files, scripts


def self_metrics():
    """心屿自身坐标——与参照仓同口径机器生成，禁止手抄进报告（M2 同源纪律）。

    ⚠️ r71 起**整行统一取 git 面（HEAD）**：上一版只有 SUITES 走 git，其余（src 行数/文件数、
    判据脚本数、CI job 数）仍 rglob 工作树，于是"并行会话未入库的在途件"会被写成横向现状——
    实测同一天两次采集记 `regression_suites=101` 而 HEAD 实数 99。混面比单一面更坏，
    因为它让台账在别的机器/CI 上必然复算不出，却在本机永远自洽。
    """
    src_loc, files, suites_files = 0, 0, 0
    self_face, self_err = "HEAD", ""
    try:
        paths = git_ls_tree("HEAD")
        n_src, src_paths, scripts = summarize_self_paths(paths)
        files = n_src
        for p in src_paths:
            src_loc += len(git_blob(p, "HEAD").splitlines())
        suites_files = len(scripts)
    except Exception as e:
        self_err = str(e)[:120]
        self_face = "取数失败"
    # 工作树与 HEAD 的差必须**看得见**：只印数字，不参与任何计数（否则又回到混面）。
    # 实测本仓合法的差有两种：① 并行会话在途未入库件；② 按红线 ignore 的本机密钥件
    # （`src/js/demo-config.js` 含 Key、故意不入库 ⇒ 它本就不该出现在与参照仓同口径的 src 统计里）。
    try:
        others = subprocess.run(["git", "-C", str(ROOT), "ls-files", "--others", "--exclude-standard",
                                 "-z", "--", "src", "_test"], capture_output=True, timeout=60)
        worktree_extra = len([x for x in (others.stdout or b"").split(b"\0") if x])
    except Exception:
        worktree_extra = -1
    EXT_ALL = (".js", ".css", ".html", ".json")
    wt_src = {str(q.relative_to(ROOT)).replace("\\", "/") for q in (ROOT / "src").rglob("*")
              if q.is_file() and q.suffix in EXT_ALL and not (EXCLUDE_PARTS & set(q.parts))}
    head_src = {x for x in locals().get("paths", []) or []
                if x.startswith("src/") and x.rsplit("/", 1)[-1].endswith(EXT_ALL)
                and not (EXCLUDE_PARTS & set(x.split("/")))}
    ignored_src = len(wt_src - head_src)
    ci_jobs, ci_err = 0, ""
    try:
        in_jobs = False
        for line in git_blob(".github/workflows/ci.yml", "HEAD").splitlines():
            if line.startswith("jobs:"):
                in_jobs = True
            elif in_jobs and line and not line.startswith(" "):
                break
            elif in_jobs and line.startswith("  ") and not line.startswith("   "):
                ci_jobs += 1
    except Exception as e:
        ci_err = str(e)[:80]
    # ⚠️ 口径分母（M3 纪律，r21 自纠）：`regression_suites` 必须是**电池里真正会跑的条目数**，
    #    不是"文件名看起来像判据脚本"的个数 —— 上一轮 self 报 19、报告写 24，就是两个分母混用了。
    #    唯一真相源 = run_all_suites.py 的 SUITES 列表；解析失败即报错，绝不回退到 glob 计数。
    battery, battery_err, battery_face = None, "", "HEAD"
    try:
        # r71 改面：取 `git show HEAD:_test/run_all_suites.py`，**不是工作树那一份**。
        # 一手现场：09-28 同日两次采集都记 regression_suites=101，而 HEAD 实数 99 ——
        # 多出的 2 条是并行会话**尚未入库**的在途套件。台账是跨轮/跨机复算的"横向现状"源，
        # 把工作树状态写成现状＝换台机器（或 CI 干净克隆）必然对不上。
        txt = subprocess.run(["git", "-C", str(ROOT), "show", "HEAD:_test/run_all_suites.py"],
                             capture_output=True, timeout=60).stdout.decode("utf-8", "replace")
        seg = txt.split("SUITES = [", 1)[1].split(chr(10) + "]", 1)[0]
        battery = len(re.findall(r'^\s*\("', seg, re.M))
        if battery == 0:
            battery_err = "HEAD 面解析到 0 条 ⇒ 不得当现状"
    except Exception as e:
        battery_err = str(e)[:80]
    ci = ROOT / ".github" / "workflows" / "ci.yml"
    # ⚠️ self 的 docs/caps **必须走与参照仓同一个匹配器**（r21 自纠）：上一版这里另写一套
    #    手写存在性判断，等于"自己用尺 A、别人用尺 B"，横向对比不可信（M2 同源纪律）。
    #    r71：人口也统一到 git 面（HEAD），不再用 `ls-files`（那是索引＝会被他人的 staged 改动带偏）。
    try:
        tracked = git_ls_tree("HEAD")
    except Exception as e:
        tracked = []
        self_err = (self_err + " ; tracked:" + str(e)[:80]).strip(" ;")
    roots = {p.split("/")[0] if "/" in p else p for p in tracked}
    dirs = {r for r in roots if any(p.startswith(r + "/") for p in tracked)}
    # 归一化：本项目用 `_test/` 承担参照仓 `tests/` 的角色，不同名但同职能 ⇒ 映射后计数，
    # 否则"文档齐备度 8/9 vs 9/9"的差别只是目录取名不同，属于假差距
    own = {("tests" if x == "_test" else x) for x in dirs} | {p for p in tracked if "/" not in p}
    docs = sorted(DOC_FILES_SET & own)
    caps = set()
    for p in tracked:
        for cap, fn in CAP_RULES.items():
            if len(p) < 300 and fn(p):
                caps.add(cap)
    try:
        if any("/api/emotion" in git_blob(p, "HEAD")
               for p in tracked if p.startswith("src/js/") and p.endswith(".js")):
            caps.add("emotion_backend_wired")
    except Exception as e:
        self_err = (self_err + " ; emotion:" + str(e)[:80]).strip(" ;")
    return {"repo": "xinyu-soulisle (私有归档仓，本项目)", "tier": "self",
            "stars": None, "pushed_at": None, "latest_release": None,
            "ci_workflows": ci_jobs or None, "language": "JavaScript/Java",
            "license": None, "default_branch": "main",
            "docs": docs, "caps": sorted(caps), "file_count": files,
            "caps_blind": blind_spot_caps(ROOT, tracked, caps),
            "src_loc_excl_vendor": src_loc, "regression_suites": battery,
            "regression_suites_face": battery_face,
            "regression_script_files": suites_files,
            "self_face": self_face, "self_face_errors": self_err or None,
            "worktree_extra_untracked": worktree_extra,
            "worktree_only_src_files": ignored_src,
            "ci_yml_error": ci_err or None,
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
    # r71：self 行的取数面必须是 git HEAD ⇒ 人口由 ls-tree 给出，未入库的件**结构上**不在人口里。
    # 反例的专属输入面：往合成人口里塞一件 `*_check.py` 形状的"在途件"，先证计数器真的会数它
    # （否则"它没被数"只是因为计数器恒零），再证从人口里去掉它 ⇒ 计数恰好少一。
    pop = ["src/js/app.js", "src/index.html", "_test/foo_check.py", "_test/j2_chat_contract.py", "README.md"]
    n_all, srcs_all, scripts_all = summarize_self_paths(pop)
    n_wo, srcs_wo, scripts_wo = summarize_self_paths([x for x in pop if x != "_test/foo_check.py"])
    if (n_all, len(scripts_all)) != (2, 2) or (n_wo, len(scripts_wo)) != (2, 1):
        print("SELFTEST-FAIL: r71 取数面控制失效（加一件应 +1、减一件应 -1，实测 "
              f"{(n_all, len(scripts_all))} / {(n_wo, len(scripts_wo))}）")
        return 1
    if summarize_self_paths([]) != (0, [], set()):
        print("SELFTEST-FAIL: 零人口却给出非零计数（违反「零输入不得记 PASS」）")
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
    # r73 第二观测通道：四类归因各有专属样本 + 两条方向相反的控制 + 一个变异体（缺任一＝通道不可信）
    chan_samples = {
        "token_stream": "Chat UI with **SSE** streaming responses, token-by-token rendering via text/event-stream.",
        "media_stream": "A live streaming room with WebRTC audio/video and HLS playback for watchers.",
        "data_infra": "Built on Kafka and Spark streaming: an event streaming pipeline for ETL workloads.",
        "test_e2e": "CI runs Playwright end-to-end tests (e2e suite) against the dockerized app.",
        "browser_tool_feature": "AI agent that does web scraping and page automation with a headless browser.",
    }
    for want_cls, sample in list(chan_samples.items()):
        # 变量名刻意避开 `got`：本函数后半段的漂移对照组就叫 got，
        # 首版我在这里写 `got = ...` 把它**遮蔽**了 ⇒ SELFTEST-PASS 那行的「全等对照零误报（N 条）」
        # 当场从 4 变成 20（20 = len("browser_tool_feature")）——数字动了但断言没动，正是"打印的数来自被遮蔽变量"那一族。
        chan_cls = cap_channel_class(sample)["e2e_browser" if want_cls in ("test_e2e", "browser_tool_feature")
                                           else "streaming"]
        if chan_cls != want_cls:
            print(f"SELFTEST-FAIL: 通道把 {want_cls} 的样本判成 {chan_cls}（归因串味）")
            return 1
    # 反向腿①：视音频直播不得冒充"逐字流式"；否则 streaming 那格会被 media-only 仓灌满
    if cap_channel_class(chan_samples["media_stream"])["streaming"] == "token_stream":
        print("SELFTEST-FAIL: media_stream 被升格成 token_stream ⇒ 通道会凭空造能力")
        return 1
    # 反向腿②：把浏览器当工具的仓库不得算"有 e2e 测试"
    if cap_channel_class(chan_samples["browser_tool_feature"])["e2e_browser"] == "test_e2e":
        print("SELFTEST-FAIL: browser_tool_feature 被升格成 test_e2e ⇒ 反向腿失效")
        return 1
    # 反向腿③④：这两条**照抄 r73 首跑真面抓到的两处冒充**（不是我编的形状，是实测文本）
    # ③ `dash.cloudflare.com` 里的 "dash" 曾被 `\bdash\b` 认成 DASH 流媒体 ⇒ 整仓被升格成 media_stream
    if cap_channel_class("**Cloudflare Workers AI**: [dash.cloudflare.com/profile/api-tokens]")["streaming"] != "none":
        print("SELFTEST-FAIL: dash.cloudflare.com 仍被当成流媒体能力 ⇒ 首跑抓到的那处冒充没修住")
        return 1
    # ④ README 里链接 `microsoft/playwright-mcp`（当作网页操作工具）曾被裸 `playwright` 认成"有 e2e 测试"
    if cap_channel_class("mcp网页操作工具： https://github.com/microsoft/playwright-mcp 记忆系统")["e2e_browser"] == "test_e2e":
        print("SELFTEST-FAIL: playwright-mcp 依赖仍被判成有 e2e 测试 ⇒ 工具名与测试语境仍互相冒充")
        return 1
    # 正向对照：真写测试的句子必须仍然算 test_e2e（防我为了消红把规则砍成恒假）
    if cap_channel_class("CI runs the Playwright test suite against the dockerized app.")["e2e_browser"] != "test_e2e":
        print("SELFTEST-FAIL: 合规正例不判 test_e2e ⇒ 收紧规则时把真能力一起砍掉了")
        return 1
    if cap_channel_class("")["streaming"] != "none" or cap_channel_class("React + FastAPI chat app.")["streaming"] != "none":
        print("SELFTEST-FAIL: 零输入/无证据文本被判成有流式能力（违反「零输入不得记 PASS」）")
        return 1
    _g73 = globals()
    _orig_sse = _g73["RE_SSE"]
    try:
        _g73["RE_SSE"] = re.compile(r"(?!)")   # 变异体：摘掉逐字流式那条归因，必须改变判定
        if cap_channel_class(chan_samples["token_stream"])["streaming"] == "token_stream":
            print("SELFTEST-FAIL: 摘掉 RE_SSE 后仍判 token_stream ⇒ 该类根本没在被判的东西上")
            return 1
    finally:
        _g73["RE_SSE"] = _orig_sse
    # 通道不得改写 caps：同一份文本走两遍，caps 相关的键必须完全不动（第二把尺防线）
    if cap_channel_class(chan_samples["token_stream"]).get("caps"):
        print("SELFTEST-FAIL: 通道返回值里出现 caps 键 ⇒ 它正在变成第二把尺")
        return 1
    # 能力匹配器本体（r70）：`rag` 裸子串会把 storage/coverage 白送成一格能力 ⇒ 两向都验
    _vm = CAP_RULES["vector_memory"]
    _must_red = ["src/storage/db.js", "test/coverage.py", "_test/plan_pdf_coverage_check.py",
                 "src/fragment/pool.py", "docs/average-note.md", "docs/drag-drop.md"]
    _must_green = ["src/rag/store.py", "src/vector-index.ts", "app/embeddings/client.py",
                   "src/RAG/retrieve.ts", "lib/rag-client.js"]
    # 前置条件自证：假阳清单必须**在旧裸子串规则下真的会命中**，否则这条控制只是在打一个不存在的靶子
    _old_rag = lambda p: "rag" in p.lower()
    _bogus = [p for p in _must_red if not _old_rag(p)]
    if _bogus:
        print("SELFTEST-FAIL: 假阳用例不成立（旧规则本就不会命中，白测）：" + " ; ".join(_bogus))
        return 1
    _bad = [p for p in _must_red if _vm(p)] + [p for p in _must_green if not _vm(p)]
    if _bad:
        print("SELFTEST-FAIL: vector_memory 匹配器失真（假阳/假阴）：" + " ; ".join(_bad[:6]))
        return 1
    if _vm("src/storage/db.js") is _vm("src/rag/store.py"):
        print("SELFTEST-FAIL: 两条相反用例同判 ⇒ 这条控制是恒真的摆设")
        return 1
    print("SELFTEST-PASS: 合成快照 4 处改动（stars·pushed_at·caps·docs）全部抓到、全等对照零误报（"
          f"{len(got)} 条）；分档正确（实质 {len(sub)} / 抖动 {len(noise)}）且纯抖动场景零实质；"
          "分母证明正确（1 有效 / 2 盲区点名，健康仓不误踢）；"
          "r30 盲区点名三侧正确（有证据→点名、无证据→空、已看见→不重复）；"
          "r31 离线四分类各判对 + 训练语境不冒充离线壳 + 摘掉归因正则即翻判（变异体）+ 零输入判 none；"
          f"r70 vector_memory 匹配器 {len(_must_red)} 条假阳全拒 + {len(_must_green)} 条真阳全收；"
          f"r71 self 行取数面 = git HEAD（未入库件结构性进不了人口，零人口不判绿）")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--offline-audit", action="store_true",
                    help="跑第二条离线观测通道（16 仓 × 2 次 API，较慢；判据本体由 --selftest 常驻守着）")
    ap.add_argument("--cap-channel", action="store_true",
                    help="跑流式/端到端的第二观测通道（r73；同样 16 仓 × 2 次 API，只作复核与下限揭示，不改 caps）")
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
    if args.cap_channel:
        chan = cap_channel_audit(cur)
        run["cap_channel"] = chan
        buckets = {}
        for cap in ("streaming", "e2e_browser"):
            for k, v in chan.items():
                buckets.setdefault((cap, v.get(cap)), []).append(k)
        unv = sorted(k for k, v in chan.items() if v.get("streaming") == "unverified")
        print("  第二通道（内容法，仅供复核，不改 caps）：")
        for cap, order in (("streaming", ("token_stream", "media_stream", "data_infra", "none")),
                           ("e2e_browser", ("test_e2e", "browser_tool_feature", "none"))):
            line = " ".join("%s=%d" % (c, len(buckets.get((cap, c), []))) for c in order)
            filename_n = sum(1 for r in cur if cap in (r.get("caps") or []))
            print(f"    {cap}: {line} unverified={len(unv)} ｜ 文件名法 caps={filename_n}/{len(cur)}"
                  f" ⇒ 内容法只用于判断「文件名法是不是下限」")
            for c in order[:2]:
                for k in sorted(buckets.get((cap, c), []))[:4]:
                    print(f"      ▶ [{c}] {k} :: {chan[k]['evidence'].get(cap, '')[:88]}")
        if unv:
            print(f"  ⚠️ 通道分母不全（{len(unv)} 仓两路皆空：{'、'.join(unv)}）⇒ 不得据"
                  f"「内容法也没见到」下否定结论")
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
