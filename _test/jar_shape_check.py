# -*- coding: utf-8 -*-
"""部署产物形态与新鲜度守卫：`server/target/soulisle-server.jar` 必须是**可运行的 fat jar**。

动因（r70 一手现场，也是 r65 挂账「thin jar 成因未登记」的答案）：
在**已有 java -jar 占着 8123** 的工作机上直接跑 `mvn package` 时 ——
  1) maven-jar-plugin 先把 fat jar **原地覆盖成 thin jar**（56,728 B，无 Main-Class）；
  2) 随后 spring-boot:repackage 要把 jar 改名成 `.original`，但文件被运行中的 JVM 锁住
     ⇒ `Unable to rename ... -> ...jar.original` ⇒ BUILD FAILURE；
  3) 于是盘上留下一枚**结构完整的 zip、却根本没有主清单属性**的 thin jar。
     任何只看「文件存在」的检查（含人眼 `ls`）都会把它读成「fat jar 已就绪」。
⇒ 结论：`build_jar.py` 那条正确路径（先 stop_holders 再构建再验货）是**约定**，
   不是闸；本轮把它变成闸。

三态（不把盲区折叠成零）：
  PASS       产物在、是 fat、且不比源码旧
  FAIL       产物在、但 thin（缺 JarLauncher / BOOT-INF/lib 为空）或比源码旧
  SKIP       产物不在（clean clone / CI 的无构建 job）⇒ 如实印 UNVERIFIED 原因，不印 PASS
"""
import argparse
import os
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JAR = ROOT / "server" / "target" / "soulisle-server.jar"
MIN_FAT_BYTES = 20_000_000          # 实测 fat=28,446,595 B；thin=56,728 B（两者差 500 倍，取中间量不致误判）
SRC_ROOTS = ("server/src/main", "server/pom.xml")


def newest_source(root=ROOT, src_roots=SRC_ROOTS):
    """返回 (最新源码文件相对路径, mtime)。跳过 target/ 与 .pyc，避免产物自比。"""
    best, best_ts = "", 0.0
    for rel in src_roots:
        p = root / rel
        cand = [p] if p.is_file() else [q for q in p.rglob("*") if q.is_file()]
        for q in cand:
            sq = str(q).replace("\\", "/")
            if "/target/" in sq or q.suffix in (".pyc", ".class"):
                continue
            ts = q.stat().st_mtime
            if ts > best_ts:
                best, best_ts = sq.rsplit("/", 1)[-1], ts
    return best, best_ts


def inspect(jar_path, src_newest_ts=0.0, src_newest="", min_bytes=MIN_FAT_BYTES):
    """纯判定：返回 dict(verdict, reason, facts...)。verdict ∈ PASS/FAIL/SKIP。"""
    jar = Path(jar_path)
    if not jar.is_file():
        return {"verdict": "SKIP", "reason": "产物不存在（clean clone / 该 job 不构建 jar）", "bytes": 0}
    size = jar.stat().st_size
    if size == 0:
        return {"verdict": "FAIL", "reason": "jar 为 0 字节", "bytes": 0}
    thin_reason = None
    libs = 0
    try:
        with zipfile.ZipFile(jar) as z:
            names = z.namelist()
            libs = sum(1 for n in names if n.startswith("BOOT-INF/lib/"))
            try:
                mf = z.read("META-INF/MANIFEST.MF").decode("utf-8", errors="replace")
            except KeyError:
                mf = ""
    except (zipfile.BadZipFile, OSError) as e:
        return {"verdict": "FAIL", "reason": "jar 不是合法 zip：%s" % type(e).__name__, "bytes": size}
    if "JarLauncher" not in mf and "Start-Class" not in mf:
        thin_reason = "thin jar（MANIFEST 无 JarLauncher/Start-Class ⇒ java -jar 报「没有主清单属性」）"
    elif libs == 0:
        thin_reason = "fat 形态缺依赖（BOOT-INF/lib 条目数 = 0）"
    elif size < min_bytes:
        thin_reason = "体积 %d B < fat 下界 %d B" % (size, min_bytes)
    if thin_reason:
        return {"verdict": "FAIL", "reason": thin_reason, "bytes": size, "libs": libs,
                "remedy": "python _test/build_jar.py（它会先停掉占 8123 的进程再构建）"}
    if src_newest_ts and jar.stat().st_mtime + 1.0 < src_newest_ts:
        return {"verdict": "FAIL", "bytes": size, "libs": libs,
                "reason": "产物比源码旧：jar mtime %s < 最新源码 %s %s" % (
                    time.strftime("%H:%M:%S", time.localtime(jar.stat().st_mtime)),
                    src_newest,
                    time.strftime("%H:%M:%S", time.localtime(src_newest_ts))),
                "remedy": "python _test/build_jar.py"}
    return {"verdict": "PASS", "bytes": size, "libs": libs, "reason": ""}


def run_real():
    newest, ts = newest_source()
    r = inspect(JAR, ts, newest)
    if r["verdict"] == "PASS":
        print("JAR-SHAPE-PASS: fat=%d libs=%d bytes ｜ 产物新于源码（最新源码 %s）" % (r["bytes"], r["libs"], newest))
        return 0
    if r["verdict"] == "SKIP":
        print("JAR-SHAPE-SKIP: %s ｜ 本轮该面未验证（不印 PASS，也不算通过）" % r["reason"])
        return 0
    print("JAR-SHAPE-FAIL: %s ｜ 产物 %s（bytes=%s libs=%s）｜ 最新源码 %s" % (
        r["reason"], JAR, r.get("bytes"), r.get("libs"), newest))
    if r.get("remedy"):
        print("  处置: %s" % r["remedy"])
    return 1


def selftest_result():
    """夹具面的**无印版**：返回 (rc, ok, total, 首条失败原因)。

    分出来是为了让调用方（`server_preflight`）能把读数折进它自己的收口行 ——
    电池聚合器按宽度截断每套件最后一行，长行尾部的数字等于没写（r70 实测被截在"（"处）。
    """
    import tempfile
    ok, fails = 0, []
    with tempfile.TemporaryDirectory() as td:
        t = Path(td)

        def mk(path, fat=True, libs=2):
            with zipfile.ZipFile(path, "w") as z:
                mf = ("Main-Class: org.springframework.boot.loader.launch.JarLauncher\r\n"
                      "Start-Class: com.xinyu.soulisle.SoulIsleApplication\r\n") if fat else "Manifest-Version: 1.0\r\n"
                z.writestr("META-INF/MANIFEST.MF", mf)
                for i in range(libs if fat else 0):
                    z.writestr("BOOT-INF/lib/dep%d.jar" % i, "x" * 40 if fat else "")
            return path

        fat = mk(t / "fat.jar")
        if inspect(fat, 0.0, min_bytes=100)["verdict"] != "PASS":
            fails.append("正例 fat 被误判：%s" % inspect(fat, 0.0, min_bytes=100))
        else:
            ok += 1

        thin = mk(t / "thin.jar", fat=False)
        r = inspect(thin, 0.0)
        if r["verdict"] != "FAIL" or "thin" not in r["reason"]:
            fails.append("反例 thin 未咬（%s）" % r)
        else:
            ok += 1

        nolibs = mk(t / "nolibs.jar", fat=True, libs=0)
        r = inspect(nolibs, 0.0)
        if r["verdict"] != "FAIL" or "BOOT-INF/lib" not in r["reason"]:
            fails.append("反例 fat-但零依赖未咬（%s）" % r)
        else:
            ok += 1

        stale = mk(t / "stale.jar")
        os.utime(stale, (time.time() - 3600, time.time() - 3600))
        r = inspect(stale, time.time(), "Newest.java", min_bytes=100)
        if r["verdict"] != "FAIL" or "比源码旧" not in r["reason"]:
            fails.append("反例 陈旧产物未咬（%s）" % r)
        else:
            ok += 1

        r = inspect(t / "absent.jar", 0.0)
        if r["verdict"] != "SKIP" or not r["reason"]:
            fails.append("反例 缺产物被折叠成 PASS/FAIL（%s）" % r)
        else:
            ok += 1
    total = 5
    rc = 0 if not fails else 1
    return rc, ok, total, (fails[0] if fails else "")


def selftest():
    rc, ok, total, why = selftest_result()
    if rc:
        print("JAR-SHAPE-SELFTEST-FAIL（%d/%d）：%s" % (ok, total, why))
        return 1
    print("JAR-SHAPE-SELFTEST-PASS（%d/%d 类夹具：fat 正例 / thin / 零依赖 / 陈旧 / 缺产物三态）" % (ok, total))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    return selftest() if a.selftest else run_real()


if __name__ == "__main__":
    sys.exit(main())
