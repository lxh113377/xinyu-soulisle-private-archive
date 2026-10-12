# -*- coding: utf-8 -*-
"""对标 r52 探针：**记忆/上下文管理的制度化程度，以及记忆到模型的"引用边"**（16 仓 + self，三通道）。

为什么是这一面：✅ `grep -icE "多轮记忆|上下文窗口|HISTORY_MAX|记忆回灌|滚动摘要" 交付物/对标分析报告-*.md`
= 十三份全 0。而首两份（09-24 / 09-24-v2）在总览表里把「记忆系统」写成 **✅ localStorage + 服务端双表** ——
那是**存在性**结论（有表、能落库），**没有一格量过"落库的记忆有没有回到发给模型的那条 messages 里"**。
本探针就是去补这一格；self 侧的行为回执另见 `_test/memory_recall_check.py`。

三通道（各自独立，取不到一律 NA(原因)，禁与 0 混同）：
  A 结构面 = git tree 按**路径段词元**分类（memory / summary / 上下文窗口 / 检索）——
     不用裸子串：`storage` 含 `rag`、`GPU memory`、React `createContext` 都会把裸子串通道喂成假命中
  B 声明面 = README 正文**锚定词组**（long-term memory / memory system / worldbook / \\bRAG\\b / 世界书…）
  C 引用边 = 「装配 messages 的文件有没有 import 记忆模块」的**正向回执**。三态，且带样本数：
     yes(真取到引用) / none-in-sample(抽了 N 个装配件都没见到) / NA(没取到)。
     ⚠️ 只有 yes 是证据；后两态**不得**写成"该仓没做记忆回灌"（抽样为空 ≠ 不存在）。
用法：python _test/peer_memory_probe.py [--json out.json] [--self-only] [--selftest]
退出码：0=分母齐、无 NA 且台账完好 1=存在 NA／恒等式或台账完好性失败／selftest 未过 2=无 GitHub token（环境）
"""
import argparse
import base64
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from benchmark_metrics import PEERS, ROOT, mem_backend_hit      # noqa: E402
from gh_cred import gh_credential                               # noqa: E402

NOISE = re.compile(r"(^|/)(node_modules|\.venv|venv|dist|build|target|vendor|\.git|_shots|"
                   r"web_raw|video_raw|__pycache__|\.next|miniprogram_npm"
                   # 测试/夹具目录**不算产品能力**（r53 实测自打）：本仓新增判据
                   # `_test/context_budget_check.py` 的词元是 context+budget，正好命中 ctxwin，
                   # 于是"产品有上下文窗口管理器"被我自己写的一个**测试脚本**充上了。
                   # 排除对 self 与 peers 同尺生效（peers 的 tests/ 里同样有这类命名）。
                   r"|_?tests?|__tests__|spec|e2e|cypress|playwright)/", re.I)
# 装配件：文件名词元里含 prompt/messages/chain/agent/llm/chat/completion 的**代码**文件
ASSEMBLY = re.compile(r"\.(py|ts|tsx|js|jsx|mjs|java|go|rs)$", re.I)
IMPORTISH = re.compile(r"(from|import|require|use)\s|@Resource|@Autowired", re.I)

# 段词元里出现即算"记忆件"（camel / kebab / snake 都切；`long`+`term` 组合单独判）
MEM_TOKENS = {"memory", "memories", "episodic", "recall", "worldbook", "lorebook",
              "characterbook", "memstore"}
SUM_TOKENS_PREFIX = ("summar",)                       # summarize / summary / summarizer
CTX_QUALIFIERS = {"manager", "window", "budget", "compress", "compression", "builder",
                  "truncat", "truncated", "truncation", "orchestrator", "store"}
RETR_TOKENS = {"retrieval", "rerank", "hyde", "chunking"}
# r127：**产品名记忆后端**也属检索轴（一手：Open-LLM-VTuber 的 mem0_llm.py / letta_agent.py 在原规则下
# 整仓 retrieval 轴为空）。判据**整条复用** caps 尺的 `mem_backend_hit`（词元表 + 限定词规则同一份，
# 禁第二份副本；r127-S11 的假阳侧教训：品牌词撞仓名时路径不含信息）。
# 反向词：`memory` 段但同时含这些词的是**泄漏/OOM 测试件**，不是记忆能力
ANTI = {"leak", "leaks", "oom", "malloc", "gc", "heap"}


def seg_tokens(seg):
    """把路径段切成词元**集合**：按 - _ . 空格切，再按 camelCase 边界切。"""
    seg = re.sub(r"\.[A-Za-z0-9]+$", "", seg)
    parts = re.split(r"[-_.\s]+|(?<=[a-z0-9])(?=[A-Z])", seg)
    return {p.lower() for p in parts if p}


def is_mem_path(path):
    for seg in path.split("/"):
        grp = seg_tokens(seg)
        if (grp & MEM_TOKENS or ("long" in grp and "term" in grp)) and not (grp & ANTI):
            return True
    return False


def _segs(path):
    return [seg_tokens(s) for s in path.split("/")]


def _hit_summar(segs):
    return any(t.startswith(SUM_TOKENS_PREFIX) for g in segs for t in g)


def _hit_ctx(segs):
    """上下文**窗口/预算**管理。⚠️ 单看 `context` 一词没有判别力：React 的
    `src/context/AppContext.tsx` 是全栈最常见的目录命名，必须再有第二枚限定词元才算，
    否则整池子都会被误判成"做了上下文管理"（selftest 反例②盯着这条）。"""
    for g in segs:
        if "context" in g and (g & CTX_QUALIFIERS):
            return True
    if any(g == {"context"} for g in segs[:-1]) and (segs[-1] & CTX_QUALIFIERS):
        return True
    return False


def _hit_retr(segs, path=""):
    for g in segs:
        if "rag" in g or (g & RETR_TOKENS):
            return True
        if "embedding" in g and (g & {"store", "index", "db", "search"}):
            return True
    # 品牌后端这一路**整条委托**给 caps 尺的同一个判据（r127-S11）：词元表同一份、
    # "品牌词元必须与集成限定词共现"这条规则也同一份，两把尺不会各说各话。
    return mem_backend_hit(path)


def classify_tree(paths):
    """通道 A：结构面。按结构单位（文件）计数，每类只记一次存在与否 + 前 3 个样例路径。
    段级判定（`src/rag/index.ts` 的证据在**目录段**上，只看文件名会整类漏掉）。"""
    out = {"memory": [], "summary": [], "ctxwin": [], "retrieval": [], "assembly": []}
    for p in paths:
        if NOISE.search("/" + p):
            continue
        segs = _segs(p)
        if len(out["memory"]) < 3 and is_mem_path(p):
            out["memory"].append(p)
        if len(out["summary"]) < 3 and _hit_summar(segs):
            out["summary"].append(p)
        if len(out["ctxwin"]) < 3 and _hit_ctx(segs):
            out["ctxwin"].append(p)
        if len(out["retrieval"]) < 3 and _hit_retr(segs, p):
            out["retrieval"].append(p)
        if len(out["assembly"]) < 6 and ASSEMBLY.search(p) \
                and (set().union(*segs) & {"prompt", "prompts", "messages", "chain", "agent",
                                           "llm", "chat", "completion", "generate", "generation"}):
            out["assembly"].append(p)
    return out


README_PAT = [
    ("long_term_memory", re.compile(r"long[\s-]?term\s+memor", re.I)),
    ("memory_system", re.compile(r"\bmemor\w*\s+(?:system|store|bank|module|architecture)\b", re.I)),
    ("conversation_memory", re.compile(r"\b(?:conversation|chat|dialogue|session|user|personal)\s+memor\w*\b", re.I)),
    ("worldbook", re.compile(r"\b(?:world|lore|character)[\s-]?book\b", re.I)),
    ("rag", re.compile(r"\bRAG\b")),                      # 大写词边界：storage / average 不算
    ("summarize_ctx", re.compile(r"summar(?:iz|is)\w*\s+(?:the\s+)?(?:conversation|history|context|chat)", re.I)),
    ("ctx_window", re.compile(r"context\s+(?:window|management|compression)", re.I)),
    ("cn", re.compile(r"长期记忆|记忆系统|世界书|上下文(窗口|压缩|管理|裁剪)")),
]


def classify_readme(text):
    if not text:
        return {}
    return {k: True for k, rx in README_PAT if rx.search(text)}


def _needles(mem_paths):
    """记忆件的**引用形状**集合。⚠️ 首版只用「去掉扩展名的原始段名」当 needle，
    于是本仓 `src/js/memory-store.js` 的 needle 是 `memory-store`，而调用点写的是
    `window.MemoryStore.record(...)` ⇒ 归一化前两者永不相等，**self 被判成 none-in-sample（假阴）**。
    现按三种真实形状各生成一枚：连写形（MemoryStore）、原段名、以及命中的词元本身。"""
    nd = set()
    for p in mem_paths:
        for seg in [x for x in p.split("/") if x]:
            tk = seg_tokens(seg)
            hit = tk & MEM_TOKENS or ({"long", "term"} <= tk)
            if not hit:
                continue
            raw = re.sub(r"\.[A-Za-z0-9]+$", "", seg).lower()
            nd.add(raw)
            nd.add(re.sub(r"[^a-z0-9]", "", raw))
            for t in tk:
                if t in MEM_TOKENS or t in ("long", "term"):
                    nd.add(t)
    return {x for x in nd if len(x) >= 4}


def find_recall_edge(mem_paths, asm_blobs):
    """通道 C：只看**正向**回执。两类形状都算引用边：
      import  = 引入语句行里出现记忆件形状（ESM / Python / Java import 皆适用）
      member  = `<形状>.` 的成员访问（浏览器全局对象式调用，如 `memorystore.record(`，
                本仓就是这一形——没有 import 语句）
    返回 (state, matched, sample_n)；state ∈ {yes, none-in-sample, NA}。
    ⚠️ 只有 yes 是证据；none-in-sample 仅说明"抽到的 n 个装配件里没有"，**不构成**"该仓没做回灌"。"""
    if not asm_blobs:
        return "NA", "", 0
    nd = _needles(mem_paths)
    if not nd:
        return "NA", "", len(asm_blobs)
    for name, body in asm_blobs.items():
        low = (body or "").lower()
        imp_lines = [x for x in low.splitlines() if IMPORTISH.search(x)]
        for n in nd:
            if any(n in ln for ln in imp_lines):
                return "yes(import)", name + " → " + n, len(asm_blobs)
        flat = re.sub(r"[^a-z0-9.]", "", low)
        for n in nd:
            if (n + ".") in flat:
                return "yes(member)", name + " → " + n, len(asm_blobs)
    return "none-in-sample", "", len(asm_blobs)


def api(path, token):
    req = urllib.request.Request("https://api.github.com/" + path,
                                 headers={"User-Agent": "xinyu-memory-probe",
                                          "Accept": "application/vnd.github+json"})
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            return json.loads(r.read().decode("utf-8", "replace")), ""
    except Exception as e:
        return None, "http=%s" % getattr(e, "code", type(e).__name__)


def fetch_blobs(slug, paths, token, limit=6):
    out = {}
    for p in paths[:limit]:
        b, _e = api("repos/%s/contents/%s" % (slug, p), token)
        if b is not None and b.get("content"):
            try:
                out[p] = base64.b64decode(b["content"]).decode("utf-8", "replace")[:180_000]
            except Exception:
                pass
    return out


def probe_repo(slug, token):
    tree, err = api("repos/%s/git/trees/HEAD?recursive=1" % slug, token)
    if tree is None:
        return {}, False, {}, ("NA", "", 0), err or "tree-fail"
    paths = [x.get("path", "") for x in tree.get("tree", []) if x.get("type") == "blob"]
    t = classify_tree(paths)
    asm = fetch_blobs(slug, t["assembly"], token)
    edge = find_recall_edge(t["memory"], asm) if t["memory"] else ("NA", "", len(asm))
    rd, e2 = api("repos/%s/readme" % slug, token)
    doc = {}
    if rd is not None:
        try:
            doc = classify_readme(base64.b64decode(rd.get("content") or "").decode("utf-8", "replace"))
        except Exception:
            e2 = "readme-decode"
    return t, bool(tree.get("truncated")), doc, edge, "+".join(x for x in (err, e2) if x)


def self_snapshot():
    paths = []
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        r = str(p.relative_to(ROOT)).replace("\\", "/")
        if NOISE.search("/" + r):
            continue
        paths.append(r)
    t = classify_tree(paths)
    asm = {}
    for p in t["assembly"]:
        try:
            asm[p] = (ROOT / p).read_text("utf-8", errors="replace")[:180_000]
        except Exception:
            pass
    edge = find_recall_edge(t["memory"], asm) if t["memory"] else ("NA", "", len(asm))
    doc = {}
    for name in ("README.md", "README.en.md"):
        f = ROOT / name
        if f.is_file():
            doc.update(classify_readme(f.read_text("utf-8", errors="replace")))
    return t, doc, edge, len(paths)


def verdict(t, doc, edge):
    a = sum(1 for k in ("memory", "summary", "ctxwin", "retrieval") if t.get(k))
    obs = "记忆/上下文件 %d/4 类" % a
    if not doc:
        obs += "｜README 无记忆声明"
    else:
        obs += "｜声明:" + ",".join(sorted(doc))
    obs += "｜引用边 %s(n=%d)" % (edge[0], edge[2])
    return obs


def selftest():
    ok, fail = 0, []
    # 正例①：四类结构证据齐 + 装配件 import 记忆件 ⇒ 引用边必须判 yes
    t1 = classify_tree(["src/store/memory.ts", "src/lib/summarizer.py",
                        "src/agent/context_manager.ts", "src/rag/index.ts"])
    e1 = find_recall_edge(t1["memory"], {"src/agent/prompt.ts": "import { recall } from '@/store/memory'"})
    if t1["memory"] and t1["summary"] and t1["ctxwin"] and t1["retrieval"] \
            and e1[0].startswith("yes"):
        ok += 1
    else:
        fail.append("正例①四类证据/引用边未全中：%s %s" % (t1, e1))
    # 正例②（r52 self 假阴的形状）：浏览器**全局对象成员访问**没有 import 语句，
    # 而本仓 ChatAgent 调 window.MemoryStore.record 就是这一形，必须判 yes(member)
    e1b = find_recall_edge(["src/js/memory-store.js"],
                           {"src/js/chat-agent.js": "window.MemoryStore.record({emotion:1})"})
    if e1b[0] == "yes(member)":
        ok += 1
    else:
        fail.append("正例②全局对象引用边未识别：%s" % (e1b,))
    # 反例⓪：装配件只是在**注释里**提了一句 memory（无引入、无成员访问）⇒ 不得算引用边
    e1c = find_recall_edge(["src/js/memory-store.js"],
                           {"src/js/a.js": "// memory is cheap here\nconst x = 1"})
    if e1c[0] == "none-in-sample":
        ok += 1
    else:
        fail.append("反例⓪注释提及被当成引用边：%s" % (e1c,))
    # 反例①：`storage` 里含 `rag` 子串，不得算检索件（首版就是用裸子串，会被这条当场打回）
    t2 = classify_tree(["src/browser/storage.js", "lib/average/score.py", "paragraph/split.ts"])
    if not t2["retrieval"]:
        ok += 1
    else:
        fail.append("反例①裸子串 rag 未隔离：%s" % t2["retrieval"])
    # r127：产品名记忆后端（mem0/letta…）必须进检索轴——与 caps 尺同一份词元表；
    #       而"长得像"的反例（palette 含 letta 子串、letter 含 lett）必须仍不命中。
    t8 = classify_tree(["src/agent/agents/mem0_llm.py", "src/agent/agents/letta_agent.py"])
    if t8["retrieval"]:
        ok += 1
    else:
        fail.append("r127 产品名后端未进检索轴（一手：Open-LLM-VTuber 整仓 retrieval 为空）：%s"
                    % t8["retrieval"])
    t9 = classify_tree(["src/ui/palette.js", "src/letter_draft.py",
                        # r127-S11 一手假阳（letta-ai/letta-code 的真实路径）：品牌名撞仓名，
                        # 只查词元会整仓白送一条检索轴；这些路径**没有**任何集成限定词。
                        "bin/letta.js", "assets/letta-code-demo.gif",
                        ".github/workflows/letta.yml"])
    if not t9["retrieval"]:
        ok += 1
    else:
        fail.append("r127 反例误伤（palette/letter/品牌自有件被判成检索件）：%s" % t9["retrieval"])
    # 反例②：React 的 createContext 目录不等于"上下文窗口管理"
    t3 = classify_tree(["src/context/AppContext.tsx", "src/context/theme.tsx"])
    if not t3["ctxwin"]:
        ok += 1
    else:
        fail.append("反例②React context 误判为窗口管理：%s" % t3["ctxwin"])
    # 反例③：`memory-leak.test.ts` 是泄漏测试件，不是记忆能力
    t4 = classify_tree(["test/memory-leak.spec.ts", "src/gc/heap_memory_check.py"])
    if not t4["memory"]:
        ok += 1
    else:
        fail.append("反例③泄漏件未排除：%s" % t4["memory"])
    # 反例④：README 里 "uses a lot of GPU memory" 不得算声明了记忆系统；而 "long-term memory" 必须算
    d1 = classify_readme("It uses a lot of GPU memory and storage")
    d2 = classify_readme("### Features\n- long-term memory across sessions")
    if not d1 and d2.get("long_term_memory"):
        ok += 1
    else:
        fail.append("反例④文档锚定失真：%s / %s" % (d1, d2))
    # 边界：有记忆件但**一个装配件都没取到** ⇒ 必须是 NA，不得写成 none-in-sample（更不得写成"没做"）
    e2 = find_recall_edge(["src/store/memory.ts"], {})
    if e2[0] == "NA":
        ok += 1
    else:
        fail.append("边界 零样本未落 NA：%s" % (e2,))
    # 对偶：抽样非空但确无引用 ⇒ none-in-sample，且 verdict 行必须带上样本数（分母可复核）
    e3 = find_recall_edge(["src/store/memory.ts"], {"src/a/prompt.ts": "export const x = 1"})
    v = verdict(t1, {}, e3)
    if e3[0] == "none-in-sample" and "n=1" in v:
        ok += 1
    else:
        fail.append("对偶 none-in-sample 形状或样本数缺失：%s ｜ %s" % (e3, v))
    # 反例⑤（r53 实测自打）：判据/测试目录里的文件**不得**充当产品能力。
    # 本仓新增 `_test/context_budget_check.py` 的词元正好是 context+budget，第一版把它算成
    # "该仓有上下文窗口管理器" ⇒ self 从 1/4 虚高到 2/4，且这个"2"里根本没有产品代码。
    t6 = classify_tree(["_test/context_budget_check.py", "tests/memory_fixture.ts",
                        "src/store/memory.ts"])
    if not t6["ctxwin"] and not t6["summary"] and t6["memory"] == ["src/store/memory.ts"]:
        ok += 1
    else:
        fail.append("反例⑤ 测试目录被当成产品能力：%s ｜ %s" % (t6["ctxwin"], t6["memory"]))
    # 对偶（防"一删了之"）：产品目录里的同名文件必须照常命中，排除面不能顺手把真能力也排除掉
    t7 = classify_tree(["src/context/context_budget.ts", "src/lib/summary.ts"])
    if t7["ctxwin"] and t7["summary"]:
        ok += 1
    else:
        fail.append("对偶 产品目录被误排除：%s ｜ %s" % (t7["ctxwin"], t7["summary"]))
    # ── r102：字段级 NA 入账规则（ledger_age 豁免到期条件的可测半边）──
    rows_fix = [
        {"repo": "a/na", "edge": ["NA", "", 6]},
        {"repo": "b/none", "edge": ["none-in-sample", "", 6]},
        {"repo": "c/yes", "edge": ["yes(import)", "x", 2]},
        {"repo": "d/missing", "edge": []},
        {"repo": "e/nokey"},
    ]
    if field_na(rows_fix) == ["a/na"]:
        ok += 1
    else:
        fail.append("field_na 只认 NA 哨兵：%r" % field_na(rows_fix))
    if field_na([{"repo": "z", "edge": ["none-in-sample", "", 6]}]) == []:
        ok += 1
    else:
        fail.append("field_na 反例 none-in-sample 被当成 NA（取到了不许记未验）")
    # ── r127-S11：NA 台账的计数单位=仓（一仓同时命中仓级+字段级只算一次）──
    rows_c = [{"repo": "a/b"}, {"repo": "c/d"}, {"repo": "e/f"}]
    ent, cs = na_census(rows_c, [{"repo": "a/b", "why": "http=TimeoutError"}],
                        ["a/b", "c/d"])
    if (len(ent) == 2 and ent[0]["repo"] == "a/b" and "TimeoutError" in ent[0]["why"]
            and "edge-NA" in ent[0]["why"] and cs["raw"] == 3 and cs["distinct"] == 2):
        ok += 1
    else:
        fail.append("r127-S11 同仓双命中未合并（一次超时被计成两个样本）：%r %r" % (ent, cs))
    # 反例：合并不得顺手把"没发生过的失败"合掉——两仓各一次失败仍是两条
    ent2, cs2 = na_census(rows_c, [], ["a/b", "c/d"])
    if len(ent2) == 2 and cs2["raw"] == 2 and cs2["distinct"] == 2:
        ok += 1
    else:
        fail.append("r127-S11 反例 两仓各一次 NA 被合并成 %d 条" % len(ent2))
    # 台账完好性：幽灵仓（名单里有、rows 里没有）与重名仓必须被**点名**，不许静默去重
    _ent3, cs3 = na_census(rows_c, [{"repo": "ghost/x", "why": "empty-tree"}], [])
    if cs3["phantom"] == ["ghost/x"]:
        ok += 1
    else:
        fail.append("r127-S11 幽灵仓未被点名：%r ⇒ usable 会从 rows 侧数出比 blind+usable==total 不成立的值" % cs3)
    _ent4, cs4 = na_census([{"repo": "a/b"}, {"repo": "a/b"}, {"repo": "c/d"}], [], ["a/b"])
    if cs4["dup_rows"] == ["a/b"]:
        ok += 1
    else:
        fail.append("r127-S11 重名仓（分母本身不可信）未被点名：%r" % cs4)
    for x in fail:
        print("  SELFTEST-FAIL " + x)
    # 声明分支数=在册腿数（13 → 19：+2 条 r127 检索词元腿、+4 条 r127-S11 NA 计数腿）。
    # 这里**故意保留手抄常量**：它的作用是"某条腿被编辑吞掉时立刻红"，
    # 若改成 len(实际执行腿) 就成了永真式（与本轮抓掉的 `n-x+x==n` 同族）。
    expected = 19
    print("MEMPEER-SELFTEST: %d/%d%s" % (ok, expected,
          "" if ok + len(fail) == expected else "  ⚠️ 分支数 %d≠%d" % (ok + len(fail), expected)))
    return 0 if ok == expected and ok + len(fail) == expected else 1


def field_na(rows):
    """字段级 NA 名单：`edge[0] == "NA"` 的仓（引用边没取到 ⇒ 该轴未验，不当反证）。

    r102 抽成纯函数：ledger_age 的 `NA_DIVERGE_WAIVED["peer-memory"]` 豁免到期条件
    要求把它计入声明位，而入账规则必须可被 selftest 喂合成行——
    `none-in-sample` / `yes(...)` 都不算 NA（那是取到了、结论是"没见到"）。
    """
    return [r["repo"] for r in rows if tuple(r.get("edge") or ("",))[0] == "NA"]


def na_census(rows, repo_na, edge_na_repos):
    """NA 台账：计数单位是**仓**，不是记录条数（r127-S11 一手）。

    同一仓可同时命中两类失败——树取空（仓级）时它的引用边必然也是 NA（字段级），
    旧写法把两条都塞进 `na` ⇒ 一次网络抖动吃掉 1 个样本却报成 blind +2、usable −2
    （实测：letta-ai/letta-code `http=TimeoutError` 那轮 12→10）。
    合并规则：仓级原因优先保留，字段级并入同一 why；名单里出现 rows 之外的仓 = 幽灵，
    rows 里出现重名仓 = 分母本身不可信，两者都要**报出来**而不是静默去重。
    """
    order = [r["repo"] for r in rows]
    dup = sorted({s for s in order if order.count(s) > 1})
    merged, why = [], {}
    for x in repo_na:
        s = x["repo"]
        if s not in why:
            why[s] = x.get("why") or "empty-tree"
            merged.append(s)
    for s in edge_na_repos:
        if s in why:
            why[s] += "+edge-NA(引用边未取到)"
        else:
            why[s] = "edge-NA(引用边未取到)"
            merged.append(s)
    entries = [{"repo": s, "why": why[s]} for s in merged]
    phantom = [s for s in merged if s not in order]
    return entries, {"raw": len(repo_na) + len(edge_na_repos), "distinct": len(merged),
                     "dup_rows": dup, "phantom": phantom}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="")
    ap.add_argument("--self-only", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest())
    token = gh_credential()
    if not token and not a.self_only:
        print("MEMPEER-UNVERIFIED: 无 GitHub token ⇒ 无法取 peers（不判 0，判环境未验）")
        sys.exit(2)
    rows, repo_na = [], []
    st, sdoc, se, sn = self_snapshot()
    rows.append({"repo": "__self__", "tier": "-", **{"tree": st}, "readme": sdoc, "edge": list(se)})
    if not a.self_only:
        for p in PEERS:
            t, trunc, doc, edge, err = probe_repo(p["repo"], token)
            if not t:
                repo_na.append({"repo": p["repo"], "why": err or "empty-tree"})
            elif trunc:
                repo_na.append({"repo": p["repo"], "why": "tree-truncated(结构面只见到部分)"})
            rows.append({"repo": p["repo"], "tier": p["tier"], "tree": t,
                         "readme": doc, "edge": list(edge), "err": err})
    n = len(rows)
    # r102：字段级 NA（`repos[*].edge[0] == "NA"`，引用边没取到）**计入声明位**。
    # 这是 ledger_age 的 `NA_DIVERGE_WAIVED["peer-memory"]` 豁免的到期条件之一：
    # 旧写法只把仓库级失败（空树/截断）写进 na，字段级失败只留在 edge 里 ⇒ 顶层声明
    # blind=0 而件内 5 处 `"NA(` 分叉（r101 一手实测：MASCOT / Mental-health-Chatbot /
    # MER-Factory / succhia / MoodChat 五仓）。语义上引用边取不到 = **该轴未验**，
    # 不是"该仓没做记忆回灌"的反证（见 ceiling_note）⇒ 计入 na/blind 才是如实声明。
    # r127-S11：两路 NA 合并**按仓去重**（一仓树取空时引用边必然也 NA ⇒ 旧法双计，
    # 一次超时把 usable 12→10 报成"少两个样本"，实际只少一个）。
    edge_na = field_na(rows)
    na, cstats = na_census(rows, repo_na, edge_na)
    na_set = {e["repo"] for e in na}
    # usable 从 rows 侧**独立**数出来，不由 blind 反推 —— 反推会让下面这条恒等式变成
    # `n-x+x==n` 的永真式（旧写法正是永真式，一条永远绿的尺；r127-S11 实测抓出）。
    usable = len([r for r in rows if r["repo"] not in na_set])
    ident_ok = (usable + len(na) == n)
    intact_ok = not cstats["phantom"] and not cstats["dup_rows"]
    print("== r52 记忆与上下文管理面对标（16 仓 + self）==")
    for r in rows:
        print("%-36s %s" % (r["repo"], verdict(r["tree"], r["readme"], tuple(r["edge"]))))
    print("应测 %d ｜ NA 仓 %d（去重前记录 %d 条）｜ usable %d＋NA %d==%d：%s ｜ 台账完好（无幽灵/无重名仓）：%s"
          % (n, len(na), cstats["raw"], usable, len(na), n,
             "OK" if ident_ok else "FAIL",
             "OK" if intact_ok else "FAIL(幽灵 %s／重名仓 %s)" % (cstats["phantom"], cstats["dup_rows"])))
    if na:
        for x in na:
            print("  NA %s: %s" % (x["repo"], x["why"]))
    if edge_na:
        print("  （其中 %d 仓是**字段级** NA：引用边没取到 ⇒ 该轴未验，不当反证；"
              "与仓级同仓的已合并，不重复计数）" % len(edge_na))
    if a.json:
        # 必须 write_bytes：Windows 下 write_text 把 "\n" 译成 "\r\n"，而 eol_parity 判据要求
        # 工作树字节 == git blob 字节 ⇒ 一份"跑一次就把自己写脏"的产物等于给下轮留假红。
        # （同族：本仓 07 卷 4KB 判据当年也是栽在 write_text 的 CRLF 上。r52 实测被抓。）
        Path(a.json).write_bytes(json.dumps(
            {"repos": rows, "na": na, "denominator": n, "blind": len(na), "usable": usable,
             "na_records_before_dedupe": cstats["raw"],
             "na_integrity": "OK" if intact_ok else "FAIL",
             "na_phantom_repos": cstats["phantom"], "na_dup_rows": cstats["dup_rows"],
             "self_paths_scanned": sn,
             "ceiling_note": "引用边通道是**正向回执**：none-in-sample / NA 两态都不构成"
                             "「该仓没做记忆回灌」的结论；且 peers 无行为注入条件，"
                             "本面只比「有没有制度化」，不比「做得好不好」。"
                             "r102 起 NA（含字段级 edge-NA）如实计入声明位 ⇒ "
                             "顶层 blind 数与件内 NA 哨兵数不再分叉。"
                             "r127-S11 起 blind 的计数单位=**仓**（同仓的仓级+字段级 NA 合并成一条）。",
             "edge_na_repos": edge_na},
            ensure_ascii=False, indent=1).encode("utf-8"))
        print("快照 → " + a.json)
    sys.exit(0 if (not na and intact_ok and ident_ok) else 1)


if __name__ == "__main__":
    main()
