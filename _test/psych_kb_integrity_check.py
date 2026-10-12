# -*- coding: utf-8 -*-
"""psych_kb_integrity_check.py — 心理学知识库「引用关联 ⇄ 取证 ⇄ 索引」三面一致性判据（r129）

为什么单独一件而不再塞进 psych_kb_build.py：构建器只认 可信度/一句话/内容 三个字段（它要把卡
编译成产品数据件），而本件管的是**卡与卡、卡与索引之间的图关系**（悬空引用、孤岛、索引漂移、
来源缺失）。同一事实只许一处判：构建器不查这些，本件不查产物字节。

判什么（三条都按 README 的成文规范，不是自造要求）：
  ① 引用关联：卡内任何 `[[PSY-XX-NNN]]` 必须指向真存在的卡（悬空=红）；不得自指；每张卡至少要
     被一条关联指到或自己指出去（孤岛=红）——README §1 要求回答用 [[编号]] 引用、§4 要求注记关系，
     孤岛条目在注入时永远不会被顺藤摸到，等于白写。
  ② 证据溯源：每张非 E 级卡必须有 `- 来源：` 且至少一条来源子行（README §2 定级纪律第 2 条 + §7 红线
     「查不到来源只能 E 级」）。此前这条**只在人工核对轮里靠人眼过**，机器面为零 ⇒ 无来源卡能一路混进产品件。
  ③ 索引对账：`索引.md` 的「条目索引表」⇄ 卡集合双向差集为 0（缺行/多行=红），索引行的「可信度」列
     与卡内 可信度 一致、「篇章」列与卡实际所在文件一致、「一句话」列与卡内 `- 一句话：` **逐字一致**
     （r129 实测 110 行可全部逐字相等 ⇒ 由提示升为硬判据：人读索引会照抄这句，索引与卡不同文就是两处真相）。
     立此条的一手代价：第 4 轮 24 条（r123 落盘）在索引里挂了 3 轮无人登记，直到 r127 手工补登 ——
     「人工补登」这件事本身就是这个缺口存在过的证据。
提示面（不判红，只报读数）：D 级卡的「两方并陈」关键词命中率。语义级判断机器做不靠谱，
     硬做会把人写的正常句子判红（判据形状必须容得下真话），所以这一维保持人工轮次抽查 + 本件报数。

用法：python _test/psych_kb_integrity_check.py [--report|--selftest]
退出码：0=绿 1=红（含点名条目）2=取数面缺失/解析失效（不得读成「没有问题」）
"""
import re
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import psych_kb_build as kb  # noqa: E402  复用同一套取数面，禁另立一份「哪张卡算存在」的语法

KB_DIR = kb.KB_DIR
INDEX = KB_DIR / "索引.md"
CARD_ID_RE = re.compile(r"^### 条目 (PSY-[A-Z]+-\d{3})｜(.+?)\s*$")
LEVEL_RE = re.compile(r"^-\s*可信度：([A-E])\s*$")
REL_LINE_RE = re.compile(r"^-\s*关联：(.*)$")
SRC_LINE_RE = re.compile(r"^-\s*来源：(.*)$")
SRC_SUB_RE = re.compile(r"^\s+-\s+\[")
IN_RE = re.compile(r"^-\s*入库：(.+)$")
REF_RE = re.compile(r"\[\[(PSY-[A-Z]+-\d{3})\]\]")
INDEX_SEC_RE = re.compile(r"^##\s*二、条目索引表\s*$")
H2_RE = re.compile(r"^##\s")
INDEX_ROW_RE = re.compile(r"^\|\s*(PSY-[A-Z]+-\d{3})\s*\|([^|]*)\|([^|]*)\|([^|]*)\|")
# 表头实测（索引.md:29）：| 编号 | 标题 | 可信度 | 篇章 | 一句话 | ⇒ group2=标题 group3=级别 group4=篇章。
#   r129 首跑我把 group2 当级别，一次造出 196 条假红（「级别不一致：卡=B 索引=公开微表情数据集…」这种
#   「级别列里装着标题」的形状本身就是取数错位的样子）——按实测表头改回，未动任何数据。
CORRECTION_RE = re.compile(r"^-\s*更正：")

SPEC_FILES = ("README.md", "索引.md")
# D 级「两方并陈」的人工抽查提示用关键词（只报数，不判红）
DEBATE_KW = ("vs", "VS", "争议", "两方", "对立", "批评", "质疑", "异", "反", "未决", "分歧", "但")


class FaceMissing(Exception):
    """取数面本身取不到 —— 必须报 rc=2，绝不得静默读成「0 问题」。"""


def card_level(lines):
    for ln in lines:
        m = LEVEL_RE.match(ln)
        if m:
            return m.group(1)
    return ""


def load_cards(kb_dir=KB_DIR):
    """返回 (cards: {id: {...}}, face_problems: [str])。cards 含原文行，供三面检查复用。"""
    if not kb_dir.is_dir():
        raise FaceMissing("知识库目录缺失 " + str(kb_dir))
    files = sorted(p for p in kb_dir.glob("*.md") if p.name not in SPEC_FILES)
    if not files:
        raise FaceMissing("篇章文件为零（目录里只有规范与索引）⇒ 无取数面")
    cards, problems = {}, []
    for path in files:
        cur_id = None
        cur = None
        for raw in path.read_text("utf-8", errors="replace").splitlines():
            line = raw.rstrip()
            m = CARD_ID_RE.match(line)
            if m:
                if cur_id is not None:
                    cards[cur_id] = cur
                cur_id, cur = m.group(1), {"file": path.name, "title": m.group(2), "lines": []}
                continue
            if cur is not None:
                cur["lines"].append(line)
        if cur_id is not None:
            cards[cur_id] = cur
    if not cards:
        raise FaceMissing("未解析到任何条目卡（卡行式与 CARD_ID_RE 漂移？）")
    return cards, problems


def index_cells(line):
    """索引表行的**唯一取数口**（实测表头 索引.md:29 = 编号|标题|可信度|篇章|一句话）。

    load_index 与「一句话漂移」比对共用这一个函数：r129 同一次里我把列序读错两回
    （第一回把标题当级别 ⇒ 196 条假红；第二回把篇章当一句话 ⇒ 110 条全不一致的假读数），
    根因是同一张表写了两套解析。同表只许一套列序。
    行尾竖线在既有文件里不统一（r123 前的行带、第 4/5 轮追加的行不带），故按 split 段数取下标，
    段数不足 6（编号/标题/级别/篇章/一句话 + 首空段）即视为非条目行。
    """
    if not line.startswith("|"):
        return None
    parts = [p.strip() for p in line.split("|")]
    if len(parts) < 6:
        return None
    if not ID_ONLY_RE.match(parts[1]):
        return None
    return {"id": parts[1], "title": parts[2], "level": parts[3],
            "chapter": parts[4], "summary": parts[5]}


ID_ONLY_RE = re.compile(r"^PSY-[A-Z]+-\d{3}$")


def load_index(index_path=INDEX):
    """只取「## 二、条目索引表」小节内的表行 ⇒ 规划槽位表（未成卡的编号）不进分母。"""
    if not index_path.is_file():
        raise FaceMissing("索引缺失 " + str(index_path))
    rows = {}
    in_sec = False
    for raw in index_path.read_text("utf-8", errors="replace").splitlines():
        line = raw.rstrip()
        if INDEX_SEC_RE.match(line):
            in_sec = True
            continue
        if in_sec and H2_RE.match(line):
            break
        if not in_sec:
            continue
        c = index_cells(line)
        if c:
            rows[c["id"]] = {"level": c["level"], "chapter": c["chapter"], "summary": c["summary"]}
    if not rows:
        raise FaceMissing("索引「条目索引表」里一条编号都没抽到 ⇒ 表格形状变了，不得据此判绿")
    return rows


SUMMARY_RE = re.compile(r"^-\s*一句话：(.*)$")


def index_wording_drift(cards, rows):
    """索引「一句话」列与卡内 `- 一句话：` 不一致的条目 ⇒ run() 把它升成硬判据（r129）。

    r129 首查抓到 PSY-AP-002 索引写 CASME II 255 条而卡写 247 条 —— 这种数字漂移正是人读索引时会抄走的，
    所以它值得被看见；但先不判红：人工登记时索引侧常被缩写，直接判红会把合法缩写也打成红
    （门禁形状必须容得下真话）。读数用于判断「能不能升成硬判据」。
    """
    drift = []
    for cid, c in cards.items():
        card_sum = ""
        for ln in c["lines"]:
            s = SUMMARY_RE.match(ln)
            if s:
                card_sum = s.group(1).strip()
                break
        want = (rows.get(cid) or {}).get("summary") or ""
        if want and card_sum and want != card_sum:
            drift.append(cid)
    return sorted(drift)


def check_relations(cards):
    """① 引用关联：悬空 / 自指 / 孤岛（孤岛=既没指出去也没被指）。

    取数面按数据流划：只有 **活引用** 参与判定（一句话/内容/关联/待验证点/来源 等行）；
    `- 更正：` 行是历史留痕，里面写的旧编号是「原来指向 X、现已改指 Y」的取证文字，
    不是有人还在引用的边 —— r129 首跑把 7 处更正行的旧编号判成悬空，实测全部是这类留痕
    （FE-017 已在 r3 整卡并入 FE-005）。历史引用另计一个数报出来，供人抽查「合并后有没有漏改的活引用」。
    """
    bad = []
    outbound = {i: set() for i in cards}
    inbound = {i: set() for i in cards}
    historical = []
    for cid, c in cards.items():
        live, hist = [], []
        for ln in c["lines"]:
            (hist if CORRECTION_RE.match(ln) else live).append(ln)
        live_text = "\n".join([c["title"]] + live)
        for ref in REF_RE.findall(live_text):
            if ref == cid:
                bad.append("%s 自指 [[%s]]" % (cid, ref))
                continue
            if ref not in cards:
                bad.append("%s 悬空引用 [[%s]]（卡集合里不存在）" % (cid, ref))
                continue
            outbound[cid].add(ref)
            inbound[ref].add(cid)
        for ref in REF_RE.findall("\n".join(hist)):
            if ref not in cards:
                historical.append("%s 更正行提及已消失的 %s" % (cid, ref))
    islands = sorted(i for i in cards if not outbound[i] and not inbound[i])
    if islands:
        bad.append("孤岛条目 %d 条（无任何 [[编号]] 进出）：%s"
                   % (len(islands), "、".join(islands[:8]) + ("…" if len(islands) > 8 else "")))
    return bad, outbound, inbound, historical


def check_provenance(cards):
    """② 证据溯源：非 E 级卡必须有 `- 来源：` + ≥1 条来源子行。"""
    bad = []
    for cid in sorted(cards):
        c = cards[cid]
        level = card_level(c["lines"])
        if level == "E":
            continue
        has_head = any(SRC_LINE_RE.match(ln) for ln in c["lines"])
        subs = sum(1 for ln in c["lines"] if SRC_SUB_RE.match(ln))
        if not has_head:
            bad.append("%s 缺 `- 来源：` 行（README §2 纪律 2：非 E 级须有可核对来源）" % cid)
        elif subs == 0:
            bad.append("%s 有来源行但零条来源子行（无法核对到具体论断）" % cid)
        if not any(IN_RE.match(ln) for ln in c["lines"]):
            bad.append("%s 缺 `- 入库：` 行（哪一轮入的库不可追溯）" % cid)
    return bad


def check_index(cards, rows):
    """③ 索引对账：双向差集 + 级别一致 + 篇章归属一致。"""
    bad = []
    only_cards = sorted(set(cards) - set(rows))
    only_rows = sorted(set(rows) - set(cards))
    if only_cards:
        bad.append("已成卡但索引缺行 %d 条：%s"
                   % (len(only_cards), "、".join(only_cards[:8]) + ("…" if len(only_cards) > 8 else "")))
    if only_rows:
        bad.append("索引有行但查无此卡 %d 条：%s"
                   % (len(only_rows), "、".join(only_rows[:8]) + ("…" if len(only_rows) > 8 else "")))
    for cid in sorted(set(cards) & set(rows)):
        lvl = card_level(cards[cid]["lines"])
        if rows[cid]["level"] != lvl:
            bad.append("%s 级别不一致：卡=%s 索引=%s" % (cid, lvl, rows[cid]["level"]))
        chapter = rows[cid]["chapter"]
        fname = cards[cid]["file"]
        stem = fname[:-3] if fname.endswith(".md") else fname
        if chapter and chapter != stem:
            bad.append("%s 篇章归属不一致：卡实际在 %s，索引写 %s" % (cid, fname, chapter))
    return bad


def debate_hint(cards):
    """提示面：D 级卡正文里「两方并陈」关键词命中率（不判红，供人工抽查排面）。"""
    d = [cid for cid in cards if card_level(cards[cid]["lines"]) == "D"]
    hit = [cid for cid in d if any(k in "\n".join(cards[cid]["lines"]) for k in DEBATE_KW)]
    return len(d), len(hit)


def run(kb_dir=KB_DIR, index_path=INDEX):
    cards, _p = load_cards(kb_dir)
    rows = load_index(index_path)
    rel, outbound, inbound, historical = check_relations(cards)
    prov = check_provenance(cards)
    idx = check_index(cards, rows)
    d_total, d_hit = debate_hint(cards)
    wording = index_wording_drift(cards, rows)
    problems = rel + prov + idx
    if wording:
        problems.append("索引「一句话」与卡内原文不一致 %d 条：%s（人读索引会照抄这句 ⇒ 必须与卡逐字同文；"
                        "r129 实测 110 行可全部逐字一致，故升为硬判据）"
                        % (len(wording), "、".join(wording[:8]) + ("…" if len(wording) > 8 else "")))
    stats = {
        "cards": len(cards), "index_rows": len(rows),
        "edges": sum(len(v) for v in outbound.values()),
        "linked": sum(1 for i in cards if outbound[i] or inbound[i]),
        "d_total": d_total, "d_hit": d_hit, "historical": len(historical),
        "wording": len(wording), "wording_ids": wording,
    }
    return problems, stats


def main():
    problems = []
    stats = {}
    try:
        problems, stats = run()
    except FaceMissing as e:
        print("PSYCH-KB-INTEGRITY-UNVERIFIED: 取数面缺失/解析失效 %s" % e)
        return 2
    if "--report" in sys.argv:
        for p in problems[:40]:
            print("  · " + p)
        print("PSYCH-KB-INTEGRITY-REPORT: 卡 %d｜索引行 %d｜关联边 %d｜有进出 %d/%d｜D 级 %d（关键词命中 %d）"
              "｜更正行历史提及已消失编号 %d 处（不判红）｜索引一句话与卡不一致 %d 条（判红项）：%s｜问题 %d 条"
              % (stats["cards"], stats["index_rows"], stats["edges"], stats["linked"], stats["cards"],
                 stats["d_total"], stats["d_hit"], stats["historical"], stats["wording"],
                 "、".join(stats["wording_ids"][:10]) + ("…" if stats["wording"] > 10 else ""),
                 len(problems)))
        return 0
    if problems:
        for p in problems[:40]:
            print("  🔴 " + p)
        print("PSYCH-KB-INTEGRITY-FAIL: 问题 %d 条（卡 %d｜索引行 %d）⇒ 只报前 40 条，全量看 --report"
              % (len(problems), stats["cards"], stats["index_rows"]))
        return 1
    print("PSYCH-KB-INTEGRITY-PASS: 卡 %d 条零悬空零孤岛｜索引双向差集 0｜非 E 级全部带来源与入库行"
          "｜关联边 %d｜D 级 %d 条人工抽查提示位待跑" % (stats["cards"], stats["edges"], stats["d_total"]))
    return 0


BASE_CARD_A = """### 条目 PSY-ZZ-001｜甲卡
- 可信度：A
- 一句话：甲的一句话
- 内容：甲的内容。
- 来源：
  - [甲论断] 张三 (2020) 某刊, 1(2):3. DOI:10.5555/zz001
- 关联：[[PSY-ZZ-002]]（支撑）
- 待验证点：无
- 入库：2026-10-12 · 第5轮
"""
BASE_CARD_B = """### 条目 PSY-ZZ-002｜乙卡
- 可信度：B
- 一句话：乙的一句话
- 内容：乙的内容。
- 来源：
  - [乙论断] 李四 (2021) 某刊, 2(3):4. DOI:10.5555/zz002
- 关联：[[PSY-ZZ-001]]（补充）
- 待验证点：无
- 入库：2026-10-12 · 第5轮
"""
BASE_INDEX = """# 索引夹具

## 二、条目索引表

| 编号 | 标题 | 可信度 | 篇章 | 一句话 |
|---|---|---|---|---|
| PSY-ZZ-001 | 甲卡 | A | 90-夹具 | 甲的一句话 |
| PSY-ZZ-002 | 乙卡 | B | 90-夹具 | 乙的一句话 |

## 三、变更记录
"""


def fixture_pair(cards_text=None, index_text=None):
    d = kb.fixture_dir({"90-夹具.md": cards_text or (BASE_CARD_A + "\n" + BASE_CARD_B)})
    idx = d / "索引.md"
    idx.write_text(index_text if index_text is not None else BASE_INDEX, encoding="utf-8", newline="\n")
    return d, idx


def has(sub, probs):
    return any(sub in p for p in probs), ("未点名「%s」，实得：%s" % (sub, probs[:3]) if not any(sub in p for p in probs) else "")


def raises_facemissing(fn):
    try:
        fn()
    except FaceMissing:
        return True, ""
    except Exception as e:  # noqa: BLE001
        return False, "意外异常 %s: %s" % (type(e).__name__, e)
    return False, "未抛 FaceMissing（取数面坏了却读成没问题）"


def selftest():
    """判据非恒真的取证（17 腿）：夹具正例 2 + 该红的 11 + 历史留痕不得判红 1 + 取数面失效 2 + 真面正例 1。

    夹具全落系统临时目录；脚本内不做磁盘直删（本仓禁用 rm/rmtree 类形态，OS 回收临时目录）。
    第 12 腿是 r129 首跑我自己踩的两处判据缺陷的回归位：列序读反（196 条假红）与
    把 `- 更正：` 行的历史编号当成活引用（7 条假红）—— 修完各留一条腿，防止改回去。
    """
    results = []

    def leg(name, fn):
        try:
            ok, why = fn()
        except Exception as e:  # noqa: BLE001  失败路径本身不得崩
            ok, why = False, "腿自身异常 %s: %s" % (type(e).__name__, e)
        results.append((name, bool(ok), why))

    def clean_fixture():
        probs, _s = run(*fixture_pair())
        return (not probs), ("干净夹具被judge红：%s" % probs[:3])

    def dangling():
        t = BASE_CARD_A.replace("[[PSY-ZZ-002]]", "[[PSY-ZZ-999]]") + "\n" + BASE_CARD_B
        probs, _s = run(*fixture_pair(cards_text=t))
        return has("悬空引用", probs)

    def selfref():
        t = BASE_CARD_A.replace("[[PSY-ZZ-002]]", "[[PSY-ZZ-001]]") + "\n" + BASE_CARD_B
        probs, _s = run(*fixture_pair(cards_text=t))
        return has("自指", probs)

    def island():
        t = BASE_CARD_A.replace("[[PSY-ZZ-002]]", "（无）") + "\n" + BASE_CARD_B.replace("[[PSY-ZZ-001]]", "（无）")
        probs, _s = run(*fixture_pair(cards_text=t))
        return has("孤岛条目", probs)

    def no_source():
        cards = (BASE_CARD_A.replace("- 来源：\n", "")
                 + "\n" + BASE_CARD_B.replace("  - [乙论断] 李四 (2021) 某刊, 2(3):4. DOI:10.5555/zz002\n", ""))
        probs, _s = run(*fixture_pair(cards_text=cards))
        a = has("缺 `- 来源：`", probs)
        b = has("零条来源子行", probs)
        return (a[0] and b[0]), (a[1] or b[1])

    def no_ship_line():
        t = (BASE_CARD_A.replace("- 入库：2026-10-12 · 第5轮\n", "") + "\n" + BASE_CARD_B)
        probs, _s = run(*fixture_pair(cards_text=t))
        return has("缺 `- 入库：`", probs)

    def index_missing_row():
        probs, _s = run(*fixture_pair(index_text=BASE_INDEX.replace("| PSY-ZZ-002 | 乙卡 | B | 90-夹具 | 乙的一句话 |\n", "")))
        return has("已成卡但索引缺行", probs)

    def index_ghost_row():
        extra = "| PSY-ZZ-009 | 幽灵卡 | A | 90-夹具 | 不该在索引里 |\n"
        probs, _s = run(*fixture_pair(index_text=BASE_INDEX.replace("## 三、变更记录", extra + "\n## 三、变更记录")))
        return has("索引有行但查无此卡", probs)

    def index_level_mismatch():
        probs, _s = run(*fixture_pair(index_text=BASE_INDEX.replace("| PSY-ZZ-002 | 乙卡 | B |", "| PSY-ZZ-002 | 乙卡 | A |")))
        return has("级别不一致", probs)

    def index_chapter_mismatch():
        probs, _s = run(*fixture_pair(index_text=BASE_INDEX.replace("| A | 90-夹具 | 甲的一句话 |", "| A | 07-别的篇章 | 甲的一句话 |")))
        return has("篇章归属不一致", probs)

    def index_column_swap():
        # 列序漂移必红：把「标题」和「可信度」两格互换 ⇒ group(3) 读到的是标题，必须判不一致，
        # 不许静默通过（r129 首跑就是把 group(2) 当级别，一次造出 196 条假红）
        swapped = BASE_INDEX.replace("| PSY-ZZ-001 | 甲卡 | A |", "| PSY-ZZ-001 | A | 甲卡 |")
        probs, _s = run(*fixture_pair(index_text=swapped))
        return has("级别不一致", probs)

    def correction_line_is_history():
        t = (BASE_CARD_A.replace("- 关联：[[PSY-ZZ-002]]（支撑）",
                                 "- 关联：[[PSY-ZZ-002]]（支撑）\n- 更正：2026-10-12 原指 [[PSY-ZZ-888]] → 改指 [[PSY-ZZ-002]]")
             + "\n" + BASE_CARD_B)
        d, idx = fixture_pair(cards_text=t)
        probs, stats = run(d, idx)
        return (not has("悬空引用", probs)[0] and stats["historical"] == 1), \
               ("更正行历史编号被当成活引用（probs=%s, historical=%s）" % (probs[:2], stats["historical"]))

    def empty_kb():
        d = kb.fixture_dir({})
        return raises_facemissing(lambda: load_cards(d))

    def spec_only_kb():
        d = kb.fixture_dir({"README.md": "规范", "索引.md": "索引"})
        return raises_facemissing(lambda: load_cards(d))

    def real_face_clean():
        probs, stats = run()
        return (not probs), ("真面现存 %d 条问题：%s" % (len(probs), probs[:3]))

    def wording_clean_match():
        d, idx = fixture_pair()
        drift = index_wording_drift(load_cards(d)[0], load_index(idx))
        return (not drift), ("索引一句话与卡逐字一致却被判漂移：%s" % drift)

    def wording_drift_caught():
        t = BASE_INDEX.replace("| 甲的一句话 |", "| 甲的一句话改过 |")
        d, idx = fixture_pair(index_text=t)
        probs, stats = run(d, idx)
        return has("索引「一句话」与卡内原文不一致", probs)

    leg("夹具正例·干净库零问题", clean_fixture)
    leg("悬空引用必红", dangling)
    leg("自指必红", selfref)
    leg("孤岛必红", island)
    leg("缺来源/来源零子行必红", no_source)
    leg("缺入库行必红", no_ship_line)
    leg("索引缺行必红", index_missing_row)
    leg("索引幽灵行必红", index_ghost_row)
    leg("索引级别漂移必红", index_level_mismatch)
    leg("索引篇章漂移必红", index_chapter_mismatch)
    leg("索引列序漂移必红（取数面自证）", index_column_swap)
    leg("更正行历史编号不判红（r129 自身缺陷回归）", correction_line_is_history)
    leg("索引一句话逐字一致⇒零漂移（列序自证）", wording_clean_match)
    leg("索引一句话被改一个字⇒必抓到", wording_drift_caught)
    leg("空目录⇒UNVERIFIED 不判绿", empty_kb)
    leg("只有规范与索引⇒UNVERIFIED 不判绿", spec_only_kb)
    leg("真面零问题（正例）", real_face_clean)

    passed = [n for n, ok, _ in results if ok]
    failed = [(n, w) for n, ok, w in results if not ok]
    for name, ok, why in results:
        print("  %-46s %s%s" % (name, "OK" if ok else "FAIL", ("" if ok else "  " + why)))
    if failed:
        print("PSYCH-KB-INTEGRITY-SELFTEST-FAIL: %d/%d 腿通过，失败：%s"
              % (len(passed), len(results), "、".join(n for n, _ in failed)))
        return 1
    _p, stats = run()
    print("PSYCH-KB-INTEGRITY-SELFTEST-PASS: %d/%d 腿（真面 卡%d 索引行%d 关联边%d 有进出%d）"
          % (len(passed), len(results), stats["cards"], stats["index_rows"], stats["edges"], stats["linked"]))
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    sys.exit(main())
