# Q129: 如果 Agent 使用非 LangChain 技术栈（纯 OpenAI API、Anthropic SDK），如何接入？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q129 |
| 分类 | SDK 与零侵入接入 |
| 难度 | ★ |

## 问题

如果 Agent 使用非 LangChain 技术栈（纯 OpenAI API、Anthropic SDK），如何接入？

## 参考答案

问题「如果 Agent 使用非 LangChain 技术栈（纯 OpenAI API、Anthropic SDK），如何接入？」考察 非 LangChain 接入。手动 record 或 HTTP API sdk/ 可独立使用，三种 adapter 映射框架事件到 14 种 ActionType，EVAL_BATCH_SIZE 控制批量 flush。 首要读 sdk/collector.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及接入，说明 sdk/adapters/ 三种 adapter 的场景选择。

## 代码依据

- `sdk/collector.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- 非 LangChain 接入：手动 record 或 HTTP API
- 代码入口：sdk/collector.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「非 LangChain 接入」最先看哪段代码？**

A: 打开 sdk/collector.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 非 LangChain 接入？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q128](../answers/Q128-SDK独立安装.md)
- [Q130](../answers/Q130-ActionType同步.md)
