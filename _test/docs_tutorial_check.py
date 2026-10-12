#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""心屿 · 教程面常驻判据（r130 新增，闭合八维第 7 维「文档厚度差」的可守护侧）。

为什么补这一根尺：
  第 7 维实测是「位齐、厚度差」——本仓教程 4 篇 ⇄ `lobehub` 单仓 51 篇。补篇数只是把数字写好看，
  真正会退化的是**腐烂**：教程里写的脚本路径被搬走、写的接口被改名，而 Markdown 永远不会自己报错。
  所以这根尺守的不是「有没有」，而是「**还成不成立**」。

四条腿：
  T1 篇数下限棘轮（只升不降）：教程被删 ⇒ 红
  T2 索引在册：每篇必须在 `docs/README.md` 出现（写了但没进索引 = 对读者不存在）
  T3 路径不腐烂：教程引用的仓库文件必须真实存在（改代码后步骤失效无人知的那一类）
  T4 接口不虚报：教程里出现的 `/api/...` 必须在 `docs/openapi.yaml` 已声明

用法：
  python _test/docs_tutorial_check.py            # 全量判
  python _test/docs_tutorial_check.py --selftest # 合成篡改自证（不依赖网络/服务）

退出码：0=绿；1=判红；2=环境未验（缺 docs/README.md、缺 openapi.yaml 或读不动 yaml）
"""
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
INDEX = DOCS / "README.md"
SPEC = DOCS / "openapi.yaml"

# 棘轮下限：**只升不降**。立尺时实测 6 篇，门槛定 4（给删减留一格，但不允许塌到历史水位以下）。
MIN_TUTORIALS = 4

# 只验这些前缀的引用：散文里出现的 `foo.py` 之类的示例名不该被当成仓库文件
REPO_PREFIXES = ("docs/", "_test/", "src/", "server/", "memory/", "deploy/", "交付物/")
REF_RE = re.compile(r"`([A-Za-z0-9_./\-]+\.(?:py|js|mjs|java|md|json|ya?ml|sh|ps1|toml))`")
API_RE = re.compile(r"/api/[A-Za-z0-9_/{}\-]+")
results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(f"  {'PASS' if ok else 'RED '}  {name}" + (f"  -> {detail}" if detail else ""))


def tutorials():
    return sorted(p for p in DOCS.glob("tutorial-*.md") if p.is_file())


def strip_ellipsis(text):
    """示意路径不是引用：`server/.../api/X.java` 里的 `...` 表示省略，不该拿去查文件是否存在。

    不清洗的话，散文里的示意路径会被判成「文件不存在」，而 `/api/X` 还会被接口腿捡走
    判成幽灵接口 —— 两处误报同一个源头（r130 首版即踩到，存量教程 02 命中）。
    """
    return re.sub(r"[A-Za-z0-9_./\-]*\.\.\.[A-Za-z0-9_./\-]*", " ", text or "")


def missing_refs(text):
    """纯函数：教程文本 → 引用了但仓库里不存在的文件路径列表。"""
    out = []
    for m in REF_RE.finditer(strip_ellipsis(text)):
        ref = m.group(1)
        if not ref.startswith(REPO_PREFIXES):
            continue
        if not (ROOT / ref).exists():
            out.append(ref)
    return sorted(set(out))


def norm_api(p):
    return re.sub(r"\{[^}]+\}", "*", p).rstrip("/")


def ghost_apis(text, spec_paths):
    """纯函数：教程文本 → 写了但 openapi 里没有声明的 /api/... 列表。

    前缀匹配与 `api_contract_check.py` 的 C3 同口径：前端用 `/api/memory` + 子路径拼接
    （`memory-store.js` 的 `api(path)` 形态），把前缀判成幽灵等于误伤真实用法。
    """
    want = {norm_api(p) for p in spec_paths}
    ghost = []
    for t in API_RE.findall(strip_ellipsis(text)):
        n = norm_api(t)
        if n in want:
            continue
        if any(n == w or n.rstrip("/") in w or w.startswith(n.rstrip("/") + "/") for w in want):
            continue
        ghost.append(n)
    return sorted(set(ghost))


def spec_paths():
    import yaml
    spec = yaml.safe_load(SPEC.read_text("utf-8"))
    return set((spec or {}).get("paths") or {})


def selftest():
    bad = []
    real = tutorials()
    if not real:
        bad.append("自检读不到任何教程 ⇒ 无法证伪（不得据此算过）")
    else:
        sample = real[0].read_text("utf-8", errors="replace")
        if missing_refs(sample):
            bad.append(f"原样教程被判引用失效：{missing_refs(sample)}（若为真缺陷请先修教程）")
        # 篡改①：写一个不存在的仓库路径 ⇒ 必须被抓
        if not missing_refs(sample + "\n见 `_test/this_file_should_not_exist.py` 的用法\n"):
            bad.append("篡改①（教程引用了不存在的脚本）未被 T3 抓到 ⇒ 腐烂腿恒真")
        # 反向腿：示意路径（`...` 省略号）不得被当成失效引用 —— 否则整条腿全是误报
        if missing_refs("见 `server/.../api/EmotionController.java` 的实现"):
            bad.append("示意路径被当成失效引用 ⇒ T3 会产生大量误报")
        if ghost_apis("见 `server/.../api/EmotionController.java`", spec_paths() if SPEC.exists() else set()):
            bad.append("示意路径里的 /api/ 片段被当成幽灵接口 ⇒ T4 会产生误报")
        # 篡改②：写一条幽灵接口 ⇒ 必须被抓
        try:
            sp = spec_paths()
            if not ghost_apis("试试 `/api/ghostly-side-door`", sp):
                bad.append("篡改②（教程凭空写一条接口）未被 T4 抓到 ⇒ 接口腿恒真")
            if ghost_apis("`/api/health`", sp):
                bad.append("原样接口被误判为幽灵 ⇒ 归一化有问题")
        except Exception as e:
            bad.append(f"自检读不动 openapi.yaml（{e}）⇒ T4 无法证伪")
        # 篡改③：把一篇教程从索引里摘掉 ⇒ T2 必须红
        idx = INDEX.read_text("utf-8", errors="replace")
        if real[0].name in idx:
            stripped = idx.replace(real[0].name, "")
            if [t for t in real if t.name not in stripped] == []:
                bad.append("篡改③（教程被移出索引）未被 T2 抓到 ⇒ 索引腿恒真")
        else:
            bad.append(f"{real[0].name} 不在索引里 ⇒ 自检无法证伪 T2")
        # 篡改④：篇数下限 —— 用合成数验证门槛会生效
        if len(real) - 1 >= MIN_TUTORIALS and not (len(real) >= MIN_TUTORIALS):
            bad.append("篡改④（篇数跌破下限）未被 T1 抓到 ⇒ 棘轮恒真")
    print("TUTORIAL-SELFTEST-%s（%s）" % ("FAIL" if bad else "PASS", "; ".join(bad) or "四类篡改均被抓到、原样零问题"))
    return 1 if bad else 0


def main():
    if "--selftest" in sys.argv:
        return selftest()
    if not INDEX.exists():
        print("TUTORIAL-ENV-ERROR: 缺 docs/README.md")
        return 2
    if not SPEC.exists():
        print("TUTORIAL-ENV-ERROR: 缺 docs/openapi.yaml")
        return 2
    try:
        sp = spec_paths()
    except Exception as e:
        print(f"TUTORIAL-ENV-ERROR: openapi.yaml 读不动（{e}）")
        return 2

    ts = tutorials()
    check("T1 教程篇数下限棘轮（只升不降）", len(ts) >= MIN_TUTORIALS,
          f"实测 {len(ts)} 篇 | 下限 {MIN_TUTORIALS}")

    idx = INDEX.read_text("utf-8", errors="replace")
    off = [t.name for t in ts if t.name not in idx]
    check("T2 每篇教程都在 docs/README.md 索引里", not off, f"未进索引：{off}" if off else f"{len(ts)} 篇逐条在册")

    rot = {}
    for t in ts:
        miss = missing_refs(t.read_text("utf-8", errors="replace"))
        if miss:
            rot[t.name] = miss
    check("T3 教程引用的仓库文件必须真实存在（路径不腐烂）", not rot,
          json.dumps(rot, ensure_ascii=False) if rot else f"{len(ts)} 篇引用逐条可达")

    ghost = {}
    for t in ts:
        g = ghost_apis(t.read_text("utf-8", errors="replace"), sp)
        if g:
            ghost[t.name] = g
    check("T4 教程里的 /api/... 必须在 openapi.yaml 已声明（不虚报接口）", not ghost,
          json.dumps(ghost, ensure_ascii=False) if ghost else f"逐条在册（spec {len(sp)} 路径）")

    fails = [r for r in results if not r[1]]
    print(f"合计 {len(results)} 项，失败 {len(fails)} 项")
    print("TUTORIAL-DOCS-PASS" if not fails else "TUTORIAL-DOCS-FAIL")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
