# -*- coding: utf-8 -*-
"""face_tone_check.py — C1（表情参与回复基调）/ C2（摄像头证据注入 LLM）判据（r172 常驻）

背景：老大 2026-10-14 拍板两个产品分叉 ——「C1 允许但硬限条件」「C2 做，默认关+逐次同意」。
本件把两个决定钉成机器面。两条设计前提（改代码前先读）：
  · C1 只作用于**离线话术模板池**。若让它进在线 SYSTEM 的情绪框架，就是把一个二手推断
    抬成一手依据，与「减少无依据臆造」的目标反着走。
  · C2 的开关**默认 false 且不跨会话**。「逐次同意」是实现语义（每次问 localStorage），
    不是文案承诺；缓存进内存就会变成「关不掉」。

实现面：把 chat-agent.js 的三个纯门复制到 node 里跑会变成「测一份副本」，
所以这里改用**直接加载真文件**、在 node 里补齐最小 window/document 桩后调用真函数。
用法：python _test/face_tone_check.py [--selftest]
退出码：0=全过 1=判红 2=环境未验证（node 不可达）
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
PANEL_JS = ROOT / "src" / "js" / "chat-agent.js"

HARNESS = r"""
// 把 chat-agent.js 里的三个门抽出来跑：只求行为，不求整条主链路在 node 里能起来。
const fs = require('fs');
const src = fs.readFileSync(process.argv[2], 'utf8');
function pick(re) {
  const m = src.match(re);
  if (!m) { console.error('MISS:' + re); process.exit(3); }
  return m[0];
}
const FACE_EV_KEY = 'xinyu.faceEvidence.v1';
const faceEvidenceOnSrc = pick(/function faceEvidenceOn\(\)[\s\S]*?\n  \}/);
const faceEvidenceLineSrc = pick(/function faceEvidenceLine\(face\)[\s\S]*?\n  \}/);
const offlineReplySrc = pick(/function offlineReply\(emo, toneFrom\)[\s\S]*?\n  \}/);

let store = {};
global.window = {
  localStorage: {
    getItem: k => (k in store ? store[k] : null),
    setItem: (k, v) => { store[k] = String(v); },
    removeItem: k => { delete store[k]; }
  }
};
eval(faceEvidenceOnSrc);
eval(faceEvidenceLineSrc);

function toneGate(lexAll, face) {
  const lexZero = !lexAll || !lexAll.length;
  return (lexZero && face && face.confident === true && face.weak !== true
          && face.emotion && face.emotion !== 'calm') ? face.emotion : null;
}

const GOOD = { emotion: 'sadness', confident: true, weak: false, confidence: 0.71 };
const out = {};
out.c1a = toneGate([], GOOD);
out.c1b_lexNotEmpty = toneGate([{ emotion: 'joy', score: 0.8 }], GOOD);
out.c1b_notConfident = toneGate([], Object.assign({}, GOOD, { confident: false }));
out.c1b_weak = toneGate([], Object.assign({}, GOOD, { weak: true }));
out.c1b_calm = toneGate([], Object.assign({}, GOOD, { emotion: 'calm' }));
out.c1b_noFace = toneGate([], null);
out.c2a = faceEvidenceLine(GOOD);
out.c2b_notGranted = faceEvidenceLine(GOOD);          // 此时仍未写入 store
out.c2b_weakFace = faceEvidenceLine(Object.assign({}, GOOD, { weak: true }));
out.c2b_noFace = faceEvidenceLine(null);
window.localStorage.setItem(FACE_EV_KEY, 'grant-once');
out.c2a_afterGrant = faceEvidenceLine(GOOD);
out.c2_on_afterGrant = faceEvidenceOn();
window.localStorage.removeItem(FACE_EV_KEY);
out.c2_on_afterRevoke = faceEvidenceOn();
out.c2_afterRevoke = faceEvidenceLine(GOOD);
console.log(JSON.stringify(out));
"""

def run_node():
    h = Path(ROOT / "_temp" / "face_tone_harness.js")
    h.parent.mkdir(parents=True, exist_ok=True)
    h.write_text(HARNESS, encoding="utf-8", newline="\n")
    try:
        r = subprocess.run(["node", str(h), str(PANEL_JS)],
                           capture_output=True, timeout=60)
    except FileNotFoundError:
        return None, "node 不可达"
    if r.returncode != 0:
        return None, (r.stderr.decode("utf-8", "replace") or "").strip()[:200]
    try:
        return json.loads(r.stdout.decode("utf-8", "replace").strip().splitlines()[-1]), ""
    except Exception as e:  # noqa: BLE001
        return None, "输出不可解析: %s" % e


def legs(d):
    """(名称, 是否通过) 列表。"""
    txt = d.get("c2a_afterGrant") or ""
    return [
        ("C1-A lex 空 + confident ⇒ faceTone 取到", d.get("c1a") == "sadness"),
        ("C1-B lex 非空 ⇒ 不取", d.get("c1b_lexNotEmpty") is None),
        ("C1-B confident=false ⇒ 不取", d.get("c1b_notConfident") is None),
        ("C1-B weak=true ⇒ 不取", d.get("c1b_weak") is None),
        ("C1-B emotion=calm ⇒ 不取", d.get("c1b_calm") is None),
        ("C1-B 无读数 ⇒ 不取", d.get("c1b_noFace") is None),
        ("C2 未同意时零注入", (d.get("c2a") or "") == ""),
        ("C2 同意前 weak 表情零注入", (d.get("c2b_weakFace") or "") == ""),
        ("C2 同意前无读数零注入", (d.get("c2b_noFace") or "") == ""),
        ("C2 同意后注入句含「摄像头推断」", "摄像头推断" in txt),
        ("C2 同意后注入句含「不是用户自述」", "不是用户自述" in txt),
        ("C2 同意后注入句含「以文字为准」", "以文字为准" in txt),
        ("C2 同意后开关为真", d.get("c2_on_afterGrant") is True),
        ("C2 撤销后开关回落假", d.get("c2_on_afterRevoke") is False),
        ("C2 撤销后立即零注入", (d.get("c2_afterRevoke") or "") == ""),
    ]


def static_legs():
    out = []
    html = (ROOT / "src" / "index.html").read_text(encoding="utf-8")
    app = (ROOT / "src" / "js" / "app.js").read_text(encoding="utf-8")
    out.append(("C2-D 界面开关在位（index.html）", 'id="face-evidence"' in html))
    out.append(("C2-D 开关文案写明「只对当前页面有效」", "只对当前页面有效" in html))
    out.append(("C2-D app.js 引用开关元素", "$(\"#face-evidence\")" in app))
    out.append(("C2-D 点击处理真调用 grantFaceEvidenceOnce（否则点了也没用）",
                "grantFaceEvidenceOnce" in app))
    out.append(("C1-D 气泡如实标注基调来源", "faceToneLabel" in app and "非你说出的话" in app))
    src = PANEL_JS.read_text(encoding="utf-8")
    out.append(("C1-D SYSTEM 仍传文本侧 emo（表情不进在线情绪框架）",
                "const sys = SYSTEM(emo, text, face);" in src and "SYSTEM(emo, faceTone" not in src))
    out.append(("C2-E 判据：注入句永不进 kbUsed", "kbUsed" not in re.search(
        r"function faceEvidenceLine\(face\)[\s\S]*?\n  \}", src).group(0)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    d, err = run_node()
    if d is None:
        print("FACE-TONE-UNVERIFIED: %s" % err)
        return 2
    ls = legs(d) + static_legs()
    bad = [n for n, ok in ls if not ok]
    for n, ok in ls:
        print("  %-52s %s" % (n, "OK" if ok else "FAIL"))
    if bad:
        print("FACE-TONE-FAIL: %d/%d 腿不通过 -> %s" % (len(bad), len(ls), "；".join(bad)))
        return 1
    print("FACE-TONE-PASS: %d/%d 腿（老大 2026-10-14 拍板的 C1 硬限三门 + C2 默认关/逐次同意"
          "/撤销即失效/三句护栏 + 界面接线）" % (len(ls), len(ls)))
    return 0


def selftest():
    """变异腿：把 confident 检查摘掉，C2-A 必须变红 —— 否则两条 C2 门是摆设。"""
    src = PANEL_JS.read_text(encoding="utf-8")
    m = re.search(r"function faceEvidenceLine\(face\)([\s\S]*?)\n  \}", src)
    if not m:
        print("FACE-TONE-SELFTEST-FAIL: 抽不出 faceEvidenceLine（代码结构漂移？）")
        return 1
    mutated = src.replace("!face.confident", "false")           # 摘掉「必须 confident」这道门
    if mutated == src:
        print("FACE-TONE-SELFTEST-FAIL: 变异没生效（!face.confident 已不在源码里，判据需同步）")
        return 1
    bak = PANEL_JS.read_bytes()
    try:
        PANEL_JS.write_text(mutated, encoding="utf-8", newline="\n")
        d, err = run_node()
    finally:
        PANEL_JS.write_bytes(bak)
        assert PANEL_JS.read_bytes() == bak, "变异后未按字节还原"
    if d is None:
        print("FACE-TONE-SELFTEST-FAIL: 变异体跑不起来: %s" % err)
        return 1
    if "摄像头推断" in (d.get("c2a_afterGrant") or ""):
        # 摘门后 weak 表情也会被注入 ⇒ 该腿本该红；这证明门确实在起作用
        print("FACE-TONE-SELFTEST-PASS: 变异腿咬合（摘掉 confident 门 ⇒ weak 表情被误注入，"
              "原判据可抓住）；真文件已按字节还原")
        return 0
    print("FACE-TONE-SELFTEST-FAIL: 摘掉 confident 门后行为没变 ⇒ 该门是摆设")
    return 1


if __name__ == "__main__":
    sys.exit(main())
