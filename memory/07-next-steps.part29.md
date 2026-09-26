# 07 - 下一步 · 卷29（r39 续卷：本轮处置与新增待办，自卷28 按 4KB 同尺续拆）

## 二、本轮处置（对应台账编号）

- **#12** 05 三条 stale 差距按实测更正，原文删除线留痕并迁 `05…part12.md`（R241）。
- **#20** 81,005,106B 可再生中间件按回收区约定迁入 `_trash/`，移动前后拼接 sha256 相同、原位清空；
  成片 `心屿SoulIsle-演示视频.mp4`（22,954,501B）**未动**；重生成路径 `python _test/demo_video_pipeline.py`。
  体量：整仓 227,817,951B → **146,815,984B**。
- **#7** Docker 从"文件名存在"升级为"CI 每轮实测"：新增两步 ——
  `docker build -f server/Dockerfile` + **容器起服三项自证**（`status:UP` / `indexFound:true` /
  `vendorFound:true` + 首页 200）。只 build 不算数：COPY 路径、jar 存在性、前端命中都要跑出来才算。
- **#19/#12 之外的注入成本**：README 属每轮注入件，`## ✅ 验证` 一节（4,745B）整卷迁
  `docs/quality-gates.md`（逐字未改）并在 `docs/README.md` 建索引（不留孤文件）；
  README 19,531B → **15,454B**，回到 16,384B 预算内。07 壳经 `trim-shell` 3,845B → 2,633B。

## 三、一处我自己的误判（写下来是因为它差点变成一条假建议）

看到 `handoff.py help trim-shell` 报 `Unknown command`，我判定"体量判据的处置建议指向一条不存在的命令"，
并准备按"高优先缺陷"落进 skill。**这是错的**：完整 `--help` 命令表里 `trim-shell`、`volume` 都在册，
是我第一次只看了 `head -25` 的截断输出。用分发表的键核实后撤回该结论，没有写进任何文档。
真正的缺陷小一号且仍然真实：**`help <命令>` 对在册命令回 Unknown**，
这会让 r36 立的"先跑 help 现读"护栏给出**假阴性**（→ 台账 #21 待办，属主侧）。
同族教训：**用被截断的视图当分母**，与我 9 月登记过的形态同源。

## 四、新增待办（本轮盘点产生）

- [ ] **P2｜`handoff.py help <cmd>` 对在册命令回 Unknown**（本轮实测：`help trim-shell` / `help recycle`
      两条都在分发表里却报未知）⇒ 属主侧修 help 主题表，或让错误文案区分"命令不存在"与"无独立帮助条目"。
- [ ] **P2｜AGENTS.md 注入超量需人工裁口径**（#19）：工具主动拒绝覆盖，正解是人工决定哪些章节改指针，
      不是删内容也不是强推重生成。
- [ ] **P3｜`_trash/` 现堆 81MB**：账面已清盘上仍占，超期处置由 volume 判据自己盯（>7 天进判据），
      下一轮若 CI/磁盘需要，走工具的 purge 链而不是手删。

## 五、并行工具的写盘行尾缺陷（本轮实测，属主侧修，未代改）

`handoff.py trim-shell` 追加写盘时**产出 CRLF**：part27 由 `2,634B / CR=0`（我 20:2x 写的）
变成 `3,929B / CR=46`（它 20:31 追加 6 条迁移项之后）。本项目 `.gitattributes` 钉了 `eol=lf`，
⇒ 常驻判据 `eol_parity` 当场判红（`FAIL 工作树含 CRLF：memory/07-next-steps.part27.md`）。
本地已按字节还原（`replace(b"
", b"
")`，行数不变、6 条迁移项全部完好，判据复绿）。

复现命令（给属主）：
`python D:/global_skills/A-project-handoff/scripts/handoff.py trim-shell <项目根>`
后 `python -c "print(open(r'<目标卷>','rb').read().count(b''))"`。
根因同 r36 那条红线：**落仓库文本禁用 `write_text` 文本模式**（Windows 把 `
` 翻成 `
`），
`splitvol.py` 的 `cmd_trim_shell` 写盘点未走 `write_bytes`/`newline="
"`。
本轮不代改：A-project-handoff 今日被并行会话连着 bump（V3.64→V3.68），且其脚本正有他人在途。
