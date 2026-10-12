# -*- coding: utf-8 -*-
"""psych_kb_build.py — 心理学知识库 -> 产品数据件构建器 + 一致性判据（r113）

交付物/心理学知识库/*.md 的条目卡（README §3 固定行式）是唯一真相源；
本脚本把它编译成 src/data/psych-kb.js（window.__XINYU_PSYCH_KB__，经典脚本零构建）。
产品侧 chat-agent.js 在回复提示词里注入相关条目，回答带〔依据:编号·级〕标注。

为什么做成判据而不是普通脚本：条目卡是**多生产者**文件（AI 入库员 + 人工更正都会写），
行式一旦漂移（字段名被改、全角冒号变半角、ID 重复），最坏结局是产品静默注入空库或脏数据
=> 所以解析层 fail-fast：缺字段 / ID 重复 / 0 条 / 输入目录缺失，一律 BUILD-FAIL，禁静默。

E 级（未查证）条目不入产品件 —— 库规 README §2：E 级禁作事实依据。重建时排除并计数。
--check：重建并与磁盘现有产物逐字节比对（不带时间戳，输出确定性的原因）。
用法：python _test/psych_kb_build.py [--check]
退出码：0=PASS 1=FAIL 2=输入面缺失
"""
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
KB_DIR = ROOT / "交付物" / "心理学知识库"
OUT = ROOT / "src" / "data" / "psych-kb.js"
KB_VERSION = "v1.3"          # 与 README 版本行同步；规范本体改动时人工 bump
BUILT_TAG = "r123"
LEVELS = ("A", "B", "C", "D", "E")
SHIP_LEVELS = ("A", "B", "C", "D")   # E 级不入产品件
CONTENT_MAX = 320            # 注入用内容截断（句界截断，超长条目保前几句即可撑起 60-120 字回复）
MAX_RELATED = 4              # 每条目自动提取的情绪关联上限

ENTRY_RE = re.compile(r"^### 条目 (PSY-[A-Z]+-\d{3})｜(.+?)\s*$")
FIELD_RE = re.compile(r"^[-\s]*(可信度|一句话|内容)：(.*)$")
LEVEL_RE = re.compile(r"^[A-E]$")

# 情绪关联自动提取（builder 侧做，运行时零分词成本）：条目文本里出现哪类情绪词就挂哪类。
# 这是**数据驱动的路由**，不是人工标注 —— 条目更新后重建即刷新。
EMO_KW = {
    "joy": ("愉悦", "开心", "快乐", "高兴", "joy"),
    "sadness": ("低落", "悲伤", "难过", "sadness", "忧郁"),
    "anger": ("愤怒", "烦躁", "生气", "anger", "恼怒"),
    "fear": ("恐惧", "焦虑", "害怕", "fear", "紧张"),
    "calm": ("平静", "calm", "放松"),
    "love": ("心动", "想念", "love", "爱意"),
}


def fail(msg):
    print("PSYCH-KB-BUILD-FAIL: " + msg)
    sys.exit(1)


def trim_sentence(text, limit):
    """句界截断：在 limit 内找最后一个句号/问号/叹号，找不到整段保留首 limit 字。"""
    if len(text) <= limit:
        return text
    cut = text[:limit]
    best = max(cut.rfind(p) for p in ("。", "！", "？", "；"))
    return cut[: best + 1] if best >= int(limit * 0.4) else cut


def parse_entries():
    if not KB_DIR.is_dir():
        fail("知识库目录缺失 " + str(KB_DIR))
    files = sorted(p for p in KB_DIR.glob("*.md") if p.name not in ("README.md", "索引.md"))
    if not files:
        fail("篇章文件为空：只有规范与索引，没有任何条目源")
    entries, seen = [], {}
    counts = {k: 0 for k in LEVELS}
    for path in files:
        cur = None
        for raw in path.read_text("utf-8", errors="replace").splitlines():
            line = raw.rstrip()
            m = ENTRY_RE.match(line)
            if m:
                if cur:
                    entries.append(cur)
                eid, title = m.group(1), m.group(2)
                if eid in seen:
                    fail("条目 ID 重复：%s（%s 与 %s）" % (eid, seen[eid], path.name))
                seen[eid] = path.name
                cur = {"id": eid, "title": title, "level": "", "summary": "", "content": "", "rel": []}
                continue
            if not cur:
                continue
            f = FIELD_RE.match(line)
            if not f:
                continue
            key, val = f.group(1), f.group(2).strip()
            if key == "可信度":
                if cur["level"]:
                    fail("条目 %s 可信度字段重复" % cur["id"])
                cur["level"] = val
            elif key == "一句话" and not cur["summary"]:
                cur["summary"] = val
            elif key == "内容" and not cur["content"]:
                cur["content"] = val
        if cur:
            entries.append(cur)
    if not entries:
        fail("0 条条目被解析：条目卡行式与 README §3 模板漂移了？（先修行式，禁降判据）")
    for e in entries:
        if e["level"] not in LEVELS:
            fail("条目 %s 可信度字段缺失或非法：%r" % (e["id"], e["level"]))
        if not e["summary"] or not e["content"]:
            fail("条目 %s 缺一句话或内容字段" % e["id"])
        counts[e["level"]] += 1
        e["content"] = trim_sentence(e["content"], CONTENT_MAX)
        hay = e["title"] + "，" + e["summary"] + e["content"]
        e["rel"] = [emo for emo, kws in EMO_KW.items()
                    if any(k in hay for k in kws)][:MAX_RELATED]
    return entries, counts, len(files)


def build_text(entries, counts, n_files):
    ship = [e for e in entries if e["level"] in SHIP_LEVELS]
    payload = {
        "version": KB_VERSION,
        "built": BUILT_TAG,
        "counts": {k: counts[k] for k in SHIP_LEVELS},
        "excludedE": counts["E"],
        "sourceFiles": n_files,
        "entries": [{"id": e["id"], "title": e["title"], "level": e["level"],
                     "summary": e["summary"], "content": e["content"], "rel": e["rel"]}
                    for e in ship],
    }
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    header = (
        "/* 心屿 · 心理学知识库数据件（r113 起由 _test/psych_kb_build.py 生成，禁手改）\n"
        " * 源 = 交付物/心理学知识库 条目卡（唯一真相源）；重建：python _test/psych_kb_build.py\n"
        " * E 级（未查证）条目不入本件：库规 README 禁其作事实依据。 */\n"
        "window.__XINYU_PSYCH_KB__ = " + body + ";\n"
    )
    return header


def main():
    entries, counts, n_files = parse_entries()
    text = build_text(entries, counts, n_files)
    if "--check" in sys.argv:
        if not OUT.exists():
            fail("产物缺失 " + str(OUT))
        if OUT.read_text("utf-8") != text:
            fail("产物与知识库源不一致：条目卡更新后未重建（跑一次不带 --check 的本脚本）")
        print("PSYCH-KB-CHECK-PASS: 产物与源一致（%d 条）" % len(entries))
        return
    OUT.write_text(text, encoding="utf-8", newline="\n")
    size = OUT.stat().st_size
    ship_n = sum(counts[k] for k in SHIP_LEVELS)
    print("PSYCH-KB-BUILD-PASS: 入库 %d 条（A:%d B:%d C:%d D:%d，E 排除 %d），"
          "源文件 %d 个 -> %s（%s bytes）"
          % (ship_n, counts["A"], counts["B"], counts["C"], counts["D"], counts["E"],
             n_files, OUT.relative_to(ROOT), format(size, ",")))
    if ship_n == 0:
        fail("全部条目均为 E 级，产品件将是空库：先升级条目再重建")


if __name__ == "__main__":
    main()
