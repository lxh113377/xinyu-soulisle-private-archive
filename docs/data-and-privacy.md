# 数据与隐私（r44 起有常驻判据）

心屿存的是**情绪记录与原话对话**，按个保法口径属敏感个人信息。这一页只写实测得到的能力，不写形容词。

| 权利 | 现在怎么做 | 谁能核验 |
|---|---|---|
| 知情 | 第四幕披露语按运行模式实时翻转：开 `remote` 时明写「会同步到本演示实例的服务端」，关时明写「只留本机、不上传」——两态互斥，不存在"永远说不上传"的那一版 | `_test/data_rights_check.py` D1a/D1b（双向断言） |
| 删除 | 「清除我的数据」= 清本机 + 调 `DELETE /api/memory/{sid}`，**再读 `/api/memory/stats` 复核归零**，回执写明「服务端已删 N 条，复核为 0」 | 同判据 D2a/D2b/D2c（UI 回执与独立 HTTP 通道各测一次） |
| 可携 | 「导出我的数据」打包服务端情绪/对话 + 本机 localStorage 为一个 JSON，条数须与 `/stats` 对齐 | 同判据 D3 |

实测回执样本（✅ 2026-09-27 08:4x）：`本机已清除 ｜ 服务端已删 3 条，复核为 0`。

## 已知边界（不藏）

- **无账号体系**（决策 #4）⇒ 会话身份是浏览器内生成的 `sessionId`，换设备即换身份。
  跨设备"记得你"靠的是同一个 sessionId，不是用户鉴权；私有部署要先加账号层才谈得上多用户数据隔离。
- **公网版刻意不开 remote**：Pages / CloudBase 只有 `/api/chat`、没有 `/api/memory`，
  开了只会给评委看到 404，所以公网那一份数据本就只留在访问者本机。
- 服务端 H2 文件库（`server/data/`）**无自动留存策略与到期清理**，由部署方自行约定；
  schema 变更目前只有 `schema.sql` 全量脚本，**无版本化迁移工具**（peers 侧实测同样只有 1/16 有）。
- README 尚无「数据与隐私」指针行：README 受 16,384B 注入预算约束（现 16,364B，余 20B），
  加行须先精简他处 ⇒ 已登记 P1，见 `memory/07-next-steps.part38.md`。

复算：`python _test/data_rights_check.py`（8 条断言全绿）；`python _test/data_rights_check.py --selftest`（9 例）；
`python _test/peer_data_rights_probe.py --selftest`（10 例）。
