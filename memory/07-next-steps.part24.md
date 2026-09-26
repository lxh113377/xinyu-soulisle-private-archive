# 07 - 下一步 · 卷24（r36 · 2026-09-26：行尾确定性 + 电池入口加固 + 公网字节同源）

> 由索引壳迁入的 r35 完成项全文，加本轮 r36 实测记录。索引壳只留指针。

## 一、自壳内迁来的 r35 完成项（逐字保留，防"拆卷即丢内容"）

- ✅ **r35 05 追平完成**（原 r34 登记的自驱项）：`memory/05-feature-status.md` 新增「当前构建状态（r20–r35）」
      权威段（三态徽章 / 本机开场白标签 / 离线壳 / 演示视频代际），r20–r28 各轮残段逐字迁 `05…part10.md`。
      复算：`grep -c "在线 AI\|本机开场白\|演示视频" memory/05-feature-status.md` = 4，体积由 savepoint 量。
- ✅ **r35 受理面闭环**（原「只有老大能解：ENV_BLOCKED」的更正与了结）：账单/配额确已恢复，
      真因是三条代码级缺陷（见 CHANGELOG「Fixed（r35）」）。修复后 run `36220200506`（sha `7aac7d2`）
      **四条 job 逐项 success**，`python _test/ci_status_check.py` ⇒ `CI-STATUS-PASS` rc=0。
      留痕的教训：这条红**换过原因却没换打印形态** ⇒ 电池收口行现拆 `RED(判红)` / `ENV-UNVERIFIED` /
      `CRASH` 三类（第三类是本轮被自己的 0xC0000409 崩溃逼出来的）。
      本机侧同日复验：`--slice 0 21` ⇒ 21/21、`--slice 21 41` ⇒ 20/20 ⇒ **41 条全绿**。
      ⚠️ 本条的 41 是 r35 当时的套件数；r36 起为 **43**（见下文复跑）。

## 二、r36 已完成（逐条带实测值，未实测的不写）

1. ✅ **工作树字节与机器无关（commit `13a7299`）**：`.gitattributes` 由"只声明部分类型"改为
   `* text=auto eol=lf` + 显式 `binary` 名单（png/jpg/jpeg/gif/webp/ico/woff/woff2/ttf/mp3/mp4/webm/pdf/jar/db/zip）
   + `*.sh`/`*.ps1` 强制 LF；108 个文本文件 `git add --renormalize` 归一，**内容零改动**由
   `git diff --name-only` == `--ignore-cr-at-eol --name-only`（只差 2 个本轮有意改的文件）证明。
   - 代价当场兑现一次：首轮归一把 20 个二进制里 0D0A 字节剥掉（PNG/MP4 少 1–2 字节），
     且"两侧都归一再比"的守卫看不见这种损失 ⇒ 全部从 `git show HEAD:` 还原（复核余 0 条不等），
     并把该形状固化成判据规则 **E3**（含 `0D0A` 但未声明 binary ⇒ 判红）+ 夹具用例。
2. ✅ **常驻判据 `_test/eol_parity_check.py`**（E1 属性表 / E2 工作树与仓库侧行尾 / E3 binary 形状 /
   E4 分母闭合 `text+binary==total`）+ 8 类样本 `--selftest`。当前实测：
   `EOL-PARITY-PASS（text=205 binary=20 total=225；工作树字节 == blob 字节）`。
   跨检出证明：两份 clone 分别按 `core.autocrlf=true` / `input` 检出，文本侧字节一致。
