# 体量治理逐项目建议 · 陪聊（2026-09-28）

> 由 QD 端 VOLEFF-R1-20260928-QD2 轮产出。只新增独立文件名，不改 `07-next-steps.md`。
> 复算：`python "D:/global_skills/A-project-handoff/scripts/handoff.py" volume "C:/Users/37533/Desktop/workspace/项目/陪聊"`

## 实测基线（2026-09-28 02:2x 本仓现场）

- 总量 **125,887,916B / 471 文件**；`.git` 等只计量项 84,423,880B（占 67%）
- 回收区 `_trash` = **81,005,106B**（占全仓 64%！）
- 发现 12 项，**可自动处置 0 项**；增长趋势 ok；语料 md 1,231,360B / 6,291,456B 健康

## 差距

1. **`_trash` 81MB 里大头是视频原始件**：`demo_video_raw.webm.20260926.r39`、
   `video_raw.20260926.r39/`（09-26 r39 轮搬进去的）。`.webm` 不在真删白名单
   （白名单只含 `.pyc/.pyo/.tsbuildinfo/.coverage/.db-journal`）⇒ 治理链**永远不会**动它，
   而它是本项目最大的单一可回收块。
2. **`.git` 84MB 无任何判据**（`VOL_COUNTED_EXEMPT_DIRS` 只计量），也就是说本项目
   "看起来 12 项超限"其实真正的大头在判据看不见的地方。
3. **可自动处置 0** ⇒ 该项目在自动治理上是**纯受益零动作**的：心跳跑不跑，它都不会变小。

## 建议（优先级 + 验收）

| 优先级 | 动作 | 命令/入口 | 估时 | 验收 |
|---|---|---|---|---|
| **P0** | 裁决 `_trash` 81MB 视频原始件：留成片、删 raw 或转存外部盘 | 先看清单 `du -ah 陪聊/_trash`；确认要永久删的路径先过 `python handoff.py purge-guard "<路径>"`（三态：受治面内 deny / OS 临时白名单 allow / 其余 need_confirm） | 25min | `du -sb 陪聊/_trash` 前后差；净减量写回本文件 |
| **P1** | 把"raw 视频不入库、成片才入库"写成本仓约定，避免同一形态每轮再攒 80MB | 在本仓 `memory/06-constraints.md` 记一条约定 + 需要时 `体量预算` 覆盖键（键名以 `volume --print-budget` 为准） | 10min | 下一轮 `volume` 的 `budget_sources` 出现 06 节行；`_trash` 不再出现新 raw 件 |
| **P2** | `.git` 84MB 归因（哪些提交带进了大文件） | `git -C 陪聊 count-objects -v`；大文件史用 `git -C 陪聊 rev-list --objects --all` 落文件后按 size 排 | 30min | 归因结论贴回本文件（未归因前不许动历史） |

**禁止**：为变绿放宽阈值；跳过 `purge-guard` 直接 `Remove-Item`；在未归因前跑历史重写。

## 与治理链的关系

心跳当前停摆（`Fenjue-VolumeGov-Daily` `0xC000013A`），但对本项目**没有影响** ——
它的可回收块全部落在链的否决表内，只有人工裁决能释放。这条事实本身就是本项目要记的账。
