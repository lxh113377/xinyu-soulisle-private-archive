# 07 - 下一步 · 卷155（r127-S11 收口：R127-12 已落 + R127-13 新登记）

> 承卷：卷154（R127-11/12）｜提交=`9315ccf`｜报告 §8 追加行 S11｜台账=`交付物/对标数据/peer-memory-2026-10-12.json`

## S11 收口回执（条目本体在卷154 的 R127-12，本卷只出回执，不重复占号）

R127-12 已按「复用同一份词元表」修法落地，
      并在收口时抓出**修复自己引入的第二形态假阳**＋**两处计数尺伤**，三条都进同一提交：
      ① 品牌词元撞仓名 ⇒ `letta-ai/letta-code` 整树 16 条命中全是 `bin/letta.js`/`assets/letta-code-demo.gif`/
        `.github/workflows/letta.yml` 这类自有件；改判据 `mem_backend_hit()`＝品牌词元 ∧ 集成限定词同路径共现，
        探针检索轴整条委托它（禁第二把尺）。真面重采 `retrieval 3/16→5/16`、`vector_memory` 仍 9/16（同 9 仓）。
      ② NA 台账计数单位=记录条数（应为仓数）：一仓树取空时引用边必然也 NA ⇒ 一次超时记两条，
        `blind 5→7 / usable 12→10` 实际只少 1 个样本；合成件上 HEAD 版更报到 `usable=-1`。
      ③ 打印行里的「恒等式 usable+NA==total」写作 `n-x+x==n` ⇒ **永真式**，`usable=-1` 照样印 OK；
        已改成 usable 从 rows 侧独立数 + 幽灵仓/重名仓点名。
      证据：`MEMPEER-SELFTEST 19/19`、`benchmark_metrics --selftest` PASS、`LEDGER-SHAPE-PASS 59 族`、
      `LEDGER-AGE-PASS 18 族`、`EIGHT-DIMS-PASS 维 8/8`；变异腿 6 条各测得翻红（含 HEAD 双计形态复算 blind=3 usable=-1）。

- [ ] 🟡 **[推荐:R127-13｜agent 自动｜待干净窗口]** **非代码后缀件充当能力证据**（本轮重采时看见，未修）：
      `peer-memory-2026-10-12.json` 里 my-neuro 的检索轴样例含 `webui-service-rag.png`，letta-code 曾有
      `assets/letta-code-demo.gif`——图片/素材路径与代码路径同权参与"有没有这类能力"的判定。
      限定词共现把 `letta-code-demo.gif` 挡掉了（无集成词元），但 `webui-service-rag.png` 仍靠 `rag` 词元在案。
      影响面：`benchmark_metrics.CAP_RULES` 全部 8 条 + `peer_memory_probe.classify_tree` 四类，都是按整树路径字符串判。
      前提（可复算）=`python _test/benchmark_metrics.py --doc-perf --quality-gates --cap-channel` 后逐格数
      非代码后缀命中占比；改动落点=给 CAP_RULES 加后缀白名单（`.py/.ts/.tsx/.js/.mjs/.java/.go/.rs/.kt/.swift/.vue/.html`）
      并同 S9 那样把两侧（self/peers）一起过一遍——**先测占比再动尺**，占比为 0 就只登记不立项。

- ⚠️ **跳号留痕（不是丢件）**：R127 系列编号 **08 从未落笔**（01–07、09–13 在册，已用
      `grep -rn "R127-08" memory/ 交付物/` 全仓复算=0 命中）。取号跳空会让下轮误读成"08 被删了"，
      故在此显式记一句；根因=当时手写序号未复核。若再发生，改法＝取号走 volume_alloc 同款独占号，不手写序号。

- [ ] 🟡 **[推荐:R127-14｜agent 自动]** **登记号唯一性无尺面**：本轮两次重复都靠手工对账才发现——一次是「拆卷只入库一半」（HEAD 的胖卷150 与新卷154 同时含 R127-06/07/11/12），一次是「回执与条目本体同号」。复算=`grep -rln "next-steps.part" _test/*.py` **零命中**⇒ 没有任何尺扫 07 各卷的 `推荐:R<轮>-<号>` 是否唯一、是否零丢失。
      前提（可复算）＝新立 `_test/next_steps_ids_check.py`：全卷取 id 计数，同号>1 判红、与上一受理面做差集报丢失；变异腿＝把 12 号写两遍必须红、拆走一整卷必须报丢失。
