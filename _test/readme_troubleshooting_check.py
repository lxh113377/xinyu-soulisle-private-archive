# -*- coding: utf-8 -*-
"""README「出错了怎么办」段 ⇄ 代码标签 **双向**对账判据（r52）。

为什么要有这条：r51 报告 §4 把"README 缺面向使用者的排障段"列成中级建议后**就地蒸发**了一轮，
而 r50/r51 反复抓到的同族事故是"建议写了没做 / 做了没接线"。补一段文档不等于补上了——
文档里的状态名一旦和代码里的字符串漂移，这段就从"帮人"变成"误导人"，
而且比没有更糟（读者会照着一句不存在的话去找按钮）。

两向都判（单向必漏）：
  T1 正向：代码里**每一个**用户可见的状态标签，README 必须原字出现（漏一个 = 文档缺状态）
  T2 反向：README 排障段里**每一个**看起来是标签的行内码，代码里必须原字存在
          （多一个 = 文档凭空造状态；这是更危险的一向，因为它教用户去找不存在的东西）
零命中不得判绿：两侧任一为空即 UNVERIFIED（读空气）。
用法：python _test/readme_troubleshooting_check.py [--selftest]
退出码：0=两向齐 1=判红 2=取数面为空（未验）
"""
import argparse
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
SEC_RE = re.compile(r"^## .*出错了怎么办[\s\S]*?(?=^---$)", re.M)
CODE_SPAN = re.compile(r"`([^`]+)`")
# 看起来像"状态标签"的行内码：含这些词素的才算，其余（命令、文件名、键名）不参与反向对账。
# ⚠️ 不含 `双路`：情绪通路那行是 ` · 情绪双路：` 前缀 + `classifyEmotion` 返回的 path 拼出来的，
#    原字两边各有一半，按"整串可追溯"判会假阳；通路文案由 j2/emotion 系判据覆盖，不在本尺面内。
LABELISH = ("在线", "离线", "降级", "记忆", "转介", "暂不可用")


def readme_section(md):
    m = SEC_RE.search(md or "")
    return m.group(0) if m else ""


def code_labels(app_src):
    """从源码抽出**用户可见状态标签**——按结构位置取，不按"含某词的字符串"取。

    ⚠️ 第一版用词素筛字符串字面量，结果把注释里的话（`配了在线却降级了`、`禁伪装在线`）
    也当成状态标签，凭空要求 README 去解释一句内部注释 ⇒ 6 条假阳。
    现在只认两个**决定状态的产地**：
      a) `modeLabel = { model: "…", fallback: "…", offline: "…", guard: "…" }[r.mode]`
      b) `refreshBadge()` 里的 `b.textContent = "…"` 赋值
    取到 <3 条即视为产地形状变了 ⇒ UNVERIFIED（宁可判"没看着"，也不静默少判一类状态）。
    """
    out = []
    m = re.search(r"modeLabel\s*=\s*\{([^}]*)\}", app_src)
    if m:
        out += re.findall(r':\s*"([^"]+)"', m.group(1))
    # 徽章那一侧**只取 refreshBadge 函数体**：全文件扫 `.textContent` 会把与"引擎状态"
    # 无关的提示（如一键点亮退出时的「已回到你的真实记忆」）也算成状态标签，
    # 于是判据在要求文档去解释一句不属于本节口径的话（取数面要按数据流划，不是按文件划）。
    bm = re.search(r"function refreshBadge\(\)\s*\{([\s\S]*?)\n  \}", app_src)
    if bm:
        out += re.findall(r'\.textContent\s*=\s*"([^"]+)"\s*;', bm.group(1))
    return {x.strip() for x in out if x.strip()}


def doc_spans(section):
    return {s.strip() for s in CODE_SPAN.findall(section or "")}


def assess(labels, spans):
    """纯函数：labels = 代码侧标签集，spans = README 行内码集。"""
    if not labels or not spans:
        return None, ("T0 取数面为空（代码标签 %d 条 / 文档行内码 %d 条）⇒ 读空气，不判绿"
                      % (len(labels), len(spans)))
    # 正向：README 的表格单元格里有"组合码"（如 `在线大模型生成 · 已带入 N 条记忆`），
    # 所以按"整段行内码拼起来做子串"判，而不是要求逐码全等（全等会误报"文档没写"）。
    joined = " ".join(spans)
    missing_doc = sorted(x for x in labels if x not in joined)
    # 反向只判"像标签的码"，且允许它是带上下文的组合串（如 `A · B` 形式的表格单元格）
    invented = sorted(x for x in spans
                      if any(w in x for w in LABELISH)
                      and not any(l in x or x in l for l in labels))
    bad = []
    for x in missing_doc:
        bad.append("T1 代码里有此状态标签，README 未写：%s" % x)
    for x in invented:
        bad.append("T2 README 写了此状态，代码里找不到原字标签：%s" % x)
    return bad, "正向 %d 条标签全部在册 ｜ 反向 %d 条码全部可追溯" % (len(labels), len(spans))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest())
    md = (ROOT / "README.md").read_text("utf-8", errors="replace")
    app = (ROOT / "src" / "js" / "app.js").read_text("utf-8", errors="replace")
    labels = code_labels(app)
    if len(labels) < 3:
        print("READMETS-UNVERIFIED: 状态标签产地取到 %d 条（<3）⇒ app.js 形状变了，"
              "本判据的取数面需随之更新，不得当作「没有状态要文档化」" % len(labels))
        sys.exit(2)
    bad, info = assess(labels, doc_spans(readme_section(md)))
    if bad is None:
        print("READMETS-UNVERIFIED: " + info)
        sys.exit(2)
    for x in bad:
        print("  · FAIL " + x)
    if bad:
        print("READMETS-FAIL: %d 条漂移（%s）" % (len(bad), info))
        sys.exit(1)
    print("READMETS-PASS: README 排障段与代码标签双向逐字一致（%s）" % info)
    sys.exit(0)


def selftest():
    ok, fail = 0, []
    labels = {"在线大模型生成", "大模型暂不可用 · 离线共情模板", "安全转介策略"}
    if not assess(labels, {"在线大模型生成", "大模型暂不可用 · 离线共情模板", "安全转介策略"})[0]:
        ok += 1
    else:
        fail.append("正例：全对上了却判红 %s" % assess(labels, labels)[0])
    b1 = assess(labels, {"在线大模型生成"})[0]
    if b1 and any("T1" in x for x in b1):
        ok += 1
    else:
        fail.append("反例①（文档少写状态）未判红：%s" % b1)
    b2 = assess(labels, set(labels) | {"● 已离线"})[0]
    if b2 and any("T2" in x for x in b2):
        ok += 1
    else:
        fail.append("反例②（文档凭空造状态）未判红：%s" % b2)
    # 边界：两侧任一为空 ⇒ UNVERIFIED（bad is None），不得判绿也不得判红
    if assess(set(), labels)[0] is None and assess(labels, set())[0] is None:
        ok += 1
    else:
        fail.append("边界 空取数面未走 UNVERIFIED")
    # 接线自证：真从 app.js 抽标签，必须抽到 model/fallback/guard 三形（防取数面退化成空集）
    src = (ROOT / "src" / "js" / "app.js").read_text("utf-8", errors="replace")
    got = code_labels(src)
    if ({"在线大模型生成", "安全转介策略", "● 在线 AI"} <= got and len(got) >= 6
            and not any("已回到你的真实记忆" in x for x in got)):
        ok += 1
    else:
        fail.append("接线 从 app.js 抽标签异常（%d 条）：%s" % (len(got), sorted(got)[:8]))
    expected = 5
    for x in fail:
        print("  SELFTEST-FAIL " + x)
    print("READMETS-SELFTEST: %d/%d%s" % (ok, expected,
          "" if ok + len(fail) == expected else "  ⚠️ 分支数 %d≠%d" % (ok + len(fail), expected)))
    return 0 if ok == expected and ok + len(fail) == expected else 1


if __name__ == "__main__":
    main()
