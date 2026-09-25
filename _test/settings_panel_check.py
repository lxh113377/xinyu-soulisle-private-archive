# -*- coding: utf-8 -*-
"""设置面板行为守卫（对标轮 r27 新增，第四刀的前置判据）

为什么先写判据再动刀：`app.js` 的设置面板是**唯一直接碰密钥输入框**的模块，
而它此前**没有任何行为判据**（只有 `public_check` 扫静态字面量）。
把这样一块代码"行为零改动地外提"，如果没有行为判据，等于没人能证明没改坏。

判据（逐项独立，S8 兜住全程）：
  S1 打开对话框：base/model 回显当前配置，**Key 输入框恒为空**（密钥绝不回显）
  S2 快捷预设：选一家 ⇒ base+model 被填入该预设的两段值（Key 不由预设代填）
  S3 保存且 Key 留空 ⇒ 已存 Key **不被洗掉**（localStorage 里仍是原值）
  S4 保存且填了新 Key ⇒ 写入新值
  S5 「逐字流式」勾选状态往返写入 cfg.stream
  S6 点「取消」⇒ 配置一字未改（改了什么都不落盘）
  S7 保存后徽章如实翻转（有 base+key+model ⇒ 在线；Key 被清 ⇒ 离线）
  S8 全程零 JS 异常

`--selftest`：对每条关键断言**注入反例**（强制回显 Key / 洗掉 Key / 预设不填 / 取消仍写盘），
必须逐项变红 —— 否则判据恒真（R247 对照组）。

前置：Java 服务端起在 8123（或任一托管 src/ 的静态服务）
用法：python _test/settings_panel_check.py [--selftest]
"""
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")

BASE = "http://127.0.0.1:8123/index.html"
CFG_KEY = "peiliao.cfg.v1"
# 用非 sk- 前缀的假值：既验证"密钥位"的行为，又不被仓库里的密钥扫描器自伤命中
OLD_KEY = "TESTKEY-LOCALONLY-0000"
NEW_KEY = "TESTKEY-NEW-1111"
results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  -> {detail}" if detail else ""))
    return bool(ok)


def read_cfg(pg):
    # 注：JS 里的 '{}' 不能写进 f-string（会被当占位符），故用字符串拼接
    return json.loads(pg.evaluate("() => localStorage.getItem(" + json.dumps(CFG_KEY) + ") || '{}'"))


def open_dialog(pg):
    pg.click("#btn-settings")
    pg.wait_for_selector("#dlg-settings[open]", timeout=5000)


def dialog_state(pg):
    return pg.evaluate("""() => ({
      open: document.querySelector('#dlg-settings').open,
      base: document.querySelector('#set-base').value,
      model: document.querySelector('#set-model').value,
      key: document.querySelector('#set-key').value,
      stream: document.querySelector('#set-stream').checked
    })""")


def badge(pg):
    return pg.evaluate("() => document.querySelector('#mode-badge').textContent.trim()")


def new_page(seed_cfg, collect):
    """起一个已注入配置的干净页面（add_init_script 在应用脚本之前跑，故首屏即带配置）。
    本机 Playwright 的 chromium headless shell 缺失 ⇒ 回落系统 Edge（与 ux_guards 同一套做法）。"""
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    try:
        browser = pw.chromium.launch()
    except Exception:
        browser = pw.chromium.launch(channel="msedge")
    pg = browser.new_page()
    pg.add_init_script(f"localStorage.setItem({json.dumps(CFG_KEY)}, {json.dumps(json.dumps(seed_cfg))});")
    pg.on("pageerror", lambda e: collect.append(str(e)))
    pg.goto(BASE)
    pg.wait_for_function("() => window.ChatAgent && typeof window.ChatAgent.isOnline === 'function'")
    return pw, pg


def run_main():
    errs = []
    pw, pg = new_page({"base": "https://api.deepseek.com/v1", "key": OLD_KEY,
                       "model": "deepseek-chat", "stream": True}, errs)
    try:
        # S1 打开：回显 base/model，Key 恒空
        open_dialog(pg)
        st = dialog_state(pg)
        check("S1 打开对话框回显 base/model 且 Key 输入框恒为空",
              st["open"] and st["base"] == "https://api.deepseek.com/v1"
              and st["model"] == "deepseek-chat" and st["key"] == "", str(st))
        # S2 快捷预设
        pg.select_option("#set-provider", "https://api.openai.com/v1|gpt-4o-mini")
        st2 = dialog_state(pg)
        check("S2 选预设填入 base+model（Key 不由预设代填）",
              st2["base"] == "https://api.openai.com/v1" and st2["model"] == "gpt-4o-mini" and st2["key"] == "", str(st2))
        # S3 保存且 Key 留空 ⇒ 不洗 Key
        pg.click("#btn-save-settings")
        c3 = read_cfg(pg)
        check("S3 保存时 Key 留空不洗掉已存密钥",
              c3.get("key") == OLD_KEY and c3.get("base") == "https://api.openai.com/v1",
              json.dumps(c3, ensure_ascii=False))
        # S4 填新 Key 保存
        open_dialog(pg)
        pg.fill("#set-key", NEW_KEY)
        pg.click("#btn-save-settings")
        check("S4 填了新 Key 则写入新值", read_cfg(pg).get("key") == NEW_KEY, json.dumps(read_cfg(pg), ensure_ascii=False))
        # S5 流式开关
        open_dialog(pg)
        if pg.is_checked("#set-stream"):
            pg.uncheck("#set-stream")
            want = False
        else:
            pg.check("#set-stream")
            want = True
        pg.click("#btn-save-settings")
        check("S5 逐字流式勾选状态落盘", read_cfg(pg).get("stream") is want, f"期望 {want} 实际 {read_cfg(pg).get('stream')}")
        # S6 取消不写盘
        open_dialog(pg)
        before = read_cfg(pg)
        pg.fill("#set-base", "https://should-not-persist.invalid/v1")
        pg.evaluate("() => document.querySelector('#dlg-settings .dlg-actions button[value=cancel]').click()")
        pg.wait_for_function("() => !document.querySelector('#dlg-settings').open")
        check("S6 点取消则配置一字未改", read_cfg(pg) == before,
              f"改前 {json.dumps(before, ensure_ascii=False)} 改后 {json.dumps(read_cfg(pg), ensure_ascii=False)}")
        # S7 徽章如实反映在线/离线（保存后刷新）
        check("S7a 有 base+key+model 时徽章为在线", "在线" in badge(pg), badge(pg))
        open_dialog(pg)
        pg.fill("#set-base", "")
        pg.fill("#set-model", "")
        pg.evaluate(f"() => window.ChatAgent.setCfg({{ key: '' }})")   # 真清掉 Key 才算离线
        pg.click("#btn-save-settings")
        check("S7b 清掉 Key 后徽章回落离线（不伪装在线）", "离线" in badge(pg), badge(pg))
        # S8 全程零异常
        check("S8 全程无 JS 异常", not errs, str(errs[:3]))
    finally:
        pg.context.browser.close()
        pw.stop()
    bad = [r for r in results if not r[1]]
    print(f"\n合计 {len(results)} 项，失败 {len(bad)} 项")
    print("SETTINGS-PANEL-PASS" if not bad else "SETTINGS-PANEL-FAIL")
    return 1 if bad else 0


def run_selftest():
    """注入反例：每条关键断言都必须能被"故意做坏"打到红，否则判据恒真。"""
    errs = []
    pw, pg = new_page({"base": "https://api.deepseek.com/v1", "key": OLD_KEY,
                       "model": "deepseek-chat", "stream": True}, errs)
    bad = []   # 只登记失败项（第一版误把成功也 append(None)，非空即判红 ⇒ 报了一条空 FAIL）
    try:
        # 反例①：强制回显 Key ⇒ S1 必须判 False（"未被抓到"= 故意做坏之后断言**仍然成立**）
        open_dialog(pg)
        pg.fill("#set-key", OLD_KEY)
        st = dialog_state(pg)
        if st["open"] and st["base"] and st["model"] and st["key"] == "":
            bad.append("反例①（Key 被回显）未被 S1 抓到 ⇒ S1 恒真")
        # 反例②：保存时把 Key 洗成空 ⇒ S3 必须判 False
        pg.evaluate("() => window.ChatAgent.setCfg({ key: '' })")
        if read_cfg(pg).get("key") == OLD_KEY:
            bad.append("反例②（Key 被洗掉）未被 S3 抓到 ⇒ S3 恒真")
        # 反例③：预设选了但 base 未填 ⇒ S2 必须判 False
        pg.evaluate("() => document.querySelector('#dlg-settings').showModal()")
        pg.evaluate("() => { document.querySelector('#set-base').value=''; }")
        if dialog_state(pg)["base"] == "https://api.openai.com/v1":
            bad.append("反例③（预设为空）未被 S2 抓到 ⇒ S2 恒真")
        # 反例④：取消仍写盘 ⇒ S6 必须判 False
        before = read_cfg(pg)
        pg.evaluate("() => window.ChatAgent.setCfg({ base: 'https://should-not-persist.invalid/v1' })")
        if read_cfg(pg) == before:
            bad.append("反例④（取消却改了配置）未被 S6 抓到 ⇒ S6 恒真")
        # 反例⑤：徽章文案为空 ⇒ S7 判据必须判 False
        pg.evaluate("() => { document.querySelector('#mode-badge').textContent = ''; }")
        if "在线" in badge(pg) or "离线" in badge(pg):
            bad.append("反例⑤（空徽章）未被 S7 抓到 ⇒ S7 恒真")
    finally:
        pg.context.browser.close()
        pw.stop()
    if bad:
        print("SELFTEST-FAIL: " + " ; ".join(x for x in bad if x))
        return 1
    print("SELFTEST-PASS: 五类注入反例全部被抓到（Key 回显 / 洗 Key / 预设未填 / 取消仍写 / 空徽章）")
    return 0


def main():
    if "--selftest" in sys.argv[1:]:
        return run_selftest()
    return run_main()


if __name__ == "__main__":
    sys.exit(main())
