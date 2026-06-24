# Q158: Wiki 知识库上传 Markdown 有没有 XSS / 路径遍历风险？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q158 |
| 分类 | 系统设计与生产化 |
| 难度 | ★ |

## 问题

Wiki 知识库上传 Markdown 有没有 XSS / 路径遍历风险？

## 参考答案

Q158 与 Wiki XSS 相关。Markdown sanitize；path 校验 Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。当前 BackgroundTasks 适合 Demo 量级；10 万/日需 Celery、PostgreSQL、Judge 限流与多租户 workspace。若涉及可靠性，提 monotonicity benchmark 容差 +0.05 与 ReplanEvaluator 无 missed 时满分 100 的规则。

## 代码依据

- `app/wiki_agent/`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- Wiki XSS：Markdown sanitize
- 代码入口：app/wiki_agent/
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「Wiki XSS」最先看哪段代码？**

A: 打开 app/wiki_agent/，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 Wiki XSS？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q157](../answers/Q157-PII脱敏.md)
- [Q159](../answers/Q159-WEBHOOK安全.md)
