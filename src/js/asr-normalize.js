/* 心屿 · 语音转写归一化（r174 / A2）
 *
 * 为什么有这件（一手来源，不是拍脑袋）：A1 回放台架 `_test/asr_replay_check.py` 的
 * scene-noise-mixed 样本实测坐实 —— `pickBest`（voice-call.js）**压根没有任何剔除口头语的机制**，
 * 引擎把「嗯那个我今天有点崩溃了」整句送进来，它就整句转给用户。本模块补这一级。
 *
 * 分级设计（关键，别合并）：
 *   选候选 = pickBest（**不改写文本**，保住 A1 的 E1b 零改写不变量）
 *   清洗文本 = 本模块 normalize（在 pickBest 之后单独一级，改写是显式的、可单测的）
 * 两者合成才进对话。合成后必须仍等于「某条候选经同一清洗」——来源可追，不许凭空造字。
 *
 * 🔴 设计红线一：**禁动带语义的词**。「有点累」≠「累」、「说一下」≠「说」——
 *   删掉程度词会改变语义，所以「有点/有点儿/有些/一点/一下」一律【不在表内】。
 * 🔴 设计红线二：清洗到空必须回退原文。「嗯」不能变成空串（那会让收句判据拿到空文本）。
 * 🔴 设计红线三（r174 实测后立，**推翻了我自己的初版**）：**句末语气词一律不许剥**。
 *   初版把「呀/啊/吧/呢」当噪声剥掉，E5 门槛当场判红并给出证据：cmn-01/04/05 三条
 *   「今天还行呀」→「今天还行」，CER 从 0.000 恶化到 0.200。
 *   原理：**句首口头语是非语义噪声，句末语气词是用户真说出来的语气** —— 情感陪伴场景里
 *   语气本身是信息（"还行呀" 与 "还行" 不是一回事），剥它是拿 fidelity 换整洁。
 *   故 `stripTrailingParticles` 保留函数但**默认不接线**，E6 有专门一条腿钉住「不许剥」。
 *
 * 判据：`_test/asr_replay_check.py`（expect_norm 腿 + E5 增益腿 + E6 纯函数组）；
 * 该件同时钉「清洗后文本 == 某条候选的清洗结果」，不许凭空造字。
 */
window.ASRNormalize = (function () {
  // 句首口头语：按长度降序匹配，否则「那个」会被「那」之类的短词先咬掉一半
  const LEAD = ["怎么说呢", "我跟你说", "你知道吗", "那个", "这个", "就是", "然后", "反正",
                "其实", "嗯", "呃", "唔", "啊", "哦"].sort((a, b) => b.length - a.length);
  // 句末语气词：单字，只在剥掉后仍有内容时才剥
  const TAIL = "啊呀吧呢哦嘛啦嘞咯喽";
  const MIN_KEEP = 2;      // 剥到比这更短就停手，避免把整句洗没
  const WS = /\s+/g;

  /** 只剥句首口头语，可剥多轮（"嗯那个呃我今天…" 要连着剥三层） */
  function stripLeadingFillers(t) {
    let s = String(t || "").trim(), moved = true;
    while (moved && s.length > MIN_KEEP) {
      moved = false;
      for (const f of LEAD) {
        if (s.length - f.length >= MIN_KEEP && s.indexOf(f) === 0) { s = s.slice(f.length).trim(); moved = true; break; }
      }
    }
    return s;
  }

  /** 剥句末语气字。🔴 **默认不接线**（红线三）：保留函数是因为可测、可复用，
   *  以及留一条「哪天要剥必须先过 E5」的显式开关位 —— 不是留着随时调用的私货。
   *  真要启用时先改 E5 阈值口径，并同步改 norm-02/norm-03 两条样本的期望。 */
  function stripTrailingParticles(t) {
    let s = String(t || "").trim(), moved = true;
    while (moved && s.length > MIN_KEEP) {
      const last = s.charAt(s.length - 1);
      if (TAIL.indexOf(last) < 0 || s.length - 1 < MIN_KEEP) break;
      s = s.slice(0, -1).trim(); moved = true;
    }
    return s;
  }

  /** 归一化主入口：压空白 → 剥【句首】口头语 → 兜底回退。
   *  **只动句首、只动空白，不动句末语气、不改字序、不删实词**（红线一 + 红线三）。 */
  function normalize(t) {
    const raw = String(t || "").trim().replace(WS, " ");
    if (!raw) return "";
    const out = stripLeadingFillers(raw);
    return out || raw;          // 红线二：洗没了就交还原文，绝不交空串
  }

  return {
    normalize,
    stripLeadingFillers,
    stripTrailingParticles,          // 🔴 默认不接线，见函数头「红线三」
    /** 供判据读取，不参与业务路径 */
    _unit: { normalize, stripLeadingFillers, stripTrailingParticles, MIN_KEEP }
  };
})();
