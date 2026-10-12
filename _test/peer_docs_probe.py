# -*- coding: utf-8 -*-
"""对标 r122 探针：**peers 的文档面**（八维表第 7 维此前 peers 侧一直写"本件不重采 ⇒ NA"）。

为什么补这一面：老大给的维度里明写「文档完善程度（API 文档 / 使用教程 / 贡献指南）」。
第 4 维在 r121 前也是同样的 NA，一代代抄到没人记得它是"没量过"而不是"对手差"——
本件就是把那一格换成可复算分母，口径与 `peer_perf_probe` 同族：**取数面单一、失明单列、不折算成零**。

取数面＝**一次 git tree**（含 blob size；复用 `peer_perf_probe.tree_entries`，不再开第二个取数口）。
四类位（对应老大原话的四项）：
  api_spec      openapi/swagger/proto/graphql schema —— "API 文档"
  guide         quickstart|getting-started|tutorial|how-to|usage|handbook —— "使用教程"
  contributing  CONTRIBUTING / DEVELOP / 贡献指南 —— "贡献指南"
  docs_site     docs/|documentation/|book/|wiki/ 目录在位（独立文档区，不是散在根目录的 md）
另带两个厚度读数（存在性≠质量）：root README 字节数、docs 目录内 md 文件数。

用法：python _test/peer_docs_probe.py [--json 交付物/对标数据/peer-docs-<date>.json]
      [--repo o/r[,o/r]] [--selftest] [--offline]
退出码：0=全 16 仓有结论（含 none 但取数面完整）1=有未验/失明 2=取数面整体不可用（无 gh/无网）
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from benchmark_metrics import PEERS                        # 分母唯一来源＝名册（不抄数字）
from peer_perf_probe import NOISE, tree_entries            # 取数面归口：只这一条通道

API_RX = re.compile(r"(^|/)(openapi|swagger)[\w.-]*\.(ya?ml|json)$|(^|/)(schema\.graphql|"
                    r"[\w.-]*\.proto|graphql\.graphql)$", re.I)
GUIDE_RX = re.compile(r"(quick[-_]?start|getting[-_]?started|tutorial|how[-_]?to|handbook|"
                      r"usage|walkthrough|user[-_]?guide|\u4f7f\u7528\u6559\u7a0b|\u5feb\u901f\u4e0a\u624b)", re.I)
CONTRIB_RX = re.compile(r"(^|/)(CONTRIBUTING|\u8d21\u732e|developer[-_]?guide|dev[-_]?guide|"
                        r"development)(\.[A-Za-z]+)?$", re.I)
DOCS_DIR_RX = re.compile(r"^(docs|documentation|doc|book|wiki|manual|guides)/", re.I)
README_RX = re.compile(r"^README(\.[A-Za-z]+)?$", re.I)


def classify_docs(paths_sizes):
    """纯函数：[(path, size)] → 四类位 + 厚度读数。噪声面（node_modules/dist/…）一律剔除。"""
    out = {"api_spec": 0, "guide": 0, "contributing": 0, "docs_site": 0,
           "readme_bytes": 0, "docs_md_files": 0}
    for p, sz in paths_sizes:
        if NOISE.search(p):
            continue
        base = p.rsplit("/", 1)[-1]
        if README_RX.match(base) and "/" not in p:
            out["readme_bytes"] = max(out["readme_bytes"], int(sz or 0))
        if API_RX.search(p):
            out["api_spec"] += 1
        if DOCS_DIR_RX.match(p) and base.lower().endswith((".md", ".rst", ".adoc", ".html")):
            out["docs_site"] = 1
        if DOCS_DIR_RX.match(p) and base.lower().endswith((".md", ".rst", ".adoc")):
            out["docs_md_files"] += 1
        # 口径边界（在册）：教程位按**文件名**判，self 与 peers 同一把尺。
        # 本仓的入门内容在 docs/README.md 的章节里、文件名不含 quickstart ⇒ 教程位如实为 0，
        # 这是真差距（没有独立 quickstart 文件），不给它开例外（开了就是口径特例撑出来的 4/4）。
        if GUIDE_RX.search(base) and not base.lower().endswith((".png", ".jpg", ".svg", ".gif")):
            out["guide"] += 1
        if CONTRIB_RX.search(base):
            out["contributing"] = 1
    return out


def shape(rec):
    """四类位 → 一句形态。只描述**在册面**，不做质量判断（字节数另列，别把"有"读成"好"）。"""
    n = sum(1 for k in ("api_spec", "guide", "contributing", "docs_site") if rec.get(k))
    return "%d/4" % n, n


def finalize(rec, blind):
    """失明优先：取数面残缺时结论一律 unverified，禁止把"看不见"写成 none。"""
    if blind:
        rec["blind"] = blind
        return "unverified(%s)" % blind
    return shape(rec)[0]


def probe(slug, token=""):
    rec = {"repo": slug}
    entries, trunc = tree_entries(slug, token)
    if trunc:
        rec["class"] = "unverified(truncated-tree)"
        rec["blind"] = "truncated-tree"
        return rec
    ps = [(e.get("path", ""), e.get("size") or 0) for e in entries if e.get("type") == "blob"]
    rec.update(classify_docs(ps))
    rec["path_count"] = len(ps)
    rec["class"] = finalize(rec, "")
    return rec


def self_only():
    """self 侧零网络，但**按 HEAD 面取数**（`git ls-tree -r -l HEAD`，size 就在这一列里）——
    与 peers 同面才可横比；工作树里有他人未提交的 docs 件，按工作树算会把在册面虚高。"""
    import subprocess
    root = Path(__file__).resolve().parents[1]
    # ⚠️ 一手踩坑（本轮当场抓到）：`--name-only` 会把 mode/type/size 列**一起吞掉**，
    #    按 `	` 切就每条都拿不到 path ⇒ entries 空 ⇒ self 判 0/4。
    #    那是"解析失败"冒充"没有文档"，正是本探针要防的那一类假零 ⇒ 用 `-r -l` 的完整列。
    r = subprocess.run(["git", "-c", "core.quotepath=false", "ls-tree", "-r", "-l", "HEAD"],
                       cwd=str(root), capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError("git ls-tree 失败 rc=%s：%s" % (r.returncode, (r.stderr or "")[:70]))
    entries = []
    for ln in (r.stdout or "").splitlines():
        meta, sep, path = ln.partition("	")
        if not sep or not path:
            continue
        cols = meta.split()
        if len(cols) < 4 or cols[1] != "blob":
            continue                        # 只要 blob（tree 条目没 size）
        size = cols[3]
        entries.append((path, -1 if size == "-" else int(size or 0)))
    if len(entries) < 100:
        raise RuntimeError("HEAD 面文件数取到 %d 条 ⇒ 解析或 git 输出异常，禁止折成「没有文档」" % len(entries))
    # **不预先缩面**：peers 拿的是整棵树，self 也必须拿整棵树（缩面＝给本仓挑跑道，两把尺）
    rec = classify_docs(entries)
    rec["repo"] = "self（心屿 MindIsle 本仓）"
    # ⚠️ 口径纪律：self 与 peers **共用 classify_docs 这一把尺**，不给本仓开例外。
    #    本仓的入门内容在 docs/README.md 的「快速开始」一章里，文件名不含 quickstart ⇒ 教程位=0。
    #    给它补判会让 self 从 3/4 变 4/4，而那条 4/4 是口径特例撑出来的，不是产物——
    #    真实差距（没有独立 quickstart 文件）反而被自己抹平（同一事实只许一处判、一把尺）。
    rec["class"] = shape(rec)[0]
    rec["face"] = "HEAD 面 git ls-tree -r HEAD（与 peers 同面）"
    return rec


def build_payload(rows, blind):
    """台账本体的**唯一构造点**（main 与契约腿共用）：抄两份就等于给形状坑留第二条路。

    声明位用 `na`（不是 blind_or_na）——`ledger_age_check.declared_na()` 只认顶层键
    ("blind","na","unverified")，认不出形状 ⇒ 整把龄期尺判 NA-UNKNOWN、rc=2 未验。
    r122 一手：我把键名写成 blind_or_na，龄期尺整体降档，而自己这侧门面照样印 PASS。
    """
    peers_rows = [r for r in rows if not str(r.get("repo", "")).startswith("self")]
    self_row = next((r for r in rows if str(r.get("repo", "")).startswith("self")), {})
    dist = {}
    for r in peers_rows:
        dist[str(r.get("class"))] = dist.get(str(r.get("class")), 0) + 1
    bits = {k: sum(1 for r in peers_rows if r.get(k))
            for k in ("api_spec", "guide", "contributing", "docs_site")}
    return {"generated_by": "_test/peer_docs_probe.py", "denominator": len(PEERS),
            "rows": rows, "na": blind, "class_dist": dist,
            "scope": "class_dist/bit_counts/na 只数 peers 行；self 单列 self_class",
            "self_class": self_row.get("class"), "bit_counts": bits,
            "note": "四类位＝API 规范 / 教程 / 贡献指南 / 独立文档区；"
                    "0/4 只在取数面完整时成立，失明一律单列 unverified 不折算成零",
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}


def shape_contract(payload):
    """**跨判据契约**：本探针的台账必须能被 `ledger_age_check.declared_na()` 认出形状。

    为什么由生产者来断：龄期尺是常驻判据，它把我这份台账认成 `NA-UNKNOWN` 时，红的是**整把尺**
    （rc=2 未验），而不是我这一族——r122 一手实测：键名写成 `blind_or_na` 后
    `declared_na()` 返回 (None,'unknown') ⇒ 17 族的龄期判据整体降档，而我自己的门面照样印 PASS。
    所以"我的输出符合下游判据的形状"必须在**我这侧**被断住，而不是等下一轮别人发现。
    取不到 ledger_age_check ⇒ 返回 None，由调用方判**未验**（禁静默放行）。
    """
    try:
        import ledger_age_check as LA
    except Exception as e:                                   # noqa: BLE001
        return (None, "ruler-unavailable(%s)" % type(e).__name__)
    return LA.shape_contract(payload)


def run_selftest():
    bad = []
    # 正向：四类位齐
    full = classify_docs([("README.md", 5000), ("openapi.yaml", 12), ("docs/quickstart.md", 9),
                          ("CONTRIBUTING.md", 7), ("docs/a.md", 3), ("src/app.ts", 1)])
    if not all(full[k] for k in ("api_spec", "guide", "contributing", "docs_site")):
        bad.append("四类位齐的样本被判缺：%s ⇒ 有文档的仓会被漏记（另一半就是假差距）" % full)
    if full["readme_bytes"] != 5000 or full["docs_md_files"] != 2:
        bad.append("厚度读数错：%s" % full)
    # 反例①：噪声面里的 docs 目录不得计入（node_modules 里全是 README/docs）
    noise = classify_docs([("node_modules/foo/docs/tutorial.md", 9), ("node_modules/foo/CONTRIBUTING.md", 9),
                           ("dist/openapi.json", 9), ("vendor/x/swagger.yaml", 9)])
    if any(noise[k] for k in ("api_spec", "guide", "contributing", "docs_site")):
        bad.append("噪声面进了分母：%s ⇒ 把依赖里的文件算成对手能力" % noise)
    # 反例②：README 在子目录不算"根 README"（厚度不得由任意同名文件撑起）
    sub = classify_docs([("pkg/README.md", 99999)])
    if sub["readme_bytes"] != 0:
        bad.append("子目录 README 被当成根 README（readme_bytes=%s）" % sub["readme_bytes"])
    # 反例③：只有图片教程 ⇒ 不算教程位
    pic = classify_docs([("docs/tutorial.png", 900)])
    if pic["guide"]:
        bad.append("教程截图被判成教程文档")
    # 反例④：失明面不得给结论
    c = finalize({"api_spec": 0, "guide": 0, "contributing": 0, "docs_site": 0}, "truncated-tree")
    if not str(c).startswith("unverified"):
        bad.append("树被截断仍判成 %s ⇒ 看不见被读成没有（r121 一手同族）" % c)
    # 反向守卫：全空样本必须 0/4（否则 shape 恒真）
    if shape({"api_spec": 0, "guide": 0, "contributing": 0, "docs_site": 0})[1] != 0:
        bad.append("shape() 恒真：全空样本仍计到位")
    # 跨判据契约三条：声明键的形状 must 被龄期尺认出（NA-UNKNOWN＝把整把常驻尺打成未验）。
    # 夹具**走生产函数本身**（build_payload），不是我另抄一份 dict——否则测的是我的构造，不是产物。
    probe_payload = build_payload([{"repo": "a/b", "class": "3/4"},
                                   {"repo": "self（心屿 MindIsle 本仓）", "class": "4/4"}], [])
    got = shape_contract(probe_payload)
    if got is None:
        bad.append("契约腿未跑成（ledger_age_check 取不到）⇒ 形状契约未验，不得静默放行")
    elif got[1] == "unknown":
        bad.append("台账形状被判 unknown ⇒ 龄期尺会整尺降档未验（r122 一手复现的键名坑）：%s" % (got,))
    # 变异腿：把键名换回 r122 那个错形状，契约腿**必须**认成 unknown（否则它就是恒绿的）
    wrong = shape_contract({"denominator": 16, "rows": [], "blind_or_na": []})
    if wrong[1] != "unknown":
        bad.append("契约腿失效：错键名 blind_or_na 被判成 %s ⇒ 这条腿抓不到自己要吃的那个坑" % (wrong,))
    print("PEER-DOCS-SELFTEST-%s（正向 1 + 反例 4 + 恒真守卫 + 跨判据形状契约 3 条，分母名册 %d 仓）"
          % ("PASS" if not bad else "FAIL: " + "; ".join(bad), len(PEERS)))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="")
    ap.add_argument("--repo", default="")
    ap.add_argument("--offline", action="store_true",
                    help="只出名册与口径，不联网（台账里明写未采，禁止折算成结论）")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return run_selftest()
    targets = [r["repo"] for r in PEERS]
    if a.repo:
        targets = [x for x in a.repo.split(",") if x in targets] or targets[:0]
    rows, blind = [], []
    if a.offline:
        rows = [{"repo": s, "class": "NA-DECLARED：--offline 未取数", "blind": "offline"} for s in targets]
        blind = [s for s in targets]
    else:
        for slug in targets:
            try:
                r = probe(slug, "")
            except Exception as e:                          # noqa: BLE001
                r = {"repo": slug, "class": "unverified(%s)" % type(e).__name__, "err": str(e)[:90]}
            rows.append(r)
            time.sleep(1.2)                                 # 错峰：连打 rest 端点会被限流
    rows.append(self_only())
    for r in rows:
        if str(r.get("class", "")).startswith(("unverified", "NA-DECLARED")):
            blind.append("%s(%s)" % (r["repo"], r.get("class")))
    # 分母口径（在册）：**dist 与 bit_counts 都只数 peers 行**。
    # self 那行是参照对象，混进桶里会印出"16 仓池里 3/4=8"这种其实含 self 的读数，
    # 而八维表拿它当"16 仓在册"抄下去 ⇒ 分母说谎（同 r121 的 peers/self 混面一族）。
    peers_rows = [r for r in rows if not str(r.get("repo", "")).startswith("self")]
    self_row = next((r for r in rows if str(r.get("repo", "")).startswith("self")), {})
    dist = {}
    for r in peers_rows:
        dist[str(r.get("class"))] = dist.get(str(r.get("class")), 0) + 1
    bits = {k: sum(1 for r in peers_rows if r.get(k))
            for k in ("api_spec", "guide", "contributing", "docs_site")}
    # 声明位用 `na`（不是 blind_or_na）——`ledger_age_check.declared_na()` 只认
    # ("blind","na","unverified") 三个顶层键，认不出形状 ⇒ 整把龄期尺判 NA-UNKNOWN、rc=2 未验。
    # r122 我就是用了 blind_or_na 把那条**常驻判据**打成的未验（一手：declared_na() 直查返回 (None,"unknown")），
    # 所以这里把形状契约写成断言（见 _shape_contract），而不是靠人记得键名。
    payload = build_payload(rows, blind)
    # 落盘前的形状自断（r126 把契约从 selftest 挪到**写路径**上）：认不出就不落盘，
    # 免得一份形状违规的台账先污染目录、再由下一轮的龄期尺把整尺打成未验。
    dec, kind = shape_contract(payload)
    if dec is None:
        print("PEER-DOCS-UNVERIFIED: 本探针产物形状不被 ledger_age_check 认得（kind=%s）⇒ 拒绝落盘" % kind)
        return 2
    if a.json:
        Path(a.json).write_bytes((json.dumps(payload, ensure_ascii=False, indent=1) + "\n")
                                 .encode("utf-8").replace(b"\r\n", b"\n"))
    full4 = sum(1 for r in peers_rows if r.get("class") == "4/4")
    print("PEER-DOCS-%s：peers 分母 %d 仓｜四类位齐(4/4)=%d｜失明或未验 %d｜形态 %s｜self=%s"
          % ("PASS" if not blind else "PARTIAL", len(peers_rows), full4, len(blind),
             " ".join("%s=%d" % kv for kv in sorted(dist.items())),
             next((r.get("class") for r in rows if str(r.get("repo", "")).startswith("self")), "NA")))
    for r in rows:
        print("  %-42s %-26s api=%s guide=%s contrib=%s docs=%s readme=%s md=%s" % (
            r["repo"][:42], r.get("class"), r.get("api_spec", "NA"), r.get("guide", "NA"),
            r.get("contributing", "NA"), r.get("docs_site", "NA"), r.get("readme_bytes", "NA"),
            r.get("docs_md_files", "NA")))
    return 0 if not blind else 1


if __name__ == "__main__":
    sys.exit(main())
