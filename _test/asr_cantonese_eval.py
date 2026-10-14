# -*- coding: utf-8 -*-
"""心屿 · 粤语 ASR 评测运行器（B3）

对 ml/build_asr_eval_set.py 产出的评测清单逐条转写，算**字错误率 CER** 与**句错误率 SER**，
按 domain / 时长桶 / 性别年龄分组，并可保存为基线、与历史基线对比（模型迭代用）。

指标定义（写死在代码里，改口径要连注释一起改）：
  · CER = 编辑距离(ref, hyp) / len(ref)，按**字符**算（粤语文本，不按词 —— 没有可信分词器）。
    对每条算，再按**字符总数加权**汇总（不是各条 CER 的算术平均：短句一条错一字就被放大）。
  · SER = hyp != ref 的句子占比（整句对错率，不加权）。
  · 二者都只统计 ref 非空的条目。

为什么不能只报一个数：同一模型在不同 domain / 不同时长上的表现可能差一倍，
单个数会把这个差异抹平。分组读数 + 总读数一起出，才看得出"到底哪类不行"。

用法：
  python _test/asr_cantonese_eval.py [--limit 300] [--url http://127.0.0.1:8321]
      [--save 基线.json] [--compare 基线.json] [--gate cer,ser]
  · --gate 0.15,0.60 = CER≤15% 且 SER≤60% 才 rc=0（供电池当门禁用；不给就只测不判）
  · --compare 会打印与基线的差值，并列出"新变差的样本"（回退证据，不是只看总数）
"""
import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(HERE, "asr_eval_manifest.jsonl")
DEFAULT_URL = "http://127.0.0.1:8321"
# 与 ml/build_asr_eval_set.py 的 PUNCT **同源**：判据里两份正则是常见的漂移源，改一处要改两处
PUNCT = re.compile(r"[\s，。！？、；：「」『』（）《》…—\-.,!?;:\"'()\[\]<>~·`@#$%^&*_+=|\\/{}]+")
# 粤语常用字 → 普通话同义字。**只用于第二口径**（norm-canto），不改第一口径的严格比对。
# 为什么需要它：SenseVoice 倾向输出普通话书面字（係→系、賭→赌、鹹魚→咸鱼）。
#   那是"听对了但用字不同"，与"听错了"是两回事；混在一个数里会同时高估和低估问题。
CANTO_MAP = {"係": "是", "唔": "不", "冇": "没", "嗰": "那", "嘅": "的", "咗": "了",
             "喺": "在", "睇": "看", "攞": "拿", "畀": "给", "谂": "想", "咪": "别",
             "嚟": "来", "哋": "们", "佢": "他", "冇得": "没得", "邊": "边", "度": "道"}


def norm_text(s):
    """去空白与标点，不改字（与评测集构建的 norm_ref 同源）"""
    return PUNCT.sub("", s or "")


def norm_canto(s):
    """第二口径：先去标点，再把粤语常用字映射为普通话同义字"""
    s = norm_text(s)
    for a, b in CANTO_MAP.items():
        s = s.replace(a, b)
    return s


def norm_simp(s):
    """第三口径：繁→简归一。CV 的 ref 由香港社区以**繁体**书写，而 SenseVoice 输出**简体**
    （個→个、淨→净、業→业、賭→赌、輸→输）。这是书写系统差异，不是识别错误，
    但它会把严格 CER 系统性抬高 —— 不隔离就会把"听对了"误判成"听错了"。
    依赖 zhconv（装不上时本口径退化为与第二口径同值，并在报告里标注 degraded）。"""
    global _ZHHCONV
    if _ZHHCONV is None:
        try:
            import zhconv
            _ZHHCONV = zhconv
        except Exception:                                    # noqa: BLE001
            _ZHHCONV = False
    if not _ZHHCONV:
        return norm_canto(s)
    return _ZHHCONV.convert(norm_canto(s), "zh-cn")


_ZHHCONV = None


def edit_distance(a, b):
    """标准 Levenshtein（字符级）。短句够用，不上 numpy：可读性 > 微优化。"""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def transcribe(url, wav_path, timeout=180):
    """返回 (text, err)。网络层错误也算 err（调用方据此判 UNVERIFIED，而不是判红）——
    引擎没起来 ≠ 引擎坏了，这个区分是本仓四态的第一条。"""
    try:
        with open(wav_path, "rb") as f:
            r = requests.post(url + "/asr", files={"file": ("e.wav", f.read(), "audio/wav")},
                              timeout=timeout)
    except requests.RequestException as e:
        return None, "网络错误 %s" % str(e)[:100]
    if r.status_code != 200:
        return None, "HTTP %d %s" % (r.status_code, r.text[:80])
    j = r.json()
    return (j.get("text") or "").strip(), None


def bucket(secs):
    if secs < 2:
        return "<2s"
    if secs < 4:
        return "2-4s"
    if secs < 6:
        return "4-6s"
    return ">=6s"


def _summarize(table):
    """分维度聚合 → 三口径读数（严格 / 粤字归一 / 繁简归一）。按样本数降序，便于先看大头。"""
    out = {}
    for k, g in sorted(table.items(), key=lambda x: -x[1]["n"]):
        out[k] = {"n": g["n"], "cer": round(g["dist"] / g["ref"], 4) if g["ref"] else None,
                  "ser": round(g["ser_bad"] / g["n"], 4),
                  "cer_canto": round(g["dist_c"] / g["ref"], 4) if g["ref"] else None,
                  "ser_canto": round(g["ser_bad_c"] / g["n"], 4),
                  "cer_simp": round(g["dist_s"] / g["ref"], 4) if g["ref"] else None,
                  "ser_simp": round(g["ser_bad_s"] / g["n"], 4)}
    return out


def _print_faces(report, per_sample, cer, ser, cer_c, ser_c, cer_s, ser_s):
    """门面行 + 三个分维度面 + 两组最差样本（严格口径与繁简归一口径各一排）。"""
    print("ASR-EVAL 条数=%d 参考总字数=%d｜严格CER=%.2f%% SER=%.2f%%｜粤字归一CER=%.2f%% SER=%.2f%%"
          "｜繁简归一CER=%.2f%% SER=%.2f%%｜耗时=%.1fs"
          % (len(report["samples"]), report["total_ref_chars"], cer * 100, ser * 100,
             cer_c * 100, ser_c * 100, cer_s * 100, ser_s * 100, report["secs"]))
    if not _ZHHCONV:
        print("  ⚠ zhconv 不可用，繁简归一口径退化为与粤字归一同值（读数不可当真）")
    for name, table in (("domain", report["by_domain"]), ("时长", report["by_dur_bucket"]),
                        ("性别", report["by_gender"])):
        parts = ["%s n=%d cer=%.1f%%(粤%.1f%%/简%.1f%%)"
                 % (k, v["n"], (v["cer"] or 0) * 100, (v["cer_canto"] or 0) * 100,
                    (v["cer_simp"] or 0) * 100)
                 for k, v in table.items()]
        print("  %s: %s" % (name, " | ".join(parts)))
    worst = sorted(per_sample, key=lambda r: -(r["dist"] / max(1, r["ref_len"])))[:5]
    for w in worst:
        print("  最差(严格): CER=%.0f%% ref=%r hyp=%r" % (100.0 * w["dist"] / max(1, w["ref_len"]),
                                                        w["ref"], w["hyp"]))
    worst_s = sorted(per_sample, key=lambda r: -(r["dist_simp"] / max(1, r["ref_len"])))[:5]
    for w in worst_s:
        print("  最差(繁简归一): CER=%.0f%% ref=%r hyp=%r" % (100.0 * w["dist_simp"] / max(1, w["ref_len"]),
                                                            w["ref"], w["hyp"]))


def _compare_baseline(path, per_sample, cer, ser, cer_c):
    """与历史基线逐样本对账（只印读数，不改判据——判绿归 --gate 那一挡）。"""
    if not os.path.isfile(path):
        print("ASR-EVAL-FAIL 对比基线不存在 %s" % path)
        return False
    base = json.load(open(path, encoding="utf-8"))
    d_cer = (cer - base["cer"]) * 100
    d_ser = (ser - base["ser"]) * 100
    d_ccer = (cer_c - base.get("cer_canto", cer_c)) * 100
    print("  对比基线(%s, n=%d)：严格CER %+.2f / 严格SER %+.2f / 归一CER %+.2f 个百分点"
          % (os.path.basename(path), base["n"], d_cer, d_ser, d_ccer))
    bmap = {s["id"]: s for s in base.get("samples", [])}
    worse = [(r["id"], r["ref"], r["hyp"], bmap[r["id"]]["hyp"])
             for r in per_sample
             if r["id"] in bmap and r["dist"] > bmap[r["id"]]["dist"]]
    better = [r for r in per_sample
              if r["id"] in bmap and r["dist"] < bmap[r["id"]]["dist"]]
    print("  逐样本：变好 %d 条 / 变差 %d 条" % (len(better), len(worse)))
    for w in worse[:5]:
        print("    回退 %s ref=%r 基线=%r 现在=%r" % w)
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="只跑前 N 条（0=全部）")
    ap.add_argument("--url", default=DEFAULT_URL)
    ap.add_argument("--save", default="", help="把本次结果存成基线 JSON")
    ap.add_argument("--compare", default="", help="与历史基线 JSON 对比")
    ap.add_argument("--gate", default="", help="形如 0.15,0.60：CER 与 SER 的上限")
    ap.add_argument("--workers", type=int, default=1, help="并发转写数（sidecar 是同步的，>1 才有效）")
    args = ap.parse_args()

    if not os.path.isfile(MANIFEST):
        print("ASR-EVAL-UNVERIFIED 找不到评测清单 %s（先跑 ml/build_asr_eval_set.py）" % MANIFEST)
        return 2
    items = [json.loads(l) for l in open(MANIFEST, encoding="utf-8") if l.strip()]
    if args.limit:
        items = items[:args.limit]

    t0 = time.time()
    results = []
    errs = []

    def one(it):
        hyp, err = transcribe(args.url, it["wav"])
        return it, hyp, err

    if args.workers > 1:
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            for it, hyp, err in ex.map(one, items):
                results.append((it, hyp))
                if err:
                    errs.append((it["id"], err))
    else:
        for it in items:
            _, hyp, err = one(it)
            results.append((it, hyp))
            if err:
                errs.append((it["id"], err))

    if errs:
        print("ASR-EVAL-UNVERIFIED %d/%d 条转写失败（例：%s）—— 有没测到的，不判绿"
              % (len(errs), len(items), errs[0]))
        return 2

    # ---- 指标 ----------------------------------------------------------
    # 三个口径（逐层放宽，用来把"不同性质的错"分开）：
    #   strict  ：ref 原样（构建时已去标点） vs hyp 去标点 ⇒ 用字必须完全一致
    #   canto   ：两侧都过 norm_canto  ⇒ 容忍"粤语字 vs 普通话字"的用字差异
    #   simp    ：两侧都过 norm_simp   ⇒ 再容忍繁简书写差异（CV ref 繁体 / 引擎输出简体）
    # 报三个数而不是一个，是因为单个数会把上面三类混在一起，既高估也低估问题。
    tot_ref = tot_dist = tot_dist_c = tot_dist_s = 0
    ser_bad = ser_bad_c = ser_bad_s = 0
    by_domain, by_bucket, by_gender = {}, {}, {}
    per_sample = []
    for it, hyp in results:
        ref = it["ref"]
        hyp_n = norm_text(hyp)
        hyp_c = norm_canto(hyp)
        hyp_s = norm_simp(hyp)
        ref_c = norm_canto(ref)
        ref_s = norm_simp(ref)
        d = edit_distance(ref, hyp_n)
        dc = edit_distance(ref_c, hyp_c)
        ds = edit_distance(ref_s, hyp_s)
        tot_ref += len(ref)
        tot_dist += d
        tot_dist_c += dc
        tot_dist_s += ds
        if hyp_n != ref:
            ser_bad += 1
        if hyp_c != ref_c:
            ser_bad_c += 1
        if hyp_s != ref_s:
            ser_bad_s += 1
        rec = {"id": it["id"], "ref": ref, "hyp": hyp_n, "dist": d,
               "ref_len": len(ref), "domain": it.get("domain"), "dur": it["dur"],
               "dist_canto": dc, "dist_simp": ds}
        per_sample.append(rec)
        for key, table in ((it.get("domain") or "unknown", by_domain),
                           (bucket(it["dur"]), by_bucket),
                           (it.get("gender") or "unknown", by_gender)):
            g = table.setdefault(key, {"n": 0, "ref": 0, "dist": 0, "ser_bad": 0,
                                       "dist_c": 0, "ser_bad_c": 0,
                                       "dist_s": 0, "ser_bad_s": 0})
            g["n"] += 1
            g["ref"] += len(ref)
            g["dist"] += d
            g["dist_c"] += dc
            g["dist_s"] += ds
            g["ser_bad"] += (hyp_n != ref)
            g["ser_bad_c"] += (hyp_c != ref_c)
            g["ser_bad_s"] += (hyp_s != ref_s)

    cer = tot_dist / tot_ref if tot_ref else 0.0
    ser = ser_bad / len(results) if results else 0.0
    cer_c = tot_dist_c / tot_ref if tot_ref else 0.0
    ser_c = ser_bad_c / len(results) if results else 0.0
    cer_s = tot_dist_s / tot_ref if tot_ref else 0.0
    ser_s = ser_bad_s / len(results) if results else 0.0

    report = {"url": args.url, "n": len(results), "total_ref_chars": tot_ref,
              "total_dist": tot_dist, "cer": round(cer, 4), "ser": round(ser, 4),
              "cer_canto": round(cer_c, 4), "ser_canto": round(ser_c, 4),
              "cer_simp": round(cer_s, 4), "ser_simp": round(ser_s, 4),
              "zhconv_ok": bool(_ZHHCONV),
              "secs": round(time.time() - t0, 1),
              "by_domain": _summarize(by_domain), "by_dur_bucket": _summarize(by_bucket),
              "by_gender": _summarize(by_gender), "samples": per_sample}

    _print_faces(report, per_sample, cer, ser, cer_c, ser_c, cer_s, ser_s)

    if args.save:
        with open(args.save, "w", encoding="utf-8", newline="\n") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print("  基线已存 %s" % args.save)

    if args.compare and not _compare_baseline(args.compare, per_sample, cer, ser, cer_c):
        return 1

    if args.gate:
        try:
            g_cer, g_ser = (float(x) for x in args.gate.split(","))
        except ValueError:
            print("ASR-EVAL-FAIL --gate 形如 0.15,0.60")
            return 1
        ok = cer <= g_cer and ser <= g_ser
        print("ASR-EVAL-%s 门禁 CER<=%.1f%%(实 %.2f%%) SER<=%.1f%%(实 %.2f%%)"
              % ("PASS" if ok else "FAIL", g_cer * 100, cer * 100, g_ser * 100, ser * 100))
        return 0 if ok else 1
    return 0


if __name__ == "__main__":
    from check_instrument import install_excepthook
    install_excepthook("ASR-EVAL")
    raise SystemExit(main())
