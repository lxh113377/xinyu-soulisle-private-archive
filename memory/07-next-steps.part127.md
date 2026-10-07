# 07-next-steps 分卷 part127 — r99 收口（2026-10-07，对标增量轮）

## 本轮性质
「从零八维对标」经现状核验改判为**增量 r99**：r21→r98 已跑 46 份归档、peers 名册 16 仓、
r98 报告已含八维表四板块。报告 = `交付物/对标分析报告-2026-10-07-r99.md`。
老大当轮裁决：不提 issue/PR、不做 peers burst 重采、四项取「收口打头 + 三条 r99」。

## 五项改造回执（两笔提交）
- **① `8e2ef95`（P0）**：r98 标 ✅ 却从未入库的件全部入提交面 —— `git ls-tree -r HEAD`
  对 `perf_ramp_delta|timing_coupling` 由 0 命中改 2 命中。根因不是忘记 add，是 **G16 ghost 腿
  取 `os.listdir` 面**（文件在盘未入库时它判绿）⇒ 电池 ⇄ 文档 ⇄ **git index** 三面化，
  取 index 不取 HEAD（钩子在提交前跑，HEAD 面会拦掉"补 add 的第一笔提交"）。
  反例三向齐（空面必红/全跟踪不误伤/独立现算同起同落）。add 前真面红点名 2 条 ⇒ add 后 PASS。
  `bench-r98-battery.log` 实测 10,714 个 NUL（PowerShell 重定向 = UTF-16）⇒ 转 UTF-8/LF 才入库。
- **②③④⑤ `b08cbaf`**：漂移尺接受理面（132→133）+ C1_HARD 逐件评审 + G16 第四段盯文档抄件。
  合一笔的原因：三项共享 `docs/quality-gates.md` 44–52 行的同几行，强拆会造出
  「README 说 133 而 SUITES 还是 132」的自相矛盾中间态。

## 本轮两条新知识（进报告 §2，别再踩）
1. **同日同机噪声实测**：`work_per_thread=4` 档内带宽 13.5%~255.8%（首轮冷启 t8=986.6 rps），
   `work=32` ≤38.4% ⇒ r96 那条「8→64 无塌方点」落在噪声带里；40% 阈值被同日两份踩穿一次
   （−40.1%，什么都没坏）。处置 = 修仪器（work 4→32）+ 阈值按实测定 50% + 口径腿拦新旧互比。
2. **完成态等待的两种错法**（改 ux_guards 时各红一次）：等「气泡数 +1」败给窗口化从顶部裁节点
   （总数会**下降**）；等「中间态」败给离线模板 3ms 回完（态在首次轮询前已过去）。
   终版 = 点提交前给当时最后一条盖身份章，之后等"带 data-emotion 且无章"。

## r100 入口（五条，每条带复算命令）
① 错峰单跑重采 peers 台账（`python _test/ledger_age_check.py`；fuse=7 天，超龄点 ~10-12；禁 burst，r96 撞限流实测）
② 每档重复取中位数把检测限从 50% 往下压 —— **先提仪器精度再谈调小阈值**
③ `clean_clone`/`rescan_shots`/`public_check` 三处：先把 Playwright 超时折成 `check(...,False)` 再改完成态
   （否则 FAIL 变 CRASH，违三态纪律；现读面 `python _test/timing_coupling_check.py --json …` 的 records 可指认）
④ 产品暴露 `window.__pendingTurns`，替掉 `ux_guards` 的 6000ms（评审账里唯一 `unobservable`）
⑤ 确认 r99 两笔推送后 CI 的 133 套件真执行位都在（`gh run view --json jobs`，不信管道 rc）
⑥ ~~**r99b 新发现**：`preflight` 拿 mtime 当权威~~ ⇒ **同日 r99c 已修**：新鲜度改判「jar 内资源逐件 SHA256 ⇄ git 面」
   +「`Implementation-Version` ⇄ pom 版本（解析须剥 `<parent>`）」，mtime 降为提示；selftest 的 `total`
   从手抄常量 5 改结构推导；回归钉＝把 jar mtime 拨早于源码必须仍 PASS（真机实测已过）。
   新遗留（r100）：**java 编译件仍无法从产物侧证新鲜** ⇒ 构建时写 stamp（`build_jar.py` 落 `server/target/.built-rev`）。

## P0（永不为空）

- 全文已迁至 **part128**（4KB 单卷硬限 R161；r99 追加 CI 归因后本卷顶到 4,180B）。复算：`wc -c memory/07-next-steps.part12*.md`。
