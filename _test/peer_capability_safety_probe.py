# -*- coding: utf-8 -*-
"""对标 r38 探针：产品**安全与评测**能力矩阵 + README 可信度件（16 仓 + self，双通道）。

为什么是这一面：r35–r37 已扫完账面（★/停更/workflow/文档件）、行尾确定性、发布可得性与工程治理，
台账连续两轮**零实质漂移**。而 iCAN 评分口径里 创新 30 / 体验 10 看的是"产品到底做了什么、
评委能不能快速信"，这两件事账面指标量不到：
  类 1 crisis    危机干预（心理健康陪伴类产品的安全底线）
  类 2 evalset   可复跑的评测集/标注数据（"效果好不好"有没有证据）
  类 3 guardrail 内容安全 / 越狱与注入防护 / 敏感词
  类 4 可信度件   README 里的 CI 徽章、演示媒体、在线体验链接

双通道与纪律（对应 consulting-analysis M5⑦⑨）：
  · 通道 A = 默认分支递归文件树（**truncated 必查**，被截断的仓其"零命中"不作数）
  · 通道 B = README 正文关键词（与 A 互不依赖，给 A 的零结论做第二通道，也补 A 看不见的"内容级"证据）
  · 每条命中都落**样本路径/原文片段**，不写裸计数；未取到记 NA(原因)，禁止与 0 混同。
用法：python _test/peer_capability_safety_probe.py [--json out.json] [--self-only]
退出码：0=两通道全程取到 1=存在 NA（如实点名）2=gh 未鉴权
"""
import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from benchmark_metrics import PEERS, ROOT   # 分母唯一真相源 = 台账池

# 文件名/路径类判据（刻意收紧，避免 JS 的 Array.filter、Java 的 dependency injection 之类误报）
CLS = {
    "crisis": re.compile(r"(crisis|suicide|self.?harm|hotline|emergency|求助|危机)", re.I),
    "evalset": re.compile(r"(eval|benchmark|dataset|testset|test_set|golden|corpus|annotat|label)", re.I),
    "guardrail": re.compile(r"(moderation|guardrail|jailbreak|prompt.?injection|nsfw|sensitive.?word"
                            r"|block.?list|blacklist|red.?team|toxic|safety)", re.I),
}
DATA_EXT = re.compile(r"\.(json|jsonl|csv|tsv|parquet|xlsx|txt|md)$", re.I)
# ⚠️ 判据/探针/CI 脚本本身**不算产品能力**：r35 同类坑（"检测密钥的判据"是全仓最像密钥的文件）
# 的本轮变体 —— 我写的安全探针文件名里就带 safety/moderation/jailbreak，不排除会给自己凭空加能力位。
# 此排除对 peers 同样生效（对称，M5⑧）。
TOOLISH = re.compile(r"(probe|_check|check_|_scan|scan_|verify|guard_|test_)", re.I)


def is_tool(path):
    return bool(TOOLISH.search(Path(path).name))

# README 正文类判据（通道 B）
DOC_CLS = {
    "crisis": re.compile(r"(crisis|suicide|self.?harm|hotline|危机干预|求助热线)", re.I),
    "evalset": re.compile(r"(evaluation|benchmark|test set|dataset|评测集|评测)", re.I),
    "guardrail": re.compile(r"(moderation|guardrail|jailbreak|prompt injection|content policy|安全策略|敏感词)", re.I),
}
TRUST = {
    "badge": re.compile(r"img\.shields\.io|/badge\.svg|github/actions/workflows/badge", re.I),
    "media": re.compile(r"\.(gif|mp4|webm)(\)|\"|'|$)", re.I),
    "live": re.compile(r"(https?://(?!github\.com|raw\.|api\.|img\.|shield|objects\.)[^\s)\]\"']+)", re.I),
}


def api(path, token):
    req = urllib.request.Request("https://api.github.com/" + path,
                                 headers={"User-Agent": "xinyu-cap-probe",
                                          "Accept": "application/vnd.github+json"})
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            return json.loads(r.read().decode("utf-8", "replace")), ""
    except Exception as e:
        code = getattr(e, "code", type(e).__name__)
        return None, "http=%s" % code


def probe_repo(slug, token):
    """通道 A：文件树；返回 (classes -> [样本], truncated, err)"""
    data, err = api("repos/%s/git/trees/HEAD?recursive=1" % slug, token)
    if data is None:
        return {}, False, err
    trunc = bool(data.get("truncated"))
    paths = [t.get("path", "") for t in data.get("tree", []) if t.get("type") == "blob"]
    out = {}
    for cls, rx in CLS.items():
        hits = []
        for p in paths:
            if is_tool(p):
                continue          # 判据/探针自身不计能力（对 self 与 peers 同一条规则）
            if cls == "evalset":
                # 评测集要求"是数据文件且名字像评测物"，否则 evaluate.js / evaluator.py 会误报
                if DATA_EXT.search(p) and rx.search(Path(p).name):
                    hits.append(p)
            elif rx.search(p):
                hits.append(p)
        if hits:
            out[cls] = sorted(hits)[:3] + (["…共 %d 条" % len(hits)] if len(hits) > 3 else [])
    return out, trunc, ""


def probe_readme(slug, token):
    """通道 B：README 正文（与树通道独立）"""
    data, err = api("repos/%s/readme" % slug, token)
    if data is None:
        return {}, err
    try:
        txt = __import__("base64").b64decode(data.get("content") or "").decode("utf-8", "replace")
    except Exception as e:
        return {}, "decode:%s" % e
    out = {}
    for cls, rx in list(DOC_CLS.items()) + list(TRUST.items()):
        m = rx.findall(txt) if cls != "live" else rx.findall(txt)
        if m:
            sample = (m[0] if isinstance(m[0], str) else str(m[0]))[:60]
            out[cls] = "%d 处｜样本 %r" % (len(m), sample)
    return out, ""


def probe_self():
    """同一套判据跑本地权威源（工作树），保证 self 与 peers 同尺。"""
    out = {}
    skip = ("/.git/", "node_modules", ".codebuddy", "_shots", "server/target", "server/data",
            "\\node_modules", "\\.git\\")
    paths = []
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        r = str(p.relative_to(ROOT)).replace("\\", "/")
        if any(x.replace("/", "/") in r for x in
               ("/.git/", "node_modules/", ".codebuddy/", "_shots/", "target/", "server/data/")):
            continue
        paths.append(r)
    for cls, rx in CLS.items():
        hits = []
        for r in paths:
            if is_tool(r):
                continue
            if cls == "evalset":
                if DATA_EXT.search(r) and rx.search(Path(r).name):
                    hits.append(r)
            elif rx.search(r):
                hits.append(r)
        if hits:
            out[cls] = sorted(hits)[:3] + (["…共 %d 条" % len(hits)] if len(hits) > 3 else [])
    readme = (ROOT / "README.md")
    txt = readme.read_text("utf-8", errors="replace") if readme.exists() else ""
    dout = {}
    for cls, rx in list(DOC_CLS.items()) + list(TRUST.items()):
        m = rx.findall(txt)
        if m:
            dout[cls] = "%d 处｜样本 %r" % (len(m), str(m[0])[:60])
    return out, dout, False, ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="")
    ap.add_argument("--self-only", action="store_true")
    a = ap.parse_args()
    token = os.environ.get("GITHUB_TOKEN") or ""
    if not token:
        r = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True)
        token = r.stdout.strip()
    if not token:
        print("CAP-PROBE-ENV-ERROR: 无 GitHub token（gh auth token 失败）")
        return 2

    rows, na = {}, []
    targets = [] if a.self_only else [(p["repo"], p["tier"]) for p in PEERS]
    for slug, tier in targets:
        tree, trunc, err1 = probe_repo(slug, token)
        doc, err2 = probe_readme(slug, token)
        rows[slug] = {"tier": tier, "tree": tree, "readme": doc, "truncated": trunc,
                      "err": [e for e in (err1, err2) if e]}
        if err1 or err2:
            na.append("%s(%s)" % (slug, "+".join(x for x in (err1, err2) if x)))
        elif trunc:
            na.append("%s(树被截断⇒零命中不可信)" % slug)
        print("[%s] %-36s 树:%s%s | README:%s" % (tier, slug,
              ",".join(sorted(tree)) or ("none" if not err1 else "NA"),
              "｜截断" if trunc else "", ",".join(sorted(doc)) or ("none" if not err2 else "NA")))
    stree, sdoc, _, _ = probe_self()
    rows["__self__"] = {"tree": stree, "readme": sdoc}
    print("[self] %-36s 树:%s | README:%s" % ("心屿 SoulIsle",
          ",".join(sorted(stree)) or "none", ",".join(sorted(sdoc)) or "none"))
    print("-" * 120)
    n = len(rows) - 1
    for cls in ("crisis", "evalset", "guardrail"):
        c = sum(1 for k, v in rows.items() if k != "__self__" and cls in v["tree"])
        d = sum(1 for k, v in rows.items() if k != "__self__" and cls in v["readme"])
        both = sum(1 for k, v in rows.items() if k != "__self__" and cls in v["tree"] and cls in v["readme"])
        print("%-10s 树通道 %2d/%d ｜ README 通道 %2d/%d ｜ 两通道都命中 %2d" % (cls, c, n, d, n, both))
    for t in ("badge", "media", "live"):
        c = sum(1 for k, v in rows.items() if k != "__self__" and t in v["readme"])
        print("可信度件 %-8s %2d/%d" % (t, c, n))
    print("应测 %d 仓 ｜ NA/截断 %d ｜ self 树命中=%s ｜ self README=%s"
          % (n, len(na), sorted(stree), sorted(sdoc)))
    if na:
        print("  未验/截断项：" + "; ".join(na))
    if a.json:
        Path(a.json).write_bytes(json.dumps({"repos": rows, "na": na, "denominator": n},
                                            ensure_ascii=False, indent=1).encode("utf-8"))
        print("落盘 %s" % a.json)
    print("CAP-PROBE-%s" % ("PARTIAL" if na else "COMPLETE"))
    return 1 if na else 0


if __name__ == "__main__":
    sys.exit(main())
