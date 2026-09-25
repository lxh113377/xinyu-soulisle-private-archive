# -*- coding: utf-8 -*-
"""仓库配置自洽守卫（r22）：让"配了但没生效/文档与配置对不上"变得可机器发现

动机（两处真实经历）：
  - r21 加了 `.github/dependabot.yml`，但**配置存在 ≠ 被受理**：dependabot 只读默认分支上该文件，
    且 ecosystem 名 / directory 拼错时 GitHub 只会静默不跑（本地无任何报错）。
  - 本项目文档里散落着"四条门禁 / 26 套件"这类**数字断言**，改配置或加套件时极易与实值脱节
    （AGENTS.md 的 04/05 段就已长期陈旧，是同一类问题的既成实证）。

判据（逐项独立，G1–G4、G6–G7 离线恒跑；G5 需 --online）：
  G1 dependabot schema：version==2、ecosystem 在支持清单内、`directory` 指向**仓库里真实存在**的目录、
     schedule.interval 合法、PR 上限为整数
  G2 CI 拓扑：`.github/workflows/ci.yml` 可解析，且 job 数 == README 声称的"N 条门禁"（数字对不上即红）
  G3 契约可发现：`docs/openapi.yaml` 存在、可解析，且被 `docs/README.md` 引用（孤文件即红）
  G4 判据清单自洽：`run_all_suites.py` 的 SUITES 条目数 == README 声称的"（N 套件）"
  G5（--online）远端受理面：默认分支上 `.github/dependabot.yml` 确实存在（GitHub 只看默认分支）
  G6 第三方授权：`src/vendor/*.js` 每一个文件都必须在 `docs/THIRD-PARTY-NOTICES.md` 里被点名
  G7 README 必须含指向该授权清单的口径行（否则读者只会看到"MIT"，而 GSAP 其实不是 MIT）
  G8 --selftest：合成篡改类**逐轮累积**（条数以 --selftest 实际输出为准，正文不抄数字——
     抄过两次都脱节）：ecosystem 拼错 / 目录不存在 / interval 非法 / updates 清空 / 抹 gsap 登记 /
     抹 README 引用 / 抹评测集行 / 评测条数改小 / 删整节 / 表退回模板原句 / 无 __main__ 守卫 /
     CI 只跑单条判据 / CI 不声明豁免 / 幽灵豁免
     必须各自报红，原样必须零问题 —— 证判据非恒真
  G9 判据脚本 import-safe：`_test/*.py` 的顶层入口调用（sys.exit(main()) 等）必须落在
     `if __name__ == "__main__":` 守卫之后 —— 判据脚本会被互相 import（--only 自查 / 聚合 runner 对账 /
     CI 复用），无守卫 = "一 import 就跑全套或跑网络，且退出码 0"（r26 实测第五次同族坑）
  G10 判据必须挂在**真会走的路径**上：CI 步骤里要整跑电池（run_all_suites.py）且声明 --exclude-llm 豁免，
     豁免项必须是真实存在的套件（幽灵豁免=恒真风险）。根因两条：① 本项目 CI 长期只跑 browser_check 一条，
     r26-r28 新加的 patch_apply / settings_panel / offline_shell 全在发布路径之外（本地绿≠有人管）；
     ② 同行实证 CodeQL 30 次全 success 但 refs/heads/main 分析数为 0——有运行记录不等于覆盖主路径。

退出码：0=REPO-CONFIG-PASS 1=任一判据失败 2=环境异常（缺 PyYAML / --online 但 gh 不可用）
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
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


def license_scope(notices_txt, readme_txt, vendor_files):
    """G6/G7 纯函数：第三方授权边界必须被正式声明且不漏登记。"""
    bad = []
    if "GreenSock" not in notices_txt:
        bad.append("授权清单未点明 GSAP 的实际条款（把整仓说成 MIT 是不准确的声明）")
    missing = [f for f in vendor_files if f not in notices_txt]
    if missing:
        bad.append(f"vendor 文件未在授权清单登记 {missing}")
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


def import_safety(text):
    """G9 纯函数：判据脚本必须 import-safe —— 顶层入口调用须落在 __main__ 守卫之后。

    r26 加，起因是本轮自己踩的第五次同族坑：给 `benchmark_metrics.py` 的分档判据做负控制时
    `import` 它 = 直接跑一遍 16 仓联网采集然后 `exit 0`，**反例压根没执行却看起来像通过**。
    判据脚本会被互相 import（`--only` 自查、CI 复用、聚合 runner 对账），无守卫就等于
    "一 import 就跑全套/跑网络"，而退出码还是 0。
    """
    lines = text.splitlines()
    guard = next((i for i, l in enumerate(lines) if l.startswith("if __name__")), None)
    bad = []
    for i, l in enumerate(lines):
        if ENTRY_RE.match(l) and (guard is None or i < guard):
            bad.append(f"第 {i + 1} 行顶层入口调用且无 __main__ 守卫（import 即执行）：{l[:44]}")
    return bad


REQ_ALIAS = {"pyyaml": "yaml", "pillow": "PIL"}   # 发行名 → import 名（清单写 PyYAML/Pillow，代码 import yaml/PIL）


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


def selftest():
    bad = []
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
    nt = (ROOT / NOTICES).read_text("utf-8") if (ROOT / NOTICES).exists() else ""
    rt = (ROOT / "README.md").read_text("utf-8")
    vf = sorted(x.name for x in (ROOT / "src" / "vendor").glob("*.js"))
    if license_scope(nt, rt, vf):
        bad.append(f"原样授权声明被判失败：{license_scope(nt, rt, vf)}")
    if not license_scope(nt.replace("gsap.min.js", "zzz"), rt, vf):
        bad.append("篡改⑤（授权清单里抹掉 gsap.min.js）未被抓到 ⇒ G6 恒真")
    if not license_scope(nt, rt.replace("THIRD-PARTY-NOTICES", "zzz"), vf):
        bad.append("篡改⑥（README 去掉指向授权清单的口径行）未被抓到 ⇒ G7 恒真")
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


def main():
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
    n = battery_count()
    check("G4 电池条目数 == README 声称的套件数", s_claim is not None and s_claim == n,
          f"run_all_suites.py 实测 {n} | README 声称 {s_claim}")
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
    vfiles = sorted(x.name for x in (ROOT / "src" / "vendor").glob("*.js"))
    lbad = license_scope(ntxt, (ROOT / "README.md").read_text("utf-8"), vfiles)
    check("G6+G7 第三方授权边界已声明且逐文件登记（GSAP 非 MIT 不可含糊）", not lbad, " ; ".join(lbad))

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
    check("G9 判据脚本全部 import-safe（禁 import 即执行）", not iviol,
          f"{len(scripts)} 个脚本已扫" + ("；违规：" + " ; ".join(iviol) if iviol else "，零违规"))

    fails = [r for r in results if not r[1]]
    print(f"\n合计 {len(results)} 项，失败 {len(fails)} 项")
    for nm, _, d in fails:
        print("  🔴", nm, d)
    print("REPO-CONFIG-PASS" if not fails else "REPO-CONFIG-FAIL")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
