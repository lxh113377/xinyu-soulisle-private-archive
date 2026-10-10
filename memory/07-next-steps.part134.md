- **卷39** `07-next-steps.part134.md` — **r104 收口（判据层对标杆，与并行会话的 r104 产品轮同名不同线）**：四项改造＝①整跑韧性（eol_parity 600s 熔断→超时分档+批量化 140.4s→30.6s 且 16 红项不变）②peers 受理面（SNAP 重采到 10-10 16/16、community 行为面换 `/pulls` 使 5 仓 blind 归零、`--repo` 增量合并不缩分母）③耦合尺债务结转（C1 29→18：11 条改完成态、**j4:10000 从 debt-open 改判 unobservable**（r101 把阴性对照窗误登记）、face_check 7 条登记）④peer_memory 字段级 NA 计入声明位并摘豁免。提交 3 个 commit（`4c804b7`/`e93b056`/`f297673`），**未推**。TDZ 核验：并行会话已在工作树修好 `app.js` 的 `setSwitch` TDZ（`applyEnabled()` 移到 `initFaceHud` 解构之后，r104 注记），我实测 10 个判据因此转绿；**但修复未入库**（与他的顶栏块同文件）。

## r104-续：app.js TDZ 核验（老大点名的下一项，结论=已修待提交）

**缺陷**：`initFace()` 里 `applyEnabled()`（原 line 428）排在
`const { setPill, setSwitch, showStage, paintHud } = initFaceHud({...})`（原 line 454）**之前**
⇒ `ready() → setSwitch()` 抛 `ReferenceError: Cannot access 'setSwitch' before initialization`。
initFace 在顶层同步执行 ⇒ 一抛则 boot/开场/对话接线全不执行，**表现是整页打不开**。

**现状**：并行会话已在工作树修好（`applyEnabled()` 移到解构之后，line 488，并留 r104 注记），
src ⇄ deploy 两端等字节，`node --check` 过。**但修复在他的未提交 diff 里**（与他的顶栏滚动态块
同文件，+35/-5），`git show HEAD:src/js/app.js` 里 TDZ 仍在 ⇒ **他的下一个提交会把它带进去**。

**实测修复有效**（我起独立服务端逐判据复跑，TDZ 受害者全部转绿）：
voice 0/4+0/3 → **4/4+3/3**｜settings_panel → PASS｜offline_shell → PASS｜
memory_recall → PASS｜context_budget → PASS｜data_rights → PASS｜fault_injection → FAULT-PASS｜
j4_remote_down → J4-FUSE-PASS｜browser_check → ALL-ASSERT-PASS。

**仍未绿的两条 a11y 属 r87 面部 UI 自己的功能债**（不是 TDZ、不是本轮范围）：
A2 全状态×双主题 **20 个违规节点**（新增表情面板缺可访问名/角色）；A7 face-switch 可见文字
「已关闭」与无障碍名「摄像头开关（开启后用摄像头识别表情）」不构成子串。

**给并行会话的一句话**：TDZ 修复与顶栏块同文件，提交时无法拆分 pathspec ⇒ 要么一起提交
（提交信息注明"含并行会话在途的顶栏滚动态块"），要么等他自己的提交。**别让修复只在工作树里。**

## r105 入口（按优先级）
1. 🔴 **`dock_auto_check.py` 接线**（G16 孤儿判据：已入库但电池/CI 两头都不执行）——并行会话件，他提交后 G16 自绿；或由他登记挂账。
2. 🔴 **G12 三源对齐**（tag=v1.8.2 而 pom=1.8.1，发版链断中间）——属 R1 切版动作，待老大裁决。
3. 🟠 **face_check 7 条 debt-open 结转**（timing_coupling 现读 18/18，其中 7 条是 face 的）：摄像头开关/关闭/总闸/F8/F9/公网关闭腿，等的大多是 `live===0` 现成状态。
4. 🟠 **a11y A2/A7**：r87 面部 UI 的 20 个违规节点 + face-switch 无障碍名子串。
5. 🟡 **perf_ramp 分桶**（r101 否证按档定阈后登记的第一步：采带 `machine_tag` 的台账）。
6. 🟡 **共享端口 8123 无属主协议**：`build_jar.stop_holders()` 按端口杀进程不认属主，本轮被杀 3 次；已给 emotion_wiring/storage_resilience 加 `XINYU_BASE` 口。
