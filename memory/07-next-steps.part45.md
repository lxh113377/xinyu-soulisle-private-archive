# 卷45 — r47 移动端与触屏面（上）：换面取证 + 首跑三条实测 + peers 结构数（2026-09-27）

> 下卷 `part46`：我自犯六条、与既有裁定的对账、登记与未闭环。
## 1. 首跑实测三条（修前 → 修后，同一把尺）

- **7 个触控目标高 27–35px**：`btn-lightshow 87x27`、`btn-dock 58x28`、`btn-settings 97x35`、
  `btn-theme 67x35`、`btn-clear/btn-export 108x35`、`btn-demo-clear x42`
  ⇒ `@media (pointer:coarse){button,.ghost-btn,.chip{min-height:44px;min-width:44px}}`
  ⇒ 修后四档视口 **tiny=0**（读数 8 组 = 4 视口 × 默认/展开两态，交互目标 110 个）。
- **输入框 14–15px**（chat-input 15 / set-provider 14 / set-base,key,model 15）⇒ iOS 聚焦自动放大整页
  ⇒ 现全部 ≥16px。
- **横向溢出四档全 False**（320/360/390/768 `scrollWidth==clientWidth`）⇒ 本来就是好的，如实记不借它抬分。

## 2. peers（16 仓，**只出结构与声明证据**）

✅ `python _test/peer_mobile_probe.py --json 交付物/对标数据/peer-mobile-2026-09-27.json`
有 HTML 入口 **12/16** ｜ 有 viewport 11 ｜ **主动禁缩放 3**（SillyTavern / succhia / ryza）｜
**按指针类型适配只有 2**（SillyTavern / opensoul）｜ 有 manifest 4。
恒等式按轴成立：应测 16 = 可用 10 + NA 2 + 范围外(非 Web) 4 ⇒ OK。
⚠️ **天花板写进快照头 `ceiling_note`**：对手真实触控几何静态取不到 ⇒ 禁止据此写"对手移动端体验更差"。

