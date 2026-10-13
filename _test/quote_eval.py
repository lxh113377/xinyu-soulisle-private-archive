# -*- coding: utf-8 -*-
"""quote_eval.py — 表达语料库效果验收：全自动盲评对照
  （r117 两臂 → r133 三臂归因 → r134 多评委×重复×60 例 → r171 四臂＋逐例配对＋分层）

机制（四段）：
  ① 生成：浏览器内直调 `ChatAgent.respond()`，对每条测试用例**同轮**生成四臂回复——
     full（全量注入：head+规则+候选，候选前 2 条带「（用：适配条件）」）/
     nofit（r171 新增：同样注入候选但**剥掉适配条件**，用来单独回答「fit 有没有用」）/
     rules-only（只给 head+规则、零候选，归因「规则文案本身」的作用）/
     old（清空 entries 模拟注入前）。同一页面、同一模型、同一温度，唯一变量 = 注入形态。
     各臂注入片段都自带「删旗标」归一化，臂间互不污染；每例跑完再 RESTORE 兜底。
  ② 重复（r134）：每臂每例生成 `--reps` 份（默认 2）——r133 实测「三维方向会翻」的根因之一
     是单样本生成；同轮重复后按例内取均，判据不再由一次抽样的运气决定。
  ③ 盲评：3 评委（product/linguist/peer，temperature=0）对两两对照做隐去版本标签的 A/B
     三维打分（适配度/自然度/丰富度，1-5）+ 生硬引用判定；每对 A/B 顺序按 (对,重复号,评委)
     各自随机（固定种子可复现）。主对照 full-vs-old 评**全部重复**；三条归因对照只评第 1 次
     重复（读数用途，控运行时长）。
  ④ 判据（r171 改判，三条线互不顶替）：
     ①效果门（挂 rc，只判「不许变差」）：主对照的**逐例配对均差**在全量与承载面都不得 < -TOL，
       full 生硬引用率 ≤ HARD_REFUSE。
     ②收益读数（只印不闸）：全量/承载面 × 三维 × 各对照的「已证实/未证实/受损」+ 符号检验 p。
     ③分层读数：承载面（倾诉/评判/庆祝/自引——素材该有用武之地的阶段）与让位面（求解释/求建议/
       日常/短消息——规则明写可放弃融入）分别算。r134 那个「三维无稳定净收益」的读数有一半是
       量法造成的：让位层占半数用例且两臂本来就该一样，等权平均把承载面的效应稀释掉了。
     评委间一致性与评委偏差仍只报告不设门（r133 教训：噪声大于信号时加硬门只会制造假红/逼虚报）。
     明细落 _test/_shots/quotes_eval_detail_r171.json（不覆盖 r117/r133/r134 的历史明细）。
     本脚本**不重写** 交付物/表达语料库/验收报告.md（收口由书记员按汇总追加）。
  --smoke：机制自证（四臂生成 + 多评委判分可解析 + 配对统计 + 明细落盘），只取前 4 例、1 重复、
     2 评委，**跳过效果门**（4 例撑不起三维判定；机制通 + 判分可解析即 PASS）。
  --selftest（r171 新增，零网络零浏览器）：配对统计与分层的纯函数自证 + 反例腿，
     覆盖 pair_arms / _arm_dim_scores / binom_p_two_sided / paired_stats / uplift_verdict /
     focus_subset / gate_fails；本件因此可在整跑电池里常驻（--exclude-llm 下也跑得动）。

跑法备注（r134 一手）：共享机器上 Start-Process 后台进程会被静默杀死 ⇒ 大用例集用
「python -c 导入本模块、切片 CASES 后调 main()」的分块前台跑，再用
`_test/quote_eval_merge.py` 合并明细重算（汇总逻辑仍唯一来源于本文件，禁造第二把尺）。

安全：Key 从 src/js/demo-config.js 动态读取（已 ignore 的本地文件），**任何输出与明细不落 Key**。
用法：python _test/quote_eval.py [--base http://127.0.0.1:8123] [--smoke] [--selftest]
      [--seed 42] [--judges 3] [--reps 2] [--cases N] [--focus all|heavy15]
退出码：0=PASS 1=FAIL（主对照效果门红）2=环境未验证/评委失败/子集形状漂移
"""
import argparse
import json
import math
import random
import re
import sys
import time
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "_test"))

DIMS = ("适配度", "自然度", "丰富度")
HARD_REFUSE = 0.10          # 主对照 full 臂生硬引用率上限
TOL = 0.1                   # 三维均分容差
CLEAN = ("ChatAgent.setCfg({}); "
         "localStorage.removeItem('peiliao.history.v1'); 1")
_DEL_FLAG = "delete window.__XINYU_WIT_QUOTES__.rulesOnly;"
_SAVE = ("if(!window.__XINYU_WIT_QUOTES_SAVE__){window.__XINYU_WIT_QUOTES_SAVE__="
         "window.__XINYU_WIT_QUOTES__.entries.slice()} ")
USE_FULL = (_SAVE + "window.__XINYU_WIT_QUOTES__.entries="
            "window.__XINYU_WIT_QUOTES_SAVE__.slice();delete window.__XINYU_WIT_QUOTES__.noFitOnly;"
            + _DEL_FLAG + " 1")
USE_NOFIT = (_SAVE + "window.__XINYU_WIT_QUOTES__.entries="
             "window.__XINYU_WIT_QUOTES_SAVE__.slice();" + _DEL_FLAG +
             "window.__XINYU_WIT_QUOTES__.noFitOnly=true; 1")
USE_OLD = (_SAVE + "window.__XINYU_WIT_QUOTES__.entries=[];"
           "delete window.__XINYU_WIT_QUOTES__.noFitOnly;" + _DEL_FLAG + " 1")
USE_RULES_ONLY = (_SAVE + "window.__XINYU_WIT_QUOTES__.entries=[];"
                  "window.__XINYU_WIT_QUOTES__.rulesOnly=true; 1")
RESTORE = ("window.__XINYU_WIT_QUOTES__.entries=window.__XINYU_WIT_QUOTES_SAVE__.slice();"
           "delete window.__XINYU_WIT_QUOTES__.noFitOnly;" + _DEL_FLAG + " 1")
ARMS = ("full", "nofit", "rules-only", "old")
ARM_SNIPPET = {"full": USE_FULL, "nofit": USE_NOFIT,
               "rules-only": USE_RULES_ONLY, "old": USE_OLD}
# 主对照 = full-vs-old（效果门只挂它）；三条归因对照只出读数不设门：
#   full-vs-nofit  → r171 新增，单独回答「带适配条件到底有没有用」（本轮唯一被改的机制）
#   full-vs-rules-only → 规则的文案本身有没有用（r133 起）
#   rules-only-vs-old → 只给规则不给素材相对不注入的位置（r133 起）
PAIRS = (("full", "old"), ("full", "nofit"), ("full", "rules-only"), ("rules-only", "old"))
MAIN_PAIR = PAIRS[0]

# ── 用例集：r117/r133 的 30 例（R1）+ r134 新增 30 例（R2）+ r171 每条补「沟通阶段」标签 ──
# R2 选题口径：开场倾诉/深度倾诉/求建议/庆祝/日常闲聊/关系问题/丧失/自我怀疑/同辈压力/
# 用户自己引用素材句/短消息——覆盖第 1 轮没测到的「阶段」与「引用边界」。
# r171 为什么要给每条打 stage：r134 的读数把 60 例**等权平均**，而 quoteRules 明写
# 「求解释的提问不用名言充数」「平静日常可放弃融入」⇒ 求解释/日常/短消息这些层里 full 与 old
# **本该几乎相同**，它们占了半数用例，于是真实效应在均分里被稀释掉（−0.05/−0.08/+0.04 那个读数）。
# 分层之后效果门只挂在承载面，让位面单独读数。标签由本轮逐条人工判定，判据写在每条上。
STAGES = ("倾诉", "评判", "庆祝", "求解释", "求建议", "日常", "自引", "短消息")
HEAVY_STAGES = ("倾诉", "评判", "庆祝", "自引")   # 承载面：素材该有用武之地的阶段
CASES_R1 = [
    ("sadness", "倾诉", "和谈了三年的女朋友分手了，感觉心里空了一块"),
    ("sadness", "评判", "考研二战又失败了，觉得自己特别没用"),
    ("sadness", "倾诉", "今天是我爸的忌日，我一个人在外地，很想他"),
    ("sadness", "评判", "朋友都说我该翻篇了，可我就是走不出来，是不是我太没出息了？"),
    ("sadness", "评判", "有时候觉得难过是件很丢人的事，我是不是不该总这样？"),
    ("joy", "庆祝", "今天收到了理想的 offer，第一时间想告诉全世界"),
    ("joy", "庆祝", "和冷战一个月的室友和好了，心里一块石头落地"),
    ("joy", "庆祝", "第一次跑完半程马拉松，觉得自己太棒了"),
    ("joy", "求解释", "开心的时候总担心乐极生悲，这种心态正常吗？"),
    ("joy", "求建议", "怎么才能把好状态留得久一点呢？"),
    ("anger", "倾诉", "组里有人把我做的方案说成是他的，气炸了"),
    ("anger", "倾诉", "室友半夜打游戏开麦，说过几次都不改"),
    ("anger", "倾诉", "被家里人拿去和表姐比较，越听越火大"),
    ("anger", "求建议", "我知道生气伤身，可就是咽不下这口气，怎么办？"),
    ("anger", "评判", "是不是我太敏感了，一点小事就炸？"),
    ("fear", "倾诉", "下周要毕业答辩了，一想到上台就心慌"),
    ("fear", "倾诉", "投了二十份简历都没有回音，怕自己真的找不到工作"),
    ("fear", "倾诉", "最近总失眠，怕身体是不是出问题了"),
    ("fear", "求建议", "别人都说不焦虑就赢了，可到底怎么才能不焦虑？"),
    ("fear", "评判", "我总是把还没发生的事想得很糟，这算毛病吗？"),
    ("calm", "日常", "考完试了，今天就想安安静静发会呆"),
    ("calm", "日常", "下雨天在宿舍听歌，感觉日子也可以这么慢"),
    ("calm", "日常", "晚上散步看到月亮很圆，想和人聊聊"),
    ("calm", "求解释", "平静的日子里总觉得少了点什么，这种空是正常的吗？"),
    ("calm", "求建议", "想慢慢把生活过好，有什么小建议吗？"),
    ("love", "倾诉", "好像喜欢上一起做项目的同学了，不知道要不要说"),
    ("love", "倾诉", "异地恋第三年，最近总觉得他没那么在乎我了"),
    ("love", "倾诉", "刷到前任的动态，还是会多看好几眼"),
    ("love", "评判", "喜欢一个人到失去自己，是不是很傻？"),
    ("love", "求解释", "怎么判断自己是真喜欢还是一时上头？"),
]

CASES_R2 = [
    ("sadness", "倾诉", "外婆去世一个月了，今天整理她的东西，突然就绷不住了"),
    ("sadness", "评判", "实习被辞退了，不敢跟家里说，觉得自己特别失败"),
    ("sadness", "评判", "我一直活在别人的期待里，突然不知道自己喜欢什么了"),
    ("sadness", "自引", "看到「欲买桂花同载酒，终不似，少年游」这句话，突然很想毕业后再也回不去的夏天"),
    ("sadness", "短消息", "嗯。"),
    ("joy", "庆祝", "比赛拿了一等奖，想第一时间跟人分享这份开心"),
    ("joy", "庆祝", "暗恋的人今天主动跟我说话了，原地开心到转圈"),
    ("joy", "庆祝", "攒了半年的钱，终于去了想去的演唱会"),
    ("joy", "庆祝", "帮了一个迷路的小孩，他跟我说谢谢的时候，我心里特别亮"),
    ("joy", "求解释", "开心完了又有点空，这种感觉正常吗"),
    ("anger", "倾诉", "小组作业全程我一个人做，汇报时队友抢功"),
    ("anger", "倾诉", "我妈又未经我同意翻我房间，还说我小题大做"),
    ("anger", "倾诉", "网购遇到商家欺诈，客服踢皮球，气到发抖"),
    ("anger", "倾诉", "被朋友当众开了个过分的玩笑，大家笑了，我只想逃走"),
    ("anger", "评判", "我知道不该为小事生气，但真的控制不住，事后又后悔"),
    ("fear", "倾诉", "保研面试下周开始，准备了很久还是怕讲不好"),
    ("fear", "倾诉", "刷到同龄人都在晒 offer，我连简历都不敢投"),
    ("fear", "倾诉", "第一次一个人在外地过年，有点慌"),
    ("fear", "倾诉", "总担心自己说错话，每次发消息都要删改好几遍"),
    ("fear", "评判", "如果考研失败了，我是不是就全完了"),
    ("calm", "日常", "周末晒着太阳看完了一本书，心里很静"),
    ("calm", "日常", "开始记录每天的三件小事，生活好像慢下来了"),
    ("calm", "日常", "在图书馆窗边看了一下午云，什么都没想"),
    ("calm", "求建议", "想养成早睡的习惯，有什么不着痕迹的小办法"),
    ("calm", "倾诉", "今天路过高中校门，突然很想跟那时候的自己说句话"),
    ("love", "倾诉", "和男朋友吵架后他总冷战，我受不了也不舍得分"),
    ("love", "求建议", "喜欢的人要毕业去别的城市了，该不该表白"),
    ("love", "倾诉", "我妈总拿我和别人家孩子比，我知道她爱我，可还是受伤"),
    ("love", "倾诉", "友情里三个人，我总感觉自己是多余的那个"),
    ("love", "求解释", "怎么才能既爱一个人，又不弄丢自己"),
]
CASES = CASES_R1 + CASES_R2
if len(CASES) != 60 or any(c[1] not in STAGES for c in CASES):
    raise SystemExit("QUOTE-EVAL-UNVERIFIED: 用例集形状漂移（须 60 条且 stage 全在枚举内）")


def focus_subset(kind, cases):
    """定向子集（r171，销 07 记录的「重情绪 15 例子集定向复测」）。纯函数，selftest 直打。

    heavy15 = 每种情绪取前 3 条**承载面**用例（sadness/anger/fear/love/joy 各 3 = 15）。
    为什么按情绪配额而不是按序号切前 15：前 15 条会全落在 sadness/joy/anger 三段里，
    等于换一种方式偏样本。返回**原索引**（1 起）列表，便于与全量明细对账。
    """
    if kind == "all":
        return list(range(1, len(cases) + 1))
    if kind != "heavy15":
        raise SystemExit("QUOTE-EVAL-UNVERIFIED: 未知 --focus 值 " + str(kind))
    per_emo, picked = {}, []
    for idx, (emo, stage, _t) in enumerate(cases, start=1):
        if stage not in HEAVY_STAGES or emo == "calm":
            continue
        if per_emo.get(emo, 0) >= 3:
            continue
        per_emo[emo] = per_emo.get(emo, 0) + 1
        picked.append(idx)
    if len(picked) != 15:
        raise SystemExit("QUOTE-EVAL-UNVERIFIED: heavy15 实取 %d 条（期望 15）" % len(picked))
    return picked

# ── 三评委（r134）：同一评分模板、不同专业视角，用评委间一致性代替「单一评委的真相」──
JUDGES = [
    {"name": "product",
     "sys": "你是资深心理陪伴产品评测专家。评审两位候选回复（A/B 顺序随机），"
            "只输出 JSON。评判不因回复长短加分，关注是否像真人陪伴者说的话。"},
    {"name": "linguist",
     "sys": "你是语言学教授，专长汉语表达与语体分析。评审两位候选回复（A/B 顺序随机），"
            "只输出 JSON。你特别关注：是否像真人在口语里会说的话（无机械感、无套话感、"
            "无总结腔、无翻译腔），以及语句镶嵌是否自然。"},
    {"name": "peer",
     "sys": "你是一名普通大学生，平时会找 AI 聊天倾诉。评审两条回复（A/B 顺序随机），"
            "只输出 JSON。你只凭直觉：哪条更像一个真诚的朋友在回你，哪条像机器在客套。"},
]
JUDGE_TMPL = """用户留言：{case}
候选回复 A：{a}
候选回复 B：{b}
请对 A、B 各打三项 1-5 整数分（5 最好）：
1) 适配度：是否切合用户此刻的情绪与具体处境（不跑题、不说教）
2) 自然度：像不像真人在说话（无机械感、无套话感、无总结腔）
3) 丰富度：表达是否饱满有层次（恰当的点拨或引用；为引而引不给高分）
再各判一位点：「生硬引用」= 是否出现硬贴式引经据典/堆砌名言/文不对题引用（true/false）。
只输出 JSON：{{"A":{{"适配度":n,"自然度":n,"丰富度":n,"生硬引用":true|false}},"B":{{...}},"winner":"A|B|平"}}"""


def read_llm_cfg():
    """从已 ignore 的 demo-config.js 动态读 base/key/model（只进内存，不进任何输出）。"""
    text = (ROOT / "src" / "js" / "demo-config.js").read_text(encoding="utf-8")
    base = re.search(r'base:\s*"([^"]+)"', text)
    key = re.search(r'key:\s*"([^"]+)"', text)
    model = re.search(r'model:\s*"([^"]+)"', text)
    if not (base and key and model):
        return None
    return {"base": base.group(1), "key": key.group(1), "model": model.group(1)}


def llm_call(cfg, messages, temperature=0.0, max_tokens=500):
    body = json.dumps({"model": cfg["model"], "messages": messages,
                       "temperature": temperature, "max_tokens": max_tokens}).encode("utf-8")
    req = urllib.request.Request(cfg["base"].rstrip("/") + "/chat/completions", data=body,
                                 headers={"Content-Type": "application/json",
                                          "Authorization": "Bearer " + cfg["key"]})
    with urllib.request.urlopen(req, timeout=90) as r:
        data = json.loads(r.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"].strip()


def parse_judge(raw):
    m = re.search(r"\{[\s\S]*\}", raw or "")
    if not m:
        return None
    try:
        j = json.loads(m.group(0))
    except Exception:
        return None
    for side in ("A", "B"):
        d = j.get(side) or {}
        for dim in DIMS:
            v = d.get(dim)
            if not isinstance(v, (int, float)) or not (1 <= v <= 5):
                return None
    if j.get("winner") not in ("A", "B", "平"):
        return None
    return j


def cited_rate(replies, entries):
    """引用检出率（报告级指标）：素材句去标点后按 8 字滑窗检测是否出现在回复里。
    粗糙但可复现；用途是证明"素材真的被用上了"（防"机制空转、评语全靠自然度"）。"""
    strip_re = re.compile(r"[\s，。！？、；：\"'（）()【】\[\]~·—…\u2011\-]")

    def hit(reply):
        r = strip_re.sub("", reply or "")
        for e in entries:
            q = strip_re.sub("", e.get("quote") or "")
            if len(q) < 6:
                continue
            for i in range(0, max(1, len(q) - 7), 4):
                if q[i:i + 8] in r:
                    return True
            if len(q) <= 8 and q in r:
                return True
        return False

    return round(sum(1 for x in replies if hit(x)) / max(1, len(replies)), 3)


def _reply_text(x):
    """明细里的回复既可能是纯文本（r117/r133/r134 旧明细）也可能是 {reply, mode}（r171 起）。
    引用检出率只读文本，两种形态都要能读——判据的失败路径自己不能崩。"""
    return x["reply"] if isinstance(x, dict) else x


def _mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def _pstd(xs):
    """总体标准差（样本即全体关心对象：本轮全部用例），零样本回 0。"""
    if len(xs) < 2:
        return 0.0
    m = _mean(xs)
    return (sum((x - m) ** 2 for x in xs) / len(xs)) ** 0.5


def pair_arms(key):
    """把 "rules-only-vs-old"、"full-vs-rules-only" 这类键拆回两臂（"-vs-" 不会被臂名里的连字符误切）。"""
    a, sep, b = key.partition("-vs-")
    return (a, b) if sep else (None, None)


def _arm_dim_scores(pr, pa, pb, dim):
    """按**本样本实际看到的 A 是哪个臂**取分（A/B 顺序逐样本随机，配对统计必须按样本回查）。"""
    other = {pa: pb, pb: pa}
    out = {pa: [], pb: []}
    for s in pr["samples"]:
        a_arm = s["a_arm"]
        if a_arm not in other:
            continue
        out[a_arm].append(s["judge"]["A"][dim])
        out[other[a_arm]].append(s["judge"]["B"][dim])
    return out


def binom_p_two_sided(pos, neg):
    """符号检验精确双侧 p（X~Bin(n,0.5)）。只用差值符号 ⇒ 对评委分制的非线性与离群点稳健。"""
    n = pos + neg
    if n == 0:
        return 1.0
    k = min(pos, neg)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / float(2 ** n)
    return min(1.0, 2.0 * tail)


def paired_stats(rows, key, dim, stages=None):
    """逐例配对差值（本对 A 臂 − B 臂）。返回 (n, 均差, 差值列表)。

    为什么配对而不是两臂均分相减（r171 的量尺改判）：用例之间的难度差远大于臂间效应
    （r134 实测每维总体 std 0.5~0.8）。两臂各自求均再相减时这部分方差**全额进入差值**；
    配对后同一用例自己和自己比，它被当区组消掉，剩下的才是注入的净效应。
    """
    pa, pb = pair_arms(key)
    out = []
    for r in rows:
        pr = r.get("pairs", {}).get(key)
        if not pr:
            continue
        if stages is not None and r.get("stage") not in stages:
            continue
        sc = _arm_dim_scores(pr, pa, pb, dim)
        if not sc[pa] or not sc[pb]:
            continue
        out.append(_mean(sc[pa]) - _mean(sc[pb]))
    return len(out), _mean(out), out


def uplift_verdict(diffs):
    """收益判定三态（只出读数，不当门）：已证实 / 未证实 / 样本不足。
    r133 教训仍在：噪声大于信号时把「必须有收益」做成硬门，只会逼出虚报或制造假红。
    但这行读数必须**印出来**——老大要的是「到底有没有变好」的答案，不是又一句「容差内通过」。
    """
    n = len(diffs)
    if n < 2:
        return "样本不足（n=%d）" % n
    pos = sum(1 for d in diffs if d > 1e-9)
    neg = sum(1 for d in diffs if d < -1e-9)
    m = _mean(diffs)
    se = _pstd(diffs) / (n ** 0.5)
    p = binom_p_two_sided(pos, neg)
    state = "已证实" if (m > 0 and p < 0.05) else ("受损" if m <= -TOL else "未证实")
    return "%s 均差%+.2f±%.2f(SE) 胜/负/平 %d/%d/%d p=%.3f" % (
        state, m, se, pos, neg, n - pos - neg, p)


def gate_fails(main_psum):
    """① 效果门（纯函数，selftest 直打反例）：只判「不许变差」，判的是**逐例配对均差**。

    形状纪律（r171）：这条门**接受诚实的零收益**（差值 ≈ 0 必须能过），只拒「注入后更差」。
    理由：把「必须有收益」做成硬门，在噪声大于信号时会逼人虚报（r133 一手 +
    「门禁拒真话却放行自相矛盾写法」同族）。收益与否由 ②读数行回答，不由 rc 回答。
    """
    out = []
    for dim in DIMS:
        for scope, label in (("all", "全量"), ("heavy", "承载面")):
            n_pd = main_psum["paired_n_%s_%s" % (scope, dim)]
            m_pd = main_psum["paired_%s_%s" % (scope, dim)]
            if n_pd >= 2 and m_pd + TOL < 0:
                out.append("主对照 %s[%s]配对均差 %+.2f 越过容差 -%.1f（注入了反而更差）"
                           % (dim, label, m_pd, TOL))
    if main_psum["full_hard"] > HARD_REFUSE:
        out.append("主对照 full 生硬引用率 %.0f%% > 上限 %.0f%%"
                   % (main_psum["full_hard"] * 100, HARD_REFUSE * 100))
    return out


def _judge_and_report(seed, rows, bad, smoke, judges, reps,
                      detail_name="quotes_eval_detail_r171.json"):
    """汇总 + 判定 + 明细落盘（r171 四臂＋配对＋分层版）。三条线各管一件事，互不顶替：
      ① 效果门（挂 rc，只判「不许变差」）：主对照 full-vs-old 的**配对均差**在全量与承载面
         都不得 < -TOL；full 生硬引用率 ≤ HARD_REFUSE。形状上接受诚实的零收益（r133 教训）。
      ② 收益读数（只印不闸）：主对照与 full-vs-nofit 各维的 已证实/未证实/受损 + 符号检验 p。
      ③ 分层读数：承载面（素材该有用武之地）与让位面（规则明写可放弃融入）分开算，
         免得让位层「两臂本来一样」把承载面的效应稀释掉——r134 那个「三维无净收益」的读数
         有一半是这把尺的量法造成的。
    评委间一致性与评委偏差仍只报告不设门。明细落 _test/_shots/（r117/r133/r134 历史明细不触碰）。"""
    if rows:
        shots = ROOT / "_test" / "_shots"
        shots.mkdir(parents=True, exist_ok=True)
        detail = shots / detail_name
        detail.write_text(json.dumps({"seed": seed, "smoke": smoke, "judges": judges,
                                      "reps": reps, "rows": rows},
                                     ensure_ascii=False, indent=1), encoding="utf-8")
        print("明细 -> _test/_shots/%s" % detail_name)
    if bad:
        print("QUOTE-EVAL-UNVERIFIED: %d 条评委失败 ⇒ 不判绿" % len(bad))
        for x in bad[:5]:
            print("   · " + x)
        return 2

    try:
        from quote_wiring_check import load_entries
        entries = load_entries() or []
    except Exception:
        entries = []

    untagged = sum(1 for r in rows if not r.get("stage"))
    summary = {"cases": len(rows), "seed": seed, "judges": judges, "reps": reps,
               "arms": list(ARMS), "pairs": {}, "untagged_stage": untagged}
    fails, warns = [], []
    if untagged:
        warns.append("%d 例无 stage 标签（旧明细合并而来？）⇒ 分层读数按未标剔除" % untagged)
    for pa, pb in PAIRS:
        key = "%s-vs-%s" % (pa, pb)
        # 主对照收全部重复；归因对照只收第 0 次重复（与生成段对称，控时长）
        samples = [(r["pairs"][key], r.get("stage"), r["replies"]) for r in rows if key in r["pairs"]]
        psum = {}
        for arm in (pa, pb):
            per_case = {}          # case_idx -> [各 (rep,judge) 样本的三维]
            case_stage = {}        # case_idx -> 沟通阶段标签（r171 分层用）
            hard_n = hard_all = 0
            replies = []
            votes = {"win_pa": 0, "win_pb": 0, "tie": 0}
            for pr, stage, reps_text in samples:
                for s in pr["samples"]:
                    # a_arm 逐样本记录：A/B 顺序按 (对, 重复号, 评委) 各自随机，
                    # 汇总必须回到**本样本**实际看到的 A 是哪个臂（r134 首跑教训：
                    # 按 pair 级固定取分会把约半数样本的三维分与生硬率错位归臂）。
                    arm_side = "A" if s["a_arm"] == arm else "B"
                    d = s["judge"][arm_side]
                    per_case.setdefault(pr["case"], []).append(d)
                    case_stage[pr["case"]] = stage
                    hard_all += 1
                    if d.get("生硬引用"):
                        hard_n += 1
                    w = s["winner_arm"]
                    if w == pa:
                        votes["win_pa"] += 1
                    elif w == pb:
                        votes["win_pb"] += 1
                    else:
                        votes["tie"] += 1
                replies.extend(_reply_text(x) for x in reps_text[arm])
            case_means = {c: [_mean([d[dim] for d in ds]) for dim in DIMS]
                          for c, ds in per_case.items()}
            for dim_i, dim in enumerate(DIMS):
                vals = [cm[dim_i] for cm in case_means.values()]
                psum["%s_%s" % (arm, dim)] = round(_mean(vals), 3)
                psum["%s_%s_std" % (arm, dim)] = round(_pstd(vals), 3)
                # r171 分层：承载面 = 素材该有用武之地的阶段；让位面 = 有标但不属承载面
                hv = [cm[dim_i] for c, cm in case_means.items()
                      if case_stage.get(c) in HEAVY_STAGES]
                lv = [cm[dim_i] for c, cm in case_means.items()
                      if case_stage.get(c) and case_stage.get(c) not in HEAVY_STAGES]
                psum["%s_%s_heavy" % (arm, dim)] = round(_mean(hv), 3)
                psum["%s_%s_light" % (arm, dim)] = round(_mean(lv), 3)
            psum["%s_hard" % arm] = round(hard_n / hard_all, 3) if hard_all else 0.0
            psum["%s_n" % arm] = hard_all
            psum["%s_cite" % arm] = cited_rate(replies, entries)
            psum.update({k: v for k, v in votes.items()})
        # r171 配对差值（本对 A 臂 − B 臂）：全量与承载面各一份，收益判定只出读数
        for scope, stages in (("all", None), ("heavy", HEAVY_STAGES)):
            for dim in DIMS:
                n_pd, m_pd, diffs = paired_stats(rows, key, dim, stages)
                psum["paired_%s_%s" % (scope, dim)] = round(m_pd, 3)
                psum["paired_n_%s_%s" % (scope, dim)] = n_pd
                psum["uplift_%s_%s" % (scope, dim)] = uplift_verdict(diffs)
        # 评委间一致性：按 (case, rep) 聚合同对三评委的 winner 投票
        agree_una = agree_maj = agree_all = 0
        for pr, _stage, _rt in samples:
            for rep_key, vs in pr.get("votes_by_rep", {}).items():
                agree_all += 1
                ws = [v for v in vs if v]
                if len(set(ws)) == 1 and ws:
                    agree_una += 1
                if ws and max(ws.count(x) for x in set(ws)) >= 2:
                    agree_maj += 1
        psum["unanimous"] = round(agree_una / agree_all, 3) if agree_all else 0.0
        psum["majority"] = round(agree_maj / agree_all, 3) if agree_all else 0.0
        # 各评委均分（偏差检查）：主对照 full 臂按评委分组
        if key == "%s-vs-%s" % MAIN_PAIR:
            by_j = {}
            for pr, _stage, _rt in samples:
                for s in pr["samples"]:
                    arm_side = "A" if s["a_arm"] == pa else "B"
                    d = s["judge"][arm_side]
                    by_j.setdefault(s["judge_name"], []).append(d)
            psum["per_judge"] = {j: {dim: round(_mean([d[dim] for d in ds]), 3) for dim in DIMS}
                                 for j, ds in by_j.items()}
        summary["pairs"][key] = psum
        print("  [%s] %s[适%.2f 自%.2f 丰%.2f｜承载 适%.2f 自%.2f 丰%.2f｜生硬%.0f%% n=%d] vs "
              "%s[适%.2f 自%.2f 丰%.2f｜承载 适%.2f 自%.2f 丰%.2f｜生硬%.0f%% n=%d] "
              "胜 %d/%d/平 %d 一致(unanimous %.0f%%/majority %.0f%%)" % (
                  key,
                  pa, psum["%s_适配度" % pa], psum["%s_自然度" % pa], psum["%s_丰富度" % pa],
                  psum["%s_适配度_heavy" % pa], psum["%s_自然度_heavy" % pa],
                  psum["%s_丰富度_heavy" % pa],
                  psum["%s_hard" % pa] * 100, psum["%s_n" % pa],
                  pb, psum["%s_适配度" % pb], psum["%s_自然度" % pb], psum["%s_丰富度" % pb],
                  psum["%s_适配度_heavy" % pb], psum["%s_自然度_heavy" % pb],
                  psum["%s_丰富度_heavy" % pb],
                  psum["%s_hard" % pb] * 100, psum["%s_n" % pb],
                  psum["win_pa"], psum["win_pb"], psum["tie"],
                  psum["unanimous"] * 100, psum["majority"] * 100))
        for dim in DIMS:
            print("      配对%s: 全量 %+.2f(n=%d) %s ｜ 承载面 %+.2f(n=%d) %s" % (
                dim, psum["paired_all_%s" % dim], psum["paired_n_all_%s" % dim],
                psum["uplift_all_%s" % dim],
                psum["paired_heavy_%s" % dim], psum["paired_n_heavy_%s" % dim],
                psum["uplift_heavy_%s" % dim]))

    main = summary["pairs"]["%s-vs-%s" % MAIN_PAIR]
    # ── ① 效果门（纯函数 gate_fails，反例腿在 --selftest 里）──
    fails.extend(gate_fails(main))
    if entries and main["full_cite"] < 0.05:
        warns.append("full 引用检出率 %.0f%% < 5%%（素材本体直接引用信号弱；WARN 计，不催引）"
                     % (main["full_cite"] * 100))
    if main.get("unanimous", 0) < 0.4:
        warns.append("主对照评委 unanimous 一致率 %.0f%% < 40%%（三维读数按评委取均后解释；"
                     "不设门——r133 教训：噪声大于信号时加硬门只制造假红）"
                     % (main.get("unanimous", 0) * 100))
    if main["win_pa"] < main["win_pb"]:   # 主对照 pa=full / pb=old
        warns.append("主对照 full 胜票 %d < old 胜票 %d（报告级 WARN，容差门另判）"
                     % (main["win_pa"], main["win_pb"]))

    if smoke:
        print("QUOTE-EVAL-SMOKE-PASS: 四臂生成/多评委判分/配对统计/明细落盘全通（--smoke 跳过效果门，仅验机制）")
        for f in fails:
            print("   · (smoke 不设门，仅记录) " + f)
        for w in warns:
            print("   ~ " + w)
        return 0
    # 门面行自带关键数字：整跑聚合只留含判据词的那一行（r40b/r130 立的折行纪律）
    nf = summary["pairs"]["full-vs-nofit"]
    print("QUOTE-EVAL-%s: cases=%d arms=%d judges=%d reps=%d 主对照 full-vs-old 配对均差 "
          "全量[适%+.2f 自%+.2f 丰%+.2f] 承载面[适%+.2f 自%+.2f 丰%+.2f] "
          "fit净贡献(承载面 full-vs-nofit)[适%+.2f 自%+.2f 丰%+.2f] "
          "生硬引用full=%.0f%% 引用检出full=%.0f%%" % (
              "FAIL" if fails else "PASS", len(rows), len(ARMS), len(judges), reps,
              main["paired_all_适配度"], main["paired_all_自然度"], main["paired_all_丰富度"],
              main["paired_heavy_适配度"], main["paired_heavy_自然度"], main["paired_heavy_丰富度"],
              nf["paired_heavy_适配度"], nf["paired_heavy_自然度"], nf["paired_heavy_丰富度"],
              main["full_hard"] * 100, main["full_cite"] * 100))
    if "per_judge" in main:
        print("  评委均分（full 臂，偏差检查）: " + " | ".join(
            "%s[适%.2f 自%.2f 丰%.2f]" % (j, v["适配度"], v["自然度"], v["丰富度"])
            for j, v in sorted(main["per_judge"].items())))
    for f in fails:
        print("   · " + f)
    for w in warns:
        print("   ~ " + w)
    return 1 if fails else 0


def _stub_row(case_no, stage, pa, pb, scores):
    """构造一条 pair 明细（零网络）。scores = [(a_arm, A三维, B三维), ...]。"""
    key = "%s-vs-%s" % (pa, pb)
    samples = []
    for a_arm, a_dims, b_dims in scores:
        samples.append({"a_arm": a_arm, "judge_name": "product", "rep": 0,
                        "judge": {"A": dict(zip(DIMS, a_dims)),
                                  "B": dict(zip(DIMS, b_dims))},
                        "winner_arm": a_arm})
    pr = {"case": case_no, "samples": samples, "votes_by_rep": {0: ["x"]}}
    return {"i": case_no, "stage": stage, "pairs": {key: pr}}


def _stub_psum(diff=0.0, n=5, hard=0.0):
    p = {"full_hard": hard}
    for scope in ("all", "heavy"):
        for dim in DIMS:
            p["paired_%s_%s" % (scope, dim)] = diff
            p["paired_n_%s_%s" % (scope, dim)] = n
    return p


def selftest():
    """r171 判据自证（纯函数，零网络零浏览器）：配对统计、分层、符号检验、效果门各有反例腿。

    写这条的动因：本轮把「两臂均分相减」换成「逐例配对差值」，新逻辑一旦取错臂或错把
    让位层算进承载面，读数会**看起来更漂亮**而不是更红——这类错法必须由反例钉住，
    不能靠下次跑批肉眼发现。"""
    legs = []
    # 1) pair_arms：臂名含连字符也不得误切
    legs.append(("pair_arms 三形态",
                 pair_arms("rules-only-vs-old") == ("rules-only", "old")
                 and pair_arms("full-vs-rules-only") == ("full", "rules-only")
                 and pair_arms("没有对照标记") == (None, None)))
    # 2) 用例集形状：60 条、stage 全在枚举内
    legs.append(("用例集 60 条且 stage 合法",
                 len(CASES) == 60 and all(c[1] in STAGES for c in CASES)))
    # 3) heavy15：恰 15 条、五种情绪各 3、全属承载面、且都是真实存在的原序号
    p15 = focus_subset("heavy15", CASES)
    got = [(CASES[k - 1][0], CASES[k - 1][1]) for k in p15]
    per = {}
    for emo, stage in got:
        per[emo] = per.get(emo, 0) + 1
    legs.append(("heavy15 定向子集形状",
                 len(p15) == 15 and all(s in HEAVY_STAGES for _e, s in got)
                 and all(v == 3 for v in per.values()) and len(per) == 5))
    # 4) 反例：未知 --focus 值必须显式失败（不许静默当成全量）
    try:
        focus_subset("bogus", CASES)
        legs.append(("反例·未知 focus 值", False))
    except SystemExit:
        legs.append(("反例·未知 focus 值", True))
    # 5) 按样本回查臂：full 在 A 时取 A 分、在 B 时取 B 分（按 pair 级固定取会错位）
    r5 = _stub_row(1, "倾诉", "full", "old",
                   [("full", (4, 4, 4), (2, 2, 2)), ("old", (2, 2, 2), (5, 5, 5))])
    sc = _arm_dim_scores(r5["pairs"]["full-vs-old"], "full", "old", "适配度")
    legs.append(("按样本回查臂取分", sc["full"] == [4, 5] and sc["old"] == [2, 2]))
    # 6) 符号检验边界
    legs.append(("符号检验 p 三档",
                 abs(binom_p_two_sided(0, 0) - 1.0) < 1e-9
                 and abs(binom_p_two_sided(10, 0) - 2.0 / 1024) < 1e-9
                 and binom_p_two_sided(5, 5) == 1.0))
    # 7) 配对差值：全量 4 例（差值 2/2/2/0 ⇒ 均差 1.5）、承载面 3 例（均差 2.0，让位那条被剔）
    rows = [_stub_row(1, "倾诉", "full", "old", [("full", (4, 4, 4), (2, 2, 2))]),
            _stub_row(2, "庆祝", "full", "old", [("full", (5, 5, 5), (3, 3, 3))]),
            _stub_row(3, "评判", "full", "old", [("old", (2, 2, 2), (4, 4, 4))]),
            _stub_row(4, "求解释", "full", "old", [("full", (3, 3, 3), (3, 3, 3))])]
    n_all, m_all, _d_all = paired_stats(rows, "full-vs-old", "适配度", None)
    n_hv, m_hv, _d_hv = paired_stats(rows, "full-vs-old", "适配度", HEAVY_STAGES)
    legs.append(("配对差值 全量/承载面分母",
                 n_all == 4 and abs(m_all - 1.5) < 1e-9
                 and n_hv == 3 and abs(m_hv - 2.0) < 1e-9))
    # 8) 反例：不存在的对照键 ⇒ n=0（不得抛、不得当成 0 收益通过）
    n0, m0, _d0 = paired_stats(rows, "nofit-vs-old", "适配度", None)
    legs.append(("反例·缺对照键返回 n=0", n0 == 0 and m0 == 0.0))
    # 9) 反例：旧明细无 stage ⇒ 承载面读不到样本（分层必须显式落空，不许蒙混成全量）
    rows_ns = [dict(r) for r in rows]
    for r in rows_ns:
        r.pop("stage", None)
    legs.append(("反例·无 stage 标签时承载面 n=0",
                 paired_stats(rows_ns, "full-vs-old", "适配度", HEAVY_STAGES)[0] == 0
                 and paired_stats(rows_ns, "full-vs-old", "适配度", None)[0] == 4))
    # 10) 收益判定四态
    legs.append(("收益判定 已证实/未证实/受损/样本不足",
                 uplift_verdict([0.4, 0.3, 0.5, 0.2, 0.6, 0.1, 0.4, 0.2, 0.5, 0.3]).startswith("已证实")
                 and uplift_verdict([0.0] * 6).startswith("未证实")
                 and uplift_verdict([-0.3, -0.2, -0.4, -0.2, -0.3]).startswith("受损")
                 and uplift_verdict([0.2]).startswith("样本不足")))
    # 11) 效果门：诚实零收益必须过（拒真话的门会逼虚报）
    legs.append(("门·诚实零收益放行", gate_fails(_stub_psum(0.0)) == []))
    # 12) 反例：配对均差变差 ⇒ 全量与承载面各自点名（3 维 × 2 层 = 6 条）
    red = gate_fails(_stub_psum(-0.2))
    legs.append(("反例·配对均差越容差判红",
                 len(red) == 6 and any("承载面" in x for x in red) and any("全量" in x for x in red)))
    # 13) 反例：n 不足不判（样本 1 条的 -0.5 不是证据）
    legs.append(("反例·n=1 不判红", gate_fails(_stub_psum(-0.5, n=1)) == []))
    # 14) 反例：生硬率超上限判红
    legs.append(("反例·生硬引用率判红", len(gate_fails(_stub_psum(0.0, hard=0.2))) == 1))
    # 15) r171 上游预检：HTTP 402 必须归因到「余额」并**不带出 Key**（这是本轮空跑 38 分钟换来的腿）
    import urllib.error as _ue
    orig_call = globals()["llm_call"]
    try:
        def _boom(cfg, msgs, temperature=0.0, max_tokens=500):
            raise _ue.HTTPError("https://x/chat/completions", 402, "Payment Required", {}, None)
        globals()["llm_call"] = _boom
        ok_p, why_p = preflight_upstream({"base": "https://x/v1", "key": "sk-SECRET-DO-NOT-LEAK",
                                          "model": "deepseek-chat"})
        legs.append(("预检·402 归因到余额且不落 Key",
                     ok_p is False and "402" in why_p and "充值" in why_p
                     and "sk-SECRET-DO-NOT-LEAK" not in why_p))
    finally:
        globals()["llm_call"] = orig_call
    # 16) 明细两形态都要读得动（旧明细纯文本 / r171 起 {reply,mode}）——引用检出不能崩在失败路径上
    legs.append(("回复取文本兼容两形态",
                 _reply_text({"reply": "甲", "mode": "model"}) == "甲" and _reply_text("乙") == "乙"))

    bad = [name for name, ok in legs if not ok]
    print("QUOTE-EVAL-SELFTEST-%s: %d/%d 腿（r171 配对/分层/符号检验/效果门/上游预检，含 %d 条反例腿）"
          % ("PASS" if not bad else "FAIL", len(legs) - len(bad), len(legs), 8))
    for b in bad:
        print("   · 红腿: " + b)
    return 0 if not bad else 1


def preflight_upstream(cfg):
    """上游可用性预检（r171 一手教训）：花一次 1-token 调用，换来「不必再烧 38 分钟空跑」。

    动因（实测）：DeepSeek 余额耗尽后上游回 **HTTP 402 Insufficient Balance**。当时本脚本没有
    任何上游探针 ⇒ 四臂生成全部静默落到离线模板（臂间同文，比较对象不存在），评委调用 225 次
    全部失败，跑完才回 rc=2；而生成结果又只在判分成功时才入账，于是 38 分钟的产物**一条都没留下**。
    两处都修：① 开工前先探上游并点名状态；② 回复带 mode，非在线即判未验。
    返回 (ok, 说明)。说明里**绝不含 Key**。
    """
    try:
        llm_call(cfg, [{"role": "user", "content": "回一个字：好"}], max_tokens=4)
        return True, "上游可用"
    except urllib.error.HTTPError as e:
        hint = {402: "余额耗尽（Insufficient Balance）⇒ 需老大充值/换 Key",
                401: "Key 失效或被撤销", 429: "限流", 404: "base/model 路径不对"}.get(e.code, "")
        return False, "上游 HTTP %d %s%s" % (e.code, e.reason, ("｜" + hint) if hint else "")
    except Exception as e:
        return False, "上游不可达：%s %s" % (type(e).__name__, str(e)[:120])


def llm_cfg_status_line(cfg):
    """配置面读数（不含 Key）：判未验时要能说出是哪一项缺。"""
    return "base=%s model=%s key=%s" % (cfg.get("base"), cfg.get("model"),
                                        "有" if cfg.get("key") else "缺")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8123")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--selftest", action="store_true",
                    help="判据自证（纯函数，零网络零浏览器；可在 --exclude-llm 的整跑里常驻）")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--judges", type=int, default=3, help="评委数（1-3，按 JUDGES 表顺序取）")
    ap.add_argument("--reps", type=int, default=2, help="每臂每例生成次数（消温度噪声）")
    ap.add_argument("--cases", type=int, default=0, help="只取前 N 例（0=按 --focus 的全部）")
    ap.add_argument("--focus", choices=("all", "heavy15"), default="all",
                    help="all=60 例全量；heavy15=承载面定向子集（五种情绪各 3 条，销 07 记录的第①项）")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    if args.smoke:
        picked, reps, judges = focus_subset("all", CASES)[:4], 1, JUDGES[:2]
    else:
        picked = focus_subset(args.focus, CASES)
        reps = max(1, args.reps)
        judges = JUDGES[:max(1, min(3, args.judges))]
    if args.cases:
        picked = picked[:args.cases]
    # 带**原始序号**一起走：--focus 之后位置号与用例号不再相等，明细对账要靠原序号
    cases = [(k,) + tuple(CASES[k - 1]) for k in picked]
    if args.focus != "all":
        print("定向子集 %s → 原序号 %s（承载面各情绪 3 条）" % (args.focus, picked))

    cfg = read_llm_cfg()
    if not cfg:
        print("QUOTE-EVAL-UNVERIFIED: demo-config.js 缺 base/key/model（密钥面不可用）")
        return 2
    # r171 预检：上游不可用 ⇒ 立刻未验，不要烧掉半小时产出一堆同文的离线模板（见 preflight_upstream 动因）
    ok_up, why_up = preflight_upstream(cfg)
    if not ok_up:
        print("QUOTE-EVAL-UNVERIFIED: 上游预检失败 ⇒ 不生成、不判分、不判绿（%s｜%s）"
              % (why_up, llm_cfg_status_line(cfg)))
        return 2
    print("上游预检 OK：%s（用例 %d 例 × %d 臂 × %d 重复）" % (why_up, len(cases), len(ARMS), reps))
    try:
        from playwright.sync_api import sync_playwright
        from browser_engine import launch as be_launch
    except Exception as e:
        print("QUOTE-EVAL-UNVERIFIED: 浏览器环境不可达: %s" % e)
        return 2

    rng = random.Random(args.seed)
    rows, bad = [], []
    try:
        with sync_playwright() as p:
            b, engine = be_launch(p, label="quote-eval")
            pg = b.new_page(viewport={"width": 1200, "height": 860})
            pg.add_init_script(
                "try{localStorage.setItem('peiliao.cfg.v1',JSON.stringify("
                "{base:'%s',key:'%s',model:'%s',stream:false}))}catch(e){}"
                % (cfg["base"], cfg["key"], cfg["model"]))
            pg.goto(args.base + "/index.html", wait_until="load", timeout=45000)
            pg.wait_for_timeout(1500)
            has = pg.evaluate("!!(window.__XINYU_WIT_QUOTES__ && "
                              "window.__XINYU_WIT_QUOTES__.entries.length)")
            if not has:
                print("QUOTE-EVAL-UNVERIFIED: 页面未见 wit-quotes 数据件（先起含 src/data 的服务）")
                b.close()
                return 2

            def gen(text, arm):
                pg.evaluate(CLEAN)
                pg.evaluate(ARM_SNIPPET[arm])
                # mode 必须一起取回来：respond() 在上游失败时静默落离线模板（mode=fallback/offline），
                # 只看 reply 文本的话，「四臂都比了同一句模板」这种失效会被读成一次正常测量（r171 一手）。
                return pg.evaluate(
                    "async (t) => { const r = await window.ChatAgent.respond(t);"
                    " return { reply: r.reply, mode: r.mode }; }", text)

            for pos, (case_no, emo, stage, text) in enumerate(cases, start=1):
                t0 = time.time()
                replies = {arm: [gen(text, arm) for _ in range(reps)] for arm in ARMS}
                pg.evaluate(RESTORE)   # 恢复（同时清 rulesOnly / noFitOnly，臂间不污染）
                if pos == 1:
                    modes = {arm: [m["mode"] for m in replies[arm]] for arm in ARMS}
                    if all(x != "model" for v in modes.values() for x in v):
                        print("QUOTE-EVAL-UNVERIFIED: 四臂回复 mode 无一为 model（%s）"
                              " ⇒ 臂间比的是离线模板，不是注入差异 ⇒ 不判绿" % modes)
                        b.close()
                        return 2
                pair_rows = {}
                for pa, pb in PAIRS:
                    main_pair = (pa, pb) == MAIN_PAIR
                    reps_to_judge = range(reps) if main_pair else [0]
                    samples, votes_by_rep = [], {}
                    for rep in reps_to_judge:
                        votes = []
                        for jd in judges:
                            a_is_pa = rng.random() < 0.5
                            a = replies[pa][rep]["reply"] if a_is_pa else replies[pb][rep]["reply"]
                            bb = replies[pb][rep]["reply"] if a_is_pa else replies[pa][rep]["reply"]
                            judge = None
                            for _try in range(3):
                                try:
                                    raw = llm_call(cfg, [
                                        {"role": "system", "content": jd["sys"]},
                                        {"role": "user", "content":
                                         JUDGE_TMPL.format(case=text, a=a, b=bb)}])
                                    judge = parse_judge(raw)
                                    if judge:
                                        break
                                except Exception:
                                    pass
                                time.sleep(2)
                            if not judge:
                                bad.append("用例 %d %s-vs-%s rep%d 评委 %s 三次均失败/非 JSON"
                                           % (case_no, pa, pb, rep, jd["name"]))
                                continue
                            map_ab = {pa: "A", pb: "B"} if a_is_pa else {pa: "B", pb: "A"}
                            winner = (pa if judge["winner"] == map_ab[pa] else
                                      pb if judge["winner"] == map_ab[pb] else "平")
                            samples.append({"judge_name": jd["name"], "rep": rep,
                                            "a_arm": pa if a_is_pa else pb,
                                            "judge": judge, "winner_arm": winner})
                            votes.append(winner)
                        votes_by_rep[rep] = votes
                    if samples:
                        pair_rows["%s-vs-%s" % (pa, pb)] = {
                            "case": case_no,
                            "samples": samples, "votes_by_rep": votes_by_rep}
                # 生成结果**无条件入账**（r171 一手：上一版只在判分成功时才 append，评委 225 次全失败
                # ⇒ 38 分钟的生成产物一条都没留下、明细文件仍是别人的旧版；判分可以失败，测量证据不行）
                rows.append({"i": case_no, "emo": emo, "stage": stage, "case": text,
                             "modes": {arm: [m["mode"] for m in replies[arm]] for arm in ARMS},
                             "replies": replies, "pairs": pair_rows})
                print("  用例 %02d/%d [#%d %s·%s] 完成（%.0fs，%d 评委×%d 重复×%d 臂）"
                      % (pos, len(cases), case_no, emo, stage, time.time() - t0,
                         len(judges), reps, len(ARMS)))
            b.close()
    except Exception as e:
        print("QUOTE-EVAL-UNVERIFIED: 运行异常: %s" % e)
        return 2

    return _judge_and_report(args.seed, rows, bad, args.smoke,
                             [j["name"] for j in judges], reps)


if __name__ == "__main__":
    sys.exit(main())
