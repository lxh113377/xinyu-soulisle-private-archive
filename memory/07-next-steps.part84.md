# 07 分卷 · 卷84 — r77 挂账补记（同轮复跑）

## 挂账补记（同轮复跑）

- [ ] **R76-04（r77 复跑仍未通）**：`handoff.py savepoint` rc=1，唯一 violation 还是根目录 `wflow.toml`
      （`handoff.py noise "<项目根>"` 现读 `{"ok": 25, "quarantine": 7, "violation": 1}`）＝他方在途件，
      不代迁 `_trash`、不代加 `.gitignore` 藏成 quarantine。`前提=git status --short wflow.toml` 不再 `??`。
- [ ] **R77-03（CI 回执缺口）**：`浏览器回归` job 取回执时仍 `in_progress` ⇒ 不折算成绿；
      已实取：`Java 服务端构建` success 携 `Tests run: 82` + `All coverage checks have been met`（双路门在受理面生效）、
      `同步守卫` success、`线上↔权威源新鲜度` failure（软步骤，R1 既存）。
      复看 `gh api repos/lxh113377/xinyu-soulisle-private-archive/actions/runs/36475295265/jobs`。
