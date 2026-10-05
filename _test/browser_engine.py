# -*- coding: utf-8 -*-
r"""browser_engine.py — 浏览器判据的**唯一** launch 实现（r96 立）。

要拦的形态（一手实测，不是传闻）：
  · 本机 Playwright 自带 Chromium 与已装版本**不匹配**：`D:\playwright-cache` 里只有
    `chromium-1228 / 1243`，而 `playwright 1.60.0` 的 `driver/package/browsers.json` 要的是
    revision **1223** ⇒ `p.chromium.launch()` 直接抛
    `Executable doesn't exist at …\chromium_headless_shell-1223\…\chrome-headless-shell.exe`。
  · 于是 `_test/*.py` 里 **29 个** 套件各自手写
    `try: chromium.launch() / except: chromium.launch(channel="msedge")`。回退本身是对的
    （系统 Edge 实测可用），坏在两件事：
      ① **没有任何一处打印过它实际用了哪个引擎** ⇒ "本地浏览器套件全绿"这句话不可归因，
         而受理面（CI ubuntu + 受管 chromium）跑的**不是同一台浏览器**；
      ② 29 份副本 ⇒ 修一次要改 29 处，必然出现"改了 28 个忘了 1 个"。
  · 本轮还量出**第三条通道**（此前没人记）：
    `executable_path = D:\playwright-cache\chromium-1243\chrome-win64\chrome.exe`
    实测能起，版本 Chromium 153.0.8010.12，**零下载**。⇒ "回退到 Edge"不是唯一选择。

选序（可被 env 覆盖，默认 `XINYU_BROWSER=auto`）：
    1) `XINYU_CHROMIUM_PATH` 指着的可执行体（本机零下载拿到真 chromium 面）
    2) 受管 `chromium.launch()`（CI 面走的就是这一条）
    3) `channel="msedge"`（本机回退，**必须被 CONTRIBUTING 声明**，见 declare 门 E1）
每次成功都往面文件追加一条 `(label, engine, version, reason)`，落点默认
`%TEMP%/xinyu-browser-face.json`（`XINYU_BROWSER_FACE_FILE` 可覆盖）。
**记录失败绝不影响调用方拿到的 browser**——留痕是旁路，不是主路（失败路径自己不能崩）。

用法（被各套件 import；本件不是判据，不进电池）：
    from browser_engine import launch
    browser, face = launch(pw, args=LAUNCH_ARGS, label="browser_check")
退出码：无（库文件）。判据在 _test/browser_engine_declare_check.py。
"""
import json
import os
import sys
import time
from pathlib import Path

FACE_ENV = "XINYU_BROWSER_FACE_FILE"
CHROMIUM_PATH_ENV = "XINYU_CHROMIUM_PATH"
MODE_ENV = "XINYU_BROWSER"

# 回退链的**顺序**也是判据的一部分：declare 门按这三个 tag 判"是否声明了实际发生的那一档"
TAG_LOCAL = "chromium@executable_path"
TAG_MANAGED = "chromium(managed)"
TAG_EDGE = "msedge(channel)"


def face_file():
    p = os.environ.get(FACE_ENV)
    if p:
        return Path(p)
    base = os.environ.get("TEMP") or os.environ.get("TMP") or str(Path.home())
    return Path(base) / "xinyu-browser-face.json"


def record(entry):
    """追加一条面记录。**任何异常都吞掉并返回 False**——留痕坏了不能让浏览器套件跟着红。"""
    try:
        entry = dict(entry)
        entry.setdefault("ts", time.strftime("%Y-%m-%dT%H:%M:%S"))
        p = face_file()
        rows = []
        if p.is_file():
            try:
                got = json.loads(p.read_text(encoding="utf-8"))
                rows = got if isinstance(got, list) else []
            except Exception:                                 # noqa: BLE001
                rows = []
        rows.append(entry)
        p.parent.mkdir(parents=True, exist_ok=True)
        # 只留最近 400 条：本文件是旁路面，不该无限长（无限长会让读它的判据自己变慢）
        p.write_bytes(json.dumps(rows[-400:], ensure_ascii=False, indent=1).encode("utf-8"))
        return True
    except Exception:                                         # noqa: BLE001
        return False


def _mk_face(tag, browser, why):
    try:
        ver = browser.version
    except Exception:                                         # noqa: BLE001
        ver = "unknown"
    return "%s(%s)%s" % (tag, ver, "" if why in ("", None) else " 原因=%s" % why)


def launch(pw, args=None, label="", quiet=False):
    """唯一入口。返回 (browser, face)。face 是**这台浏览器自己的身份串**，不是配置串。
    三档全失败 ⇒ 抛最后一次的异常（不静默降级成"没有浏览器"）。"""
    mode = (os.environ.get(MODE_ENV) or "auto").strip().lower()
    attempts, last_err = [], None
    if mode in ("auto", "", "local", "chromium_path"):
        exe = os.environ.get(CHROMIUM_PATH_ENV, "").strip()
        if exe and Path(exe).is_file():
            attempts.append(("local", exe))
        elif mode in ("local", "chromium_path"):
            raise RuntimeError("%s 指向不存在的文件: %r" % (CHROMIUM_PATH_ENV, exe))
    if mode in ("auto", "", "managed", "edge"):
        attempts.append(("managed", None))
        attempts.append(("edge", None))
    tried = []
    for kind, exe in attempts:
        try:
            if kind == "local":
                b = pw.chromium.launch(executable_path=exe, args=args or [])
                tag = TAG_LOCAL
            elif kind == "managed":
                b = pw.chromium.launch(args=args or [])
                tag = TAG_MANAGED
            else:
                b = pw.chromium.launch(channel="msedge", args=args or [])
                tag = TAG_EDGE
        except Exception as e:                                # noqa: BLE001 —— 下一档是设计，不是兜错
            why = "%s:%s" % (type(e).__name__, str(e).splitlines()[0][:90] if str(e) else "")
            tried.append("%s->%s" % (kind, why[:60]))
            last_err = e
            continue
        face = _mk_face(tag, b, "; ".join(tried))
        if not quiet:
            record({"label": label or Path(sys.argv[0]).name, "engine": tag,
                    "version": getattr(b, "version", "unknown"),
                    "skipped": list(tried), "face": face})
        return b, face
    raise RuntimeError("三档浏览器全部起不来: %s" % (" | ".join(tried) or "无候选"))


if __name__ == "__main__":
    print(__doc__)
    sys.exit(0)
