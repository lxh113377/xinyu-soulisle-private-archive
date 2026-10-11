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
      其他异常              → NAME-RED        rc=1   仪器异常（同样点名，不裸抛）
    """
    def hook(etype, e, tb):
        if issubclass(etype, KeyboardInterrupt):
            sys.__excepthook__(etype, e, tb)
            return
        msg = str(e) or "(异常无消息 ⇒ 不可归因，须给断言/等待补读数)"
        # playwright 的 TimeoutError 不继承内置 TimeoutError，故按名字兜住
        if issubclass(etype, TimeoutError) or "Timeout" in etype.__name__:
            print("%s-UNVERIFIED 判据未跑完（超时）：%s" % (name, msg))
            code = 2
        elif issubclass(etype, AssertionError):
            print("%s-RED 断言未通过：%s" % (name, msg))
            code = 1
        else:
            print("%s-RED 仪器异常（判据未出结论）：%s: %s" % (name, etype.__name__, msg))
            code = 1
        print("   （结论行由 check_instrument.install_excepthook 兜底产出，rc=%d）" % code)
        sys.stdout.flush()
        sys.exit(code)

    sys.excepthook = hook


if __name__ == "__main__":
    # --selftest：用「必然超时」的假 page 验证超时真的会落成 UNVERIFIED + rc=2，
    # 而不是裸抛栈（本模块存在的唯一理由就是这条，必须能自证）。
    class _TimeoutPage:
        def wait_for_function(self, *a, **k):
            raise TimeoutError("模拟：wait_for_function 超时")

    try:
        wait_done(_TimeoutPage(), "() => true", 10, "SELFTEST", "模拟超时")
    except SystemExit as e:
        print("check_instrument 自检：退出码=%s（应为 2 = 未验，不是 0/1）" % e.code)
        sys.exit(0 if e.code == 2 else 1)
    print("check_instrument 自检失败：超时没有落成 UNVERIFIED（裸抛了）")
    sys.exit(1)
