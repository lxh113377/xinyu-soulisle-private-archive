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
--selftest：判据自证（正例绿/反例红）。⚠️ r134 披露：r133 轮的原 15 腿 selftest 为**未提交**工作区件，
  在 2026-10-13 02:08 的 _test 清场事件中随目录丢失（_temp/headcheck 副本亦无）；现版 10 腿为
  **清场后重建**（覆盖同族不变量但非原版复刻），r133 责任面下次接触本件时应比对补强。
用法：python _test/wit_quotes_build.py [--check] [--selftest] [--dir <源目录>] [--out <产物路径>]
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
WQ_VERSION = "v1.2"
BUILT_TAG = "r171"
LEVELS = ("A", "B", "C", "D", "E")
SHIP_LEVELS = ("A", "B", "C", "D")   # E 级不入产品件
EMOTIONS = ("joy", "sadness", "anger", "fear", "calm", "love")
SCENES = ("共情", "安抚", "鼓励", "解释", "开解", "庆祝", "自我接纳", "陪伴")
# 文件名前缀数字 -> 篇码（防条目放错篇章）
CHAPTERS = {"01": "CL", "02": "MS", "03": "NET", "04": "PH"}
CAT_NAMES = {"CL": "文言与古诗词", "MS": "名家名句", "NET": "网络热句", "PH": "哲学思辨"}
QUOTE_MAX = 260     # 句面上限（超长逼拆条，防注入超体量预算）
FIT_MAX = 34        # 适配条件上限（注入面每条都要带它，超一条字就挤掉一条候选）
# ⚠️ r171 删除 `USAGE_MAX` 与 `trim_sentence()`：产物里的 `usage` 曾是 md「用法」的 120 字**截断副本**，
#   全仓零消费者（实测 `.usage` 命中只有各判据里 OpenAI 响应桩的 "usage":{}），却占首屏 44,094B。
#   注入面需要的信息改由 `fit` 承载（md 仍是「用法」全文的唯一真相源）。
REQUIRED = ("可信度", "出处", "适用情绪", "适用场景", "用法", "句面", "风险注记", "入库")
# r171 可选第 9 列：人工直写的「适配条件」。派生只是保底，不是终态 ——
# 实测 174 条里 26 条（其中整卷 PH 20 条）的「用法」首句先讲概念、触发条件写在后半句，
# 压到 34 字内就只剩场景标签（弱信号）。给卡面一个**直写位**，修卡就变成纯内容活，
# 不必把算法改成会咬人的模糊截断（截出半句话比标签更误导模型）。
OPTIONAL = ("适配提示",)
FIELDS = REQUIRED + OPTIONAL

ENTRY_RE = re.compile(r"^### 条目 (QTE-([A-Z]+)-\d{3})｜(.+?)\s*$")
FIELD_RE = re.compile(r"^[-\s]*(可信度|出处|适用情绪|适用场景|用法|句面|风险注记|入库|适配提示)：(.*)$")
LEVEL_RE = re.compile(r"^[A-E]$")
PAREN_RE = re.compile(r"（[^（）]*）")


def derive_fit(usage, scene):
    """从「用法」的触发子句派生注入用的适配条件（r171）。

    为什么要有这个字段：r117-r134 的注入行只有 `[id·level]句面`，模型拿到的是**没有适用条件的
    裸句**——它无从判断「这句此刻贴不贴得上」，于是要么整句硬贴（生硬引用），要么干脆不用
    （r117 首轮 30 轮零引用）。`usage` 里其实写着触发条件，但单条最长 120 字，五条一起塞不进
    注入预算。本函数把触发子句压成 ≤FIT_MAX 的字，只保留「用户…时」这一层信息。

    三级降级（确定性，禁静默丢）：① 取到第一个「时」为止；② 去掉（）补语后再取；
    ③ 都不合长度就回落「适合：<场景标签>」。③ 会被计数并打进构建行。
    返回值恒非空且长度 ≤ max(FIT_MAX, 回落串长度)。
    """
    trigger = usage.find("时")
    if trigger >= 0:
        cand = usage[: trigger + 1]
        if cand and len(cand) <= FIT_MAX:
            return cand
        stripped = PAREN_RE.sub("", usage)
        trigger2 = stripped.find("时")
        if trigger2 >= 0:
            cand2 = stripped[: trigger2 + 1]
            if cand2 and len(cand2) <= FIT_MAX:
                return cand2
    return "适合：" + "、".join(scene)


def fail(msg):
    print("WIT-QUOTES-BUILD-FAIL: " + msg)
    sys.exit(1)


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
    fit_fallback = 0
    fit_counts = {"card": 0, "derived": 0, "scene": 0}
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
        card_fit = e["fields"].get("适配提示", "")
        if "适配提示" in e["fields"] and not card_fit:
            fail("条目 %s 写了「适配提示」列但值为空（要么填 ≤%d 字的触发子句，要么整行删掉）"
                 % (e["id"], FIT_MAX))
        if card_fit and len(card_fit) > FIT_MAX:
            fail("条目 %s 适配提示超长 %d 字（上限 %d，注入预算按条算）"
                 % (e["id"], len(card_fit), FIT_MAX))
        if card_fit:
            fit, fit_src = card_fit, "card"
        else:
            fit = derive_fit(e["fields"]["用法"], scene)
            fit_src = "scene" if fit.startswith("适合：") else "derived"
        fit_counts[fit_src] += 1
        if fit_src == "scene":
            fit_fallback += 1
        shipped.append({
            "id": e["id"], "cat": e["cat"], "title": e["title"], "level": level,
            "quote": quote, "src": e["fields"]["出处"],
            "emo": emo, "scene": scene, "fit": fit,
            "risk": e["fields"]["风险注记"],
        })
    shipped.sort(key=lambda x: x["id"])
    by_cat = {c: 0 for c in CAT_NAMES}
    for e in shipped:
        by_cat[e["cat"]] += 1
    by_emo = {}
    by_scene = {}
    for e in shipped:
        for x in e["emo"]:
            by_emo[x] = by_emo.get(x, 0) + 1
        for x in e["scene"]:
            by_scene[x] = by_scene.get(x, 0) + 1
    data = {
        "version": WQ_VERSION,
        "built": BUILT_TAG,
        "counts": {"total": len(shipped), "by_level": counts, "by_cat": by_cat,
                   "by_emo": by_emo, "by_scene": by_scene, "fitSrc": fit_counts,
                   "fitFallback": fit_fallback, "excludedE": counts["E"]},
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


CARD_TMPL = """### 条目 QTE-CL-901｜自证测试条目
- 可信度：{level}
- 出处：自证测试（不入库）
- 适用情绪：{emo}
- 适用场景：{scene}
- 用法：测试用法句。
- 句面：{quote}
- 风险注记：测试。
- 入库：是
"""
OK_CARD = dict(level="A", emo="sadness", scene="共情", quote="试金石一句，验解析通路。")


def _write_card(tmp_dir, name, text):
    tmp_dir.mkdir(parents=True, exist_ok=True)
    p = tmp_dir / name
    p.write_text(text, encoding="utf-8")
    return p


def _expect_fail(tmp_dir, name, text, why, write=True):
    """反例腿：喂坏卡 ⇒ parse_entries 必须 fail-fast（SystemExit code=1）。"""
    if write:
        _write_card(tmp_dir, name, text)
    try:
        parse_entries(tmp_dir)
    except SystemExit as e:
        if e.code == 1:
            return True
        print("   · 反例 %s：退出码 %s ≠ 1" % (why, e.code))
        return False
    except Exception as e:
        print("   · 反例 %s：异常类型 %s（应为 fail-fast 退出）" % (why, type(e).__name__))
        return False
    print("   · 反例 %s：未拦截（静默放行）" % why)
    return False


# --- selftest 的四族桩 + 收口（升模块级，按主题切：坏卡面 fail-fast 族／fit 派生族／真面变异腿族／直写位族）---
# 拆出来的原因只是 loc_guard 的「单函数 ≤150 行」门；判定体、卡面字面量、legs.append 顺序均与拆前逐字同文。
def _st_legs_bad_card_failfast(tmp, legs):
    """腿 3-10：坏卡面必须 fail-fast（ID 重复／篇码错位／枚举非法／句面超长／缺字段／通用并列），外加 E 级排除计数。"""
    # 3) 反例：ID 重复（卡面已写入 d2，不再经 _write_card 覆盖）
    d2 = tmp / "dup"
    _write_card(d2, "01-CL-test.md", CARD_TMPL.format(
        level="A", emo="sadness", scene="共情", quote="第一句。")
        + "\n\n" + CARD_TMPL.format(level="B", emo="sadness", scene="安抚", quote="第二句。"))
    legs.append(("反例·ID 重复 fail-fast", _expect_fail(d2, "", "", "ID 重复", write=False)))
    # 4) 反例：篇码与文件名不符（先 format 再 replace，防占位符漏填）
    d3 = tmp / "chap"
    _write_card(d3, "01-CL-test.md",
                CARD_TMPL.format(**OK_CARD)
                .replace("QTE-CL-901", "QTE-MS-901"))
    legs.append(("反例·篇码与篇章文件不符", _expect_fail(d3, "", "", "篇码错位", write=False)))
    # 5) 反例：情绪枚举非法
    d4 = tmp / "emo"
    _write_card(d4, "01-CL-test.md",
                CARD_TMPL.format(**OK_CARD)
                .replace("适用情绪：sadness", "适用情绪：狂喜"))
    legs.append(("反例·情绪枚举非法", _expect_fail(d4, "", "", "情绪枚举", write=False)))
    # 6) 反例：场景枚举非法
    d5 = tmp / "scene"
    _write_card(d5, "01-CL-test.md",
                CARD_TMPL.format(**OK_CARD)
                .replace("适用场景：共情", "适用场景：唠嗑"))
    legs.append(("反例·场景枚举非法", _expect_fail(d5, "", "", "场景枚举", write=False)))
    # 7) 反例：句面超长
    d6 = tmp / "long"
    _write_card(d6, "01-CL-test.md",
                CARD_TMPL.format(level="A", emo="sadness", scene="共情",
                                 quote="长" * (QUOTE_MAX + 1)))
    legs.append(("反例·句面超长", _expect_fail(d6, "", "", "句面超长", write=False)))
    # 8) 反例：缺字段
    d7 = tmp / "miss"
    _write_card(d7, "01-CL-test.md",
                "\n".join(l for l in CARD_TMPL.format(**OK_CARD).splitlines()
                          if not l.startswith("- 入库")))
    legs.append(("反例·缺字段", _expect_fail(d7, "", "", "缺字段", write=False)))
    # 9) E 级不入产品件
    d8 = tmp / "elevel"
    _write_card(d8, "01-CL-test.md",
                CARD_TMPL.format(**OK_CARD).replace("可信度：A", "可信度：E"))
    d8_data = parse_entries(d8)
    legs.append(("E 级排除·不入产品件", d8_data["counts"]["excludedE"] == 1
                 and d8_data["counts"]["total"] == 0))
    # 10) 「通用」不得与具体情绪并列
    d9 = tmp / "allmix"
    _write_card(d9, "01-CL-test.md",
                CARD_TMPL.format(**OK_CARD)
                .replace("适用情绪：sadness", "适用情绪：sadness、通用"))
    legs.append(("反例·「通用」并列具体情绪", _expect_fail(d9, "", "", "通用并列", write=False)))


def _st_legs_fit_derive(tmp, legs):
    """腿 11-15：fit 派生三档（触发子句／去括号／超长回落）+ 两条结构不变量（fit 恒在位、零死重量）。"""
    # 11) fit 派生（r171）：「用法」里短触发子句 ⇒ 取到第一个「时」为止
    d10 = tmp / "fitok"
    _write_card(d10, "01-CL-test.md",
                CARD_TMPL.format(**OK_CARD)
                .replace("用法：测试用法句。", "用法：用户说撑不住了时，先接住再轻引半句。"))
    d10_data = parse_entries(d10)
    legs.append(("fit·触发子句派生（止于「时」）",
                d10_data["entries"][0]["fit"] == "用户说撑不住了时"
                and d10_data["counts"]["fitFallback"] == 0))
    # 12) fit 二级降级（r171）：触发子句含（）补语、去括号后落回上限内 ⇒ 用去括号形态，不算回落
    d11 = tmp / "fitparen"
    _write_card(d11, "01-CL-test.md",
                CARD_TMPL.format(**OK_CARD)
                .replace("用法：测试用法句。",
                         "用法：用户在经历长期照护压力与自我消耗、并且明确表示已经没有退路"
                         "（如离职、休学、搬走）时，先接住他撑了很久这件事，忌给建议。"))
    d11_data = parse_entries(d11)
    legs.append(("fit·去括号后入上限",
                d11_data["entries"][0]["fit"] == "用户在经历长期照护压力与自我消耗、并且明确表示已经没有退路时"
                and d11_data["counts"]["fitFallback"] == 0))
    # 13) fit 三级回落（r171）：去括号后仍超 FIT_MAX ⇒ 回落场景标签 + 计数，禁硬截半句
    d12 = tmp / "fitfb"
    _write_card(d12, "01-CL-test.md",
                CARD_TMPL.format(**OK_CARD)
                .replace("用法：测试用法句。",
                         "用法：用户在经历长期的照护压力与自我消耗，并且已经在多个场合"
                         "明确表示自己没有退路（如离职、休学、搬走）时，先接住，忌给建议。"))
    d12_data = parse_entries(d12)
    fb_fit = d12_data["entries"][0]["fit"]
    legs.append(("fit·超长回落场景标签并计数",
                fb_fit == "适合：共情" and len(fb_fit) <= FIT_MAX
                and d12_data["counts"]["fitFallback"] == 1))
    # 14) fit 恒在位且不越界（r171 结构不变量：注入面每条都读它，缺键即静默退化成裸句）
    legs.append(("fit·每条必有且 ≤ 上限",
                all(e.get("fit") and len(e["fit"]) <= FIT_MAX
                    for d in (d10_data, d11_data, d12_data) for e in d["entries"])))
    # 15) 零死重量（r171）：产物不得再携带 md 字段的截断副本 `usage`（全仓零消费者，实测占 44,094B）
    legs.append(("产物无 usage 副本（只有 fit）",
                all("usage" not in e for d in (d10_data, d11_data, d12_data) for e in d["entries"])))


def _st_legs_real_face_mutation(tmp, legs):
    """腿 16-17：真面产物变异腿 + 未篡改对照腿（缺对照腿则 16 恒真）。"""
    # 16) 变异腿（r171 补齐 —— r134 清场重建时把这条丢了，docs/quality-gates.md 却一直在册，
    #     属「登记了却没有的桶」）：真面产物**改一个字节**必须与重建结果不一致。
    #     作业面 = Temp 副本，宿主文件字节前后同指纹（判据不得改写自己的宿主）。
    host = OUT
    host_before = host.read_bytes()
    rebuilt = render(parse_entries(CORPUS_DIR))
    cp = tmp / "artifact_mut.js"
    cp.write_bytes(host_before)
    t = cp.read_text("utf-8")
    mid = len(t) // 2
    tampered = t[:mid] + ("0" if t[mid] != "0" else "1") + t[mid + 1:]
    cp.write_text(tampered, encoding="utf-8", newline="\n")
    legs.append(("变异腿·真面产物改一字节必判不一致",
                 len(tampered) == len(t) and tampered != rebuilt
                 and cp.read_text("utf-8") != rebuilt
                 and host.read_bytes() == host_before))
    # 17) 对照腿（缺它则 16 是恒真）：未篡改的产物副本必须与重建结果**逐字节相等**
    cp2 = tmp / "artifact_pristine.js"
    cp2.write_bytes(host_before)
    legs.append(("对照·未篡改产物与重建逐字节相等", cp2.read_text("utf-8") == rebuilt))


def _st_legs_fit_card_direct(tmp, legs):
    """腿 18-20：卡面直写「适配提示」列的三腿（直写优先／超长 fail-fast／空值 fail-fast）。"""
    # 18) 卡面直写优先（r171 可选列「适配提示」）：人工写的触发子句必须盖过派生路径
    d13 = tmp / "fitcard"
    _write_card(d13, "01-CL-test.md",
                CARD_TMPL.format(**OK_CARD)
                .replace("用法：测试用法句。", "用法：这里先讲一大段概念与背景，触发条件写在后半句。")
                + "- 适配提示：用户说熬不下去了时\n")
    d13_data = parse_entries(d13)
    legs.append(("适配提示·卡面直写优先",
                d13_data["entries"][0]["fit"] == "用户说熬不下去了时"
                and d13_data["counts"]["fitSrc"]["card"] == 1
                and d13_data["counts"]["fitSrc"]["scene"] == 0))
    # 19) 反例：直写超上限 ⇒ fail-fast（注入预算按条算，静默截断会咬掉半句）
    d14 = tmp / "fitlong"
    _write_card(d14, "01-CL-test.md",
                CARD_TMPL.format(**OK_CARD) + "- 适配提示：" + "长" * (FIT_MAX + 1) + "\n")
    legs.append(("反例·适配提示超长 fail-fast",
                 _expect_fail(d14, "", "", "适配提示超长", write=False)))
    # 20) 反例：列写了但值为空 ⇒ fail-fast（空值会把直写位静默让给派生，等于假装有人修过卡）
    d15 = tmp / "fitempty"
    _write_card(d15, "01-CL-test.md", CARD_TMPL.format(**OK_CARD) + "- 适配提示：\n")
    legs.append(("反例·适配提示空值 fail-fast",
                 _expect_fail(d15, "", "", "适配提示为空", write=False)))


def _st_print_verdict(legs):
    """收口印结论（拆自 selftest 的收尾段）：分母现读 len(legs)，红腿逐条点名，返回 rc。"""
    bad = [name for name, ok in legs if not ok]
    print("WIT-QUOTES-SELFTEST-%s: %d/%d 腿（r171 加 fit 派生四腿＋零死重量＋真面变异腿＋对照腿＋直写位三腿；r134 重建 10 腿；原 r133 15 腿随清场丢失，见 docstring）"
          % ("PASS" if not bad else "FAIL", len(legs) - len(bad), len(legs)))
    for b in bad:
        print("   · 红腿: " + b)
    return 0 if not bad else 1


def selftest():
    """判据自证（r134 重建版 10 腿；原 r133 15 腿版随清场丢失，见 docstring 披露）。
    全部用临时目录构造的卡面，零网络零浏览器；正例绿 + 反例红，防恒真。

    本函数只留骨架（造夹具目录 → 按主题调四族桩 → 收口印结论）；桩体按主题边界升模块级
    （loc_guard 的「单函数 ≤150 行」门），legs.append 的顺序与每族的判定体逐字未改。"""
    import shutil
    import tempfile
    legs = []
    tmp = Path(tempfile.mkdtemp(prefix="wq_selftest_"))
    try:
        # 1) 正例：合法 A 级卡 → 1 条入库、字段齐全
        d1 = tmp / "ok"
        _write_card(d1, "01-CL-test.md", CARD_TMPL.format(**OK_CARD))
        d1_ok = parse_entries(d1)
        legs.append(("正例·合法卡入库 1 条", d1_ok["counts"]["total"] == 1
                     and d1_ok["entries"][0]["id"] == "QTE-CL-901"
                     and d1_ok["entries"][0]["level"] == "A"))
        # 2) 确定性：同输入两次 render 逐字节相等
        legs.append(("确定性·两次渲染逐字节相等", render(d1_ok) == render(parse_entries(d1))))
        _st_legs_bad_card_failfast(tmp, legs)
        _st_legs_fit_derive(tmp, legs)
        _st_legs_real_face_mutation(tmp, legs)
        _st_legs_fit_card_direct(tmp, legs)

        return _st_print_verdict(legs)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="重建并与磁盘产物逐字节比对")
    ap.add_argument("--selftest", action="store_true", help="判据自证（正例绿/反例红）")
    ap.add_argument("--dir", type=Path, default=CORPUS_DIR)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--index", action="store_true", help="同时生成/更新 源目录/索引.md（供取号与总览）")
    args = ap.parse_args()
    if args.selftest:
        return selftest()

    data = parse_entries(args.dir)
    text = render(data)
    if args.check:
        if not args.out.exists():
            fail("产物不存在（先不带 --check 跑一次重建）：" + str(args.out))
        old = args.out.read_text("utf-8")
        if old == text:
            print("WIT-QUOTES-BUILD-PASS %d 条（A%d/B%d/C%d/D%d，E 排除 %d，fit 直写%d/派生%d/回落%d）--check 与磁盘一致" % (
                data["counts"]["total"], data["counts"]["by_level"]["A"],
                data["counts"]["by_level"]["B"], data["counts"]["by_level"]["C"],
                data["counts"]["by_level"]["D"], data["counts"]["excludedE"],
                data["counts"]["fitSrc"]["card"], data["counts"]["fitSrc"]["derived"],
                data["counts"]["fitSrc"]["scene"]))
            return 0
        fail("--check 不一致：产物与重建结果不同（条目源被改过且未重建？）")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8", newline="\n")
    if args.index:
        rows = ["| %s | %s | %s | %s | %s |" % (
            e["id"], e["title"][:24], e["level"], CAT_NAMES[e["cat"]], "、".join(e["emo"]))
            for e in data["entries"]]
        idx = args.dir / "索引.md"
        idx.write_text(
            "# 表达语料库 · 索引\n\n"
            "> 自动生成（_test/wit_quotes_build.py --index），勿手改；供取号与总览。\n"
            "> 第 3 轮（r171，2026-10-13）：%d 条 A-D 级（E 级构建期排除 %d 条）；"
            "适配条件直写 %d 条／派生 %d 条／场景回落 %d 条。\n"
            "> 第 2 轮（r134，2026-10-13）：161 条 A-D 级（E 级构建期排除 0 条）。\n"
            "> 第 1 轮（r117，2026-10-12）：101 条 A-D 级（E 级构建期排除 0 条）。\n\n"
            "| 编号 | 标题 | 可信度 | 篇章 | 适用情绪 |\n|---|---|---|---|---|\n%s\n"
            % (data["counts"]["total"], data["counts"]["excludedE"],
               data["counts"]["fitSrc"]["card"], data["counts"]["fitSrc"]["derived"],
               data["counts"]["fitSrc"]["scene"], "\n".join(rows)),
            encoding="utf-8", newline="\n")
        print("INDEX -> %s（%d 行）" % (idx, len(rows)))
    print("WIT-QUOTES-BUILD-PASS 已重建 %s：%d 条（A%d/B%d/C%d/D%d，E 排除 %d，fit 直写%d/派生%d/回落%d）" % (
        str(args.out).replace(str(ROOT) + "\\", "").replace(str(ROOT) + "/", ""),
        data["counts"]["total"], data["counts"]["by_level"]["A"],
        data["counts"]["by_level"]["B"], data["counts"]["by_level"]["C"],
        data["counts"]["by_level"]["D"], data["counts"]["excludedE"],
        data["counts"]["fitSrc"]["card"], data["counts"]["fitSrc"]["derived"],
        data["counts"]["fitSrc"]["scene"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())