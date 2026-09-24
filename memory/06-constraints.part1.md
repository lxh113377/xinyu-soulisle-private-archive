# 06-constraints.part1.md

<!-- 本卷为 06-constraints.md 的延续（R199.5） -->

## 已闭环条目归档（V3.48.0 活载卷自愈迁移）

- [x] [BUG] `handoff.py sync` 03 报「未检测到技术栈配置文件」——`pom.xml` 在 `server/` 子目录，旧判据只扫项目根 — 影响 03 自动块 | 状态：已修复（2026-09-22，A-project-handoff V3.44.0 增子目录清单兜底）

- [x] [BUG] `handoff.py sync` 04 把 `deploy/cloudbase/.../index.js` 当入口——`rglob` 命中交付副本 + 无 Java 启动类 — 影响 04 自动块 | 状态：已修复（V3.44.0 增 `*Application.java`/`index.html` + 副本降权）

- [x] [BUG] `handoff.py sync` 02 树混入 `.codebuddy/`/`.wrangler/`——`EXCLUDE_DIRS` 硬编码不读 `.gitignore` — 影响 02 自动块 | 状态：已修复（V3.44.0 sync 时并入 `.gitignore` 目录条目）

- [x] [BUG] `handoff.py review` 交叉一致性误报——「任意 ≥1 词交集即报」，陪聊 3 条误报的 07 项均内嵌 ✅ 子项且交集仅 `js` 巧合 — 影响 review 判分 | 状态：已修复（V3.44.0 复合未完成项跳过 + 过滤标签/扩展名 token；实测误报归零 9/9）
