# -*- coding: utf-8 -*-
"""wit_quotes_build.py — 表达语料库 -> 产品数据件构建器 + 一致性判据（r117）

交付物/表达语料库/*.md 的条目卡（README §3 固定行式）是唯一真相源；
本脚本把它编译成 src/data/wit-quotes.js（window.__XINYU_WIT_QUOTES__，经典脚本零构建）。
产品侧 chat-agent.js 每轮按情绪+话题匹配候选注入系统提示词，模型按引用规则自行判断引用。

为什么做成判据而不是普通脚本：条目卡是**多生产者**文件（4 名研究员 + 审读员 + 人工更正都会写），
行式一旦漂移（字段名被改、全角冒号变半角、ID 重复、情绪/场景枚举非法、条目放错篇章），
最坏结局是产品静默注入空库或脏数据 => 解析层 fail-fast：缺字段 / ID 重复 / 0 条 / 枚举非法 /
篇章错位 / 输入目录缺失，一律 BUILD-FAIL，禁静默。

E 级（未核）条目不入产品件 —— 库规 README §2。重建时排除并计数。
--check：重建并与磁盘现有产物逐字节比对（固定版本串，输出确定性）。
用法：python _test/wit_quotes_build.py [--check] [--dir <源目录>] [--out <产物路径>]
退出码：0=PASS 1=FAIL 2=输入面缺失
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
CORPUS_DIR = ROOT / "交付物" / "表达语料库"
OUT = ROOT / "src" / "data" / "wit-quotes.js"
WQ_VERSION = "v1.0"
BUILT_TAG = "r117"
LEVELS = ("A", "B", "C", "D", "E")
SHIP_LEVELS = ("A", "B", "C", "D")   # E 级不入产品件
EMOTIONS = ("joy", "sadness", "anger", "fear", "calm", "love")
SCENES = ("共情", "安抚", "鼓励", "解释", "开解", "庆祝", "自我接纳", "陪伴")
# 文件名前缀数字 -> 篇码（防条目放错篇章）
CHAPTERS = {"01": "CL", "02": "MS", "03": "NET", "04": "PH"}
CAT_NAMES = {"CL": "文言与古诗词", "MS": "名家名句", "NET": "网络热句", "PH": "哲学思辨"}
QUOTE_MAX = 260     # 句面上限（超长逼拆条，防注入超体量预算）
USAGE_MAX = 120     # 用法截断（注入展示用；行式源不截）
REQUIRED = ("可信度", "出处", "适用情绪", "适用场景", "用法", "句面", "风险注记", "入库")

ENTRY_RE = re.compile(r"^### 条目 (QTE-([A-Z]+)-\d{3})｜(.+?)\s*$")
FIELD_RE = re.compile(r"^[-\s]*(可信度|出处|适用情绪|适用场景|用法|句面|风险注记|入库)：(.*)$")
LEVEL_RE = re.compile(r"^[A-E]$")


def fail(msg):
    print("WIT-QUOTES-BUILD-FAIL: " + msg)
    sys.exit(1)


def trim_sentence(text, limit):
    """句界截断：在 limit 内找最后一个句号/问号/叹号/分号，找不到即整段保留（防半个字）。"""
    if len(text) <= limit:
        return text
    cut = text[:limit]
    best = max(cut.rfind(p) for p in ("。", "！", "？", "；"))
    return cut[: best + 1] if best >= int(limit * 0.4) else cut


def parse_entries(corpus_dir):
    if not corpus_dir.is_dir():
        print("WIT-QUOTES-BUILD-INPUT-MISSING: 语料库目录缺失 " + str(corpus_dir))
        sys.exit(2)
    files = sorted(p for p in corpus_dir.glob("*.md")
                   if p.name not in ("README.md", "索引.md") and re.match(r"^\d{2}-", p.name))
    if not files:
        fail("篇章文件为空：目录里只有规范/索引，没有任何 01-*.md 形态的条目源")
    entries, seen = [], {}
    counts = {k: 0 for k in LEVELS}
    for path in files:
        chapter = CHAPTERS.get(path.name[:2])
        if chapter is None:
            fail("篇章文件名前缀非法（须 01/02/03/04）：" + path.name)
        cur = None
        for raw in path.read_text("utf-8", errors="replace").splitlines():
            line = raw.rstrip()
            m = ENTRY_RE.match(line)
            if m:
                if cur:
                    entries.append(cur)
                eid, cat, title = m.group(1), m.group(2), m.group(3)
                if cat not in CAT_NAMES:
                    fail("篇码非法：%s（%s）" % (cat, path.name))
                if cat != chapter:
                    fail("条目 %s 篇码 %s 与文件名 %s 不符（防放错篇章）" % (eid, cat, path.name))
                if eid in seen:
                    fail("条目 ID 重复：%s（%s 与 %s）" % (eid, seen[eid], path.name))
                seen[eid] = path.name
                cur = {"id": eid, "cat": cat, "title": title, "fields": {}, "src_file": path.name}
                continue
            if not cur:
                continue
            f = FIELD_RE.match(line)
            if not f:
                continue
            key, val = f.group(1), f.group(2).strip()
            if key in cur["fields"]:
                fail("条目 %s 字段重复：%s" % (cur["id"], key))
            cur["fields"][key] = val
        if cur:
            entries.append(cur)
    if not entries:
        fail("全库 0 条")
    shipped = []
    for e in entries:
        missing = [k for k in REQUIRED if k not in e["fields"]]
        if missing:
            fail("条目 %s 缺字段：%s（%s）" % (e["id"], ",".join(missing), e["src_file"]))
        level = e["fields"]["可信度"]
        if not LEVEL_RE.match(level):
            fail("条目 %s 可信度非法：%s（须 A-E 单字）" % (e["id"], level))
        quote = e["fields"]["句面"]
        if not quote:
            fail("条目 %s 句面为空" % e["id"])
        if len(quote) > QUOTE_MAX:
            fail("条目 %s 句面超长 %d 字（上限 %d，请拆条）" % (e["id"], len(quote), QUOTE_MAX))
        emo = [x.strip() for x in e["fields"]["适用情绪"].split("、") if x.strip()]
        if not emo:
            fail("条目 %s 适用情绪为空" % e["id"])
        if "通用" in emo:
            if len(emo) > 1:
                fail("条目 %s 「通用」不得与具体情绪并列（%s）" % (e["id"], "、".join(emo)))
            emo = ["all"]
        else:
            for x in emo:
                if x not in EMOTIONS:
                    fail("条目 %s 情绪枚举非法：%s（须 joy/sadness/anger/fear/calm/love 或 通用）" % (e["id"], x))
        scene = [x.strip() for x in e["fields"]["适用场景"].split("、") if x.strip()]
        if not scene:
            fail("条目 %s 适用场景为空" % e["id"])
        for x in scene:
            if x not in SCENES:
                fail("条目 %s 场景枚举非法：%s（须 %s）" % (e["id"], x, "/".join(SCENES)))
        counts[level] += 1
        if level not in SHIP_LEVELS:
            continue   # E 级不入产品件
        shipped.append({
            "id": e["id"], "cat": e["cat"], "title": e["title"], "level": level,
            "quote": quote, "src": e["fields"]["出处"],
            "emo": emo, "scene": scene,
            "usage": trim_sentence(e["fields"]["用法"], USAGE_MAX),
            "risk": e["fields"]["风险注记"],
        })
    shipped.sort(key=lambda x: x["id"])
    by_cat = {c: 0 for c in CAT_NAMES}
    for e in shipped:
        by_cat[e["cat"]] += 1
    data = {
        "version": WQ_VERSION,
        "built": BUILT_TAG,
        "counts": {"total": len(shipped), "by_level": counts, "by_cat": by_cat,
                   "excludedE": counts["E"]},
        "entries": shipped,
    }
    return data


def render(data):
    # 紧凑序列化（无缩进）：数据件是给浏览器加载的产物，103 条约省 20KB 下载量；
    # 人读场景走 --check 报错行与源文件，不依赖缩进。确定性不受影响（同数据同输出）。
    return ("/* 心屿 · 表达语料库数据件（自动生成，勿手改 —— 源=交付物/表达语料库/*.md，"
            "构建器=_test/wit_quotes_build.py）*/\n"
            "window.__XINYU_WIT_QUOTES__=" +
            json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + ";\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="重建并与磁盘产物逐字节比对")
    ap.add_argument("--dir", type=Path, default=CORPUS_DIR)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    data = parse_entries(args.dir)
    text = render(data)
    if args.check:
        if not args.out.exists():
            fail("产物不存在（先不带 --check 跑一次重建）：" + str(args.out))
        old = args.out.read_text("utf-8")
        if old == text:
            print("WIT-QUOTES-BUILD-PASS %d 条（A%d/B%d/C%d/D%d，E 排除 %d）--check 与磁盘一致" % (
                data["counts"]["total"], data["counts"]["by_level"]["A"],
                data["counts"]["by_level"]["B"], data["counts"]["by_level"]["C"],
                data["counts"]["by_level"]["D"], data["counts"]["excludedE"]))
            return 0
        fail("--check 不一致：产物与重建结果不同（条目源被改过且未重建？）")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8", newline="\n")
    print("WIT-QUOTES-BUILD-PASS 已重建 %s：%d 条（A%d/B%d/C%d/D%d，E 排除 %d）" % (
        str(args.out).replace(str(ROOT) + "\\", "").replace(str(ROOT) + "/", ""),
        data["counts"]["total"], data["counts"]["by_level"]["A"],
        data["counts"]["by_level"]["B"], data["counts"]["by_level"]["C"],
        data["counts"]["by_level"]["D"], data["counts"]["excludedE"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())