# -*- coding: utf-8 -*-
"""bench_quality_gates.py — 「质量门」同址尺（r95 自 benchmark_metrics.py 整块迁出）。

问的是"这道检查能不能让构建失败"，不是"有没有这个配置文件"。迁出理由与验收见
`交付物/对标分析报告-2026-10-04-r95.md`；搬块脚本的三条硬规矩见同轮 %TEMP% 的
_r95_split_quality_gates.py docstring。
对外只依赖三个取数函数（gh / git_blob / git_ls_tree），它们留在 benchmark_metrics ——
那里同时是 12 个 peer probe 的 PEERS 单一真相源，搬它们会牵动全部探针；故本件用
**函数内延迟导入**破环：调用发生在 benchmark_metrics 完成初始化之后。
"""
import base64
import re


def _fetch():
    """延迟取 benchmark_metrics 的三个取数函数（模块级 import 会形成循环）。

    r95 控制性 seam：本模块 globals() 里若已装有同名可调用（selftest 的接线腿会装桩），
    优先用桩。桩**必须装在被审对象所在的模块**——装在 benchmark_metrics 对被迁函数无效
    （迁块当场让 ③-d 与 r75 接线两条腿各判红一次，实证见 r95 报告 §2.4）。
    """
    g = globals()
    if all(callable(g.get(k)) for k in ("gh", "git_blob", "git_ls_tree")):
        return g["gh"], g["git_blob"], g["git_ls_tree"]
    from benchmark_metrics import gh, git_blob, git_ls_tree
    return gh, git_blob, git_ls_tree

# ── r75：**质量门**的同址尺——问的是"这道检查能不能让构建失败"，不是"有没有这个配置文件"。
#     起因（本轮只读枚举，非凭印象）：`_test/peer_quality_tooling_probe.py`（r58）自己写明了天花板
#     ——「覆盖率与缺陷率都不在本轮取数面内」，它量的是**配置在不在、测试文件在不在、CI 有没有执行位**；
#     而 self 侧实测 `grep -n "jacoco\|coverage" server/pom.xml` = 0 命中（surefire 在，跑用例但**无门槛**）。
#     同一件"质量工程"的两个半边：一只尺量"有没有装"，另一只量"装了之后会不会拦人"——后者从没量过，
#     正是「把现成的尺换到没人量的那一半」。判据形状按类分两种，**不许混用**：
#       · coverage / mutation 这类是**阈值型**：配置文件在 ≠ 有门，必须见到"低于阈值即失败"的形状
#         （`fail_under` / `--cov-fail-under` / `check-coverage` / `thresholds.break` / jacoco 的 `<rule><limit><minimum>`）；
#       · lint / typecheck / secret-scan 这类是**执行型**：退出码天然非零，门槛＝"配置 ∧ CI 真跑它"。
#     与 r73/r74 通道同源：不参与 caps、不设兜底、取不到内容一律 `unverified`（不得写成"该仓没有门"）。
QG_CLASSES = ("coverage_gate", "mutation_gate", "lint_gate", "typecheck_gate", "secret_scan_gate")
QG_CANDIDATES = {
    "coverage_gate": re.compile(r"(^|/)(jacoco[\w.-]*\.xml|\.coveragerc|coverage\.cfg|setup\.cfg"
                                r"|codecov\.ya?ml|\.nycrc[\w.-]*|pyproject\.toml|vitest\.config\.[\w]+|jest\.config\.[\w]+"
                                r"|pom\.xml$|build\.gradle(\.kts)?$)"
                                r"|(^|/)(tests?|benchmarks?)/?cov[\w.-]*\.yml$", re.I),
    "mutation_gate": re.compile(r"(^|/)(stryker[\w.-]*\.(js|ts|cjs|mjs|json)|mutmut\.cfg|setup\.cfg"
                                r"|infection[\w.-]*\.(json|dist)|pitest[\w.-]*|pom\.xml)$", re.I),
    "lint_gate": re.compile(r"(^|/)(\.eslintrc[\w.-]*|eslint\.config\.[\w]+|\.pylintrc|ruff\.toml"
                            r"|\.flake8|biome\.json(?:c)?|\.standard-json|golangci\.yml)$", re.I),
    "typecheck_gate": re.compile(r"(^|/)(tsconfig[\w.-]*\.json|mypy\.ini|pyrightconfig\.json"
                                 r"|\.pylintrc|typed\.py)$", re.I),
    "secret_scan_gate": re.compile(r"(^|/)(\.gitleaks\.toml|\.secrets\.baseline|\.pre-commit-config\.yaml"
                                   r"|\.secretlintrc[\w.-]*|\.trufflehog|detect_secrets[\w.-]*)$", re.I),
}
# 阈值型类的"会让构建失败"形状（正文面；只在这些候选文件里找，避免全仓正文爆炸）
QG_THRESHOLD_SHAPE = {
    "coverage_gate": re.compile(r"(fail_under|cov-fail-under|check-coverage|thresholds?[^\n]{0,40}?\b(lines|functions|statements)"
                                r"|<rule>|<limit>|minimum|coverage[^\n]{0,24}?(8|9)\d(\.\d+)?%)", re.I),
    "mutation_gate": re.compile(r"(mutationScoreThreshold|mutationThreshold|<mutationScale|failure_under"
                                r"|min-msi|mutator[\s\S]{0,30}?(coverage|mutation)|thresholds[\s\S]{0,24}break"
                                r"|\b(pitest|stryker|mutmut|infection)\b[\s\S]{0,60}?(threshold|limit|break|msi))",
                               re.I),
}
QG_CI_EXEC_SHAPE = re.compile(r"(eslint|biome|flake8|ruff|pylint|mypy|pyright|tsc\s+--noEmit|gitleaks"
                              r"|trufflehog|detect-secrets|secretlint|jacoco|codecov|nyc|vitest\s+--coverage"
                              r"|pytest[^\n]{0,40}--cov)", re.I)
# 执行型类的 CI 形状**按工具词**匹配（本轮 selftest 的正例抓到一处自欺：早期版本拿"文件名正则"去搜 CI 正文，
# 于是 `npm run lint: eslint . --max-warnings 0` 这种真在拦人的步被判成"CI 没跑" ⇒ 假阴性）。
QG_EXEC_TOKENS = {
    "lint_gate": re.compile(r"(eslint|biome|flake8|ruff|pylint|standard\b|rubocop|clippy|golint|revive"
                            r"|风格|规范检查|代码检查|代码风格)", re.I),
    "typecheck_gate": re.compile(r"(mypy|pyright|tsc\s+--noEmit|tsc\s+-p|flow\s+check|typescript\s+--noEmit"
                                 r"|类型检查|静态类型)", re.I),
    "secret_scan_gate": re.compile(r"(gitleaks|trufflehog|detect[-_]?secrets|secretlint|git-secrets|snyk\s+code"
                                   r"|checkov|semgrep|密钥[^\n]{0,12}(扫描|检查|零入库)|零密钥)", re.I),
}
# CI 面的取样上限：**取不全时不得判"没有"**（blindness is not zero）。wf_fetched < wf_total 且没找到执行位
# ⇒ 该类记 None（unverified），而不是 False。r75 首跑就是因为只取 3 个 workflow 而 lobehub 有 31 个，
# 把整面读成"peers 一律无门"——那是我的取数面塌缩，不是对手的事实。
QG_CI_FETCH_CAP = 12
# r95 finding③：门禁正文的**取样顺序**。旧实现是 `ci_all[:12]`，而 GitHub tree 是字母序 ⇒
# lobehub 33 个流里 `test.yml`（第 32）与 `lighthouse.yml`（第 14）**结构上永远取不到正文**，
# 于是 `vitest --coverage` + Codecov 那一步从没被这把尺读过，而展示面把"没测到"与"测过没有"
# 折叠成同一个 `0/16`。本表把「最可能含门禁执行位」的文件名特征排到前面——**只改取样顺序，
# 不改判定**：取不到仍记 unverified。
# ⚠️ 特征表沿用 r74 的前缀纪律但方向相反：**不列裸 `bench`**（`workbench` 会命中），`release` 也不列
#    （它是发布通道不是门禁，列进来会把 test.yml 挤出面——本轮实测过一次）。裸 `ci` 同样不列，
#    `ci.yml` 由下面的整名档（QG_CI_EXACT）负责。
QG_CI_PRIORITY = re.compile(r"(test|coverage|quality|lint|check|secret|scan|typecheck|e2e"
                            r"|lighthouse|lhci|web[-_]?vitals|bundle|size|budget"
                            r"|benchmark|k6|artillery|locust|audit|security|unit|integration)", re.I)
# 第二档：**整名就是一个门禁通用名**（`test.yml` / `e2e.yml` / `ci.yml` / `quality.yml`…）。
# 只按子串命中排序时，`claude-auto-e2e-testing.yml` 这类"双命中"会把裸 `test.yml` 挤到 tie-break
# 之后（lobehub 实测：新面 12 个里仍无 test.yml）。整名命中是更强的信号，单列一档。
QG_CI_EXACT = re.compile(r"^(tests?|ci|quality|lint|typecheck|coverage|e2e|checks?|gate|audit|"
                         r"secret[-_]?scan|unit|integration|smoke)$", re.I)


def qg_ci_score(name):
    """纯函数：workflow 文件名的门禁相关性分档（2=整名即门禁名 / 1=名字含门禁特征 / 0=无关）。"""
    stem = re.sub(r"\.ya?ml$", "", (name or "").rsplit("/", 1)[-1], flags=re.I)
    if QG_CI_EXACT.match(stem):
        return 2
    return 1 if QG_CI_PRIORITY.search(stem) else 0


def qg_ci_pick(paths, cap=QG_CI_FETCH_CAP):
    """纯函数：workflow 清单 → 本轮真去取正文的那 cap 个。

    排序键：① 相关性分档（高者在前）② 路径小写（保证确定性，不随 tree 返回顺序漂移）。
    人口 ≤ cap 时原样全取（不截断、不重排成"看起来像筛过"）。
    """
    wf = list(paths or [])
    cap = int(cap)
    if cap <= 0 or len(wf) <= cap:
        return wf
    return sorted(wf, key=lambda p: (-qg_ci_score(p), p.lower()))[:cap]


def qg_gate_line(cls, members_n, population_n, unv_n, self_mark):
    """门面行三值化（r95 finding③）：`有门=已验口径（未验N，人口M）`。

    **分母不含未验**：旧形态 `0/16` 让读者得到「16 个对手都没有」，实际是「14 个测过没有、
    2 个没测到」——把不可得折成 0，与折成 1 同样是谎（本仓铁律 Unavailable is not zero）。
    """
    return "%-17s peers 有门=%d/%d（未验%d，人口%d） self=%s" % (
        cls, members_n, max(population_n - unv_n, 0), unv_n, population_n, self_mark)


def qg_ci_face(paths):
    """从清单里挑出 workflow 文件（返回全部路径与条数，由调用方决定取多少并如实报覆盖率）。"""
    wf = [p for p in (paths or []) if p.startswith(".github/workflows/") and p.endswith((".yml", ".yaml"))]
    return wf


# r78 第二条路由：**自写门禁**。旧 `qg_classify` 对执行型三类的第一句是 `if not files: out=False`，
# 而 `files` 只来自"标准工具文件名"清单（.gitleaks.toml / eslint.config.* / mypy.ini…）⇒
# 本仓的密钥门 `_test/tracked_secret_scan.py` 明明被 CI 每一步跑着（ci.yml 现读第 56 行确有该步骤），
# 却被这把尺读成「self=❌无」，r77 总览表因此带了一条**假缺口**；同法对 peers 也失效，
# 那一格的分子分母从来就不是对手的事实。
# 与 r75「有配置≠有门」互为对偶：那条防"假阳"，这条防"假阴"。
QG_RUN_CMD = re.compile(r"^(?:-\s*)?(?:run:\s*)?(?:[\w./-]*/)?(?:npx|npm\s+run|yarn|pnpm|uvx?|pipx|"
                        r"python3?|bash|sh|go|cargo|make|gradle|mvn|deno|bun)\b")
QG_INVOKED_TOKENS = {
    "lint_gate": re.compile(r"\b(eslint|biome|flake8|ruff|pylint|rubocop|clippy|golint|revive)\b"
                            r"|[\w./-]*(?:lint|eslint)[\w.-]*\.(?:py|sh|js|ts)", re.I),
    "typecheck_gate": re.compile(r"\b(mypy|pyright|pytype)\b|\btsc\s+(?:-p|--noEmit)\b"
                                 r"|[\w./-]*(?:typecheck|tsc|mypy|pyright)[\w.-]*\.(?:py|sh|js|ts)", re.I),
    "secret_scan_gate": re.compile(r"\b(gitleaks|trufflehog|secretlint|git-secrets|detect[-_]secrets)\b"
                                   r"|[\w./-]*(?:secret|gitleaks|trufflehog)[\w.-]*\.(?:py|sh|js|ts)", re.I),
}


def qg_invoked_line(cls, ci_text):
    """纯函数：找 CI 里"执行行真调用了一个带该类工具词的可执行体"的第一行。

    只认执行行（`run:` 之后或以解释器/构建工具开头的行）——**注释与步骤名不算**，
    否则 `起 fat jar（无密钥，仅情绪接口）` 这种描述性文字会把"没门"读成"有门"。
    """
    rx = QG_INVOKED_TOKENS.get(cls)
    if not rx:
        return ""
    for line in (ci_text or "").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.startswith("- name:") or s.startswith("name:"):
            continue
        if not QG_RUN_CMD.search(s):
            continue
        if rx.search(s):
            return s[:120]
    return ""


def qg_exec_verdict(cls, files, ci_text, ci_complete):
    """执行型类的三态判定：True=找到执行位 / False=CI 面读全了且确实没有 / None=面没读全，不得下结论。

    两条路由任一命中即 True：① 标准配置文件 ∧ CI 执行位（r75 原口径）；
    ② 无标准配置但 CI 执行行真调用了带该类工具词的可执行体（r78 新增，覆盖自写门禁）。
    """
    if files:
        m = QG_EXEC_TOKENS[cls].search(ci_text or "")
        if m:
            return True, "%s ∧ CI 执行位=%s" % (files[0], m.group(0)[:40])
    inv = qg_invoked_line(cls, ci_text)
    if inv:
        return True, "自写门禁 ∧ CI 真调用：%s" % inv
    if not ci_complete:
        return None, "%s CI 面未取全 ⇒ 不得判「无门」" % ("%s 在，但" % files[0] if files else "")
    return False, ("%s 在而 CI 面取全后未见执行位" % files[0]) if files \
        else "无标准配置、且 CI 执行行里没有该类可执行体（步骤名/注释不计）"


def qg_tree_candidates(paths):
    """结构面：每个类挑出候选文件（只证"有这个东西"，不证它有牙）。"""
    cand = {}
    for cls, rx in QG_CANDIDATES.items():
        cand[cls] = [p for p in (paths or []) if len(p) < 300 and rx.search(p)]
    return cand


def qg_classify(cand, blobs, ci_text, ci_complete=True):
    """纯函数：候选文件 + 这些文件的正文 + workflow 文本 → 五类的"能不能拦人"。

    阈值型类必须有**失败形状**才算 gate；执行型类必须有**配置 ∧ CI 执行位**。
    候选存在但正文没取到 ⇒ 该类记 `unverified`（不得塌缩成 False）；
    CI 面没取全（`ci_complete=False`）而没找到执行位 ⇒ 同样记 None，**不得判"没有门"**。
    """
    out, ev, unv = {}, {}, []
    for cls in QG_CLASSES:
        files = cand.get(cls) or []
        if cls in QG_THRESHOLD_SHAPE:
            if not files:
                out[cls] = False
                continue
            read = [f for f in files if f in blobs]
            if not read:
                unv.append("%s(候选 %s 正文未取到)" % (cls, files[0]))
                out[cls] = None
                continue
            hit = next(((f, QG_THRESHOLD_SHAPE[cls].search(blobs[f])) for f in read
                        if QG_THRESHOLD_SHAPE[cls].search(blobs[f] or "")), None)
            out[cls] = bool(hit)
            if hit:
                ev[cls] = "%s :: %s" % (hit[0], hit[1].group(0)[:60])
        else:
            # r78：执行型三类**不得**因为"没有标准配置文件"就直接判无——自写门禁只看 CI 执行行
            v, why = qg_exec_verdict(cls, files, ci_text, ci_complete)
            out[cls] = v
            ev[cls] = why
            if v is None:
                unv.append("%s(CI 面未取全)" % cls)
    return out, ev, unv


def self_quality_gates(rev="HEAD"):
    """self 侧走同一函数：清单=ls-tree，正文=pom/配置 blob，CI 文本=`.github/workflows/*.yml` blob。"""
    _, git_blob, git_ls_tree = _fetch()
    paths = git_ls_tree(rev)
    cand = qg_tree_candidates(paths)
    want = sorted({f for files in cand.values() for f in files})[:8]
    blobs = {}
    errs = []
    for f in want:
        try:
            blobs[f] = git_blob(f, rev)
        except Exception as e:
            errs.append("%s:%s" % (f, str(e)[:40]))
    ci_all = qg_ci_face(paths)
    ci_take = qg_ci_pick(ci_all)
    ci_text, errs2 = "", []
    for f in ci_take:
        try:
            ci_text += git_blob(f, rev) + "\n"
        except Exception as e:
            errs2.append("ci:%s" % str(e)[:40])
    cls, ev, unv = qg_classify(cand, blobs, ci_text, ci_complete=(len(ci_all) <= len(ci_take)))
    # 天花板自证：本尺认两形——① 标准工具配置（.gitleaks.toml / eslint.config.* / jacoco `<limit>`…）
    #   ∧ CI 执行位；② r78 补：**无标准配置但 CI 执行行真调用了一个带该类工具词的可执行体**（自写门禁）。
    #   两侧同一函数 ⇒ 同法；注释与步骤名不计（防"提到关键词就算有门"）。
    # `ci_steps_homegrown` 继续带出全部自写步骤名，供人核"名册 vs 判定"是否同源，只作说明不参与对照。
    step_names = re.findall(r"(?m)^\s*-\s+name:\s*(.+)$", ci_text)
    return {"classes": cls, "evidence": ev, "unverified": unv + errs, "ci_face": "%d/%d" % (len(ci_take), len(ci_all)),
            "candidates": {k: v[:3] for k, v in cand.items()}, "face": rev,
            "ci_step_count": len(step_names),
            "ci_steps_homegrown": [s.strip()[:34] for s in step_names
                                   if re.search(r"守卫|门禁|红线|校验|扫描|自检|对账|预算|一致性", s)],
            "partial_errors": "; ".join(errs + errs2)}


def quality_gate_audit(repos, max_fetch=4):
    """peers 侧：tree 挑候选 → 只取候选文件正文（≤max_fetch/仓）→ 同一 qg_classify。"""
    gh, _, __ = _fetch()
    out = {}
    for r in repos:
        full = r["repo"]
        branch = r.get("default_branch") or "HEAD"
        errs, paths, ci_text = [], [], ""
        try:
            tr = gh("repos/%s/git/trees/%s?recursive=1" % (full, branch), timeout=90)
            paths = [e["path"] for e in tr.get("tree", []) if e.get("type") == "blob"]
            if tr.get("truncated"):
                errs.append("tree_truncated")
        except Exception as e:
            errs.append("tree:" + str(e)[:60])
            out[full] = {"classes": {}, "evidence": {}, "unverified": ["tree 取不到：" + str(e)[:60]]}
            continue
        cand = qg_tree_candidates(paths)
        blobs = {}
        for cls, files in cand.items():
            for f in files[:max_fetch]:
                if f in blobs:
                    continue
                try:
                    d = gh("repos/%s/contents/%s?ref=%s" % (full, f, branch), timeout=40)
                    blobs[f] = base64.b64decode((d.get("content") or "").strip()).decode("utf-8", errors="replace")
                except Exception as e:
                    errs.append("%s:%s" % (f, str(e)[:40]))
        ci_all = qg_ci_face(paths)
        ci_take = qg_ci_pick(ci_all)
        for p in ci_take:
            if p in blobs:
                continue
            try:
                d = gh("repos/%s/contents/%s?ref=%s" % (full, p, branch), timeout=40)
                blobs[p] = base64.b64decode((d.get("content") or "").strip()).decode("utf-8", errors="replace")
            except Exception as e:
                errs.append("ci:%s" % str(e)[:40])
        ci_text = "\n".join(blobs[p] for p in ci_take if p in blobs)
        cls, ev, unv = qg_classify(cand, blobs, ci_text, ci_complete=(len(ci_all) <= len(ci_take)))
        out[full] = {"classes": cls, "evidence": ev, "unverified": unv,
                     "ci_face": "%d/%d" % (len(ci_take), len(ci_all)),
                     "candidates": {k: v[:3] for k, v in cand.items()},
                     "partial": bool(errs), "partial_errors": "; ".join(errs)[:160]}
    return out
