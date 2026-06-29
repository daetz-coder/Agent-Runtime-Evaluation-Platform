# Q174: 阅读 `hybrid_search` 的 RRF 实现，手工算两个排名的融合结果。

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q174 |
| 分类 | 编码与现场设计题 |
| 难度 | ★ |

## 问题

阅读 `hybrid_search` 的 RRF 实现，手工算两个排名的融合结果。

## 参考答案

问题「阅读 `hybrid_search` 的 RRF 实现，手工算两个排名的融合结果。」考察 RRF 手算。两列表 rank 代入 1/(60+r+1) 相加 改动 Evaluator 需同步 app/models/schemas.py、evaluators/__init__.py、evaluation_graph 注册与 aggregate WEIGHTS。 首要读 app/wiki_agent/agent/tools/search_tools.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及接入，说明 sdk/adapters/ 三种 adapter 的场景选择。

## 代码依据

- `app/wiki_agent/agent/tools/search_tools.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- RRF 手算：两列表 rank 代入 1/(60+r+1) 相加
- 代码入口：app/wiki_agent/agent/tools/search_tools.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「RRF 手算」最先看哪段代码？**

A: 打开 app/wiki_agent/agent/tools/search_tools.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 RRF 手算？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q173](../answers/Q173-instrument-langgraph.md)
- [Q175](../answers/Q175-新增Safety维.md)
