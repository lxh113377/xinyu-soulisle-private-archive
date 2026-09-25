# 07-next-steps.part15.md

<!-- 本卷为 07-next-steps.part14.md 的延续 -->

- [x] **对标轮 r21（2026-09-25 同日第二轮）已落地**：① 接口契约唯一声明源 `docs/openapi.yaml`（11 条）+ 三方对账守卫
      `_test/api_contract_check.py`（C1 不缺文档 / C2 不虚文档 / C3 前端偷调即红 / C4 运行态状态码与必需键 / C5 自证）
      ② `.github/dependabot.yml`（maven@/server + github-actions@/）③ 测量装置自纠（漂移纳入 caps/docs；
      self 套件数改取 `run_all_suites.py` 条目数为唯一分母）④ 参照池 14→16。电池 **26 套件**。
      **同时勾销一处 r20 错误归因**："零构建挂不上 dependabot"→ 实测 Maven 与 Actions 两个 ecosystem 可直接挂，
      更正注在 `06-constraints.md`（原条目保留，不删改历史）。
