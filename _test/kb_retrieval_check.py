#!/usr/bin/env python3
"""r178-KB17：检索判据离线常驻化（kb_retrieval_check.py）。

为什么必须立：第 16 轮的 K8 是**浏览器腿**，依赖 8123 服务 + chromium，重且慢（单次 ~20s）；
而 kbBlockFor 的改动是主线，它应该有一条**快的、离线的**回归腿，否则下次改注入面就是裸奔。

两条纪律（README §7.2）：
1. 不得造第二把尺 —— 本件**只复述 kbBlockFor 的判据本体**（从 src/js/chat-agent.js 抽函数体，
   eval 后直接调 kbBlockFor），不另立打分公式、不另立阈值。任何"本件自己的判据"都是违规。
2. 期望域集合**抄 K8 的同一份**（见 EXPECTED），两处漂移即红 —— 漂移说明要么 K8 的期望域写错了，
   要么 kbBlockFor 的行为变了，必须人工裁决，不能让两个尺子各自自洽。

零浏览器、零网络、零密钥。
"""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = [
    ("sadness", "我最近总是提不起劲，做什么都没意思", ["SL"]),
    ("sadness", "我为什么会反复想同一件难过的事，心理学上有什么原理？", ["EW", "FM"]),
    ("fear", "我不知道自己想要什么，选专业选得好迷茫", ["ID"]),
    ("fear", "我拿到两个 offer，选哪个好，好焦虑", ["AX"]),
    ("sadness", "我妈总拿我跟别人家孩子比，我很难受", ["FM"]),
    ("anger", "室友总是不打招呼就用我东西，我快气死了", ["NG"]),
    ("sadness", "分手三个月了，我还是走不出来", ["RS", "RJ"]),
    ("sadness", "我总觉得别人在背后议论我", ["SC", "SH"]),
    ("fear", "马上要答辩了，我睡不着觉", ["SL", "AX"]),
    ("sadness", "我每天都刷手机到凌晨，停不下来", ["EM", "IN"]),
    ("joy", "今天跟朋友开了个玩笑，大家都笑了", ["HU"]),
    ("calm", "我想试试冥想，有用吗", ["MI"]),
    ("sadness", "我是不是太敏感了，一点小事就崩溃", ["CB", "PR"]),
    ("sadness", "我很努力了但还是觉得自己不够好", ["HK", "CB"]),
    ("sadness", "家里人对我的期待太高了，我喘不过气", ["FM"]),
    ("sadness", "我总是拖延，作业拖到最后一天", ["PR"]),
    ("fear", "我害怕跟陌生人说话，是不是社交恐惧", ["NG", "FE"]),
    ("sadness", "奶奶去世了，我一直缓不过来", ["GR"]),
    # r178-KB17：WV 域首次进本件（与 K8 同一份期望域集合，反漂移）。
    ("fear", "我拿到两个 offer，选哪个好，好纠结", ["WV"]),
    # r178-KB19：补「找工作」后重加本条（N15 闭环）。
    ("fear", "毕业了不知道找什么工作，好慌", ["ID"]),
    ("sadness", "嗯嗯", []),
]


def load_kb_block():
    src = (ROOT / "src" / "js" / "chat-agent.js").read_text(encoding="utf-8")
    start = src.index("/* r178-KB16：冷域触发词表")
    fstart = src.index("function kbBlockFor(", start)
    i = src.index("{", fstart); depth = 0; end = -1
    for j in range(i, len(src)):
        c = src[j]
        if c == "{": depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0: end = j + 1; break
    slice_ = src[start:end]
    kbtext = (ROOT / "src" / "data" / "psych-kb.js").read_text(encoding="utf-8")
    m = re.search(r"window.__XINYU_PSYCH_KB__\s*=\s*(\{[\s\S]*\})", kbtext)
    KB_json = m[1]
    js = 'global.window={__XINYU_PSYCH_KB__:' + KB_json + '};\nconst EMPTY_KB={block:"",used:[]};\n' + slice_ + '\nconst fs=require("fs");\nconst CASES=JSON.parse(fs.readFileSync(process.argv[2],"utf8"));\nconst out=[];for(const [emo,txt,expect] of CASES){const r=kbBlockFor(emo,txt,1600);out.push({emo,txt,used:r.used.map(e=>e.id),empty:!r.used.length});}\nprocess.stdout.write(JSON.stringify(out));\n'
    # r187 修（一手：CI 全新 clone 上 FileNotFoundError _temp/_kb_block.js）：
    #   _temp/ 是 gitignore 的运行态目录，全新 clone 上不存在 ⇒ write_text 直接崩。
    #   本件 2026-10-16 才首次入库上 CI（G16 第五腿抓出的 7 件之一），此前从未在
    #   全新 clone 上跑过 ⇒ 缺陷一直隐形。修法 = 落盘前 mkdir（parents 防上层也缺）。
    #   同轮去掉紧随其后的三行重复代码（p 定义 + write_text 写了两遍，纯搬运事故）。
    tmp = ROOT / "_temp"
    tmp.mkdir(parents=True, exist_ok=True)
    p = tmp / "_kb_block.js"
    p.write_text(js, encoding="utf-8")
    # 注：exec 是 Python 词法，跑不了 JS ⇒ 走 node。js 只负责把函数体写到 _temp/_kb_block.js。
    cases_path = tmp / "_kb_cases.json"
    cases_path.write_text(json.dumps(CASES, ensure_ascii=False), encoding="utf-8")
    import subprocess
    sub_out = subprocess.run(["node", str(p), str(cases_path)], capture_output=True, text=True)
    if sub_out.returncode != 0:
        raise RuntimeError("node _kb_block.js failed: " + sub_out.stderr)
    return json.loads(sub_out.stdout)


def main():
    out = load_kb_block()
    # 反作弊：断言抽出来的确实是 r178-KB16 的三路判据，不是别的版本
    src = (ROOT / "src" / "js" / "chat-agent.js").read_text(encoding="utf-8")
    if "DOMAIN_KW" not in src:
        print("KB-RETRIEVAL-FAIL: src/js/chat-agent.js 里没有 DOMAIN_KW，抽出来的不是 r178-KB16 判据")
        return 1
    miss = 0; wrong = 0; inject = 0
    cases_path = ROOT / "_temp" / "_kb_cases.json"
    cases_path.write_text(json.dumps(CASES, ensure_ascii=False), encoding="utf-8")
    for emo, txt, expect in CASES:
        r = out.pop(0)
        got = {e.split("-")[1] for e in r["used"]}
        if not got:
            if expect:
                miss += 1; inject += 1
                print("  MISS  [" + emo + "] " + txt[:20] + " -> (零注入，期望域 " + ",".join(expect) + " 未命中)")
            continue  # 期望域为空 = 纯倾诉轮，零注入是期望行为，不计 fail
        if not (got & set(expect)):
            wrong += 1
            print("  WRONG [" + emo + "] " + txt[:20] + " -> " + ",".join(sorted(got)) + " 期望 " + ",".join(sorted(expect)))
    # 「嗯嗯」零注入是**期望行为**（纯倾诉轮不注入），不是 fail；fail 只有两类：
    # ① 本该命中却零注入（冷域主诉没被 DOMAIN_KW 兜住）② 命中了但域不对。
    ok = (miss == 0 and wrong == 0)
    print("KB-RETRIEVAL-" + ("PASS" if ok else "FAIL") + ": " + str(len(CASES)) + " 条主诉，期望域未命中 " + str(wrong) + " 条、纯倾诉轮误注入 " + str(inject) + " 条")
    return 0 if ok else 1



def _run_with_override(dom_override=None, case_override=None):
    """变异腿用：在内存里改判据本体（DOMAIN_KW）或期望域（CASES），跑完返回 rc。
    不动 src、不动 _temp 残留。"""
    import copy
    cases = [list(c) for c in CASES]
    if case_override:
        for idx, new in case_override.items():
            cases[idx][2] = new
    cases_path = ROOT / "_temp" / "_kb_cases.json"
    cases_path.write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")
    src = (ROOT / "src" / "js" / "chat-agent.js").read_text(encoding="utf-8")
    if dom_override:
        src = src.replace(dom_override[0], dom_override[1])
    start = src.index("/* r178-KB16：冷域触发词表")
    fstart = src.index("function kbBlockFor(", start)
    i = src.index("{", fstart); depth = 0; end = -1
    for j in range(i, len(src)):
        c = src[j]
        if c == "{": depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0: end = j + 1; break
    slice_ = src[start:end]
    kbtext = (ROOT / "src" / "data" / "psych-kb.js").read_text(encoding="utf-8")
    m = re.search(r"window.__XINYU_PSYCH_KB__\s*=\s*(\{[\s\S]*\})", kbtext)
    KB_json = m[1]
    js = 'global.window={__XINYU_PSYCH_KB__:' + KB_json + '};\nconst EMPTY_KB={block:"",used:[]};\n' + slice_ + '\nconst fs=require("fs");\nconst CASES=JSON.parse(fs.readFileSync(process.argv[2],"utf8"));\nconst out=[];for(const [emo,txt,expect] of CASES){const r=kbBlockFor(emo,txt,1600);out.push({used:r.used.map(e=>e.id),empty:!r.used.length});}\nprocess.stdout.write(JSON.stringify(out));\n'
    p = ROOT / "_temp" / "_kb_block.js"
    p.write_text(js, encoding="utf-8")
    import subprocess
    sub_out = subprocess.run(["node", str(p), str(cases_path)], capture_output=True, text=True)
    if sub_out.returncode != 0:
        return 1, "node failed: " + sub_out.stderr
    out = json.loads(sub_out.stdout)
    miss = wrong = inject = 0
    for o, (_, _, expect) in zip(out, cases):
        got = {e.split("-")[1] for e in o["used"]}
        if not o["used"]:
            if expect:
                miss += 1; inject += 1
            continue
        if not (got & set(expect)):
            wrong += 1
    return (0 if (miss == 0 and wrong == 0) else 1), "miss=%d wrong=%d inject=%d" % (miss, wrong, inject)


def selftest():
    # 腿 1：真面 —— 当前 src + 当前 CASES，必须 PASS
    rc1, d1 = _run_with_override()
    # 腿 2：判据本体变异 —— 把 MI 域的触发词「冥想」换成「打坐」，「我想试试冥想」就该命中不到 MI 了
    rc2, d2 = _run_with_override(dom_override=('MI: ["冥想", "正念"]', 'MI: ["打坐", "正念"]'))
    # 腿 3：期望域漂移 —— 把「奶奶去世了」的期望域从 GR 改成 FM（模拟 K8 与本件期望域不一致）
    rc3, d3 = _run_with_override(case_override={18: ["FM"]})
    legs = [
        ("真面（当前 src + 当前 CASES）", rc1, d1),
        ("变异腿：MI 域触发词「冥想」→「打坐」", rc2, d2),
        ("变异腿：期望域 GR→FM 漂移", rc3, d3),
    ]
    # 判据有效性 = 真面绿 + 变异腿红（README 7.2 的「先证判尺再信读数」）。
    # 变异腿恒绿说明判据是橡皮图章（永远 PASS），恒红说明判据自己崩了 —— 两种都判 FAIL。
    allok = (rc1 == 0 and rc2 != 0 and rc3 != 0)
    for name, rc, d in legs:
        print("  " + ("OK  " if rc == 0 else "FAIL") + " " + name + "  （" + d + "）")
    print("KB-RETRIEVAL-SELFTEST-" + ("PASS" if allok else "FAIL") + ": " + str(len(legs)) + " 腿（真面绿 + 变异腿红 = 判据咬合）")
    return 0 if allok else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    sys.exit(main())
