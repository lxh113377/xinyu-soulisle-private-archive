# 任务卡 — 2026-09-24 对标分析与工程文档补齐轮

## 本轮目标
与 GitHub 同类优质开源项目（LobeChat / Open-LLM-VTuber / SillyTavern）七维度对标，产出结构化报告，并直接执行报告中**非破坏性高优先级改进**（纯新增文件 + README 增补，零运行时代码改动）。

## 验收判据
1. `交付物/对标分析报告-2026-09-24.md` 含：对比总览表 / 逐项差距 / 改进建议清单(高中低) / 实施路径
2. 新增 `.env.example`、`CONTRIBUTING.md`、`SECURITY.md`、`CHANGELOG.md`、`.github/workflows/ci.yml`、issue/PR 模板、README badge 化 + TOC + `README.en.md`
3. 红线不破：不改 `src/`、`deploy/`、`server/` 任何运行时代码；不碰 `demo-config.js`；不触碰上轮被 Mimosa 钩子拦截的 7 个暂存文件（提交用 pathspec 限定）
4. 提交后 push 并核对 SHA（R20 #20 四步基线）

## 备选方案与取舍
- A. 本轮连 SSE 流式输出一起做 —— **弃**：违反 J2「契约 1:1」验收判据红线，距 09-30 截止仅 6 天，波及前端渲染/双后端/18 个回归脚本，风险不对称。
- B. 只出报告不动手 —— **弃**：用户明示直接执行；且 badge/CI/贡献文档是评委可见的低成本高收益项。
- C. **选定**：报告 + 纯文档/CI 类执行，流式/PWA/移动端列为赛后 P1。

## to-do
① 报告 ② .env.example ③ CONTRIBUTING/SECURITY/CHANGELOG ④ CI workflow ⑤ issue/PR 模板 ⑥ README 增补 + 英文版 ⑦ 本地可跑项验证 ⑧ pathspec 提交 + push

## checkpoint / 回滚预案
全部为新增文件或 README 单文件改动；回滚 = `git revert` 本轮提交（pathspec 提交不含他人在制改动），或逐文件移入回收站（`handoff.py recycle`）。

## 决策记录
- SSE 流式、PWA、i18n、主题令牌化 → 登记为赛后 P1（详见报告 §4）
