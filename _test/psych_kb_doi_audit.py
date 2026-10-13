# -*- coding: utf-8 -*-
"""psych_kb_doi_audit.py — 知识库 **引用错配** 审计判据（r173-KB13 立）

背景（`--links` 探活单独不够）：
  r167 轮曾抓出四处「DOI 存在 / 链接可达，但与之并列的作者、年份、题名对不上」的错引
  ——BFI-2 编制论文实为 Soto & John (2017) 非 2008、Ktzyk et al. (2019) PLOS ONE 查无此文、
  Koepp et al. (2014) 全 0 命中、Kroenke 2001 任务书 DOI 实测 404。
  这类错误**探活探不出来**（URL 是活的、甚至 DOI 也是真的），只有把「卡面引文」与
  「Crossref/OpenAlex 权威题录」逐字段比对才能发现。本判据把这一步从人工纪律变成机器面。

比对三字段：
  F1 年份 —— Crossref issued/published 年份必须出现在该来源行里 ⇒ 判红
  F2 作者 —— 至少 1 位作者姓氏出现在该来源行里                    ⇒ 判红
  F3 题名 —— English title 实词命中率不足                          ⇒ **仅 WARN，不判红**
      为什么不判红：README §2 对「规范文献引文」的强制要素是**作者、年份、出处**三项，
      题名并非必写；卡面大量来源行按中文行式写成 `[论断] 作者 (年份) 出处 DOI …`，
      本就把题名省略了。首跑 22 条即命中 9 条，其中 8 条全是这类「写了作者年份出处、
      没写英文题名」的合规行 ⇒ 把 F3 判红只会刷出一屏假红。故 F3 降级为提示。

抽取面纪律（首跑即触发，勿回避）：
  来源行里常写 `DOI 10.xxxx（2026-10-12 Crossref 核实）` 或 `...708867/full`，
  裸正则会把「（日期…）」和 URL 的 /full 后缀一并吞进 DOI ⇒ 查出来 404 ⇒ **假红**。
  故 `_clean()` 遇非 ASCII 字符即截断、`_variants()` 额外退化到 `10.<reg>/<一段>` 重试。
  这是「尺自己坏风向第四类」的典型面：先修尺，再谈飞镖结果。

  `- 更正：` 行**跳过**（撤链留痕不算活引用，与 integrity_check --links 同一口径）。

抽取面自检门（r177-KB14 立，闭环第 13 轮遗留 N2）：
  r131 为 `integrity_check --links` 立的纪律——「抽取面吐出含非 ASCII 的串 ⇒ rc=1 并作废本次读数
  （那是尺自己坏了）」——在 r173 只写进了 docstring、**没做成守卫**（N2 遗留项）。
  本脚本的 `scan_doi`/`_clean` 字符白名单本身就是 ASCII，正常路径永不触发该门；
  它是**不变量断言**：一旦未来有人为「兼容全角括号/CJK」放宽字符集，脏串会被静默查成
  假 404（假红）或假 200（假绿）⇒ 本门立刻 fail-closed 作废读数，而不是放行。
  判据腿见 `--selftest`（含「把 scan_doi 打成返回非 ASCII ⇒ 必须 rc=1」的变异腿，证门非恒真）。

为什么不带 build 那种确定性前缀：本脚本是**联网**件 —— README §7 定「联网 ⇒ 只作人工轮次
工具，不进回归电池与 CI」，故它的读数不参与 BuildSuites 的 GREEN/RED，只作人工轮次取证工具。
网络不可达时 **rc=2 UNVERIFIED** —— 取不到读数既不判绿也不判红（与 integrity_check 同语义）。

用法：
  python _test/psych_kb_doi_audit.py                                  # 全库
  python _test/psych_kb_doi_audit.py --file 31-心理测量与筛查量表.md    # 单篇
  python _test/psych_kb_doi_audit.py --limit 30                       # 只审前 N 行（探水路）
  python _test/psych_kb_doi_audit.py --selftest                       # 不联网自证（夹具在临时目录）
退出码：0=无硬性错配 1=发现错配(F0/F1/F2) **或抽取面自检门 fail-closed** 2=网络不可核 3=输入面缺失
"""
import json
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
KB_DIR = ROOT / "交付物" / "心理学知识库"

DOI_HEAD_RE = re.compile(r"\b10\.\d{4,9}/")   # 只定位起点，边界交给 scan_doi 的括号平衡算法
ENTRY_RE = re.compile(r"^### 条目 (PSY-[A-Z]+-\d{3})｜(.+?)\s*$")
# 注意：不含 `[`/`]`（r173 实测卡面 `- […] DOI 10.1111/xxx.x]]` 会把右方括号粘进 DOI，
# 查出来 404 ⇒ 假红。DOI 后缀含方括号的极罕见，宁可截断也不当 Blender。
OK_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._;-/():+<>=")
STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "into", "over", "under",
    "your", "their", "how", "why", "what", "all", "new", "you", "via", "not",
    "but", "does", "effect", "effects", "study", "more", "than",
}
UA = "xinyu-kb-doi-audit/1.0 (mailto:xinyu-audit@localhost)"


def _clean(raw):
    """截断到第一个非 DOI 合法字符为止（含中文全角括号），并去掉句读尾巴。"""
    out = []
    for ch in raw:
        if ch in OK_CHARS:
            out.append(ch)
        else:
            break
    return "".join(out).rstrip(".,;:/")


def _variants(cleaned):
    """[完整 cleaned] + [退化为 10.<reg>/<一段>]——URI 里常多带 /full /abstract 等平台后缀。"""
    vs = [cleaned]
    seg = cleaned.split("/")
    if len(seg) > 2:
        vs.append("/".join(seg[:2]))
    seen, out = set(), []
    for v in vs:
        v = v.strip("/") if v.count("/") < 1 else v
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out


def scan_doi(line, start):
    """从 line[start:] 起按**括号平衡**扫出 DOI 边界。

    为什么不能只用固定的排除字符集：真实 DOI 有两种互斥形态 ——
      a) Elsevier 老式内含年份括号，如 10.1016/s0005-7967(97)00070-3：必须**允许**内部 `()`；
      b) 行尾粘过来的 `(PMID…)` / 全角括号：一旦允许 `(` 就会把后面中文一并吞进 DOI ⇒ 假 404。
    平衡算法同时满足两者：`(` 计数 +1、`)` 计数 -1，计数转负立即停；
    扫完若仍有未闭合 `(`，回退到最后一个计数归零的位置。
    """
    bal, end, last_bal = 0, start, start
    for i in range(start, len(line)):
        ch = line[i]
        if ch in OK_CHARS or ch in "()":
            if ch == "(":
                bal += 1
            elif ch == ")":
                bal -= 1
                if bal < 0:
                    break
                if bal == 0:
                    last_bal = i + 1
            end = i + 1
        else:
            break
    return line[start:(last_bal if bal > 0 else end)].rstrip(".,;:/")


def _get(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout,
                                context=ssl.create_default_context()) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def crossref(doi):
    d = _get("https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="/"))
    msg = d.get("message", {})
    authors = [a.get("family", "").strip() for a in (msg.get("author") or []) if a.get("family")]
    years = set()
    for key in ("issued", "published-online", "published-print", "created"):
        parts = ((msg.get(key) or {}).get("date-parts") or [[]])[0]
        if parts and parts[0]:
            years.add(int(parts[0]))
    return {
        "title": ((msg.get("title") or [""])[0] or "").strip(),
        "authors": authors, "years": sorted(years),
        "container": ((msg.get("container-title") or []) or [""])[0],
    }


def openalex(doi):
    d = _get("https://api.openalex.org/works/doi:" + urllib.parse.quote(doi, safe="/"))
    authors = [a["author"]["display_name"].split()[-1] for a in (d.get("authorships") or [])]
    return {
        "title": (d.get("title") or "").strip(),
        "authors": [a for a in authors if a],
        "years": sorted({int(d["publication_year"])}) if d.get("publication_year") else [],
        "container": ((d.get("primary_location") or {}).get("source") or {}).get("display_name") or "",
    }


def resolve(doi, attempts=4):
    """返回 (meta, err)；err == '404' 表示**重试后仍**确实查无 —— 不经重试不算数。

    为什么必须重试剔除：r173 首跑全库时并发 6 连发 483 个 DOI，Crossref/OpenAlex 边缘被限流，
    返回体被中间件换成 404 ⇒ 178 条「查无此文献」假红，其中含 `10.1038/nature03086`
    （Adolphs 2005 Nature，硬通货）。定点单线程复测同一批 DOI 全部 200 ⇒ **红的是尺不是库**。
    故：网络类异常一律退避重试；只有耗尽重试仍 404 才判 F0。
    """
    # r173 踩坑根因：首版 resolve 直接拿**未清洗**的抽取串去查 API ——
    # 行尾部串进来的「（2026-10-12 Crossref 核实）」会被当 DOI 后缀 ⇒ Crossref 回 404 ⇒ 假红，
    # 且因为输出打印时才 _clean()，屏幕上看着是干净的 DOI，误导性极强。清洗必须发生在查询之前。
    doi = _clean(doi)
    if not doi:
        return None, "empty-after-clean"
    last_net = None
    for cand in _variants(doi):
        for fn in (crossref, openalex):
            for k in range(attempts):
                try:
                    return fn(cand), None
                except urllib.error.HTTPError as e:
                    last_net = str(e.code)
                    # 关键：连 404 也要退避重试。实测限流期来自边缘节点的「伪 404」与真 404
                    # 返回体无法区分，只有让请求间隔拉大后复 differ 才拿得到真读数。
                    if k < attempts - 1:
                        time.sleep(1.5 * (k + 1))
                except Exception as e:
                    last_net = type(e).__name__
                    if k < attempts - 1:
                        time.sleep(1.5 * (k + 1))
    return None, (last_net or "unreachable")


CACHE = ROOT / "_temp" / "kb-r173" / "doi_cache.json"


def load_cache():
    if CACHE.is_file():
        try:
            return json.loads(CACHE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_cache(c):
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(c, ensure_ascii=False, indent=0), encoding="utf-8")


def _tokens(title):
    return {w.lower() for w in re.findall(r"[A-Za-z]{4,}", title) if w.lower() not in STOPWORDS}


def check_line(line, meta):
    """返回 (hard, warn)：hard 判红，warn 仅提示。"""
    low = line.lower()
    hard, warn = [], []

    if meta["years"] and not any(str(y) in line for y in meta["years"]):
        yrs = [int(x) for x in re.findall(r"(?:19|20)\d{2}", line)]
        if any(abs(a - b) <= 1 for a in yrs for b in meta["years"]):
            # 差 1 年：几乎总是「在线优先年」 vs 「正式卷次年」两种合法口径（如 NHB 9 卷 2025
            # 但 online-first 2024），判红会逼人改成错的那个 ⇒ 降为提示。
            warn.append(("F1年份±1", "Crossref 记 %s，行内 %s（在线优先/卷次年口径差异，需人工确认）"
                         % (sorted(meta["years"]), sorted(set(yrs)))))
        else:
            hard.append(("F1年份", "Crossref 记 %s，行内未见" % sorted(meta["years"])))

    if meta["authors"] and not any(a.lower() in low for a in meta["authors"]):
        # 团体作者的合法写法：CTFPHC/WHO/学会指南在 Crossref 里登记的是**个人作者**，
        # 卡面按规范写团体名（如 Canadian Task Force on Preventive Health Care）——
        # 这不是错引，判红会逼人把团体名改成个人名。故机构名在行 ⇒ 降为提示。
        if re.search(r"(task force|institute|association|organisation|organization|committee|"
                     r"society|consortium|group|WHO|ministry|college| academy)", line, re.I):
            warn.append(("F2团体作者", "卡面写团体作者，Crossref 登记个人作者 %s —— 口径差异，非错引"
                         % meta["authors"][:3]))
        else:
            hard.append(("F2作者", "Crossref 作者 %s 均未在行内出现" % meta["authors"][:3]))

    toks = _tokens(meta["title"])
    if toks:
        hit = {t for t in toks if t in low}
        need = max(3, int(len(toks) * 0.3)) if len(toks) >= 10 else min(3, len(toks))
        if len(hit) < need:
            warn.append(("F3题名", "行内未附英文题名（缺失≥%d词）；Crossref题名=%r" % (need, meta["title"])))
    return hard, warn


def _segment(line, pos):
    """取 DOI 所在的**片段**作比对范围。

    为什么不能整行比对：卡面常在一条来源行里顺带提到别的 DOI（如 `- 内容：…Vogel (2006) DOI:10.1037/…
    ，…；另一出处 DOI:10.3389/…`），整行比对会把第二个 DOI 的作者要求施加到只写了前一条作者的行上
    ⇒ 假红。按 `；/`｜` 切片段后各归各的。
    """
    bounds = [len(line)]
    for ch in "；;｜|\n":
        i = line.find(ch, pos)
        if i >= 0:
            bounds.append(i)
    start = 0
    for ch in "；;｜|\n":
        j = line.rfind(ch, 0, pos)
        if j >= 0:
            start = max(start, j + 1)
    end = min(bounds)
    seg = line[start:end]
    # 片段里除 URL/DOI 之外几乎没文本 ⇒ 多半是 DOI 藏在 `https://doi.org/…` 里、
    # 同片段的作者信息在被切掉的那半段（r173 实测触发：25-32 篇一次刷出 111 条假红）⇒ 回退用整行。
    probe = re.sub(r"https?://\S+", "", seg)
    probe = re.sub(r"\b10\.\d{4,9}/\S+", "", probe)
    return seg if len(probe.strip()) >= 12 else line


def extraction_gate(rows):
    """抽取面自检门（r177-KB14 立）：DOI 抽取串必须纯 ASCII，否则尺坏 ⇒ 作废读数。

    返回 broken 列表（空 = 门放行）。纪律出处 = r131（integrity_check --links 的同名门），
    r173 轮只写在 docstring 未做守卫（第 13 轮遗留 N2），本函数补上。
    为什么必须 fail-closed 而不是放行：含非 ASCII 的串拿去查 Crossref 要么假 404（假红）、
    要么被平台容错成 200（假绿）——两种都会让整轮读数不可信，而屏幕上 DOI 看着还是干净的。
    """
    broken = []
    for name, entry, line, doi, seg, ndoi in rows:
        bad = sorted({c for c in doi if ord(c) > 127})
        if bad:
            broken.append((name, entry, doi, bad))
    return broken


def collect(files):
    rows = []
    for p in files:
        cur = "（篇章）"
        for ln in p.read_text(encoding="utf-8").splitlines():
            m = ENTRY_RE.match(ln)
            if m:
                cur = m.group(1)
                continue
            s = ln.strip()
            if s.startswith("- 更正：") or s.startswith("- 待验证点："):
                continue      # 撤链留痕 / 缺口描述里的 DOI 只是转述提及，不是引用行
            if s.startswith(">"):
                continue      # 篇章头的「> 取证口径：…」纪要行，内含多 DOI 但无作者 ⇒ 不属引用行
            hits = [scan_doi(ln, h.start()) for h in DOI_HEAD_RE.finditer(ln)]
            hits = [h for h in hits if h]
            for m in DOI_HEAD_RE.finditer(ln):
                doi = scan_doi(ln, m.start())
                if doi:
                    rows.append((p.name, cur, ln.strip(), doi, _segment(ln, m.start()), len(hits)))
    return rows


def selftest():
    """--selftest：不联网、不读仓库面（夹具建在系统临时目录），只证抽取面与自检门。

    三腿：
      ① 正常抽取腿：干净行 + Elsevier 老式 `(97)` 行 → 抽出 DOI 与预期逐字相等
         （一行两处 DOI——显式 `DOI x` 与 URL 内 DOI——各出一行，既有行为照钉）；
      ② 反证腿：①的干净行过门必须零命中——否则②判红可能来自「门常红」，证明不了门有分辨力；
      ③ 门非恒真腿（变异）：把 scan_doi 打成返回含 CJK 的串 ⇒ extraction_gate 必须全量报坏。
    """
    import tempfile
    legs = []

    def leg(name, ok, detail=""):
        legs.append((name, bool(ok), detail))

    with tempfile.TemporaryDirectory() as td:
        kb = Path(td) / "kb"
        kb.mkdir()
        f = kb / "99-gate-selftest.md"
        f.write_text(
            "### 条目 PSY-XX-999｜自检夹具\n"
            "- 来源：\n"
            "  - [干净行] Doe, J. (2020). Title. Journal. DOI 10.1000/clean123；"
            "https://api.crossref.org/works/10.1000/clean123\n"
            "  - [Elsevier 老式] Roe, R. (1997). Title. Journal. DOI 10.1016/s0005-7967(97)00070-3；"
            "https://doi.org/10.1016/s0005-7967(97)00070-3\n",
            encoding="utf-8")
        rows = collect([f])
        dois = [r[3] for r in rows]
        # 每行 2 个 DOI_HEAD_RE 命中（显式 DOI + URL 内 DOI）⇒ 预期为翻倍 multiset
        expect = ["10.1000/clean123", "10.1000/clean123",
                  "10.1016/s0005-7967(97)00070-3", "10.1016/s0005-7967(97)00070-3"]
        leg("干净行+Elsevier(97) 抽取逐字正确", dois == expect, "got=%r" % dois)
        gate_clean = extraction_gate(rows)
        leg("反证：干净行过门零命中", gate_clean == [], "broken=%r" % gate_clean)

        orig = globals()["scan_doi"]
        try:
            globals()["scan_doi"] = lambda line, start: "10.1234/坏串-尺坏了"
            rows_bad = collect([f])
        finally:
            globals()["scan_doi"] = orig
        broken = extraction_gate(rows_bad)
        leg("变异：scan_doi 吐出非 ASCII ⇒ 门必须 fail-closed",
            len(rows_bad) > 0 and len(broken) == len(rows_bad),
            "broken=%d/%d" % (len(broken), len(rows_bad)))

    ok = all(x[1] for x in legs)
    for name, passed, detail in legs:
        print("  %s %s%s" % ("PASS" if passed else "FAIL", name,
                             ("（%s）" % detail) if (detail and not passed) else ""))
    print("KB-DOI-AUDIT-SELFTEST-%s: %d/%d 腿过"
          % ("PASS" if ok else "FAIL", sum(1 for x in legs if x[1]), len(legs)))
    return 0 if ok else 1


def main(argv):
    if "--selftest" in argv:
        return selftest()
    file_filter = limit = None
    for i, a in enumerate(argv):
        if a == "--file" and i + 1 < len(argv):
            file_filter = argv[i + 1]          # 逗号分隔多个文件名子串，便于分批续跑
        if a == "--limit" and i + 1 < len(argv):
            limit = int(argv[i + 1])
        if a == "--clear-err":
            c = load_cache()
            for k in [k for k, v in c.items() if v.get("v") is None]:
                c.pop(k)
            save_cache(c)
            print("已清上次失败缓存 %s" % CACHE)

    if not KB_DIR.is_dir():
        print("KB-DOI-AUDIT-ERROR: 输入面缺失 %s" % KB_DIR)
        return 3
    # 审计面 = 篇章文件（两位数字前缀）。README.md 的 §3 是**模板示例**、
    # 索引.md 的变更记录行会整段引 DOI —— 两者都不是条目来源行，纳进来只会刷假红（r173 首跑实测）。
    files = sorted(f for f in KB_DIR.glob("*.md") if re.match(r"^\d{2}-", f.name))
    if file_filter:
        keys = [k.strip() for k in file_filter.split(",") if k.strip()]
        files = [f for f in files if any(k in f.name for k in keys)]
        if not files:
            print("KB-DOI-AUDIT-ERROR: 无匹配文件 %s" % file_filter)
            return 3

    rows = collect(files)
    if limit:
        rows = rows[:limit]

    # 抽取面自检门先于任何网络查询：尺坏时绝不拿脏串去刷读数（r177-KB14 闭环 N2）。
    # 顺序很重要——门若排在网络查询之后，坏尺已经产出一批缓存读数，作废就只剩口头作废。
    broken = extraction_gate(rows)
    if broken:
        print("KB-DOI-AUDIT-GATE-BROKEN: 抽取面吐出含非 ASCII 的 DOI 串 %d 条 ⇒ 作废本次读数（尺坏，非库错）"
              % len(broken))
        for name, entry, doi, bad in broken[:5]:
            print("  · %s · %s · %r（非 ASCII: %s）" % (name, entry, doi, "".join(bad)))
        return 1

    # 同名 DOI 只解析一次。网络件**禁用高并发**（r173 教训：并发 6 ⇒ 边缘限流伪装 404），
    # 取 2 并发 + 磁盘缓存（重跑只补查上次失败者，可续跑、不必一次吃到超时）。
    cache = load_cache()
    raws = sorted({r[3] for r in rows})
    todo = [r for r in raws if cache.get(r, {}).get("v") is None]
    if todo:
        with ThreadPoolExecutor(max_workers=2) as ex:
            for raw, (meta, err) in zip(todo, ex.map(resolve, todo)):
                cache[raw] = {"v": meta, "e": err} if meta is not None else {"v": None, "e": err}
        save_cache(cache)

    hard_rows, warn_rows, unver = [], [], 0
    for name, entry, line, raw, seg, ndoi in rows:
        rec = cache.get(raw) or {}
        meta, err = rec.get("v"), rec.get("e")
        if meta is None and err == "404":
            hard_rows.append((name, entry, line, _clean(raw), [("F0查无此文献", "Crossref/OpenAlex 均无此 DOI")]))
            continue
        if meta is None:
            unver += 1
            continue
        # 比对范围取**整行**：片段化会漏掉写在 DOI 前面的作者/年份（r173 实测 25-32 篇一次假红 111 条），
        # 而「一行多 DOI 归属不定」由下面的 ndoi>1 降级规则兜住，不需要靠切花 activeFragment。
        h, w = check_line(line, meta)
        if h and ndoi > 1:
            # 一行多个 DOI 时，作者/年份归属到哪个 DOI 无法可靠判定 ⇒ 不判红，留给人工。
            warn_rows.append((name, entry, line, [("多行一DOI", "本行 %d 个 DOI，无法可靠归属；疑似 %s：%s"
                                                   % (ndoi, h[0][0], h[0][1][:60]))]))
        elif h:
            hard_rows.append((name, entry, line, _clean(raw), h))
        elif w:
            warn_rows.append((name, entry, line, w))

    print("KB-DOI-AUDIT: 来源行数=%d｜唯一 DOI=%d｜不可核=%d｜硬性错配=%d｜题名未附(仅提示)=%d"
          % (len(rows), len(raws), unver, len(hard_rows), len(warn_rows)))
    for name, entry, line, doi, probs in hard_rows:
        print("\n[错配] %s · %s" % (name, entry))
        print("  DOI  : %s" % doi)
        print("  行   : %s" % (line[:190] + ("…" if len(line) > 190 else "")))
        for k, v in probs:
            print("  · %s：%s" % (k, v))
    if argv and "--verbose" in argv:
        for name, entry, line, w in warn_rows[:20]:
            print("  ~ %s · %s · %s" % (name, entry, w[0][1][:80]))

    if unver and not hard_rows:
        print("KB-DOI-AUDIT-UNVERIFIED: %d 条取不到题录读数，既不判绿也不判红" % unver)
        return 2
    if hard_rows:
        print("PSYCH-KB-DOI-AUDIT-FAIL: %d 条硬性错配（F0/F1/F2）" % len(hard_rows))
        return 1
    print("PSYCH-KB-DOI-AUDIT-PASS: 引用作者/年份与权威题录一致（%d 行，另有 %d 行未附英文题名）"
          % (len(rows), len(warn_rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
