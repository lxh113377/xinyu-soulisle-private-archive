# 开源精读 · Open-LLM-VTuber 的「打断语义」与「agent 扩展面」（r127 / 2026-10-12）

> 任务原文「参考 GitHub 优质项目系统性学习 / 复现关键功能 / 对比自身实现差异」的落地件。
> 对象：`Open-LLM-VTuber/Open-LLM-VTuber`（14,053★，Python，末次 push 2026-05-15）。
> 读的原文：`agent/agents/agent_interface.py`、`agent/agent_factory.py`（`gh api` 取回，非二手转述）。
> 结论：**不提 issue**（对方无缺陷）；但我方有一条**可复现的行为落差**＋一条**架构借鉴**，见下。

## 一、两边形态对照（同一功能，两种做法）

| 面 | 对方（原文） | 我方（HEAD 面原文） | 判定 |
|---|---|---|---|
| 打断语义 | `AgentInterface.handle_interrupt(heard_response: str)` —— 抽象方法，**把打断前已被听到的半句交给 agent**（docstring：The AI may not be able to understand that it was interrupted.） | `voice-call.js::bargeIn()`：`cancelSpeech()` 后 `speakingBuf = ""` —— **半句直接丢弃**，无回传 | ⚠️ **真落差**（下节） |
| 记忆后端 | 抽象成接口，由 `AgentFactory.create_agent(choice,…)` **静态工厂按配置**选实现（basic_memory / mem0 / letta / hume） | 布尔开关 `cfg.remote`（本地 localStorage / 远端 H2 两态） | 借鉴（非缺陷） |
| 抽象层级 | `chat()` 返回 `AsyncIterator[BaseOutput]`，`SentenceOutput`（文本+TTS 文本）/`AudioOutput`（音频+转写）两类输出显式建模 | 回调式 `onDelta(full)` + 前端切句 | 形态不同，够用；不构成差距项 |

## 二、落差一：被打断的半句被丢掉（可复现，未修）

- **行为差异**：对方让模型知道「我说到一半被你打断」；我方模型对此**无感知**——下一轮它当上一句是完整的。
- **可复现**：通话中说一句长回复 → 中途插话 → 再问「你刚才说到哪了」⇒ 对方形态可作答，我方形态无信息可答。
- **最小修法（提案，未动码）**：`bargeIn()` 里判 `speakingBuf.trim()` 非空 ⇒ 以「被打断的助手消息」注入下一轮上下文
  （沿用 `chat-agent.js` 现有 history 形状，加一个不破坏旧读法的标记字段；无半句时行为与旧版**完全一致**）。
- **验收（三条，可复算）**：① 既有 `_test/voice_call_check.py` 全绿（零回归）；② 新增用例：脚本化「说到第 2 句被打断」
  ⇒ 断言下一轮上下文里含被截断前缀；③ 无半句路径：注入前后 history 逐字节相同（防"顺手改形状"）。
- **开工前提（实测）**：`src/js/voice-call.js` 与 `src/js/chat-agent.js` **当前均有未提交改动**（`git status` 读 M）
  ⇒ 按项目并发纪律**不在在途件上动手**；待干净窗口再做。已登记 `07-next-steps.part150.md` R127-09。

## 三、落差二：扩展面形态（借鉴，非缺陷）

- 对方的「记忆后端 = 接口 + 工厂」把 *换实现* 变成 `config` 一行；我方把 *开关远端* 变成 `cfg.remote` 一行。
- **对第 5 维（可扩展性）的意义**：将来若开向量长记忆（选项 A），**第一步不该是加服务**，而是先把
  `MemoryService` 抽成 `MemoryProvider` 接口（默认实现＝现有 H2 两表）——这样侧车接进来只是新增一个实现，
  而不是改动调用面。代价≈1 轮、零行为变化，且让"是否开向量"这个决策**更便宜**。
- 已并入卷152 的 A 案「最小可逆试验」前置。

## 四、为什么不对他们提 issue

读了 `agent_interface.py` / `agent_factory.py` 两份原文，**未见缺陷**：抽象方法的"未实现即告警 + pass"是刻意设计，
工厂是显式闭集（非动态插件面，文档也如此声明）。按发送门槛（本地交付件《开源协作现状-2026-10-12-r127.md》§三），
无最小复现不得发——**不凑数**。
