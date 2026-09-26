# 07 - 下一步 · 卷26（r37 · 2026-09-26：交付可得性 / 依赖队列 / 远端可见面）

## 一、r37 已完成（数字全部当场打印，未实测的不写）

1. ✅ **本仓首个 GitHub Release `v1.4.1`**（远端实测：`isDraft=false`、2 个资产）
   - `soulisle-server-1.4.1.jar` 28,438,588 B —— 内嵌 `version=1.4.1`、含 **0** 个前端文件
     （静态页按 `file:` 直读不入库）、**0** 处密钥形态、`mybatis-plus-core-3.5.17.jar` 在册（证明依赖已生效）。
   - `xinyu-web-1.4.1.zip` 249,409 B / 23 文件 —— 零密钥前端包，逐文件扫 `sk-` 形态 0 命中。
   - ⚠️ 发版前必须先停 8123 服务：jar 被运行中进程锁住 ⇒ `repackage` 改名失败，
     且**旧 jar 已被截成 48,907 B**（差点把半成品当 28MB 产物上传）。
2. ✅ **dependabot 队列清空 3/4**：#4 mybatis-plus 3.5.7→3.5.17、#1 checkout 4→7、#3 setup-python 5→7
   已合并，三次 push 的 CI 逐项 `success`（run `36236421340` / `36236407756` / 36236336824 链）。
   #3 与 #1 同改 `ci.yml` 冲突 ⇒ 用 `@dependabot rebase` 让工具自己 rebase 后再合，
   **不在他人分支上手解冲突**。
3. ✅ **新增常驻判据 `remote_tree_audit.py`**（两条套件，电池 43→**45**）：扫 **origin 默认分支文件树**
   而非本机 `git ls-files`；deny-list 7 条 + 放行 2 条（`.env.example`、零密钥 `demo-config.js`），
   `truncated=true`/空树 ⇒ rc=2 不判绿。实测远端 **230 个 blob 零命中**（当前无外泄）。
   自证被自己的**假反例**打回一次：样本 `public/x.png` 本不在禁用面 ⇒ 换成 `_test/_shots/lit_single.png`。
4. ✅ **新观测面探针 `peer_hygiene_probe.py`**（人工轮次工具，不入电池）：
   第一版只查根目录，把 self 判成"一键起=none"，而 `server/Dockerfile` 实际存在
   ⇒ 统一 `"" / server/ / docker/ / deploy/` 四组路径对**所有仓同尺**并打印命中路径（M5⑧）。

## 二、本轮新登记的待办

- [ ] **P1｜Spring Boot 3.2.5 → 4.1.1（PR #2，本轮判定不合并）**
      理由：主版本跳（配置项/actuator/依赖基线语义变更），而 v2 Java 后端**不是演示主路径**
      （公网走 Pages Function + CloudBase），截止前收益≈0、风险实。
      触发条件：复赛结束后，或与"fat jar 真部署到目标机"同批做（届时才有验证面）。
- [ ] **P2｜依赖队列 SLA**：dependabot 已配置且不等价于"有人在处理"——本轮 4 条 PR 挂了 2 天，
      是"能力位有了但没用起来"的实证。建议每轮 savepoint 顺带 `gh pr list --author app/dependabot` 一条命令。
- [ ] **P2｜Release 复现自动化**：jar/zip 目前手工构建上传，`gh release` 未进 CI；
      做成"打 tag 即出资产"需先解决：CI 内 `mvn package` 缓存耗时 + **资产面密钥门禁**
      （现有两条只覆盖仓库，不覆盖 Release 资产）。
- [ ] **P2｜一键起的实测面**：`server/Dockerfile` 至今**本机未构建过**（无 Docker），
      对标语义上"有 Dockerfile"只算文件名存在。补法=在 CI 里 build（ubuntu runner 有 docker），
      代价是配额与时长；**未实测前不得在交付材料里写"支持一键容器部署"**。
