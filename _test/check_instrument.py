"""判据仪器的统一兜底（r112 · BLIND-RED 族收口）

立规背景（r105 一手）：一台判据若**抛了栈却没印结论行**，电池只看到 rc≠0，
于是它在账面上与「环境未验」长得一模一样 —— 真缺陷就这样被仪器自己的崩溃盖住。
r105 把这类记为 BLIND-RED，当时 6 条，本轮收口余下 4 条并立本模块防再犯。

本模块的三条语义（**rc 与结论行必须成套**，缺一即视为仪器故障）：

  ┌ 结论            ┌ rc ┌ 含义
  │ XXX-PASS        │ 0  │ 判据跑完且通过
  │ XXX-RED         │ 1  │ 判据跑完，产品/代码层面判红（**有读数、有点名**）
  │ XXX-UNVERIFIED  │ 2  │ 判据**没跑完**（超时/环境/依赖缺失）——不得当绿，也不得冒充红

为什么 UNVERIFIED 必须是 rc=2 而不是 1：rc=1 会被读成「产品红」，
于是「仪器崩了」与「产品有问题」在台账上不可分，下一次排查会往错的方向走。

用法：
    from check_instrument import wait_done, unverified, instrument_red
    wait_done(page, "() => window.__XINYU__ && ...", 15000, "J4-MEMORY", "开场演示未回到 done")

守卫：`_test/blindred_guard_check.py`（AST 清点：裸 assert / 裸 wait 且无兜底 ⇒ 判红点名）
"""
import os
import subprocess
import sys


def unverified(name, what, exc=None):
    """仪器没跑完 ⇒ 落「未验」结论行 + rc=2，绝不裸抛栈。"""
    tail = "" if exc is None else "：%s: %s" % (type(exc).__name__, exc)
    print("%s-UNVERIFIED %s%s" % (name, what, tail))
    print("   处置：本件判据未跑完（rc=2）。不得记为绿，也不得记为产品红 ——"
          " 先修仪器或补环境再谈判据结论。")
    sys.exit(2)


def instrument_red(name, what):
    """判据跑完且判红 ⇒ 点名 + rc=1（what 必须自带读数，否则不可归因）。"""
    print("%s-RED %s" % (name, what))
    sys.exit(1)


def wait_done(page, expr, timeout, name, what):
    """wait_for_function 的唯一允许形态：超时/异常一律收敛成 UNVERIFIED。

    直接写 page.wait_for_function(...) 会让 playwright 抛 TimeoutError，
    脚本在印结论行之前就死掉 —— 这正是 BLIND-RED 的成因。
    """
    try:
        page.wait_for_function(expr, timeout=timeout)
    except Exception as e:  # playwright TimeoutError / Error / 页面已关
        unverified(name, "%s（wait_for_function %dms 未完成）" % (what, timeout), e)


# r170 S4：环境不可达不是「产品红」也不是「仪器崩」，是**没跑成**。
# 一手实发（同日两次整跑对照）：8123 无人监听时 `page.goto` 抛
# `Error: Page.goto: net::ERR_CONNECTION_REFUSED at http://127.0.0.1:8123/index.html`，
# 原 `else` 分支把它落成 `NAME-RED …（判据未出结论）` + rc=1 ⇒ 电池记成产品红，
# 而同仓 `storage_resilience` 对同一事实正确回 rc=2。**同一环境事实在同一次整跑里被落成两档**
# （一次跑：16 条 ENV-UNVERIFIED vs 9 条 BLIND-RED）——假红会把真红淹掉，且把人往错方向支使。
ENV_MARKERS = (
    "ERR_CONNECTION_REFUSED", "ERR_CONNECTION_RESET", "ERR_CONNECTION_ABORTED",
    "ERR_CONNECTION_TIMED_OUT", "ERR_NAME_NOT_RESOLVED", "ERR_INTERNET_DISCONNECTED",
    "ERR_ADDRESS_UNREACHABLE", "ERR_EMPTY_RESPONSE",
    "ECONNREFUSED", "ECONNRESET", "Connection refused", "ConnectionRefusedError",
    "服务未在", "被测服务不在", "没有监听",
)


def verdict_for(etype_name, msg):
    """纯函数：(异常类名, 异常消息) → (结论档, rc)。判定写成纯函数，selftest 喂样本即可，
    不必为每条腿起子进程（起子进程会让「测的到底是哪条」依赖解释器与启动顺序）。

    四档与模块头的语义表一一对应：
      timeout / env → UNVERIFIED rc=2（判据没跑完：不得当绿，也不得冒充红）
      assertion     → RED        rc=1（判据跑完，产品/代码判红）
      instrument    → RED        rc=1（仪器自己的 bug，必须响亮，不许静默）
    """
    low = msg or ""
    if issubclass_name(etype_name, "Timeout") or "Timeout" in etype_name:
        return "UNVERIFIED", 2
    if any(m in low for m in ENV_MARKERS):
        return "UNVERIFIED", 2
    if etype_name == "AssertionError":
        return "RED", 1
    return "RED", 1


def issubclass_name(etype_name, frag):
    """按**名字**判而非按继承判 —— playwright 的 TimeoutError 不继承内置那个（本模块在册的老坑）。"""
    return frag in (etype_name or "")


def install_excepthook(name):
    """进程级兜底：给**顶层脚本形态**的判据装上「永不零结论行」的保险。

    与「逐个把 assert 包进 try」相比：
      · 低侵入 —— 2 行覆盖整份脚本（几百行的顶层脚本不必整体缩进）；
      · 更根本 —— 兜住的是**所有**未捕获异常，不止 assert / wait 两类
        （比如 KeyError、playwright Error、页面已关都能打出结论行）。
    实测（r113）：excepthook 里的 sys.exit(code) 真能决定进程退出码，
    且不会打印 "Error in sys.excepthook" 噪音。

    语义（与 unverified / instrument_red 完全一致，只是粒度从"一处"变成"一份脚本"）：
      AssertionError        → NAME-RED        rc=1   判据跑完、产品/代码判红
      TimeoutError/*Timeout → NAME-UNVERIFIED rc=2   判据没跑完，不得冒充红
      环境不可达（r170）    → NAME-UNVERIFIED rc=2   被测服务没起 ≠ 产品红，也不等于仪器崩
      其他异常              → NAME-RED        rc=1   仪器异常（同样点名，不裸抛）
    """
    def hook(etype, e, tb):
        if issubclass(etype, KeyboardInterrupt):
            sys.__excepthook__(etype, e, tb)
            return
        msg = str(e) or "(异常无消息 ⇒ 不可归因，须给断言/等待补读数)"
        kind, code = verdict_for(etype.__name__, msg)
        if kind == "UNVERIFIED":
            why = "判据未跑完（超时）" if "Timeout" in etype.__name__ else "被测对象不可达（环境）"
            print("%s-UNVERIFIED %s：%s: %s" % (name, why, etype.__name__, msg))
            print("   处置：本件判据没跑成（rc=2）。不得记为绿，也不得记为产品红 ——"
                  " 先起被测面（定版 jar@8123：java -jar server/target/soulisle-server.jar"
                  " --server.port=8123）再谈判据结论。")
        elif etype.__name__ == "AssertionError":
            print("%s-RED 断言未通过：%s" % (name, msg))
        else:
            print("%s-RED 仪器异常（判据未出结论）：%s: %s" % (name, etype.__name__, msg))
        print("   （结论行由 check_instrument.install_excepthook 兜底产出，rc=%d）" % code)
        sys.stdout.flush()
        sys.exit(code)

    sys.excepthook = hook


if __name__ == "__main__":
    # --selftest：三件必须各自成立 ——
    #   ① 真超时/真不可达 ⇒ 落 UNVERIFIED rc=2（本模块存在的理由）
    #   ② 断言失败与仪器 bug ⇒ **必须仍是 rc=1**（反向腿：只把「该未验的判成未验」的尺
    #      等于把一切判成未验，那比假红更糟 —— 它会安静地让所有真红消失）
    #   ③ 端到端：excepthook 装好后真的决定进程退出码
    bad = []
    cases = [
        ("Error", "Page.goto: net::ERR_CONNECTION_REFUSED at http://127.0.0.1:8123/index.html",
         "UNVERIFIED", 2),
        ("TimeoutError", "Timeout 15000ms exceeded", "UNVERIFIED", 2),
        ("Error", "page.wait_for_function: Execution context was destroyed", "RED", 1),
        ("AssertionError", "J4 断言：清除后条数应为 0，实测 3", "RED", 1),
        ("KeyError", "'choices'", "RED", 1),
    ]
    for etn, m, want_kind, want_rc in cases:
        kind, rc = verdict_for(etn, m)
        if (kind, rc) != (want_kind, want_rc):
            bad.append("%s/%s → %s/%s（应为 %s/%s）" % (etn, m[:28], kind, rc, want_kind, want_rc))
    if not ENV_MARKERS:
        bad.append("环境标记被清空 ⇒ 第一腿恒假")
    # 端到端腿：起一个子进程，让它在 goto 风格的「不可达」异常下死掉，看真退出码
    probe = ("import sys; sys.path.insert(0, %r)\n"
             "from check_instrument import install_excepthook\n"
             "install_excepthook('E2E')\n"
             "raise RuntimeError('Page.goto: net::ERR_CONNECTION_REFUSED at http://127.0.0.1:8123/')\n"
             % os.path.dirname(os.path.abspath(__file__)))
    r = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, timeout=60)
    if r.returncode != 2:
        bad.append("端到端：不可达异常实得 rc=%s（应为 2）输出=%s" % (r.returncode, (r.stdout or "")[:120]))
    # 端到端腿②（r112 原有那条的替身）：`wait_done` 遇必然超时必须落 rc=2 而不是裸抛栈。
    # 原来这条在主进程里直接调 wait_done，靠 SystemExit 读码 —— 一旦它改成抛栈，本自检会**崩**
    # 而不是报「腿失效」，红因就被读成「文件坏了」。搬进子进程后退出码可核、结论行可核。
    wd = ("import sys; sys.path.insert(0, %r)\n"
          "from check_instrument import wait_done\n"
          "class P:\n"
          "    def wait_for_function(self, *a, **k): raise TimeoutError('模拟：wait_for_function 超时')\n"
          "wait_done(P(), '() => true', 10, 'SELFTEST', '模拟超时')\n"
          % os.path.dirname(os.path.abspath(__file__)))
    r2 = subprocess.run([sys.executable, "-c", wd], capture_output=True, text=True, timeout=60)
    if r2.returncode != 2 or "SELFTEST-UNVERIFIED" not in (r2.stdout or ""):
        bad.append("端到端：wait_done 超时未落 UNVERIFIED+rc=2（实得 rc=%s）" % r2.returncode)
    print("CHECK-INSTRUMENT-SELFTEST-%s（%d 档判定 + 端到端两条：不可达异常、wait_done 超时）"
          % ("PASS" if not bad else "FAIL: " + "; ".join(bad), len(cases)))
    sys.exit(1 if bad else 0)
