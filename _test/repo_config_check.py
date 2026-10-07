# -*- coding: utf-8 -*-
"""仓库配置自洽守卫（r22）：让"配了但没生效/文档与配置对不上"变得可机器发现

动机（两处真实经历）：
  - r21 加了 `.github/dependabot.yml`，但**配置存在 ≠ 被受理**：dependabot 只读默认分支上该文件，
    且 ecosystem 名 / directory 拼错时 GitHub 只会静默不跑（本地无任何报错）。
  - 本项目文档里散落着"四条门禁 / 26 套件"这类**数字断言**，改配置或加套件时极易与实值脱节
    （AGENTS.md 的 04/05 段就已长期陈旧，是同一类问题的既成实证）。

判据（逐项独立，G1–G4、G6–G7 离线恒跑；G5 需 --online）：
  G1 dependabot schema：version==2、ecosystem 在支持清单内、`directory` 指向**仓库里真实存在**的目录；
     G1b(r50) maven 必须配 ignore 大版本（实测 PR#2 spring-boot 3.2.5→4.1.1 常红），actions 侧无此症状故不扩面
     schedule.interval 合法、PR 上限为整数
  G2 CI 拓扑：`.github/workflows/ci.yml` 可解析，且 job 数 == README 声称的"N 条门禁"（数字对不上即红）
  G3 契约可发现：`docs/openapi.yaml` 存在、可解析，且被 `docs/README.md` 引用（孤文件即红）
  G4 判据清单自洽：`run_all_suites.py` 的 SUITES 条目数 == README 声称的"（N 套件）"
  G14 对标仓数自洽：README 的现行状态句「对标源数据台账（N 仓指标」== 台账 `peers_expected`
     （只锚现行句：历史轮次里的"14 仓"当时就是 14，宽口径会误伤）
  G5（--online）远端受理面：默认分支上 `.github/dependabot.yml` 确实存在（GitHub 只看默认分支）
  G6 第三方授权：**分母从 `_test/vendor-manifest.json` 现读**（不再写死 src/vendor），
     每个 vendored 文件都必须在 `docs/THIRD-PARTY-NOTICES.md` 有**带许可条款的表行**；
     名册含非 src/ 件时归属文必须显式交代 `_test/vendor` 边界（r46 补，同族第二处盲区）
  G7 README 必须含指向该授权清单的口径行（否则读者只会看到"MIT"，而 GSAP 其实不是 MIT）
  G8 --selftest：合成篡改类**逐轮累积**（条数以 --selftest 实际输出为准，正文不抄数字——
     抄过两次都脱节）：ecosystem 拼错 / 目录不存在 / interval 非法 / updates 清空 / 抹 gsap 登记 /
     抹 README 引用 / 抹评测集行 / 评测条数改小 / 删整节 / 表退回模板原句 / 无 __main__ 守卫 /
     CI 只跑单条判据 / CI 不声明豁免 / 幽灵豁免
     必须各自报红，原样必须零问题 —— 证判据非恒真
  G9 判据脚本 import-safe：`_test/*.py` 的顶层入口调用（sys.exit(main()) 等）必须落在
     `if __name__ == "__main__":` 守卫之后 —— 判据脚本会被互相 import（--only 自查 / 聚合 runner 对账 /
     CI 复用），无守卫 = "一 import 就跑全套或跑网络，且退出码 0"（r26 实测第五次同族坑）。
     三腿：① import-safe ② 解析得动 ③ 块内非首条裸字符串（r90：`def lag_days` 被编辑吞掉后
     原 docstring 变成 `return` 之后的裸字符串，**py_compile 与 selftest 全过**，只有这条腿看得见；
     覆盖面=`_test/*.py` 顶层 86 文件实测 0 误报，不覆盖面=server/ 与仓库外的自写脚本）
  G10 判据必须挂在**真会走的路径**上：CI 步骤里要整跑电池（run_all_suites.py）且声明 --exclude-llm 豁免，
  豁免项必须是真实存在的套件（幽灵豁免=恒真风险）。根因两条：① 本项目 CI 长期只跑 browser_check 一条，
     r26-r28 新加的 patch_apply / settings_panel / offline_shell 全在发布路径之外（本地绿≠有人管）；
     ② 同行实证 CodeQL 30 次全 success 但 refs/heads/main 分析数为 0——有运行记录不等于覆盖主路径。

  G11 依赖清单对账：判据脚本 import 的第三方包 == `_test/requirements.txt`，且每个跑判据的 CI job 都装了它
  G12 版本断言三源对账：`git tag` 最大值 == `server/pom.xml` <version> == 文档「当前版本：**vX.Y.Z**」
  G15 AC 追溯键唯一性棘轮：08 一个 id 只挂一条命题（存量 7 按基线放行，新增重复即红）
  G16 电池脚本 ⇄ `docs/quality-gates.md` 明细双向对账：电池里跑的 `_test/*.py|js` 必须在该文档出现，
     文档写了而 `_test/` 查无此件也算红（r57 实证：该文档被当作"判据清单"读，而 44 条套件里 16 条从未在其中，
     同族根因 M5⑥ 一处清单两处实现；分母从 SUITES 现读，零分母不判绿）
  G19 `docs/` 真实文件 ⇄ `docs/README.md` 索引双向对账（r89）：磁盘上的每份文档都必须被索引链接（幽灵引文也算红）。
     动因：r87 交付 API/EXTENSIONS/PERF-BASELINE 三本手册后索引仍只列 openapi.yaml ⇒ 写了但没人找得到；
     原 G3 只问"openapi 被引用了吗"，对其余文档零覆盖（拿存在性结论冒充目录完整性）
  G17 对标台账 self 行的**取数面必须显式为 git HEAD**（r72，[推荐:R71-01] 的机器落点）：
     缺 `self_face` / 值非 HEAD / `self_face_errors` 非空 / `regression_suites` 非正整数 ⇒ 红。
     动因（r71 一手）：`self_metrics()` 曾一半走 git、一半 `rglob` 工作树，同一行里
     `regression_suites=101`（含并行会话未入库的 2 条）与真值 99 并存、零报错，
     台账被下一轮当"横向现状"抄走就追不回责任方。台账记的套件数与 HEAD 现算值的**差值只印不拦**
     ——CI 里无法重跑联网采集来刷新台账，拦它就是造一条不可自愈的红（违 R-10 进链前三问）
  G18 聚合器收口行的 rc 必须由**真退出码**派生（r74，`_test/run_all_suites.py:584` 一手）：
     该行原为 `print(f"BATTERY: … rc=0")` 的字面量，退出码却在下面才 `return` ⇒ 本地整跑 rc=1、
     同 SHA 的 CI 两个 job failure，两处日志都还印着 `rc=0`。判据取 **HEAD 正文**（工作树可能混着
     他人未入库 hunk：既不能把别人现场算成我的红，也不能被他人在途态掩护），要求
     ①存在 BATTERY 摘要行 ②该行 rc 是 `{...}` 插值而非数字字面量 ③存在 `return bat_rc|rc` 的同源返回。
     取不到正文／没有摘要行一律判红（R247：无对象可判不得静默放行）
  G13 判据账本自洽：本文件头部登记的 G 清单与 `main()` 里实际执行的 check("G..") 一一对应
     —— 漏登记与幽灵登记都判红（这条由 G13 自己盯着自己，根因见 guard_inventory 的 docstring）

退出码：0=REPO-CONFIG-PASS 1=任一判据失败 2=环境异常（缺 PyYAML / --online 但 gh 不可用）
"""
import argparse
import ast
import json
import re
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
# 模块级抓头部说明：函数内的 `__doc__` 是**该函数自己的** docstring，拿它当清单会读到空
# ⇒ G13 会把"自己没登记"误判成别人漏登记（写这条时当场自抓到的一次误归因）。
HEADER_DOC = __doc__ or ""
SUPPORTED_ECO = {"npm", "pip", "maven", "gradle", "github-actions", "docker", "cargo",
                 "composer", "mix", "nuget", "terraform", "gofmod", "gomod", "bundler", "pub"}
INTERVALS = {"daily", "weekly", "monthly", "quarterly", "yearly"}
results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  -> {detail}" if detail else ""))


def load_yaml(rel):
    import yaml
    return yaml.safe_load((ROOT / rel).read_text("utf-8"))


def validate_dependabot(cfg):
    """纯函数：返回问题清单（G1 与 G6 共用）。"""
    bad = []
    if not isinstance(cfg, dict) or cfg.get("version") != 2:
        return [f"dependabot version 必须为 2，实际 {cfg.get('version') if isinstance(cfg, dict) else cfg}"]
    ups = cfg.get("updates") or []
    if not ups:
        return ["updates 为空：等于没配任何依赖监控"]
    for u in ups:
        eco, d = u.get("package-ecosystem"), u.get("directory", "/")
        if eco not in SUPPORTED_ECO:
            bad.append(f"ecosystem {eco!r} 不在 GitHub 支持清单内（会静默不跑）")
        rel = (ROOT / d.lstrip("/")) if d != "/" else ROOT
        if not rel.exists():
            bad.append(f"directory {d!r} 在仓库里不存在（ecosystem 找不到 manifest）")
        elif d != "/" and eco == "maven" and not (rel / "pom.xml").exists():
            bad.append(f"maven@{d} 目录下没有 pom.xml")
        elif d != "/" and eco == "npm" and not (rel / "package.json").exists():
            bad.append(f"npm@{d} 目录下没有 package.json")
        if (u.get("schedule") or {}).get("interval") not in INTERVALS:
            bad.append(f"{eco} schedule.interval 非法：{(u.get('schedule') or {}).get('interval')}")
        if not isinstance(u.get("open-pull-requests-limit", 5), int):
            bad.append(f"{eco} open-pull-requests-limit 不是整数")
        # G1b 依赖升级策略（r50 加；按证据**只对 maven 要求**，不给 actions 也上一道）：
        #   同时成立的两条实测 —— `actions/checkout 4→7`、`setup-python 5→7` 这类 major 升级
        #   我们**正常合并过**（PR #1/#3，merged_at 有值）；而 dependabot PR #2 提的
        #   `spring-boot-starter-parent 3.2.5→4.1.1`（跨大版本）从 09-24 挂到 r50，
        #   java-build 与浏览器回归两条 job 直接 fail ⇒ 这张 PR 结构性不可能通过。
        #   结论不是"dependabot 没用"，是"配置在册 ≠ 策略成立"：一张永远红的 PR 挂着，
        #   等于把自动化的收益换成常 noise，还会掩盖真正该看的那张。
        if eco == "maven":
            ig = u.get("ignore") or []
            if not any(re.search(r">=\s*\d", str(v)) for i in ig
                       for v in (i.get("versions") or [])):
                bad.append("maven 未配 ignore 大版本 ⇒ 会持续收到结构性不可能合并的 major PR"
                           "（实测 PR #2 spring-boot 3.2.5→4.1.1 常红）")
    return bad


def ci_jobs():
    return list((load_yaml(".github/workflows/ci.yml").get("jobs") or {}).keys())


def readme_claims():
    txt = (ROOT / "README.md").read_text("utf-8", errors="replace")
    jobs = re.search(r"GitHub Actions\s*([一二三四五六七八九十\d]+)\s*条门禁", txt)
    suites = re.search(r"全量电池（(\d+)\s*套件", txt) or re.search(r"★ 全量电池（(\d+)\s*套件", txt)
    digits = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}

    def num(s):
        return int(s) if s and s.isdigit() else digits.get(s or "", None)
    return num(jobs.group(1)) if jobs else None, (int(suites.group(1)) if suites else None)


def battery_count():
    txt = (ROOT / "_test" / "run_all_suites.py").read_text("utf-8", errors="replace")
    seg = txt.split("SUITES = [", 1)[1].split("\n]", 1)[0]
    return len(re.findall(r'^\s*\("', seg, re.M))


def battery_scripts():
    """电池 SUITES 真正调用的 `_test/` 脚本名集合（分母从代码现读，不从文档现读）。

    为什么单独取这一份而不是 `os.listdir('_test')`：目录里有大量**没接线**的一次性脚本
    （截图/CORS 探针…），把它们一律要求登记会把"文档"变成"目录镜像"，那是另一个维度。
    本条守的是"会阻断发布的判据 ⇄ 被当作判据清单来读的那份文档"这一对真相。
    """
    txt = (ROOT / "_test" / "run_all_suites.py").read_text("utf-8", errors="replace")
    seg = txt.split("SUITES = [", 1)[1].split("\n]", 1)[0]
    return {p.split("/")[-1] for p in re.findall(r'"_test/([^"]+?\.(?:py|js))"', seg)}


def git_index_scripts():
    """git index 面的 `_test/` 脚本名；取不到返回 None（该腿未验，不是通过）。"""
    r = subprocess.run(["git", "-C", str(ROOT), "ls-files", "--cached", "--", "_test"],
                       capture_output=True, timeout=60)
    if r.returncode != 0:
        return None
    return {p.split("/")[-1] for p in (r.stdout or b"").decode("utf-8", "replace").splitlines()
            if p.strip()}


def gate_doc_audit(scripts, doc_text, on_disk, tracked=None):
    """G16 纯函数：电池脚本 ⇄ docs/quality-gates.md ⇄ git 三面双向对账。

    立此条的实证（r57）：`docs/quality-gates.md` 头部写着「本文件不抄数」，所以**数字**没骗人，
    但它是 README 迁出去的"判据体系明细"，读者（含下一轮的我）会当成清单来读 —— 实测 44 条
    非 selftest 套件里 **16 条从未出现在其中**（perf_baseline / j2 / j4 / offline_shell / …），
    且这条盲区存活了 15 轮无人报警。同族根因仍是 M5⑥：**同一个清单有两处实现**。
    零分母不得判绿（R247）：取不到任何电池脚本 = 解析失效，不是"没有判据"。

    第三面（r99 一手补）：磁盘与文档两面都在、**唯独从未 `git add`** 的判据，前两条腿谁都看不见。
    实证 = r98 报告把 `timing_coupling_check.py` / `perf_ramp_delta_check.py` 标 ✅，而
    `git ls-tree -r HEAD` 对这两个名字 0 命中 ⇒ 远端 CI 跑的那套判据里没有它们，本地三绿照旧。
    取 index 面（`git ls-files --cached`）不取 HEAD 面：HEAD 面会让"把这些文件补进第一笔提交"
    这个动作本身被自己拦住（钩子在提交前跑，那时 HEAD 还没有它们）。
    """
    bad = []
    if not scripts:
        return ["G16 解析不到任何电池脚本（SUITES 形状变了？）⇒ 不得据此判绿"]
    missing = sorted(s for s in scripts if s not in doc_text)
    if missing:
        bad.append("在电池里跑、却没进 quality-gates 的脚本 %d 条：%s"
                   % (len(missing), "、".join(missing[:6]) + ("…" if len(missing) > 6 else "")))
    named = {m.split("/")[-1] for m in re.findall(r"_test/([A-Za-z0-9_.\-]+\.(?:py|js))", doc_text)}
    ghost = sorted(n for n in named if n not in on_disk)
    if ghost:
        bad.append("quality-gates 写了而 `_test/` 查无此件：%s" % "、".join(ghost))
    if tracked is not None:
        untracked = sorted(s for s in scripts if s not in tracked)
        if untracked:
            bad.append("电池登记了而 git 未跟踪（在盘上但没入库，CI 与发布面读不到）%d 条：%s"
                       % (len(untracked), "、".join(untracked[:6]) + ("…" if len(untracked) > 6 else "")))
    return bad


def docs_index_audit(index_text, disk_names):
    """G19 纯函数：`docs/` 真实文件 ⇄ `docs/README.md` 索引双向对账。

    立此条的实证（r89，2026-10-01）：r87 一次性交付 `API.md`/`EXTENSIONS.md`/`PERF-BASELINE.md`
    三本手册，而索引表里仍只有 `openapi.yaml` 一行 ⇒ **写了但没人找得到**。这与对标 G6 判的
    「机制有、文档无 = 扩展能力不可发现」是同一条缺陷，只不过这次砸在上一轮自己的交付物上；
    而原 G3 只问「openapi.yaml 被索引引用了吗」，对**其余文档**零覆盖（存在性结论冒充目录完整性）。
    零分母不得判绿（R247）。
    """
    if not disk_names:
        return ["G19 取不到 docs/ 下任何文件（目录改名或扫描失效）⇒ 不得据此判绿"]
    linked = set()
    for t in re.findall(r"\]\(([^)\s]+?)\)", index_text):
        linked.add(Path(t.split("#")[0]).name)
    names = set(disk_names)
    bad = []
    missing = sorted(n for n in names if n != "README.md" and n not in linked)
    if missing:
        bad.append("磁盘有、索引不引（写了等于没写）：%s" % "、".join(missing))
    ghost = sorted(n for n in linked
                   if n.endswith((".md", ".yaml")) and n not in names)
    if ghost:
        bad.append("索引引了而磁盘查无此件：%s" % "、".join(ghost))
    return bad


def remote_has_file(rel, repo):
    out = subprocess.run(["gh", "api", f"repos/{repo}/contents/{rel}"],
                         capture_output=True, text=True, encoding="utf-8", timeout=60)
    if out.returncode != 0:
        msg = (out.stderr or "").lower()
        if "could not resolve" in msg or "timed out" in msg or "connection" in msg:
            raise OSError(msg[:120])
        return False, (out.stderr or "")[:120]
    return True, "默认分支可见"


NOTICES = "docs/THIRD-PARTY-NOTICES.md"
# 许可 token：归属行里必须出现其一，否则"提个文件名"也算登记（那是洗白不是声明）
LIC_TOKEN = re.compile(r"\b(MIT|Apache|BSD|ISC|GPL|LGPL|MPL|Mozilla Public|GreenSock)"
                       r"|标准许可|Standard License", re.I)


def manifest_vendor_files():
    """G6 的分母从 vendor 名册现读（与 r43 修好的 vendor_freshness_check 同一范式）。

    ⚠️ 这条是**同族第二处**：r43 把 freshness 判据的枚举面从写死 `src/vendor` 改成读
    `vendor_dirs`，当时只修了一处 —— G6 仍写死 `src/vendor/*.js`，于是 r42 引入的
    `_test/vendor/axe-core-4.10.2.min.js`（**MPL-2.0，非 MIT**）在授权边界上又隐形了一整轮，
    而 THIRD-PARTY-NOTICES 正文那句"`_test/` 全部由本团队原创"因此是假陈述。
    返回 (basenames, relpaths)；名册取不到 ⇒ ([], []) 由调用方按 UNVERIFIED 处理，禁判绿。
    """
    fp = ROOT / "_test" / "vendor-manifest.json"
    if not fp.exists():
        return [], []
    try:
        libs = json.loads(fp.read_text("utf-8")).get("libs") or []
    except Exception:
        return [], []
    rel = [str(x.get("file") or "") for x in libs if x.get("file")]
    return sorted({Path(r).name for r in rel}), sorted(rel)


def header_license(text):
    """从文件头部 banner 里取**实测**许可（一手证据）。返回 token 集合，可能为空=无可识别声明。

    为什么不往 vendor-manifest.json 再加 license 字段：那会让"用的是哪个许可"有两处声明源，
    正好制造本仓已登记过的"改了声明没改文件"那族漂移。名册只管清单与哈希，许可只写在归属表，
    而本函数负责把表里的说法**和文件本体对一次账**。
    """
    t = (text or "")[:4000]
    out = set()
    if re.search(r"SPDX-License-Identifier:\s*MIT|@license[^\n]*MIT", t, re.I):
        out.add("MIT")
    if re.search(r"GreenSock|standard-license", t, re.I):
        out.add("GreenSock")
    if re.search(r"Mozilla Public\s+License|MPL", t, re.I):
        out.add("MPL")
    if re.search(r"Apache License|Apache-2", t, re.I):
        out.add("Apache")
    if re.search(r"\bBSD[- ]?3-Clause|Redistribution and use in source", t, re.I):
        out.add("BSD")
    return out


def row_license(row):
    out = set()
    if re.search(r"\bMIT\b", row):
        out.add("MIT")
    if re.search(r"GreenSock|标准许可|Standard License", row, re.I):
        out.add("GreenSock")
    if re.search(r"MPL|Mozilla Public", row, re.I):
        out.add("MPL")
    if re.search(r"Apache", row, re.I):
        out.add("Apache")
    if re.search(r"\bBSD\b", row):
        out.add("BSD")
    return out


def vendor_headers(relpaths):
    """读每个 vendored 文件的**头部 4KB**（banner 一定在最前面），作为许可的一手证据。"""
    out = {}
    for r in relpaths:
        p = ROOT / Path(r)
        if p.exists():
            out[Path(r).name] = p.read_text("utf-8", errors="replace")[:4000]
    return out


def license_scope(notices_txt, readme_txt, vendor_files, vendor_paths=None, headers=None):
    """G6/G7 纯函数：第三方授权边界必须被正式声明且不漏登记。

    两条独立出口各自报告（不许第一条红就把后面的吞掉）：
      · 未登记 —— 名册里有、归属表里没有对应表行
      · 无许可 —— 有表行但行内不含任何许可 token（把声明写成"见上游"等于没声明）
    """
    bad = []
    if "GreenSock" not in notices_txt:
        bad.append("授权清单未点明 GSAP 的实际条款（把整仓说成 MIT 是不准确的声明）")
    rows = [ln for ln in notices_txt.splitlines() if ln.lstrip().startswith("|")]

    def lic_cell(r):
        cells = [c.strip() for c in r.split("|")]
        return cells[3] if len(cells) > 3 else r
    unregistered, unlicensed = [], []
    for f in vendor_files:
        hit = [r for r in rows if f in r]
        if not hit:
            unregistered.append(f)
        elif not any(LIC_TOKEN.search(lic_cell(r)) for r in hit):
            unlicensed.append(f)
    if unregistered:
        bad.append(f"vendored 文件未在授权清单登记 {unregistered}")
    if unlicensed:
        bad.append(f"授权清单里有行但没写许可条款 {unlicensed}（提文件名不算声明）")
    # G6b 对账：表里**说的**许可，必须与文件 banner 里**实测的**许可一致。
    # 这条是判据的牙：否则我可以在表里把 MPL 的 axe-core 写成 MIT 就"合规"了。
    # 取交集而非全等：GSAP 行合法地写着「非 MIT、非 OSI」，全等会把正确的句子判成错。
    for f in vendor_files:
        if f in unregistered or not headers:
            continue
        actual = header_license(headers.get(f, ""))
        claimed = set()
        for r in [x for x in rows if f in x]:
            # 只取**授权列**做对账：扫整行会被上游 URL 里的 "greensock" 之类喂成正确，
            # 也会让"MPL 写在别的列、授权列空着"这种洗白形态过关（⑤b 首跑就是这么漏的）。
            claimed |= row_license(lic_cell(r))
        if not actual:
            bad.append(f"{f} 的 banner 里取不到可识别许可声明 ⇒ 无法与归属表对账（新增第三方件必须带上游 banner）")
        elif claimed and not (claimed & actual):
            bad.append(f"{f} 归属表写 {sorted(claimed)} 但文件 banner 实测是 {sorted(actual)} ⇒ 声明与实物不符")
    # 「原创范围」是**可证伪断言**：名册里一旦存在非 src/ 的第三方件，归属文必须显式交代该边界。
    # 不这么判的原因：旧写法靠正则找"`_test/` … 全部 … 原创"，而原句里 `_test/` 与「全部」隔着换行，
    # 正则永远不匹配 ⇒ 假陈述照样过关（判据恒真的一种新形态）。改成要求正面出现 `_test/vendor` 面名。
    off_src = [r for r in (vendor_paths or []) if not r.startswith("src/")]
    if off_src and "_test/vendor" not in notices_txt:
        bad.append("名册里有非 src/ 的第三方件 %s，但授权清单没交代 _test/vendor 这条边界"
                   "（正文把 _test/ 说成全部原创即为假陈述）" % off_src)
    if "THIRD-PARTY-NOTICES" not in readme_txt:
        bad.append("README 没有指向授权清单的口径行（读者只会看到 MIT）")
    return bad


EVAL_KEYS = ("eval", "dataset", "provenance", "blindset", "frozen")
CONSTR = "memory/06-constraints.md"
# 只承担"裁决数据"角色的文件才要求登记；vendor 台账是配置声明件，不属评测集（分母不同）
MANAGED_DATA = ("emotion-eval-dataset.json",)


def eval_data_files():
    """磁盘上承担裁决作用的数据文件（按文件名关键词），另并入显式白名单防漏。"""
    out = set(MANAGED_DATA)
    for p in sorted((ROOT / "_test").glob("*.json")):
        if any(k in p.name.lower() for k in EVAL_KEYS):
            out.add(p.name)
    return sorted(out)


def eval_section(text):
    i = text.find("评测集隔离")
    if i < 0:
        return ""
    rest = text[i:].split("\n## ")[0].split("\n---\n")[0]
    return rest


def eval_scope(seg, files, counts):
    """G8 纯函数：评测集红线必须真落地。

    ⚠️ 两处口径修正（本轮实测踩到后写死，别再用错分母）：
    ① 占位符判据**锚定 init 模板原句**（"清单：（如 "），不能泛指"段里出现（如 "就算占位符"
       —— 登记表的说明行本身合法地含中文括号示例，第一版因此把已填实的表判成红（假红同样是缺陷）。
    ② 条数只对**裁决用数据文件**（`files`，按 eval/dataset/provenance/blind/frozen/testset 关键词判定）核，
       不对手登记的配置件（如 `_test/vendor-manifest.json`，它是 3 个库不是 3 条样本）核 ——
       第一版对全部登记文件比 `len(items)`，把 vendor 台账判成"实际 0 条、声称 3 条"。
    """
    bad = []
    if not seg.strip():
        return ["06 缺「评测集隔离」章节（R196 init 必填项）"]
    if "清单：（如 " in seg or "清单: (如 " in seg:
        bad.append("清单仍是 init 模板占位符（未填实际文件）⇒ 这条红线等于没落地")
    for f in files:
        if f not in seg:
            bad.append(f"承担裁决作用的 {f} 未在 06 登记来源（provenance）")
    for f, declared in (counts or {}).items():
        if f not in files:
            continue                      # 配置声明件只要求"存在"，不按样本条数核
        p = ROOT / "_test" / f
        if not p.exists():
            bad.append(f"06 登记的 {f} 磁盘上不存在（文档写了≠磁盘有，R240）")
            continue
        try:
            d = json.loads(p.read_text("utf-8"))
        except Exception as e:
            bad.append(f"{f} 不可解析：{e}")
            continue
        items = d if isinstance(d, list) else (d.get("items") or d.get("cases") or d.get("data") or [])
        if declared != len(items):
            bad.append(f"{f} 实际 {len(items)} 条，06 声称 {declared} 条")
    return bad


def eval_counts(seg):
    """从登记段落抽「文件名 … N 条」配对（同一行内）。"""
    out = {}
    for line in seg.splitlines():
        name = re.search(r"([A-Za-z0-9_.-]+\.json)", line)
        num = re.search(r"(\d+)\s*条", line)
        if name and num:
            out[name.group(1)] = int(num.group(1))
    return out


ENTRY_RE = re.compile(r"^(sys\.exit\(|main\(|raise SystemExit)")


def _top_entry_stmts(tree):
    """纯函数：模块**顶层语句**中的入口调用 → [(行号, 反解析文本)]。

    只取 `tree.body` 的直接子节点（Expr(Call) / Raise），与旧行扫描的覆盖面一致
    （旧尺的 `^sys.exit(` 也只认 col 0 起手的行），区别是**字符串字面量不再算语句**。
    """
    out = []
    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            out.append((node.lineno, ast.unparse(node.value)))
        elif isinstance(node, ast.Raise):
            out.append((node.lineno, "raise " + (ast.unparse(node.exc) if node.exc else "")))
    return out


def import_safety(text):
    """G9 纯函数：判据脚本必须 import-safe —— 顶层入口调用须落在 __main__ 守卫之后。

    r26 加，起因是本轮自己踩的第五次同族坑：给 `benchmark_metrics.py` 的分档判据做负控制时
    `import` 它 = 直接跑一遍 16 仓联网采集然后 `exit 0`，**反例压根没执行却看起来像通过**。
    判据脚本会被互相 import（`--only` 自查、CI 复用、聚合 runner 对账），无守卫就等于
    "一 import 就跑全套/跑网络"，而退出码还是 0。

    r95 取数面由「文本行」换成「AST 顶层语句」（一手：`verdict_exit_parity_check.py` 的自检样本
    `GOOD_EXPLICIT` 是三引号字符串，串内 col-0 的 `sys.exit(0 if ok else 1)` 被旧尺当成真入口
    ⇒ 一件本来 import-safe 的判据被判红）。旧尺的分子里混着「字符串内容」，属**取数面比它自称的
    语义宽**；新尺按语句取，字符串结构性看不见。解析不动时**退回行扫描**（语法错由
    `py_syntax_hygiene` 单独点名，本函数不吞掉它）。
    """
    try:
        tree = ast.parse(text)
    except SyntaxError:
        lines = text.splitlines()
        gl = next((i for i, l in enumerate(lines) if l.startswith("if __name__")), None)
        return [f"第 {i + 1} 行顶层入口调用且无 __main__ 守卫（import 即执行）：{l[:44]}"
                for i, l in enumerate(lines)
                if ENTRY_RE.match(l) and (gl is None or i < gl)]
    guard = next((n.lineno for n in tree.body
                  if isinstance(n, ast.If) and "__name__" in ast.unparse(n.test)), None)
    return [f"第 {ln} 行顶层入口调用且无 __main__ 守卫（import 即执行）：{txt[:44]}"
            for ln, txt in _top_entry_stmts(tree)
            if ENTRY_RE.match(txt) and (guard is None or ln < guard)]


REQ_ALIAS = {"pyyaml": "yaml", "pillow": "PIL"}   # 发行名 → import 名（清单写 PyYAML/Pillow，代码 import yaml/PIL）


def py_syntax_hygiene(text):
    """G9 第二腿：判据脚本必须**解析得动**。

    为什么算进 G9 而不是新开判据号（r51 §5-P1 立的账）：本仓台账里"内联/heredoc 写盘把
    `\\n` 落成真实换行、把字面量里的引号吞掉"这一族已复发 12 次，而它的**第一现场就是
    SyntaxError**。可 `third_party_imports()` 对 SyntaxError 是 `except: continue` ——
    一个被写坏的文件在依赖审计里**直接隐身**，比报错更糟。本腿把它变成点名。
    """
    import ast as _ast
    try:
        _ast.parse(text)
    except SyntaxError as e:
        return [f"SyntaxError 第 {e.lineno} 行：{e.msg}（heredoc/内联写盘吞转义或引号的第一现场）"]
    except Exception as e:                       # 递归过深等：同样算"解析不动"
        return [f"parse 异常 {type(e).__name__}"]
    return []


def docstring_swallow(text):
    """G9 第三腿：非块首的「裸字符串语句」= def/docstring 首行被编辑吞掉的指纹（r90 两次一手）。

    为什么第二腿拦不住：`py_compile` / `ast.parse` 对「吞掉 `def f():` 或 `\"\"\"首行\"\"\"`」
    **都可能全过**。本轮两次实测各有结局：一次是 SyntaxError（第二腿当场抓到）；另一次
    `def lag_days(commits):` 被吞后，原 docstring 静默变成 `judge()` 里 `return` 之后的一条
    **裸字符串语句**——编译过、导入过、`--selftest` 也过，只有真调用 `lag_days()` 时才 `NameError`。
    判据取 flake8 B018 的同形：任何块（模块/函数/类）里**不是第一条**语句的裸字符串都不是有意写法。
    真面误报率实测：`_test/*.py` 86 个文件命中 **0** 条 ⇒ 高精度，可进阻断链。
    """
    import ast as _ast
    try:
        tree = _ast.parse(text)
    except Exception:
        return []          # 语法坏了由第二腿点名，本腿不重复报
    out = []
    for node in _ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(body, list):
            continue
        for i, st in enumerate(body):
            if i == 0:
                continue                      # 块首裸字符串 = docstring，合法形态
            if isinstance(st, _ast.Expr) and isinstance(st.value, _ast.Constant) \
                    and isinstance(st.value.value, str):
                out.append("第 %d 行是块内非首条裸字符串（上方 `def`/docstring 首行被吞的形状）"
                           % st.lineno)
    return out


def java_quote_parity(text):
    """**advisory only（不进闸）**：Java 逐行未转义 ASCII 双引号须成对。

    r52 实测误报率 **6/20 文件**被报红（假阳形态：`{\\"emotion\\"...}` 这类 JSON 字面量里的
    反斜杠-引号交替、跨行 `+` 拼接），即"文本启发式重造 Java 词法器"不成立。
    该事实的**权威判据是 javac**（吞掉字面量内部引号的第一现场就是「未结束的字符串文字」），
    而 java-build 一直在 CI 链上、且 T4 盯住构建步不得加 `-DskipTests`
    （⇒ 见 `_test/java_test_guard.py`）。同一事实不另立第二把更差的尺。
    本函数保留给**手工诊断**用（判红时先看它给不给方向），不进 G9 的判定集合。
    """
    out = []
    in_block = False
    for i, raw in enumerate(text.splitlines()):
        s = raw.strip()
        if in_block:
            if "*/" in s:
                in_block = False
            continue
        if s.startswith("/*") and "*/" not in s[2:]:
            in_block = True
            continue
        if s.startswith("//") or s.startswith("*") or s.startswith("/*"):
            continue                        # 注释行里的引号不参与配对
        if '"""' in raw:
            continue                        # 文本块：边界不是逐行奇偶
        n, in_s, in_c, k = 0, False, False, 0
        while k < len(raw):
            ch = raw[k]
            if in_s:
                if ch == "\\":
                    k += 2
                    continue
                if ch == '"':
                    n += 1                  # ⚠️ 收口引号也要计数：首版只数开引号，
                in_s = False                #    一个字符串贡献 1 ⇒ "奇数"变成"字符串个数为奇"，
                k += 1                      #    实测 17/20 文件全报红，是判据错不是代码错
                continue
            if in_c:
                if ch == "\\":
                    k += 2
                    continue
                if ch == "'":
                    in_c = False
                k += 1
                continue
            if ch == "/" and raw[k + 1:k + 2] == "/":
                break                       # 行注释：其后不计数
            if ch == '"':
                n += 1
                in_s = True
            elif ch == "'":
                in_c = True
            k += 1
        if in_s or in_c:
            out.append(f"第 {i + 1} 行字符串/字符字面量未闭合（{s[:48]}）")
            continue
        if n % 2:
            out.append(f"第 {i + 1} 行未转义 ASCII 双引号为奇数（{n} 个）：{s[:48]}")
    return out



def ci_invoked_scripts(ci_text, suites_text):
    """CI 真会执行的判据脚本 = workflow 的 run 里点名的 ∪ 电池 SUITES 里的。
    审计面必须按这个集合来，否则会把"本地工具的重依赖"算进 CI 清单（G11 反过来判它幽灵依赖）。"""
    names = set(re.findall(r"_test/([A-Za-z0-9_]+\.py)", ci_text)) | set(re.findall(r'"_test/([A-Za-z0-9_]+\.py)"', suites_text))
    return sorted(ROOT / "_test" / n for n in names if (ROOT / "_test" / n).exists())


def third_party_imports(files=None):
    """AST 扫给定脚本的真实第三方 import（stdlib 与本目录模块排除）；files=None 时扫全部 _test。"""
    import ast as _ast
    std = set(getattr(sys, "stdlib_module_names", set()))
    local = {p.stem for p in (ROOT / "_test").glob("*.py")}
    out = set()
    for p in sorted(files if files is not None else (ROOT / "_test").glob("*.py")):
        try:
            tree = _ast.parse(p.read_text("utf-8", errors="replace"))
        except SyntaxError:
            continue
        for n in _ast.walk(tree):
            mods = []
            if isinstance(n, _ast.Import):
                mods = [a.name.split(".")[0] for a in n.names]
            elif isinstance(n, _ast.ImportFrom) and n.module and n.level == 0:
                mods = [n.module.split(".")[0]]
            for m in mods:
                if m and m not in std and m not in local and not m.startswith("_"):
                    out.add(m)
    return out


def req_names(text):
    out = set()
    for ln in (text or "").splitlines():
        ln = ln.split("#")[0].strip()
        if not ln:
            continue
        name = re.split(r"[<>=!;\[]", ln)[0].strip().lower()
        if name:
            out.add(REQ_ALIAS.get(name, name))
    return out


def ci_deps_audit(ci_text, req_text, imports):
    """G11 纯函数：依赖清单 == 判据实际 import，且每个跑判据的 job 都装了清单。

    r28 加。根因是实测：CI 的 java-build job 长期红着（`api_contract_check.py` 要 PyYAML，
    那个 job 只 setup-python 没装依赖 ⇒ rc=2），而**本机装了所以永远看不见** ——
    与同行「本地全绿、CI 判红」同族（两处实现/两份环境）。清单化 + 本判据 = 少写一处就报红。
    """
    bad = []
    req = req_names(req_text)
    if not req:
        bad.append("G11 requirements.txt 为空或缺失 ⇒ 依赖全靠各 job 口头安装（就是本次事故形态）")
    if not imports:
        bad.append("待审脚本集合为空 ⇒ G11 在读空气（先疑 CI 解析失效）")
    miss = sorted(imports - req)
    if miss:
        bad.append(f"判据实际 import 未登记进清单：{miss}")
    ghost = sorted(req - imports)
    if ghost:
        bad.append(f"清单里有但没有任何判据 import（幽灵依赖，装了就没人查）：{ghost}")
    body = ci_text.split("jobs:", 1)[1] if "jobs:" in ci_text else ""
    blocks = re.split(r"(?m)^  ([a-z][a-z0-9_-]*):$", body)
    runs = installs = 0
    for i in range(1, len(blocks) - 1, 2):
        txt = blocks[i + 1]
        if "_test/" in txt:
            runs += 1
            if "requirements.txt" not in txt:
                bad.append(f"job「{blocks[i]}」跑 _test 判据却没装 requirements.txt")
            else:
                installs += 1
    if not runs:
        bad.append("CI 里没有任何 job 跑 _test 判据 ⇒ G11 在读空气（先疑解析失效）")
    return bad, runs, installs


def ci_battery_audit(ci_text, suites_text):
    """G10 纯函数：判据必须挂在**真会走的路径**上，且豁免分母可自证。

    r28 加，根因有两处一手实证：① 本项目 CI 的 browser-regression job 长期只跑 `browser_check` 一条，
    r26-r28 新加的 patch_apply / settings_panel / offline_shell 全都不在发布路径上（本地绿≠线上有人管）；
    ② 同行事故形态更狠：CodeQL 30 次全 success，但 `refs/heads/main` 分析数为 0 —— 有运行记录不等于覆盖主路径。
    本判据不检查"跑没跑绿"，检查的是"该跑的东西在不在路径上 + 豁免是不是真豁免"。
    """
    bad = []
    if "run_all_suites.py" not in ci_text:
        bad.append("CI 里没有整跑电池的步骤 ⇒ 新增判据只在本地生效（装了不等于在用）")
    elif "--exclude-llm" not in ci_text:
        bad.append("CI 跑电池却未声明无密钥豁免 ⇒ 要么 runner 必红，要么有人偷偷删套件")
    names = re.findall(r'^\s+\("([a-z0-9_]+)",', suites_text, re.M)
    if not names:
        bad.append("解析不到 SUITES 名单 ⇒ G10 在读空气")
    m = re.search(r"LLM_SUITES = \{([^}]*)\}", suites_text, re.S)
    exempt = re.findall(r"\"([^\"]+)\"", m.group(1)) if m else []
    if not exempt:
        bad.append("缺 LLM_SUITES 声明 ⇒ --exclude-llm 无豁免可算，CI 覆盖分母不可证")
    ghost = [e for e in exempt if e not in names]
    if ghost:
        bad.append(f"豁免项不在实跑清单内（幽灵豁免，恒真风险）：{ghost}")
    return bad, len(names), exempt


def version_truth(tag, pom):
    """G12 纯函数：把"当前版本"这条断言绑到三个权威源上，任一侧脱节即红。

    立此条的实证（r35）：`ROADMAP.md` 版本节奏段写着 **v1.3.0**，而 `git tag` 已有 `v1.4.0`、
    `server/pom.xml` 也是 `1.4.0` —— 与本项目反复登记的"文档数字与实值脱节"同族，
    而 G2/G4 只覆盖 README 的门禁数/套件数，版本断言**当时没有机器责任方**。
    本函数只在两侧同构时才算绿：tag==pom==文档，且文档断言真的存在（漏声明=失去责任方，判红）。
    """
    bad = []
    if not tag:
        bad.append("G12 取不到 git tag ⇒ 版本判据在读空气（先疑仓库无标签）")
    if not pom:
        bad.append("G12 取不到 server/pom.xml 的 <version> ⇒ 同上")
    if tag and pom and tag.lstrip("v") != pom:
        bad.append(f"权威源互不一致：tag={tag} 而 pom={pom}（发版链断在中间）")
    return bad


def version_doc_audit(docs_text, pom):
    """G12 文档侧：每个 `当前版本：**vX.Y.Z**` 断言必须等于权威版本；ROADMAP 必须有这一行。"""
    bad = []
    seen = 0
    for name, text in docs_text.items():
        found = set(re.findall(r"当前版本[：:]\s*\*\*v?(\d+\.\d+\.\d+)", text))
        if not found and name == "ROADMAP.md":
            bad.append("ROADMAP 的「当前版本：**vX.Y.Z**」断言行失踪 ⇒ 版本声明没有机器责任方")
        for v in sorted(found):
            seen += 1
            if pom and v != pom:
                bad.append(f"{name} 声称 v{v}，权威源 pom 为 {pom}")
    if not seen:
        bad.append("G12 零命中：全仓没有任何版本断言可核对（不得据此判绿）")
    return bad


def _read(rel):
    """读受仓管文档；不存在按空串（调用方靠"零命中即红"兜，不会静默放行）。"""
    p = ROOT / rel
    return p.read_text("utf-8", errors="replace") if p.exists() else ""


def peer_count_audit(readme_text, truth):
    """G14 文档侧：README 里"对标源数据台账（N 仓指标"这一**现行状态**断言必须等于台账记的 N。

    只锚这一句是有意的：README/ROADMAP 里还有"第二轮 14 仓""参照池由 14 扩到 16"这类
    **历史轮次**陈述，它们当时就是 14，用宽正则一律钉成红 = 误伤（r36 实测先写过宽口径，
    立刻把 `14 仓实测指标横向对账` 那条历史行判红）。
    """
    bad = []
    found = set(re.findall(r"对标源数据台账（(\d+) 仓指标", readme_text))
    if not found:
        bad.append("G14 零命中：README 没有可核对的对标仓数断言 ⇒ 该声明没有机器责任方（不得据此判绿）")
    if len(found) > 1:
        bad.append(f"G14 README 内仓数断言自相矛盾：{sorted(found)}")
    for c in sorted(found):
        if truth is None:
            bad.append("G14 取不到台账 peers_expected ⇒ 无权威值可比（先疑台账缺失/损坏）")
        elif int(c) != int(truth):
            bad.append(f"README 声称 {c} 仓，台账权威值 {truth}（差 {int(c)-int(truth):+d}）")
    return bad


def head_blob(rel):
    """HEAD 面的文件正文（git 决定的量，他人未入库的在途改动结构性进不了判定面）。"""
    r = subprocess.run(["git", "-C", str(ROOT), "show", "HEAD:%s" % rel],
                       capture_output=True, timeout=60)
    if r.returncode != 0:
        raise RuntimeError("git show HEAD:%s 失败" % rel)
    return (r.stdout or b"").decode("utf-8", "replace")


def battery_rc_facade_problems(src):
    """G18 纯函数：聚合器的收口摘要行必须由**真退出码**派生，不得硬印 rc 字面量。

    根因（r74 一手）：`print(f"BATTERY: … rc=0")` 里的 `rc=0` 一直是字面量，而退出码在下面才算是
    ⇒ 本地整跑 rc=1、CI 同 SHA 两个 job failure，两处日志都还印着 `rc=0`；这行是人与机器共同的收口读数，
    印错等于**伪造回执**（本仓台账里"94/98 rc=0"那类句子全部来自它）。
    只在 HEAD 面判（工作树里可能混着他人未入库的 hunk，不能把别人的现场算成我的红，也不能被他人在途态掩护）。
    """
    if not src:
        return ["G18 取不到 run_all_suites.py 的 HEAD 正文 ⇒ 无对象可判，不得记绿"]
    lines = re.findall(r'print\(.{0,4}BATTERY:[^\n]*', src)
    if not lines:
        return ["G18 没找到 BATTERY 摘要行（聚合器形状变了 ⇒ 这条判据须随之重写，禁止静默放行）"]
    bad = []
    for ln in lines:
        if re.search(r'rc=\d+["\']', ln):
            bad.append("G18 摘要行硬印 rc 字面量：%s ⇒ 印出的 rc 与进程退出码不同源" % ln[:64])
        elif "rc={" not in ln:
            bad.append("G18 摘要行的 rc 不是插值（%s）⇒ 无法证明它跟着 return 走" % ln[:64])
    if not re.search(r'return\s+(bat_rc|rc)\b', src):
        bad.append("G18 没找到「退出码由同一变量返回」的形状 ⇒ 打印与返回可能两处各算各的")
    return bad


def head_battery_count():
    """HEAD 面现算的 SUITES 条目数（只用于**印差值**，不参与判定：
    拿"台账 ⇄ 当前 HEAD"做阻断会撞 R-10 不可自愈——CI 里没法重跑联网采集来刷新台账。"""
    try:
        txt = head_blob("_test/run_all_suites.py")
        seg = txt.split("SUITES = [", 1)[1].split(chr(10) + "]", 1)[0]
        return len(re.findall(r'^\s*\("', seg, re.M))
    except Exception:
        return None


def ledger_peer_count():
    p = ROOT / "交付物" / "对标数据" / "benchmark-metrics.json"
    try:
        return int(json.loads(p.read_text("utf-8", errors="replace"))["peers_expected"])
    except Exception:
        return None


def ledger_last_self(path=None):
    """台账末次 run 的 self 行（取不到返回 None，由调用方判红，不得当"没问题"）。"""
    p = path or (ROOT / "交付物" / "对标数据" / "benchmark-metrics.json")
    try:
        runs = json.loads(Path(p).read_text("utf-8", errors="replace"))["runs"]
        return (runs[-1].get("self") or {}) if runs else None
    except Exception:
        return None


def ledger_face_problems(last_self):
    """G17 纯函数：对标台账 self 行的**取数面必须显式声明且必须是 git 面**。

    为什么钉这一格（r71 一手）：`self_metrics()` 曾经一半走 git、一半 `rglob` 工作树，
    于是同一行里 `regression_suites=101`（工作树：含并行会话未入库的 2 条）与真值 99 并存，
    看上去完全自洽、零报错 ⇒ 台账一旦被下一轮当"横向现状"抄走，就再也追不回是谁写错的。
    r72 把它钉成闸（[推荐:R71-01] 的机器落点）。
    """
    if not last_self:
        return ["G17 读不到台账末次 run 的 self 行 ⇒ 无对象可判，不得据此判绿"]
    bad = []
    face = last_self.get("self_face")
    if face is None:
        bad.append("G17 self 行没有 `self_face` 字段 ⇒ 无法证明它是 git 面（r71 之前的形状，正是事故源）")
    elif face != "HEAD":
        bad.append("G17 `self_face=%r` 非 HEAD ⇒ 台账正在把工作树/降级态写成横向现状" % (face,))
    if last_self.get("regression_suites_face") not in (None, "HEAD"):
        bad.append("G17 `regression_suites_face=%r` 非 HEAD" % (last_self.get("regression_suites_face"),))
    if last_self.get("self_face_errors"):
        bad.append("G17 面取数有错却仍落账：%s ⇒ 禁止静默退回工作树后照常打印" % str(last_self["self_face_errors"])[:80])
    n = last_self.get("regression_suites")
    if not isinstance(n, int) or n <= 0:
        bad.append("G17 `regression_suites=%r` 非正整数 ⇒ 零输入/缺值不得记为已验" % (n,))
    return bad


def pom_version():
    p = ROOT / "server" / "pom.xml"
    if not p.exists():
        return ""
    m = re.search(r"<artifactId>soulisle-server</artifactId>\s*<version>([^<]+)</version>",
                  p.read_text("utf-8", errors="replace"))
    return m.group(1).strip() if m else ""


TAG_RE = re.compile(r"(?:refs/tags/)?(v?\d+\.\d+\.\d+(?:-[0-9A-Za-z.]+)?)(\^\{\})?$")


def pick_latest_tag(output):
    """纯函数：从 `git tag` 或 `git ls-remote --tags` 的输出里挑最大的版本 tag。

    必须处理两种形态：① 一行一个 tag 名；② `<sha>\\trefs/tags/vX.Y.Z`（可带 `^{}` 剥离行）。
    `^{}` 行不能当独立候选 —— 否则同一个 tag 会被数两次，且排序键不同。
    """
    cands = []
    for line in output.splitlines():
        parts = line.split()
        if not parts:
            continue
        ref = parts[-1]                    # `git tag` 只有一列；ls-remote 是 `<sha>\trefs/tags/X`
        if ref.endswith("^{}"):
            continue
        m = TAG_RE.match(ref)
        if m:
            cands.append(m.group(1))
    if not cands:
        return ""
    def key(t):
        core = t.lstrip("v").split("-")[0]
        return tuple(int(x) for x in core.split(".")[:3])
    return sorted(cands, key=key)[-1]


def latest_tag():
    """tag 权威面：本地优先，本地取不到再读远端。

    立此处的实测根因（r35）：CI 的 `actions/checkout@v4` 默认不拉旧 commit 上的 tag ⇒
    本函数首版只跑 `git tag` 时在 CI 返回空，G12 判"读空气"红 ——
    **判据自带"本机恒真 / CI 恒红"的环境假设**，正是我在报告 §2 里批评的那一族，自己又踩了一次。
    """
    def run(args):
        try:
            r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", timeout=30)
        except OSError:
            return ""
        return r.stdout if r.returncode == 0 else ""

    local = pick_latest_tag(run(["git", "-C", str(ROOT), "tag", "--sort=-v:refname"]))
    if local:
        return local
    remote = pick_latest_tag(run(["git", "-C", str(ROOT), "ls-remote", "--tags", "origin"]))
    if remote:
        print("  NOTE  G12 本地无 tag（浅克隆/CI 常态），已改读 `git ls-remote --tags origin`")
    return remote


AC_DUP_BASELINE = 7   # r40b 实测存量：08 里 13/14/15/16/17/18/19 各挂了 2 条命题
_AC_DEF = re.compile(r"- \[.\] (?:\*\*)?AC-OBS-(\d+)")


def ac_id_audit(ac_text):
    """G15 纯函数：`08-ac-obs.md` 的 AC id 是验收面追溯键，一个 id 只能挂一条命题。

    立此条的实证（r40b 加 AC-OBS-23 时顺手数了一遍 id）：30 条定义只用掉 23 个 id，
    `AC-OBS-13/14/15/16/17/18/19` **每个都挂了两条互不相干的命题**——
    例如 AC-OBS-19 既写"首屏第三方库可溯源"（r20）又写"容器镜像真构建真运行"（2026-09-23）。
    `flow --verify-ac` 的实跑回显里同一个 id 出现两次，且它把整套报成"24 条 AC"
    ⇒ 重复的后果不是难看，是**一条判红不知道该勾哪一行 + AC 计数失真**。

    分级：存量 7 个 id 已脏，重编号会牵动 README/07/CHANGELOG 的交叉引用（另事，已登记 07 待办）。
    本判据**只钉增量**（棘轮只降不升）：新出现的重复当场红，存量按基线放行并写明来源。
    """
    ids = [m.group(1) for ln in ac_text.splitlines() if ln.startswith("- [")
           for m in [_AC_DEF.match(ln)] if m]
    if not ids:
        return ["G15 零命中：08 解析不到任何 AC 定义 ⇒ 读空气，不得判绿"]
    counts = {}
    for i in ids:
        counts[i] = counts.get(i, 0) + 1
    dup = {i: c for i, c in counts.items() if c > 1}
    extra = sum(c - 1 for c in dup.values())
    if extra > AC_DUP_BASELINE:
        return [f"G15 AC id 重复增量：额外 {extra} 条 > 基线 {AC_DUP_BASELINE}"
                f"（重复 id={sorted(dup, key=int)}）⇒ 同一追溯键挂了多条命题"]
    return []


def guard_inventory(header_text, source_text):
    """G13 纯函数：`main()` 里真正执行的每条 G 判据，必须在本文件头部的判据清单里有一行说明。

    立此条的实证（r35，两次同族）：G11（依赖清单对账）落地时**只**写在函数 docstring 里，
    头部清单从 G10 直接跳到"退出码"一行 —— 读文件的人以为只有 10 条判据；同族形态是
    CI 步骤名手抄"30 条实跑"与实际 34 条脱节、ROADMAP 版本号停在上一版。
    根因同一：**同一个清单有两处实现（代码 / 说明），改一处不会让另一处跟上**（M5⑥）。
    零命中不得判绿（R247）：解析不到任何 G 编号 = 正则失效，不是"没有判据"。
    """
    # 一条 check() 可以同时承担多条判据（实际有 `check("G6+G7 ...")` 这种合并项）
    # ⇒ 必须把整条名字里的 G 编号全取出来。首版只取第一个数字，当场把 G7 误判成"登记了没执行"
    #   （判据自己太窄导致的假红 —— 先修判据，不动登记，R263）。
    executed = set()
    for m in re.finditer(r'check\(\s*"([^"]*)"', source_text):
        executed.update(re.findall(r"G(\d+)", m.group(1)))
    documented = set(re.findall(r"^\s*G(\d+)", header_text, re.M))
    if not executed:
        return ["G13 解析不到任何 check(\"G..\") ⇒ 判据清单为空，不得据此判绿"]
    missing = sorted(set(executed) - set(documented), key=int)
    ghost = sorted(set(documented) - set(executed), key=int)
    bad = []
    if missing:
        bad.append(f"已执行但未在头部登记的判据：G{'、G'.join(missing)}")
    if ghost:
        bad.append(f"头部登记但 main() 里查无实行的判据：G{'、G'.join(ghost)}")
    return bad


def _st_mut_a(bad):
    """r94：由 `selftest` 前段整体下移（selftest 原 291 行 > loc_guard 的 150 行门）。

    切点由 AST 求得（段内 ≤140 行且跨越变量最少），不靠目测；本段产出 ex0/n_all/p 供后段用。
    """
    cfg = load_yaml(".github/dependabot.yml")
    if validate_dependabot(cfg):
        bad.append(f"原样配置被判失败：{validate_dependabot(cfg)}")
    t1 = json.loads(json.dumps(cfg)); t1["updates"][0]["package-ecosystem"] = "mavenx"
    if not validate_dependabot(t1):
        bad.append("篡改①（ecosystem 拼错）未被抓到 ⇒ 恒真")
    t2 = json.loads(json.dumps(cfg)); t2["updates"][0]["directory"] = "/no-such-dir"
    if not validate_dependabot(t2):
        bad.append("篡改②（directory 不存在）未被抓到 ⇒ 恒真")
    t3 = json.loads(json.dumps(cfg)); t3["updates"][0]["schedule"]["interval"] = "hourly-ish"
    if not validate_dependabot(t3):
        bad.append("篡改③（interval 非法）未被抓到 ⇒ 恒真")
    j, s = readme_claims()
    if j == 999 or s == 9999:
        bad.append("README 数字解析本身就是 999 ⇒ 判据读的是空气")
    if validate_dependabot({"version": 2, "updates": []}) == []:
        bad.append("篡改④（updates 清空）未被抓到 ⇒ 恒真")
    db_ni = json.loads(json.dumps(cfg))
    for _u in (db_ni.get("updates") or []):
        if _u.get("package-ecosystem") == "maven":
            _u.pop("ignore", None)
    # 篡改④b（r50）：把 maven 的 ignore 摘掉 ⇒ 必须红。
    # 反向还要证"不扩面"：actions 没有 ignore 也**不该**被判红（否则就是无据推广策略）。
    if db_ni and not validate_dependabot(db_ni):
        bad.append("篡改④b（摘掉 maven 的 ignore 大版本）未被抓到 ⇒ G1b 恒真")
    acts_only = {"version": 2, "updates": [{"package-ecosystem": "github-actions", "directory": "/",
                 "schedule": {"interval": "weekly"}}]}
    if validate_dependabot(acts_only):
        bad.append("篡改④c：actions 侧无 ignore 被判红 ⇒ 策略被无据扩面（实测 major 升级可正常合并）")
    nt = (ROOT / NOTICES).read_text("utf-8") if (ROOT / NOTICES).exists() else ""
    rt = (ROOT / "README.md").read_text("utf-8")
    vf, vp = manifest_vendor_files()
    vh = vendor_headers(vp)
    if not vf:
        bad.append("G6 分母取不到（vendor-manifest.json 缺失或 libs 为空）⇒ 判据无从判，记失败不记通过")
    if license_scope(nt, rt, vf, vp, vh):
        bad.append(f"原样授权声明被判失败：{license_scope(nt, rt, vf, vp, vh)}")
    if not license_scope(nt.replace("gsap.min.js", "zzz"), rt, vf, vp, vh):
        bad.append("篡改⑤（授权清单里抹掉 gsap.min.js）未被抓到 ⇒ G6 恒真")
    if not license_scope(nt, rt.replace("THIRD-PARTY-NOTICES", "zzz"), vf, vp, vh):
        bad.append("篡改⑥（README 去掉指向授权清单的口径行）未被抓到 ⇒ G7 恒真")
    # 篡改⑤b：**整列抹掉授权信息** ⇒ 必须红。
    # ⚠️ 第一版只替换 "**MPL-2.0**" 那几个字，而同一列里还留着 banner 原文
    # `Mozilla Public License, v. 2.0` ⇒ 反例根本没造成缺陷却期望判红（无效反例，见 [[invalid-negative-control]]）。
    cell_anchor = "**MPL-2.0**（banner 自证 `Copyright (c) 2015 - 2024 Deque Systems, Inc.` + `Mozilla Public License, v. 2.0`）"
    bare = nt.replace(cell_anchor, "见上游")
    if cell_anchor not in nt:
        bad.append("篡改⑤b 的夹具失效：授权列原文与判据锚点不一致（文档被改过，测试要同步）")
    elif bare == nt or not license_scope(bare, rt, vf, vp, vh):
        bad.append("篡改⑤b（把 axe-core 的授权列整列改成「见上游」）未被抓到 ⇒ 登记判据可被洗白")
    # 篡改⑤c：名册新增一个 vendored 件而归属表没动 ⇒ 必须红（分母来自名册，不来自目录扫描）
    if not license_scope(nt, rt, vf + ["brand-new-lib.min.js"], vp + ["_test/vendor/brand-new-lib.min.js"], vh):
        bad.append("篡改⑤c（名册多一个未登记的 vendored 文件）未被抓到 ⇒ 新库仍可隐形")
    # 篡改⑤d：把归属文里 `_test/vendor` 这条边界交代抹掉 ⇒ 必须红（正向要求的对偶断言）
    if not license_scope(nt.replace("_test/vendor", "_test/zzz"), rt, vf, vp, vh):
        bad.append("篡改⑤d（抹掉 _test/vendor 边界交代）未被抓到 ⇒ 边界声明判据恒真")
    # 篡改⑤e：**把授权列改成与文件 banner 不符的说法**（GSAP 实物是 GreenSock 标准许可，写成 MIT 必须翻红）
    forged = nt.replace("**GreenSock Standard License**（非 MIT、非 OSI；免费用于非竞争性产品）", "**MIT**")
    if forged == nt:
        bad.append("篡改⑤e 的夹具失效：授权列原文与判据锚点不再一致（文档被改过，测试要同步）")
    elif not license_scope(forged, rt, vf, vp, vh):
        bad.append("篡改⑤e（把 GSAP 授权列伪写成 MIT）未被抓到 ⇒ 许可对账恒真")
    ct = (ROOT / "memory" / "06-constraints.md").read_text("utf-8")
    seg0, files0 = eval_section(ct), eval_data_files()
    if eval_scope(seg0, files0, eval_counts(seg0)):
        bad.append(f"原样评测集登记被判失败：{eval_scope(seg0, files0, eval_counts(seg0))}")
    if not eval_scope(seg0.replace("emotion-eval-dataset.json", "zzz.json"), files0, eval_counts(seg0)):
        bad.append("篡改⑦（抹掉评测集登记行）未被抓到 ⇒ G8 恒真")
    shrunk = seg0.replace("**73 条**", "**9 条**")
    if not eval_scope(shrunk, files0, eval_counts(shrunk)):
        bad.append("篡改⑧（把声称条数改小）未被抓到 ⇒ G8 条数判据恒真")
    if not eval_scope(eval_section(ct.replace("评测集隔离", "zzz节")), files0, eval_counts(seg0)):
        bad.append("篡改⑨（删掉整节标题）未被抓到 ⇒ G8 恒真")
    back = seg0.replace("- 测试专用文件清单（r23", "- 测试专用文件清单：（如 eval/x.json / blindset / frozen）\n  - 备注（r23")
    if not eval_scope(back, files0, eval_counts(back)):
        bad.append("篡改⑩（表退回 init 模板原句）未被抓到 ⇒ 占位符判据恒真")
    # 篡改⑪：G9 两侧都要验（只验"该红"会漏掉"把一切判红"的恒假判据）
    nognb = "import sys\ndef main():\n    return 0\nsys.exit(main())\n"
    if not import_safety(nognb):
        bad.append("篡改⑪a（无 __main__ 守卫的脚本）未被抓到 ⇒ G9 恒真")
    if import_safety("import sys\ndef main():\n    return 0\nif __name__ == '__main__':\n    sys.exit(main())\n"):
        bad.append("篡改⑪b（有守卫的脚本）被判失败 ⇒ G9 恒假，判据只会刷红")
    if import_safety("import sys\ndef main():\n    if len(sys.argv) > 9:\n        sys.exit(2)\n    return 0\nif __name__ == '__main__':\n    sys.exit(main())\n"):
        bad.append("篡改⑪c（函数体内缩进的 sys.exit 被判违规）⇒ G9 没分清顶层与函数内")
    # 篡改⑪d：G9 第二腿（解析得动）两侧都要验。正例是**本仓真实全量**——
    # 只验合成样本会漏掉"判据对本仓真实文件恒假"这一形（首版 java 腿就是这么被实测打回的）。
    if not py_syntax_hygiene("def f():\n    return \"未闭合\n"):
        bad.append("篡改⑪d（SyntaxError 文件）未被抓到 ⇒ G9 解析腿恒真")
    if py_syntax_hygiene("def f():\n    return \"ok\"\n"):
        bad.append("篡改⑪e（合法文件被判解析失败）⇒ G9 解析腿恒假")
    _realbad = [p.name for p in sorted((ROOT / "_test").glob("*.py"))
                if py_syntax_hygiene(p.read_text("utf-8", errors="replace"))]
    if _realbad:
        bad.append(f"篡改⑪f：本仓真实判据脚本有 {_realbad} 解析失败却该由 G9 主体报红")
    # 篡改⑪g..⑪j：G9 第三腿（r90）——模块级裸字符串 = docstring/def 首行被编辑吞掉的指纹。
    #   反例形状直接取自本轮我自己写坏的那两处：一处 SyntaxError（⑪d 已抓），
    #   一处 `def lag_days` 被吞后**编译全过**、`--selftest` 也过 ⇒ 只有这条腿看得见。
    if not docstring_swallow('def a():\n    return 1\n    "上面那行 def 被吞了，这段本该是它的 docstring"\n'):
        bad.append("篡改⑪g（`def` 被吞→块内非首条裸字符串）未被抓到 ⇒ G9 第三腿恒真")
    if docstring_swallow('"""模块 docstring。"""\n\nimport sys\n\ndef a():\n    return 1\n'):
        bad.append("篡改⑪h（合法模块 docstring 被判违规）⇒ G9 第三腿恒假")
    if docstring_swallow('import sys\ndef a():\n    """函数 docstring 是块首，不算违规。"""\n    return 1\n'):
        bad.append("篡改⑪i（块首 docstring 被误判）⇒ 第三腿没按「非首条」取数")
    _dsbad = [p.name for p in sorted((ROOT / "_test").glob("*.py"))
              if docstring_swallow(p.read_text("utf-8", errors="replace"))]
    if _dsbad:
        bad.append(f"篡改⑪j：本仓真实判据脚本有 {_dsbad} 带块内非首条裸字符串却该由 G9 第三腿判红")
    # 篡改⑪k：第三腿的对照必须打到**真实文件本文**（誊写夹具会顺手把错的地方改对）——
    #   这里在内存里把 r90 自己吞掉的那一行 `def lag_days(commits):` 从真文里删掉再跑，
    #   判据必须翻红；再把那一行原样放回，必须翻绿。两侧都取到才算这条腿有判定力。
    _rg = (ROOT / "_test" / "release_governance_check.py").read_text("utf-8", errors="replace")
    _broken = _rg.replace("def lag_days(commits):\n", "", 1)
    if _broken == _rg:
        bad.append("篡改⑪k 前置不成立：真文里找不到 `def lag_days(commits):` 那一行 ⇒ 这条对照打不到对象")
    elif not docstring_swallow(_broken):
        bad.append("篡改⑪k（真文吞掉 def 行）未被第三腿抓到 ⇒ 腿对本次真实事故无判定力")
    elif docstring_swallow(_rg):
        bad.append("篡改⑪k 复原侧判红 ⇒ 第三腿把完好文件也咬了（恒假）")
    # 篡改⑫：CI 覆盖面的正反两侧（缺电池步骤 / 幽灵豁免 必须报红；原样必须零违规）
    st = (ROOT / "_test" / "run_all_suites.py").read_text("utf-8", errors="replace")
    ci0 = (ROOT / ".github" / "workflows" / "ci.yml").read_text("utf-8", errors="replace")
    g0, n_all, ex0 = ci_battery_audit(ci0, st)
    if g0:
        bad.append(f"原样 CI 覆盖被判失败：{g0}")
    if ci_battery_audit(ci0.replace("run_all_suites.py --exclude-llm", "browser_check.py"), st)[0] == []:
        bad.append("篡改⑫a（CI 退回只跑单条判据）未被 G10 抓到 ⇒ G10 恒真")
    if ci_battery_audit(ci0.replace(" --exclude-llm", ""), st)[0] == []:
        bad.append("篡改⑫b（CI 跑电池但不声明豁免）未被 G10 抓到")
    # 变异必须**只动豁免集合**：上一版用裸 replace('"stream_contract"', ...) 把 SUITES 里的同名条目
    # 一起改了，于是"幽灵"自己变得合法 —— 反例造得不干净，等于没造（r28 实测这条报"未被抓到"）。
    ghost_src = st.replace('"stream_contract", "online_check"}', '"stream_contract", "no_such_suite"}')
    if ghost_src == st:
        bad.append("篡改⑫c 的锚点没命中 ⇒ 变异未生效（这种「没变却以为变了」必须单独抓）")
    elif ci_battery_audit(ci0, ghost_src)[0] == []:
        bad.append("篡改⑫c（幽灵豁免：豁免了一个不存在的套件）未被 G10 抓到")
    if ci_battery_audit(ci0.replace("run_all_suites.py --exclude-llm", "run_all_suites.py --exclude-llm --exclude-llm"), st)[0]:
        bad.append("篡改⑫d 对照失效：重复 flag 不应触发任何违规（判据过敏）")
    # 篡改⑬：依赖清单与 CI 装依赖（本次事故的机器化封口）
    # r94 注：AST 把 `p` 也报成跨越量，但它是**推导式局部变量**（`[p.name for p in ...]`），
    # py3 下不外泄 ⇒ 不进签名（照抄 AST 会拿到 NameError，实测踩到）。真正要交出去的是 n_all/ex0。
    return n_all, ex0


def _st_mut_b(bad):
    """r94：由 `selftest` 中段下移。这段只依赖 `bad`，不读前段产出（已逐行核过）。"""
    ci_full = (ROOT / ".github" / "workflows" / "ci.yml").read_text("utf-8", errors="replace")
    req_full = (ROOT / "_test" / "requirements.txt").read_text("utf-8", errors="replace")
    imps = third_party_imports(ci_invoked_scripts(ci_full, (ROOT / "_test" / "run_all_suites.py").read_text("utf-8", errors="replace")))
    g11_0, r_run, r_ins = ci_deps_audit(ci_full, req_full, imps)
    if g11_0:
        bad.append(f"原样 CI 依赖被判失败：{g11_0}")
    if ci_deps_audit(ci_full.replace("pip install -r _test/requirements.txt", "pip install nothing"), req_full, imps)[0] == []:
        bad.append("篡改⑬a（job 不装清单）未被 G11 抓到 ⇒ 恒真")
    if ci_deps_audit(ci_full, req_full.replace("PyYAML", ""), imps)[0] == []:
        bad.append("篡改⑬b（清单漏一个真实依赖）未被 G11 抓到")
    if ci_deps_audit(ci_full, req_full + "\nrequests\n", imps)[0] == []:
        bad.append("篡改⑬c（清单里的幽灵依赖，没人 import）未被 G11 抓到")
    if not r_run:
        bad.append("篡改⑬ 反例组失效：CI 里根本没解析到跑判据的 job（G11 在读空气）")
    # 篡改㉕a..c（r95）：G9 的取数面由「文本行」换成「AST 顶层语句」，两侧都要验。
    #   一手代价：`verdict_exit_parity_check.py` 的自检样本 GOOD_EXPLICIT 是三引号字符串，串内那行
    #   col-0 的 `sys.exit(0 if ok else 1)` 让一件**本来 import-safe** 的判据被判红（假阳）。
    #   腿放在本段而非 `_st_mut_a`：后者是 r94 拆出来的 149 行段，加 9 行就撞 loc 门的函数长 150。
    if import_safety("SAMPLE = '''\nimport sys\nsys.exit(1)\n'''\nOK = True\n"):
        bad.append("篡改㉕a（字符串字面量内的 sys.exit 被当成顶层入口）⇒ 取数面仍是文本行而非 AST 语句")
    if not import_safety("import sys\nsys.exit(1)\n"):
        bad.append("篡改㉕b（同形态摘掉引号成真顶层调用后未判红）⇒ ㉕a 是空腿，证不了任何东西")
    # ㉕c 已知软面（**故意不判红**，钉成用例而非留给下一个人重新发现）：顶层 `if <非 __name__ 条件>:`
    #   体内的入口调用缩进 >0，旧尺（col 0）与新尺（tree.body 直接子节点）都看不见 ⇒
    #   本尺只判「直写顶层」这一形，不作终审；j4 那类整篇顶层脚本亦在此面内（见 r95 报告 §5）。
    if import_safety("import sys\nif len(sys.argv) > 1:\n    sys.exit(1)\n"):
        bad.append("篡改㉕c（顶层 if 体内的缩进入口被判红）⇒ 与旧尺覆盖面不一致，本次改动越界")
    # 篡改⑭：版本断言三源对账（r35 一手实证 —— ROADMAP 停在 v1.3.0 而 tag/pom 已是 1.4.0）


def _st_g16_git_face(bad, real_scripts, real_doc, real_disk):
    """㉑e-g（r99）G16 第三面 git index 的三条腿。

    抽成独立函数的原因不是美观：`_st_mut_c` 加这 10 行后函数长 160 > `loc_guard --enforce`
    的 150 上限，本仓的行数门当场把我拦下（LOC-FAIL 点名 `_st_mut_c`）。
    """
    if not gate_doc_audit(real_scripts, real_doc, real_disk, set()):
        bad.append("篡改㉑e（真电池配空 git index）未被抓到 ⇒ 「在盘未入库」这一态仍隐形（r98 两把尺的原事故）")
    if gate_doc_audit(real_scripts, real_doc, real_disk, real_scripts):
        bad.append("篡改㉑f（git 面 ⊇ 电池全集）被判红 ⇒ 第三腿过严，第一次接真面就误伤")
    real_tracked = git_index_scripts()
    if not real_tracked:
        bad.append("㉑g git index 面取不到或为空 ⇒ 第三腿本轮未验，不得把「没报红」当「验过」")
    else:
        want = [s for s in real_scripts if s not in real_tracked]
        got = [l for l in gate_doc_audit(real_scripts, real_doc, real_disk, real_tracked)
               if "git 未跟踪" in l]
        if bool(want) != bool(got):
            bad.append("㉑g 第三腿读数与独立现算的未跟踪集不一致（现算 %d 条，判据报 %d 行）"
                       "⇒ 它解析的不是 index 面" % (len(want), len(got)))


def _st_mut_c(bad, n_all, ex0):
    """r94：由 `selftest` 后段下移（含收尾打印与退出码）。

    `n_all`/`ex0` 由前段产出、收尾打印要用 ⇒ 显式入参（AST 在切点 1083 报的跨越集是空的，
    那是因为它按「定义于前、读于后」统计，而这两个名字在收尾 print 里被读 ⇒ 仍须传入）。
    """
    if version_truth("v1.4.0", "1.4.0"):
        bad.append("篡改⑭a（tag 与 pom 相等）被判失败 ⇒ G12 恒假，只会刷红")
    if not version_truth("v1.4.0", "1.3.0"):
        bad.append("篡改⑭b（两个权威源互斥）未被 G12 抓到 ⇒ 恒真")
    if not version_truth("", "1.4.0"):
        bad.append("篡改⑭c（取不到 tag = 判据在读空气）未被 G12 抓到")
    if version_doc_audit({"ROADMAP.md": "当前版本：**v1.4.0**"}, "1.4.0"):
        bad.append("篡改⑭d（文档等于权威源）被判失败 ⇒ 文档侧恒假")
    if not version_doc_audit({"ROADMAP.md": "当前版本：**v1.3.0**"}, "1.4.0"):
        bad.append("篡改⑭e（文档落后一版，正是本次真实缺陷形态）未被 G12 抓到")
    if not version_doc_audit({"ROADMAP.md": "这一节没写版本", "README.md": "也没有"}, "1.4.0"):
        bad.append("篡改⑭f（全仓零版本断言 / ROADMAP 断言行失踪）未被 G12 抓到 ⇒ 零命中被判绿（R247）")
    # 篡改⑮：判据清单与头部说明对账（G13 自己也得被登记，否则它就是个暗判据）
    src_self = Path(__file__).read_text("utf-8", errors="replace")
    if guard_inventory(HEADER_DOC, src_self):
        bad.append(f"篡改⑮a（本文件自身）被判失败：{guard_inventory(HEADER_DOC, src_self)}")
    fake_hdr = "\n".join(f"  G{i} 占位" for i in range(1, 12)) + "\n"
    if not guard_inventory(fake_hdr, 'check("G1 ok")\ncheck("G12 版本")\n'):
        bad.append("篡改⑮b（执行了 G12 而头部只到 G11）未被 G13 抓到 ⇒ 恒真")
    if not guard_inventory("  G9 只有这一条\n", 'check("G1 x")\ncheck("G2 y")\n'):
        bad.append("篡改⑮c（头部登记与实际执行两套账）未被 G13 抓到")
    if not guard_inventory("  G1 占位\n", 'print("没有判据")\n'):
        bad.append("篡改⑮d（零命中：解析不到任何 G）未被 G13 抓到 ⇒ 读空气被判绿")
    # 篡改⑯：tag 解析必须对两种形态都成立（r35 实测 CI 浅克隆无本地 tag ⇒ G12 假红）
    if pick_latest_tag("v1.3.0\nv1.4.0\n") != "v1.4.0":
        bad.append("篡改⑯a（本地 `git tag` 两行形态）挑错版本")
    lsremote = ("aaa refs/tags/v1.3.0\nbbb refs/tags/v1.3.0^{}\n"
                "ccc refs/tags/v1.4.0\nddd refs/tags/v1.4.0^{}\n")
    if pick_latest_tag(lsremote) != "v1.4.0":
        bad.append("篡改⑯b（`ls-remote --tags` 含 ^{} 剥离行）挑错 ⇒ 未覆盖 CI 形态")
    if pick_latest_tag("") != "" or pick_latest_tag("no tags\n") != "":
        bad.append("篡改⑯c（空输入/无 tag）没返回空串 ⇒ 会拿垃圾当版本")
    if pick_latest_tag("v1.10.0\nv1.9.0\n") != "v1.10.0":
        bad.append("篡改⑯d（两位数minor）按字典序排 ⇒ 1.9 被判大于 1.10")
    # ⑱ G15 AC 追溯键：真文件须放行 / 多造一条重复须红 / 零定义须红
    real_ac = _read("memory/08-ac-obs.md")
    if ac_id_audit(real_ac):
        bad.append(f"篡改⑱a（真实 08 应按基线放行）被判红：{ac_id_audit(real_ac)}")
    if not ac_id_audit(real_ac + "\n- [x] AC-OBS-23: 又一条命题挂着同一个 id\n"):
        bad.append("篡改⑱b（新增一条 id 重复）未被 G15 抓到 ⇒ 棘轮失效")
    if not ac_id_audit("# 标题\n没有定义行\n"):
        bad.append("篡改⑱c（零定义）被判绿 ⇒ 读空气")
    # ⑰ G14 对标仓数：正向（一致）必须零问题，三种负向必须各自报红
    ok_line = "python _test/benchmark_metrics.py  # 对标源数据台账（16 仓指标 + …）"
    if peer_count_audit(ok_line, 16):
        bad.append("篡改⑰a（README 与台账一致）被误判红 ⇒ 判据过严，第一次接真文就误伤")
    if not peer_count_audit(ok_line.replace("16 仓", "9 仓"), 16):
        bad.append("篡改⑰b（文档 9 仓 vs 台账 16 仓）未被抓到 ⇒ 恒绿")
    if not peer_count_audit("台账说明（删掉了仓数断言）", 16):
        bad.append("篡改⑰c（现行状态句失踪）未被抓到 ⇒ 声明失去机器责任方却判绿（R247 同族）")
    if not peer_count_audit(ok_line, None):
        bad.append("篡改⑰d（台账取不到权威值）被判绿 ⇒ 无权威值可比时必须红")
    # ㉑ G16 电池脚本 ⇄ quality-gates 双向对账：正向用**真文档真电池**跑（证明不误伤），
    #    三条负向各自必须红（漏登记 / 幽灵登记 / 零分母）。首跑只测负向会漏掉"判据过严"这一族。
    real_scripts = battery_scripts()
    real_doc = _read("docs/quality-gates.md")
    real_disk = {p.name for p in (ROOT / "_test").iterdir() if p.is_file()}
    g16now = gate_doc_audit(real_scripts, real_doc, real_disk)
    if g16now:
        bad.append("篡改㉑a（当前真实文档与电池）被判红：%s" % g16now)
    victim = sorted(real_scripts)[0]
    thinned = "\n".join(l for l in real_doc.splitlines() if victim not in l)
    if not gate_doc_audit(real_scripts, thinned, real_disk):
        bad.append("篡改㉑b（从文档抹掉一条真在电池里的脚本 %s）未被抓到 ⇒ 漏登记可隐形" % victim)
    if not gate_doc_audit(real_scripts, real_doc + "\npython _test/ghost_check_never_written.py  # 幽灵\n", real_disk):
        bad.append("篡改㉑c（文档引用不存在的判据脚本）未被抓到 ⇒ 反向腿失效")
    if not gate_doc_audit(set(), real_doc, real_disk):
        bad.append("篡改㉑d（分母取空）被判绿 ⇒ 违 R247 零命中不得判绿")
    _st_g16_git_face(bad, real_scripts, real_doc, real_disk)
    # ㉔ G19 docs 索引双向对账：正向不误伤 + 抹链接必红 + 幽灵引文必红 + 空分母不得判绿
    dn_real = sorted(p.name for p in (ROOT / "docs").iterdir() if p.is_file()) \
        if (ROOT / "docs").exists() else []
    di_real = _read("docs/README.md")
    if docs_index_audit(di_real, dn_real):
        bad.append("篡改㉔a（当前真实 docs 索引）被判红：%s" % docs_index_audit(di_real, dn_real))
    _dvictim = next((n for n in dn_real if n not in ("README.md", "openapi.yaml")), "")
    if _dvictim:
        _thinned = re.sub(r"\]\(" + re.escape(_dvictim) + r"(?:#[^)]*)?\)", "](索引里被抹掉的一行)", di_real)
        if _thinned == di_real:
            bad.append(f"篡改㉔b 前置不成立：索引里找不到 {_dvictim} 的链接 ⇒ 这条腿在打不存在的靶子")
        elif not docs_index_audit(_thinned, dn_real):
            bad.append(f"篡改㉔b（从索引抹掉 {_dvictim} 的链接）未被抓到 ⇒ 漏引可隐形")
    if not docs_index_audit(di_real + "\n[幽灵](NEVER_WRITTEN_DOC.md)\n", dn_real):
        bad.append("篡改㉔c（索引引一份磁盘没有的文档）未被抓到 ⇒ 反向腿失效")
    if not docs_index_audit(di_real, []):
        bad.append("篡改㉔d（docs 分母取空）被判绿 ⇒ 违 R247 零命中不得判绿")
    # ㉒ G17 台账取数面：正向必须零问题（不误伤真台账），四条负向各自必须红，零输入不得判绿
    ls_real = ledger_last_self()
    if ledger_face_problems(ls_real):
        bad.append("篡改㉒a（当前真实台账）被判红：%s" % ledger_face_problems(ls_real))
    if ls_real and ls_real.get("self_face") == "HEAD":
        noface = {k: v for k, v in ls_real.items() if k != "self_face"}
        if not ledger_face_problems(noface):
            bad.append("篡改㉒b（抹掉 self_face 字段）未被抓到 ⇒ 面声明缺失可隐形")
        else:
            ok_face = ledger_face_problems(dict(ls_real, self_face="HEAD"))
            if ok_face:
                bad.append("篡改㉒b 的正面对照失效（合规值也判红，说明这条腿恒真）：%s" % ok_face)
        if not ledger_face_problems(dict(ls_real, self_face="worktree")):
            bad.append("篡改㉒c（self_face 改成 worktree）未被抓到 ⇒ 只查字段存在不查值")
        if not ledger_face_problems(dict(ls_real, self_face_errors="boom")):
            bad.append("篡改㉒d（面取数报错仍落账）未被抓到 ⇒ 静默降级照样能绿")
        if not ledger_face_problems(dict(ls_real, regression_suites=0)):
            bad.append("篡改㉒e（suites 记 0）未被抓到 ⇒ 零输入被判成已验")
    else:
        bad.append("篡改㉒前提：真台账 self_face 不是 HEAD 或读不到，㉒b-e 全部未取证")
    if not ledger_face_problems(None):
        bad.append("篡改㉒f（整个 self 行缺失）被判绿 ⇒ 无对象可判时不得判绿")
    # ㉓ G18 收口摘要行：正向取 HEAD 真面必须零问题，四条反向各自必须**点名的**红（r74 一手：该行的 rc 曾是字面量）
    g18_real = ""
    try:
        g18_real = head_blob("_test/run_all_suites.py")
    except Exception as e:
        bad.append("篡改㉓前提：取不到 HEAD 的聚合器正文（%s）⇒ G18 未取证" % str(e)[:40])
    if g18_real:
        if battery_rc_facade_problems(g18_real):
            bad.append("篡改㉓a（当前 HEAD 聚合器正文）被判红：%s" % battery_rc_facade_problems(g18_real))
        probs_b = battery_rc_facade_problems(g18_real.replace("rc={bat_rc}", "rc=0"))
        if not probs_b:
            bad.append("篡改㉓b（插值改回硬印 rc=0）未被抓到 ⇒ 判据对本仓真实历史形状恒绿")
        elif "硬印" not in " ".join(probs_b):
            bad.append("篡改㉓b 红了但没点名「硬印」：%s" % probs_b)
        if not battery_rc_facade_problems(re.sub(r'print\(.{0,4}BATTERY:[^\n]*', "", g18_real)):
            bad.append("篡改㉓c（抹掉整行摘要）被判绿 ⇒ 形状漂移静默放行")
        if not battery_rc_facade_problems(g18_real.replace("return bat_rc", "return 0")):
            bad.append("篡改㉓d（return 与打印不同源）未被抓到 ⇒ 只查打印行")
    if not battery_rc_facade_problems(""):
        bad.append("篡改㉓e（空正文）被判绿 ⇒ 违 R247 零输入不得判绿")
    real = sorted((ROOT / "_test").glob("*.py"))
    viol = [p.name for p in real if import_safety(p.read_text("utf-8", errors="replace"))]
    if viol:
        bad.append(f"篡改⑪d（真实判据脚本 {len(real)} 个里有 {len(viol)} 个 import 即执行：{viol}）")
    # 反例条数**从代码里算**，不手抄：上一版写"十一类"、这一版写"十五类"，两次都与实际断言数脱节
    # ——这正是本项目反复登记的"文档手抄数字"同一族，判据自己也不能例外。
    n_mut = Path(__file__).read_text("utf-8").count('bad.append("篡改')
    print(f"SELFTEST-PASS: {n_mut} 条合成篡改断言全部被抓到、原样零问题（CI 实跑 {n_all} 套件 / 豁免 {len(ex0)}）"
          if not bad else "SELFTEST-FAIL: " + "; ".join(bad))
    return 1 if bad else 0


def selftest():
    """r94：只留调度——三段断言体已下移到 `_st_mut_a/b/c`。

    拆的动因是 loc_guard 的函数长门（≤150）；拆法保证调用序与原来逐语句一致，
    故首个失败点、断言条数与退出码都不变（`--selftest` 的 n_mut 是验真点）。
    """
    bad = []
    n_all, ex0 = _st_mut_a(bad)
    _st_mut_b(bad)
    return _st_mut_c(bad, n_all, ex0)



def _cfg_head():
    """r94：main() 的 argparse + 环境门（原 main 171 行 > loc_guard 的 150 行门）。

    `check()`（第 84 行）与 `results`（第 81 行）都在模块级 ⇒ 各段追加无需传参。
    """
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--online", action="store_true")
    a = ap.parse_args()
    try:
        import yaml  # noqa: F401
    except Exception as e:
        print(f"REPO-CONFIG-ENV-ERROR: 缺 PyYAML（{e}）")
        return 2
    if a.selftest:
        sys.exit(selftest())

    db = ROOT / ".github" / "dependabot.yml"
    if not db.exists():
        print("REPO-CONFIG-FAIL: 缺 .github/dependabot.yml（r21 配的依赖自动更新被删了？）")
        return 1
    bad = validate_dependabot(load_yaml(".github/dependabot.yml"))
    check("G1 dependabot schema 与 manifest 目录可达", not bad, " ; ".join(bad))

    jobs = ci_jobs()
    j_claim, s_claim = readme_claims()
    check("G2 CI job 数 == README 声称的门禁数", j_claim is not None and len(jobs) == j_claim,
          f"ci.yml 实测 {len(jobs)} job {jobs} | README 声称 {j_claim}")
    spec_ok = (ROOT / "docs" / "openapi.yaml").exists()
    refs = "openapi.yaml" in (ROOT / "docs" / "README.md").read_text("utf-8", errors="replace") \
        if (ROOT / "docs" / "README.md").exists() else False
    check("G3 契约文件存在且被索引引用（不留孤文件）", spec_ok and refs,
          f"存在={spec_ok} 被 docs/README.md 引用={refs}")
    docs_names = sorted(p.name for p in (ROOT / "docs").iterdir() if p.is_file()) \
        if (ROOT / "docs").exists() else []
    g19bad = docs_index_audit(_read("docs/README.md"), docs_names)
    check("G19 docs/ 文件 ⇄ docs/README.md 索引双向对账（漏引/幽灵引都红）", not g19bad,
          f"docs/ 实有 {len(docs_names)} 件（分母从目录现读）| " + (" ; ".join(g19bad) or "全部在册"))
    n = battery_count()
    check("G4 电池条目数 == README 声称的套件数", s_claim is not None and s_claim == n,
          f"run_all_suites.py 实测 {n} | README 声称 {s_claim}")
    scripts = battery_scripts()
    on_disk = {p.name for p in (ROOT / "_test").iterdir() if p.is_file()}
    tracked = git_index_scripts()
    g16bad = gate_doc_audit(scripts, _read("docs/quality-gates.md"), on_disk, tracked)
    check("G16 电池脚本 ⇄ quality-gates 明细 ⇄ git index 三面双向对账（漏登/幽灵登/未入库皆红）",
          not g16bad,
          f"电池脚本 {len(scripts)} 条（分母从 SUITES 现读）| git index 面 "
          f"{len(tracked) if tracked is not None else '取不到 ⇒ 第三腿未验'} 条 | "
          + (" ; ".join(g16bad) or "全部在册"))
    pom, tag = pom_version(), latest_tag()
    docs_text = {name: (ROOT / name).read_text("utf-8", errors="replace")
                 for name in ("ROADMAP.md", "README.md") if (ROOT / name).exists()}
    g12bad = version_truth(tag, pom) + version_doc_audit(docs_text, pom)
    check("G12 版本断言三源对账（git tag == pom == 文档「当前版本」）", not g12bad,
          f"tag={tag or '取不到'} pom={pom or '取不到'} 文档={sorted(docs_text)} | " + " ; ".join(g12bad))
    # r39：可核对面跟着声明走。README 的「## ✅ 验证」一节整体迁往 docs/quality-gates.md 后，
    # 只扫 README 会让 G14 报"零命中"（r39 实测就这么红过一次）⇒ 审计面取 README ∪ 迁移目的地，
    # **只扩文件集合、不放宽正则**（历史轮次的「14 仓」陈述仍故意不匹配）。
    claim_text = docs_text.get("README.md", "") + "\n" + _read("docs/quality-gates.md")
    g14bad = peer_count_audit(claim_text, ledger_peer_count())
    check("G14 对标仓数断言 == 台账权威值（README 现行状态句）", not g14bad,
          f"台账 peers_expected={ledger_peer_count()} | " + (" ; ".join(g14bad) or "README 断言与台账一致"))
    # G17（r72，[推荐:R71-01] 的机器落点）：台账 self 行必须显式声明自己取自 git 面
    lself = ledger_last_self()
    g17bad = ledger_face_problems(lself)
    head_now = head_battery_count()
    led_n = (lself or {}).get("regression_suites")
    diff_txt = ("差值=%s" % ("?" if (head_now is None or not isinstance(led_n, int)) else led_n - head_now))
    check("G17 对标台账 self 行的取数面必须显式为 HEAD（禁把工作树态写成现状）", not g17bad,
          f"self_face={(lself or {}).get('self_face')!r} 台账记 suites={led_n} ｜ HEAD 现算={head_now} ｜ {diff_txt}（差值只报不拦：CI 无法重跑采集来刷新台账） | "
          + (" ; ".join(g17bad) or "面声明齐"))
    try:
        g18src = head_blob("_test/run_all_suites.py")
    except Exception as e:
        g18src = ""
    g18bad = battery_rc_facade_problems(g18src)
    g18line = (re.findall(r'print\(.{0,4}BATTERY:[^\n]*', g18src) or ["（HEAD 里没有 BATTERY 摘要行）"])[0].strip()
    check("G18 聚合器收口行必须印真退出码（禁硬印 rc 字面量；只在 HEAD 面判）", not g18bad,
          "HEAD 摘要行=%s ｜ %s" % (g18line[:74], " ; ".join(g18bad) or "rc 跟着 return 走"))
    ac_text = _read("memory/08-ac-obs.md")
    acbad = ac_id_audit(ac_text)
    check("G15 AC 追溯键唯一性棘轮（08 一个 id 一条命题，存量基线 %d）" % AC_DUP_BASELINE,
          not acbad, acbad and " ; ".join(acbad)
          or "无新增重复（存量 7 条按基线放行，重编号另登 07 待办）")
    g13bad = guard_inventory(HEADER_DOC, Path(__file__).read_text("utf-8", errors="replace"))
    check("G13 判据账本自洽（头部登记 == main() 实际执行，漏登/幽灵登都红）", not g13bad,
          " ; ".join(g13bad))
    return a


def _cfg_body(a):
    """r94：main() 的在线通道 + G6/G7/G8/G11/G10/G9（原样搬，判据口径零改写）。"""
    if a.online:
        repo = None
        try:
            u = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True,
                               text=True, encoding="utf-8", timeout=30).stdout
            m = re.search(r"[:/]([^/]+)/([^/]+?)(\.git)?$", u.strip())
            repo = f"{m.group(1)}/{m.group(2)}" if m else None
            ok, why = remote_has_file(".github/dependabot.yml", repo)
            check("G5 默认分支上 dependabot 配置可见（GitHub 只看默认分支）", ok, f"{repo} {why}")
        except OSError as e:
            print(f"REPO-CONFIG-ENV-ERROR: 在线核验不可达 {e}")
            return 2
    else:
        print("  SKIP  G5 远端受理面（加 --online 才查 GitHub 默认分支）")

    ntxt = (ROOT / NOTICES).read_text("utf-8") if (ROOT / NOTICES).exists() else ""
    if not ntxt:
        print("REPO-CONFIG-FAIL: 缺 docs/THIRD-PARTY-NOTICES.md（vendor 里有第三方库，必须逐文件声明授权）")
        return 1
    vfiles, vpaths = manifest_vendor_files()
    vheads = vendor_headers(vpaths)
    if not vfiles:
        # 分母取不到不是"很干净"：名册是 vendored 资产的唯一声明源，缺它=全部第三方件同时隐形
        check("G6+G7 第三方授权边界已声明且逐文件登记（GSAP 非 MIT 不可含糊）", False,
              "取不到 _test/vendor-manifest.json 的 libs ⇒ G6 无分母，判红不判过")
    else:
        lbad = license_scope(ntxt, (ROOT / "README.md").read_text("utf-8"),
                          vfiles, vpaths, vheads)
        check("G6+G7 第三方授权边界已声明且逐文件登记（GSAP 非 MIT 不可含糊）", not lbad,
              " ; ".join(lbad) + "｜分母=%d(名册现读)" % len(vfiles))

    ct = (ROOT / "memory" / "06-constraints.md").read_text("utf-8") if (ROOT / "memory" / "06-constraints.md").exists() else ""
    seg, dfiles = eval_section(ct), eval_data_files()
    ebad = eval_scope(seg, dfiles, eval_counts(seg))
    check("G8 评测集来源已登记且声称条数==实际条数（R196 红线机器化）", not ebad, " ; ".join(ebad)
          + f" | 裁决用数据 {dfiles} | 登记表抽到条数 {eval_counts(seg)}")

    reqp = ROOT / "_test" / "requirements.txt"
    g11bad, n_runs, n_inst = ci_deps_audit(
        (ROOT / ".github" / "workflows" / "ci.yml").read_text("utf-8", errors="replace"),
        reqp.read_text("utf-8", errors="replace") if reqp.exists() else "",
        third_party_imports(ci_invoked_scripts(
            (ROOT / ".github" / "workflows" / "ci.yml").read_text("utf-8", errors="replace"),
            (ROOT / "_test" / "run_all_suites.py").read_text("utf-8", errors="replace"))))
    check("G11 依赖清单==判据实际 import，且跑判据的 job 都装了清单", not g11bad,
          f"{n_runs} 个 job 跑判据 / {n_inst} 个装了 requirements.txt；清单={sorted(req_names(reqp.read_text('utf-8', errors='replace')) if reqp.exists() else [])}")

    gbad, n_all, ex0 = ci_battery_audit(
        (ROOT / ".github" / "workflows" / "ci.yml").read_text("utf-8", errors="replace")
        if (ROOT / ".github" / "workflows" / "ci.yml").exists() else "",
        (ROOT / "_test" / "run_all_suites.py").read_text("utf-8", errors="replace"))
    check("G10 判据挂在真会走的路径上（CI 跑电池 + 豁免可自证）", not gbad,
          f"CI 整跑电池，实跑 {n_all - len(ex0)} + 豁免 {len(ex0)} == {n_all} 套件（豁免={sorted(ex0)}，原因=runner 无上游密钥）"
          + (" ; " + " ; ".join(gbad) if gbad else ""))

    scripts = sorted((ROOT / "_test").glob("*.py"))
    iviol = [f"{p.name} → {import_safety(p.read_text('utf-8', errors='replace'))[0]}"
             for p in scripts if import_safety(p.read_text("utf-8", errors="replace"))]
    # G9 第二腿（r51 §5-P1 立的账，本轮机器化）：判据脚本必须**解析得动**。
    # 动因不是"又想加一条"，而是台账里"内联/heredoc 写盘吞转义与引号"已复发 12 次，
    # 而 `third_party_imports()` 对 SyntaxError 是 `except: continue` ⇒ 被写坏的文件
    # 在依赖审计里**直接隐身**。⚠️ Java 那一半试过文本启发式，误报 6/20，已撤出判定集合
    #（该事实的权威判据是 javac + T4 盯 -DskipTests，见 java_quote_parity 的 docstring）。
    syviol = [f"{p.name} → {py_syntax_hygiene(p.read_text('utf-8', errors='replace'))[0]}"
              for p in scripts if py_syntax_hygiene(p.read_text("utf-8", errors="replace"))]
    dsviol = [f"{p.name} → {docstring_swallow(p.read_text('utf-8', errors='replace'))[0]}"
              for p in scripts if docstring_swallow(p.read_text("utf-8", errors="replace"))]
    check("G9 判据脚本全部 import-safe（禁 import 即执行）、解析得动且无模块级裸字符串",
          not iviol and not syviol and not dsviol,
          f"{len(scripts)} 个脚本已扫"
          + ("；违规：" + " ; ".join((iviol + syviol + dsviol)[:6])
             if (iviol or syviol or dsviol) else "，零违规"))



def _cfg_report(results):
    """r94：main() 的收尾统计与退出码（原样搬）。"""
    fails = [r for r in results if not r[1]]
    print(f"\n合计 {len(results)} 项，失败 {len(fails)} 项")
    for nm, _, d in fails:
        print("  🔴", nm, d)
    # 判据清单必须出现在结论行里：电池只保留每条套件"最后一条含判据词的行"，
    # 逐条 PASS 行在 CI 里全被折掉 ⇒ 只写 REPO-CONFIG-PASS 等于把"到底跑了哪几条"藏起来
    #（与 r40b 给 perf_baseline 补实测值是同一族，修法同类而不是各修各的）。
    ran = sorted({g for n, _o, _d in results for g in re.findall(r"G\d+", n)},
                 key=lambda s: int(s[1:]))
    # 计数单位写清楚：一条 check() 的名字里可以同时点两个判据号（G9 就是两腿），
    # 所以 17 次调用与 18 个号**同时为真**。只印一个数，下一轮会把另一个读成对账不上（r90 一手）。
    print("REPO-CONFIG-PASS（实跑 %d 项检查，覆盖 %d 个判据号：%s）" % (len(results), len(ran), " ".join(ran))
          if not fails else
          "REPO-CONFIG-FAIL（实跑 %d 项，红 %d 项，覆盖 %d 个判据号：%s）"
          % (len(results), len(fails), len(ran), " ".join(x[0].split()[0] for x in fails)))
    return 1 if fails else 0


def main():
    """r94：只留调度——三段分别下移到 `_cfg_head` / `_cfg_body` / `_cfg_report`。

    调用序与原来逐语句一致 ⇒ 判据号、计数与退出码都不变（`REPO-CONFIG-PASS` 的
    「实跑 N 项」是验真点）。切点由 AST 定位，不靠行号。
    """
    a = _cfg_head()
    if a.selftest:
        sys.exit(selftest())
    _cfg_body(a)
    return _cfg_report(results)



if __name__ == "__main__":
    sys.exit(main())
