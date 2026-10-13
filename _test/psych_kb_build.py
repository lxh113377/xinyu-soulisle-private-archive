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
--selftest：判据非恒真的取证（13 腿，含 2 条真面变异腿）。夹具全部建在系统临时目录，
            绝不读写仓库面；正例腿另附「真面 --check 必须 PASS」+「真产物改一个字符必须判不一致」。
用法：python _test/psych_kb_build.py [--check|--selftest]
退出码：0=PASS 1=FAIL 2=输入面缺失
"""
import json
import re
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
KB_DIR = ROOT / "交付物" / "心理学知识库"
OUT = ROOT / "src" / "data" / "psych-kb.js"
KB_VERSION = "v2.0"          # 与 README 版本行同步；规范本体改动时人工 bump
BUILT_TAG = "r167-KB11b"       # b = 截断保全免责短语（r167-KB11b 立）
LEVELS = ("A", "B", "C", "D", "E")
SHIP_LEVELS = ("A", "B", "C", "D")   # E 级不入产品件
CONTENT_MAX = 320            # 注入用内容截断（句界截断，超长条目保前几句即可撑起 60-120 字回复）
BOUNDARY_MAX = 60            # 免责短语自身的长度上限（超此值判为正则咬多了 -> fail-fast，不静默灌长段）
MAX_RELATED = 4              # 每条目自动提取的情绪关联上限

# README §7：治疗类实证条目内须带「不构成医疗/诊断建议」边界句（知识免责，非产品禁令）。
# 该句在卡面多写在内容末尾 => 会被 CONTENT_MAX 截断静默丢弃，注入 LLM 时就只剩研究结论、
# 少了免责信号。故截断前先把它摘出来，截断后若不在正文里则前置到句首（r167-KB11b 立）。
# 收紧条件（两道，缺一即误抓）：
#  ①必须同时出现免责动词与医疗/诊断类名词 —— 否则「preprint 单独不作依据」这类证据状态声明
#    会被误当医疗免责句带进提示词；
#  ②免责名词（建议/依据/判断/结论）**必填** —— 否则「机制与延伸（供话术底、不作诊断）：睡眠剥夺后
#    杏仁核对负性刺激反应增强」会整句被当成免责句前置，而它前半段是机制陈述、不是免责。
BOUNDARY_RE = re.compile(
    r"(?:不构成|非诊断|不作)[^。；\n]{0,16}(?:治疗|医疗|诊断|处方|心理干预|临床)[^。；\n]{0,6}?(?:建议|依据|判断|结论)"
)

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


class BuildFail(Exception):
    """构建期失败。由 main() 唯一出口转成 rc=1；--selftest 在进程内捕获它做取证。"""


def fail(msg):
    raise BuildFail(msg)


def trim_sentence(text, limit):
    """句界截断：在 limit 内找最后一个句号/问号/叹号，找不到整段保留首 limit 字。"""
    if len(text) <= limit:
        return text
    cut = text[:limit]
    best = max(cut.rfind(p) for p in ("。", "！", "？", "；"))
    return cut[: best + 1] if best >= int(limit * 0.4) else cut


def extract_boundary(text, eid=""):
    """摘出卡内的医疗免责短语（README §7）。找不到返回 None。

    只取免责短语本身，不连后面解释性的逗句一起搬（否则「本卡不构成治疗建议，所有措辞须以…
    为唯一 A/B 判据」会把半段工程说明灌进提示词）。长度超 BOUNDARY_MAX 判为正则咬多了 -> fail-fast。
    """
    for seg in re.split(r"(?<=。)|(?<=；)", text):
        m = BOUNDARY_RE.search(seg)
        if not m:
            continue
        head = seg[: m.end()]
        tail = seg[m.end():]
        stop = re.search(r"[。，、/（(]", tail)
        clause = (head + (tail[: stop.start()] if stop else tail)).strip(" ；")
        if len(clause) > BOUNDARY_MAX:
            fail("条目 %s 的免责短语长 %d 字（> %d）：正则咬多了，请修 BOUNDARY_RE 或该卡措辞"
                 % (eid or "?", len(clause), BOUNDARY_MAX))
        return clause + "。"
    return None


def keep_boundary(raw_content, eid=""):
    """截断 + 免责短语保全。返回注入用 content。

    语义：先在**未截断**原文里摘免责短语，再做句界截断；若摘出的短语在截断后已不存在，
    则前置到句首。前置而非后置，是因为后置会被下一次长度变化再次截掉，前置则位置恒定、
    且提示词里免责信号出现在研究结论之前。
    """
    bnd = extract_boundary(raw_content, eid)
    body = trim_sentence(raw_content, CONTENT_MAX)
    if not bnd or bnd in body:
        return body
    return bnd + body


def parse_entries(kb_dir=KB_DIR):
    if not kb_dir.is_dir():
        fail("知识库目录缺失 " + str(kb_dir))
    files = sorted(p for p in kb_dir.glob("*.md") if p.name not in ("README.md", "索引.md"))
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
        e["content"] = keep_boundary(e["content"], e["id"])
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


def check_pair(kb_dir=KB_DIR, out=OUT):
    """源卡 ⇄ 产物一致性判定（不打印，供 --check 与 --selftest 共用，避免两套实现）。"""
    entries, counts, n_files = parse_entries(kb_dir)
    text = build_text(entries, counts, n_files)
    if not out.exists():
        fail("产物缺失 " + str(out))
    if out.read_text("utf-8") != text:
        fail("产物与知识库源不一致：条目卡更新后未重建（跑一次不带 --check 的本脚本）")
    return entries, counts, n_files


CARD = "### 条目 %s｜%s\n- 可信度：%s\n- 一句话：%s\n- 内容：%s\n- 来源：略\n"


def fixture_dir(files):
    d = Path(tempfile.mkdtemp(prefix="psychkb_selftest_"))
    for name, text in files.items():
        (d / name).write_text(text, encoding="utf-8", newline="\n")
    return d


def raises_buildfail(fn):
    try:
        fn()
    except BuildFail:
        return True, ""
    except Exception as e:  # noqa: BLE001  其它异常也算「未按预期失败」，但必须点名
        return False, "意外异常 %s: %s" % (type(e).__name__, e)
    return False, "未抛 BuildFail（判据没咬）"


ASSIGN = "window.__XINYU_PSYCH_KB__ = "


def payload_of(text):
    """从数据件文本取 JSON 载荷。按赋值锚点切，不用 split("= ") —— 头注释里「源 = 交付物…」也含 "= "。"""
    return json.loads(text.split(ASSIGN, 1)[1].rsplit(";\n", 1)[0])


def selftest():
    """判据非恒真的取证：正例 6 条 + 该红的 7 条（含 2 条真面变异腿）= 13 腿。夹具只落系统临时目录。

    临时件不做删除：本仓禁用磁盘直删（lessons-p0「Windows 删除必须走回收站」），
    系统临时目录由 OS 回收，脚本内 rmtree 反而会撞那条机械护栏。
    """
    results = []

    def leg(name, fn):
        try:
            ok, why = fn()
        except Exception as e:  # noqa: BLE001  失败路径本身不得崩（BLIND-RED 家族）
            ok, why = False, "腿自身异常 %s: %s" % (type(e).__name__, e)
        results.append((name, bool(ok), why))

    def ok_parse_one():
        d = fixture_dir({"90-夹具.md": CARD % ("PSY-ZZ-001", "焦虑与放松", "A",
                                              "一句话谈焦虑", "内容讲放松。")})
        entries, counts, n_files = parse_entries(d)
        if len(entries) != 1 or entries[0]["level"] != "A" or n_files != 1:
            return False, "正例解析得 %d 条/%d 篇" % (len(entries), n_files)
        if "fear" not in entries[0]["rel"]:
            return False, "情绪关联未挂上 fear（rel=%s）" % entries[0]["rel"]
        return True, ""

    def ok_e_excluded():
        d = fixture_dir({"90-夹具.md": CARD % ("PSY-ZZ-002", "已查证条", "A", "甲", "甲内容。")
                         + CARD % ("PSY-ZZ-003", "未查证条", "E", "乙", "乙内容。")})
        entries, counts, n_files = parse_entries(d)
        payload = payload_of(build_text(entries, counts, n_files))
        if payload["excludedE"] != 1 or len(payload["entries"]) != 1:
            return False, "E 排除 excludedE=%s entries=%d" % (payload["excludedE"], len(payload["entries"]))
        return True, ""

    def ok_truncate():
        long_text = "这是一段足够长的中文内容用来验证句界截断。" * 20
        d = fixture_dir({"90-夹具.md": CARD % ("PSY-ZZ-004", "长内容", "B", "摘要", long_text)})
        entries, counts, n_files = parse_entries(d)
        c = entries[0]["content"]
        if len(c) > CONTENT_MAX or c[-1] not in "。！？；":
            return False, "截断后 len=%d 末字符=%r" % (len(c), c[-1:])
        return True, ""

    def ok_boundary_kept():
        """免责短语在内容末尾时，必须被摘出并前置到句首（r167-KB11b 立）。"""
        filler = "这是一段足够长的中文内容用来把免责短语挤到截断线之外。" * 20
        raw = filler + "边界句：本条为证据综述，不构成治疗建议。"
        d = fixture_dir({"90-夹具.md": CARD % ("PSY-ZZ-014", "带免责", "B", "摘要", raw)})
        entries, counts, n_files = parse_entries(d)
        c = entries[0]["content"]
        # 对照：未截断原文里免责短语确实在很靠后的位置
        if raw.index("不构成治疗建议") < len(raw) - 40:
            return False, "夹具前提不成立：免责短语本就在末尾"
        if "不构成治疗建议" not in c:
            return False, "免责短语在产物里丢了：len=%d 头40=%r" % (len(c), c[:40])
        if not c.startswith("边界句：本条为证据综述，不构成治疗建议。"):
            return False, "免责短语未前置到句首：头40=%r" % c[:40]
        return True, ""

    def red_boundary_lost_without_gate():
        """变异腿：摘掉 keep_boundary（即回到本轮修复前的行为），免责短语必须复现丢失。

        腿非恒真的证据 —— 若这步也「不丢」，说明夹具根本不触发截断，正例腿是装饰。
        """
        filler = "这是一段足够长的中文内容用来把免责短语挤到截断线之外。" * 20
        raw = filler + "边界句：本条为证据综述，不构成治疗建议。"
        legacy = trim_sentence(raw, CONTENT_MAX)          # 修复前行为：只截断，不保全
        if "不构成治疗建议" in legacy:
            return False, "变异腿失效：旧行为下免责短语竟然没丢，正例腿可能是装饰"
        if "不构成治疗建议" not in keep_boundary(raw, "PSY-ZZ-015"):
            return False, "keep_boundary 也没保住（变异腿通过但正例腿是假的）"
        return True, ""

    def ok_ship_zero_guard():
        d = fixture_dir({"90-夹具.md": CARD % ("PSY-ZZ-005", "全是未查证", "E", "甲", "甲内容。")})
        entries, counts, n_files = parse_entries(d)
        payload = payload_of(build_text(entries, counts, n_files))
        if payload["entries"] or payload["excludedE"] != 1:
            return False, "全 E 面 entries=%d" % len(payload["entries"])
        return True, ""

    def red_missing_level():
        d = fixture_dir({"90-夹具.md": "### 条目 PSY-ZZ-010｜缺级\n- 一句话：甲\n- 内容：乙。\n"})
        return raises_buildfail(lambda: parse_entries(d))

    def red_dup_id():
        one = CARD % ("PSY-ZZ-011", "同号甲", "A", "甲", "甲内容。")
        d = fixture_dir({"90-夹具.md": one + one})
        return raises_buildfail(lambda: parse_entries(d))

    def red_only_spec():
        d = fixture_dir({"README.md": "规范", "索引.md": "索引"})
        return raises_buildfail(lambda: parse_entries(d))

    def red_shape_drift():
        # 半角冒号 + 缺「｜」：行式与 README §3 漂移，解析必须报 0 条而不是静默产出空库
        d = fixture_dir({"90-夹具.md": "### 条目 PSY-ZZ-012:漂移标题\n- 可信度: A\n- 一句话: 甲\n"})
        return raises_buildfail(lambda: parse_entries(d))

    def red_bad_level_letter():
        d = fixture_dir({"90-夹具.md": CARD % ("PSY-ZZ-013", "非法级", "F", "甲", "甲内容。")})
        return raises_buildfail(lambda: parse_entries(d))

    def red_real_face_consistent():
        entries, counts, n_files = check_pair()
        if not entries:
            return False, "真面解析 0 条"
        return True, ""

    def red_tampered_product():
        prod = OUT.read_text("utf-8")
        mid = len(prod) // 2
        tampered = prod[:mid] + "X" + prod[mid + 1:]
        d = fixture_dir({})
        bad = d / "psych-kb.tampered.js"
        bad.write_text(tampered, encoding="utf-8", newline="\n")
        return raises_buildfail(lambda: check_pair(KB_DIR, bad))

    leg("正例·单卡解析+情绪关联", ok_parse_one)
    leg("E 级构建期排除并计数", ok_e_excluded)
    leg("内容句界截断", ok_truncate)
    leg("免责短语截断后仍前置到句首", ok_boundary_kept)
    leg("摘掉保全逻辑免责句必丢（变异腿）", red_boundary_lost_without_gate)
    leg("全 E 面产物为空库（供 main 的红腿判定）", ok_ship_zero_guard)
    leg("缺可信度字段即停", red_missing_level)
    leg("条目撞号即停", red_dup_id)
    leg("只有规范与索引即停", red_only_spec)
    leg("卡行式漂移即停（禁静默产出空库）", red_shape_drift)
    leg("可信度非法字母即停", red_bad_level_letter)
    leg("真面源⇄产物一致（正例）", red_real_face_consistent)
    leg("真产物篡改一位必判不一致（变异腿）", red_tampered_product)

    passed = [n for n, ok, _ in results if ok]
    failed = [(n, why) for n, ok, why in results if not ok]
    for name, ok, why in results:
        print("  %-46s %s%s" % (name, "OK" if ok else "FAIL", ("  " + why) if why else ""))
    if failed:
        print("PSYCH-KB-SELFTEST-FAIL: %d/%d 腿通过，失败 %d 条：%s"
              % (len(passed), len(results), len(failed),
                 "、".join(n for n, _ in failed)))
        sys.exit(1)
    entries, counts, _n = parse_entries()
    print("PSYCH-KB-SELFTEST-PASS: %d/%d 腿（真面 %d 条 A%d B%d C%d D%d E排除%d｜变异腿咬合 2 处）"
          % (len(passed), len(results), len(entries), counts["A"], counts["B"], counts["C"],
             counts["D"], counts["E"]))


def main():
    try:
        if "--selftest" in sys.argv:
            selftest()
            return
        if "--check" in sys.argv:
            entries, counts, _n = check_pair()
            print("PSYCH-KB-CHECK-PASS: 产物与源一致（%d 条，A%d B%d C%d D%d，E 排除 %d）"
                  % (len(entries), counts["A"], counts["B"], counts["C"], counts["D"], counts["E"]))
            return
        entries, counts, n_files = parse_entries()
        text = build_text(entries, counts, n_files)
        OUT.write_text(text, encoding="utf-8", newline="\n")
        size = OUT.stat().st_size
        ship_n = sum(counts[k] for k in SHIP_LEVELS)
        print("PSYCH-KB-BUILD-PASS: 入库 %d 条（A:%d B:%d C:%d D:%d，E 排除 %d），"
              "源文件 %d 个 -> %s（%s bytes）"
              % (ship_n, counts["A"], counts["B"], counts["C"], counts["D"], counts["E"],
                 n_files, OUT.relative_to(ROOT), format(size, ",")))
        if ship_n == 0:
            fail("全部条目均为 E 级，产品件将是空库：先升级条目再重建")
    except BuildFail as e:
        print("PSYCH-KB-BUILD-FAIL: " + str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
