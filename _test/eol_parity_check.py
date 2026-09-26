# -*- coding: utf-8 -*-
"""行尾确定性判据（对标轮 r36 新增）—— 让"逐字节对账"类主张在任何机器上成立。

为什么要有它（r36 一手实测，两条都是本轮自己踩的）：
 1. `.gitattributes` 原先只钉 `*.sh eol=lf` + `* text=auto`，而本机 `core.autocrlf=true`
    ⇒ **108 个被跟踪文件的工作树字节 ≠ 仓库 blob 字节**（工作树 CRLF / blob LF）。
    公网 `js/app.js` 实测 13,698B 含 249 个 CR，而 clone 后检出只有 13,449B
    ⇒ `live_sync`（线上==权威源逐字节）、`deploy_sync`（SHA256 双向比对）、`size_budget`（字节预算）、
    成片 sha256 台账 这一族主张**只在 Windows 成立**，外人复算不出来。
    参照池 16 仓实测 `.gitattributes` 为 6/16 有 —— 所以这条不是"别人有我也要有"，
    而是"我们自己声明了字节级一致，就必须让它与机器无关"。
 2. 归一化时把二进制也当文本处理，PNG 里的 `0D 0A` 被当换行删掉（实测 20 个文件被削 1~2B），
    而"两侧同法归一再比较"的守卫**看不出来**（两侧都被削 ⇒ 恒等自比，R220 同族）。
    ⇒ 必须有 E3：工作树含 `0D0A` 的被跟踪文件必须被 git 判为 binary，否则判红。

判据（逐项独立，全绿才 PASS）：
  E1 策略在册：`.gitattributes` 存在；文本侧含 `eol=lf`；二进制侧有显式 `binary` 声明
  E2 检出无关：每个 text 类被跟踪文件 —— 工作树字节与其 HEAD blob 字节完全相等，
     且两侧都不含 CRLF（同时覆盖"本机工作树"与"外人 clone"两种形态）
  E3 二进制不漏 declare：工作树含 `0D0A` 的被跟踪文件必须被 git 判为 binary
  E4 分母自证：`text + binary == total`；取不到 git 或跟踪清单为空 ⇒ rc=2（ENV-UNVERIFIED），不得判绿

用法：python _test/eol_parity_check.py [--selftest]
"""
import pathlib
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = pathlib.Path(__file__).resolve().parents[1]
NUL = bytes([0])


def git_z(*args):
    out = subprocess.run(["git", "-c", "core.quotepath=off"] + list(args) + ["-z"],
                         capture_output=True, cwd=str(ROOT), check=True).stdout
    return [x.decode("utf-8") for x in out.split(NUL) if x]


def blob_of(rel):
    """"检出时应得的字节" = 索引里的 blob（`git show :path`），不是 HEAD。

    为什么不能用 HEAD：本轮 `--selftest` 首跑就把自己判红了 —— `.gitattributes` 与刷新后的台账
    是**已暂存的内容改动**，拿 HEAD 比必然不等 ⇒ 判据把在途改动当成缺陷（假红）。
    索引才是"下一次 clone 会拿到的字节"；取不到索引再退 HEAD（干净工作树两者相同）。
    """
    staged = subprocess.run(["git", "show", ":" + rel], capture_output=True, cwd=str(ROOT)).stdout
    if staged:
        return staged
    return subprocess.run(["git", "show", "HEAD:" + rel], capture_output=True,
                          cwd=str(ROOT)).stdout


def is_binary(rel):
    """按 git 自己的判定（属性 + 内容探测），不靠猜扩展名。"""
    out = subprocess.run(["git", "check-attr", "binary", "--", rel], capture_output=True,
                         text=True, cwd=str(ROOT)).stdout
    return out.strip().endswith(": binary: set")


def audit(paths, reader=None, bin_check=None, blob_reader=None, dirty=None):
    """纯函数主体：返回 (问题清单, 统计字典)。

    reader / bin_check / blob_reader / dirty 四项都必须可注入 —— `--selftest` 造的样本名不在索引里，
    走真的 `git check-attr` / `git show` 只会拿到 unspecified 与空字节，那测的是夹具不是判据。

    ⚠️ 等价判定只作用于**未修改**的文件（r35 判据首跑即自判红两处，就是漏了这一层）：
    "工作树字节 == 仓库侧字节" 问的是「检出与机器无关」，而一次正常的编辑当然会让两者不等。
    所以编辑中的文件只查两侧**都不含 CRLF**（这才是字节级主张的要害），不查相等。
    """
    read = reader or (lambda rel: (ROOT / rel).read_bytes() if (ROOT / rel).is_file() else None)
    binlike = bin_check or is_binary
    blobs = blob_reader or blob_of
    dirty = dirty or set()
    bad, n_text, n_bin = [], 0, 0
    for rel in paths:
        wt = read(rel)
        if wt is None:
            bad.append("%s 取不到工作树字节（分母在漏）" % rel)
            continue
        if binlike(rel):
            n_bin += 1
            continue
        n_text += 1
        blob = blobs(rel)
        if b"\r\n" in wt:
            bad.append("工作树含 CRLF：%s" % rel)
        if b"\r\n" in blob:
            bad.append("仓库侧 blob 含 CRLF（外人 clone 会拿到不同字节）：%s" % rel)
        if rel not in dirty and wt != blob:
            bad.append("工作树字节 != blob 字节（且该文件没有待提交改动）：%s" % rel)
    return bad, {"text": n_text, "binary": n_bin, "total": len(paths)}


def selftest() -> int:
    """判据非恒真自证：该红的必须红、该放行的必须放行、零输入不得判绿。"""
    bad = []

    def fake_bin(rel):
        return rel.endswith(".png")                    # 只有 .png 被"声明"为 binary

    def reader_with(payloads):
        return lambda rel: payloads[rel][0]            # (工作树字节, 仓库侧字节)

    def blob_with(payloads):
        return lambda rel: payloads[rel][1]

    PNG_HEAD = b"\x89PNG\r\n\x1a\n"                    # 真 PNG 头部就含 0D0A
    cases = [
        ("LF 文本，blob 也是 LF（合规）",
         {"a.md": (b"x\ny\n", b"x\ny\n")}, []),
        ("工作树含 CRLF 而 blob 是 LF（本机恒绿、CI 恒红那一族的形状）",
         {"a.md": (b"x\r\ny\r\n", b"x\ny\n")}, ["a.md"]),
        ("声明 binary 且含 0D0A（PNG 必须放行，一个字节都不许动）",
         {"a.png": (PNG_HEAD, PNG_HEAD)}, []),
        ("含 0D0A 却未声明 binary（E3 点名 —— 本轮 PNG 被削 1~2B 那次的封口）",
         {"a.bin": (PNG_HEAD, PNG_HEAD)}, ["a.bin"]),
        ("声明 binary 但不含 0D0A（必须放行：不得要求二进制含 CRLF）",
         {"b.png": (b"\x89PNG\x1a\n\x00\x01", b"\x89PNG\x1a\n\x00\x01")}, []),
        ("仓库侧 blob 含 CRLF 而工作树是 LF（外人 clone 会拿到不同字节，必须点名）",
         {"c.md": (b"x\ny\n", b"x\r\ny\r\n")}, ["c.md"]),
        # 正在编辑的文件：内容本就与仓库侧不等，属正常在途改动 ⇒ 不得判红
        # （r36 首跑就被这条误判：README 与 run_all_suites 当时都在我手里改着）
        ("在途改动的文本（两侧皆 LF、内容不等）必须放行",
         {"d.md": (b"new\n", b"old\n")}, []),
        ("在途改动但工作树带 CRLF ⇒ 仍必须点名（脏不是免检理由）",
         {"e.md": (b"new\r\n", b"old\n")}, ["e.md"]),
    ]
    for name, payloads, expect in cases:
        dirty = {k for k, (wt, bl) in payloads.items() if wt != bl}
        e2, st = audit(list(payloads), reader_with(payloads), fake_bin,
                       blob_with(payloads), dirty)
        hit = [x for x in expect if any(x in m for m in e2)]
        if expect and len(hit) != len(expect):
            bad.append("违规样本漏报：%s -> %s" % (name, e2[:1]))
        if not expect and e2:
            bad.append("合规样本被误判：%s -> %s" % (name, e2[:1]))
        if st["text"] + st["binary"] != st["total"]:
            bad.append("分母不闭合：%s" % name)
    _, st0 = audit([], reader_with({}), fake_bin)
    if st0["total"] != 0:
        bad.append("零输入却算出非零分母")
    if bad:
        print("EOL-PARITY-SELFTEST-FAIL: " + " ; ".join(bad))
        return 1
    print("EOL-PARITY-SELFTEST-PASS: %d 类样本各归各位（合规文本放行 / 工作树 CRLF 判红 / "
          "binary 的 0D0A 放行与不要求 / 未声明 binary 的 0D0A 判红 / 仓库侧 CRLF 判红）"
          "+ 零输入分母为 0" % len(cases))
    return 0


def main() -> int:
    try:
        paths = git_z("ls-files")
    except (subprocess.SubprocessError, OSError) as err:
        print("EOL-PARITY-ENV: 取不到 git 跟踪清单（%s）⇒ 不判绿" % type(err).__name__)
        return 2
    if not paths:
        print("EOL-PARITY-ENV: git ls-files 返回 0 个文件 ⇒ 分母为空，不得据此判绿（R247）")
        return 2

    bad = []
    ga = ROOT / ".gitattributes"
    if not ga.is_file():
        bad.append("E1 缺 .gitattributes")
    else:
        txt = ga.read_text("utf-8", errors="replace")
        if "eol=lf" not in txt:
            bad.append("E1 .gitattributes 未钉 eol=lf（文本侧）")
        if "binary" not in txt:
            bad.append("E1 .gitattributes 无显式 binary 声明")

    dirty = set()
    for rec in git_z("status", "--porcelain"):
        code, rel = rec[:2], rec[3:]
        if code.strip() and code.strip() != "??":
            dirty.add(rel)                    # 有未提交内容改动：只查 CRLF，不查与仓库侧相等
    e2, st = audit(paths, dirty=dirty)
    bad += e2
    if st["text"] + st["binary"] != st["total"]:
        bad.append("E4 分母不闭合：text %d + binary %d != total %d"
                   % (st["text"], st["binary"], st["total"]))
    for line in bad:
        print("  FAIL", line)
    if bad:
        print("EOL-PARITY-FAIL: %d 项 ⇒ 「逐字节 / SHA256 / 字节预算」类主张在他人 clone 上不可复算" % len(bad))
        return 1
    print("EOL-PARITY-PASS（text=%d binary=%d total=%d；工作树字节 == blob 字节 ⇒ 与机器无关）"
          % (st["text"], st["binary"], st["total"]))
    return 0


if __name__ == "__main__":
    sys.exit(selftest() if "--selftest" in sys.argv[1:] else main())
