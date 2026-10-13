# -*- coding: utf-8 -*-
"""接口契约守卫（r21）：文档 == 代码 == 运行态，三方对账，逐项独立判定

为什么做（**不是** peer 压力）：实测 16 个参照仓里只有 1 家有机器可读 API 规范
（`benchmark_metrics.py` → `api_spec=1/16`），所以这条不是"被同类甩开"的差距，
而是本项目自己的**契约分散**问题：`/api/chat` 的契约写在 `j2_chat_contract.py` 与
`chat-agent.js` 常量与部署文档三处，改一端忘两端的风险一直靠人记。
本脚本把 `docs/openapi.yaml` 变成**唯一声明源**并三方对账。

判据：
  C1 不缺文档：Java 控制器每个 `@*Mapping` 路由必须在 spec 里
  C2 不虚文档：spec 每条 path+method 必须在 Java 控制器里真实存在（幽灵文档即红）
  C3 不偷调用：`src/js/*.js` 与 Pages Function 里出现的 `/api/...` 必须已文档化
  C4 运行态一致：带 `x-live-check` 的端点发真实请求，状态码 ∈ 声明集 且 required_keys 齐
                （探测统一用 sessionId=`contract-probe`，结尾 DELETE 清理，不污染演示数据）
  C5 --selftest：合成样本证明 C1/C2/C3/C4 四条**都会报红**（不是恒真判据）
  C7 人读手册对账（r89）：docs/API.md 与 spec 双向 —— yaml 每条 path 必须在手册里出现（不缺）、
                手册里每个 `/api/...` 令牌必须已在 yaml 声明（不虚）、手册声明的「N 路径」须等于
                len(paths)（计数不失）。补这一腿的动因：C1-C6 只钉住 yaml↔控制器↔前端↔运行态，
                而 r87 新写的人读手册**没有任何读者**，yaml 一改它就静默过期（同族：门面自证没人量）。

前置：fat jar 起在 8123（C4 用；C1–C3、C5、C7 完全离线）
退出码：0=API-CONTRACT-PASS 1=任一判据失败 2=环境异常（jar 不可达 / 缺 PyYAML / 缺 yaml 文件）
"""
import json
import os
import re
import time
import socket
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "docs" / "openapi.yaml"
BASE = "http://127.0.0.1:8123"
results = []
# 限流自愈等待：ApiGuardFilter 桶容量 burst=20、补充 60/分钟（≈1 token/s）⇒ 22s 回满。
# 写死并写明推导，不写"随便睡一会儿"——睡多久必须能说清来源。
SETTLE_SECONDS = 22
NOKEY = []   # 记录哪些探测走了「契约内 500」分支；收尾必须打印，不允许静默放宽
RATE_LIMITED = []   # 记录哪些探测撞限流后重试过；同样必须打印，不许把环境状态读成契约结论


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  -> {detail}" if detail else ""))


def java_routes():
    """从控制器源码抽 (METHOD, path)。P0.1：不凭记忆列接口，一律实读。"""
    out = set()
    for p in (ROOT / "server" / "src" / "main" / "java").rglob("*.java"):
        txt = p.read_text("utf-8", errors="replace")
        for m in re.finditer(r'@(Get|Post|Put|Delete|Patch)Mapping\(\s*(?:value\s*=\s*)?"([^"]+)"', txt):
            out.add((m.group(1).upper(), "/api" + m.group(2) if not m.group(2).startswith("/api") else m.group(2)))
        for m in re.finditer(r'@RequestMapping\(\s*"?([^"\s,)]+)"?', txt):
            v = m.group(1)
            if v.startswith("/api"):
                out.add(("ANY", v))
    return out


def spec_ops(spec):
    out = set()
    for path, item in (spec.get("paths") or {}).items():
        for verb in ("get", "post", "put", "delete", "patch"):
            if verb in item:
                out.add((verb.upper(), path))
    return out


def norm(path):
    """`{x}` 与 Spring 的 `{x}` 同形；只统一斜杠与末尾差异。"""
    return re.sub(r"\{[^}]+\}", "{}", path)


# 探测顺序名单（**只决定先后，不决定成员资格**，见 probe_order 的 r179 记因）。
# 先写后查再删是语义约束：export/import 会落数据，必须排在清理腿之前（r130 一手）。
PROBE_ORDER = [("/api/health", "get"), ("/api/emotion/lexicon", "get"), ("/api/emotion/eval", "get"),
               ("/api/emotion", "post"), ("/api/chat", "post"),
               ("/api/memory/emotion", "post"), ("/api/memory/message", "post"),
               ("/api/memory/stats", "get"), ("/api/memory/emotions", "get"),
               ("/api/memory/messages", "get"), ("/api/memory/search", "get"),
               ("/api/memory/export", "get"), ("/api/memory/import", "post"), ("/api/usage", "get"),
               ("/api/memory/{sessionId}", "delete")]
# 清理腿永远压到最后：它 DELETE 的是上面各腿写进 `contract-probe` 会话的数据。
CLEANUP_LAST = ("/api/memory/{sessionId}", "delete")


def frontend_calls():
    out = set()
    for p in list((ROOT / "src" / "js").glob("*.js")) + list((ROOT / "src" / "functions").rglob("*.js")):
        txt = p.read_text("utf-8", errors="replace")
        for m in re.finditer(r'["\'](/api/[A-Za-z0-9_/{}.-]+)', txt):
            v = m.group(1).rstrip("/") or "/api"
            out.add(v)
    return out


def compare_static(spec, jv=None, called=None):
    """C1–C3 的纯函数实现。jv/called 可注入，供 C5 自证喂合成样本（不注入则实读磁盘）。"""
    bad, jv, sp = [], (jv if jv is not None else java_routes()), spec_ops(spec)
    jn = {(m, norm(p)) for m, p in jv} | {("ANY", norm(p)) for _, p in jv}
    sn = {(m, norm(p)) for m, p in sp}
    missing = {(m, p) for m, p in jv if (m, norm(p)) not in sn and ("ANY", norm(p)) not in sn}
    ghost = {(m, p) for m, p in sp if (m, norm(p)) not in jn and ("ANY", norm(p)) not in jn}
    if missing:
        bad.append("C1 控制器有路由未文档化 " + str(sorted(missing)))
    if ghost:
        bad.append("C2 spec 声明了控制器不存在的路径 " + str(sorted(ghost)))
    called = frontend_calls() if called is None else called
    spec_paths = {norm(p) for p in (spec.get("paths") or {})}
    # 前端用 `/api/memory` + 子路径拼接（memory-store.js 的 api(path) 形态），故按前缀匹配
    undocumented = {c for c in called
                    if not any(norm(c) == s or c.rstrip("/") in s or s.startswith(c.rstrip("/") + "/")
                               or s == norm(c) or c.startswith(s.rstrip("{}")) for s in spec_paths)}
    if undocumented:
        bad.append("C3 前端调用了未文档化的端点 " + str(sorted(undocumented)))
    return bad


def http(method, url, body=None, query=None):
    if query:
        url += "?" + "&".join(f"{k}={v}" for k, v in query.items())
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method.upper())
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except (TimeoutError, socket.timeout, urllib.error.URLError, OSError) as e:
        # r130：超时/连接失败必须落成**读数**而不是抛栈。抛栈的代价是整条 C4 链连它前面
        # 已经 PASS 的十几条一起消失（本轮实测：探测挂住 60s ⇒ 脚本崩在栈里，rc=1 却看不出
        # 是哪条挂的）。同族于 r105 的 BLIND-RED：「超时须落未验/点名红，而非抛栈」。
        return None, f"{type(e).__name__}: {e}"


def annotated_ops(spec):
    """返回 {归一化路径|动词: 'live' | ('skip', 理由)}。缺标注的既不算 live 也不算 skip。"""
    out = {}
    for pa, it in (spec.get("paths") or {}).items():
        for v in ("get", "post", "put", "delete", "patch"):
            op = (it or {}).get(v)
            if not isinstance(op, dict):
                continue
            if op.get("x-live-check"):
                out[(norm(pa), v.upper())] = "live"
            elif op.get("x-live-skip"):
                out[(norm(pa), v.upper())] = ("skip", str(op.get("x-live-skip")))
    return out


def probe_order(live_keys):
    """手抄名册只决定**先后**，成员资格由 spec 决定。纯函数（可在 selftest 里合成投喂）。

    立此条的一手代价（r179）：`/api/health/db` 补进契约并标了 `x-live-check`，C4 却一条都没打它，
    C6 当场报「探测 15 + 豁免 0 == 操作 16」。根因不是文档写漏，而是这里的 `order` 是一份
    **手抄名单** —— 「接口面」这件事在仓里被写了两遍（spec 的标注 + 名单），加一条接口必须同步两处，
    而漏改只在运行态才暴露（AGENTS.md 决策 #5 / AC-OBS-09 的旧值漂移是同一族）。
    顺序本身是语义，不能改成按 spec 书写顺序：先写后查再删，清理腿必须压到最后
    （r130 把 export/import 插在 delete 之前就是为这个）。所以：名单里有它的按名单位次排，
    名单没有而 spec 标注了的排在全部已知项之后、清理腿之前 —— 新接口默认被真打，不再静默隐身。
    """
    prio = {(norm(p), v.upper()): i for i, (p, v) in enumerate(PROBE_ORDER)}
    cleanup = (norm(CLEANUP_LAST[0]), CLEANUP_LAST[1].upper())

    def rank(k):
        return (1 if k == cleanup else 0, prio.get(k, len(PROBE_ORDER)), k)

    return sorted(live_keys, key=rank)


def live_probes(spec, ann=None):
    """C4：按固定顺序跑（先写后查再删），不依赖 spec 里的书写顺序。返回 (探测数, 豁免集合)。"""
    # 顺序即语义：先写后查再删。r130 在 delete 之前插入 export/import（导入会落数据，
    # 必须排在清理之前，否则探测自己写的条目会被下一轮的清理假设打乱）。
    # 名单 PROBE_ORDER 只承担排序；**要不要打**由下面的 live 决定（见 probe_order 的 r179 记因）。
    ann = ann if ann is not None else annotated_ops(spec)
    skipped = {k: v[1] for k, v in ann.items() if isinstance(v, tuple)}
    live = {}
    for p, it in (spec.get("paths") or {}).items():
        for v, op in (it or {}).items():
            if v in ("get", "post", "put", "delete", "patch") and isinstance(op, dict) and op.get("x-live-check"):
                live[(norm(p), v.upper())] = (p, v, op.get("x-live-check") or {})
    done = 0
    for key in probe_order(live):
        path, verb, cfg = live[key]
        url = BASE + (cfg.get("path") or (path if "{sessionId}" not in path else path.replace("{sessionId}", "contract-probe")))
        st, bodytxt = http(verb, url, cfg.get("body"), cfg.get("query"))
        if st == 429:
            # r131：**被限流不是契约不符**。令牌桶是服务端共享状态——紧挨着跑完性能基准
            # （62 次请求）再跑契约，就会看到 /api/usage 与 delete 各吃一个 429（实测）。
            # 把它判成红，等于让红项长期指向一个不可修的东西。等桶回满重试一次再判。
            time.sleep(SETTLE_SECONDS)
            st, bodytxt = http(verb, url, cfg.get("body"), cfg.get("query"))
            RATE_LIMITED.append(f"{verb} {path}")
        want = cfg.get("status") or [200]
        ok = st in want
        detail = f"{verb} {path} -> {st}"
        if st is None:
            # 连不上/超时：点名到具体端点并带上异常类型，不当绿也不静默跳过
            detail = f"{verb} {path} -> 未验（{bodytxt[:80]}）"
        # r28：CI runner 没有上游密钥（密钥不落仓）。那种环境下 `POST /api/chat` 的**契约正确响应**
        # 就是 `500 {"error":"no-key"}`（错误体与 v1 逐字一致，本来就是 J2 的验收项之一）。
        # 只对「这一条端点 + 这个错误体」放宽，并把走了哪条分支打印出来 —— 静默放宽等于没判。
        if not ok and path == "/api/chat" and st == 500 and '"no-key"' in bodytxt:
            ok = True
            NOKEY.append(f"{verb} {path}")
        if ok and cfg.get("required_keys"):
            try:
                parsed = json.loads(bodytxt)
            except Exception:
                parsed = None
            keys = [k for k in cfg["required_keys"]
                    if (isinstance(parsed, dict) and k in parsed)
                    or (isinstance(parsed, list) and (not parsed or k in parsed[0]))]
            miss = [k for k in cfg["required_keys"] if k not in keys]
            if miss:
                ok, detail = False, detail + f" 缺键 {miss}"
        check(f"C4 运行态一致 {verb} {path}", ok,
              detail + ("" if ok else f" | body[:80]={bodytxt[:80]}")
              + (f"｜接受契约内 500（本环境无上游密钥，错误体 no-key 与 v1 逐字一致）"
                 if f"{verb.upper()} {path}" in NOKEY else ""))
        done += 1
    return done, skipped


def norm_path(p):
    """归一化路径以便双向对账：`{sessionId}` 这类模板段统一成 `*`，去尾斜杠。"""
    return re.sub(r"\{[^}]+\}", "*", p).rstrip("/")


def manual_legs(spec_paths, manual_text):
    """C7 纯函数：yaml 路径集 ⇄ 人读手册文本。返回失败描述列表（空=一致）。
    分母取自 yaml（被检对象写不进去的量）；手册侧只认 `/api/` 前缀令牌。"""
    bad = []
    want = {norm_path(p) for p in spec_paths}
    missing = sorted(p for p in spec_paths if norm_path(p) not in
                     {norm_path(t) for t in re.findall(r"/api/[A-Za-z0-9_/{}-]+", manual_text)})
    if missing:
        bad.append(f"手册缺接口（yaml 有、API.md 无）：{missing}")
    ghost = sorted({t for t in re.findall(r"/api/[A-Za-z0-9_/{}-]+", manual_text)
                    if norm_path(t) not in want})
    if ghost:
        bad.append(f"手册虚报接口（API.md 写了、yaml 无）：{ghost}")
    claimed = re.findall(r"(\d+)\s*(?:条)?路径", manual_text)
    if claimed and int(claimed[0]) != len(want):
        bad.append(f"手册声明的路径数过期：写 {claimed[0]}、yaml 实为 {len(want)}")
    return bad


def selftest():
    """合成样本证明 C1/C2/C3/C4 四条判据**都会报红**（不是恒真）。"""
    import yaml
    spec = yaml.safe_load(SPEC.read_text("utf-8"))
    bad = []
    if compare_static(spec):
        bad.append(f"原样 spec 被判失败：{compare_static(spec)}")
    trimmed = json.loads(json.dumps(spec))
    trimmed["paths"].pop("/api/emotion/lexicon")
    if not compare_static(trimmed):
        bad.append("篡改①（删掉一个真实路由的文档）未被 C1 抓到 ⇒ 恒真")
    ghosted = json.loads(json.dumps(spec))
    ghosted["paths"]["/api/does-not-exist"] = {"get": {"responses": {"200": {}}}}
    if not compare_static(ghosted):
        bad.append("篡改②（凭空加一条幽灵路径）未被 C2 抓到 ⇒ 恒真")
    if not compare_static(spec, called={"/api/secret-side-channel"}):
        bad.append("篡改③（前端偷调未文档化端点）未被 C3 抓到 ⇒ 恒真")
    req = ["lex", "final", "not-present"]
    parsed = {"lex": {}, "final": {}, "path": "x"}
    miss = [k for k in req if k not in parsed]
    if miss != ["not-present"]:
        bad.append(f"篡改④（响应缺 required 键）判据不生效：miss={miss}")
    missing_ann = {k for k in spec_ops(spec)} - set(annotated_ops(spec))
    if not missing_ann and len(spec_ops(spec)) == len(annotated_ops(spec)):
        # 原样应全覆盖；再用"删掉一条标注"的样本证明 C6 会报红
        pass
    stripped = json.loads(json.dumps(spec))
    stripped["paths"]["/api/memory/emotions"]["get"].pop("x-live-check", None)
    a_full, a_strip = annotated_ops(spec), annotated_ops(stripped)
    if len(a_strip) >= len(a_full):
        bad.append("篡改⑤（抹掉一条 x-live-check 标注）未被 C6 抓到 ⇒ 覆盖判据恒真")
    # probe_order（r179 新增）：成员资格由 spec 决定，名单只管先后。五条腿各钉一个失效形态。
    known = [(norm(p), v.upper()) for p, v in PROBE_ORDER]
    fresh = (norm("/api/health/db"), "GET")
    cleanup_key = (norm(CLEANUP_LAST[0]), CLEANUP_LAST[1].upper())
    seq = probe_order(known + [fresh])
    if fresh not in seq:
        bad.append("probe_order 腿①：spec 新增而名单未写的接口被丢掉 ⇒ 新接口静默不探测，"
                   "这正是 r179 现场（/api/health/db 标了 x-live-check 而 C4 一条没打）")
    if probe_order([fresh]) != [fresh]:
        bad.append("probe_order 腿②：只投一件却排出别件 ⇒ 序列由名单决定而非由入参决定，"
                   "等于回到手抄名册（腿① 会被这条掩护成假绿）")
    if seq[-1] != cleanup_key:
        bad.append("probe_order 腿③：清理腿没压到最后（实=%s）⇒ 探测自己写进 contract-probe 的数据会被提前删走" % (seq[-1],))
    if [k for k in seq if k in known] != known:
        bad.append("probe_order 腿④：已知项相对次序改变 ⇒「先写后查再删」的语义不再成立")
    if probe_order([]) != []:
        bad.append("probe_order 腿⑤：空入参凭空造出探测项 ⇒ 无标注的接口也被打，成员资格失控")
    # C7 三态：原样必须过，三类合成篡改必须各报红
    sp = set(spec.get("paths") or {})
    mdp = ROOT / "docs" / "API.md"
    if not mdp.exists():
        bad.append("C7 自检读不到 docs/API.md ⇒ 无法证伪（不得据此算过）")
    else:
        md = mdp.read_text("utf-8", errors="replace")
        if manual_legs(sp, md):
            bad.append(f"原样手册被判失败：{manual_legs(sp, md)}")
        if not manual_legs(sp | {"/api/brand-new-route"}, md):
            bad.append("篡改⑥（yaml 新增接口而手册没写）未被 C7 抓到 ⇒ 手册腿恒真")
        if not manual_legs(sp, md + "\n`GET /api/ghostly-side-door`\n"):
            bad.append("篡改⑦（手册凭空多写一条接口）未被 C7 抓到 ⇒ 手册腿恒真")
        # 篡改⑧要把计数写歪。⚠️ 这里**不能硬编码**旧计数串（第一版写死 "11 路径"，
        # 手册真值改成 12 之后替换变空操作 ⇒ 合成样本等于原样 ⇒ 腿被误判成恒真）。
        # 正解：从手册里正则读回它自己声明的数，再换成一个对不上的值。
        _claimed = re.findall(r"(\d+)\s*(?:条)?路径", md)
        if not _claimed:
            bad.append("C7 自检读不到手册声明的路径计数 ⇒ 计数腿无法证伪")
        elif manual_legs(sp, md.replace(_claimed[0] + " 路径", "999 路径", 1)) == []:
            bad.append("篡改⑧（手册把路径计数写歪）未被 C7 抓到 ⇒ 计数腿恒真")
    print("SELFTEST-PASS: 删文档/加幽灵/偷调用/缺键/抹标注/手册三面漂移 八类样本均被抓到、原样零问题"
          if not bad else "SELFTEST-FAIL: " + "; ".join(bad))
    return 1 if bad else 0


def main():
    global BASE
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    # r130：8123 上跑的可能是他人旧产物（瘦 jar 无新路由），那时 C4 会整片假红。
    # 给一个显式换基址的口子，就能在「含新代码的实例」上完成运行态对账，
    # 而不是靠 x-live-skip 把新接口永久豁免掉（C6b 会因此判红，正是它的作用）。
    base = os.environ.get("XINYU_CONTRACT_BASE", "").strip()
    if "--base" in sys.argv:
        idx = sys.argv.index("--base")
        if idx + 1 < len(sys.argv):
            base = sys.argv[idx + 1].strip()
    if base:
        BASE = base.rstrip("/")
        print(f"  · 运行态基址 = {BASE}（--base 覆盖，非默认 8123）")
    if not SPEC.exists():
        print("API-CONTRACT-ENV-ERROR: 缺 docs/openapi.yaml")
        return 2
    try:
        import yaml
    except Exception as e:
        print(f"API-CONTRACT-ENV-ERROR: 缺 PyYAML（{e}）")
        return 2
    spec = yaml.safe_load(SPEC.read_text("utf-8"))
    bad = compare_static(spec)
    check("C1+C2+C3 三方静态对账（控制器↔文档↔前端）", not bad, " ; ".join(bad))
    jv = java_routes()
    print(f"  · 控制器路由 {len(jv)} 条 | spec 操作 {len(spec_ops(spec))} 条 | 前端引用 "
          f"{len(frontend_calls())} 条")
    # C7（r89）：人读手册 ⇄ yaml。放在 jar 探测**之前**，这样无密钥/无服务的降级环境里
    # 这一腿仍出数；手册缺失按判红处理（人读手册是门面件，被删不是"环境异常"）。
    mdp = ROOT / "docs" / "API.md"
    if not mdp.exists():
        check("C7 人读手册对账（API.md ⇄ openapi.yaml）", False, "docs/API.md 不存在")
    else:
        mb = manual_legs(set((spec.get("paths") or {})), mdp.read_text("utf-8", errors="replace"))
        check("C7 人读手册对账（API.md ⇄ openapi.yaml：不缺/不虚/计数不失）",
              not mb, " ; ".join(mb) or f"yaml {len(spec.get('paths') or {})} 路径逐条在册、零幽灵")
    st, health_body = http("get", BASE + "/api/health")
    if st != 200:
        print(f"API-CONTRACT-ENV-ERROR: 服务未在 {BASE} 运行（C4 需要它）")
        return 2
    # r131：**运行态结果必须注明它是从哪份产物上量出来的**。
    # `build` 是自 r131 起的产物身份；缺失 ⇒ 打的是更早的产物（本仓实测：8123 上就是这种）。
    # 此前「旧产物没有新路由」只能靠某条超时去猜，于是同一份绿被反复误读成"新代码没问题"。
    # 不据此判红（换新产物不由本判据控制，判红只会把环境问题刷成红项），但**绝不允许静默**。
    build = None
    try:
        build = (json.loads(health_body) or {}).get("build")
    except Exception:
        build = None
    legacy = not build
    print("  · 运行态产物身份: build=%s" % (build if build else "**缺失** ⇒ 这是 r131 之前的产物"))
    if legacy:
        print("    ⚠ 以下 C4 结果来自**无产物身份的旧实例**：新接口的运行态证据请以"
              " `python _test/api_contract_check.py --base <含新代码的实例>` 为准。")
        if "--require-build" in sys.argv:
            # r131：严格模式。旧产物上的 404/405 不是"接口错了"，是"这份产物里根本没有它"——
            # 把那当作红会让红项长期挂着却不指向任何可修的东西。严格模式下直接判未验。
            print("API-CONTRACT-UNVERIFIED: 该实例无产物身份（r131 之前的产物）⇒"
                  " --require-build 下不予置评（rc=2）。换新产物后复跑。")
            return 2
    ops = spec_ops(spec)
    ann = annotated_ops(spec)
    done, skipped = live_probes(spec, ann)
    # C6（r22）：覆盖度改为**精确对账**，不再用 "done >= 8" 这种会静静放过缺口的阈值。
    # 上一轮真实操作 11 条、只探测 8 条，断言却绿 —— 典型"阈值低于总量即掩盖"。
    check("C6 覆盖度：每条操作要么真实探测、要么显式 x-live-skip 并给理由",
          done + len(skipped) == len(ops) and len(skipped) == 0 or (done + len(skipped) == len(ops)),
          f"探测 {done} + 豁免 {len(skipped)} == 操作 {len(ops)}"
          + ("" if done + len(skipped) == len(ops) else " ⇒ 有接口既不探测也不解释"))
    check("C6b 零豁免（本项目 11 条接口全部可安全真实打；出现豁免必须有人复核）",
          len(skipped) == 0, f"当前豁免 {len(skipped)} 条：{sorted(skipped)}")
    if RATE_LIMITED:
        print(f"  · 限流重试：{len(RATE_LIMITED)} 条曾撞上 429（等 {SETTLE_SECONDS}s 后重打一次）"
              f" —— {'; '.join(RATE_LIMITED)}")
    fails = [r for r in results if not r[1]]
    print(f"\n合计 {len(results)} 项，失败 {len(fails)} 项")
    for n, _, d in fails:
        print("  🔴", n, d)
    if fails:
        print("API-CONTRACT-FAIL")
    elif legacy:
        print("API-CONTRACT-PASS（⚠ 运行态打的是**无产物身份的旧实例**，"
              "本轮的绿只能证明旧产物这些接口还在，不能当新代码的证据）")
    else:
        print("API-CONTRACT-PASS")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
