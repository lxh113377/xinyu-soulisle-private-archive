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
  PASS       产物在、是 fat（新鲜度另报 `fresh=ok|unverified`，见下）
  FAIL       产物在、但 thin（缺 JarLauncher / BOOT-INF/lib 为空），或**产物内容比 git 面旧**
  SKIP       产物不在（clean clone / CI 的无构建 job）⇒ 如实印 UNVERIFIED 原因，不印 PASS

新鲜度口径（r99c 换掉 mtime）：旧写法 `jar.mtime < 最新源码.mtime ⇒ FAIL` 在同一天同一份代码的
两次 CI 运行里一次红一次绿（runner 上 checkout 与 cache 还原各写一套时间），比的是"文件怎么搬来的"
而不是代码新旧。现改为两条任何机器都同值的判据：
  (A) jar 内 `BOOT-INF/classes/<资源>` 的 SHA256 ⇄ git 跟踪的 `server/src/main/resources/<同名>`
  (B) jar `META-INF/MANIFEST.MF` 的 `Implementation-Version` ⇄ `server/pom.xml` 工程版本
java 源码（编译件）无法从产物侧证明新鲜 ⇒ 该面如实留 advisory，补法（构建时写 stamp）在 r100。
"""
import argparse
import hashlib
import os
import re
import subprocess
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JAR = ROOT / "server" / "target" / "soulisle-server.jar"
MIN_FAT_BYTES = 20_000_000          # 实测 fat=28,446,595 B；thin=56,728 B（两者差 500 倍，取中间量不致误判）
SRC_ROOTS = ("server/src/main", "server/pom.xml")
RES_DIR = "server/src/main/resources"
RES_IN_JAR = "BOOT-INF/classes/"


def tracked_resources(root=ROOT):
    """git 跟踪的 `server/src/main/resources/*` 文件名。取不到 git ⇒ 返回 None（未验，不判红）。"""
    r = subprocess.run(["git", "-C", str(root), "ls-files", "--", RES_DIR],
                       capture_output=True, timeout=60)
    if r.returncode != 0:
        return None
    names = [l.strip().split("/")[-1] for l in
             (r.stdout or b"").decode("utf-8", "replace").splitlines() if l.strip()]
    return sorted(names)


def pom_version(root=ROOT):
    """`server/pom.xml` 的**工程自身**版本（先剥掉 <parent> 段再取第一个 <version>）。

    实测：不剥 parent 会先命中 `<parent>...<version>3.2.5</version>`（Spring Boot 的版本），
    而工程版本是 1.8.1 ⇒ 拿它当权威会把每条版本对账都做成假红。
    """
    try:
        txt = (root / "server" / "pom.xml").read_text("utf-8", errors="replace")
    except OSError:
        return ""
    stripped = re.sub(r"<parent>.*?</parent>", "", txt, flags=re.S)
    m = re.search(r"<version>\s*([^<\s]+)\s*</version>", stripped)
    return m.group(1) if m else ""


def manifest_version(mf_text):
    m = re.search(r"^Implementation-Version:\s*(\S+)", mf_text or "", flags=re.M)
    return m.group(1) if m else ""


def freshness_pair(jar_path, mf_text, root=ROOT, rels=None):
    """产物 ⇄ git 面的**可比字节 / 可比版本**。返回 (state, detail, remedy)。

    state ∈ ok / fail / unverified。为什么换掉 mtime（r99c 一手）：
    `jar mtime < 源码 mtime` 这条腿在同一天、同一份代码的两次 CI 运行里
    一次 `PREFLIGHT-FAIL: jar mtime 00:00:00 < 最新源码 17:03:06`、一次 `PREFLIGHT-PASS`
    ⇒ 它比的是**文件怎么被搬到那台机器上的**（checkout / cache 还原各写一套时间），
    不是代码新旧。资源字节与版本号两端都由 git 决定，任何机器同值。

    `rels` 是包内 seam（不新建文件、不 mock git）：selftest 传夹具清单即可跑通 ok/fail 两侧，
    生产路径留 None ⇒ 由 `tracked_resources(root)` 现读。
    """
    if rels is None:
        rels = tracked_resources(root)
        if rels is None:
            return "unverified", "资源清单取不到（无 git）", ""
    bad = []
    with zipfile.ZipFile(jar_path) as z:
        names = set(z.namelist())
        for name in rels:
            ent = RES_IN_JAR + name
            if ent not in names:
                bad.append("%s(jar 内无此件)" % name)
                continue
            src = root / RES_DIR / name
            if not src.is_file():
                bad.append("%s(git 在册而盘上无件)" % name)
                continue
            want = hashlib.sha256(src.read_bytes()).hexdigest()
            got = hashlib.sha256(z.read(ent)).hexdigest()
            if want != got:
                bad.append(name)
    if bad:
        return "fail", "资源比产物新：%s" % ",".join(bad), "python _test/build_jar.py"
    pv, jv = pom_version(root), manifest_version(mf_text)
    if not pv or not jv:
        return "unverified", "版本取不到 pom=%s jar=%s" % (pv or "-", jv or "-"), ""
    if pv != jv:
        return "fail", "版本不一致：pom=%s jar Implementation-Version=%s" % (pv, jv), \
            "python _test/build_jar.py（或按发布流程切版）"
    return "ok", "资源 %d 件 SHA256 等值｜版本 pom=jar=%s" % (len(rels), pv), ""


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


def inspect(jar_path, src_newest_ts=0.0, src_newest="", min_bytes=MIN_FAT_BYTES,
            root=ROOT, rels=None):
    """纯判定：返回 dict(verdict, reason, facts..., fresh, fresh_detail)。verdict ∈ PASS/FAIL/SKIP。"""
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
    # 新鲜度：**不再比 mtime**（r99c）。mtime 由"文件怎么被搬到这台机器上"决定，
    # 同码同天在 CI 上红绿各一次即证据。旧的 src_newest_ts/src_newest 只留作提示文本。
    try:
        state, detail, remedy = freshness_pair(jar, mf, root, rels)
    except (OSError, zipfile.BadZipFile) as e:                # noqa: BLE001
        state, detail, remedy = "unverified", "新鲜度取数失败(%s)" % type(e).__name__, ""
    out = {"verdict": "PASS", "bytes": size, "libs": libs, "reason": "",
           "fresh": state, "fresh_detail": detail,
           "mtime_note": "机器局域量，不参与判定"}
    if state == "fail":
        out.update({"verdict": "FAIL", "reason": detail, "remedy": remedy})
    return out


def run_real():
    newest, ts = newest_source()
    r = inspect(JAR, ts, newest)
    if r["verdict"] == "PASS":
        print("JAR-SHAPE-PASS: fat=%d libs=%d bytes ｜ 新鲜度=%s（%s）｜ mtime 提示：最新源码 %s（机器局域量，不参与判定）"
              % (r["bytes"], r["libs"], r["fresh"], r["fresh_detail"], newest))
        return 0
    if r["verdict"] == "SKIP":
        print("JAR-SHAPE-SKIP: %s ｜ 本轮该面未验证（不印 PASS，也不算通过）" % r["reason"])
        return 0
    print("JAR-SHAPE-FAIL: %s ｜ 产物 %s（bytes=%s libs=%s fresh=%s）｜ 新鲜度明细 %s" % (
        r["reason"], JAR, r.get("bytes"), r.get("libs"), r.get("fresh"), r.get("fresh_detail")))
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
        # 三枚形状夹具只判"是不是 fat"，不参与新鲜度 ⇒ `rels=()` 显式声明"这轮没有资源要核"，
        # 新鲜度落在 unverified（不是 ok，也不是红）。
        if inspect(fat, 0.0, min_bytes=100, rels=())["verdict"] != "PASS":
            fails.append("正例 fat 被误判：%s" % inspect(fat, 0.0, min_bytes=100, rels=()))
        else:
            ok += 1

        thin = mk(t / "thin.jar", fat=False)
        r = inspect(thin, 0.0, rels=())
        if r["verdict"] != "FAIL" or "thin" not in r["reason"]:
            fails.append("反例 thin 未咬（%s）" % r)
        else:
            ok += 1

        nolibs = mk(t / "nolibs.jar", fat=True, libs=0)
        r = inspect(nolibs, 0.0, rels=())
        if r["verdict"] != "FAIL" or "BOOT-INF/lib" not in r["reason"]:
            fails.append("反例 fat-但零依赖未咬（%s）" % r)
        else:
            ok += 1

        # ── r99c：新鲜度从 mtime 换成「产物内可比字节 + 版本号」，反例逐条重写 ──
        SCHEMA = b"CREATE TABLE chat_message (id BIGINT PRIMARY KEY);\n"
        fake = t / "fakeroot"
        (fake / RES_DIR).mkdir(parents=True)
        (fake / RES_DIR / "schema.sql").write_bytes(SCHEMA)
        # pom 里故意带 <parent> 段：不剥 parent 会先命中 Spring Boot 的 3.2.5（实测的假红来源）
        (fake / "server" / "pom.xml").write_text(
            "<project><parent><artifactId>spring-boot-starter-parent</artifactId>"
            "<version>3.2.5</version></parent>"
            "<artifactId>soulisle-server</artifactId><version>1.8.1</version></project>",
            encoding="utf-8")

        def mkjar(name, res=SCHEMA, ver="1.8.1"):
            p = t / name
            with zipfile.ZipFile(p, "w") as z:
                z.writestr("META-INF/MANIFEST.MF",
                           "Implementation-Title: soulisle-server\r\n"
                           "Implementation-Version: %s\r\n"
                           "Main-Class: org.springframework.boot.loader.launch.JarLauncher\r\n"
                           "Start-Class: com.xinyu.soulisle.SoulIsleApplication\r\n" % ver)
                z.writestr("BOOT-INF/lib/dep0.jar", "x" * 40)
                if res is not None:
                    z.writestr(RES_IN_JAR + "schema.sql", res)
            return p

        def check(label, cond):
            nonlocal ok
            if cond:
                ok += 1
            else:
                fails.append(label)

        check("pom 版本解析要剥 <parent>（否则读到 Spring Boot 的 3.2.5 造成假红）",
              pom_version(fake) == "1.8.1")
        r = inspect(mkjar("fresh.jar"), 0.0, min_bytes=10, root=fake, rels=["schema.sql"])
        check("正例 资源字节等值 + 版本一致 ⇒ PASS 且 fresh=ok（%s）" % r,
              r["verdict"] == "PASS" and r["fresh"] == "ok")
        r = inspect(mkjar("oldres.jar", res=b"-- stale schema --\n"), 0.0, min_bytes=10,
                    root=fake, rels=["schema.sql"])
        check("反例 资源比产物新 ⇒ FAIL 并点名 schema.sql（%s）" % r,
              r["verdict"] == "FAIL" and "schema.sql" in r["reason"])
        r = inspect(mkjar("oldver.jar", ver="1.8.0"), 0.0, min_bytes=10, root=fake,
                    rels=["schema.sql"])
        check("反例 jar 版本 1.8.0 而 pom 1.8.1 ⇒ FAIL（%s）" % r,
              r["verdict"] == "FAIL" and "版本不一致" in r["reason"])
        r = inspect(mkjar("nores.jar", res=None), 0.0, min_bytes=10, root=fake,
                    rels=["schema.sql"])
        check("反例 jar 内缺该资源件 ⇒ FAIL 并标「jar 内无此件」（不许读成没东西要核）（%s）" % r,
              r["verdict"] == "FAIL" and "jar 内无此件" in r["reason"])
        stale = mkjar("mtime-stale.jar")
        os.utime(stale, (time.time() - 3600, time.time() - 3600))
        r = inspect(stale, time.time(), "Newest.java", min_bytes=10, root=fake,
                    rels=["schema.sql"])
        check("回归钉 jar 的 mtime 早于源码 ⇒ 必须仍 PASS（今天 CI 那条假红的原形）（%s）" % r,
              r["verdict"] == "PASS" and "机器局域量" in r.get("mtime_note", ""))
        r = inspect(mkjar("nogit.jar"), 0.0, min_bytes=10, root=fake)
        check("未验态 取不到 git 资源清单 ⇒ fresh=unverified（既不折成 ok 也不冒判红）（%s）" % r,
              r["verdict"] == "PASS" and r["fresh"] == "unverified")
        real = inspect(JAR) if JAR.is_file() else {"verdict": "SKIP", "fresh": ""}
        check("真面 jar 的新鲜度读数存在且三态之一（verdict=%s fresh=%s）"
              % (real["verdict"], real.get("fresh")),
              real["verdict"] in ("PASS", "FAIL", "SKIP")
              and (real["verdict"] != "PASS" or real.get("fresh") in ("ok", "unverified")))

        r = inspect(t / "absent.jar", 0.0)
        if r["verdict"] != "SKIP" or not r["reason"]:
            fails.append("反例 缺产物被折叠成 PASS/FAIL（%s）" % r)
        else:
            ok += 1
    # 分母**结构推导**，不再手抄常量（原来是 `total = 5`，我加 7 条腿它就报 11/5）：
    # 每条腿要么计入 ok、要么计入 fails，所以 total == ok + len(fails) 是恒等式而不是清单。
    total = ok + len(fails)
    if total <= 0:
        fails.append("零分母不得判绿（R247）：一条夹具腿都没跑到")
        total = len(fails)
    rc = 0 if not fails else 1
    return rc, ok, total, (fails[0] if fails else "")


def selftest():
    rc, ok, total, why = selftest_result()
    if rc:
        print("JAR-SHAPE-SELFTEST-FAIL（%d/%d）：%s" % (ok, total, why))
        return 1
    print("JAR-SHAPE-SELFTEST-PASS（%d/%d 类夹具：形态 4 + 新鲜度 7（含回归钉「mtime 早于源码必须仍绿」））"
          % (ok, total))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    return selftest() if a.selftest else run_real()


if __name__ == "__main__":
    sys.exit(main())
