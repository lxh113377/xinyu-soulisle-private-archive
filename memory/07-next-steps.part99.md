# 07-next-steps.part99.md

<!-- 本卷为 07-next-steps.part92.md 的延续 -->

## ④ 本轮三次踩同一族（已进 `memory/AGENTS.md` 排障表）

⇒ 《提交清单》第 3 行「双线」里那条评委真可能打开的备用链接，从 09-24 起给评委看的是**另一个作品**。

处置（**加法，零覆盖**：不删他人任何一件）：`tcb hosting deploy deploy/xinyu /xinyu`（25 件），
验收走**独立通道**（不采信 CLI 自带校验，见 ④）：逐文件 `curl` 回读，**25/25 字节数与内容全等**；
`XINYU_URL=https://qwer-…tcloudbaseapp.com/xinyu/ python _test/public_check.py` 现场过
中间页放行 True、标题对、`CRISIS: True`、`KEY_LEAK: False`，但断言「对话未走在线」判红 ——
该 404 体是对象存储的 `NoSuchKey` ⇒ **静态托管域名不代理云函数**，`chat` 函数本身在役（`tcb fn list` 实测），
路由改动属控制台动作且该 env 三项目共享 ⇒ 本轮**未擅动**，清单行改为「该线现为界面如实标注的离线降级」。
