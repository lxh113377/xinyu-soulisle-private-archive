"""心屿 · Dockerfile 磁盘级模拟验收（本机无 Docker 时的最强替代证据）

立此脚本的原因（2026-09-23）：原计划「装 Docker 后跑通镜像」，但实地探测发现本机装的是
**Docker Sandboxes**(`Docker.sbx`) —— 它没有 `docker` CLI、daemon 也起不来，且产品定位是
「给 AI agent 用的隔离沙箱」，**不是镜像构建器**。为了不空等，把 Dockerfile 在磁盘上
逐行模拟实现一遍：

    COPY  → 真实拷文件（并遵守 .dockerignore 的排除语义）
    ENV   → 真实注入进程环境
    WORKDIR → 真实作为 java 进程 cwd
    ENTRYPOINT → 真实执行

**关键：COPY/ENV 直接从 `server/Dockerfile` 解析，禁止手抄** —— 否则这份模拟会在
Dockerfile 改动后静默失效（模拟与真品脱钩 = 假证据）。

能证：镜像内文件是否齐全、路径/ENV 是否正确、静态页与 API 是否可用、**镜像内是否含密钥**。
不能证：base image 拉取、层缓存、ENTRYPOINT exec 形式、容器网络/端口映射 —— 这些仍需真 Docker。

用法：python _test/docker_image_sim_check.py            → 0 = DOCKER-SIM-PASS
      python _test/docker_image_sim_check.py --keep     → 保留模拟根目录以便人工翻查
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCKERFILE = ROOT / "server" / "Dockerfile"
DOCKERIGNORE = ROOT / ".dockerignore"
IMAGE_ROOT = "/app"          # 容器内工作目录，模拟时映射到临时根
PORT = 8126
KEY_RE = re.compile(r"sk-[A-Za-z0-9]{20,}")


def parse_dockerfile():
    """从 Dockerfile 提取 COPY 与 ENV —— 唯一真相源，禁止手抄。"""
    copies, envs, workdir = [], {}, "/"
    for raw in DOCKERFILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.upper().startswith("COPY "):
            parts = line.split()[1:]
            # 合并形如 `COPY a b c dest/` 的多源写法
            copies.append((parts[:-1], parts[-1]))
        elif line.upper().startswith("ENV "):
            for k, v in re.findall(r'(\w+)=("[^"]*"|\S+)', line[4:]):
                envs[k] = v.strip('"')
        elif line.upper().startswith("WORKDIR "):
            workdir = line.split(None, 1)[1].strip()
    return copies, envs, workdir


def parse_dockerignore():
    if not DOCKERIGNORE.is_file():
        return []
    out = []
    for raw in DOCKERIGNORE.read_text(encoding="utf-8").splitlines():
        s = raw.strip()
        if s and not s.startswith("#"):
            out.append(s)
    return out


def is_ignored(rel: str, patterns) -> bool:
    """简化版 .dockerignore 语义：只实现本仓库用到的形态（精确路径 / 目录名 / ** 前缀）。"""
    rel = rel.replace("\\", "/")
    for p in patterns:
        p = p.replace("\\", "/").rstrip("/")
        if p.startswith("**/"):
            if p[3:] in rel or rel.endswith(p[3:]):
                return True
        elif p in ("**/__pycache__", "**/*.pyc"):
            if rel.endswith(".pyc") or "/__pycache__/" in f"/{rel}":
                return True
        elif "/" in p:
            if rel == p:
                return True
        else:
            if rel == p or rel.startswith(p + "/") or f"/{p}/" in f"/{rel}/":
                return True
    return False


def pick_java():
    """探测 JDK >= 17 —— 不能信任 JAVA_HOME（本机默认是 JDK 8）。"""
    cands = []
    if os.environ.get("JAVA_HOME"):
        cands.append(Path(os.environ["JAVA_HOME"]) / "bin" / "java.exe")
    cands.append(Path("C:/Program Files/Eclipse Adoptium/jdk-17.0.20.101-hotspot/bin/java.exe"))
    for base in (Path("C:/Program Files/Eclipse Adoptium"), Path("C:/Program Files/Java")):
        if base.is_dir():
            cands += sorted(base.glob("jdk-17*/bin/java.exe"))
    cands.append(Path(shutil.which("java") or "/nonexistent"))
    for c in cands:
        if not c.is_file():
            continue
        try:
            out = subprocess.run([str(c), "-version"], capture_output=True, text=True,
                                 timeout=20).stderr
        except Exception:
            continue
        m = re.search(r'version "(\d+)', out)
        if m and int(m.group(1)) >= 17:
            return c
    return None


def scan_keys(root: Path):
    """扫描目录下的真实 Key 形态，返回命中文件（相对路径）列表。"""
    hits = []
    for f in root.rglob("*"):
        if f.is_file() and f.stat().st_size < 40 * 1024 * 1024:
            try:
                if KEY_RE.search(f.read_bytes().decode("utf-8", "replace")):
                    hits.append(str(f.relative_to(root)))
            except Exception:
                pass
    return hits


def selftest() -> int:
    """隔离桩：证明「密钥扫描」判据既不恒真也不恒假。

    背景（2026-09-23 实证）：当天已因 PowerShell 别名覆盖导致哈希比较全取 null、
    8 个文件全报 SAME 的假通过。凡「0 命中即通过」类判据，必须附隔离桩。
    """
    tmp = Path(tempfile.mkdtemp(prefix="xinyu_keyscan_selftest_"))
    try:
        (tmp / "clean.txt").write_text("心屿 SoulIsle 正常文本，不含密钥", encoding="utf-8")
        nested = tmp / "nested"
        nested.mkdir()
        (nested / "leak.js").write_text('var k = "sk-' + "a" * 32 + '";', encoding="utf-8")

        hits = scan_keys(tmp)
        print(f"隔离桩：注入 1 处密钥 + 1 个干净文件 -> 命中 {len(hits)} 处 {hits}")
        ok = len(hits) == 1 and hits[0].endswith("leak.js")
        if not ok:
            # 反例：清掉泄漏文件后必须回到 0（证明不是恒真/恒假）
            (nested / "leak.js").unlink()
            clean_hits = scan_keys(tmp)
            print(f"隔离桩反例：移除泄漏文件后命中 {len(clean_hits)} 处")
            ok = len(clean_hits) == 0 and len(hits) == 1
        print("DOCKER-SIM-SELFTEST-PASS" if ok else "DOCKER-SIM-SELFTEST-FAIL")
        return 0 if ok else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()

    fails = []

    if not DOCKERFILE.is_file():
        print("DOCKER-SIM-FAIL: 找不到 server/Dockerfile")
        return 1
    copies, envs, workdir = parse_dockerfile()
    ignores = parse_dockerignore()
    print(f"[解析] Dockerfile: COPY×{len(copies)} ENV×{len(envs)} WORKDIR={workdir}")
    if len(copies) < 3:
        fails.append(f"COPY 解析可疑（只拿到 {len(copies)} 条），模拟结论不可信")
    if not envs:
        fails.append("ENV 一条都没解析到，模拟结论不可信")

    java = pick_java()
    if not java:
        print("DOCKER-SIM-FAIL: 本机找不到 JDK >= 17")
        return 1
    print(f"[JDK ] {java}")

    keep = "--keep" in sys.argv
    tmp = Path(tempfile.mkdtemp(prefix="xinyu_imagesim_"))
    try:
        # ---- 1) 执行 COPY（含 .dockerignore 语义）----
        src_count = 0
        for srcs, dst in copies:
            if len(srcs) != 1:
                fails.append(f"多源 COPY 未支持，请人工核对: {srcs} -> {dst}")
                continue
            src = ROOT / srcs[0]
            rel_dst = dst[len(IMAGE_ROOT):].lstrip("/") if dst.startswith(IMAGE_ROOT) else dst.lstrip("/")
            target = tmp / rel_dst
            if not src.exists():
                fails.append(f"COPY 源不存在: {srcs[0]}")
                continue
            if src.is_dir() or srcs[0].endswith("/"):
                for f in src.rglob("*"):
                    if not f.is_file():
                        continue
                    rel_from_src = f.relative_to(src).as_posix()
                    if is_ignored(f"{srcs[0].rstrip('/')}/{rel_from_src}", ignores):
                        continue
                    out = target / rel_from_src
                    out.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(f, out)
                    src_count += 1
            else:
                if is_ignored(srcs[0], ignores):
                    print(f"  (被 .dockerignore 排除) {srcs[0]}")
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, target)
                src_count += 1
        print(f"[COPY] 共写入 {src_count} 个文件 -> {tmp}")
        if src_count < 3:
            fails.append(f"COPY 只写入 {src_count} 个文件，输入可疑")

        # ---- 2) 镜像内容物断言（不依赖运行）----
        web = tmp / "web"
        for need in ("index.html", "js/app.js", "js/emotion-engine.js", "vendor/three.min.js", "css/style.css"):
            if not (web / need).is_file():
                fails.append(f"镜像内缺前端文件: web/{need}")
        if not (tmp / "app.jar").is_file():
            fails.append("镜像内缺 app.jar")
        ds = tmp / "_test" / "emotion-eval-dataset.json"
        if not ds.is_file():
            fails.append("镜像内缺评测集")
        else:
            n = len(json.loads(ds.read_text(encoding="utf-8"))["items"])
            print(f"[内容] 评测集 {n} 条")
            if n < 60:
                fails.append(f"镜像内评测集只有 {n} 条（应为 73）")

        # ---- 3) 镜像内密钥扫描（红线）----
        hits = scan_keys(tmp)
        print(f"[红线] 镜像内 sk- 命中: {len(hits)}  {hits[:3]}")
        if hits:
            fails.append(f"红线：镜像内含真实 Key -> {hits[:3]}")

        # ---- 4) 真实运行（ENV / WORKDIR / ENTRYPOINT）----
        run_env = os.environ.copy()
        for k, v in envs.items():
            run_env[k] = v.replace(IMAGE_ROOT, str(tmp))
        # 模拟 docker run -e DEEPSEEK_KEY=... 给一个假 key，避免回落离线影响断言
        run_env.setdefault("DEEPSEEK_KEY", "")

        # WORKDIR 映射：`/app` 本身 = 临时根，`/app/x` = tmp/x
        sub = workdir[len(IMAGE_ROOT):].lstrip("/") if workdir.startswith(IMAGE_ROOT) else workdir.lstrip("/")
        work_cwd = tmp / sub if sub else tmp
        work_cwd.mkdir(parents=True, exist_ok=True)
        print(f"[WORK] cwd={work_cwd}")

        proc = subprocess.Popen(
            [str(java), "-jar", str(tmp / "app.jar"), f"--server.port={PORT}"],
            cwd=str(work_cwd), env=run_env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            encoding="utf-8", errors="replace",
        )
        try:
            base = f"http://127.0.0.1:{PORT}"
            health = None
            for _ in range(60):
                if proc.poll() is not None:
                    break
                try:
                    with urllib.request.urlopen(base + "/api/health", timeout=3) as r:
                        health = json.loads(r.read().decode("utf-8"))
                    break
                except Exception:
                    time.sleep(1)
            if not health:
                out = proc.stdout.read() if proc.stdout else ""
                fails.append("服务未就绪（复现镜像启动失败）。最后 800 字日志:\n" + out[-800:])
            else:
                print(f"[健康] {json.dumps(health, ensure_ascii=False)}")
                if health.get("status") != "UP":
                    fails.append("health.status != UP")
                for k in ("indexFound", "vendorFound"):
                    if not health.get(k):
                        fails.append(f"health.{k} != true")
                if str(tmp) not in health.get("webRoot", "") and IMAGE_ROOT not in health.get("webRoot", ""):
                    fails.append(f"webRoot 未指向镜像内前端: {health.get('webRoot')}")

                for path in ("/", "/js/app.js", "/vendor/three.min.js", "/css/style.css"):
                    try:
                        with urllib.request.urlopen(base + path, timeout=10) as r:
                            code, ln = r.status, len(r.read())
                    except urllib.error.HTTPError as e:
                        code, ln = e.code, 0
                    print(f"[静态] {code} {path} ({ln}B)")
                    if code != 200:
                        fails.append(f"静态资源非 200: {path} -> {code}")

                try:
                    with urllib.request.urlopen(base + "/api/emotion/eval", timeout=60) as r:
                        ev = json.loads(r.read().decode("utf-8"))
                    print(f"[评测] {ev.get('total')} 条 / {ev.get('accuracy')} / 危机 {ev.get('crisis_recall')}")
                    if ev.get("total") != 73 or ev.get("accuracy") != "98.6%":
                        fails.append(f"镜像内评测指标异常: {ev.get('total')} / {ev.get('accuracy')}")
                except Exception as exc:  # noqa: BLE001
                    fails.append(f"/api/emotion/eval 失败: {exc}")
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
    finally:
        if keep:
            print(f"[保留] 模拟根目录: {tmp}")
        else:
            shutil.rmtree(tmp, ignore_errors=True)

    print()
    if fails:
        print("DOCKER-SIM-FAIL")
        for f in fails:
            print("  -", f)
        return 1
    print("DOCKER-SIM-PASS  (Dockerfile 的 COPY/ENV/WORKDIR/ENTRYPOINT 在磁盘上等价实现后全部通过)")
    print("注意：这不等于 docker build 已验证 —— 基础镜像、层缓存、容器网络仍需真 Docker。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
