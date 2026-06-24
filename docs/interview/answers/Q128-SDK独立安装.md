# Q128: SDK 能否独立 pip 安装并在非本项目 Agent 中使用？依赖有哪些？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q128 |
| 分类 | SDK 与零侵入接入 |
| 难度 | ★ |

## 问题

SDK 能否独立 pip 安装并在非本项目 Agent 中使用？依赖有哪些？

## 参考答案

Q128 与 SDK 独立安装 相关。httpx 依赖；不依赖 app 包 Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。sdk/ 可独立使用，三种 adapter 映射框架事件到 14 种 ActionType，EVAL_BATCH_SIZE 控制批量 flush。若涉及可靠性，提 monotonicity benchmark 容差 +0.05 与 ReplanEvaluator 无 missed 时满分 100 的规则。

## 代码依据

- `sdk/`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- SDK 独立安装：httpx 依赖
- 代码入口：sdk/
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「SDK 独立安装」最先看哪段代码？**

A: 打开 sdk/，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 SDK 独立安装？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q127](../answers/Q127-state-diff截断.md)
- [Q129](../answers/Q129-非LangChain接入.md)
