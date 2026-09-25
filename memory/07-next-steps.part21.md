# 07 分卷 21 — r30：技能治理链四条挂账的闭环全记录

> 由 `07-next-steps.md`（索引壳，R161 ≤4096B）迁出。写前 `assert not exists` 占号；体积断言先于落盘（part20 二）。

## 一、四条处置结果

| # | 挂账来源 | 处置 | 落点 |
|---|---|---|---|
| ① | r25：同族坑第三次复发即禁写"下次注意"、须当轮工具化 | ✅ 已落地 | A-get-memory **V4.33.0** Step 2.7「复发计数硬门槛」 |
| ② | r25：新判据当轮须喂真实动作 + 红/绿两侧各成类 | ✅ **改判为已承接** | 已在 A-get-memory V4.30.0 Step 2.7 三条硬判据在案 ⇒ 按 consulting M5⑥「同一判断只有一处实现」，**不在 consulting-analysis 复制第二处** |
| ③ | r30：失败面必须与成功面同条登记，禁只写"已交付" | ✅ 已落地 | A-get-memory **V4.32.0** Step 2.5 第 8 条 |
| ④ | r30：对标表观测面不对称时单列盲点而非并入同列 | ✅ 已落地 | consulting-analysis **V1.7.0** M5 第⑧问 |

## 二、"待老大"这条理由为什么撤

旧台账写「属全局技能治理链，agent 不擅改归属方资产」。本轮实测**该理由不成立** —— 治理链每一步都有机器门禁，
agent 自走后全绿，不存在"改了没人知道"：

```
改权威源（只动两个 SKILL.md，pathspec 限定）
  → check-skill-mirror.ps1 -Fix                    [GATE:mirror-pass] missing=0 mismatch=0
  → eval/verify_truth_consistency.py               33 PASS / 0 FAIL / 0 SKIP
  → A-skill-manager/assets/disk_registry_diff.py   0 漏注册 / 0 回滚 / 0 幽灵
  → handoff.py noise                               [GATE:noise-pass] 零散射
  → pre-commit [source-guard]                      PASS（基线 63336 / 硬顶 65536 / 余量 8252）
  → git commit（pathspec）+ ls-remote              HEAD == origin/main
```

未跑 `build_indexes --apply`：先 grep 确认派生件里**不存**这两个技能的版本号（`grep -rl "4[.]31[.]0"
skill/registry/ /d/global_memory/skill_content/` → 零命中），而 `D:/global_skills` 另有 12 个他人 WIP 文件处
`M` 态，整树重生会把别人的 hunk 卷进我的提交（治理文档明令：混文件时只提权威源并留痕）⇒ **索引未重生，在此留痕**。

## 三、两条新规则的原文要点（后续引用用，正文在技能内）

- **V4.32.0 Step 2.5 第 8 条**：交付类条目须同条写「成功面（可复算命令 + 产物指纹）」与
  「失败面（`rc≠0` 原文 + 归因 + 反证命令）」，缺任一侧判**不完整**＝未闭环。
  根因＝r30 成片首跑 `rc=1`：绝对 URL 相对页面 `localhost:8123` 属跨源，`/api/chat` 无
  `Access-Control-Allow-Origin`（curl 带 Origin 实测只有 200）⇒ S3 落进离线模板被自身断言拦住。
- **V4.33.0 Step 2.7 复发计数硬门槛**：同族坑累计第 3 次起，收口形态必须是**机器可判载体**
  （判据/守卫/assert/夹具三向），`已闭环` 证据须为「载体路径 + 会红的反例实测」。
  根因＝「没报错 ≠ 生效」一族**六次**复发（r20 假健康 / r22 阈值掺水 / r24 吞报错+手抄数字 /
  r25 静默空改 / r26 反例没跑却像通过 / r30 断言排在落盘之后），前五次收口文字全是"已登记教训"。
- **V1.7.0 M5⑧**：`CAP_RULES` 只读路径 ⇒ "能力写在内容里"的一侧被静默少算（self 少报
  `streaming`/`e2e_browser`）。并入 `caps`＝给一侧换尺（M5⑥ 同族）；正解＝计数不动 + **单列「盲区点名」**。

## 四、提交与核验

| 仓库 | 提交 | 远程 |
|---|---|---|
| `D:/global_skills` | `177f3e3`（V4.32.0+V1.7.0）→ `710ad37`（V4.33.0） | `ls-remote` == HEAD（四个短哈希均 `git cat-file -t` 验真） |
| `.agents/skills`（Codex 镜像） | `c46f7d8` → `f25deb0`（pathspec，未动他人 316 个 WIP） | 无 upstream，派生仓由树 owner 自管 |
| 陪聊项目 | 本卷 + 07 壳（≤4096B 复核后提交） | `ls-remote` 逐次核验 |
