# 07 分卷 20 — r30 迁出：CI 覆盖面三条判据 + 台账增补

> 由 `07-next-steps.md`（索引壳，R161 ≤4096B）迁出。迁出轮次 r30（2026-09-25）。
> 同族坑**一到五次**的权威台账在 `part18`，本卷不重复抄表，只登记 r30 新增项（避免两处真相）。

## 一、CI 判据覆盖面（r28 改，r29–r30 加守卫）

原先 CI 只跑 `browser_check` 一条 ⇒ 新增判据**只在本地生效**（"装了不等于在用"）。
现改为整电池 `python _test/run_all_suites.py --exclude-llm`，并由三条常驻判据分别盯着：

| 判据 | 盯什么 | 实跑口径 |
|---|---|---|
| **G10** `repo_config_check.py` | 覆盖面分母：CI 是否真跑电池、豁免名单是否点名（`实跑 + 豁免 == 总数`） | 缺电池步骤即红 |
| **G11** `repo_config_check.py` | 依赖清单：CI 调用的脚本里第三方 import 是否都在 `_test/requirements.txt` | 名单按「CI 会调用的脚本」取，不是全仓 |
| 新判据 `_test/ci_status_check.py` | **受理面三态**：HEAD 最近一次 run 归为 `PASS` / `CODE_FAIL` / `ENV_BLOCKED` | 未取到有效结论打印 `CI-STATUS-PENDING`，禁止声称「CI 已验」 |

> G11 首跑即查出 CI 已红 4 个提交（本地装了 PyYAML 所以看不见）—— 见 `CHANGELOG.md` r28。

## 二、同族坑台账 r30 增补（前五次见 `part18`）

| 轮次 | 形态 | 根因 | 收口手段 |
|---|---|---|---|
| r30 | 索引壳超限 | `07-next-steps.md` 被 r30 写成 4612B，超 R161 的 4096B | 本卷即迁出产物；壳体积落盘前用 `assert size <= 4096` 卡死，不靠"记得回头查" |

**仍开的口子**：G 系列只守 README 的数字，05/06/07 正文数字无守卫 ⇒ 已改为「正文只写复算命令」，
扩到全仓文档数字需老大拍板。

## 三、成片重录的前置条件（r30 实测，pipeline 自带守卫）

`_test/demo_video_pipeline.py` 开录前有 assert：**要求同源代理链路**，本机 `src/js/demo-config.js` 必须
`proxy` 有值且 `base` 为空；当前是浏览器直连（键为 `base`/`key`/`model`/`remote`/`emotionRemote`），
守卫直接 `AssertionError` 拦下 —— **这是正确行为，不绕**。

三步（下一轮首件做）：

1. 先取该文件 sha256 存档：`python -c "import hashlib,pathlib;print(hashlib.sha256(pathlib.Path('src/js/demo-config.js').read_bytes()).hexdigest())"`
2. 临时改 `proxy: "http://127.0.0.1:8123/api/chat"`、`base` 置空 → `python _test/demo_video_pipeline.py`
3. 录完按哈希**还原**并复核一致，再复跑 `public_check` + `live_sync`，把成片指纹写进 `提交清单与验收状态.md`

> 该文件 gitignored，属"环境模拟改权威源"族：备份/还原必须机器核验（同 r28 `ci_equiv_rehearsal.py` 的做法），
> 不能只写"记得改回来"。
