# 07-next-steps 卷68 — r68（JS 守卫的 ESM 静默空转面修掉 + r67 的 CI 回执取到）

> 取号 `volume_alloc.py`（O_EXCL）｜报告 `交付物/对标分析报告-2026-09-28-r68.md`

## 一、一条实测否证 + 一条修复

- **否证了自己的前提**：r67 我写「`node --check` 对 `.js` 按 CommonJS 解析，项目转 ESM 会误判合法文件」——
  **从未实测**。本轮直测 node v24.16：`export const z=1;` 的 `.js` rc=0；`import x from "y";` 的 `.js` rc=0；
  **`import…` + `function oops( {` 的 `.js` 仍 rc=0**，同字节改名 `.mjs` 才抓到错。
  ⇒ 真相反向且更坏：**含 ESM 语法的 `.js` 上 `node --check` 静默放行坏代码** ⇒ 上一轮刚装的语法闸
  对这类文件**零判定力**（记绿而什么都没检）。
- **修法**：`check_one()` 按顶层 `import|export` 判形态，ESM 形态把同一份字节落临时 `.mjs` 再检
  （`TemporaryDirectory` 内，不在仓根留残渣）；门面行加 `script=N module=M` 计数。
  反例两条：含 ESM 的 `.js` 必须通过**且**被归进 `module`；坏 ESM 必须 FAIL 并点名文件+kind。
  **变异对照**＝只摘"改检目标"这一步（kind 照样算）→ `SELFTEST-FAIL ESM 反向腿未咬 ok=1 fails=[]`、
  套件 6/7；真实源跑前跑后 sha 相等，副本清零。
- ⚠️ 如实标注：用例①的 `okE != 1` 断言在本机 Node 上**惰性**（坏文件也 rc=0），判定力在分类断言与
  用例②上——不冒充"两条都咬得住"。

## 二、r67 的"只认回执"闭口

run `36370771737`（sha `8b1d526`）→ 电池 **94/96 rc=0，判红仅 `live_sync`**；
`js_syntax`／`js_syntax_selftest` 在 Linux 受理面双绿 ⇒ 新判据已被受理面确认，`ci_status` 的红
完全由"公网未发布"解释，不是代码缺陷。

## 三、未闭合（不折叠）

`live_sync`／`ci_status` 待对外发布授权（发布超出本机可回滚范围，不自动执行）｜
电池墙钟未量化（先出耗时分布再谈并行，advisory 不成闸）｜flake 对标缺原文｜
peers 本轮未重采（同日两次实质漂移 0；跨日必须重采，沿用要标 run 时刻）。
