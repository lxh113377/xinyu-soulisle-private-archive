# 品牌分叉裁决记录：心屿 MindIsle ⇄ 心屿 SoulIsle

> ✅ **裁决结果（2026-10-01 老大拍板）：改用 MindIsle** —— r86 轮已全线执行：
> UI（`src/index.html` 品牌位 + manifest + css 注释）→ `deploy/xinyu` 同步副本 →
> 《应用方案》PDF 重渲染（20 页、9 图，`心屿MindIsle-应用方案.pdf`）→ 演示视频重录
> （`心屿MindIsle-演示视频.mp4`，221.4s）→ 公网双线重发（pages.dev + CloudBase /xinyu/）→
> 判据权威源随之切换（`deliverable_inventory_check` 以 `src/index.html` 为准）。
> 本目录两件因此从"待裁决的分叉"转为**裁决依据留档**（最早出现 MindIsle 品牌的原件）。
> SoulIsle 时代的提交版交付件在隔壁 `已提交留档-SoulIsle-20260930/`。
> 域名 `xinyu-soulisle.pages.dev` 为技术标识，未随品牌改（改域名=换部署项目，风险不对称）。

---

## 以下为 2026-09-30 移位时的原始裁决分析（留痕不改写）

## 事实（本轮现读）

| 面 | 品牌串 | 证据 |
|---|---|---|
| 权威源 `src/index.html` 品牌位 | **SoulIsle** | 交付面判据 `deliverable_inventory_check` 的品牌权威源就是它 |
| 《应用方案》PDF（20 页、已署五人实名） | **SoulIsle** 0 处 MindIsle | `交付物/提交包/心屿SoulIsle-应用方案.pdf` |
| 提交包 zip（09-30 定版，含 PDF+MP4） | **SoulIsle** | `交付物/心屿SoulIsle-作品提交-20260930.zip` |
| 演示视频成片 | **SoulIsle** | `demo_video_out/心屿SoulIsle-演示视频.mp4`，218.5s |
| 公网域名 | `xinyu-soulisle.pages.dev` | 已随 r85 重部署（deployment `a07fee7f`） |
| 报名表「作品名称」栏 | 心屿 SoulIsle（✅ 已定） | `报名信息-待填清单.md` |
| **本目录这两件** | **MindIsle 12 处、SoulIsle 0 处** | pypdf 抽文本层实测（PDF 20 页，无实名署名，是汇报用 deck） |

## 为什么移出提交包

`提交包/` 里同时躺着两份「参赛方案」，**文件名只差一个品牌词**（`心屿SoulIsle-应用方案.pdf`
vs `心屿MindIsle_参赛方案.pdf`），而今天是提交硬截止 ⇒ 交错的代价是「评委拿到的作品名与官网报名不一致」，
属不可逆的对外错误。移出后 `提交包/` 只剩一套品牌。

## 裁决选项（老大一句话即可）

- **A（推荐）维持 SoulIsle**：本目录两件保持"参考资料"，不改任何对外材料。官网/PDF/视频/域名已四面一致，零改动。
- **B 改用 MindIsle**：需同步改 6 处 —— `src/index.html` 品牌位、`deploy/xinyu/index.html` 同步副本、
  《应用方案》PDF 重渲染并重新过 `plan_pdf_coverage_check` + `pdf_leak_scan`、演示视频重录（片尾与标题）、
  报名表作品名、pages.dev 品牌露出。今天截止，**B 在剩余时间内不可能零风险完成** ⇒ 不建议。

## 判据侧的影响（如实记）

`_test/deliverable_inventory_check.py` 对**未登记且未跟踪**的交付物只计数不判红（防锁住在途件）；
一旦 `git add` 这两件，规则会立刻按「未登记但已入库的交付物品牌分叉」判红。本目录在 `git` 里仍是
**未跟踪**状态 ⇒ 不进提交面、不触发红，但 `git status` 看得见，不会重演"静默消失"。
