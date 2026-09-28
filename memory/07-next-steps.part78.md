> 接续卷77（同一轮 r75 挂账的后半 + 推荐下一步）。切卷理由（数字实测）：整批 4570 B > 4,096 B 封顶，
> `volume_alloc` 首次取号即拦并回收空卷；正文两侧 3299 B / 1269 B，各加卷头行后分别入卷 77 与 78。

- [ ] 🟡 **R75-03 `--quality-gates` 的 CI 面**：workflow 上限取 12 ⇒ lobehub（33 个）永远两格记未验。
      改进方向＝改走 `actions/workflows` 列表 API（1 次拿全名册，含 `name` 字段），而非逐文件取正文。
- [ ] 🟡 **R75-04 `mvn verify` 的 CI 实跑回执未取**：本地只用等效路径（`test + jacoco:check@executionId`）验过，
      **故意不跑 `package`**——8123 上他人进程持有 jar，重打包会撞 Windows 文件锁（r72 的瘦 jar 事故同形）。
      取数动作＝本次推送后读 CI java-build job 日志里的 `jacoco:0.8.12:check` 行。
- [ ] ⏳ iCAN 报名 PII（截止 **2026-09-30**，剩 2 天）：唯一动作在老大侧。
- [ ] ⏳ 真机复跑、flake 对标原文、8123 旧 jar 进程刷新（先查占用者再 `python _test/build_jar.py`）。

## 推荐下一步（≤3，带稳定 id）

- `[推荐:R75-A]` agent 自动：R75-02 补四类用例（缺口 69% 集中在四张类，收益/成本比最高）。
- `[推荐:R75-B]` 用户操作：R75-01 发布裁决 —— 一次性清掉 `live_sync`/`ci_status`/R1 三条红。
- `[推荐:R75-C]` P2 可选：R75-03 改 workflow 名册取数（1 次 API 拿全量，消掉"未验"这一档的永久残留）。

- [ ] 🟠 **R75-05 产物被本轮 pom 改动判旧（真红，非噪声）**：`前提=python _test/server_preflight.py`
      ⇒ `PREFLIGHT-FAIL: jar=FAIL(产物比源码旧：jar mtime 12:49:06 < 最新源码 pom.xml 18:04:49｜bytes=28446595 libs=46) 夹具=5/5`。
      这正是 r70 那道产物新鲜度闸**第一次拦到我自己**——我为加覆盖率门改了 pom，却没重打 jar。
      修法＝`python _test/build_jar.py`（它会**先停占 8123 的进程**再构建再验货），但 8123 上那个 java 进程是
      08:36 起的、**非本会话所起** ⇒ 按并行会话纪律不代停、不代重启，登记给端口占用者让位后执行。
      **受理面不受影响**：CI 的 java-build job 从源码 `mvn verify` 自建自验（该 job 日志里的 `jacoco:check` 行即回执）。
      本地这条红在重打 jar 之前**每轮都会红** ⇒ 禁当环境噪声降级，也禁为把它洗绿去放宽新鲜度判据。
