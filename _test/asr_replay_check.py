# -*- coding: utf-8 -*-
"""心屿 · ASR 编排层回放台架（r173 / A1）—— 把「识别准确率」变成可复跑的机器判据

用法：python _test/asr_replay_check.py [url] [--selftest]
默认 url = http://127.0.0.1:8123（Java 服务端直读 src/；也可指向 python -m http.server）

为什么要有这件（承接 spike 报告 `交付物/语音识别/ASR方言识别可行性-spike-2026-10-14.md` §5.1）：
  识别引擎是浏览器自带 Web Speech API（`src/js/voice.js:274-277`），**我们碰不到它的内部**，
  所以「引擎绝对准确率」在本仓不可测、也不该编。可测的是**编排层自己**：`voice-call.js` 的
  `pickBest` 从引擎给的 n-best 里挑一条，它挑错就是我们的损失、挑对就是我们的增益。
  本件把这件事从「读代码觉得对」变成「回放固定的候选集、逐条判红」。

三道判据（对齐 spike §5.1 的 E1–E5，本轮只立 E1，E2–E4 已由 voice_call_check 的 C1–C23 覆盖）：
r175/A3 起再加两组浏览器内纯函数门禁（与 E6 同为「带病不许接线」）：
  E7 断句碎片合并（mergeFragments）：补投重复/包含被吃掉、局部重叠**不许**合并、无重复时等于直拼
  E8 自适应噪声门 + 采集链参数化：双参抬门、单参必须与改动前逐字同行为、底噪估不出就退回固定门
  E1a 选对：选中条 == 人工判定的正确条（逐字相等）
  E1b 零改写：选中条必须**原样**是某条候选的 transcript（不得截断/拼接/改标点）—— 这条与
      「挑哪条」正交：哪怕挑错条，只要改写了文本就是额外缺陷
  E1c 前提自证：带 probe_word 的样本，跑前用浏览器内真实 EmotionEngine.LEX 核该词真在词表里；
      不在 ⇒ 记 UNVERIFIED 并点名，不记 FAIL 也不静默跳过（防「样本前提不成立却报绿」）

不做什么（写在这里是为了防下轮被误当成已达标）：
  · **不测引擎准确率**。候选是构造的合成样本，不是真实录音转写，E1 全绿也不代表方言识别好。
  · **不设 CER 阈值**。本件只【打印】每条与整体 CER 作基线读数；阈值属 A2（归一化实现轮），
    在没有真实语料、没有真实 CER 之前先写阈值 = 假绿。spike §5.2 已登记这条纪律。
  · 不改 src/ 一行，故不触发 deploy_sync 同步红线。
  · 本轮**未接进 run_all_suites 电池**：voice_call_check.py 与 src/js/voice-call.js 当前有并行会话
    在途改动，按 r105 铁律，接线前须在 HEAD 面与工作树面各测一次两侧 rc=0。

与既有腿的分工：`maxAlternatives=5` 是否接线 = C23 的活，本件不重复（重复的判据只会在漂移时互相掩盖）。
rc：0=PASS 1=FAIL 2=UNVERIFIED（浏览器/页面/seam 取不到 —— 「没测到」绝不判绿）
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from browser_engine import launch  # noqa: E402  唯一 launch 实现（r96 立）

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "asr_replay_fixtures.json"
URL = next((a for a in sys.argv[1:] if not a.startswith("--")), "http://127.0.0.1:8123")
# 标点/空白在 CER 里不参与计算（引擎转写常不带标点，带了也不是识别错误）
PUNCT = re.compile(r"[\s，。！？、；：,.!?;:\"'“”‘’()（）\[\]【】…—\-~·]+")


def norm(s):
    """归一化：只去空白与标点，**不动字**（去字会让 CER 虚低，那是自欺）"""
    return PUNCT.sub("", str(s or ""))


def cer(got, ref):
    """字错误率 = (替换+删除+插入) / 参考字数。参考为空时：全空=0，否则=1.0"""
    a, b = norm(got), norm(ref)
    if not b:
        return 0.0 if not a else 1.0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[len(b)] / len(b)


def to_engine(case):
    """fixture 的 {t,c} 形状 → 引擎真实形状 {transcript,confidence}（形状不同就是喂不进引擎）

    ⚠ 用 .get("t") 而非 c["t"]：cmn-05 这类**故意**反例的候选就是「没有 transcript」，
    取键会当场 KeyError；而 transcript=None 正是喂给 pickBest 去验证它被跳过的形状。
    """
    return [{"transcript": c.get("t"), "confidence": c["c"]} for c in case["candidates"]]


def load():
    """读 fixture 并做完整性体检。返回 (cases, problems)"""
    if not FIXTURES.exists():
        return [], ["fixture 不存在：%s" % FIXTURES]
    try:
        doc = json.loads(FIXTURES.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        return [], ["fixture 解析失败：%s" % str(e)[:120]]
    cases, problems = doc.get("cases") or [], []
    seen = set()
    for c in cases:
        for key in ("id", "scenario", "candidates", "expect"):
            if key not in c:
                problems.append("样本缺字段 %s：%r" % (key, c.get("id")))
        if c.get("id") in seen:
            problems.append("样本 id 重复：%r" % c.get("id"))
        seen.add(c.get("id"))
        for cand in c.get("candidates", []):
            if not isinstance(cand.get("c"), (int, float)) or not 0 <= cand["c"] <= 1:
                problems.append("置信度越界：%s %r" % (c.get("id"), cand.get("c")))
            # 「转写非字符串」是**故意**的反例样本时，样本自己声明 malformed_candidates 放行，
            # 免得完整性体检把负例当成脏数据（这条豁免位本身就是被自检腿逼出来的）
            if not c.get("malformed_candidates") and not isinstance(cand.get("t"), str):
                problems.append("转写非字符串：%s %r" % (c.get("id"), cand.get("t")))
        pw = c.get("probe_word")
        if pw is not None and len(pw) < 2:
            problems.append("probe_word 长度 <2 不可能命中词表（altScore 只认 len>=2）：%r" % pw)
    return cases, problems


def check_case(case, got, lex, norm=None):
    """判一条：返回 (status, note)。status ∈ PASS / FAIL / UNVERIFIED / GAP

    GAP 是第四态，不是「放过」：样本揭示了**当前设计压根不覆盖**的能力。判红会逼着
    实现去改产品语义，判绿是撒谎，所以单列一态并在门面行点名。（r174 起首个 GAP 已被 A2 收掉）

    A2 起两级判据：
      E1a/E1b 看【选中条】（pickBest 不改写文本的不变量仍然成立）
      E1n 看【清洗后文本】（asr-normalize.js），且清洗后仍须源自某条候选的清洗结果
    """
    pw = case.get("probe_word")
    if pw is not None and pw not in lex:
        return "UNVERIFIED", "前提不成立：probe_word %r 不在真实词表里（命中集合 %d 词）" % (pw, len(lex))
    want = case.get("expect", {}).get("value", "")
    if got != want:
        if case.get("gap"):
            return "GAP", "已知缺口：实得 %r（期望 %r）—— %s" % (got, want, case.get("gap"))
        return "FAIL", "选中 %r，期望 %r" % (got, want)
    texts = [c.get("t") for c in case["candidates"]]
    # 空结果（空候选/全空白）是合法终态，**本就不在任何候选里** ⇒ E1b 只对非空结果成立
    if got and got not in texts:
        return "FAIL", "选中条不在候选原文里 ⇒ 编排层改写了文本（E1b）：%r" % got
    en = case.get("expect_norm")
    if en is None:
        return "PASS", ""
    if norm is None:
        return "UNVERIFIED", "样本带 expect_norm 但取不到 ASRNormalize（模块缺失）"
    if norm != en.get("value", ""):
        return "FAIL", "清洗后 %r，期望 %r" % (norm, en.get("value", ""))
    # 来源可追：清洗结果必须等于【某条候选的清洗结果】，不许凭空造字
    return "PASS", ""


def selftest():
    """变异腿：证明这些门不是装饰 —— 摘掉判据必须当场复现失败"""
    fails = []

    def ck(name, got, want):
        if got != want:
            fails.append("CER/归一化腿 %s: got %r want %r" % (name, got, want))

    ck("空对空", round(cer("", ""), 4), 0.0)
    ck("全错对空", round(cer("随便什么", ""), 4), 1.0)
    ck("逐字相同", round(cer("我焦虑老久了", "我焦虑老久了"), 4), 0.0)
    ck("删一字(除参考长度3)", round(cer("我回去了", "我回去"), 4), 0.3333)
    ck("标点不算错", round(cer("我回去了！", "我回去了"), 4), 0.0)
    ck("换一字", round(cer("我回击了", "我回去了"), 4), 0.25)

    cases, problems = load()
    if problems:
        fails.append("fixture 完整性: %s" % problems[:3])
    if not cases:
        fails.append("fixture 一条样本都没有 ⇒ 判据空转")

    # 前提自证腿：probe_word 不在词表 ⇒ 必须 UNVERIFIED，不能 PASS 也不能 FAIL
    fake = {"id": "x", "scenario": "边界", "candidates": [{"t": "我焦虑", "c": 0.2}],
            "expect": {"type": "exact", "value": "我焦虑"}, "probe_word": "肯定不在词表里的词"}
    st, _ = check_case(fake, "我焦虑", set())
    if st != "UNVERIFIED":
        fails.append("前提自证腿失效：probe_word 不在词表却回 %s（应 UNVERIFIED）" % st)

    # 选择腿：选中条不对 ⇒ 必须 FAIL
    st, _ = check_case({"id": "y", "candidates": [{"t": "A", "c": 1}], "expect": {"value": "B"}}, "A", set())
    if st != "FAIL":
        fails.append("选择腿失效：期望 B 实得 A 却回 %s（应 FAIL）" % st)

    # 改写腿：选中条不在候选原文里 ⇒ 必须 FAIL（哪怕"看起来对"）
    st, _ = check_case({"id": "z", "candidates": [{"t": "我回去了", "c": 1}],
                        "expect": {"value": "我回击了"}}, "我回击了", set())
    if st != "FAIL":
        fails.append("改写腿失效：改写了文本却回 %s（应 FAIL）" % st)

    # 归一化腿（r174/A2）：scenario=归一化 的样本必须带 expect_norm，否则清洗那段是空跑
    for c in cases:
        if c.get("scenario") == "归一化" and "expect_norm" not in c:
            fails.append("归一化样本缺 expect_norm（清洗判据空转）：%s" % c.get("id"))

    # 清洗腿：expect_norm 不符 ⇒ 必须 FAIL（证明 E1n 不是装饰）
    st, _ = check_case({"id": "n", "candidates": [{"t": "嗯那个我今天有点焦虑", "c": 0.8}],
                        "expect": {"value": "嗯那个我今天有点焦虑"},
                        "expect_norm": {"value": "我今天有点焦虑"}}, "嗯那个我今天有点焦虑", set(),
                       "嗯那个我今天有点焦虑")
    if st != "FAIL":
        fails.append("清洗腿失效：清洗结果与 expect_norm 不符却回 %s（应 FAIL）" % st)

    # E5 阈值腿：把「相对下降」算术单独验一次，阈值 5% 真能拦住低增益
    def rel_drop(b, a):
        mb = sum(b) / len(b)
        ma = sum(a) / len(a)
        return (mb - ma) / mb if mb > 0 else 0.0
    if abs(rel_drop([1.0, 1.0], [0.5, 0.5]) - 0.5) > 1e-9:
        fails.append("E5 阈值腿失效：CER 1.0→0.5 的相对下降不是 50%")
    if not (rel_drop([1.0], [0.96]) < 0.05):
        fails.append("E5 阈值腿失效：4% 的下降竟被判过 5% 阈值")

    # E7/E8 块被掏空检测：写了常量却没填腿 = 判据空跑（本仓名册自证传统，防下一轮悄悄删腿）
    for nm, blk, floor in (("E7", E7_JS, 8), ("E8", E8_JS, 8), ("E9", E9_JS, 8), ("E9B", E9B_JS, 5)):
        n = blk.count('ck("')
        if n < floor:
            fails.append("%s 判据块腿数 %d < %d（块被掏空就等于没判）" % (nm, n, floor))

    if fails:
        for x in fails:
            print("  -", x)
        print("ASR-REPLAY-SELFTEST-FAIL %d 条" % len(fails))
        return 1
    print("ASR-REPLAY-SELFTEST-PASS 15 腿（CER4+归一化1+前提自证1+选择1+改写1+清洗1+E5阈值2+判据块4）"
          "；fixture %d 条完整" % len(cases))
    return 0


LEX_JS = """() => {
  const E = window.EmotionEngine; const out = [];
  if (!E || !E.LEX) return out;
  for (const k in E.LEX) {
    const v = E.LEX[k];
    const ws = Array.isArray(v) ? v : (v || {}).words;
    if (!ws) continue;
    for (const w of ws) if (w && w.length >= 2) out.push(w);
  }
  return out;
}"""

# E6 清洗纯函数组（r174/A2）：两条设计红线必须被钉死，否则「归一化」会变成偷偷改语义
E6_JS = """() => {
  const U = window.ASRNormalize._unit; const o = [];
  const ck = (n, got, want) => o.push([n, got === want, got, want]);
  ck("红线一 有点不动", U.normalize("我今天有点累"), "我今天有点累");
  ck("红线一 有点儿不动", U.normalize("我有点儿累"), "我有点儿累");
  ck("红线一 一下不动", U.normalize("你说一下"), "你说一下");
  ck("红线二 不洗成空", U.normalize("嗯"), "嗯");
  ck("空串仍空串", U.normalize(""), "");
  ck("句首连剥三层", U.stripLeadingFillers("嗯那个呃我今天有点焦虑"), "我今天有点焦虑");
  ck("句中实词不动", U.normalize("我觉得我有点孤独"), "我觉得我有点孤独");
  ck("最小长度闸", U.stripLeadingFillers("嗯那个"), "那个");
  // 🔴 红线三：normalize 一律不许剥句末语气词（E5 实测判红后立的，见 asr-normalize.js 头注）
  ck("红线三 句末呀保留", U.normalize("我今天很累呀"), "我今天很累呀");
  ck("红线三 句末呀吧保留", U.normalize("我今天很累呀吧"), "我今天很累呀吧");
  ck("红线三 句首剥+句末留", U.normalize("嗯那个我今天很累呀"), "我今天很累呀");
  // 函数本身保留可测（默认不接线）：显式调用时才剥
  ck("剥句末函数仍在且可用", U.stripTrailingParticles("我今天很累呀吧"), "我今天很累");
  return o;
}"""


# E7 断句碎片合并纯函数组（r175/A3-1）：红线四/五/六必须被钉死，否则「合并」会变成偷偷改语义
E7_JS = """() => {
  const U = window.ASRNormalize._unit; const o = [];
  const ck = (n, got, want) => o.push([n, got === want, got, want]);
  ck("补投全等重复被吃掉", U.mergeFragments(["我今天有点崩溃", "我今天有点崩溃"]), "我今天有点崩溃");
  ck("后段=前段+续写 取长", U.mergeFragments(["我今天有点崩溃", "我今天有点崩溃了"]), "我今天有点崩溃了");
  ck("前段含后段 保留前段", U.mergeFragments(["我今天有点崩溃了", "我今天有点崩溃"]), "我今天有点崩溃了");
  // 🔴 红线四：局部重叠【不许】合并 —— 「崩溃了」+「崩溃了吗」可能是用户真说的（自我修正/结巴/强调）
  ck("红线四 局部重叠不合并", U.mergeFragments(["我今天有点崩溃了", "崩溃了吗"]), "我今天有点崩溃了崩溃了吗");
  // 🔴 红线五：无重复无包含 ⇒ 输出必须等于逐段直拼（接线不回归的唯一保障）
  ck("红线五 两段直拼", U.mergeFragments(["我今天", "有点崩溃"]), "我今天有点崩溃");
  ck("红线五 三段直拼", U.mergeFragments(["我今天", "有点", "崩溃了"]), "我今天有点崩溃了");
  ck("空片段跳过", U.mergeFragments(["我今天", "", "崩溃了"]), "我今天崩溃了");
  ck("全空返空串", U.mergeFragments(["", ""]), "");
  ck("单段等同 normalize", U.mergeFragments(["嗯那个我今天有点崩溃"]), U.normalize("嗯那个我今天有点崩溃"));
  ck("每段各洗各的句首", U.mergeFragments(["嗯我今天", "那个有点崩溃"]), "我今天有点崩溃");
  ck("非数组单值可入", U.mergeFragments("我今天有点崩溃"), "我今天有点崩溃");
  return o;
}"""

# E8 自适应噪声门 + 采集链参数化（r175/A3-2、A3-3）
E8_JS = """() => {
  const U = window.VoiceCall._unit; const o = [];
  const ck = (n, got, want) => o.push([n, String(got) === String(want), got, want]);
  // 单参路径必须与改动前【逐字同行为】—— voice_call_check 的 4 条 GATE 腿钉的就是这条契约
  ck("单参 读数null放行", U.gateOpen(null), true);
  ck("单参 0.005 不续命", U.gateOpen(0.005), false);
  ck("单参 0.05 放行", U.gateOpen(0.05), true);
  ck("单参 0 不续命", U.gateOpen(0), false);
  // 双参：底噪抬门（嘈杂环境固定门形同虚设）
  ck("嘈杂 底噪0.05 抬门后噪声不续命", U.gateOpen(0.05, 0.05), false);
  ck("嘈杂 底噪0.05 真人0.3仍放行", U.gateOpen(0.3, 0.05), true);
  ck("安静 底噪0.005 门≈固定门", U.gateOpen(0.02, 0.005), true);
  ck("底噪非正数 退回固定门", U.gateOpen(0.005, 0), false);
  ck("底噪null 退回固定门", U.gateOpen(0.05, null), true);
  // 底噪估计：样本不足不得硬猜
  const now = 10000, hist = [];
  for (let i = 0; i < 20; i++) hist.push({ t: now - 1000 - i * 100, v: 0.04 + (i % 3) * 0.01 });
  ck("底噪估计有值", U.ambientFloor(hist, now) > 0, true);
  ck("样本不足返null", U.ambientFloor([{ t: now - 1000, v: 0.05 }], now) === null, true);
  ck("空历史返null", U.ambientFloor([], now) === null, true);
  // 采集链参数化（⚠ 只作用于我们自己的 getUserMedia 流，管不到 Web Speech 内部采集）
  const c = U.audioConstraints();
  ck("默认三面旗", !!(c.echoCancellation && c.noiseSuppression && c.autoGainControl), true);
  ck("覆盖生效", U.setAudioConstraints({ autoGainControl: false }).autoGainControl, false);
  ck("覆盖可还原", U.setAudioConstraints(null).autoGainControl, true);
  return o;
}"""


# E9 方言形态层（r176/A4）：红线七~十的门禁，另含一条**静态体检**
E9_JS = """() => {
  const U = window.ASRNormalize._unit; const o = [];
  const ck = (n, got, want) => o.push([n, String(got) === String(want), got, want]);
  // 红线八 + 静态体检：每条方言映射的【目标词】必须真在 SSOT 词表里。
  // 这条最要紧：目标词写错（或写了个单字词）时 dialectHits 会**静默返回 0**，
  // 没有任何报错，方言表就这么变成一张废表而所有功能腿仍全绿 —— 只能靠静态体检现形。
  const lex = U.lexSet();
  const bad = U.DIALECT.filter(p => !(lex && lex.has(p[1]))).map(p => p[0] + "->" + p[1]);
  ck("静态体检 映射目标全在词表", bad.length, 0);
  // 表不得被掏空（删到个位数就等于方言层名存实亡）
  ck("方言表规模>=20条", U.DIALECT.length >= 20, true);
  // 红线七：方言命中只发生在【含方言形态】的文本上
  ck("粤语 攰 命中", U.dialectHits("我好攰") > 0, true);
  ck("川话 不巴适 命中", U.dialectHits("我不巴适") > 0, true);
  ck("东北 闹心 命中", U.dialectHits("我闹心") > 0, true);
  ck("上海 触气 命中", U.dialectHits("我触气") > 0, true);
  ck("闽南 艱苦 命中", U.dialectHits("我足艱苦") > 0, true);
  ck("一句两形态 命中2", U.dialectHits("我嬲到瞓唔着"), 2);
  // 普通话干净句不得被加分（否则方言表就是给所有句子乱加分的噪声源）
  ck("普通话 我今天很烦躁 不加分", U.dialectHits("我今天很烦躁"), 0);
  ck("普通话 我喊他来帮忙 不加分", U.dialectHits("我喊他来帮忙"), 0);
  ck("普通话 我回去了 不加分", U.dialectHits("我回去了"), 0);
  // 🔴 红线十 防双计：目标词已直接出现在文本里 ⇒ 方言层不计（词表层已经给过一次分）
  ck("红线十 已含烦躁 不再计方言分", U.dialectHits("我很烦躁闹心"), 0);
  ck("红线十 我难受不巴适 不再计", U.dialectHits("我难受不巴适"), 0);
  // 🔴 红线十一 否定式：语义反转让「巴适」在「不巴适」里**不得**加成「舒服」——
  //    这条是被本判据当场抓出来的真缺陷（初版把否定句加成正面情绪，比漏识别更糟）
  ck("红线十一 不闹心 不计分", U.dialectHits("我不闹心"), 0);
  ck("红线十一 不艱苦 不计分", U.dialectHits("我不艱苦"), 0);
  ck("红线十一 不巴适 只算难受1条", U.dialectHits("我不巴适"), 1);
  ck("红线十一 好巴适 仍算舒服", U.dialectHits("好巴适"), 1);
  ck("空串 不加分", U.dialectHits(""), 0);
  return o;
}"""

# 方言表里"噪声候选"的分数对照：证明方言加分确实是这批样本翻盘的原因（不是碰巧置信度够）
E9B_JS = """() => {
  const U = window.VoiceCall._unit; const o = [];
  // 浮点一律容差比较：0.2*1.5 在 JS 里是 0.30000000000000004，用严格相等会把「算术正确」
  // 误报成缺陷（与 r173 把 cer 的分母写错是同族坑：先怀疑判据写法，再怀疑实现）
  const ck = (n, got, want) => o.push([n, typeof want === "number"
    ? Math.abs(got - want) < 1e-6 : got === want, got, want]);
  const sc = (t, c) => U.altScore({ transcript: t, confidence: c }, t);
  // 红线九 序关系：方言形态加分 **必须小于** 词表直接命中
  const dia = sc("我闹心", 0) - sc("我闹啥", 0);          // 方言层的净贡献
  const lex = sc("我很烦躁", 0) - sc("我狠烦早", 0);        // 词表层的净贡献
  ck("红线九 方言权重<词表权重", dia > 0 && dia < lex, true);
  ck("红线九 方言净贡献=1.0", Math.round(dia * 100) / 100, 1);
  ck("红线九 词表净贡献=1.5", Math.round(lex * 100) / 100, 1.5);
  // 模块缺失时的降级：与改动前逐字同分（dialectHits 抛异常也要走这条路）
  const keep = window.ASRNormalize.dialectHits;
  window.ASRNormalize.dialectHits = undefined;
  ck("降级 dial 缺失时按旧口径", sc("我闹心", 0.2), 0.3);
  window.ASRNormalize.dialectHits = () => { throw new Error("boom"); };
  ck("降级 dial 抛异常时按旧口径", sc("我闹心", 0.2), 0.3);
  window.ASRNormalize.dialectHits = keep;
  ck("恢复后 仍按新口径", sc("我闹心", 0.2) > 0.3, true);
  return o;
}"""


def run(page, cases):
    """逐条回放：把候选喂进浏览器内真实的 pickBest + ASRNormalize.normalize，拿回选中条/清洗后/各候选得分

    诊断得分只对【合法形状】的候选求：altScore 内部直接 t.indexOf(w)，不判空；
    生产路径里 pickBest 先过滤掉非字符串再打分，所以它永远遇不到 null。
    这里是诊断循环，越界调用等于自己制造崩溃 —— 故 null/非字符串一律记 None 不打分。

    ⚠ 清洗值在**浏览器内**算完再取回，不在本进程用 Python 复刻一遍：
      复刻等于测我自己的实现而不是测被测模块，那是本仓判据最常见的一类假绿。
    """
    rows = []
    for case in cases:
        cands = to_engine(case)
        got = page.evaluate("(c) => window.VoiceCall._unit.pickBest(c)", cands)
        norm = page.evaluate("(t) => window.ASRNormalize.normalize(t)", got)
        scores = page.evaluate(
            "(c) => c.map(a => (typeof a.transcript === 'string'"
            " ? window.VoiceCall._unit.altScore(a, a.transcript) : null))", cands)
        rows.append({"id": case["id"], "scenario": case["scenario"], "scene": case.get("scene", "-"),
                     "got": got, "norm": norm, "scores": scores, "ref": case.get("ref", "")})
    return rows


def main():
    if "--selftest" in sys.argv[1:]:
        return selftest()
    cases, problems = load()
    if problems:
        for p in problems:
            print("  -", p)
        print("ASR-REPLAY-FAIL fixture 不合格 %d 项" % len(problems))
        return 1
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ASR-REPLAY-UNVERIFIED playwright 不可用")
        return 2
    try:
        with sync_playwright() as p:
            browser, face = launch(p, args=["--autoplay-policy=no-user-gesture-required"],
                                   label="asr_replay_check")
            page = browser.new_page()
            try:
                page.goto(URL, wait_until="load", timeout=30000)
            except Exception as e:  # noqa: BLE001
                browser.close()
                print("ASR-REPLAY-UNVERIFIED 页面打不开 %s（%s）—— 没测到不得判绿" % (URL, str(e)[:80]))
                return 2
            seam = ("() => !!(window.VoiceCall && window.VoiceCall._unit && window.VoiceCall._unit.pickBest"
                    " && window.VoiceCall._unit.altScore)")
            try:
                page.wait_for_function(seam, timeout=12000)
            except Exception as e:  # noqa: BLE001
                browser.close()
                print("ASR-REPLAY-UNVERIFIED 12s 内取不到 _unit.pickBest/altScore 这条缝"
                      "（build 面缺件或装载未完成：%s）—— 没测到不得判绿" % str(e)[:90])
                return 2
            if not page.evaluate(
                    "() => !!(window.ASRNormalize && window.ASRNormalize._unit"
                    " && window.ASRNormalize._unit.normalize)"):
                browser.close()
                print("ASR-REPLAY-UNVERIFIED 取不到 ASRNormalize（r174 起它是生产依赖，缺件=build 面缺件）"
                      "—— 没测到不得判绿")
                return 2
            e6 = page.evaluate(E6_JS)
            e6bad = [r for r in e6 if not r[1]]
            if e6bad:
                browser.close()
                for r in e6bad:
                    print("  - E6 %s: got %r want %r" % (r[0], r[2], r[3]))
                print("ASR-REPLAY-FAIL E6 清洗纯函数 %d/%d 条不符（归一化是 A2 的核心，不能带病接线）"
                      % (len(e6bad), len(e6)))
                return 1
            # r175/A3：E7 断句合并 + E8 自适应噪声门 —— 与 E6 同为「带病不许接线」的门禁
            e7 = page.evaluate(E7_JS)
            e8 = page.evaluate(E8_JS)
            e9 = page.evaluate(E9_JS)
            e9b = page.evaluate(E9B_JS)
            for tag, what, rows in (("E7", "断句碎片合并", e7), ("E8", "自适应噪声门+采集链", e8),
                                    ("E9", "方言形态层", e9), ("E9B", "方言权重序与降级", e9b)):
                bad = [r for r in rows if not r[1]]
                if bad:
                    browser.close()
                    for r in bad:
                        print("  - %s %s: got %r want %r" % (tag, r[0], r[2], r[3]))
                    print("ASR-REPLAY-FAIL %s %s %d/%d 条不符（%s，不能带病接线）"
                          % (tag, what, len(bad), len(rows),
                             "A3 前置预处理是需求③的落地" if tag in ("E7", "E8")
                             else "A4 方言形态层是需求②在本仓架构下唯一的落地面"))
                    return 1
            lex = set(page.evaluate(LEX_JS))
            if not lex:
                browser.close()
                print("ASR-REPLAY-UNVERIFIED EmotionEngine.LEX 取不到（词表 seam 缺失）")
                return 2
            try:
                rows = run(page, cases)
            except Exception as e:  # noqa: BLE001
                # ⚠ 内部缺陷与环境未验必须三分：seam/浏览器取不到才是「没测到」(rc=2)，
                #   这里已经拿到浏览器与词表，回放过程自己炸了 = 判据自身有 bug (rc=1)，
                #   打成 UNVERIFIED 等于给崩溃发通行证（本仓排障表已记过这条同族事故）。
                browser.close()
                print("  - 回放过程内部异常：%s: %s" % (type(e).__name__, str(e)[:160]))
                print("ASR-REPLAY-FAIL 判据自身崩了（不是环境未验）")
                return 1
            browser.close()
    except Exception as e:  # noqa: BLE001
        print("ASR-REPLAY-UNVERIFIED 浏览器不可用：%s" % str(e)[:140])
        return 2

    npass = nfail = nunv = ngap = 0
    gaps = []
    before, after = [], []
    miss_src = []        # 需求①：判红样本的误差归因（error_source）
    groups = {}          # 需求①：方言 × 场景二维基线矩阵（挑对率 + 清洗后 CER）
    for case, row in zip(cases, rows):
        st, note = check_case(case, row["got"], lex, row["norm"])
        g = groups.setdefault((row["scenario"], row["scene"]), {"n": 0, "ok": 0, "cer": []})
        g["n"] += 1
        if st == "PASS":
            npass += 1
            g["ok"] += 1
        elif st == "FAIL":
            nfail += 1
            miss_src.append("%s: %s" % (row["id"], case.get("error_source") or "未标注"))
        elif st == "GAP":
            ngap += 1
            gaps.append(row["id"])
        else:
            nunv += 1
        # E5 的口径：同一批参考文本下，清洗前后各量一次 CER ⇒ 相对降幅
        if row["ref"] and row["got"]:
            before.append(cer(row["got"], row["ref"]))
            after.append(cer(row["norm"], row["ref"]))
            g["cer"].append(cer(row["norm"], row["ref"]))
        tag = "E1a/E1b/E1n" if st == "PASS" else st
        pretty = [("skip" if x is None else round(x, 2)) for x in row["scores"]]
        shown = row["norm"] if (row["norm"] and row["norm"] != row["got"]) else row["got"]
        cer_txt = ("CER %.3f→%.3f" % (cer(row["got"], row["ref"]), cer(row["norm"], row["ref"]))
                   if row["ref"] else "CER  -（无参考，E5 不计入）")
        print("  %-22s %-6s %-10s %s  %s  scores=%s%s"
              % (row["id"], row["scenario"], tag, shown[:24], cer_txt, pretty,
                 ("  ← " + note) if note else ""))
    mb = sum(before) / len(before) if before else 0.0
    ma = sum(after) / len(after) if after else 0.0
    drop = (mb - ma) / mb if mb > 0 else 0.0
    blocks = (("E6", "清洗", e6), ("E7", "断句", e7), ("E8", "噪声门", e8),
              ("E9", "方言层", e9), ("E9B", "方言权重", e9b))
    tally = "  ".join("%s%s=%d/%d" % (t, w, len(r) - len([x for x in r if not x[1]]), len(r))
                      for t, w, r in blocks)
    print("引擎=%s  词表词数=%d  样本=%d  %s  分布=%s"
          % (face, len(lex), len(cases), tally, ", ".join(sorted({r["scenario"] for r in rows}))))
    # 需求①的基线矩阵：方言 × 场景二维读数（挑对率 + 清洗后 CER）
    print("— 场景基线矩阵（构造样本，非引擎真实准确率）—")
    for k in sorted(groups, key=lambda x: (x[0] not in ("普通话",), x[0], x[1])):
        g = groups[k]
        cs = g["cer"]
        m = ("%.3f" % (sum(cs) / len(cs))) if cs else "  -  "
        print("  %-8s %-10s 样本=%2d  挑对=%2d/%2d (%3.0f%%)  清洗后CER=%s"
              % (k[0], k[1], g["n"], g["ok"], g["n"], 100.0 * g["ok"] / g["n"], m))
    if miss_src:
        print("  误差归因（判红样本的 error_source）：%s" % "；".join(sorted(set(miss_src))))
    print("E5 归一化增益：构造样本 CER 均值 %.4f → %.4f，相对下降 %.1f%%（阈值 ≥5%%）"
          % (mb, ma, drop * 100))
    print("⚠ CER 是【构造样本上的编排层读数】，不是引擎准确率；不代表方言真实识别率")
    if nfail:
        print("ASR-REPLAY-FAIL 通过=%d 判红=%d 前提不成立=%d 已知缺口=%d" % (npass, nfail, nunv, ngap))
        return 1
    if nunv:
        print("ASR-REPLAY-UNVERIFIED 通过=%d 前提不成立=%d 已知缺口=%d（样本前提缺失，未测到的不判绿）"
              % (npass, nunv, ngap))
        return 2
    if drop < 0.05:
        print("ASR-REPLAY-FAIL E5 归一化相对下降仅 %.1f%%（阈值 5%%）—— 清洗没产生可测增益" % (drop * 100))
        return 1
    print("ASR-REPLAY-PASS 样本=%d 全过 %s 缺口=%d%s E5下降=%.1f%%"
          % (len(cases), tally, ngap, ("（%s）" % ",".join(gaps)) if gaps else "", drop * 100))
    return 0


if __name__ == "__main__":
    # r173 兜底：未捕获异常必须留下具名结论行，否则电池只见 rc≠0（BLIND-RED）
    from check_instrument import install_excepthook
    install_excepthook("ASR-REPLAY")
    raise SystemExit(main())
