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
退出码：0=分母齐且无 NA 1=存在 NA 或 selftest 未过 2=无 GitHub token（环境）
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
from benchmark_metrics import PEERS, ROOT

NOISE = re.compile(r"(^|/)(node_modules|\.venv|venv|dist|build|target|vendor|\.git|_shots|"
                   r"web_raw|video_raw|__pycache__|\.next|miniprogram_npm)/", re.I)
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


def _hit_retr(segs):
    for g in segs:
        if "rag" in g or (g & RETR_TOKENS):
            return True
        if "embedding" in g and (g & {"store", "index", "db", "search"}):
            return True
    return False


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
        if len(out["retrieval"]) < 3 and _hit_retr(segs):
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
    for x in fail:
        print("  SELFTEST-FAIL " + x)
    expected = 9
    print("MEMPEER-SELFTEST: %d/%d%s" % (ok, expected,
          "" if ok + len(fail) == expected else "  ⚠️ 分支数 %d≠%d" % (ok + len(fail), expected)))
    return 0 if ok == expected and ok + len(fail) == expected else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="")
    ap.add_argument("--self-only", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest())
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
    if not token and not a.self_only:
        print("MEMPEER-UNVERIFIED: 无 GitHub token ⇒ 无法取 peers（不判 0，判环境未验）")
        sys.exit(2)
    rows, na = [], []
    st, sdoc, se, sn = self_snapshot()
    rows.append({"repo": "__self__", "tier": "-", **{"tree": st}, "readme": sdoc, "edge": list(se)})
    if not a.self_only:
        for p in PEERS:
            t, trunc, doc, edge, err = probe_repo(p["repo"], token)
            if not t:
                na.append({"repo": p["repo"], "why": err or "empty-tree"})
            elif trunc:
                na.append({"repo": p["repo"], "why": "tree-truncated(结构面只见到部分)"})
            rows.append({"repo": p["repo"], "tier": p["tier"], "tree": t,
                         "readme": doc, "edge": list(edge), "err": err})
    n = len(rows)
    print("== r52 记忆与上下文管理面对标（16 仓 + self）==")
    for r in rows:
        print("%-36s %s" % (r["repo"], verdict(r["tree"], r["readme"], tuple(r["edge"]))))
    print("应测 %d ｜ NA/截断 %d ｜ 恒等式 usable+NA==total：%s"
          % (n, len(na), "OK" if n - len(na) + len(na) == n else "FAIL"))
    if na:
        for x in na:
            print("  NA %s: %s" % (x["repo"], x["why"]))
    if a.json:
        # 必须 write_bytes：Windows 下 write_text 把 "\n" 译成 "\r\n"，而 eol_parity 判据要求
        # 工作树字节 == git blob 字节 ⇒ 一份"跑一次就把自己写脏"的产物等于给下轮留假红。
        # （同族：本仓 07 卷 4KB 判据当年也是栽在 write_text 的 CRLF 上。r52 实测被抓。）
        Path(a.json).write_bytes(json.dumps(
            {"repos": rows, "na": na, "denominator": n, "blind": len(na), "usable": n - len(na),
             "self_paths_scanned": sn,
             "ceiling_note": "引用边通道是**正向回执**：none-in-sample / NA 两态都不构成"
                             "「该仓没做记忆回灌」的结论；且 peers 无行为注入条件，"
                             "本面只比「有没有制度化」，不比「做得好不好」。"},
            ensure_ascii=False, indent=1).encode("utf-8"))
        print("快照 → " + a.json)
    sys.exit(1 if na else 0)


if __name__ == "__main__":
    main()
