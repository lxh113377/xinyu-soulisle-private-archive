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


def check(name, ok, detail="", pg=None):
    if not ok and pg is not None:
        detail += diag(pg)                       # 只在报红时取证，PASS 不刷屏
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


def arm_settle(pg):
    """装一个"保存已落盘"的完成态探针。

    为什么需要它：`Settings` 的落盘写在 `<dialog>` 的 `close` 事件处理器里，而 `close` 是
    `dialog.close()` 之后才派发的 ⇒ 「点完按钮就读」在语义上读的是一个**未被同步保证**的时刻。
    本监听在应用之后注册，同一事件内监听器按注册顺序同步执行 ⇒ 计数增加代表应用的写入已跑完。
    若反过来先注册，会拿到"事件已触发但尚未写入"的中间态 —— 比不等待更糟的假完成。

    ⚠️ 诚实边界（r35 实测）：反例⑥在本机测到「`close()` 返回后同一次 evaluate 里已读到新值」
    ⇒ **竞态在本平台不成立，CI 那四条红不由它解释**，本轮不声称修好了 CI，只把"点了没落盘"
    变成必然超时判红（反例⑦）并让报红自带现场（`diag`）。
    """
    pg.evaluate("""() => {
      window.__saveDone = 0;
      document.querySelector('#dlg-settings').addEventListener(
        'close', () => { window.__saveDone += 1; });
    }""")


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
    arm_settle(pg)
    return pw, pg


def click_save(pg):
    """点保存并等到落盘完成态；点了却没关窗（未保存）会在 5s 后超时判红，不静默放过。"""
    n = pg.evaluate("() => window.__saveDone")
    pg.click("#btn-save-settings")
    pg.wait_for_function("() => window.__saveDone > %d" % n, timeout=5000)


def diag(pg):
    """失败时把"点完保存后页面上到底发生了什么"打全。

    立此条的原因（r35）：CI 上 S3/S4/S5/S7b 四条红、本机 9/9 绿且换 CI 版 demo-config 仍绿
    ⇒ 单一变量都没能复现。**判据若不带现场证据，下一轮就还在猜。**
    DOM 值 ≠ cfg 值 ⇒ 落盘处理器没跑；returnValue ≠ 'save' ⇒ 表单-对话框语义没走到；
    open 仍为 True ⇒ 点击根本没关窗。三种红各自指向不同修法。
    """
    try:
        return " | 现场=%s" % pg.evaluate("""() => {
          const d = document.querySelector('#dlg-settings');
          return JSON.stringify({
            open: d.open, rv: d.returnValue, done: window.__saveDone,
            domBase: document.querySelector('#set-base').value,
            cfg: JSON.parse(localStorage.getItem('peiliao.cfg.v1') || '{}'),
            ua: navigator.userAgent.replace(/\\s+/g, ' ').slice(0, 70)
          });
        }""")
    except Exception as exc:                       # 取证失败不许把判据本身弄红成崩
        return " | 现场取证失败:%s" % type(exc).__name__


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
        click_save(pg)
        c3 = read_cfg(pg)
        check("S3 保存时 Key 留空不洗掉已存密钥",
              c3.get("key") == OLD_KEY and c3.get("base") == "https://api.openai.com/v1",
              json.dumps(c3, ensure_ascii=False), pg=pg)
        # S4 填新 Key 保存
        open_dialog(pg)
        pg.fill("#set-key", NEW_KEY)
        click_save(pg)
        check("S4 填了新 Key 则写入新值", read_cfg(pg).get("key") == NEW_KEY,
              json.dumps(read_cfg(pg), ensure_ascii=False), pg=pg)
        # S5 流式开关
        open_dialog(pg)
        if pg.is_checked("#set-stream"):
            pg.uncheck("#set-stream")
            want = False
        else:
            pg.check("#set-stream")
            want = True
        click_save(pg)
        check("S5 逐字流式勾选状态落盘", read_cfg(pg).get("stream") is want,
              f"期望 {want} 实际 {read_cfg(pg).get('stream')}", pg=pg)
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
        click_save(pg)
        check("S7b 清掉 Key 后徽章回落离线（不伪装在线）", "离线" in badge(pg), badge(pg) + diag(pg))
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
        # 反例⑥：去**测**"点完就读"到底会不会读到旧值（不是先假设它成立）。
        #         r35 本机实测：`d.close('save')` 同步返回后同一次 evaluate 里已读到新值
        #         ⇒ 竞态在本平台不成立，**CI 那四条红不由它解释**；此条保留是为了：
        #         ① 若哪天平台行为变了（真排队），这里会立刻显出差异；② 强制本文件对"等待是否必要"持有证据。
        probe = "https://race-probe.invalid/v1"
        pg.evaluate("""(v) => {
          const d = document.querySelector('#dlg-settings');
          if (!d.open) d.showModal();
          document.querySelector('#set-base').value = v;
          d.close('save');
        }""", probe)
        raced = read_cfg(pg).get("base")
        pg.wait_for_function("() => (JSON.parse(localStorage.getItem(%s) || '{}')).base === %s"
                             % (json.dumps(CFG_KEY), json.dumps(probe)), timeout=5000)
        settled = read_cfg(pg).get("base")
        if settled != probe:
            bad.append("反例⑥b 等完成态之后仍读不到新值 ⇒ 落盘链路坏了")
        print("  · 反例⑥ 竞态实测：close() 同步返回时读到 %r，等完成态后读到 %r，"
              "两者相同 ⇒ 本平台无此竞态（不相同 ⇒ 等待是必需的）" % (raced, settled))
        # 反例⑦：把保存按钮改成"点了不关窗"（= 没触发落盘）⇒ click_save 必须超时判红，
        #         否则等待只是装饰，删掉也不会红（那正是 r35 之前 CI 与本地不同结果的形态）。
        pg.evaluate("() => { const d = document.querySelector('#dlg-settings'); "
                    "if (!d.open) d.showModal(); "
                    "document.querySelector('#btn-save-settings').type = 'button'; }")
        try:
            click_save(pg)
            bad.append("反例⑦（保存不关窗）未被 click_save 抓到 ⇒ 完成态等待恒真")
        except Exception:
            print("  · 反例⑦ 如预期抓红（保存未落盘 ⇒ 等待超时，不静默放过）")
    finally:
        pg.context.browser.close()
        pw.stop()
    if bad:
        print("SELFTEST-FAIL: " + " ; ".join(x for x in bad if x))
        return 1
    print("SELFTEST-PASS: 注入反例全部被抓到（Key 回显 / 洗 Key / 预设未填 / 取消仍写 / 空徽章 / "
          "落盘竞态 / 保存不关窗）—— 条数以本函数实际反例为准，正文不抄数字")
    return 0


def main():
    if "--selftest" in sys.argv[1:]:
        return run_selftest()
    return run_main()


if __name__ == "__main__":
    sys.exit(main())
