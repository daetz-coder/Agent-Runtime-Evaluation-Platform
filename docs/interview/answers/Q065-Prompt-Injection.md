# Q65: 如何防止 Judge prompt 被 trajectory 里的恶意内容注入（Prompt Injection）？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q065 |
| 分类 | LLM-as-Judge 评估体系 |
| 难度 | ★ |

## 问题

如何防止 Judge prompt 被 trajectory 里的恶意内容注入（Prompt Injection）？

## 参考答案

Q65 与 Prompt Injection 相关。trajectory 中恶意指令；分隔符+系统 prompt  hardened Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。六维 Evaluator 继承 BaseEvaluator，temperature=0，JSON 解析失败时各子维 fallback 50 分。若涉及 RAG，强调 hybrid_search 的 RRF k=60 与 record_retrieval 写入 ActionType.RETRIEVAL。

## 代码依据

- `app/evaluators/base.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- Prompt Injection：trajectory 中恶意指令
- 代码入口：app/evaluators/base.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「Prompt Injection」最先看哪段代码？**

A: 打开 app/evaluators/base.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 Prompt Injection？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q064](../answers/Q064-分数与feedback不一致.md)
- [Q066](../answers/Q066-prompt版本管理.md)
