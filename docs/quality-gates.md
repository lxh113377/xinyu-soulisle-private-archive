# 判据体系明细（从 README 迁出，r39 体量体检）

> README 是每轮注入件，超 16,384B 预算即算**每轮重复付费**；本节明细改放这里，README 留指针。
> 内容逐字迁自 README「## ✅ 验证」一节，未改写（取证见当日会话日志）。


```powershell
python _test/run_all_suites.py           # ★ 全量电池（47 套件逐条直取 rc，聚合不掩盖单项失败）
python _test/browser_check.py            # 离线降级 / 双色 / 滚动淡入淡出，输出 ALL-ASSERT-PASS
python _test/deploy_sync_check.py        # src → deploy/xinyu 三类比对（MISSING/DIFF/EXTRA 归零）
python _test/engine_consistency_check.py # JS 引擎 ↔ Java 引擎逐项对账（词表结构级）
python _test/emotion_wiring_check.py     # 情绪后端化接线：接线顺序/公网零开关/危机短路/熔断回落/双端一致（9 项 + --selftest）
python _test/strategy_check.py           # 共情策略表 ↔ 词表成对性（--selftest 注入分叉证判据非恒真）
node _test/emotion_eval.js               # 前端情绪评测集复跑
python _test/stream_contract.py          # A 非流式契约不破 / B SSE 含内容帧≥2 / C 前端逐字且回落不冒充
python _test/ux_guards_check.py          # TTS 朗读 / 对话窗口化 / 响应式与粒子降档（逐项 21 判据）
python _test/size_budget_check.py        # 首屏体积预算 + 「新文件必须登记」覆盖判据（漏登记即红）
python _test/vendor_freshness_check.py   # vendor 完整性哈希 + 版本对账；--check-upstream 报上游漂移
python _test/benchmark_metrics.py        # 对标源数据台账（16 仓指标 + 与上次快照逐字段漂移）；联网采集，人工轮次跑
python _test/live_sync_check.py          # 线上 `/` 与 deploy/xinyu 逐字节比对（部署未跟进即红）
python _test/safety_guard_check.py        # 输入侧护栏行为验证：注入 6 例必须点名 + 正常 6 例不得误伤（含 --selftest）
python _test/eol_parity_check.py         # 行尾确定性：工作树字节 == 仓库 blob 字节 + binary 形状（E1–E4，8 类 --selftest）
python _test/patch_apply.py --selftest       # 补丁器自证：锚点失配/歧义/同义/插入/正常/缺失 + 行尾两侧 八类行为（防"没报错=生效了"）
python _test/api_contract_check.py       # 接口契约三方对账（控制器↔docs/openapi.yaml↔前端）+ 11 条运行态真实打 + C6 零漏探测
python _test/repo_config_check.py --online # 仓库配置自洽：dependabot schema/目录可达 + 文档数字断言==机器实测 + 默认分支受理面
```

> 前置：多数判据需 fat jar 起在 8123（`java -jar server/target/soulisle-server.jar --server.port=8123`，
> 工作目录 = 项目根，`DEEPSEEK_KEY` 走进程环境）。⚠️ 改 `src/` 后**必须重启 jar** 再验（进程内静态资源有缓存）。

GitHub Actions 四条门禁（`.github/workflows/ci.yml`）：同步守卫+评测+策略表+体积+**vendor 供给链**+密钥扫描、Java 构建+**词表一致性红线**（此前只写在 `memory/AGENTS.md` 靠人记，现已机器化）、浏览器回归（runner 无 GPU，强制 SwiftShader）、公网新鲜度。
四条 job 都挂在 `main` push 上真跑；浏览器 job 首轮就抓到本机看不到的真实缺陷：`src/js/demo-config.js` 被 gitignore，全新 clone 下 `<script>` 静态引它 → 首屏 3 个 404 打破「console 0 报错」。修法＝CI 自动用公网零密钥 stub 补占位（本地按 `CONTRIBUTING.md` 第一步手工补一次）。

**受理面状态以远端为准，不在本文件写死**：`python _test/ci_status_check.py`（HEAD 最近一次 run 三态分类：PASS / CODE_FAIL / ENV_BLOCKED）。r35（2026-09-26）实测到一次"本机 37 条全绿、CI 两条 job 真红"的分叉，三条根因与修法见 `交付物/对标分析报告-2026-09-26.md` §2；同类分叉已封成常驻判据（密钥扫描两侧同源 + `voice_selftest` + settings 落盘完成态等待）。

最近实测（2026-09-26 对标轮 r35）：全量电池 **47 条套件实跑全绿**（r36 增 `eol_parity`±自证：工作树字节 == 仓库 blob 字节，于是本仓「逐字节 / SHA256 / 字节预算」类主张在任何机器 clone 上可复算），且远端 HEAD run `36220200506` 四条 job 逐项 `success`（r35 收口，2026-09-26 实测）。前置探针 `preflight` 打头：被测服务没起时收口行写 `ENV-UNVERIFIED` 而不是判红）（含受理面体检 ci_status，在 CI 内部自动 SKIP）；情绪评测 **73 条 / 98.6% / 危机 6-6**（JS ↔ Java 逐项全等）；`emotion_wiring_check` 9/9（后端路径实测生效 + 不可达即熔断不伪装 + 危机未经后端）；gsap 3.15.0 升级后 `browser_check`/`lightshow`/`pixel_dual` 全绿；首屏关键路径 831,152 B（预算 858,752 B 内；r36 行尾归一后从 832,382 降为现值，复算 `python _test/size_budget_check.py`）；公网已重新部署并 `LIVE-SYNC-PASS`。


---
