# -*- coding: utf-8 -*-
"""commit_face.py — 棘轮类判据的「写不进去的那一面」单一读取器（r177 立）

为什么单独有一件、而不是各尺自己抄一遍：r174 在耦合尺上抓到「尺读工作树、基线记提交面」，
r175 在兜底尺上抓到**同一条**，本轮普查又数出第三/四/五把同型尺（loc_guard、size_budget、
suite_count_sync）。同一条判断散在几处各写一遍，正是本仓「两份真相」那族缺陷的形状 ——
故抽成本件，接入即复用，禁止再自带第二份 git 取面逻辑。

口径（承 r175 `blindred_guard_check.head_entries`，一字不放宽）：
  · 判定只许取**提交面**（HEAD 对象库）：并行会话正在打字的字节不该把本轮判红；
  · 工作树面值**照常印**，但降级为「在途增量」单列，不参与红因；
  · 取不到（git 失败 / 超时 / 件不在 HEAD）一律落 errs，由调用方判 rc=2 UNVERIFIED，
    **严禁回落工作树数冒充提交面数**；
  · 外部调用（subprocess）一律在 try 内，且异常要落成失败原因 —— 失败路径自己不许崩
    （R275 家规；r175 第三次实发的位置是「我为修缺陷而新写的函数」本身）。

三态与全仓判据同构：0=有结论且通过 / 1=判红 / 2=未验（本件 `--selftest` 直接返回码）。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _git_batch(specs, cwd=None, timeout=60):
    """一次 `git cat-file --batch` 取回多个对象。返回 (dict rel→bytes, missing[rel], err|None)。

    为什么是一次批量而不是逐件 `git show`：在册代码面 275 件，单件 56ms ⇒ 逐件要 15s；
    一把尺的取数成本不能比被审对象还贵（电池里会被超时档位咬）。
    按**请求顺序**解析：头行 `<oid> blob <size>` 后紧跟 size 字节 + 一个 LF，
    所以内容里有多少换行都不影响切分；`<x> missing` 表示 HEAD 里根本没有这件。
    """
    if not specs:
        return {}, [], None
    payload = "\n".join("HEAD:%s" % p for p in specs).encode("utf-8") + b"\n"
    try:
        r = subprocess.run(["git", "cat-file", "--batch", "--buffer"],
                           input=payload, capture_output=True,
                           cwd=str(cwd or ROOT), timeout=timeout)
    except Exception as e:                                    # noqa: BLE001
        return {}, [], "subprocess:%s" % type(e).__name__
    if r.returncode != 0:
        return {}, [], "git rc=%d %s" % (r.returncode,
                                         (r.stderr or b"").decode("utf-8", "replace")[:80])
    buf, out, missing = r.stdout or b"", {}, []
    for rel in specs:
        nl = buf.find(b"\n")
        if nl < 0:
            return {}, [], "batch 截断（请求 %d 件，解析到 %s 处断了）" % (len(specs), rel)
        head, buf = buf[:nl], buf[nl + 1:]
        parts = head.split(b" ")
        if len(parts) >= 2 and parts[1] == b"missing":
            missing.append(rel)
            continue
        if len(parts) < 3 or not parts[2].isdigit():
            return {}, [], "头行不合形（%s）⇒ 解析器认不出就不许猜" % head[:60]
        size = int(parts[2])
        if len(buf) < size:
            return {}, [], "内容短于声明长度（%s：声明 %d，实得 %d）" % (rel, size, len(buf))
        out[rel] = buf[:size]
        buf = buf[size + 1:]
    return out, missing, None


def show_batch(rels, cwd=None, runner=None):
    """纯包装：路径清单 → ({rel: text}, 仅工作树存在的新件, 失败原因|None)。

    runner 注入是为了 selftest 不依赖真 git（同 r175 的 reader 口径）。
    取不到一律 (…, …, 原因) —— 不返回空 dict 冒充「HEAD 里都扫过了」。
    """
    runner = runner or _git_batch
    specs = [str(p).replace("\\", "/") for p in rels]
    try:
        blobs, missing, err = runner(specs, cwd)
    except Exception as e:                                    # noqa: BLE001
        return {}, [], "read:%s" % type(e).__name__
    if err:
        return {}, [], err
    try:
        return ({k: v.decode("utf-8", "replace") for k, v in blobs.items()},
                missing, None)
    except Exception as e:                                    # noqa: BLE001
        return {}, [], "decode:%s" % type(e).__name__


def head_sizes(cwd=None, runner=None):
    """一次 `git ls-tree -r -l HEAD` 取回**提交面**逐文件字节数：({rel: int}, err|None)。

    size 列对目录/符号链接是 `-`；非数字一律**不猜成 0**（R310：解析器对认不出的输入
    必须显式失败或整条跳过，假值进了分母会在离现场很远的地方炸出无关的红）。
    """
    def _run():
        r = subprocess.run(["git", "-c", "core.quotepath=false", "ls-tree", "-r", "-l", "HEAD"],
                           capture_output=True, cwd=str(cwd or ROOT), timeout=60)
        if r.returncode != 0:
            raise RuntimeError("git ls-tree rc=%d %s" % (r.returncode,
                                                         (r.stderr or b"").decode("utf-8", "replace")[:80]))
        return (r.stdout or b"").decode("utf-8", "replace")
    try:
        txt = runner() if runner else _run()
    except Exception as e:                                    # noqa: BLE001
        return {}, "%s" % type(e).__name__
    out, skipped = {}, []
    for ln in txt.splitlines():
        cols = ln.split("\t", 1)
        if len(cols) != 2:
            skipped.append(ln[:60])                            # 整行不合形：不猜路径也不猜字节
            continue
        toks, rel = cols[0].split(), cols[1].strip()
        if len(toks) != 4:
            skipped.append(rel)
            continue
        size = toks[3]
        if not size.isdigit():
            skipped.append(rel)                                # 目录/链接/子模块：本尺无此项义务
            continue
        out[rel] = int(size)
    return out, None if not skipped else "非文件/不合形条目 %d 条已跳过（不折成 0）" % len(skipped)


def pair_line(label, head_val, wt_val, new_cnt=0, new_names=(), round_tag="r177"):
    """唯一打印口径：面值与现值**各出一格**，并自证「比的是哪一面」。

    为什么这行必须由本件印而不是各尺自印：r174/r175 两轮的账面都印了 PASS/RED，
    读者却无从知道两个数来自不同面 —— 可见性本身就是缺陷的一半。
    """
    delta = "?"
    if isinstance(head_val, int) and isinstance(wt_val, int):
        delta = wt_val - head_val
    names = "、".join(list(new_names)[:3]) + ("…" if new_cnt > 3 else "") if new_cnt else "无"
    return ("   · 比较面(%s)：%s 提交面=%s｜现读工作树=%s（在途增量 %s，未入库新件 %d 个：%s）"
            % (round_tag, label, head_val, wt_val, delta, new_cnt, names or "无"))


def selftest():
    """合成面双向打过：面值喂判定、现值只单列；外部调用抛异常不许崩。"""
    bad = []
    _A = "def f():\n    pass\n"
    _B = "x = 1\n"
    fake = {"a.py": _A, "b.py": _B}

    def runner_ok(specs, cwd=None):
        return ({k: v.encode("utf-8") for k, v in fake.items() if k in specs},
                [s for s in specs if s not in fake], None)

    texts, missing, err = show_batch(["a.py", "b.py", "z.py"], runner=runner_ok)
    if err or sorted(texts) != ["a.py", "b.py"] or missing != ["z.py"]:
        bad.append("①提交面取面/缺件分列出错：%s/%s/%s" % (sorted(texts), missing, err))

    # ② 反例：HEAD 里根本没有的件必须落成 missing，不能被读成「取到空内容 ⇒ 合规」
    t2, m2, e2 = show_batch(["z.py"], runner=runner_ok)
    if e2 or "z.py" in t2 or m2 != ["z.py"]:
        bad.append("②未入库新件被当成已扫过：%s/%s" % (t2, m2))

    # ③ 外部调用真抛一次 ⇒ 必须落成失败原因且不冒泡（先证桩确实会抛，否则这条打在空气上）
    def _boom(specs, cwd=None):
        raise ValueError("读不动")
    raised = False
    try:
        _boom(["a.py"])
    except Exception:                                          # noqa: BLE001
        raised = True
    if not raised:
        bad.append("③前置条件死了：桩没抛异常，这条反例在打一个不存在的靶子")
    t3, m3, e3 = show_batch(["a.py"], runner=_boom)
    if not e3 or not e3.startswith("read:") or t3 or m3:
        bad.append("④runner 抛异常没落成失败原因（或被静默吞掉）：%s" % e3)

    # ⑤ 解析器对认不出的输入显式失败，禁静默返回空 dict 冒充「都扫过了」
    def _garbled(specs, cwd=None):
        return {}, [], "头行不合形"
    t5, _m5, e5 = show_batch(["a.py"], runner=_garbled)
    if not e5 or t5:
        bad.append("⑤git 面读不到被静默成空结论：%s" % e5)

    # ⑥ head_sizes 的非数字 size 列不得被折成 0（夹具形状逐字取自 `git ls-tree -r -l HEAD` 真输出）
    def _ls_tree():
        return ("100644 blob b673fc03884feadcb2187f3fb40a9c09e18bba0a   22632\tREADME.md\n"
                "100644 blob 2222222222222222222222222222222222222222   -\tsrc/link\n"
                "乱形一行没有制表符\n")
    sizes, note = head_sizes(runner=_ls_tree)
    if sizes != {"README.md": 22632} or not note or "2 条" not in note:
        bad.append("⑥非数字 size 被当成 0 或整行丢弃：%s（note=%s）" % (sizes, note))

    # ⑦ 口径行必须两面都印，且差值自证
    line = pair_line("超限件数", 9, 11)
    if "提交面=9" not in line or "现读工作树=11" not in line or "在途增量 2" not in line:
        bad.append("⑦比较面行没把两面与差值都印出来：%s" % line)
    line_na = pair_line("超限件数", "未验", 11)
    if "在途增量 ?" not in line_na:
        bad.append("⑧面值非整数时不许硬造差值（会读成 0）：%s" % line_na)

    # ⑨ 变异对照：同一个面上「工作树比提交面多一件」必须能被这两行读数分开——
    #    面值喂判定 = ['a.py','b.py']，现值只单列 = 再加 z.py。若两集合相同，
    #    这条腿就打在空气上（r175 家规：反例的前置条件得先证明活着）。
    judged_head = sorted(texts)
    judged_wt = sorted(set(texts) | set(missing))
    if judged_head == judged_wt or judged_wt != ["a.py", "b.py", "z.py"]:
        bad.append("⑨变异失效：面值与现值样本未分叉（%s vs %s），证不了判定只吃提交面"
                   % (judged_head, judged_wt))
    print("COMMIT-FACE-SELFTEST-%s（%d 类：取面/缺件单列/外部抛异常不崩/解析失败不静默/"
          "非数字不折 0/两面口径行/变异对照）" % ("PASS" if not bad else "FAIL: " + "; ".join(bad), 9))
    return 1 if bad else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    sizes, note = head_sizes()
    if note:
        print("COMMIT-FACE-UNVERIFIED: 提交面取不到（%s）⇒ 不得据此判绿" % note)
        sys.exit(2)
    print("COMMIT-FACE-PASS 提交面在册文件 %d 条（本件只做取面，判定由各尺自持）" % len(sizes))
    sys.exit(0)
