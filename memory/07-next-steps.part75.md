# 07-next-steps 卷75 — r73（对标装上第二把尺：两尺交集为 0 这一格能力被证伪）

> 取号 `volume_alloc.py`（O_EXCL）｜报告 `交付物/对标分析报告-2026-09-28-r73.md`｜入场基线 `8afe0e8`

## 一、本轮最重要的一条实测（会推翻上一轮的表）

`streaming` 这格，16 仓同一轮两把尺：
- 文件名法（`CAP_RULES`，十几轮以来的唯一依据）：`CheaperjamRen/leemo`、`lobehub/lobehub`
- 内容法（r73 新增 `--cap-channel`，读 description+homepage+README）：`Bwcx-songyu/MoodChat`（Spring AI Reactor Flux 流式）、
  `ddxfish/sapphire`（SSE-driven reactions）
- **交集 = 0，并集 = 4**（另 `morettt/my-neuro` 是"直播"，属 `media_stream`，不算逐字流式）
⇒ "对手只有 2/16 做流式"这句在旧台账里被反复抄写，**两把尺都不支持它**。报告口径改为两尺并陈、各自点名测到谁。
`e2e_browser` 方向相反：文件名法 3 家、内容法只有 1 家（README 不写测试是常态），
`chibi` 是"把浏览器当产品功能"（`browser_tool_feature`）⇒ **内容法也不得反过来当权威**，通道不改 caps。

## 二、通道首跑抓到我自己两处冒充（已修＋永久反例）

1. `dash` 把 `dash.cloudflare.com` 认成 DASH 流媒体 ⇒ 去掉裸 dash，改 `dynamic adaptive streaming`。
2. 裸 `playwright` 把 README 里的 `microsoft/playwright-mcp`（网页操作工具）认成"有 e2e 测试"
   ⇒ 要求**工具名与测试语境邻近**（两侧顺序都行），并加**合规正例**（`Playwright test suite` 仍算）防砍成恒假。
- 两条负向腿**照抄实测文本**（A-get-memory ⑨：对照必须打到真实本文，不能只有誊写夹具）；
  **变异对照走纯内存 monkeypatch**（把两条正则退回首跑版 ⇒ `rc=1` 各自点名；未变异 `rc=0`；复位 `rc=0`），
  不碰真实源、无副本残留（守 ⑰-b）。修后重跑：`media_stream 2→1`、`test_e2e 2→1`。

## 三、一次"数字动了但断言没动"的自纠

夹具里写 `got = cap_channel_class(...)` **遮蔽**了同函数后半段用作漂移对照组的 `got`
⇒ `SELFTEST-PASS` 门面行「全等对照零误报（4 条）」当场变 **（20 条）**（20 = `len("browser_tool_feature")`）。
断言没错，只有**印出来的数**来自被遮蔽变量。改名 `chan_cls` 后复跑回到 4 条。
⇒ 新判据上线时，凡门面行带计数，须核对"这个数在改动前后是否稳定"；本轮靠"4 变 20 不合理"抓到。

## 四、G8 时序本轮改正

【数据流假设】块 `轮73-cap-channel-second` 在**首个源码写入之前**落盘并跑 `[GATE:dag-pass]`，
改掉 r71/r72 连续两轮"改完才补块"的坏形（V10.79.0 要求 precheck 与写盘同链）。

## 五、未闭合（不折叠）

R1↔切版锁死（实测 **`feats=8/5`**，且本轮 feat 提交后会到 9/5；须授权发布或授权降 advisory）｜`live_sync`/`ci_status` 待发布授权｜
`jar_shape` 未占独立 SUITES 名额（他方第 4 轮未入库，`census 在 HEAD 里=False`）｜
两格能力的"证据文件行"待落 `docs/quality-gates.md`（同因，该文件在途）｜真机复跑｜flake 原文｜
8123 旧 jar 进程｜焚诀根 5 个 0 字节散件（他人现场，G-b 拦）｜`i18n_locale` 按裁决排后
