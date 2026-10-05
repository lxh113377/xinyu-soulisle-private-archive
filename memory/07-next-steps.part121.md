# 07-next-steps 分卷 · r97 收口：备用线已上线 / Pages 面拦在凭据 ⇒ v1.8.1 held（2026-10-06）

## 冻结树整跑（提交 `e103db0` + 本地附注 tag `v1.8.1`）

- `python _test/run_all_suites.py --exclude-llm`（日志 `交付物/对标数据/bench-r97-battery1.log`）
  ⇒ **`BATTERY: 124/126 rc=1 RED(判红，必须修): live_sync,live_sync_alt`**；恒等式 实跑 126 + 豁免 3 == 129 ✓（`CENSUS-PASS 证据面 129/129`）；合计 **815s**。
- 本轮改的那条在电池里也跑到了：`voice rc=0 9.3s | VOICE-PASS` + `voice_selftest rc=0（5 个边界）`。
- 两条红**同因且非代码缺陷**：公网还在跑 v1.8.0 的 `js/voice.js` —— 判据自报 `['js/voice.js(live=4148B local=4798B)']`，
  curl 两面各自 `bytes=4148 code=200`。判据未放宽、未排除、未降级成 rc=2。

## 已做的一半：备用线（CloudBase）发布 + 复验

- `MSYS_NO_PATHCONV=1 tcb hosting deploy ../xinyu /xinyu -e qwer-d4gf2r76o8829463b` ⇒ `rc=0`。
  两处实测纠正了文档：README:186 写的是目标 `/`，而云端实际键是 `xinyu/…` ⇒ 按 `/xinyu` 发；
  不带 `MSYS_NO_PATHCONV=1` 时 Git Bash 把 `/xinyu` 改写成了 `C:/Program Files/Git/xinyu`（`tcb hosting list` 的 Key 列即此形态）。
- 复验：**`LIVE-SYNC-PASS`**，`引用 21 项 | 逐字节相等 21 | 缺失 0 | 漂移 0`；curl 该面 `voice.js bytes=4798`。
- 🔴 新状态必须记住：备用线现在**比远端 `origin/main`（`479ab43`）新** ⇒ 下轮看到 `live_sync_alt` 红先查这条，
  线上领先仓库不是漂移，别回滚线上。

## held 的一半：Pages 面拦在凭据（第三次同款），连带整条推送链

- 三条独立取证（只看有无）：`CLOUDFLARE_API_TOKEN`/`CF_API_TOKEN`/`CLOUDFLARE_ACCOUNT_ID` 全 unset；
  `~/.wrangler` 与 `%LOCALAPPDATA%/.wrangler` 不存在（仓内只有 `wrangler-account.json` 的账号 id，无 token）；
  **`gh secret list` 与 `gh variable list` 均空**。全局 wrangler 仍崩在 `miniflare → require workerd`（`npx --yes wrangler --version` 吐栈）。
- ⇒ 唯一本机通道 `npx wrangler pages deploy xinyu --project-name=xinyu-soulisle --commit-dirty=true` 跑不起来。
  与 `part95`⑨、`part98` 是同一道坎（第三次）。
- **决定：不推 `main`、不推 tag、不建 Release。** CI 电池步是 `run_all_suites.py --exclude-llm`，**不豁免 live 面**
  ⇒ 推上去必带 `live_sync` 判红，还会级联成下轮 `ci_status` 的红（自造挂账）。按本仓「护栏拦住就别绕：如实报未发 + 拦在哪 + 失败面」处置；
  不放宽判据、不把 rc=1 洗成 rc=2、不摘 live 套件。本地其余均已就位：`RELEASE-GOV-PASS commits=0`、
  `REPO-CONFIG-PASS 17 项 0 失败`、`pre-push` 契约 14 条 blocking 全绿（`--dry-run` 实测放行，SSH-over-443 备用路线可认证）。
- **解封只差一件事**：老大给一个 Cloudflare API Token（Pages + 该 project 写权限），或允许一次交互式 `wrangler login`。
  之后按序：publish → `live_sync` 单跑 → 整跑 → 先推 `v1.8.1` 再推 `main`（tag 先于分支，见 `part112`）→ `ci_watch` → 建 Release。

## 下轮入口（新增，不折叠）

- ⬜ 残余「本侧动作界 ≠ 有界时间界」：`start()` 后既不派 `end` 也不派 `error` 时需用户点一下才复原（详 `part120`）。
- ⬜ `A4=SKIP|PASS` 在受理面仍无读数（r96 §2.9 更正注，两轮未做）。
- ⬜ 🔴 共享工具缺陷：`flow . --sync` 写回 `part5` 时不查 4KB 单卷硬限（本轮顶到 4,609B ⇒ `savepoint` 判 `single_block`）。写入端未修；全文、复算命令与本轮自犯同款见 `07-next-steps.part123.md`。
- ⬜ 口径不一致登记：`.ci/contract.json` 把 `live-sync` 列为 deferred，而 CI 电池不豁免它 —— 「本地 deferred、CI 阻断」并存。
  本轮**只登记不动手**（动它=改护栏）；要么 CI 显式跳过，要么契约升它进 blocking，二选一由下轮定。
