# -*- coding: utf-8 -*-
"""断点标尺棘轮（r129 新增 · F-R-1 / r168 接线并修自噬）：宽度断点必须落在唯一标尺内，且不得漂移

为什么做这条判据（F-R-1 体检红项的落点）：
2026-10-12 Step 2.5 前端专项实测出——本仓零构建纯 CSS，宽度断点散落
`@media(max-width:480/640/768/768/900/1024px)`，**5 个唯一值、768 在 style.css
内部定义了两次、480 横跨 style.css 与 voice-call.css 两文件，且没有任何一处
声明「这是标尺」**。后果不是「现在难看」，而是**下一个要加一端设备的人只能猜数字**，
每加一端就是一次全仓返工 —— 这正是 F-R-1「断点是共享契约」要防的东西。

⚠️ 关键取舍：为什么是**尺**而不是**搬代码**？
把两处 768 合并、或把 15 处 `@media` 全部搬到文件末尾集中，会改变**层叠顺序**：
本仓两处 768 服务的是**不相交的选择器**（一处顶栏/对话坞，一处表情浮窗），
合并后将来改表情样式就可能连带踩到对话坞布局。这是「为整洁冒回归风险」——
按本仓铁律 R263（修判据不修数据、禁为求绿改数据面），
正解是**让标尺可执行、让漂移当场判红**，而不是重排级联。

判据三条：
  B1 唯一标尺：style.css 头部必须声明本仓的唯一断点标尺（当前 5 档）
  B2 取值合法：所有 `@media` 的宽度取值必须 ∈ 标尺集合（新增档位须显式改标尺，不许私造）
  B3 棘轮：每个断点值的**定义处数**不得超过基线，只增不减即红
     （基线记录当前真实分布；不把「现在有 2 处」洗成「标准就是 2 处」）

非宽度媒体查询（`prefers-reduced-motion` / `pointer:coarse` / `hover` / `max-height`）
**不计入** —— 它们不是宽度标尺的成员，混进来会让分母失真。

退出码：0=BREAKPOINT-SCALE-PASS 1=任一红 2=环境未验（读不到 CSS 面，不得声称已验）

## r168 两处修（本件此前是 G16 点名的孤儿判据：已入库、已写文档，电池与 CI 两头零执行）

1. **自噬面**：第一版 `--selftest` 用 `primary.read_text()` 取备份后**直接改写权威源**
   `src/css/style.css` 做变异，靠 `finally` 写回。⇒ 变异与还原之间任何中断（Ctrl-C / 崩溃 /
   并发写）都会把全站样式表留在残缺态。2026-10-13 08:36 实测该面确实处于被清空态
   （`src/css/style.css` 与 `voice-call.css` 同时 0 字节，wt oid=空块 e69de29），
   当时 `--selftest` 读到空面后把空串写回，只是没造成新损失。**风险不靠运气承担**：
   现在变异全部在 `tempfile` 副本上进行，并在收尾**逐文件比对权威源字节是否被改过**，
   改过即 SELFTEST-FAIL（这条腿就是本修的牙）。
2. **空面判据失真**：style.css 为 0 字节时 B1 恒假、B3 因 `counts={}` 恒真，
   于是「权威源被清空」这一环境事实被读成「产品违规 + 一项 vacuous PASS」。
   现在 `face_problem()` 先行，空面/零分母一律 rc=2 未验并点名，不自相矛盾。
   配反向腿：把副本清空必须得 rc=2 而不是 rc=1。
"""
import re
import shutil
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
CSS_DIR = ROOT / "src" / "css"

# 唯一标尺的声明锚点：style.css 头部注释里的一行，机器可读
SCALE_RE = re.compile(r"@breakpoint-scale\s+((?:\d+(?:px)?\s*)+)")
MEDIA_WIDTH_RE = re.compile(r"@media\s*\(?\s*(?:max|min)-width\s*:\s*(\d+)px")

# r129 基线：每个宽度值当前真实出现的「定义处数」（src/css 全量）。
# 只增不减 ⇒ 红。压降是加分项，不强求（强求会逼着人去搬级联，那是回归风险）。
BASELINE = {"480": 2, "640": 1, "768": 2, "900": 1, "1024": 1}

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  -> {detail}" if detail else ""))


def css_files(css_dir=CSS_DIR):
    d = Path(css_dir)
    if not d.is_dir():
        return None
    return sorted(p for p in d.glob("*.css"))


def declared_scale(text):
    m = SCALE_RE.search(text)
    if not m:
        return None
    return sorted({int(x.replace("px", "")) for x in m.group(1).split()}, key=lambda v: -v)


def width_counts(files):
    """返回 {断点值: [(文件名, 行号), ...]}，只数宽度媒体查询。"""
    out = {}
    for p in files:
        for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            for m in MEDIA_WIDTH_RE.finditer(line):
                out.setdefault(int(m.group(1)), []).append((p.name, i))
    return out


def face_problem(files, primary):
    """被检面对不对得起这把尺 ⇒ 不对得起就返回原因（判据不得据空面出结论）。"""
    if files is None:
        return "src/css 不在预期位置"
    if not files:
        return "src/css 下零个 .css 文件 ⇒ 分母为空，不得读成「没有断点」"
    if not primary.exists():
        return f"读不到 {primary}"
    if primary.stat().st_size == 0:
        return (f"{primary.name} 为 0 字节 ⇒ 权威样式表被清空（在途写入或事故），"
                "此时 B1 恒假、B3 因计数为空而恒真，任何结论都是假的")
    if sum(p.stat().st_size for p in files) == 0:
        return "src/css 全部为 0 字节 ⇒ 整个被检面为空"
    return None


def run_checks(files, primary):
    """前提：face_problem() 已判过（面可信）。返回本次独立快照的 results。"""
    # ⚠️ results 必须在这里清空。第一版把它当模块级累加器、check() 只追加不重置，
    # 于是「变异 → 还原 → 复跑原样」里的**最后那次复跑读到的是历次运行的累积结果**，
    # 把早已撤销的变异红项又数了一遍 ⇒ 自测误报「还原后仍判红」。
    # 同族：api_contract_check 篡改⑧ 硬编码旧计数串导致变异腿空操作。
    # 正解：每次 run_checks() 都是一次独立快照。
    del results[:]
    text = primary.read_text(encoding="utf-8", errors="replace")

    # B1 唯一标尺已声明
    scale = declared_scale(text)
    check("B1 唯一断点标尺已在 style.css 头部声明",
          scale is not None,
          f"标尺 = {scale}（降序）" if scale else "找不到 @breakpoint-scale 声明行")

    # B2 取值合法
    counts = width_counts(files)
    if scale is None:
        check("B2 所有宽度断点落在标尺内", False, "标尺未声明，本腿判红（不得据此另开 B3）")
    else:
        stray = sorted(v for v in counts if v not in scale)
        check("B2 所有宽度断点落在标尺内", not stray,
              f"越界值 = {stray}；实际出现 = {sorted(counts, reverse=True)}"
              if stray else f"实际出现 = {sorted(counts, reverse=True)}，标尺 = {scale}")

    # B3 棘轮：只增不减
    grew = []
    for v, cap in BASELINE.items():
        n = len(counts.get(int(v), []))
        if n > cap:
            grew.append(f"{v}px 定义处 {n} > 基线 {cap}（{counts[int(v)]}）")
    # 标尺里新增的档位（不在基线里）也算漂移，须显式更新基线并说明理由
    new_keys = sorted(v for v in counts if str(v) not in BASELINE)
    if new_keys:
        grew.append(f"出现基线外的新断点值 {new_keys} ⇒ 须显式改标尺与基线，不许私造")
    check("B3 断点定义处数棘轮（只增不减）", not grew,
          "；".join(grew) if grew else "各值定义处数 = " + str({str(k): len(v) for k, v in counts.items()}))
    return results


def judge(css_dir=CSS_DIR):
    """一把尺的三个出口：(rc, 红项名单)。rc=2 表示被检面对不起这把尺。"""
    files = css_files(css_dir)
    primary = Path(css_dir) / "style.css"
    problem = face_problem(files, primary)
    if problem:
        return 2, [f"ENV: {problem}"]
    res = run_checks(files, primary)
    red = [n for n, ok, _ in res if not ok]
    return (1 if red else 0), red


def _snapshot(css_dir):
    """被检面的逐文件字节指纹（副本作业前后各取一次，证权威源没被碰）。"""
    out = {}
    for p in css_files(css_dir) or []:
        out[p.name] = p.stat().st_size
    return out


def selftest():
    """变异腿：三条判据各自必须能被打翻，且**全程不碰权威源**。"""
    pristine = _snapshot(CSS_DIR)
    if not pristine:
        print("SELFTEST-FAIL: src/css 无可读面，无法证伪（不得据此声称变异腿已过）")
        return 2
    tmp = Path(tempfile.mkdtemp(prefix="breakpoint_scale_"))
    bad = []
    try:
        for name in pristine:
            shutil.copyfile(CSS_DIR / name, tmp / name)
        primary = tmp / "style.css"
        others = [p for p in css_files(tmp) if p != primary]
        backup = {p: p.read_bytes() for p in css_files(tmp)}

        def restore():
            for p, b in backup.items():
                p.write_bytes(b)

        def mutate(path, old, new, label):
            t = path.read_text(encoding="utf-8")
            if old not in t:
                raise AssertionError(f"变异腿空操作：{path.name} 里找不到 {old!r}（{label}）")
            path.write_text(t.replace(old, new, 1), encoding="utf-8")

        # 腿 1 · B1：抹掉标尺声明 ⇒ 必须判红
        try:
            text = primary.read_text(encoding="utf-8")
            m = SCALE_RE.search(text)
            if not m:
                raise AssertionError("变异腿空操作：style.css 里本就找不到标尺声明 ⇒ B1 恒真")
            # ⚠️ 必须锚定**整行声明**，不能只锚 @breakpoint-scale 这四个字母：
            # 它在文件里出现两次（正文说明里也提了一次），replace(...,1) 会打到说明那处，
            # 真声明纹丝不动 ⇒ 变异没打中却以为自己打中了。
            decl_line = next(l for l in text.splitlines() if SCALE_RE.search(l))
            primary.write_text(text.replace(decl_line, "/* @breakpoint-scale REMOVED */"),
                               encoding="utf-8")
            rc, red = judge(tmp)
            if rc != 1 or not any(n.startswith("B1") for n in red):
                bad.append(f"B1 变异腿失效：抹掉标尺声明后 rc={rc} 红项={red}（期望 rc=1 且点名 B1）")
        except AssertionError as e:
            bad.append(str(e))
        finally:
            restore()

        # 腿 2 · B2/B3：在 voice-call.css 里私造一个 850px 断点 ⇒ 必须判红
        if others:
            try:
                mutate(others[0], "}", "}\n@media(max-width:850px){.x{color:red}}", "B2/B3")
                rc, red = judge(tmp)
                if rc != 1:
                    bad.append(f"B2/B3 变异腿失效：私造 850px 断点后 rc={rc} 红项={red}（期望 rc=1）")
            except AssertionError as e:
                bad.append(str(e))
            finally:
                restore()
        else:
            bad.append("腿 2 未执行：src/css 除 style.css 外没有第二个 CSS 文件（分母异常）")

        # 腿 3 · 空面反向腿（r168 新增）：把副本清空 ⇒ 必须是 rc=2 未验，不得判红
        try:
            primary.write_bytes(b"")
            rc, red = judge(tmp)
            if rc != 2:
                bad.append(f"空面门失效：style.css 清空后 rc={rc}（期望 2 未验；判红会把环境事故"
                           "写成产品违规，同时 B3 因计数为空而 vacuous PASS）")
        finally:
            restore()

        # 腿 4 · 还原后原样必须全绿
        rc, red = judge(tmp)
        if rc != 0:
            bad.append(f"还原后仍非绿：rc={rc} 红项={red}（变异没撤销干净）")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        after = _snapshot(CSS_DIR)
        if after != pristine:
            bad.append(f"自噬腿：--selftest 改动了权威源 src/css（前={pristine} 后={after}）")

    print("SELFTEST-PASS: B1 抹标尺、B2/B3 私造新断点、空面必落未验 三类变异腿各自打翻，"
          "还原后原样零红，且权威源 src/css 逐文件字节数未变"
          if not bad else "SELFTEST-FAIL: " + "; ".join(bad))
    return 1 if bad else 0


def main():
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    rc, red = judge()
    if rc == 2:
        print(f"BREAKPOINT-SCALE-ENV-UNVERIFIED: {red[0]}，不得声称已验")
        return 2
    counts = width_counts(css_files())
    if rc == 1:
        print(f"合计 {len(results)} 项，红 {len(red)}")
        for n in red:
            print(f"  🔴 {n}")
        print("BREAKPOINT-SCALE-FAIL")
        return 1
    dist = "、".join(f"{v}px×{len(x)}" for v, x in sorted(counts.items(), reverse=True))
    print(f"合计 {len(results)} 项，红 0｜分布 {dist}")
    print("BREAKPOINT-SCALE-PASS 断点全部落在唯一标尺内、定义处数未增长")
    return 0


if __name__ == "__main__":
    sys.exit(main())
