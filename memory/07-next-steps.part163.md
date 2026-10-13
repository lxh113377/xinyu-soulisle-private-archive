# 07-next-steps.part163.md

<!-- 本卷为 07-next-steps.part160.md 的延续 -->

## 三、一手教训（本轮真踩，全文见报告 §8）

**提交**：`5595278`（build 身份 + 基准自愈）、`f49afa0`（契约报产物身份）、r131 收口一笔。
**JUnit 171 → 172 例**；契约 19/19；教程判据 4/4；性能 selftest 19/19；核心能力 PASS。

## 五、本轮新发现的两条（不在上表内，登记待办）

1. **部署同步当前红 1 项，归属并行会话**：`deploy_sync_check` → `DIFF css/voice-call.css`。
   实测取证：`src/css/voice-call.css` 是 **M（在途）**，工作树 sha `6e8b063a…`，而
   `deploy/xinyu/css/voice-call.css` 与 **HEAD 版相同**（`9a449d64…`）⇒
   是并行会话改了 src 尚未同步 deploy，**不是本轮改动**（本轮未碰任何 css）。
   ⇒ **演示/提交前必须先绿**（用户 2026-09-23 铁律），届时需对方补齐同步；不要代为同步
   （半成品传播到公网比不同步更糟）。
2. **成本闸只覆盖了一半暴露面（新 P1）**：r130 的 S2 按日闸在 **Java 服务端**；而公网 v1 线
   （`pages.dev` → `deploy/functions/api/chat.js`）是**无状态 Pages Function**，既没有令牌桶
   （`ApiGuardFilter` 在 Java 侧）也没有按日累计（要 KV/D1 才能做）。公网面当前只有
   「密钥不落前端」这一层。选项：① Cloudflare KV 计数（要建 namespace + 改 wrangler.toml，
   属对外发布动作，需老大点头）；② 接受平台层限制并写进 `data-and-privacy.md` 的边界声明；
   ③ 公网 /api/chat 加**无状态**的次数上限（按 CF 提供的 `cf-connecting-ip` + 单实例内存，
   重启即失效，只能挡瞬时打爆）。**本轮只登记不动手**。

## 三、一手教训（本轮真踩，全文见报告 §8）

1. **单测全绿 ≠ 能启动**：`MemoryPortService` 漏 `@Service`、`QuotaFilter` 双构造器漏 `@Autowired` ⇒
   `spring-boot:run` 直接失败，而 169 个用例一个没红（JUnit 是手工装配，容器走另一条链）。**新增控制器/服务必须真起一次。**
2. **`spring-boot:run` 的 cwd 不是项目根** ⇒ `./src/`、`./_test/emotion-eval-dataset.json` 全失效（lexicon 500 / eval 404）。
   正解：显式给 `XINYU_WEB_ROOT` / `XINYU_EVAL_DATASET` / `XINYU_LEXICON` 绝对路径。
3. **他人进程持有的 jar 会让 `package` 失败并留下瘦 jar**（93,975 B 冒充 20 MB，本仓第二次）。
   绕行 = `spring-boot:run` 跑 `target/classes` + **独立端口 8130** + **独立内存库**（H2 文件库不支持多进程写）。全程未动 8123。
4. **基准会被自家限流闸打回**：`--rounds 30` > `burst 20` ⇒ 10 次 429。429 须单独计 `rate_limited`，
   成功样本 <60% 判 **rc=2 未验**（不拿残缺样本下结论）；默认 rounds 已改为 15。
5. **变异锚点出现多处时单次替换＝空操作**（r128 同族，但这次正解是**全量替换**，因为语义是「任一处存活＝没删干净」）。
6. **判据自己崩会带走前面所有 PASS**：`api_contract_check` 的 C4 超时未捕获 ⇒ 抛栈，11 条 PASS 与"哪条挂了"一起消失。
   超时必须落成读数（同族于 r105 BLIND-RED）。
7. **C6b 零豁免不许「先豁免以后再验」**：想给 3 条新接口写 `x-live-skip` 会判红 —— 那正是它的作用。
   正解是给判据开 `--base` 换到含新代码的实例真验。
8. **共享文件的提交用 blob 精修**：`run_all_suites.py` 在途（含他人 +3 行）⇒ 以 HEAD 为底只加我的 7 行造 blob
   灌索引（`update-index --cacheinfo`），工作树不动，未吞他人改动。
