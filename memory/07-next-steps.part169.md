# 07-next-steps 分卷 part169 — r167-KB11 心理学知识库第 11 轮（主干）

> 详细台账见 `交付物/心理学知识库/索引.md` 变更记录「第11轮」系列行；**续轮（收尾/收尾二）见 part170**。主壳 `07-next-steps.md` 全程未改：实测已 23,195 B（4KB 硬限 5.7 倍）且有并行会话在途 diff（非本轮），按并发纪律不碰，**该超限为存量待拆卷**。

## 完成

- 落卡 24 + 升级 5：164 → **188 条**（A44/B73/C31/D40，E=0）。六新域各 4 条新建篇 27–32（CB 认知扭曲｜JB 判断偏差｜PD 人格差异｜IN 成瘾行为｜PS 心理测量｜MI 正念）。UP 5 条 = EM-002/FE-014/NG-002/EW-002/AP-014，**无一条推翻原结论**。
- 形态：首次「主会话 + 7 名研读子代理并行」，主进程唯一写盘。README v1.9→**v2.0**，提交 `fbd3547`（15 件白名单）。
- 四处错引证伪后未入库：BFI-2 实为 Soto & John (2017)；「Ktzyk 2019 PLOS ONE」查无此文；「Koepp 2014」四路 0 命中；Kroenke 2001 任务书 DOI 404。另**一处任务书前提被官方原文推翻**（PHQ/GAD-7 实为 no permission required）。
- 门禁全绿：build PASS 188｜`--check` PASS｜integrity PASS（零悬空零孤岛、索引双向差集 0）｜`core_capability_baseline` PASS 双能力无回退｜部署副本 sha256 双侧一致。

## 未收（结转，详见 part170）

1. 🔴 **KB 新内容上线**：受「先清存量红再上线」约束（r131 口径：三面入库 → deploy_sync 归零 → 整跑电池 → live/public）。
2. 🔴 **`deploy_sync_check` 红 1 项**：`css/style.css` DIFF（src 40,041 / deploy 40,563 B），两侧同为 `94e623b`（10-12 r129）落盘 ⇒ **存量且已提交，非本轮**，归 r129 轮。
3. 🟠 **`size_budget` 3 项 OVER 均为他轮存量**（face-engine / face-smile-rules / chat-agent，后者属 r171 在途）。本轮 `psych-kb.js` 已重登记 157,186→**178,085**（实测 170,297）归零。
4. 🟠 **`_test/size_budget_check.py` 未纳入本轮提交**（含 r171 在途改动，按 R236 留工作树给该轮），本轮只改 psych-kb 一行。
5. 🟡 **待验证点存量**：188 卡绝大多数仍带未闭合项（本轮只清 5 条）。队列用 `python _test/psych_kb_integrity_check.py --backlog`。
6. 🟡 **07 主壳 23,195 B 超 4KB 硬限**（存量），待走 split/拆卷。

## 下一轮选题

- 用户 2026-10-13 菜单中**未被选中**的两域：**EL 情绪粒度与 affect labeling**、**PE 朋辈支持**。
- 已占用勿再取：CB / JB / PD / IN / PS / MI。