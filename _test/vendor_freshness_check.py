# -*- coding: utf-8 -*-
"""首屏 vendor 供给链守卫（完整性 + 版本声明对账 + 上游漂移探测）

动机（对标轮 r20，实测数字）：心屿走「零构建 + 本地 vendor」路线，三个第三方库直接落盘在
`src/vendor/`，**没有任何 lockfile / 没有 dependabot**（14 个参照仓里只有 2 家有 deps_autoupdate，
而它们都有 package.json 可以挂；心屿挂不上）⇒ 供应商漂移在本项目里是**纯盲区**：
  - 实测 `src/vendor/three.min.js` 内容里 `REVISION` 值为 **128**（2021 年），
    上游 mrdoob/three.js 当时最新 **r186**（2026-09-24 发布）；
  - `gsap.min.js` / `ScrollTrigger.min.js` banner 声明 **3.12.5**，上游 greensock/GSAP 最新 tag **3.15.0**。
对这类项目，正确做法不是"默默换库"，而是把「谁在什么时候是什么版本、和上游差多少」变成
机器可读的台账 + 每次回归都跑的判据。

判据（V1–V3 离线恒跑，V4 需 --check-upstream）：
  V1 完整性：`_test/vendor-manifest.json` 声明的 sha256/size == 磁盘实际（防无声替换/篡改）
  V2 版本对账：按 manifest 的 detect 正则**从文件内容里**解析出版本 == 声明版本
             （防"注释里写着 r128、实际换了库"，也防正则本身失效造成假通过）。
             `detect: null` 是**一档合法声明**（模型/wasm 无版本横幅可解析）：该条只离开 V2，
             V1 完整性照查，且条数折进判定行（`V2 参与 N 条／声明 detect=null M 条`）——不许静默变瞎。
  V3 覆盖：`src/vendor/*.js` 必须全部登记 —— 新增库不登记即红（与 size_budget 的覆盖判据同族）
  V4 上游漂移：查 GitHub 最新 release/tag，报告落后多少；**默认不判红**（截止前不制造阻塞），
             加 --strict 才把"落后"当失败
  V5 --selftest：合成样本逐轮累积（**条数以本函数实际输出为准，正文不抄数字**）；含 r105 新增的
             「条目缺字段／detect 非串／detect=null 只关一条腿」三形 —— 崩溃必须变成点名判红

退出码：0=FRESHNESS-PASS 1=任一判据失败 2=环境异常（--check-upstream 无网络/无 gh）
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "_test" / "vendor-manifest.json"


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


REQUIRED_FIELDS = ("file", "version", "sha256", "size", "detect")


def field_problems(lib):
    """条目自身可解析性：缺字段 / 类型不对 ⇒ 点名判红，绝不让判据崩成 Traceback。

    一手代价（r105 实测）：名册新增 4 条 mediapipe 条目带 `"detect": null`（wasm/模型文件
    没有可解析的版本横幅），而本函数当时假设 detect 恒为字符串 ⇒
    `re.search(None, …)` 抛 `TypeError: first argument must be string or compiled pattern`，
    电池把这一族收进 **BLIND-RED(判红却无任何判据结论行 ⇒ 仪器崩了)**：既不知道哪条不对，
    也不知道其余 V1/V3 有没有跑过。修类不修例：五字段各判「缺失」与「类型」，
    `detect: null` 有明确语义（本条不参与 V2 版本解析），缺键与错类型才是红。
    """
    name = lib.get("file") if isinstance(lib.get("file"), str) else "<缺 file 字段>"
    out = []
    for k in REQUIRED_FIELDS:
        if k not in lib:
            out.append(f"{name} 缺字段 {k}（名册条目不可解析，V1/V2 对它没有读数）")
            continue
        v = lib[k]
        if k == "size":
            if isinstance(v, bool) or not isinstance(v, int):
                out.append(f"{name} 的 size 不是整数（实={v!r}）")
        elif k == "detect":
            if v is None:
                continue                       # 显式声明「无可解析版本串」，是合法档不是缺件
            if not isinstance(v, str) or not v:
                out.append(f"{name} 的 detect 既不是 null 也不是非空正则串（实={v!r}）")
            else:
                try:
                    re.compile(v)
                except re.error as e:
                    out.append(f"{name} 的 detect 不是合法正则：{e}")
        elif not isinstance(v, str) or not v:
            out.append(f"{name} 的 {k} 不是非空字符串（实={v!r}）")
    return out


def audit(manifest, disk):
    """纯函数：manifest(dict) + disk({相对路径: bytes}) → (问题清单, V2 未参与条数)。V1–V3 与 V5 共用。"""
    bad = []
    libs = manifest.get("libs") or []
    if not libs:
        return ["manifest.libs 为空（判据没有输入，不允许当通过）"], 0
    n_skip = 0
    for lib in libs:
        pr = field_problems(lib)
        if pr:
            bad.extend(pr)
            continue
        rel, want_v = lib["file"], lib["version"]
        data = disk.get(rel)
        if data is None:
            bad.append(f"{rel} 磁盘缺失")
            continue
        if hashlib.sha256(data).hexdigest() != lib["sha256"]:
            bad.append(f"{rel} sha256 与 manifest 不符（文件被替换？跑 --refresh 确认后再更新台账）")
        if len(data) != lib["size"]:
            bad.append(f"{rel} 字节数 {len(data)} != 声明 {lib['size']}")
        if lib["detect"] is None:
            n_skip += 1
            continue
        m = re.search(lib["detect"], data.decode("utf-8", "replace"))
        if not m:
            bad.append(f"{rel} 版本正则零命中（{lib['detect']}）—— 判据失效或文件已换，不得视为通过")
        else:
            got = m.group(1)
            norm = ("r" + got) if not got[0].isalpha() and lib["version"].startswith("r") else got
            if norm != want_v:
                bad.append(f"{rel} 内容解析出 {norm}，manifest 声明 {want_v}")
    return bad, n_skip


def audit_coverage(manifest, vendor_files):
    """按**相对路径整条**比，不按 basename。

    两个 vendor 目录里放同名文件时，basename 口径会互相顶包（src/vendor/a.js 已登记
    就能替 _test/vendor/a.js 蒙过 V3）；所以磁盘侧一律带目录前缀（见 vendor_files_on_disk）。
    """
    declared = {l["file"] for l in manifest.get("libs", [])}
    return sorted(set(vendor_files) - declared)


def vendor_dirs(manifest):
    """枚举面从名册自己读（缺省回落到历史面 src/vendor）。

    ⚠️ 这里曾经**写死** `src/vendor` 一个目录 ⇒ r42 把 axe-core（553,290B）落进 `_test/vendor/`
    时，本判据整轮全绿却对它一无所知：**登记册的分母来自被审对象自己**，新面天然不进审计
    （与 r41 把 disclaimer_forensics 的分母从"手抄单个报告"改成"从目录现读"是同一族）。
    """
    dirs = manifest.get("vendor_dirs") or ["src/vendor"]
    return [str(d) for d in dirs]


def vendor_files_on_disk(manifest):
    """所有声明的 vendor 目录下的 js（带相对目录前缀，避免两个同名文件互相顶包）。"""
    out = []
    for d in vendor_dirs(manifest):
        base = ROOT / d
        if not base.exists():
            continue
        for p in base.glob("*.js"):
            out.append(f"{d}/{p.name}")
    return sorted(out)


def upstream_latest(lib):
    """返回 (最新标识, 取证方式)。上游不发 release 的仓（GSAP）退回 tags。"""
    repo, kind = lib["upstream_repo"], lib.get("upstream_kind", "release")
    if kind == "release":
        try:
            j = json.loads(_gh(f"repos/{repo}/releases/latest"))
            return j["tag_name"], "release"
        except Exception:
            pass
    j = json.loads(_gh(f"repos/{repo}/tags"))
    if not isinstance(j, list) or not j:
        raise RuntimeError(f"{repo} 无 tag 可读")
    return j[0]["name"], "tag"


def _gh(path, timeout=40):
    p = subprocess.run(["gh", "api", path], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    if p.returncode != 0:
        msg = (p.stderr or "").strip()
        low = msg.lower()
        if "could not resolve" in low or "timeout" in low or "connection" in low:
            raise OSError(msg[:160])
        raise RuntimeError(f"gh api {path} -> {msg[:160]}")
    return p.stdout


def selftest():
    manifest = json.loads(MANIFEST.read_text("utf-8"))
    disk = {l["file"]: (ROOT / l["file"]).read_bytes() for l in manifest["libs"]}
    bad = []
    orig, orig_skip = audit(manifest, disk)
    if orig:
        bad.append(f"原样被判失败：{orig}")
    tampered = json.loads(json.dumps(manifest))
    tampered["libs"][0]["sha256"] = "0" * 64
    if not audit(tampered, disk)[0]:
        bad.append("篡改样本①（改 sha256）未被抓到 —— V1 恒真")
    bumped = json.loads(json.dumps(manifest))
    bumped["libs"][1]["version"] = "9.9.9"
    if not audit(bumped, disk)[0]:
        bad.append("篡改样本②（版本声明与内容脱节）未被抓到 —— V2 恒真")
    real_on_disk = vendor_files_on_disk(manifest)
    ghost = json.loads(json.dumps(manifest))
    # 篡改样本③：删掉 axe 那条登记（= r42 的真实处境：文件在盘上、台账里没有、且它在第二个 vendor 目录）
    axe_rel = next((l["file"] for l in manifest["libs"] if "axe-core" in l["file"]), None)
    ghost["libs"] = [l for l in ghost["libs"] if "axe-core" not in l["file"]]
    if not axe_rel:
        bad.append("篡改样本③构造无效：名册里没有 axe-core 条目")
    elif axe_rel not in real_on_disk:
        bad.append(f"篡改样本③构造无效：{axe_rel} 不在磁盘枚举面里（vendor_dirs 配错？）")
    elif axe_rel not in audit_coverage(ghost, real_on_disk):
        bad.append("篡改样本③（删掉 axe 的登记）未被 V3 抓到 —— 覆盖判据恒真")
    if not audit_coverage(manifest, real_on_disk + ["_test/vendor/sneaky.min.js"]):
        bad.append("篡改样本④（第二个 vendor 目录凭空塞未登记文件）未被抓到 —— V3 恒真")
    # 篡改样本⑤：basename 顶包 —— 只登记 src/vendor/twin.js，磁盘另有 _test/vendor/twin.js
    collide = json.loads(json.dumps(manifest))
    collide["libs"].append({"file": "src/vendor/twin.js", "name": "twin", "version": "1",
                            "sha256": "0" * 64, "size": 1})
    if "_test/vendor/twin.js" not in audit_coverage(collide, ["src/vendor/twin.js",
                                                              "_test/vendor/twin.js"]):
        bad.append("篡改样本⑤（同名文件靠 basename 顶包）未被抓到 —— 覆盖判据口径太松")
    # r105 样本⑥⑦⑧⑨：名册条目不可解析 ⇒ 必须点名判红，且**绝不抛异常**
    #   （一手代价：detect=null 让整条判据崩成 TypeError，电池只能报 BLIND-RED，
    #     其余 V1/V3 有没有跑过无人知道。崩溃与判红与环境三分，是本仓自有不变量。）
    for drop, tag in (("detect", "样本⑥缺 detect 键"), ("sha256", "样本⑦缺 sha256"),
                      ("file", "样本⑧缺 file 键")):
        m = json.loads(json.dumps(manifest))
        m["libs"][0].pop(drop, None)
        try:
            got = audit(m, disk)[0]
        except Exception as e:                                     # noqa: BLE001
            bad.append(f"{tag}：判据抛异常 {type(e).__name__} 而非点名判红")
            continue
        if not [g for g in got if "缺字段" in g]:
            bad.append(f"{tag}：未被点名（实={got[:1]}）")
    m = json.loads(json.dumps(manifest))
    m["libs"][0]["detect"] = 7
    try:
        got = audit(m, disk)[0]
    except Exception as e:                                         # noqa: BLE001
        bad.append(f"样本⑨ detect=int：抛 {type(e).__name__} 而非点名判红")
        got = []
    if not [g for g in got if "detect" in g]:
        bad.append("样本⑨ detect=int：未被点名 ⇒ 类型门恒真")
    # 样本⑩ detect=null 只关 V2 一条腿，不许把整条目豁免掉（sha256 篡改仍须抓到）
    m = json.loads(json.dumps(manifest))
    m["libs"][0]["detect"] = None
    m["libs"][0]["sha256"] = "0" * 64
    got, skipped = audit(m, disk)
    if skipped != orig_skip + 1:
        bad.append("样本⑩ detect=null 应让 V2 未参与数在现名册基线 %d 上加 1，实=%d"
                   "（期望由被审对象自报，不手抄）" % (orig_skip, skipped))
    if not [g for g in got if "sha256" in g]:
        bad.append("样本⑩ detect=null 把整条目豁免了 ⇒ null 被读成「这条不用查」")
    if orig_skip:
        print(f"  · 现名册有 {orig_skip} 条声明 detect=null（V2 版本解析不参与，V1 完整性照查）")
    n_case = 10
    print(f"SELFTEST-PASS: {n_case} 类样本全部判其所、原样零问题" if not bad
          else "SELFTEST-FAIL: " + "; ".join(bad))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--check-upstream", action="store_true")
    ap.add_argument("--strict", action="store_true", help="把「落后上游」也判为失败")
    ap.add_argument("--refresh", action="store_true", help="用磁盘实际值回写 sha256/size（改库后显式跑）")
    args = ap.parse_args()

    if not MANIFEST.exists():
        print("FRESHNESS-ENV-ERROR: 缺少 _test/vendor-manifest.json")
        return 2
    manifest = json.loads(MANIFEST.read_text("utf-8"))

    if args.selftest:
        sys.exit(selftest())

    if args.refresh:
        for lib in manifest["libs"]:
            p = ROOT / lib["file"]
            lib["sha256"], lib["size"] = sha256(p), p.stat().st_size
        MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", "utf-8")
        print("VENDOR-MANIFEST-REFRESHED（请核对 git diff 后提交）")
        return 0

    disk = {}
    for lib in manifest["libs"]:
        rel = lib.get("file")
        if not isinstance(rel, str) or not rel:
            continue
        p = ROOT / rel
        disk[rel] = p.read_bytes() if p.exists() else None
    bad, n_skip = audit(manifest, disk)
    for lib in manifest["libs"]:
        rel = lib.get("file")
        if not isinstance(rel, str) or disk.get(rel) is None:
            continue
        sha = lib.get("sha256")
        size = lib.get("size")
        print("  %-14s 声明 %-8s sha256=%s… size=%s" % (
            str(lib.get("name", rel))[:14], str(lib.get("version", "<缺>")),
            sha[:12] if isinstance(sha, str) else "<缺>",
            "{:,d} B".format(size) if isinstance(size, int) and not isinstance(size, bool)
            else "<非整数:%r>" % (size,)))
    check_ok = not bad
    print(f"  {'PASS' if check_ok else 'FAIL'}  V1+V2 完整性与版本对账"
          f"（V2 参与 {len(manifest['libs']) - n_skip} 条／声明 detect=null {n_skip} 条）"
          + ("" if check_ok else "  -> " + "; ".join(bad)))

    on_disk = vendor_files_on_disk(manifest)
    unreg = audit_coverage(manifest, on_disk)
    print(f"  {'PASS' if not unreg else 'FAIL'}  V3 vendor 全覆盖登记（枚举面={','.join(vendor_dirs(manifest))}，磁盘 {len(on_disk)} 件）"
          + ("" if not unreg else f"  -> 未登记 {unreg}"))

    stale = 0
    if args.check_upstream:
        try:
            for lib in manifest["libs"]:
                latest, how = upstream_latest(lib)
                same = latest == lib["version"] or latest.lstrip("v") == lib["version"].lstrip("v")
                stale += 0 if same else 1
                print(f"  {'OK  ' if same else 'STALE'}  {lib['name']:14s} 钉 {lib['version']:8s} "
                      f"上游 {latest:10s}（取证={how}，来源 {lib['upstream_repo']}）")
        except OSError as e:
            print(f"FRESHNESS-ENV-ERROR: 上游探测不可达 {e}")
            return 2
        except Exception as e:
            print(f"  FAIL  V4 上游探测失败（判据本身出错，不得静默） -> {e}")
            return 1
    else:
        print("  SKIP  V4 上游漂移（加 --check-upstream 才联网核对）")

    fails = bool(bad) or bool(unreg) or (args.strict and stale > 0)
    if fails:
        print("VENDOR-FRESHNESS-FAIL")
        return 1
    print("VENDOR-FRESHNESS-PASS" + ("" if not stale else f"（{stale} 个库落后上游，未加 --strict 不阻塞）"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
