# Q19: `evidence` 动作类型的设计意图是什么？它和 `retrieval` 有什么区别？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q019 |
| 分类 | Agent 架构与设计理念 |
| 难度 | ★ |

## 问题

`evidence` 动作类型的设计意图是什么？它和 `retrieval` 有什么区别？

## 参考答案

retrieval 记录检索动作：query、retrieved_docs 列表（path/snippet/score 等）；evidence 记录最终送入 LLM 的证据池（可能裁剪/重排后）。RetrievalEvaluator 消费 retrieval；evidence 帮助评 evidence_accuracy 与幻觉。Wiki search 节点 hybrid_search 后 record_retrieval，respond 前可 record_evidence。

## 代码依据

- `app/evaluators/retrieval_evaluator.py`
- `app/wiki_agent/agent/eval_middleware.py`
- `app/models/action_types.py`

## 回答要点

- retrieval=召回阶段
- evidence=生成前证据池
- retrieved_docs 结构是评估输入
- 两者分离定位召回 vs 引用问题

## 常见追问

**Q: 只录 evidence 够吗？**

A: 不够，无法评 coverage/relevance 召回。

**Q: 字段必填？**

A: path、content/snippet、score 等见 RetrievalEvaluator prompt。

## 相关题目

- [Q018](../answers/Q018-think-node-decision.md)
- [Q020](../answers/Q020-第三方框架适配.md)
