# 教程 02 · 危机转介（最高优先级那一支，以及两套词表为什么不能互相冒充）

> 情绪链路里唯一"错了就有可能出事"的一支，是危机信号的识别与转介。
> 这一章讲三件事：**它在哪一层拦、拦了之后走什么路径、以及两套词表的边界在哪**。

## 1. 优先级：危机分支比其他一切都很早

前端词典引擎里危机判定是一次子串扫描，命中即置位，**不参与"分歧采信 LLM"那套逻辑**：

- `src/js/emotion-engine.js:117` — `const crisis = CRISIS.some(w => text.includes(w));`
  词表来自单一真相源 `src/data/emotion-lexicon.js` 的 `crisis` 字段（JS 与 Java 各加载同一文件）。
- 服务端 `server/.../api/EmotionController.java` 的危机分支更严：**连"有没有 Key"都不问**就返回，
  即危机命中时不产生任何上游调用（这条是构建期用例钉住的，见 `EmotionControllerTest`）。

也就是说：**危机优先 ≠ 危机更准**，它是"宁可粗糙也要先接住"的一层。

## 2. 转介长什么样

界面在命中时给的是**求助入口**（热线/转介文案），位置可复算：

- `src/index.html:124` — 危机转介与热线文案的落点
- `src/js/app.js:170`、`:364` — 转介腿的编排
- `src/js/voice-call.js:324` — 通话浮层里同样有危机转介（语音路径不例外）

验收判据（常驻，不用信我这句话）：

```bash
python _test/browser_check.py     # 断言 CRISIS 为真：危机信号被拦截并推送求助入口
```

## 3. 两套词表的边界（这里最容易讲错）

| 词表 | 在哪 | 管什么 | 例 |
|---|---|---|---|
| **危机词表** | `src/data/emotion-lexicon.js` 的 `crisis` | 输入侧：这句话要不要走危机分支 | 由数据件定义，改它=改产品行为 |
| **高危输出词表** | `server/.../safety/SafetyGuard.java` | 输出侧：生成的回复本身是否越界 | `SafetyGuard.java:60` 形如 `(上吊\|割腕\|烧炭\|跳楼\|服毒\|吞药).{0,12}(方法\|怎么做\|步骤…)` |

一手实测结论（r76 立的、本轮复核仍然成立）：**"跳楼"不在词典危机词表里**——
在 `src/data/emotion-lexicon.js` 里 grep 它是 0 命中，它出现在 `SafetyGuard.java` 的高危模式里。

⇒ 两套词表**不得互相冒充**。答辩或写文档时把"SafetyGuard 覆盖了跳楼"说成"危机识别覆盖了跳楼"，
就是拿输出侧的功劳盖输入侧的缺口。真要覆盖，得往 `crisis` 里加词，并复跑评测集看召回变化。

## 4. 复跑危机召回

```bash
node _test/emotion_eval.js                       # JS 侧：评测集里 crisis 一类的召回
curl -s localhost:8123/api/emotion/eval          # Java 侧：服务端直读同一份评测集，输出与 JS 侧同构
mvn -B -f server/pom.xml test                    # 构建期：EmotionControllerTest 把双端一致钉成回归
```

评测集是 `_test/emotion-eval-dataset.json`，**不复制进 jar**（决策 #5），所以双端跑的是同一份数据——
这也是"双端逐项一致"能成立的前提。它的条数以盘面现读为准（判据 `G8` 会盯声称条数 ⇄ 实际条数是否一致），
本文故意不写死数字：写死的句子不会自己变。

## 5. 演示时怎么说这一段

被问"你们怎么保证安全"，可复算的答案是三层：输入侧危机拦截（词典，最高优先级、不调模型）
→ 输出侧安全闸（`SafetyGuard`，管回复本身）→ 构建期用例（`EmotionControllerTest` 把"危机不调 LLM"钉成回归）。
不要说成"我们用了大模型判断危机"——那条路径恰恰**不用**大模型。
