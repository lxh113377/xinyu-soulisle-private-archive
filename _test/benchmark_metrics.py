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

# ── r74：「文档完善程度」与「性能表现」两格的**同址尺**（peers 与 self 同一套规则、同一张脸）。
#     起因是本轮读 r73 报告 §1 时抓到的两件事：
#       · 「文档」行 self 侧印 `docs 9/9`（官方九项覆盖），peers 侧印 `api_spec 1/16`（另一格能力）
#         ⇒ 两个不同判据的数字被并排当对照，等于没有对照；
#       · 「性能」行 peers 侧写「peers 无 perf 字段 ⇒ 不可比」，但**这 16 仓里有没有人公开过测量装置
#         或测量数字**从来没被问过——"不可比"是先于取数下的结论。
#     所以这里补一组类，并让 self 侧走 git HEAD 面（r71 的取数面纪律），peers 侧走同一棵 tree+README，
#     两侧同法才有"差距"可言。与 r73 通道同源：**不参与 caps、不设兜底、取不到记 unverified**。
DOC_CLASSES = ("docs_site", "agent_facing_doc", "changelog_root", "readme_thorough")
PERF_CLASSES = ("bench_script", "ci_perf_step", "published_numbers")
# 树派生类：结论只能从**整棵文件清单**读出来。清单没取到就是「未验」，不得写成「该仓没有」。
# （r76 一手：chibi 的 tree 取数失败、README 取成功，旧写法把 docs_site/changelog_root 直接判 False，
#   于是 6 小时内同一条尺从 9/16 掉到 8/16、changelog_root 从 3/16 掉到 2/16，而漂移行不会点名这类翻转。）
TREE_DERIVED_CLASSES = ("docs_site", "agent_facing_doc", "changelog_root", "bench_script", "ci_perf_step")
RE_DOCS_SITE_DIR = re.compile(r"(^|/)(docs|doc|documentation|guides?|wiki|handbook)/", re.I)
RE_DOCS_SITE_CFG = re.compile(r"(^|/)(mkdocs\.ya?ml|docusaurus\.config\.(js|ts|mjs)|book\.toml"
                              r"|\.vitepress/|\.vuepress/|docs/conf\.py$)", re.I)
# 面向 AI agent 的说明文件——2026 年 peers 里新出现的可借鉴面，与"给人看的 docs"是两件事，必须分开计
RE_AGENT_DOC = re.compile(r"(^|/)(AGENTS\.md|CLAUDE\.md|GEMINI\.md|llms(-full)?\.txt|\.cursorrules"
                          r"|\.clinerules|\.cursor/rules/|\.github/copilot-instructions\.md|\.agents/)", re.I)
RE_CHANGELOG_ROOT = re.compile(r"^CHANGELOG(\.|_|$)", re.I)
RE_BENCH_PATH = re.compile(r"(^|/)(bench|benchmarks|benchmark|perf|performance|load_?tests?|stress|jmh|asv_bench)/"
                           r"|(^|/)(locustfile\.py|k6[\w.-]*\.js|[\w.-]+\.jmx|wrk[\w.-]*\.lua|vegeta\.ya?ml|hey\.sh)"
                           r"|(^|/)perf[\w.-]*\.(py|js|ts|go|rb|sh)$"
                           r"|^(tools|scripts|bin)/[\w.-]*bench[\w.-]*\.(py|js|ts|go|rb|sh)$", re.I)
# 反deny：名字里带 bench 但职责是**指标汇总器**而不是测量装置（r74 首跑真面抓到的两处：
# 本仓 `_test/benchmark_metrics.py` 与 leemo 的 `aggregate_benchmark.py`）——同名不同事，必须显式否掉，
# 否则这条尺会把自己的采集器记成"我们有性能装置"。规则对 peers 与 self 同样生效（同址）。
BENCH_DENY = re.compile(r"(bench|benchmark)[\w-]*(_?metrics?|_?collect|_?aggregat|_?report|_?summary)", re.I)
RE_CI_PERF = re.compile(r"^\.github/workflows/(?:[\w.-]*[-_])?(perf|bench|benchmark|load[-_]?test|stress)"
                        r"[\w.-]*\.ya?ml$", re.I)
# r74 首跑抓到 `deploy-workbench.yml` 被裸 `bench` 认成性能步 ⇒ 名字边界必须是分隔符或行首（workbench 不算）
RE_PERF_KW = re.compile(r"(benchmark|latency|throughput|\bp\d{2}\b|qps|req/s|\brps\b|tokens?/s|tok/s"
                        r"|\bttft\b|首字|吞吐|压测|实测|measured)", re.I)
RE_PERF_NUM = re.compile(r"\d+(\.\d+)?\s*(ms|µs|μs|req/s|tokens/s|tok/s|qps|rps|tps)\b|\d+(\.\d+)?\s*倍|P\d{2}=\d")
README_MIN_CHARS = 3000
README_MIN_SIGNALS = 3


def doc_perf_tree_class(paths):
    """纯函数：文件清单 → 结构类命中（docs_site/agent_facing_doc/changelog_root/bench_script/ci_perf_step）。

    零输入 ⇒ 五类全 False，**不得**因为"什么都没看见"就升格成任何结论（R247 同族）。
    """
    hits = {k: False for k in ("docs_site", "agent_facing_doc", "changelog_root",
                               "bench_script", "ci_perf_step")}
    ev = {}
    for p in paths or []:
        if len(p) >= 300:
            continue
        if not hits["docs_site"] and (RE_DOCS_SITE_DIR.search(p) or RE_DOCS_SITE_CFG.search(p)):
            hits["docs_site"] = True
            ev["docs_site"] = p
        if not hits["agent_facing_doc"] and RE_AGENT_DOC.search(p):
            hits["agent_facing_doc"] = True
            ev["agent_facing_doc"] = p
        if not hits["changelog_root"] and "/" not in p and RE_CHANGELOG_ROOT.search(p):
            hits["changelog_root"] = True
            ev["changelog_root"] = p
        if not hits["bench_script"] and RE_BENCH_PATH.search(p) and not BENCH_DENY.search(p.rsplit("/", 1)[-1]):
            hits["bench_script"] = True
            ev["bench_script"] = p
        if not hits["ci_perf_step"] and RE_CI_PERF.search(p):
            hits["ci_perf_step"] = True
            ev["ci_perf_step"] = p
    return hits, ev


def doc_perf_text_class(text):
    """纯函数：README 正文 → readme_thorough / published_numbers。

    `readme_thorough` 要 **长度 ∧ ≥3 个结构信号**（单看长度会把"长篇营销文"算成好文档）；
    `published_numbers` 要 **同一行里既有指标词又有数+单位**（单看"高性能/极致性能"不算数字）。
    """
    t = text or ""
    signals = [len(re.findall(r"(?m)^#{1,4}\s+\S", t)) >= 5,
               bool(re.search(r"!\[", t)),
               bool(re.search(r"\[!\[", t)),
               bool(re.search(r"(?im)^#{1,4}.*(quick\s?start|getting started|install|部署|安装|快速开始|使用方法|usage)", t))]
    thorough = len(t) >= README_MIN_CHARS and sum(signals) >= README_MIN_SIGNALS
    published = False
    for line in t.splitlines():
        if RE_PERF_KW.search(line) and RE_PERF_NUM.search(line):
            published = True
            evidence = line.strip()[:120]
            break
    ev = {}
    if thorough:
        ev["readme_thorough"] = "len=%d signals=%d/4" % (len(t), sum(signals))
    if published:
        ev["published_numbers"] = evidence
    return {"readme_thorough": thorough, "published_numbers": published}, ev


def doc_perf_class(paths, text):
    """两侧共用的合并判据：结构类来自清单，内容类来自正文。返回 dict（含 evidence/partial 由调用方补）。"""
    tree_hits, tree_ev = doc_perf_tree_class(paths)
    text_hits, text_ev = doc_perf_text_class(text)
    out = dict(tree_hits)
    out.update(text_hits)
    out["classes"] = sorted(k for k, v in out.items() if v is True)
    out["evidence"] = dict(tree_ev, **text_ev)
    return out


def self_doc_perf(rev="HEAD"):
    """self 侧用**同一套规则**跑 git 面（清单=ls-tree，正文=README blob），不读工作树。"""
    paths = git_ls_tree(rev)
    dirs = []
    for p in paths:
        head = p.rsplit("/", 1)[0] if "/" in p else ""
        if head:
            dirs.append(head + "/")
    joined = "\n".join(dirs) + "\n" + "\n".join(paths)
    readme = git_blob("README.md", rev) if "README.md" in paths else ""
    cls = doc_perf_class(paths, readme)
    cls["face"] = rev
    cls["self_paths"] = len(paths)
    cls["readme_chars"] = len(readme)
    return cls


def doc_perf_downgrade(cls, tree_present):
    """纯函数：树清单没取到 ⇒ 树派生类一律降到 None（未验），**不得**留 False（＝"该仓没有"）。

    这是 r75 给执行型质量门修的同一个洞的另一半：那一半修在 `qg_exec_verdict`，
    这一半修在同址尺的文档/性能维。R263 精神——先修判据，不改数据凑绿。
    """
    if tree_present:
        return cls
    out = dict(cls)
    for c in TREE_DERIVED_CLASSES:
        out[c] = None
    return out


def doc_perf_counts(audit, key):
    """纯函数：把 {仓: 读数} 切成 (有, 无, 未验, 分母)；未验**单列**，不并进"无"。"""
    has = [k for k, v in audit.items() if v.get(key) is True]
    no = [k for k, v in audit.items() if v.get(key) is False]
    unv = [k for k, v in audit.items() if v.get(key) is None]
    return len(has), len(no), len(unv), len(audit), sorted(has), sorted(unv)


def doc_perf_audit(repos, limit=200000):
    """对每个参照仓取 tree 清单 + README 正文跑同一判据；取不到必须记 unverified 并点名。"""
    out = {}
    for r in repos:
        full = r["repo"]
        branch = r.get("default_branch") or "HEAD"
        paths, errs = [], []
        try:
            tr = gh("repos/%s/git/trees/%s?recursive=1" % (full, branch), timeout=90)
            paths = [e["path"] for e in tr.get("tree", []) if e.get("type") == "blob"]
            if tr.get("truncated"):
                errs.append("tree_truncated")
        except Exception as e:
            errs.append("tree:" + str(e)[:70])
        text = ""
        try:
            rd = gh("repos/" + full + "/readme")
            text = base64.b64decode((rd.get("content") or "").strip()).decode("utf-8", errors="replace")[:limit]
        except Exception as e:
            errs.append("readme:" + str(e)[:70])
        if not paths and not text.strip():
            out[full] = {"classes": [], "evidence": {}, "unverified": "; ".join(errs) or "两路均空"}
            continue
        cls = doc_perf_class(paths, text)
        # 只「整棵清单没取到」才降级；truncated（取到一部分）留在 partial 里由人工判，不静默改口径
        cls = doc_perf_downgrade(cls, tree_present=bool(paths))
        cls["partial"] = bool(errs)
        if errs:
            cls["partial_errors"] = "; ".join(errs)
        cls["path_count"] = len(paths)
        out[full] = cls
    return out


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


# ── r75：**质量门**的同址尺——问的是"这道检查能不能让构建失败"，不是"有没有这个配置文件"。
#     起因（本轮只读枚举，非凭印象）：`_test/peer_quality_tooling_probe.py`（r58）自己写明了天花板
#     ——「覆盖率与缺陷率都不在本轮取数面内」，它量的是**配置在不在、测试文件在不在、CI 有没有执行位**；
#     而 self 侧实测 `grep -n "jacoco\|coverage" server/pom.xml` = 0 命中（surefire 在，跑用例但**无门槛**）。
#     同一件"质量工程"的两个半边：一只尺量"有没有装"，另一只量"装了之后会不会拦人"——后者从没量过，
#     正是「把现成的尺换到没人量的那一半」。判据形状按类分两种，**不许混用**：
#       · coverage / mutation 这类是**阈值型**：配置文件在 ≠ 有门，必须见到"低于阈值即失败"的形状
#         （`fail_under` / `--cov-fail-under` / `check-coverage` / `thresholds.break` / jacoco 的 `<rule><limit><minimum>`）；
#       · lint / typecheck / secret-scan 这类是**执行型**：退出码天然非零，门槛＝"配置 ∧ CI 真跑它"。
#     与 r73/r74 通道同源：不参与 caps、不设兜底、取不到内容一律 `unverified`（不得写成"该仓没有门"）。
QG_CLASSES = ("coverage_gate", "mutation_gate", "lint_gate", "typecheck_gate", "secret_scan_gate")
QG_CANDIDATES = {
    "coverage_gate": re.compile(r"(^|/)(jacoco[\w.-]*\.xml|\.coveragerc|coverage\.cfg|setup\.cfg"
                                r"|codecov\.ya?ml|\.nycrc[\w.-]*|pyproject\.toml|vitest\.config\.[\w]+|jest\.config\.[\w]+"
                                r"|pom\.xml$|build\.gradle(\.kts)?$)"
                                r"|(^|/)(tests?|benchmarks?)/?cov[\w.-]*\.yml$", re.I),
    "mutation_gate": re.compile(r"(^|/)(stryker[\w.-]*\.(js|ts|cjs|mjs|json)|mutmut\.cfg|setup\.cfg"
                                r"|infection[\w.-]*\.(json|dist)|pitest[\w.-]*|pom\.xml)$", re.I),
    "lint_gate": re.compile(r"(^|/)(\.eslintrc[\w.-]*|eslint\.config\.[\w]+|\.pylintrc|ruff\.toml"
                            r"|\.flake8|biome\.json(?:c)?|\.standard-json|golangci\.yml)$", re.I),
    "typecheck_gate": re.compile(r"(^|/)(tsconfig[\w.-]*\.json|mypy\.ini|pyrightconfig\.json"
                                 r"|\.pylintrc|typed\.py)$", re.I),
    "secret_scan_gate": re.compile(r"(^|/)(\.gitleaks\.toml|\.secrets\.baseline|\.pre-commit-config\.yaml"
                                   r"|\.secretlintrc[\w.-]*|\.trufflehog|detect_secrets[\w.-]*)$", re.I),
}
# 阈值型类的"会让构建失败"形状（正文面；只在这些候选文件里找，避免全仓正文爆炸）
QG_THRESHOLD_SHAPE = {
    "coverage_gate": re.compile(r"(fail_under|cov-fail-under|check-coverage|thresholds?[^\n]{0,40}?\b(lines|functions|statements)"
                                r"|<rule>|<limit>|minimum|coverage[^\n]{0,24}?(8|9)\d(\.\d+)?%)", re.I),
    "mutation_gate": re.compile(r"(mutationScoreThreshold|mutationThreshold|<mutationScale|failure_under"
                                r"|min-msi|mutator[\s\S]{0,30}?(coverage|mutation)|thresholds[\s\S]{0,24}break"
                                r"|\b(pitest|stryker|mutmut|infection)\b[\s\S]{0,60}?(threshold|limit|break|msi))",
                               re.I),
}
QG_CI_EXEC_SHAPE = re.compile(r"(eslint|biome|flake8|ruff|pylint|mypy|pyright|tsc\s+--noEmit|gitleaks"
                              r"|trufflehog|detect-secrets|secretlint|jacoco|codecov|nyc|vitest\s+--coverage"
                              r"|pytest[^\n]{0,40}--cov)", re.I)
# 执行型类的 CI 形状**按工具词**匹配（本轮 selftest 的正例抓到一处自欺：早期版本拿"文件名正则"去搜 CI 正文，
# 于是 `npm run lint: eslint . --max-warnings 0` 这种真在拦人的步被判成"CI 没跑" ⇒ 假阴性）。
QG_EXEC_TOKENS = {
    "lint_gate": re.compile(r"(eslint|biome|flake8|ruff|pylint|standard\b|rubocop|clippy|golint|revive"
                            r"|风格|规范检查|代码检查|代码风格)", re.I),
    "typecheck_gate": re.compile(r"(mypy|pyright|tsc\s+--noEmit|tsc\s+-p|flow\s+check|typescript\s+--noEmit"
                                 r"|类型检查|静态类型)", re.I),
    "secret_scan_gate": re.compile(r"(gitleaks|trufflehog|detect[-_]?secrets|secretlint|git-secrets|snyk\s+code"
                                   r"|checkov|semgrep|密钥[^\n]{0,12}(扫描|检查|零入库)|零密钥)", re.I),
}
# CI 面的取样上限：**取不全时不得判"没有"**（blindness is not zero）。wf_fetched < wf_total 且没找到执行位
# ⇒ 该类记 None（unverified），而不是 False。r75 首跑就是因为只取 3 个 workflow 而 lobehub 有 31 个，
# 把整面读成"peers 一律无门"——那是我的取数面塌缩，不是对手的事实。
QG_CI_FETCH_CAP = 12


def qg_ci_face(paths):
    """从清单里挑出 workflow 文件（返回全部路径与条数，由调用方决定取多少并如实报覆盖率）。"""
    wf = [p for p in (paths or []) if p.startswith(".github/workflows/") and p.endswith((".yml", ".yaml"))]
    return wf


# r78 第二条路由：**自写门禁**。旧 `qg_classify` 对执行型三类的第一句是 `if not files: out=False`，
# 而 `files` 只来自"标准工具文件名"清单（.gitleaks.toml / eslint.config.* / mypy.ini…）⇒
# 本仓的密钥门 `_test/tracked_secret_scan.py` 明明被 CI 每一步跑着（ci.yml 现读第 56 行确有该步骤），
# 却被这把尺读成「self=❌无」，r77 总览表因此带了一条**假缺口**；同法对 peers 也失效，
# 那一格的分子分母从来就不是对手的事实。
# 与 r75「有配置≠有门」互为对偶：那条防"假阳"，这条防"假阴"。
QG_RUN_CMD = re.compile(r"^(?:-\s*)?(?:run:\s*)?(?:[\w./-]*/)?(?:npx|npm\s+run|yarn|pnpm|uvx?|pipx|"
                        r"python3?|bash|sh|go|cargo|make|gradle|mvn|deno|bun)\b")
QG_INVOKED_TOKENS = {
    "lint_gate": re.compile(r"\b(eslint|biome|flake8|ruff|pylint|rubocop|clippy|golint|revive)\b"
                            r"|[\w./-]*(?:lint|eslint)[\w.-]*\.(?:py|sh|js|ts)", re.I),
    "typecheck_gate": re.compile(r"\b(mypy|pyright|pytype)\b|\btsc\s+(?:-p|--noEmit)\b"
                                 r"|[\w./-]*(?:typecheck|tsc|mypy|pyright)[\w.-]*\.(?:py|sh|js|ts)", re.I),
    "secret_scan_gate": re.compile(r"\b(gitleaks|trufflehog|secretlint|git-secrets|detect[-_]secrets)\b"
                                   r"|[\w./-]*(?:secret|gitleaks|trufflehog)[\w.-]*\.(?:py|sh|js|ts)", re.I),
}


def qg_invoked_line(cls, ci_text):
    """纯函数：找 CI 里"执行行真调用了一个带该类工具词的可执行体"的第一行。

    只认执行行（`run:` 之后或以解释器/构建工具开头的行）——**注释与步骤名不算**，
    否则 `起 fat jar（无密钥，仅情绪接口）` 这种描述性文字会把"没门"读成"有门"。
    """
    rx = QG_INVOKED_TOKENS.get(cls)
    if not rx:
        return ""
    for line in (ci_text or "").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.startswith("- name:") or s.startswith("name:"):
            continue
        if not QG_RUN_CMD.search(s):
            continue
        if rx.search(s):
            return s[:120]
    return ""


def qg_exec_verdict(cls, files, ci_text, ci_complete):
    """执行型类的三态判定：True=找到执行位 / False=CI 面读全了且确实没有 / None=面没读全，不得下结论。

    两条路由任一命中即 True：① 标准配置文件 ∧ CI 执行位（r75 原口径）；
    ② 无标准配置但 CI 执行行真调用了带该类工具词的可执行体（r78 新增，覆盖自写门禁）。
    """
    if files:
        m = QG_EXEC_TOKENS[cls].search(ci_text or "")
        if m:
            return True, "%s ∧ CI 执行位=%s" % (files[0], m.group(0)[:40])
    inv = qg_invoked_line(cls, ci_text)
    if inv:
        return True, "自写门禁 ∧ CI 真调用：%s" % inv
    if not ci_complete:
        return None, "%s CI 面未取全 ⇒ 不得判「无门」" % ("%s 在，但" % files[0] if files else "")
    return False, ("%s 在而 CI 面取全后未见执行位" % files[0]) if files \
        else "无标准配置、且 CI 执行行里没有该类可执行体（步骤名/注释不计）"


def qg_tree_candidates(paths):
    """结构面：每个类挑出候选文件（只证"有这个东西"，不证它有牙）。"""
    cand = {}
    for cls, rx in QG_CANDIDATES.items():
        cand[cls] = [p for p in (paths or []) if len(p) < 300 and rx.search(p)]
    return cand


def qg_classify(cand, blobs, ci_text, ci_complete=True):
    """纯函数：候选文件 + 这些文件的正文 + workflow 文本 → 五类的"能不能拦人"。

    阈值型类必须有**失败形状**才算 gate；执行型类必须有**配置 ∧ CI 执行位**。
    候选存在但正文没取到 ⇒ 该类记 `unverified`（不得塌缩成 False）；
    CI 面没取全（`ci_complete=False`）而没找到执行位 ⇒ 同样记 None，**不得判"没有门"**。
    """
    out, ev, unv = {}, {}, []
    for cls in QG_CLASSES:
        files = cand.get(cls) or []
        if cls in QG_THRESHOLD_SHAPE:
            if not files:
                out[cls] = False
                continue
            read = [f for f in files if f in blobs]
            if not read:
                unv.append("%s(候选 %s 正文未取到)" % (cls, files[0]))
                out[cls] = None
                continue
            hit = next(((f, QG_THRESHOLD_SHAPE[cls].search(blobs[f])) for f in read
                        if QG_THRESHOLD_SHAPE[cls].search(blobs[f] or "")), None)
            out[cls] = bool(hit)
            if hit:
                ev[cls] = "%s :: %s" % (hit[0], hit[1].group(0)[:60])
        else:
            # r78：执行型三类**不得**因为"没有标准配置文件"就直接判无——自写门禁只看 CI 执行行
            v, why = qg_exec_verdict(cls, files, ci_text, ci_complete)
            out[cls] = v
            ev[cls] = why
            if v is None:
                unv.append("%s(CI 面未取全)" % cls)
    return out, ev, unv


def self_quality_gates(rev="HEAD"):
    """self 侧走同一函数：清单=ls-tree，正文=pom/配置 blob，CI 文本=`.github/workflows/*.yml` blob。"""
    paths = git_ls_tree(rev)
    cand = qg_tree_candidates(paths)
    want = sorted({f for files in cand.values() for f in files})[:8]
    blobs = {}
    errs = []
    for f in want:
        try:
            blobs[f] = git_blob(f, rev)
        except Exception as e:
            errs.append("%s:%s" % (f, str(e)[:40]))
    ci_all = qg_ci_face(paths)
    ci_take = ci_all[:QG_CI_FETCH_CAP]
    ci_text, errs2 = "", []
    for f in ci_take:
        try:
            ci_text += git_blob(f, rev) + "\n"
        except Exception as e:
            errs2.append("ci:%s" % str(e)[:40])
    cls, ev, unv = qg_classify(cand, blobs, ci_text, ci_complete=(len(ci_all) <= len(ci_take)))
    # 天花板自证：本尺认两形——① 标准工具配置（.gitleaks.toml / eslint.config.* / jacoco `<limit>`…）
    #   ∧ CI 执行位；② r78 补：**无标准配置但 CI 执行行真调用了一个带该类工具词的可执行体**（自写门禁）。
    #   两侧同一函数 ⇒ 同法；注释与步骤名不计（防"提到关键词就算有门"）。
    # `ci_steps_homegrown` 继续带出全部自写步骤名，供人核"名册 vs 判定"是否同源，只作说明不参与对照。
    step_names = re.findall(r"(?m)^\s*-\s+name:\s*(.+)$", ci_text)
    return {"classes": cls, "evidence": ev, "unverified": unv + errs, "ci_face": "%d/%d" % (len(ci_take), len(ci_all)),
            "candidates": {k: v[:3] for k, v in cand.items()}, "face": rev,
            "ci_step_count": len(step_names),
            "ci_steps_homegrown": [s.strip()[:34] for s in step_names
                                   if re.search(r"守卫|门禁|红线|校验|扫描|自检|对账|预算|一致性", s)],
            "partial_errors": "; ".join(errs + errs2)}


def quality_gate_audit(repos, max_fetch=4):
    """peers 侧：tree 挑候选 → 只取候选文件正文（≤max_fetch/仓）→ 同一 qg_classify。"""
    out = {}
    for r in repos:
        full = r["repo"]
        branch = r.get("default_branch") or "HEAD"
        errs, paths, ci_text = [], [], ""
        try:
            tr = gh("repos/%s/git/trees/%s?recursive=1" % (full, branch), timeout=90)
            paths = [e["path"] for e in tr.get("tree", []) if e.get("type") == "blob"]
            if tr.get("truncated"):
                errs.append("tree_truncated")
        except Exception as e:
            errs.append("tree:" + str(e)[:60])
            out[full] = {"classes": {}, "evidence": {}, "unverified": ["tree 取不到：" + str(e)[:60]]}
            continue
        cand = qg_tree_candidates(paths)
        blobs = {}
        for cls, files in cand.items():
            for f in files[:max_fetch]:
                if f in blobs:
                    continue
                try:
                    d = gh("repos/%s/contents/%s?ref=%s" % (full, f, branch), timeout=40)
                    blobs[f] = base64.b64decode((d.get("content") or "").strip()).decode("utf-8", errors="replace")
                except Exception as e:
                    errs.append("%s:%s" % (f, str(e)[:40]))
        ci_all = qg_ci_face(paths)
        ci_take = ci_all[:QG_CI_FETCH_CAP]
        for p in ci_take:
            if p in blobs:
                continue
            try:
                d = gh("repos/%s/contents/%s?ref=%s" % (full, p, branch), timeout=40)
                blobs[p] = base64.b64decode((d.get("content") or "").strip()).decode("utf-8", errors="replace")
            except Exception as e:
                errs.append("ci:%s" % str(e)[:40])
        ci_text = "\n".join(blobs[p] for p in ci_take if p in blobs)
        cls, ev, unv = qg_classify(cand, blobs, ci_text, ci_complete=(len(ci_all) <= len(ci_take)))
        out[full] = {"classes": cls, "evidence": ev, "unverified": unv,
                     "ci_face": "%d/%d" % (len(ci_take), len(ci_all)),
                     "candidates": {k: v[:3] for k, v in cand.items()},
                     "partial": bool(errs), "partial_errors": "; ".join(errs)[:160]}
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


TREE_FIELDS = ("caps", "docs")
BLIND_SEP = "#"


def split_field(field):
    """`caps#本轮树取数失败` → `("caps", "本轮树取数失败")`；无标记 → `(field, None)`。"""
    if BLIND_SEP in field:
        k, reason = field.split(BLIND_SEP, 1)
        return k, reason
    return field, None


def tree_blind_reason(row):
    """这一行的**树派生读数**（caps/docs/file_count）有没有取到。

    判据只认取数状态，不认"清单为空"——树真取到了、里面真没匹配文件，那是对手的实况，
    必须留在「实质」档（否则这把尺从此看不见任何能力退化）。
    `file_count` 用 `in row` 而非 `.get()`：历史快照与 selftest 合成行没这个键，
    按 `.get()` 判会让所有旧行都变成"瞎"，把实质差整批吞进盲区档。
    """
    if row.get("tree_error"):
        return "树取数失败"
    if row.get("tree_truncated"):
        return "树截断"
    if "file_count" in row and row["file_count"] is None:
        return "树读数缺失"
    return None


def diff_snap(prev_repos, cur_repos,
              keys=("stars", "pushed_at", "latest_release", "ci_workflows", "caps", "docs")):
    """逐仓逐字段差值。返回 [(repo, field, old, new)]；全等快照必须返回空列表。

    r21 补：`caps` / `docs` 也纳入比对。根因是本轮第二次采集实测抓到 sapphire 的 `container`
    能力**从清单里消失却零漂移报告** —— 只比 4 个数字字段的"漂移守卫"对能力矩阵变化是瞎的。

    r79-D 补「取数失败差」：字段名带 `#原因` ⇔ 这一格的变化来自**我这把尺瞎**，不是对手动了。
    一手代价：14/16 降级采集报出 `▶ 实质 morettt/my-neuro caps: ['i18n_locale','vector_memory'] -> []`
    —— 读起来像"对手把记忆能力删了"，实际是那 2 仓之一的 git 树没取到，`probe_repo` 的
    `except` 支把 caps/docs 置了空。三类字段的取数失败形态不同，规则也不同：
      · `caps`/`docs` —— 看**该侧行**的树状态（tree_error / tree_truncated / file_count is None）；
      · `ci_workflows` —— probe_repo 里唯一带 try/except 的字段，None ⟺ 那次调用失败
        （零工作流的仓回 `total_count=0`），所以**两个方向**都算取数失败；
      · `stars`/`pushed_at`/`latest_release` —— 取数失败会让整行缺席（`gh()` 直接抛 → hard_fail），
        能出现在这里的都是真差，`latest_release None -> v2` 是真发了一版，不得并入本档。
    元组长度保持 4：下游按 4 值解包的点很多，加一位要么当场崩、要么静默错位。
    """
    drift = []
    prev = {r["repo"]: r for r in prev_repos}
    for cur in cur_repos:
        old = prev.get(cur["repo"])
        if not old:
            drift.append((cur["repo"], "repo_added", None, cur.get("stars")))
            continue
        cur_blind = tree_blind_reason(cur)
        prev_blind = tree_blind_reason(old)
        for k in keys:
            o, n = old.get(k), cur.get(k)
            if o == n:
                continue
            if k in TREE_FIELDS and cur_blind:
                k = f"{k}{BLIND_SEP}本轮{cur_blind}：空清单是没看到，不是对手删了"
            elif k in TREE_FIELDS and prev_blind:
                k = f"{k}{BLIND_SEP}基线{prev_blind}：本轮补上，不是对手新增"
            elif k == "ci_workflows" and (o is None or n is None):
                k = f"{k}{BLIND_SEP}工作流清单没取到（None=调用失败，不是没有 CI）"
            drift.append((cur["repo"], k, o, n))
    return drift


def classify_drift(drift):
    """把漂移分成「实质 / 抖动 / 补录 / 取数失败」四档 ⇒ (substantive, noise, roster, blind)。

    r26 加：本轮 6 处漂移里 4 处是 ★ 数 ±1（含 lobehub 82,808→82,807 的**倒退**，
    平台清虚假账号所致），单点 star 差值不构成趋势证据；若与"对手发布 v2.5.0→v2.13.1"
    混在一张表里报，台账就失去了指方向的能力。故 stars 一律入抖动档，
    其余字段（pushed_at / latest_release / ci_workflows / caps / docs）算实质。

    r77 加第三档：`repo_added`（基线里根本没有这仓）**不是对手动了**，而是我这把尺
    自己上一轮没数到它——一手代价：02:53 那次采集 3 个仓 `unexpected EOF` 判红，
    但它已经把残缺快照**覆写进台账**，下一次采集于是报出 5 处「实质（可行动）」
    （opensoul/succhia/ryza/MoodChat 全是 `None -> 值`）。把"我补齐了覆盖"记成
    "对手发生了变化"，会把人支去做一件不存在的动作。

    r79-D 加第四档：与补录档同一族、粒度不同——补录是**整仓**上轮没数到，本档是**单字段**
    这轮或上轮没数到（见 diff_snap 的标记规则）。两档都不许进「实质」，共同的判据是一句话：
    **「实质」= 对手动了；这三档 = 我的尺动了。** 四档求和必须等于总漂移，
    由调用处断言（分档器悄悄吞一格，比误分更坏——它会让你以为世界很安静）。
    """
    def key_of(d):
        return split_field(d[1])[0]

    blind = [d for d in drift if BLIND_SEP in d[1]]
    named = [d for d in drift if BLIND_SEP not in d[1]]
    roster = [d for d in named if key_of(d) == "repo_added"]
    noise = [d for d in named if key_of(d) == "stars"]
    sub = [d for d in named if key_of(d) not in ("stars", "repo_added")]
    return sub, noise, roster, blind


def pick_snapshot_path(path, fetched, expected):
    """降级采集不得覆写权威台账（r77）：取数不全时另写 `.partial.json`，基线留给上一次完整采集。

    与 r76「存在性 ≠ 能力」「没读到 ≠ 没有」同一族：**残缺读数一旦进了分母，
    下一轮就没人能区分"世界变了"与"我上轮瞎了"。**
    """
    if expected and fetched < expected:
        return path.with_name(path.stem + ".partial" + path.suffix)
    return path


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
    sub, noise, roster, blind = classify_drift(got)
    if [(s[0], s[1]) for s in noise] != [("lobehub/lobehub", "stars")]:
        print(f"SELFTEST-FAIL: 抖动档应只有 stars，实际 {[(n[0], n[1]) for n in noise]}")
        return 1
    if len(sub) != 3 or any(s[1] == "stars" for s in sub):
        print(f"SELFTEST-FAIL: 实质档应含 pushed_at/caps/docs 三条且不含 stars，实际 {[(s[0], s[1]) for s in sub]}")
        return 1
    if roster or blind:
        print(f"SELFTEST-FAIL: 基线未缺仓、树也取到了，却判出补录/取数失败档（判据过敏）："
              f"roster={roster} blind={blind}")
        return 1
    if len(sub) + len(noise) + len(roster) + len(blind) != len(got):
        print(f"SELFTEST-FAIL: 四档求和 {len(sub)+len(noise)+len(roster)+len(blind)} != 总漂移 {len(got)}"
              "（分档器吞格 ⇒ 世界看起来比实际安静）")
        return 1
    only_stars = [d for d in got if d[1] == "stars"]
    s2, n2, r2, b2 = classify_drift(only_stars)
    if s2 or len(n2) != 1 or r2 or b2:
        print(f"SELFTEST-FAIL: 纯 ★ 抖动被误判为实质（分类器恒真）：sub={s2}")
        return 1
    # r77 反例：基线缺仓（上一轮取数失败留下的残缺快照）必须落「补录」档，不得算成对手的变化
    degraded_prev = [r for r in base if r["repo"] != "s-nagaev/chibi"]
    s3, n3, r3, b3 = classify_drift(diff_snap(degraded_prev, base))
    if s3 or n3 or b3 or len(r3) != 1 or r3[0][0] != "s-nagaev/chibi" or split_field(r3[0][1])[0] != "repo_added":
        print(f"SELFTEST-FAIL: 基线缺仓应只进补录档，实际 sub={[(x[0], x[1]) for x in s3]} "
              f"noise={[(x[0], x[1]) for x in n3]} roster={[(x[0], x[1]) for x in r3]} blind={b3}")
        return 1
    # r79-D 正例：本轮树没取到 ⇒ caps/docs 从有到空是**我这把尺瞎**，不得读成"对手删了能力"
    blind_cur = json.loads(json.dumps(base))
    blind_cur[0]["caps"] = []
    blind_cur[0]["docs"] = []
    blind_cur[0]["file_count"] = None
    blind_cur[0]["tree_error"] = "boom"
    s4, n4, r4, b4 = classify_drift(diff_snap(base, blind_cur))
    if s4 or n4 or r4 or sorted(split_field(x[1])[0] for x in b4) != ["caps", "docs"]:
        print(f"SELFTEST-FAIL: 树取数失败的 caps/docs 空清单仍进了实质档（把瞎读成退化）："
              f"sub={[(x[0], x[1]) for x in s4]} blind={[(x[0], x[1]) for x in b4]}")
        return 1
    if not any("树取数失败" in x[1] for x in b4):
        print(f"SELFTEST-FAIL: 取数失败档没点名原因（只说「这格不算」却不说为什么 = 第二条盲区账）："
              f"{[x[1] for x in b4]}")
        return 1
    # r79-D 变异腿（反向自证）：摘掉 tree_error 那一行，同一份 caps/docs 空清单**必须**回落实质档
    _mangled = json.loads(json.dumps(blind_cur))
    del _mangled[0]["tree_error"]
    _mangled[0]["file_count"] = 1234
    s5, n5, r5, b5 = classify_drift(diff_snap(base, _mangled))
    if len(s5) != 2 or b5:
        print(f"SELFTEST-FAIL: 摘掉取数失败标记后实质档仍为 {len(s5)} 条 ⇒ 这条腿没作用在被审对象上，"
              f"分档器在无条件吞掉 caps/docs（blind={[(x[0], x[1]) for x in b5]}）")
        return 1
    # r79-D 第三、四态：基线侧瞎（本轮补上）与 ci_workflows 的 None 双向
    blind_prev = json.loads(json.dumps(base))
    blind_prev[1]["caps"] = []
    blind_prev[1]["file_count"] = None
    blind_prev[1]["tree_error"] = "boom"
    cur_full = json.loads(json.dumps(base))
    cur_full[1]["caps"] = ["vector_memory", "container"]
    s6, n6, r6, b6 = classify_drift(diff_snap(blind_prev, cur_full))
    if s6 or len(b6) != 1 or "基线树取数失败" not in b6[0][1]:
        print(f"SELFTEST-FAIL: 基线侧树瞎、本轮补上，应进取数失败档并写明「基线」："
              f"sub={[(x[0], x[1]) for x in s6]} blind={[(x[0], x[1]) for x in b6]}")
        return 1
    wf_drift = diff_snap(base, [dict(base[0], ci_workflows=None), base[1]])
    s7, n7, r7, b7 = classify_drift(wf_drift)
    if s7 or len(b7) != 1 or split_field(b7[0][1])[0] != "ci_workflows":
        print(f"SELFTEST-FAIL: ci_workflows 5→None（该字段唯一带 try/except，None=调用失败）"
              f"应进取数失败档：sub={[(x[0], x[1]) for x in s7]} blind={b7}")
        return 1
    # 反面对照：latest_release None→v2 是**真发布**（取数失败会让整行缺席），不得并入本档
    s8, n8, r8, b8 = classify_drift(diff_snap(base, [dict(base[0], latest_release=None), base[1]]))
    if len(s8) != 1 or b8:
        print(f"SELFTEST-FAIL: v1→None 这类无 try/except 字段的差被误判成取数失败 ⇒ 实质档会漏报退化："
              f"sub={[(x[0], x[1]) for x in s8]} blind={b8}")
        return 1
    # r77 写盘守卫：降级采集另写 .partial，完整采集才覆写权威台账（两侧都验）
    from pathlib import Path as _P
    snap = _P("交付物/对标数据/benchmark-metrics.json")
    if pick_snapshot_path(snap, 13, 16) != snap.with_name("benchmark-metrics.partial.json"):
        print("SELFTEST-FAIL: 降级采集（13/16）没有另写 partial ⇒ 残缺读数会覆写基线")
        return 1
    if pick_snapshot_path(snap, 16, 16) != snap or pick_snapshot_path(snap, 16, 0) != snap:
        print("SELFTEST-FAIL: 完整采集（或无分母）却把台账改道了")
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
    # ── r74 同址尺（文档维 / 性能维）：五类结构 + 两类内容，每类都配方向相反的腿
    _d1, _e1 = doc_perf_tree_class(["docs/index.md", "src/app.tsx"])
    if not _d1["docs_site"] or _d1["agent_facing_doc"] or _d1["changelog_root"]:
        print("SELFTEST-FAIL: docs 目录面判错（docs_site 应真、agent 面与 changelog 应假）：%s" % _d1)
        return 1
    # docs_site 的第二条腿只走"站点配置文件"这一形（与目录那条规则各自专属，摘掉任一都必须翻红）
    _d1b, _ = doc_perf_tree_class(["mkdocs.yml", "src/app.tsx"])
    if not _d1b["docs_site"]:
        print("SELFTEST-FAIL: docs_site 的配置文件腿恒假（mkdocs.yml 没被认出）：%s" % _d1b)
        return 1
    _d2, _ = doc_perf_tree_class(["AGENTS.md", "README.md"])
    if not _d2["agent_facing_doc"] or _d2["docs_site"]:
        print("SELFTEST-FAIL: AGENTS.md 与「文档站」互相冒充（反向腿①）：%s" % _d2)
        return 1
    _d3, _ = doc_perf_tree_class(["CHANGELOG.md"])
    _d4, _ = doc_perf_tree_class(["pkg/CHANGELOG.md"])
    if not _d3["changelog_root"] or _d4["changelog_root"]:
        print("SELFTEST-FAIL: changelog_root 不分根级/子目录（两条相反用例必须一真一假）")
        return 1
    _d5, _ = doc_perf_tree_class([".github/workflows/ci.yml"])
    _d6, _ = doc_perf_tree_class([".github/workflows/perf-bench.yml"])
    if _d5["ci_perf_step"] or not _d6["ci_perf_step"]:
        print("SELFTEST-FAIL: CI 性能步判错（普通 ci.yml 不得算，perf-bench.yml 必须算）")
        return 1
    _d7, _ = doc_perf_tree_class(["benchmarks/run.go", "locustfile.py", "k6.load.js"])
    if not _d7["bench_script"]:
        print("SELFTEST-FAIL: 三种常见压测件形态都没认出来 ⇒ 结构类恒假")
        return 1
    # r74 首跑真面抓到的四处冒充，逐条钉成永久反例（原文照抄，不是我编的形状）
    # 最后一条是给 BENCH_DENY 的**专属输入面**：收紧 RE_BENCH_PATH 后，深路径已结构性出局，
    # 但 `scripts/` 根级仍会命中，此时只有 deny 能否掉"指标汇总器"——没有这条样本，deny 就是死规则（实测摘掉它 rc 仍 0）。
    _must_not_bench = ["_test/benchmark_metrics.py",
                       "bundled-skills/default-enabled/skill-creator/scripts/aggregate_benchmark.py",
                       "apps/server/src/router-hono/devtools/handlers/memoryUserMemoryBenchmarkLocomo.ts",
                       "docs/performance-notes.md",
                       "scripts/benchmark_metrics.py", "scripts/collect_bench_metrics.py"]
    _fp = [p for p in _must_not_bench if doc_perf_tree_class([p])[0]["bench_script"]]
    if _fp:
        print("SELFTEST-FAIL: 采集器/汇总器/深路径仍被算成测量装置（假阳未修住）：" + " ; ".join(_fp))
        return 1
    _must_bench = ["_test/perf_baseline_check.py", "tools/tts_benchmark.py",
                   "scripts/bench-model.ts", "bench/http.py"]
    _fn = [p for p in _must_bench if not doc_perf_tree_class([p])[0]["bench_script"]]
    if _fn:
        print("SELFTEST-FAIL: 收紧时把真装置一起砍掉了（正例失控）：" + " ; ".join(_fn))
        return 1
    _deny_on = doc_perf_tree_class(["_test/benchmark_metrics.py", "_test/perf_baseline_check.py"])[0]
    if not _deny_on["bench_script"] or "benchmark_metrics" in str(_deny_on.get("evidence", {}).get("bench_script", "")):
        print("SELFTEST-FAIL: bench 类的取样顺序失真（应命中 perf_baseline_check 而非采集器）：%s" % _deny_on)
        return 1
    if doc_perf_tree_class([".github/workflows/deploy-workbench.yml"])[0]["ci_perf_step"]:
        print("SELFTEST-FAIL: deploy-workbench.yml 仍被当成 CI 性能步（lobehub 首跑那处假阳没修住）")
        return 1
    if doc_perf_text_class("- 曲线由控制页本地生成（250ms 步进的正弦/方波/斜坡），只有波形*规格*走网络"
                           "——丝滑程度与网络延迟无关。")[0]["published_numbers"]:
        print("SELFTEST-FAIL: 「与网络延迟无关」这类设计陈述被当成公开性能数字（succhia 首跑假阳）")
        return 1
    _tx = lambda s: doc_perf_text_class(s)[0]          # 只取判定字典（证据留给合并函数）
    _t_good = "\n".join(["# Title"] + ["## S%d" % i for i in range(6)]
                        + ["[![CI](x.svg)](y)", "![shot](a.png)", "## Install", "x" * 3000])
    _t_long_only = "y" * 5000
    _t_marketing = "\n".join(["# 标题"] + ["## S%d" % i for i in range(6)] + ["我们追求极致性能，快到飞起。", "z" * 3000])
    if not _tx(_t_good)["readme_thorough"]:
        print("SELFTEST-FAIL: 合规长 README（6 标题+徽章+截图+Install）未判 thorough")
        return 1
    if _tx(_t_long_only)["readme_thorough"]:
        print("SELFTEST-FAIL: 只有长度没有结构信号被判成好文档（营销文混进来）")
        return 1
    if not _tx("Throughput benchmark: p95 latency is 240 ms at 1,200 req/s.")["published_numbers"]:
        print("SELFTEST-FAIL: 同行含指标词与数+单位却没认出公开数字")
        return 1
    if _tx(_t_marketing)["published_numbers"]:
        print("SELFTEST-FAIL: 「极致性能」这类营销词被当成性能证据（反向腿②）")
        return 1
    if _tx("We have 12000 stars, thanks! (2024)")["published_numbers"]:
        print("SELFTEST-FAIL: 无关数字行（★ 数）冒充性能数字")
        return 1
    _z = doc_perf_class([], "")
    if _z["classes"] or _z["evidence"]:
        print("SELFTEST-FAIL: 零输入升格成能力（违反「零输入不得记 PASS」）：%s" % _z["classes"])
        return 1
    if _z.get("caps"):
        print("SELFTEST-FAIL: 同址尺返回值里出现 caps 键 ⇒ 它正在变成第二把 caps 尺")
        return 1
    # 变异腿：摘掉 agent 面与"数+单位"两条正则，对应类必须翻（证明判定力在它们身上）
    _g74 = globals()
    _orig_agent, _orig_num = _g74["RE_AGENT_DOC"], _g74["RE_PERF_NUM"]
    try:
        _g74["RE_AGENT_DOC"] = re.compile(r"(?!)")
        if doc_perf_tree_class(["AGENTS.md"])[0]["agent_facing_doc"]:
            print("SELFTEST-FAIL: 摘掉 RE_AGENT_DOC 后仍判 agent_facing_doc ⇒ 该类没在被判对象上")
            return 1
        _g74["RE_PERF_NUM"] = re.compile(r"(?!)")
        if _tx("p95 latency is 240 ms")["published_numbers"]:
            print("SELFTEST-FAIL: 摘掉 RE_PERF_NUM 后仍判 published_numbers ⇒ 恒真是营销词在替它判")
            return 1
    finally:
        _g74["RE_AGENT_DOC"], _g74["RE_PERF_NUM"] = _orig_agent, _orig_num
    # self 侧同址的**接线**自证：不读真实仓（桩不得依赖本机态），改用注入的 git 读数
    _orig_ls, _orig_blob = _g74["git_ls_tree"], _g74["git_blob"]
    asked = []
    try:
        _g74["git_ls_tree"] = lambda rev="HEAD": (asked.append(("ls", rev)),
                                                  ["README.md", "AGENTS.md", "CHANGELOG.md",
                                                   "docs/quality-gates.md"])[1]
        _g74["git_blob"] = lambda p, rev="HEAD": (asked.append(("blob", p, rev)), _t_good)[1]
        _s = self_doc_perf()
        if _s["face"] != "HEAD" or not _s["docs_site"] or not _s["agent_facing_doc"]:
            print("SELFTEST-FAIL: self 侧没走同址尺（face=%s %s）" % (_s["face"], _s["classes"]))
            return 1
        if ("ls", "HEAD") not in asked or ("blob", "README.md", "HEAD") not in asked:
            print("SELFTEST-FAIL: self 侧未从 git HEAD 面取数（取数面没被问到 = 接线是假的）：%s" % asked)
            return 1
    finally:
        _g74["git_ls_tree"], _g74["git_blob"] = _orig_ls, _orig_blob
    # ── r76：树派生类的「没读到 ≠ 没有」必须可演习（r75 只给执行型质量门修了这个洞的另一半）
    _d = doc_perf_downgrade({"docs_site": False, "changelog_root": False, "readme_thorough": True}, False)
    if _d["docs_site"] is not None or _d["changelog_root"] is not None or _d["readme_thorough"] is not True:
        print("SELFTEST-FAIL: 整棵 tree 取不到时存在性类没降到未验，或把文本派生类一起降了：%s" % (_d,))
        return 1
    if doc_perf_downgrade({"docs_site": False}, True)["docs_site"] is not False:
        print("SELFTEST-FAIL: 树明明取到了却被降成未验 ⇒ 这把尺会把自己的读数洗成不可知")
        return 1
    _a = {"x/y": {"docs_site": True, "readme_thorough": False},
          "z/w": {"docs_site": None},
          "q/r": {"docs_site": False, "readme_thorough": True}}
    _n = doc_perf_counts(_a, "docs_site")
    if (_n[0], _n[1], _n[2], _n[3]) != (1, 1, 1, 3):
        print("SELFTEST-FAIL: 有/无/未验 三档没分开（本轮治的正是把未验并进无）：%s" % (_n,))
        return 1
    _orig_tdc = globals()["TREE_DERIVED_CLASSES"]
    try:
        globals()["TREE_DERIVED_CLASSES"] = ()
        if doc_perf_downgrade({"docs_site": False}, False)["docs_site"] is None:
            print("SELFTEST-FAIL: 摘掉树派生类名单后仍降级 ⇒ 这条腿没作用在被判对象上（恒真）")
            return 1
    finally:
        globals()["TREE_DERIVED_CLASSES"] = _orig_tdc
    # ── r75 质量门同址尺：阈值型类必须"有牙"才算 gate；执行型类必须"配置 ∧ CI 真跑"
    _q_pom = "<project><plugin>jacoco-maven-plugin</plugin><configuration><rules><rule>" \
             "<limit><minimum>0.80</minimum></limit></rule></rules></configuration></project>"
    _q_nooth = "[run]\nbranch = True\nsource =\n    src/\n"        # 有 .coveragerc 但没有 fail_under
    _c1 = qg_tree_candidates(["server/pom.xml", "codecov.yml", ".eslintrc.json", "tsconfig.json"])
    if not _c1["coverage_gate"] or not _c1["lint_gate"]:
        print("SELFTEST-FAIL: 质量门候选清单没认出 pom/codecov/eslint：%s" % _c1)
        return 1
    _g1, _e1, _u1 = qg_classify({"coverage_gate": ["server/pom.xml"], "lint_gate": [".eslintrc.json"]},
                                {"server/pom.xml": _q_pom}, "npm run lint: eslint . --max-warnings 0")
    if _g1["coverage_gate"] is not True or _g1["lint_gate"] is not True:
        print("SELFTEST-FAIL: 合规正例没判出 gate（jacoco rule+limit / eslint ∧ CI）：%s %s" % (_g1, _e1))
        return 1
    _g2, _, _ = qg_classify({"coverage_gate": [".coveragerc"], "lint_gate": [".eslintrc.json"]},
                            {".coveragerc": _q_nooth}, "build: npm run build")
    if _g2["coverage_gate"]:
        print("SELFTEST-FAIL: 有 .coveragerc 没 fail_under 被判成覆盖率门（配置在≠有牙）")
        return 1
    if _g2["lint_gate"]:
        print("SELFTEST-FAIL: eslint 配置在而 CI 没跑它，仍判成 lint 门（执行型缺 CI 执行位）")
        return 1
    _g3, _, _u3 = qg_classify({"coverage_gate": ["codecov.yml"]}, {}, "lint")
    if _g3["coverage_gate"] is not None or not _u3:
        print("SELFTEST-FAIL: 候选正文没取到时塌缩成了 False 且没记 unverified：%s %s" % (_g3, _u3))
        return 1
    # r75 修正的两条专属腿：① CI 面没取全时**不得**判"没有门"（首跑我只取 3 个 workflow 而 lobehub 有 31 个）
    _gpartial, _ep, _up = qg_classify({"lint_gate": [".eslintrc.json"]}, {}, "nothing relevant", ci_complete=False)
    if _gpartial["lint_gate"] is not None or not _up:
        print("SELFTEST-FAIL: CI 面未取全却判成「无门」（取数面塌缩当结论）：%s %s" % (_gpartial, _up))
        return 1
    _gfull, _ef, _uf = qg_classify({"lint_gate": [".eslintrc.json"]}, {}, "nothing relevant", ci_complete=True)
    if _gfull["lint_gate"] is not False or _uf:
        print("SELFTEST-FAIL: CI 面取全时的对照组失效（「读全了确实没有」不得也记成未验）：%s" % _gfull)
        return 1
    # ② 中文步骤名假阴：本仓 CI 的密钥守卫 job 名叫「… + 密钥扫描」，只认英文工具词会把我方已有的门读成无
    _gzh, _ezh, _uzh = qg_classify({"secret_scan_gate": [".secrets.baseline"]}, {},
                                   "name: 同步守卫 + 情绪评测/策略表门禁 + 密钥扫描")
    if _gzh["secret_scan_gate"] is not True:
        print("SELFTEST-FAIL: 中文 CI 步骤名没认出（英文工具词假阴）：%s %s" % (_gzh, _ezh))
        return 1
    # ③ r78 自写门禁路由（正例）：**没有**任何标准配置文件，只靠 CI 执行行真调用 `_test/tracked_secret_scan.py`
    #    ⇒ 必须判 True，且证据点名那一行（这条腿抓的是 r77 报告总览表里那条 `self=❌无` 假缺口）
    _own_ci = ("jobs:\n  sync:\n    steps:\n      - name: 密钥零入库扫描\n        run: |\n"
               "          python _test/tracked_secret_scan.py --selftest\n"
               "          python _test/tracked_secret_scan.py\n")
    _gown, _eown, _uown = qg_classify({"secret_scan_gate": []}, {}, _own_ci)
    if _gown["secret_scan_gate"] is not True or "tracked_secret_scan" not in (_eown.get("secret_scan_gate") or ""):
        print("SELFTEST-FAIL: 自写门禁（无标准配置、CI 真调用）没认出或证据没点名行：%s %s" % (_gown, _eown))
        return 1
    # ③-b 反例（同一条腿的另一侧）：CI 里只有**描述性文字**提到"无密钥"、执行行是 java -jar ⇒ 必须 False，
    #      否则这条路由就把"提到关键词"升格成"有门"（与 r75「有配置≠有门」互为对偶）
    _li_ci = ("jobs:\n  demo:\n    steps:\n      - name: 起 fat jar（无密钥，仅情绪接口）\n"
              "        run: java -jar server/target/soulisle-server.jar\n")
    _gli, _eli, _uli = qg_classify({"secret_scan_gate": []}, {}, _li_ci)
    if _gli["secret_scan_gate"] is not False:
        print("SELFTEST-FAIL: 注释/步骤名里的「无密钥」被升格成有门（假阳）：%s %s" % (_gli, _eli))
        return 1
    # ③-c 盲区侧：无标准配置 ∧ CI 面没取全 ⇒ None（不得塌缩成 False；这正是本轮从 `if not files: False` 救回来的形状）
    _gbl, _ebl, _ubl = qg_classify({"lint_gate": []}, {}, "nothing relevant", ci_complete=False)
    if _gbl["lint_gate"] is not None or not _ubl:
        print("SELFTEST-FAIL: 无候选 + CI 未取全却判成「无门」：%s %s" % (_gbl, _ubl))
        return 1
    _g4, _, _u4 = qg_classify(qg_tree_candidates([]), {}, "")
    if any(bool(v) for v in _g4.values()) or _u4:
        print("SELFTEST-FAIL: 零输入升格成质量门（违反「零输入不得记 PASS」）：%s" % _g4)
        return 1
    _g95 = globals()
    # ③-d 变异腿（证明 ③ 的正例不是被别的腿喂绿的）：摘掉"自写门禁"路由 ⇒ 同一个输入必须回 False
    _orig_inv = dict(_g95["QG_INVOKED_TOKENS"])
    try:
        _g95["QG_INVOKED_TOKENS"] = {}
        _gmut, _emut, _umut = qg_classify({"secret_scan_gate": []}, {}, _own_ci)
    finally:
        _g95["QG_INVOKED_TOKENS"] = _orig_inv
    if _gmut["secret_scan_gate"] is not False:
        print("SELFTEST-FAIL: 摘掉自写门禁路由后正例仍判有门（这条腿没作用在被审对象上）：%s" % _gmut)
        return 1
    _gback, _, _ = qg_classify({"secret_scan_gate": []}, {}, _own_ci)
    if _gback["secret_scan_gate"] is not True:
        print("SELFTEST-FAIL: 还原路由后正例没回 True（变异腿与还原不可信）：%s" % _gback)
        return 1
    # 变异门反例（r75 首跑真面抓到，抓的是**我自己刚装的 jacoco**）：`<id>jacoco-check-line-coverage</id>`
    # 里的 "coverage" 曾被宽松分支 `coverage[^<]{0,20}<` 认成变异门 ⇒ 本仓 pom 一度被判 `mutation_gate=True`。
    # 现在必须：jacoco-only pom 判 False，真 stryker/pitest 配置判 True（两条方向相反，缺一即这条腿恒真）。
    _jac_pom = ("<artifactId>jacoco-maven-plugin</artifactId>"
                "<execution><id>jacoco-check-line-coverage</id><phase>verify</phase>"
                "<goals><goal>check</goal></goals><configuration><rules><rule><limits><limit>"
                "<counter>LINE</counter><minimum>0.35</minimum></limit></limits></rule></rules>"
                "</configuration></execution>")
    if qg_classify({"mutation_gate": ["server/pom.xml"]}, {"server/pom.xml": _jac_pom}, "")[0]["mutation_gate"]:
        print("SELFTEST-FAIL: jacoco 的 coverage/check 被认成变异门（本仓 pom 亲自中招那条没修住）")
        return 1
    _stryker = ("module.exports = { mutate: 'src/**/*.ts', thresholds: { break: 80 } };")
    if not qg_classify({"mutation_gate": ["stryker.conf.js"]}, {"stryker.conf.js": _stryker}, "")[0]["mutation_gate"]:
        print("SELFTEST-FAIL: 真 stryker thresholds.break 配置没判出变异门（收紧时砍掉了真能力）")
        return 1
    _orig_cov = _g95["QG_THRESHOLD_SHAPE"]["coverage_gate"]
    try:
        _g95["QG_THRESHOLD_SHAPE"]["coverage_gate"] = re.compile(r"(?!)")
        if qg_classify({"coverage_gate": ["server/pom.xml"]}, {"server/pom.xml": _q_pom}, "")[0]["coverage_gate"]:
            print("SELFTEST-FAIL: 摘掉阈值正则后仍判 coverage_gate ⇒ 该类没在被判的形状上")
            return 1
    finally:
        _g95["QG_THRESHOLD_SHAPE"]["coverage_gate"] = _orig_cov
    _asked75 = []
    _orig_ls75, _orig_blob75 = _g95["git_ls_tree"], _g95["git_blob"]
    try:
        _g95["git_ls_tree"] = lambda rev="HEAD": (_asked75.append(("ls", rev)),
                                                  ["server/pom.xml", ".eslintrc.json",
                                                   ".github/workflows/ci.yml"])[1]
        _g95["git_blob"] = lambda p, rev="HEAD": (_asked75.append(("blob", p, rev)),
                                                  _q_pom if p.endswith("pom.xml")
                                                  else ("name: CI\njobs:\n  guard:\n    name: 同步守卫\n"
                                                        "      - name: 密钥零入库扫描（判据与本地电池同源）\n"
                                                        "        run: python _test/secret_leak_check.py\n"
                                                        if "workflows" in p else ""))[1]
        _s75 = self_quality_gates()
        if _s75["face"] != "HEAD" or _s75["classes"].get("coverage_gate") is not True:
            print("SELFTEST-FAIL: self 侧质量门没走同址尺（face=%s %s）" % (_s75["face"], _s75["classes"]))
            return 1
        # 口径翻转（r78，随证据改判，不是"把尺调松到能过"）：r75 这条腿当年把"本尺只认标准工具文件名"
        # 固化成断言（自写门**应当**判 False），于是 `secret_scan_gate` 实际测的是"有没有用 gitleaks 这类名牌货"，
        # 而不是这一类宣称的"能不能让构建失败"。本仓 CI 每一步真跑着 `_test/tracked_secret_scan.py`（rc≠0 就红），
        # 判 False 是把行为存在的门报成缺口 ⇒ 与 r75「有配置≠有门」同族、方向相反的另一侧（行为有、尺看不见）。
        # 现在两侧同法：合成 CI 里的 `run: python _test/secret_leak_check.py` 必须认出，且证据点名那一行。
        if _s75["classes"].get("secret_scan_gate") is not True:
            print("SELFTEST-FAIL: 自写密钥守卫（CI 真调用）仍判无门 ⇒ 尺只认名牌货：%s" % _s75["classes"])
            return 1
        if "secret_leak_check.py" not in (_s75["evidence"].get("secret_scan_gate") or ""):
            print("SELFTEST-FAIL: secret_scan_gate 判了 True 却没点名那条调用行（证据不可追溯）：%s"
                  % _s75["evidence"].get("secret_scan_gate"))
            return 1
        if not any("密钥" in s for s in _s75.get("ci_steps_homegrown") or []):
            print("SELFTEST-FAIL: 自写门的名册没带出（天花板没说出来＝下一轮会把它读成「我方无门」）：%s"
                  % _s75.get("ci_steps_homegrown"))
            return 1
        if _s75.get("ci_step_count", 0) < 1:
            print("SELFTEST-FAIL: CI 步骤数为 0 ⇒ 正文根本没读到：%s" % _s75.get("ci_face"))
            return 1
        if ("ls", "HEAD") not in _asked75 or ("blob", ".github/workflows/ci.yml", "HEAD") not in _asked75:
            print("SELFTEST-FAIL: self 侧未从 git HEAD 取清单/CI 正文（接线是假的）：%s" % _asked75[:4])
            return 1
    finally:
        _g95["git_ls_tree"], _g95["git_blob"] = _orig_ls75, _orig_blob75
    # ---- A9（r82 新增，静态接线腿）：`classify_drift` 的**每一个**调用点都必须按四档解包 ----
    # 立此腿的一手：r79-D 把返回从 3 值加到 4 值，9 处调用点改了 8 处，**唯独生产路径 main() 那一处漏了**
    # ⇒ `--selftest` 全绿而真面每次跑到收口就 `ValueError: too many values to unpack`（本轮实测 rc=1，
    #   采数全部印完才崩，漂移一条都没落进台账）。这是 R238「用单测掩盖接线错误」的又一形态：
    #   签名变更的爆炸半径只在**没人跑的那条路**上显形。数一下有几个 `=` 是结构判定，不靠人记得改了几处。
    _src_self = Path(__file__).read_text(encoding="utf-8", errors="replace")
    _call_sites = re.findall(r"^(\s*)([A-Za-z_,\s]*?)=\s*classify_drift\(", _src_self, re.M)
    if len(_call_sites) < 2:
        print("SELFTEST-FAIL: A9 没找到 ≥2 处 classify_drift 解包赋值 ⇒ 正则失效或调用点被改写，"
              "这条腿会恒真：%r" % (_call_sites,))
        return 1
    _bad_arity = [(lhs.strip(), len([x for x in lhs.split(",") if x.strip()]))
                  for _ind, lhs in _call_sites
                  if len([x for x in lhs.split(",") if x.strip()]) != 4]
    if _bad_arity:
        print("SELFTEST-FAIL: A9 有调用点不按四档解包（签名演进时漏改的那一处就是真面会崩的那一处）："
              "%r ｜ 已扫 %d 处调用点" % (_bad_arity, len(_call_sites)))
        return 1
    print("SELFTEST-PASS: 合成快照 4 处改动（stars·pushed_at·caps·docs）全部抓到、全等对照零误报（"
          f"{len(got)} 条）；分档正确（实质 {len(sub)} / 抖动 {len(noise)}）且纯抖动场景零实质；"
          "分母证明正确（1 有效 / 2 盲区点名，健康仓不误踢）；"
          "r30 盲区点名三侧正确（有证据→点名、无证据→空、已看见→不重复）；"
          "r31 离线四分类各判对 + 训练语境不冒充离线壳 + 摘掉归因正则即翻判（变异体）+ 零输入判 none；"
          f"r70 vector_memory 匹配器 {len(_must_red)} 条假阳全拒 + {len(_must_green)} 条真阳全收；"
          "r71 self 行取数面 = git HEAD（未入库件结构性进不了人口，零人口不判绿）；"
          "r73 流式/端到端通道：四类归因 + 4 条真实冒充反例 + 变异体 + 通道不带 caps 键；"
          "r74 同址尺：docs/agent/changelog(根级)/bench/CI性能步 五类各有相反用例 + 长度不冒充好文档 + "
          "「极致性能」与★数行都不冒充性能数字 + 零输入不升格 + 两条变异腿翻判 + self 侧接线用注入读数自证；"
          "r75 质量门：**有配置≠有门**（.coveragerc 无 fail_under 判否 / eslint 无 CI 执行位判否）＋ "
          "正文取不到记 unverified 不塌缩 False ＋ 阈值正则变异体翻判 ＋ self 侧走 HEAD 面接线自证 ＋ 零输入不升格；"
          "r76 同址尺的同一洞另一半：**整棵 tree 没取到时树派生类降到未验**（不是 False），文本派生类不受牵连，"
          "有/无/未验 三档分开计数，摘掉树派生类名单即翻判（变异体证明这条腿作用在被判对象上）；"
          "r77 台账自伤：**基线缺仓只进「补录」档不进「实质」档**（把「我上轮瞎了」报成「对手动了」"
          "会支使人做一件不存在的动作），且**降级采集改道 .partial、完整采集才覆写权威台账**"
          "（13/16 与 16/16 两侧都验）；"
          "r78 口径翻转：**自写门禁（无标准配置、CI 执行行真调用）必须认出且点名那一行**，"
          "另一侧反例＝CI 里只有步骤名/注释提「无密钥」而执行行是 java -jar ⇒ 必须判无（防升格）；"
          "摘掉该路由正例即回 False（变异腿）、还原即回 True")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--offline-audit", action="store_true",
                    help="跑第二条离线观测通道（16 仓 × 2 次 API，较慢；判据本体由 --selftest 常驻守着）")
    ap.add_argument("--cap-channel", action="store_true",
                    help="跑流式/端到端的第二观测通道（r73；同样 16 仓 × 2 次 API，只作复核与下限揭示，不改 caps）")
    ap.add_argument("--doc-perf", action="store_true",
                    help="跑 r74 同址尺：文档维/性能维，peers 与 self 用同一套规则（16 仓 × 2 次 API，较慢）")
    ap.add_argument("--quality-gates", action="store_true",
                    help="跑 r75 质量门同址尺：五类「能不能让构建失败」，peers 与 self 同一套规则（API 调用较多）")
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
    if args.doc_perf:
        # 同一套规则跑两侧：peers 走 tree+README（GitHub API），self 走 git HEAD 的 ls-tree+blob。
        # 目的就是把 r73 报告里「self=docs 9/9 vs peers=api_spec 1/16」那种**不同源对照**换成同址读数。
        audit = doc_perf_audit(cur)
        self_dp = self_doc_perf()
        run["doc_perf_channel"] = {"peers": audit, "self": self_dp,
                                   "rule": "两侧同规则；不参与 caps；两路皆空记 unverified"}
        unv = sorted(k for k, v in audit.items() if v.get("unverified"))
        print("  同址尺（文档维/性能维；peers 与 self 同一套规则，不改 caps）：")
        for title, keys in (("文档", DOC_CLASSES), ("性能", PERF_CLASSES)):
            for c in keys:
                n_has, n_no, n_unv, n_den, members, unv_members = doc_perf_counts(audit, c)
                sv = self_dp.get(c)
                mark = "✅有" if sv is True else ("❌无" if sv is False else "⚠️未验")
                print(f"    [{title}] {c:<18} peers 有={n_has}/{n_den} 无={n_no} 未验={n_unv} "
                      f"self(HEAD)={mark}  例：{'、'.join(members[:3]) or '—'}")
                if n_unv:
                    print(f"      ⚠️ 该类不得写成「{n_no} 仓无 {c}」——下列仓的取数面未验"
                          f"（多为整棵 tree 没取到，r76）：{'、'.join(unv_members[:4])}")
        print(f"    self 面：face={self_dp['face']} paths={self_dp['self_paths']} "
              f"README={self_dp['readme_chars']}字符 classes={self_dp['classes']}")
        for c in DOC_CLASSES + PERF_CLASSES:
            if self_dp.get(c):
                print(f"      ▶ self 证据 [{c}] {self_dp['evidence'].get(c, '')[:80]}")
        if unv:
            print(f"  ⚠️ 同址尺分母不全（{len(unv)} 仓两路皆空：{'、'.join(unv)}）"
                  f"⇒ 不得据「peers 全零」下否定结论")
    if args.quality_gates:
        qg = quality_gate_audit(cur)
        qg_self = self_quality_gates()
        run["quality_gate_channel"] = {"peers": qg, "self": qg_self,
                                       "rule": "阈值型须有失败形状、执行型须配置∧CI；不参与 caps；取不到记 unverified"}
        print("  质量门同址尺（五类「能不能让构建失败」；不改 caps）：")
        for c in QG_CLASSES:
            members = sorted(k for k, v in qg.items() if (v.get("classes") or {}).get(c) is True)
            unv = sorted(k for k, v in qg.items() if (v.get("classes") or {}).get(c) is None)
            sv = qg_self["classes"].get(c)
            print(f"    {c:<17} peers 有门={len(members)}/{len(qg)} 未验={len(unv)} "
                  f"self={'✅有' if sv is True else ('❌无' if sv is False else '⚠️未验')}"
                  f"  例：{'、'.join(members[:3]) or '—'}")
            if unv:
                print(f"      ⚠️ 该类不得写成「{len(unv)} 仓无门」——它们是**取数面未验**：{'、'.join(unv[:4])}")
        print(f"    self 面：face={qg_self['face']} CI 正文取数={qg_self.get('ci_face')} "
              f"步骤数={qg_self.get('ci_step_count')}（候选={ {k: v[0] if v else '—' for k, v in qg_self['candidates'].items()} }）")
        print("    天花板（本尺只认标准工具文件名，自写判据形态的门**结构性看不见**，故下列步骤名单独列出、"
              "不参与两侧对照）：")
        for s in (qg_self.get("ci_steps_homegrown") or [])[:8]:
            print(f"      ▷ self 自写门：{s}")
        for c, e in (qg_self.get("evidence") or {}).items():
            print(f"      ▶ self 证据 [{c}] {str(e)[:92]}")
        if qg_self.get("unverified") or qg_self.get("partial_errors"):
            print(f"    ⚠️ self 侧未验项：{qg_self.get('unverified')} {qg_self.get('partial_errors')[:80]}")
    hist = (hist + [run])[-6:]
    drift = diff_snap(prev_repos, cur)
    # 降级采集不得覆写权威台账（r77 一手：02:53 那次 3 仓 EOF 仍把残缺快照写进基线，
    # 下一次于是报出 5 处"实质漂移"，全是 None -> 值 —— 是我上轮瞎了，不是对手动了）
    snap_target = pick_snapshot_path(path, len(cur), len(PEERS))

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"generated_by": "_test/benchmark_metrics.py",
               "peers_expected": len(PEERS), "runs": hist}
    tmp = snap_target.with_suffix(".json.tmp")
    # write_bytes 而非 write_text：文本模式在 Windows 会把 \n 翻成 \r\n，
    # 台账一旦带 CRLF，"逐字节对账/SHA256"类主张在别人 clone 上就复算不出来（eol_parity 实测抓到过一次）
    tmp.write_bytes(json.dumps(payload, ensure_ascii=False, indent=1).encode("utf-8"))
    os.replace(tmp, snap_target)

    print(f"采集: {len(cur)}/{len(PEERS)} 仓 | 快照 {snap_target.relative_to(ROOT).as_posix()}"
          + ("｜⚠️ 降级：权威台账未覆写，基线仍取上一次完整采集" if snap_target != path else "")
          + f" | 历史 {len(hist)} 次")
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
            # r82 修：`classify_drift` 自 r79-D 起返回**四档**（实质/抖动/补录/取数失败），
            # 而生产路径这一处仍按三值解包 ⇒ 每次真跑到这里就 `ValueError: too many values to unpack`，
            # 采数全部印完才崩（rc=1），漂移一条都没落进台账。9 处调用点里 8 处已跟上新签名，
            # 唯独这条**唯一会被真面走到**的那处漏了 —— `--selftest` 全绿而真面崩，正是 R238 说的
            # 「用单测掩盖接线错误」。下面 A9 那条静态腿就是为堵这一族：调用点解包数!=4 当场红。
            sub, noise, roster, blind = classify_drift(drift)
            print(f"漂移: {len(drift)} 处 = 实质 {len(sub)} 处（可行动）+ 抖动 {len(noise)} 处"
                  f"（★ 单点差值含倒退，不作趋势证据）+ 补录 {len(roster)} 处"
                  f"（基线上轮没数到 ⇒ 是我补齐了覆盖，不是对手变化）+ 取数失败 {len(blind)} 处"
                  f"（本轮树没取到 ⇒ 这把尺瞎，不得读成对手退化）"
                  f"｜与上一次快照逐字段比对，禁止沿用旧数字")
            for repo, k, o, n in sub:
                print(f"  ▶ 实质 {repo} {k}: {o} -> {n}")
            for repo, k, o, n in noise:
                print(f"    抖动 {repo} {k}: {o} -> {n}")
            for repo, k, o, n in roster:
                print(f"      ▷ 补录 {repo} {k}: {o} -> {n}")
            for repo, k, o, n in blind:
                print(f"      ✗ 取数失败 {repo} {k}: {o} -> {n}")
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
