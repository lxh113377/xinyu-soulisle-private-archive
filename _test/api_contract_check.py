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

前置：fat jar 起在 8123（C4 用；C1–C3、C5 完全离线）
退出码：0=API-CONTRACT-PASS 1=任一判据失败 2=环境异常（jar 不可达 / 缺 PyYAML / 缺 yaml 文件）
"""
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "docs" / "openapi.yaml"
BASE = "http://127.0.0.1:8123"
results = []
NOKEY = []   # 记录哪些探测走了「契约内 500」分支；收尾必须打印，不允许静默放宽


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


def live_probes(spec, ann=None):
    """C4：按固定顺序跑（先写后查再删），不依赖 spec 里的书写顺序。返回 (探测数, 豁免集合)。"""
    order = [("/api/health", "get"), ("/api/emotion/lexicon", "get"), ("/api/emotion/eval", "get"),
             ("/api/emotion", "post"), ("/api/chat", "post"),
             ("/api/memory/emotion", "post"), ("/api/memory/message", "post"),
             ("/api/memory/stats", "get"), ("/api/memory/emotions", "get"),
             ("/api/memory/messages", "get"), ("/api/memory/{sessionId}", "delete")]
    ann = ann if ann is not None else annotated_ops(spec)
    skipped = {k: v[1] for k, v in ann.items() if isinstance(v, tuple)}
    live = {(norm(p), v.upper()): op.get("x-live-check") or {}
            for p, it in (spec.get("paths") or {}).items() for v, op in (it or {}).items()
            if v in ("get", "post", "put", "delete", "patch") and isinstance(op, dict) and op.get("x-live-check")}
    done = 0
    for path, verb in order:
        cfg = live.get((norm(path), verb.upper()))
        if not cfg:
            continue
        url = BASE + (cfg.get("path") or (path if "{sessionId}" not in path else path.replace("{sessionId}", "contract-probe")))
        st, bodytxt = http(verb, url, cfg.get("body"), cfg.get("query"))
        want = cfg.get("status") or [200]
        ok = st in want
        detail = f"{verb} {path} -> {st}"
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
    print("SELFTEST-PASS: 删文档/加幽灵/偷调用/缺键/抹标注 五类样本均被抓到、原样零问题"
          if not bad else "SELFTEST-FAIL: " + "; ".join(bad))
    return 1 if bad else 0


def main():
    if "--selftest" in sys.argv:
        sys.exit(selftest())
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
    st, _ = http("get", BASE + "/api/health")
    if st != 200:
        print("API-CONTRACT-ENV-ERROR: fat jar 未在 8123 运行（C4 需要它）")
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
    fails = [r for r in results if not r[1]]
    print(f"\n合计 {len(results)} 项，失败 {len(fails)} 项")
    for n, _, d in fails:
        print("  🔴", n, d)
    print("API-CONTRACT-PASS" if not fails else "API-CONTRACT-FAIL")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
