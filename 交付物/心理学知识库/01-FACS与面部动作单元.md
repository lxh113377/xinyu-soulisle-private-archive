# 01-FACS与面部动作单元

> 篇章内容：FACS、AU、表情度量体系（README §5）。条目卡行式规范见 README §3，编号规则见 README §4。

### 条目 PSY-FE-001｜FACS：面部动作编码系统与动作单元（AU）
- 可信度：A
- 定级理由：原始手册与多个独立权威来源（APA PsycNet、行为科学综述、iMotions/Noldus 白皮书）一致，教科书级共识
- 一句话：FACS 把表情拆成约 46 个肌肉级「动作单元（AU）」，是表情研究的中立度量衡；它编码动作而非情绪，「AU→情绪」映射是另一回事。
- 内容：FACS 由 Paul Ekman 与 Wallace Friesen 1978 年提出（方法论吸收瑞典解剖学家 Hjortsjö 1969 的解剖学工作），2002 年由 Ekman/Friesen/Hager 修订为《FACS: The Manual》，至今仍是行为科学表情测量的标准工具。AU = 把每块面部肌肉的可观察动作编成最小编号：AU1=眉头内侧上提（发愁）、AU4=皱眉、AU6=脸颊上提（眼角笑）、AU12=嘴角上拉；AU6+AU12 同现即「杜兴式微笑」（真笑：眼角+嘴角一起动）。计数口径：文献常引约 46 个 AU（另有口径把面部本体肌肉动作记 28 个主 AU、再加头部/眼球动作码），随版本与计数方式而异。成为度量衡的三个原因：①按解剖学客观分解，编码「动了哪块肌肉」而非「是什么情绪」，理论中立——Ekman 派与 Barrett 派都能用；②可逐帧标注，可量化可复制；③生态齐全——CK+/GEMEP/CASME II 等 AU 标注数据集与 OpenFace 等自动 AU 工具都建在它上面。产品含义：AU 可当输入特征，但它只承诺描述动作，不承诺「AU=情绪」。
- 来源：
  - [FACS 1978 提出、2002 修订、被引万余次、为表情测量标准] Ekman & Friesen (1978) Facial Action Coding System；Ekman, Friesen & Hager (2002) FACS: The Manual；APA PsycNet 条目 https://psycnet.apa.org/doiLanding?doi=10.1037%2Ft27734-000
  - [方法论吸收 Hjortsjö 1969 解剖学工作] FACS 白皮书与比较研究转述（2026-10-11 检索核实）
  - [AU≈46（比较研究口径）与 28 主 AU（iMotions/Noldus 口径）并存] 检索核实的多来源口径（2026-10-11）
- 关联：[[PSY-FE-004]]（补充：FACS 描述中立使争议双方共用同一度量衡）｜[[PSY-FE-002]]（支撑：微表情泄漏研究以 AU 标注区域）
- 待验证点：AU 计数建议以 2002 版官方手册原文终核（46 vs 28 主 AU vs 44 等口径并存）
- 入库：2026-10-11 · 第1轮

### 条目 PSY-FE-005｜Duchenne 真笑标记：感知层有效，「真心指标」有效度争议
- 可信度：D
- 定级理由：Girard 2021（强度伪影）与 Gunnery & Ruben 2016 元分析（感知层部分支持）均为同行评审一手研究且结论对立，按规范强制 D 两方并陈
- 一句话：心屿 smileKind/masking 判据（AU12+AU6/AU7 比值 0.20）的心理学原型与效度边界：真笑标记在「观察者感知真诚」层面有效，但作为「真心指标」存在强度伪影争议，产品措辞必须用「可能」。
- 内容：本项目表情侧判据的心理学原型：真笑（Duchenne 笑）= 口部 AU12（颧大肌，对应 blendshape mouthSmile）+ 眼周 AU6/AU7（眼轮匝肌眶部，对应 cheekSquint/eyeSquint）同时参与；社交性微笑只有口部。心屿据此立了三态判据 smileKind（face-engine.js:84-100）：口部微笑<0.35=未检出；眼周/口部比值≥0.20=真笑，否则社交性微笑；社交笑且紧张线索（抿唇/压眉）≥0.30⇒masking=强颜欢笑嫌疑（app.js:129 文案用「可能是强颜欢笑」）。效度两方：支持方——Gunnery & Ruben 2016 元分析（被引约 246）显示观察者确实用 Duchenne 标记判断真诚，视频比照片效应更强；Etcoff 等 2021 的 Botox 自然实验提供感知层因果级补强（AU12 强度匹配下化学移除眼周 Duchenne 标记后，微笑被观察者评为更少感到/更不自发/更不强烈/更不开心，四项均显著；见来源⑤，其「最强版假说未支持、标记可摆出」细节归质疑方）。质疑方——Krumhuber & Manstead 2009 证明眼周参与可以伪装；Girard & Cohn 2021 控制微笑强度/时长后正式检验八项竞争假说：多数被反驳或仅微弱支持，眼周收缩对自评积极情绪的独特信息几乎全部与微笑强度/时长共享、缺乏特异性且高度依赖情境（对观察者评分虽有独特效应，作者称其为「艺术真实」而非「光学真实」）；Gunnery/Hall/Ruben 2013 证明 Duchenne 笑可被刻意做出。产品启示：判据可用但结论必须降格——masking 只能触发探询与标注（「可能是强颜欢笑」「礼貌性微笑+紧绷迹象」这类或然措辞），不能下「你在装」「假笑」断言；ratioOn=0.20 仅由 4 张真笑照标定，扩样本必须复标（rules:196-199）。
- 来源：
  - [Duchenne 标记在感知层有效但作为「真心指标」被指为强度伪影] Girard, J.M., Cohn, J.F., Yin, L. & Morency, L.-P. (2021). Reconsidering the Duchenne Smile: Formalizing and Testing Hypotheses About Eye Constriction and Positive Emotion. Affective Science, 2(1):32–47, DOI 10.1007/s42761-020-00030-w；https://pmc.ncbi.nlm.nih.gov/articles/PMC8317937/（2026-10-11 PMC 页面实抓核实）
  - [观察者确实用 Duchenne 标记判真诚（视频>照片）] Gunnery, S.D. & Ruben, M.A. (2016) Perceptions of Duchenne and non-Duchenne smiles: A meta-analysis, Cognition and Emotion 30(3):501-515, DOI 10.1080/02699931.2015.1018817（2026-10-11 Crossref 实抓核实：作者 S. D. Gunnery、M. A. Ruben；被引约 246）
  - [Duchenne 笑可被刻意做出，AU6 非「不可伪造」] Gunnery, S.D., Hall, J.A. & Ruben, M.A. (2013). The Deliberate Duchenne Smile. Journal of Nonverbal Behavior（检索转述）
  - [Duchenne 标记可被故意伪装（含眼周参与）] Krumhuber, E.G. & Manstead, A.S.R. (2009) Can Duchenne smiles be feigned?（原 FE-017 来源②并入；未附 URL，该论断另有 Girard & Cohn 2021 与 Gunnery/Hall/Ruben 2013 两条带源支撑）
  - [AU12 匹配下化学移除眼周 Duchenne 标记（AU6 检出率 97%→19%）后，微笑被评为更少感到/更不自发/更不强烈/更不开心（−0.30/−0.25/−0.24/−0.11，均显著）；作者称不支持最强版假说、标记可在无积极情绪时摆出但仍被感知为真] Etcoff, N., Stock, S., Krumhuber, E. G., & Reed, L. I. (2021). A Novel Test of the Duchenne Marker: Smiles After Botulinum Toxin Treatment for Crow's Feet Wrinkles. Frontiers in Psychology, 11, 612654. DOI 10.3389/fpsyg.2020.612654. PMID 33510690（2026-10-11 PMC 全文实抓核实）；https://pmc.ncbi.nlm.nih.gov/articles/PMC7835207/
- 关联：[[PSY-FE-001]]（支撑：AU 与 blendshape 对应体系）｜[[PSY-MM-002]]（支撑：探询不断言原则的直接依据）｜[[PSY-MM-006]]（支撑：只标注不裁决的依据）
- 待验证点：ratioOn=0.20 样本仅 4 张真笑照，扩样本后必须复标（rules:196-199）；原「Etcoff 2021（面部瘫痪重建研究）提供部分生理支持」论断已移出（无可核对来源）——检索所见同作者 2021 年论文实为 Etcoff, Stock, Krumhuber 等〈A Novel Test of the Duchenne Marker: Smiles after Botulinum Toxin Treatment for Crow's Feet Wrinkles〉Frontiers in Psychology（Botox 自然实验、非面部瘫痪重建，检索摘要提示其结论方向与「生理支持」相反），下轮核对原文后再定是否并入；原 FE-017 卡所记「masking UI 文案须核降格」已由 r113 质量门部分落实，留核验
- 入库：2026-10-11 · 第1轮
- 更正：2026-10-11 来源①引文出处原值「IEEE Trans. Affective Computing」→「Affective Science 2(1):32–47, DOI 10.1007/s42761-020-00030-w」，副题原值「…Formalizing and Testing Competing Hypotheses」→「…Formalizing and Testing Hypotheses About Eye Constriction and Positive Emotion」，作者补全为 Girard/Cohn/Yin/Morency 并补 PMC URL（PMC8317937 页面实抓核实；论文本体真实存在，仅引文出处字段失实）
- 更正：2026-10-11 增补同题分工注记：本卡与 [[PSY-FE-017]] 同题近重复（均为 Duchenne 真笑标记效度争议、同引 Gunnery & Ruben 2016 与 Girard & Cohn 2021、级别同 D）——分工：本卡收心屿产品判据锚点（smileKind≥0.20/masking 阈值、4 照标定），FE-017 收 Krumhuber 2009 反方条目与效度两方概述；引用方按需取用（产品措辞/判据→本卡，效度两方→FE-017），合并列为下轮议题（独立审读修订）
- 更正：2026-10-11 内容与定级理由中「Etcoff 2021（面部瘫痪重建研究）提供部分生理支持」原值→移出、移入待验证点（该论断无可核对来源行，违反 README §2 定级纪律2；检索所见同作者 2021 年论文为 Botox 自然实验而非面部瘫痪重建，级别未动）
- 更正：2026-10-11 元分析作者原值「Gunnery, S.D. & Hall, J.A. (2016)」→「Gunnery, S.D. & Ruben, M.A. (2016), Cognition and Emotion 30(3):501-515, DOI 10.1080/02699931.2015.1018817」（Crossref 实抓核实；定级理由/内容/来源② 三处同步更正；FE-017 对同一文献引注的第二作者本就正确，两卡矛盾消除，级别未动）
- 更正：2026-10-11 合并：[[PSY-FE-017]]（原编号 PSY-FE-007）同题近重复整卡并入本卡——并入 Krumhuber & Manstead 2009 反方来源、Girard & Cohn 2021「八项竞争假说/艺术真实」细节与「礼貌性微笑+紧绷迹象」措辞规则，关联补 [[PSY-MM-006]]；全库 4 处 [[PSY-FE-017]] 引用（07 篇 ER-003 内容与关联、06 篇 MM-006 内容与关联）统一改指本卡，FE-017 卡体与索引行移除，总条目 55→54（主会话人工轮合并，第 2 轮独立审读议题落地）
- 更正：2026-10-11 待验证点中 Etcoff 2021 子项原值「检索摘要提示其结论方向与『生理支持』相反，下轮核对原文后再定是否并入」→已实读原文（PMC7835207 全文，2026-10-11）判定：【「提供部分生理支持」论断维持移出、不并入】——该文是对微笑照片的观察者评分实验（393 名 MTurk 评分者评 32 名患者肉毒毒素鱼尾纹治疗前后的摆拍最大微笑，FACS 证实 AU12 强度前后匹配、AU6 检出率 97%→19%），测的是观察者感知而非「标记是否生理上证明真实情绪」，且作者明说「Duchenne 标记可在无积极情绪时摆出，但仍被他人感知为真」、本研究「不支持 Duchenne 假说的最强版本」；但可作为【感知层支持】的一手实验证据并入本卡支持方（对 Gunnery & Ruben 2016 元分析的因果级补强：AU12 匹配下化学移除眼周标记后，微笑被评为更少感到 −0.30、更不自发 −0.25、更不强烈 −0.24、更不开心 −0.11，均显著），其「最强版未支持/标记可摆出」细节归质疑方；待验证点描述「Botox 自然实验、非面部瘫痪重建」经实读确认无误。
- 更正：2026-10-11 内容段支持方句原值止于「…视频比照片效应更强。」→增补「Etcoff 等 2021 的 Botox 自然实验提供感知层因果级补强（…四项均显著；见来源⑤，其『最强版假说未支持、标记可摆出』细节归质疑方）」（独立审读修订：上一更正行已判定 Etcoff 2021「并入本卡支持方」，但内容段「效度两方」支持方句未落该证据，更正行声称与正文实况脱节——本轮把来源⑤证据落到正文消费面，口径与更正行判定一致）

### 条目 PSY-FE-010｜端侧面部推理的可用信号：478 关键点与 52 维 blendshape
- 可信度：B
- 定级理由：能力数字由本仓一手 vendor 实测与独立技术社区页一致；官方文档页直读超时未核，故不升 A
- 一句话：浏览器端 MediaPipe FaceLandmarker 可稳定拿到 478 点人脸网格与 52 维 blendshape（近似 AU 强度），模型+运行时约 13.7MB 且可惰性加载，这是端侧情绪/微表情特征的全部原料。
- 内容：478 点=468 网格+10 虹膜；52 维 blendshape 为 0~1 系数（近似 FACS 的 AU），输入 256×256 裁剪脸。本仓一手实测：face_landmarker.task 3,758,596B + vision_wasm_internal.wasm 9,574,032B 等合计 13,674,721B，惰性加载（用户点开才下），GPU 优先 CPU 回落，WASM SIMD 探测门（不达标明示降级）。运行口径：8fps 轮询、EMA α=0.3、读数有效期 3000ms。
- 来源：
  - [478 点+52 blendshape+256×256 输入] webai.show 技术文档（MediaPipe 模型卡转述）；URL: https://webai.show
  - [vendor 字节、惰性加载、GPU/CPU 回落、SIMD 探测、8fps/EMA/3000ms] 本仓实测：src/vendor/mediapipe 目录字节；face-mediapipe-bridge.js:18-21,65-66,76-85；face-smile-rules.js:203-207
- 关联：[[PSY-FE-011]]（支撑：微表情需更高采样率）｜[[PSY-FE-013]]（补充：运行时与预算）
- 待验证点：官方 ai.google.dev 文档页未直接抓到（超时）；单帧推理延迟未实测
- 入库：2026-10-11 · 第1轮

### 条目 PSY-FE-015｜表情识别准确率：实验室基准与真实场景的落差
- 可信度：B
- 定级理由：多篇同行评审基准+顶刊综述（PSPI，被引1400+）一致，但基准数字随年份漂移、未达教科书级稳定值
- 一句话：表情识别存在三层落差：摆拍基准 SOTA 90%+、自然场景大数据 63-66%、而真实自发场景中面部构型与情绪的共现率仅约19%。
- 内容：硬数据：三层基准给天花板：摆拍精选 RAF-DB（约3万张）SOTA≈90–92%、老混合基准 FER2013 SOTA≈75.2%（人类仅65–68%）、自然场景 AffectNet 8类 SOTA≈63–66%（2024-2025 综述，2026-10-11 检索）。自发真实场景给地板：Barrett 等顶刊综述（PSPI 20(1):1-68，PMC6640856 原文实读）发现实验室自发场景中假设面部构型仅在 19%（.15-.25）的对应情绪事件出现（r=.32）；真实格斗赛后仅 8/55、25/119 名胜者露 Duchenne 真笑；摆拍与自发差异显著。产品含义：任何 FER 模块在真实摄像头上都没有可靠准确率，本仓 MediaPipe blendshape+规则法不例外——自证：r102 实测读数强度 p25 仅 0.47，ratioOn=0.20 仅 4 张真笑照标定（face-smile-rules.js:196-199 自注扩样本必须复标）。
- 来源：
  - [自发场景面部构型与情绪共现仅约19%，真笑 8/55 与 25/119] Barrett, Adolphs, Marsella, Martinez & Pollak (2019) Emotional Expressions Reconsidered, Psychological Science in the Public Interest 20(1):1-68；https://pmc.ncbi.nlm.nih.gov/articles/PMC6640856/
  - [FER2013 人类准确率 65-68%、SOTA 约75.2%] Khaireddin & Chen (2021) State of the Art Performance on FER2013, arXiv（被引400+）；https://arxiv.org
  - [RAF-DB SOTA 90-92%、AffectNet 8类 63-66%] 2024-2025 FER 综述基准检索（paperswithcode 系数字，2026-10-11）
- 关联：[[PSY-FE-004]]（支撑——普适性争议的量化面）｜[[PSY-MM-003]]（支撑）
- 待验证点：FER SOTA 数字随年份漂移（RAF-DB 各文 87.65%~96.51% 不等），引用必须注检索日期；该综述常被转引的『真实场景准确率约50%或更低』一句本轮未在原文核实到，未采用；改用已核实的 .19/.15-.25/8-55/25-119；本仓表情侧缺对外可复跑的准确率指标（文本侧 73 条/98.6% 不适用于表情）
- 入库：2026-10-11 · 第1轮
- 更正：2026-10-11 原编号PSY-FE-005→PSY-FE-015（入库时编号冲突：PSY-FE-005 已被同批先行入库条目《Duchenne 真笑标记：感知层有效，「真心指标」有效度争议》占用且两者主题不同，按 README §4 取未占用号改号入库，内容与来源未改动）

### 条目 PSY-FE-016｜遮挡（口罩）显著削弱情绪识别
- 可信度：B
- 定级理由：人因与机器两条独立证据链方向一致、量级明确，属已重复验证的实证
- 一句话：口罩遮挡使人脸情绪识别下降约20个百分点（人因研究 88%→68%；机器方法约70.76%），遮挡应显式提示而非继续输出分类。
- 内容：两类证据一致：人因研究（Face masks impair facial emotion recognition and induce specific emotion confusions, 2022）显示口罩使人脸情绪识别 88%→68%，约掉 20 个百分点，且损伤随情绪类别不同（依赖嘴部线索的情绪掉得更多）；机器方法（Elsayed et al. 2023, PMC10067009）在口罩下 3 类情绪识别 70.76%。含义：口罩不是噪声而是结构性信息缺失——嘴部 blendshape 全零时，依赖嘴部权重的 joy/sadness/contempt 判据全部失效，此时读数不是『低置信』而是『不可判』，应单独出『遮挡』提示而非继续给分类。
- 来源：
  - [口罩使人脸情绪识别约掉20个百分点（88%→68%）] Face masks impair facial emotion recognition and induce specific emotion confusions (2022)；2026-10-11 检索
  - [机器方法口罩下情绪识别 70.76%（3类）] Elsayed, Y. et al. (2023) PMC10067009；https://pmc.ncbi.nlm.nih.gov/articles/PMC10067009
- 关联：[[PSY-FE-015]]（补充——准确率落差的遮挡特例）
- 待验证点：本仓尚无遮挡检测（2026-10-11 代码实读），嘴部 blendshape 全零启发式为建议方案、未实现
- 入库：2026-10-11 · 第1轮
- 更正：2026-10-11 原编号PSY-FE-006→PSY-FE-016（入库时编号冲突：PSY-FE-006 已被同批先行入库条目《微表情作为测谎/意图识别证据：科学证据不足且学界分裂》占用且两者主题不同，按 README §4 取未占用号改号入库，内容与来源未改动）
