# 07-next-steps 卷67 — r67（struct 两态拆分 + JS 语法面入账 + linter 取舍登记）

> 取号 `volume_alloc.py`（O_EXCL）｜报告 `交付物/对标分析报告-2026-09-28-r67.md`（卷号以 volume_alloc 实发 67 为准，草稿曾误写 68）

## 一、本轮做了两条（均带变异/双向证据）

1. **拆 `rows[].struct` 两态**（r66 报告 G3 落地）：旧 `sorted(s) if s else None` 把「没测到」与
   「测到但零命中」折叠成同一个 `null`。现由唯一出口 `row_shape()` 分开：`null`=未测、`[]`=测到零命中。
   真面立刻改写可声明事实：**16 仓里 7 仓是"测到了但零命中"**（此前与盲区同形）。
   反例腿 4 条挂进 `--selftest`；**变异对照**＝把出口换回旧折叠写法（r66 前盘上真实那一行）
   → `SELFTEST-FAIL 两态折叠复发…实得 None`。⚠️ 第一次变异打在临时目录时红在
   `ModuleNotFoundError`——**环境错不是判据红**，那条对照不作数；按「夹具须落在被保护分支的输入面内」
   移进 `_test/` 重做才拿到真红。真实源跑前跑后 sha 相等。
2. **JS 语法守卫** `_test/js_syntax_check.py`：`src/js` 与 `deploy/xinyu/js` 双份逐文件 `node --check`，
   两面 **28 个文件全过**。此前 97 道电池里没有任何静态语法判据（`grep -l "node --check" _test/*`=0），
   parse 错只能被浏览器判据**间接**发现，报出来是"断言超时"而非"哪个文件第几行"。
   口径钉死：覆盖面=语法与严格模式可解析性；**不覆盖面**=风格/未定义变量/lint 规则 ⇒ 禁读作"有 lint"。
   三态 0/1/2，node 缺失记 UNVERIFIED 不记通过；桩 5 腿含"枚举下限"（FACES 拼错会静默少测）。

## 二、linter 取舍（已登记 ROADMAP，不再含糊）

实测分母 counted=16 下 peers 有 linter 仅 **2/16** ⇒ "业界都有"不成立。本项目**只做可解析性这一半**、
不装 ESLint 全量：零构建前端引 lint 必带 `node_modules`，与体量治理 `repo_max`/缓存 TTL 冲突；
且风格规则集不产出可现场复跑的证据。未覆盖面明写，对外不得称"有 lint"。

## 三、复算与消费者同步

- `python _test/js_syntax_check.py` / `--selftest`；`python _test/peer_quality_tooling_probe.py --selftest`。
- 电池 97→**99**，三处消费者同批：`run_all_suites.py` SUITES ＋ README「（99 套件）」＋
  `docs/quality-gates.md` 明细行。⚠️ 第一次只改前两处即被 `repo_config` **G16 双向对账**当场拦红
  （漏登 1 条），补登后 `REPO-CONFIG-PASS` 14 条。
- 自省一条执行偏差：`selftest rc=0` 一度是我把管道尾 `tail` 的退出码当成 python 的（本仓在册
  「退出码死在管道里」当场复现），改直取 rc 后立刻暴露打印崩。

## 四、未闭合（不折叠）

`live_sync` 仍判红（公网缺 r65 两处修复，发布需授权）｜CI 是否因本轮转绿只认推送后回执｜
flake 对标仍缺原文｜`node --check` 只覆盖经典脚本，ESM 目标的覆盖面本轮未单独证。
