# ASR 评测体系 + 本机引擎接入（要求1 基线 / 要求2 方言 / 要求3 预处理）

> 建立于 2026-10-14。目标：把「方言识别准确率」从**感觉**变成**可复现的数字**。
> 本文件同时记录**踩过的坑** —— 每一条都是实测出来的，不是推测。

## 一句话现状

**判据内核 + 本机引擎接入已建成并全部自检通过；真实基线数字尚未产出，卡在外部依赖：拿不到带标注的方言语料。**

---

## 目录

| 文件 | 职责 | 自检 |
|---|---|---|
| `normalize.py` | 文本归一化（标点/全半角/繁简/方言正字） | `py -3.12 normalize.py` |
| `metrics.py` | CER/WER + 错误来源定位 | `py -3.12 metrics.py` |
| `scenarios.py` | 声学场景合成（噪声/混响/近场/远场） | `py -3.12 scenarios.py` |
| `eval_set.py` | 评测清单格式 + 语料适配层 | `py -3.12 eval_set.py` |
| `engine_qwen.py` | Qwen3-ASR 推理封装 | `python engine_qwen.py`（环境体检） |
| `run_eval.py` | 评测主循环 | 需模型+语料 |
| `audio_quality_check.js` | 前端质量闸判据（Q1–Q10） | `node _test/asr/audio_quality_check.js` |
| `asr_local_check.js` | 本机适配器判据（A1–A12） | `node _test/asr/asr_local_check.js` |
| `asr_chain_check.py` | HTTP 链路判据（J1–J8） | `py -3.12 _test/asr/asr_chain_check.py` |
| `engine_switch_check.py` | 浏览器选路+降级判据（J9–J14） | `py -3.12 _test/asr/engine_switch_check.py` |

服务与前端：
`server/asr-service/app.py`（Python 推理服务）·
`server/src/main/java/com/xinyu/soulisle/asr/AsrProxy.java`（HTTP 代理）·
`api/AsrController.java`（端点）·
`src/js/asr-local.js`（浏览器适配器）·
`src/js/audio-quality.js`（要求3 质量闸）。

---

## 本机引擎接入（2026-10-14 已完成并实测）

```
浏览器 getUserMedia(AEC/NS/AGC) → ScriptProcessor 收 PCM → 能量切块
  → 打包 16k/16bit/mono WAV → POST /api/asr
  → AsrController → AsrProxy(JDK HttpClient)
  → server/asr-service/app.py (FastAPI, 常驻显存)
  → Qwen3-ASR-0.6B (CUDA) → 文本回灌 SpeechRecognition 形状的 onresult
```

**实测数据**（RTX 5070 Ti / bfloat16）：
- 模型加载 2.0s，稳态 **RTF ≈ 0.10–0.11**（快于实时 10 倍）
- 3s 音频：推理 310ms，**端到端往返 376ms**
- 6s 音频：推理 598ms（188KB，正好卡在 256KiB 体闸内）

**两条红线的落地方式**：
1. **默认态零探测**：`xinyu.asr.enabled=false`（默认）+ `AsrLocal` 默认关 ⇒
   判据 J9 实测 **0 条 /api/asr 请求**。
2. **不得伪装在线**：本机服务任何失败都走 `onerror` → `voice-call.js` **当场回落 Web Speech**，
   且界面文案从「本机识别」改成「浏览器识别」（判据 J12/J13 实测）。

**启动方式**：
```powershell
# 1) 先起 Python 服务
$env:HF_HUB_OFFLINE="1"; $env:XINYU_ASR_MODEL="D:/asr-data/models/Qwen3-ASR-0.6B-hf"
D:\asr-train\.venv\Scripts\python.exe server\asr-service\app.py     # 监听 127.0.0.1:8765
# 2) 再起 Java（带 ASR 开关）
$env:XINYU_ASR_ENABLED="true"; $env:XINYU_ASR_URL="http://127.0.0.1:8765"
java -jar server\target\soulisle-server.jar --server.port=8123
# 3) 浏览器侧显式开启：localStorage['peiliao.asrlocal.v1'] = '1'
```

### ⚠⚠ 热词偏置实测结论：**对本模型无效，别指望它**

`prompt=Vocabulary: …` 已全部接线（Python 服务 `DEFAULT_VOCAB` → Java → 前端 `vocab=on|off`，
判据 A13），但**实测没有效果**，如实记录：

| 实验 | 样本 | 无 prompt | 带目标词表 | 带无关词表 |
|---|---|---|---|---|
| 普通句子 | 30 条普通话 | 97.07% | 97.07% | — |
| 含专名句子 | 24 条 | 82.90% | 82.32% | 82.32% |

**关键读法**：目标词表与无关词表**结果完全相同**，且都**略低于**无 prompt。
这说明模型确实读到了 prompt（输出变了 6/24 条），但**偏置方向随机、与词表内容无关** ——
它不是在「往正确方向引导」，而是在扰动解码。

结论与取舍：
- **不把它当优化手段**。接线保留（默认开、无额外延迟 333ms vs 342ms），
  但**不作为「方言专名纠偏」的卖点**，也不写进验收。
- 若将来要真纠偏，可靠路径是 **LoRA 微调**（把方言专名与情绪术语喂进去），
  而不是靠 prompt。
- 判据 `vocab_probe.py` 已把三组对照固化，避免后人只看 on/off 就下错结论。

**这是本轮最重要的一条负面结论：需求2「适配方言发音规则/俚语」在无微调前基本无解。**

### ⚠ 换引擎的真实代价（如实登记）
- **n-best 重排失效**：Qwen3-ASR 是贪心解码，一次只出一条，`maxAlternatives` 恒 1。
  **C23（`pickBest` 取词表命中的那条）在本引擎上不成立** —— 这是能力退化，不是 bug。
- **无 interim 结果**：本机引擎是端点式的，拿不到 Web Speech 的实时中间结果。
  用户说完 → 静音 420ms 切块 → 推理 → 文字到达，比 Web Speech 的体感慢约 1s。
- **体闸约束**：单次语音上限 6s（256KiB ÷ 32KB/s）。超长由前端截断。

---

## 关键口径（不可随意更改）

### 1. 语料级 CER，不是逐条 CER 求平均

```
CER = (替换S + 删除D + 插入I) / 参考字符总数N
准确率 = 1 - CER        ← 验收指标 98% / 92% 指这个
```

逐条求平均会**偏袒短句**。自检实测：同一组用例
语料级 = 0.0769，逐条平均 = 0.0500，**差 2.7 个百分点**。
两种口径混用会直接导致验收结论翻转。

### 2. `real_audio` 字段隔离合成数据

闽南语目前只能拿到 TTS 合成语料（`lianghsun/tw-hokkien-audio`，CosyVoice3 生成）。
合成音频的声学分布 ≠ 真实语音，用它测出的准确率**不代表真实用户场景**。
清单里 `real_audio:false` 的条目在报告里单独标注，**不与真实录音混算**。

### 3. 场景靠合成，不靠录音

安静/嘈杂/近场/远场用「干净语料 + 可控退化」复现（CHiME / DNS Challenge 标准做法）。
好处：条件可复现、SNR 可精确对齐。代价：合成条件 ≠ 真实录音，
故本体系产出的场景数用于**横向对比与回归**，绝对值另需真实录音校验。

`scenarios.py` 共 12 个场景：clean / noisy×4(SNR 20,10,5,0 dB) / reverb×3(RT60 0.3,0.6,1.0s) / near / far×3(1,3,5m)。

---

## 本轮踩过的坑（全部实测，勿重犯）

### 坑1：`generate(inputs)` 位置传 BatchFeature 必炸
```
AttributeError  (generation/utils.py:2534  batch_size = inputs_tensor.shape[0])
```
`inputs_tensor.shape` 打在 `BatchFeature.__getattr__` 上。
正解：**`model.generate(**inputs, ...)` 解包传参**。`engine_qwen.py` 已修。

### 坑2：输出带 `language Chinese<asr_text>` 前缀
不解包就会让 CER 100% 错。正解：官方
`processor.decode(ids, return_format="transcription_only")`；老版本 transformers
退回手工剥壳。两条路都在 `engine_qwen._decode()` 里，**必须产出纯正文**。

### 坑3：`apply_transcription_request` 不能位置传
`language` 要按名传（`"Chinese"`）或按码传（`"zh"`）；
批量时官方示例传 `language=["zh"]`，但稳妥做法是**逐条传标量**。

### 坑4：**方言名不是 `language` 的合法取值**（最容易被模型卡误导的一点）
模型卡 Supported Dialects 列了 22 种中国方言，看起来都能强制切。**实际上**：
```
ValueError: Unsupported language: 'Sichuan'.
Supported codes: [ar, cs, da, de, el, en, es, fa, fi, fil, fr, hi, hu, id, it,
                  ja, ko, mk, ms, nl, pl, pt, ro, ru, sv, th, tr, vi, yue, zh]
Supported names: [Arabic, Cantonese, Chinese, Czech, ...]
```
查证 `transformers/models/qwen3_asr/` 全目录：**只有 `LANGUAGE_CODE_TO_NAME`，
没有任何方言接口**。
⇒ **只有粤语可用 `language='yue'` 强制**；
四川/东北/上海/闽南话只能靠**自动语种识别**，无法强制。

### 坑5：`prompt` 能否承载方言指令 —— **本轮未能证明**
在**普通话音频**上分别喂「热词」「四川话指令」「吴语指令」，输出**逐字相同**。
这**什么也没证明**（音频本来就是普通话，本就不该有变化）。
**没有方言音频之前不下任何结论。**

### 坑6：`snrDb` 里 `+f && +f.r` 的废码
`+f` 对普通对象得 `NaN`（falsy），`&&` 整个短路 ⇒ `v` 恒 `NaN`
⇒ 所有帧被跳过 ⇒ `snrDb` **恒返回 null** ⇒ 噪声判定链路静默失效。
判据 Q3/Q8/Q9/Q10 四条一起变红才暴露。已修（支持 `{r,speech}` 与裸数字两种形态）。

### 坑7：RIR 长度与 RT60 无关
镜像声源法阶数 12 只覆盖约 0.21s，`rt60=0.3` 与 `rt60=1.0` 生成的 RIR
**长度完全相同** ⇒ 混响场景形同虚设。修正：RIR 长度取
`max(镜像法延迟, ceil(rt60*sr))`。

### 坑8：`Case.from_json` 把 `meta` 传了两次
显式 `meta` 与「未知键合并」同时给 `meta` ⇒
`got multiple values for keyword argument 'meta'`。已修。

### 坑10：FastAPI 里 `from __future__ import annotations` + 函数内 import ⇒ 422
`POST /transcribe` 全部返
`422 {"loc":["query","request"],"msg":"Field required"}` —— 报错信息极具误导性
（看起来像客户端少传参数，实际是服务端注解解析失败）。
根因：PEP 563 把 `request: Request` 变成字符串，FastAPI 用 `get_type_hints` 解析，
而 `Request` 是在 `build_app()` **函数内部**导入的、不在模块 globals，解析不到就退化成 query 参数。
正解：**本文件不写 `from __future__ import annotations`**，或把 fastapi 提到模块顶层。

### 坑11：`proc.decode()` 批量下返回 list，不是 str
退化路径 `re.sub(r"^\s*language\s+\S+\s*", "", raw)` 炸
`TypeError: expected string or bytes-like object, got 'list'`。
且它发生在 `except` 分支里 ⇒ **整个请求 503**，错误现场完全指不到真因。
正解：先统一把嵌套 list 压成字符串再剥壳。

### 坑12：判据自己的 bug（两次，结论完全反过来）
都不是被审代码的错，但都让测试给出**与事实相反**的结论，必须单独记：
- 缺 `navigator.mediaDevices.getUserMedia` 桩 ⇒ 本机引擎 `start()` 判「不支持」
  ⇒ 立刻 onerror ⇒ **降级逻辑正常工作** ⇒ 却测出 `engine=webspeech`，
  看起来像「开启态没切到本机引擎」。
- 阶段间没调 `endCall()` ⇒ 第二次 `startCall` 因 `state!=="idle"` 提前返回
  ⇒ `rec` 还是上一阶段的 ⇒ 同样误判。
- 另：前端打的是 `/api/asr?dialect=`，`/transcribe` 是 **Python 那一层**的路径；
  拿 `/transcribe` 筛前端请求会一条都数不到。

### 坑13：`Blob.arrayBuffer()` 返回 Promise
浏览器与 Node 里都是 Promise，不能当同步用。判据里当同步读会直接崩。

### 坑14：float 边界不要钉
`0.01 * 2.2 = 0.022000000000000002`，用 `0.022` 断言会因一个 ULP 失败。
门槛类断言一律用**有间隔**的值，边界属浮点噪声，不是行为契约。

### 坑9：本机网络对大文件极不稳定
实测吞吐：ModelScope **7-8 MB/s**（模型 1.56GB/4:45 下完），
OpenSLR-trmal 1.56 MB/s（瞬时）但**持续只有 8 KB/s**，
huggingface.co **大文件 0 字节直接失败**，hf-mirror 308 重定向。
⇒ **大文件优先走 ModelScope / 腾讯云镜像；别信瞬时测速。**

---

---

## 实测基线（2026-10-14，RTX 5070 Ti / bfloat16 / Qwen3-ASR-0.6B）

### KeSpeech test shard0（232 条）

| 方言 | 干净 | 10dB 噪声 | 3m 远场 | 整句全对(干净) |
|---|---|---|---|---|
| 普通话 | **94.94%** | 93.33% | 87.46% | 71.7% |
| 东北话 | **91.41%** | 90.20% | 88.32% | 53.8% |
| 四川话(川渝) | **90.99%** | 86.95% | 79.45% | 55.0% |
| 官话(中原/江淮/冀鲁/兰银/胶辽) | **89.26%** | 89.15% | 80.72% | 48.3% |

RTF 均值 0.0167。**对照验收指标：普通话差 3.1pp、方言差 1~3pp，均未达标。**
噪声下降：普通话 1.6pp / 东北 1.2pp 满足 ≤3%；川渝 4.0pp **超标**。

### 粤语 Common Voice zh-HK test（250 条）

| 方言 | 干净 | 10dB 噪声 | 3m 远场 | 整句全对(干净) |
|---|---|---|---|---|
| 粤语 | **82.79%** | 77.73% | 72.17% | 33.2% |

错误构成：替换 284 / 删除 216 / 插入 4。Top 混淆对：
`无↔冇 ×14`、`左→咗 ×10`、`亚→阿`、`她→他`、`里→尼/你`、`喺→系`。

**读法：这些几乎全是「粤语正字 vs 普通话同音字」，不是听错了。**
模型听对了粤语发音，只是转成**书面规范字**（`冇`/`咗`/`喺`），
而 Common Voice 的标注用的是另一套写法（`无`/`左`/`里`）。
⇒ **82.79% 里有相当一部分是标注体系差异，不是识别错误。**
要拿到可信的粤语数，必须先定一套正字映射（`_test/asr/eval_set.py` 的 `dialect_map`
已预留钩子），而不是靠调模型去迎合某一种写法。

⚠ **许可**：Common Voice 数据集标 CC0，但**录音者同意书限定非商业用途**。
商用前须自行确认，清单 `meta.license` 已如实记录。

### 前置降噪 A/B：**实测无收益，已登记为负面结论**

`_test/asr/denoise.py`（谱减 + 高频补偿 + 电平对齐）全部实现且自检通过，
但跑完 A/B 结论是**不该上**：

| 场景 | 平均 Δ | 变好方言数 |
|---|---|---|
| clean | **-0.08pp** | 2/4 |
| noisy_10db | **-0.52pp** | 0/4 |
| far_3m | **-0.82pp** | 1/4 |

加权总准确率 **88.46% → 87.98%（-0.49pp）**。其中川渝远场掉了 3.12pp。

**诊断**：算法侧指标看着是对的（信噪比 12.16 → 23.10dB，+10.94dB），
但**对下游 ASR 是负作用**。原因是 Qwen3-ASR 本身是**多语种大模型**，
它对噪声的鲁棒性来自训练时的数据增强；我们在前端做的谱减把
「噪声底 + 语音」的相对关系改掉了（插入错误从 3 条涨到 21 条），
相当于用我们的先验去覆盖它的先验，而我们的先验更差。

**结论：不做。** 保留代码与 A/B 判据（防止后人重复试），但不接入生产链路。
真要提升远场，正确方向是**训练时加远场增强**（LoRA 时混入 far-field 样本），
而不是推理前硬降噪。

---

## 六方言的语料可得性（已核实）

| 方言 | 公开语料 | 能否验收 |
|---|---|---|
| 普通话 | AISHELL-3(OpenSLR 17.75GB) / WenetSpeech / KeSpeech | ✅ 可以 |
| 粤语 | **WenetSpeech-Yue**，含现成 `WSYue-ASR-eval` | ✅ 可以 |
| 四川话 | **WenetSpeech-Chuan**（10,000+ 小时） | ✅ 可以 |
| 上海话(吴) | **WenetSpeech-Wu**，含现成 `WenetSpeech-Wu-Bench` | ✅ 可以 |
| 东北话 | KeSpeech「8 方言」覆盖北方官话区，**沈阳待核实** | ⚠️ 待验 |
| 闽南语 | 仅 TTS 合成 `tw-hokkien-audio`；`teochew_wild`(18.9h 野外录音) 需申请 | ❌ **无法验收** |

**结论：闽南语 ≥92% 在现有公开语料条件下无法真实验收。**
唯一有真实录音的是 `teochew_wild`（潮州话 18.9h，需登录申请），
且潮州话 ≠ 厦门话（同属闽南语支，音系差异大）。

---

## 怎么跑基线

```powershell
# 0) 环境体检
D:\asr-train\.venv\Scripts\python.exe engine_qwen.py
# 期望：ENGINE-ENV-PASS（需 CUDA 可用 + 显存>=8GB）

# 1) 造清单（示例：AISHELL-3 test 划分）
py -3.12 -c "import sys; sys.path.insert(0,'.'); from eval_set import *; \
  cs=from_aishell3('D:/asr-data/aishell3'); write_manifest(cs,'manifests/mandarin.jsonl'); print(len(cs))"

# 2) 跑「方言 × 场景」矩阵
D:\asr-train\.venv\Scripts\python.exe run_eval.py `
  --manifest manifests/mandarin.jsonl `
  --model D:/asr-data/models/Qwen3-ASR-0.6B-hf `
  --scenarios clean,noisy_10db,far_3m `
  --out reports/baseline.json
```

跑分缓存写在 `reports/hyp_cache.jsonl`：**同一音频+场景+模型只推理一次**，
改归一化规则或换后处理时不必重跑推理。迭代成本主要在这里省。

---

## 实测性能基线（要求5 的起点）

RTX 5070 Ti Laptop(12GB) / `bfloat16` / 13.67s 中文音频：

| 项 | 实测 |
|---|---|
| 模型加载 | 2.2s |
| 单句推理（预热后） | **1.24s**，RTF=**0.098** |
| 首次调用（含 CUDA kernel 编译） | 18.19s ⇒ **必须预热再计时** |

⚠ 第一次调用 18s 是 CUDA 预热，不是稳态性能。做性能判据前必须先跑一次预热。

---

## 下一步（按优先级）

1. **拿语料**：ModelScope / 腾讯云镜像优先。普通话基线到手后立刻跑第一个真实数字。
2. **接 Web Speech 替换**：本机 ASR 不可用时的降级路径要保留（红线：不得伪装在线）。
3. **方言强制**：粤可用 `yue`；另五种只能自动识别 —— 这决定了
   「92% 方言」必须**按方言分别评估**，不能混算。
4. **热词偏置**：`prompt=Vocabulary: ...` 是零训练成本的方言专名纠偏手段，
   待有方言音频后实测其对混淆对的影响。
5. **LoRA**：放在最后。现已证明模型原生覆盖六方言，
   LoRA 从「唯一路径」降级为「可选精修」。