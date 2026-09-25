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
  G8 --selftest：十类合成篡改（ecosystem 拼错 / 目录不存在 / interval 非法 / updates 清空 /
     抹 gsap 登记 / 抹 README 引用 / 抹评测集行 / 评测条数改小 / 删整节 / 表退回模板原句）
     必须各自报红，原样必须零问题 —— 证判据非恒真

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
    print("SELFTEST-PASS: 十类合成篡改全部被抓到、原样零问题" if not bad else "SELFTEST-FAIL: " + "; ".join(bad))
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

    fails = [r for r in results if not r[1]]
    print(f"\n合计 {len(results)} 项，失败 {len(fails)} 项")
    for nm, _, d in fails:
        print("  🔴", nm, d)
    print("REPO-CONFIG-PASS" if not fails else "REPO-CONFIG-FAIL")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
