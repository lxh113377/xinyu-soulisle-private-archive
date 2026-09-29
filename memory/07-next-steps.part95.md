# 07-next-steps.part95.md

<!-- 本卷为 07-next-steps.part91.md 的延续 -->

## ⑨ 本轮没做成的两件（不折叠）

此前任何跑在树上的读数不可信」）+ 口径面把 `repo_config_check` 的 rc 原样并入（不另写一套「什么算好尺」）。
真面 `点名 15 件｜解析坏 0｜归属失明 0｜体检 rc=0`；演习注入 r81 那一形 ⇒
`rc=1 · 401:28 invalid syntax` + 「未入库改动把它写坏了」，随后按字节还原。

## ⑦ 建议 8（T8 具名缺口）的归因结论：**结构不可达，不虚报覆盖**

`LlmProxy.call`(漏 6 指令) / `openStream`(漏 8 指令) 逐行复算后全落在 `LlmProxy.java:95` 与 `:126`
的 `payload == null → bad-json`，唯一来源是 `:166-167` 的 `writeValueAsString` catch。
而 `toMessageList` 把任何入参形状都归一成 `Map<String,String>`（非对象跳过、`hasNonNull` 挡 null、其余 `asText()`）
⇒ 该 catch 不可能触发。沿用 r77「不为凑数写反射」：**BRANCH 仍 96.28%（LINE 97.75 / METHOD 96.43 与 r81 逐项相等）**，
用例数 82→**83**。替代交付 = 把这条原本只有散文的不变量钉成用例
（畸形四类入参走两条公开出口，断言字段皆字符串且状态码仍是上游的而非 500）。
要真提 BRANCH 只能动**真分支**：`MemoryController`（分支漏 3/30）、`ChatController`（分支漏 2/30）仍是活靶。

## ⑧ 我自己造的两处红（先记再修，别只记别人的）

1. `eol_parity` 被我判红：用 `Path.write_text()` 打补丁 3 处，Windows 下 `newline=None` 把 `\n`→`\r\n`
   ⇒ `_test/run_all_suites.py` 工作树 785 条 CRLF、HEAD blob 0 条 ⇒ 他人 clone 字节不可复算。
   按字节归一后 `EOL-PARITY-PASS（text=405 binary=20 total=425）`。与既有记忆「记 sha 的写入器必须锁 newline」同源。
2. **夹具与解析器按同一个假设写** ⇒ 自证体系内部一致、外部全错：我给 `git ls-tree -l -z` 写解析时按
   「sha\tpath\tsize」造夹具，结果 `--selftest` 全绿而真面 89/89 判废；`od -c` 实测字段序是
   `100644 blob <40hex>` + **空格填充** + `<size>` + **单个 TAB** + path + `\0`。
   修法是换一条**独立取数通道**对账（`--name-only -z` 再数一遍条目数），而不是给夹具补一条同假设的用例。
   另：`-l` 与 `--name-only` **互斥**（实测 git 报错），首版就是混用了 —— fail-closed 判 UNVERIFIED 是对的。

## ⑨ 本轮没做成的两件（不折叠）

- **发版（G6）没做，拦在凭据不在授权**：`CLOUDFLARE_API_TOKEN`/`CF_API_TOKEN`/`CLOUDFLARE_ACCOUNT_ID` 均未设、
  `~/.wrangler` 登录态不存在（仓里只有缓存的 `wrangler-account.json` 账号 id），且临时前缀装 wrangler 两次失败
  （npm `Exit handler never called`，日志显示 workerd 各平台包对 `registry.npmmirror.com` 先 ECONNREFUSED 重试再 200）。
  ⇒ 公网仍是 r79 之前的构建，`public_check`/`live_sync`/`ci_status` 三条红同源不解。
  **需要老大给的只有 Cloudflare API Token（或一次交互式 `wrangler login`）**；拿到后按
  `cd deploy` → `pages deploy xinyu --project-name=xinyu-soulisle --commit-dirty=true`（日志须见 `Uploading Functions bundle`）
  → 先记回滚锚 deployment id → 复算 `live_sync_check` + `public_check`。
- **推送要靠内联关代理**：`.gitconfig` 的 `http(s).proxy=http://127.0.0.1:7897` 在跑的时刻代理客户端没起，
  `git push` 报 `Failed to connect to github.com port 443 via 127.0.0.1`，而 curl 直连 github/api/pages.dev 全 200。
  处置**不改配置**（改共享配置属他人可见状态），只对该条命令内联：
  `git -c http.proxy= -c https.proxy= push origin main` ⇒ `9e3c94f..c38f97a`，`ls-remote` 与 HEAD 同值。
  下轮遇到同类失败先按「域名×时刻」测直连，再决定内联关代理；别把「代理在配置里」当成「代理在跑」。
