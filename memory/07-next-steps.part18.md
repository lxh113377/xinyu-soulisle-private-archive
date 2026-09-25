# 07-next-steps · part18（人工拆卷：第四刀做法与同族坑台账全文）

> 换卷理由：`07-next-steps.md` 是**索引壳**（`split --check` 判「主卷不拆」，须 ≤4096B，R161 零豁免）。
> r26 回写第四刀做法后实测 4,809B ⇒ 超限。工具只报警不代劳（同 r25 那次一模一样的形态），
> 故把两段长正文原文迁本卷，主壳留摘要 + 指针。迁入时间：2026-09-25（对标轮 r26）。上卷 `part17.md`。

## 第四刀（设置面板）做法全文

- [ ] `app.js` 切分**第四刀 = 设置面板** → `src/js/settings.js`。
      范围：`#btn-settings` 打开对话框、`#set-provider` 预设填入 base+model、`dlg` 的 `close` 事件合并写入
      （Key 留空=不改、proxy 由运行环境持有、输入框恒不回显旧 Key）。
      判据：`browser_check` 的「点右上角「模型设置」」链路 + `ux_guards` U1
      （Key 永不回显、空输入不洗掉已存 Key）。
      ⚠️ **这一刀的特殊风险**：它碰密钥输入框，迁移时必须实测 `deploy` 版仍是零密钥代理
      （`deploy_sync` 的红线复核会抓：`js/demo-config.js: 零密钥=True 与src不同=True`）。

## 每刀固定动作序列（缺一即不算完成）

1. 外提模块（保持 `window.X = (function(){...})()` 约定，DOM id 与 localStorage 键零改名）；
2. `index.html` 引入顺序核对（模块必须在 `app.js` 之前）；
3. `python _test/deploy_sync_check.py` 三类归零（MISSING / DIFF / EXTRA），同步命令**禁接 `2>/dev/null`**；
4. `size_budget_check.py` 登记新文件 **且收紧旧件预算**（只减文件不减约束 = 白切）；
5. `python _test/run_all_suites.py` 全量 29 套件 rc=0；
6. 公网重部署 `cd deploy && npx wrangler pages deploy xinyu --project-name=xinyu-soulisle --commit-dirty=true`
   （失败先分类：网络/环境 vs 代码；收口判据只有一个 = 线上取到新文件且与磁盘**等字节**）；
7. `live_sync` / `public_check` / `online_check` 复验；
8. 回写 05 / 06 / 07 / ROADMAP / CHANGELOG / 对标报告，pathspec 限定提交 + push + `git ls-remote` 核对。

## 同族坑台账（五次复发，全文）

| 轮次 | 形态 | 共同点 | 收口方式 |
|---|---|---|---|
| r20 | `mvn package` BUILD FAILURE（Windows 文件锁）把 fat jar 换成 48,920B 瘦 jar，旧进程仍回 `/api/health` 200 | 把"进程在答"当"产物对了" ⇒ 假健康 | CI FAT-JAR 体积 + `BOOT-INF` 双查（配 160B 瘦 jar 反例实测会红） |
| r22（r21 写入） | 契约覆盖判据 `done >= 8`，真实操作 11 条 | 阈值低于总量 ⇒ 永远绿 | 改成恒等式「已探测 + 显式豁免 == 总量」+ 零豁免判据 |
| r24 | `cp ... 2>/dev/null` 把 index.html 复制错目录；另 06 写「app.js 469 行」实测 471 | stderr 被吞 ⇒ 看不见；文档数字无守卫 | 同步命令禁接 `2>/dev/null` 写进动作序列；06 立规"正文禁手抄数字" |
| r25 | `str.replace` 锚点 `4_355` 与文件实际 `4355` 不匹配，未命中却打印"已登记" | 无返回值原地替换 ⇒ 静默无操作 | 当轮做出 `_test/patch_apply.py`（六类自证）并入电池 |
| **r26** | **给分档判据做负控制时 `import` 无守卫脚本 = 先跑完联网采集再 `exit 0`，反例一行都没执行** | **把"我以为我验证过了"当"验证过了"** | 补 3 处 `__main__` 守卫 + 常驻判据 **G9** + selftest 十一类含两条反向样本 |

⇒ 结论仍是一句：**记 lessons 不等于会遵守，机器化才算闭环**；且 r26 补一条——
**"验证动作"本身也必须被验证**（反例要留下可核对的 rc，否则它可能根本没跑）。
