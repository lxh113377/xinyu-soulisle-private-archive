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
             （防"注释里写着 r128、实际换了库"，也防正则本身失效造成假通过）
  V3 覆盖：`src/vendor/*.js` 必须全部登记 —— 新增库不登记即红（与 size_budget 的覆盖判据同族）
  V4 上游漂移：查 GitHub 最新 release/tag，报告落后多少；**默认不判红**（截止前不制造阻塞），
             加 --strict 才把"落后"当失败
  V5 --selftest：合成三类篡改样本（改哈希 / 改版本声明 / 塞未登记文件）必须各自报红，
             原样必须零问题 —— 证明 V1–V3 非恒真

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


def audit(manifest, disk):
    """纯函数：manifest(dict) + disk({相对路径: bytes}) → 问题清单。V1–V3 与 V5 共用。"""
    bad = []
    libs = manifest.get("libs") or []
    if not libs:
        return ["manifest.libs 为空（判据没有输入，不允许当通过）"]
    for lib in libs:
        rel, want_v = lib["file"], lib["version"]
        data = disk.get(rel)
        if data is None:
            bad.append(f"{rel} 磁盘缺失")
            continue
        if hashlib.sha256(data).hexdigest() != lib["sha256"]:
            bad.append(f"{rel} sha256 与 manifest 不符（文件被替换？跑 --refresh 确认后再更新台账）")
        if len(data) != lib["size"]:
            bad.append(f"{rel} 字节数 {len(data)} != 声明 {lib['size']}")
        m = re.search(lib["detect"], data.decode("utf-8", "replace"))
        if not m:
            bad.append(f"{rel} 版本正则零命中（{lib['detect']}）—— 判据失效或文件已换，不得视为通过")
        else:
            got = m.group(1)
            norm = ("r" + got) if not got[0].isalpha() and lib["version"].startswith("r") else got
            if norm != want_v:
                bad.append(f"{rel} 内容解析出 {norm}，manifest 声明 {want_v}")
    return bad


def audit_coverage(manifest, vendor_files):
    declared = {Path(l["file"]).name for l in manifest.get("libs", [])}
    return sorted(set(vendor_files) - declared)


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
    if audit(manifest, disk):
        bad.append(f"原样被判失败：{audit(manifest, disk)}")
    tampered = json.loads(json.dumps(manifest))
    tampered["libs"][0]["sha256"] = "0" * 64
    if not audit(tampered, disk):
        bad.append("篡改样本①（改 sha256）未被抓到 —— V1 恒真")
    bumped = json.loads(json.dumps(manifest))
    bumped["libs"][1]["version"] = "9.9.9"
    if not audit(bumped, disk):
        bad.append("篡改样本②（版本声明与内容脱节）未被抓到 —— V2 恒真")
    real_on_disk = sorted(p.name for p in (ROOT / "src" / "vendor").glob("*.js"))
    ghost = json.loads(json.dumps(manifest))
    ghost["libs"].pop()                      # 模拟"新 vendor 库落盘但没登记台账"
    dropped = Path(manifest["libs"][-1]["file"]).name
    if dropped not in real_on_disk:
        bad.append(f"篡改样本③构造无效：{dropped} 不在磁盘清单里")
    elif dropped not in audit_coverage(ghost, real_on_disk):
        bad.append("篡改样本③（删掉一个库的登记）未被 V3 抓到 —— 覆盖判据恒真")
    if not audit_coverage(manifest, real_on_disk + ["sneaky.min.js"]):
        bad.append("篡改样本④（凭空塞未登记文件）未被抓到 —— V3 恒真")
    print("SELFTEST-PASS: 4 类篡改全部被抓到、原样零问题" if not bad else "SELFTEST-FAIL: " + "; ".join(bad))
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
        p = ROOT / lib["file"]
        disk[lib["file"]] = p.read_bytes() if p.exists() else None
    bad = audit(manifest, disk)
    for lib in manifest["libs"]:
        p = ROOT / lib["file"]
        if disk.get(lib["file"]) is not None:
            print(f"  {lib['name']:14s} 声明 {lib['version']:8s} "
                  f"sha256={lib['sha256'][:12]}… size={lib['size']:,d}")
    check_ok = not bad
    print(f"  {'PASS' if check_ok else 'FAIL'}  V1+V2 完整性与版本对账"
          + ("" if check_ok else "  -> " + "; ".join(bad)))

    on_disk = sorted(p.name for p in (ROOT / "src" / "vendor").glob("*.js"))
    unreg = audit_coverage(manifest, on_disk)
    print(f"  {'PASS' if not unreg else 'FAIL'}  V3 vendor 全覆盖登记"
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
