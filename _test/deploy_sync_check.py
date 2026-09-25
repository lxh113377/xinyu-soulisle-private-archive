# 心屿 · 部署副本同步守卫（src/ → deploy/xinyu/）
#
# 立此脚本的原因（2026-09-23 实证）：修完 `src/js/emotion-engine.js` 的缺陷后，
# `deploy/xinyu/`（公网版）**仍是旧引擎** —— 若直接构建镜像/部署，线上会继续跑带缺陷的版本。
# 更隐蔽的是：第一次手工比对时 PowerShell 函数 `H` 被内置别名 `h`(Get-History) 覆盖，
# 两边哈希都取不到 → `None == None` → **8 个文件全报 SAME**（假通过）。
# 因此本脚本强制：① 哈希必须非空 ② 输入必须先证非空 ③ 三类比对全归零才算 PASS。
#
# 用法：python _test/deploy_sync_check.py     → 0 = DEPLOY-SYNC-PASS，1 = FAIL
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
DST = ROOT / "deploy" / "xinyu"

# 不参与前端同步的内容：Pages Function 源单独部署在 deploy/functions/
EXCLUDE_DIRS = {"functions"}
# 刻意不复制的文件：公网零密钥 stub（src 版含真实 Key，绝不能覆盖过去）。
# 它**不参与内容比对**（两端本就该不同），只走下方「红线复核」。
EXCLUDE_FILES = {"js/demo-config.js"}
WHITELIST_EXTRA = {"js/demo-config.js", "_headers"}   # _headers 是 Pages 专属（jar 不读），只存在于部署副本
KEY_RE = "sk-[A-Za-z0-9]{20,}"


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(p: Path, base: Path) -> str:
    return p.relative_to(base).as_posix()


def main() -> int:
    import re

    fails = []

    if not SRC.is_dir() or not DST.is_dir():
        print("DEPLOY-SYNC-FAIL: src/ 或 deploy/xinyu/ 不存在")
        return 1

    src_files = [
        p for p in SRC.rglob("*")
        if p.is_file()
        and not (set(p.relative_to(SRC).parts) & EXCLUDE_DIRS)
        and rel(p, SRC) not in EXCLUDE_FILES
    ]
    # 输入非空性断言（R247：结论为「0 命中/通过」前必须先证输入非空）
    if len(src_files) < 5:
        fails.append(f"输入可疑：src/ 只扫到 {len(src_files)} 个文件，比对结论不可信")
    print(f"扫描 src/ = {len(src_files)} 个文件")

    src_rel = {rel(p, SRC) for p in src_files}
    dst_rel = {rel(p, DST) for p in DST.rglob("*") if p.is_file()} - EXCLUDE_FILES

    missing = sorted(src_rel - dst_rel)
    extra = sorted(dst_rel - src_rel)
    diff = []
    for p in src_files:
        r = rel(p, SRC)
        q = DST / r
        if q.is_file():
            a, b = sha256(p), sha256(q)
            if not a or not b:
                fails.append(f"哈希为空（比对不可信）: {r}")
            elif a != b:
                diff.append(r)

    for r in missing:
        print(f"  MISSING  {r}")
    for r in diff:
        print(f"  DIFF     {r}")
    unexpected_extra = [r for r in extra if r not in WHITELIST_EXTRA]
    for r in unexpected_extra:
        print(f"  EXTRA    {r}")
    for r in extra:
        if r in WHITELIST_EXTRA:
            print(f"  EXTRA(白名单，符合预期)  {r}")

    if missing:
        fails.append(f"MISSING {len(missing)} 项")
    if diff:
        fails.append(f"DIFF {len(diff)} 项")
    if unexpected_extra:
        fails.append(f"EXTRA {len(unexpected_extra)} 项")

    # 红线复核：白名单里的 stub 必须存在、零密钥、且与含 Key 的 src 版不同
    for r in WHITELIST_EXTRA:
        stub = DST / r
        origin = SRC / r
        if not stub.is_file():
            fails.append(f"缺少公网零密钥 stub: {r}")
            continue
        text = stub.read_text(encoding="utf-8", errors="replace")
        if re.search(KEY_RE, text):
            fails.append(f"红线：公网 stub 含真实 Key -> {r}")
        if origin.is_file() and sha256(stub) == sha256(origin):
            fails.append(f"红线：公网 stub 与 src 版相同（src 版含 Key）-> {r}")
        print(f"  红线复核 {r}: 零密钥={not re.search(KEY_RE, text)} 与src不同="
              f"{not origin.is_file() or sha256(stub) != sha256(origin)}")

    print()
    if fails:
        print("DEPLOY-SYNC-FAIL")
        for f in fails:
            print("  -", f)
        return 1
    print(f"DEPLOY-SYNC-PASS  (src→deploy/xinyu 三类归零：missing=0 diff=0 extra=0(白名单外))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
