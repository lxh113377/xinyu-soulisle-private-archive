# 卷41 — r46 许可与供给链面（上）：换面取证 + peers 实数 + 判据盲区主缺陷（2026-09-27）

> 下卷 `part42`：防伪登记两条断言、我自犯四条、未闭环序。
## 1. peers 实数（16 仓 + self，双通道）

`python _test/peer_license_probe.py --json 交付物/对标数据/peer-license-2026-09-27.json`（NA/截断 0）

- 有 LICENSE 类件 **14/16**；GitHub 检测为 MIT 6/16；检测不出/自定义 5/16（`none` 2 + `custom/none` 3）。
- **带 vendored 第三方代码的只有 3/16**：leemo 16 件、sapphire 3 件、ryza 1 件。
- **三者中带归属件的只有 1/3**（leemo）。⇒ 这一维对手普遍缺位，真正的对手是我们自己的声明与实物是否一致。
- self：vendored 7 件（src/vendor 3 + deploy/xinyu/vendor 副本 3 + `_test/vendor/axe-core` 1）、归属件 1 份。

## 2. 本轮主缺陷：不是"没写文档"，是"判据的分母写死了目录"

- 实物：`_test/vendor/axe-core-4.10.2.min.js`（553,290B）banner 自证
  `Copyright (c) 2015 - 2024 Deque Systems, Inc.` + `Mozilla Public License, v. 2.0` ⇒ **非 MIT**。
- 缺陷：G6 取数面 `sorted(x.name for x in (ROOT/"src"/"vendor").glob("*.js"))` ⇒ `_test/vendor/` 对 G6
  **永久隐形**，归属表不登记它也全绿。
- **同族第二处**（必须记着）：r43 我在 `vendor_freshness_check.py` 上治过一模一样的毛病，
  当时在名册里留了注记"这件第三方资产在治理面外躺了一整轮"——**但只修了那一处**。
  ⇒ 修缺陷要枚举同类出口，本轮把 G6 的**活分母 + 自测夹具**两处一起改成从 `vendor-manifest.json` 现读。
- 连带假陈述：归属表正文"`src/`、`server/`、`_test/`、`deploy/functions/` 等全部由本团队原创"，
  r42 之后即为假。已更正为"四个文件除外，`_test/`（`_test/vendor/` 除外）原创"。
- 修前复算：`FAIL G6+G7 … vendored 文件未在授权清单登记 ['axe-core-4.10.2.min.js']`；
  修后：`PASS …｜分母=4(名册现读)`。

