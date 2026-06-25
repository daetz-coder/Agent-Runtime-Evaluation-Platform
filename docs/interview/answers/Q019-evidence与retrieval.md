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

`evidence` 的设计目的是**记录最终提供给 LLM 用于生成回答的证据集合**，而 `retrieval` 记录的是**检索阶段召回的候选文档**。两者对应 RAG（Retrieval-Augmented Generation）流程中的不同阶段，因此需要分开记录。

------

### retrieval：记录检索阶段（Recall）

`retrieval` 用于记录检索动作本身，包括：

- 检索 query；
- 检索得到的 `retrieved_docs`；
- 每个文档的 `path`、`snippet/content`、`score` 等信息。

例如：

```text
Query:
"Transformer attention"

Retrieved Docs:
Doc A (score=0.95)
Doc B (score=0.91)
Doc C (score=0.83)
```

它反映的是：

> **系统检索到了哪些候选资料。**

**主要用于：**

- Retrieval Evaluator；
- 评估 Recall、Coverage、Relevance；
- 判断检索质量是否足够。

------

### evidence：记录最终证据池（Evidence Pool）

检索完成后，Agent 通常不会把所有召回文档直接交给 LLM，而会经过：

- 去重（Deduplication）；
- 重排序（Reranking）；
- 裁剪（Chunk Selection）；
- 拼接（Context Packing）。

最终形成真正送入 Prompt 的上下文。

例如：

```text
Retrieved:
A
B
C
D
E
F

↓

Rerank

↓

Keep:
A
C
E

↓

Trim

↓

Evidence
```

`evidence` 记录的就是：

> **最终进入 LLM Prompt 的证据内容。**

因此，它更贴近生成阶段。

------

## retrieval 与 evidence 的区别

| Action        | 记录内容                                    | 所处阶段   | 作用                                |
| ------------- | ------------------------------------------- | ---------- | ----------------------------------- |
| **retrieval** | 检索得到的候选文档（query、retrieved_docs） | 召回阶段   | 评估检索质量（Coverage、Relevance） |
| **evidence**  | 最终送入 LLM 的证据池                       | 生成前阶段 | 评估证据引用是否准确、是否支撑回答  |

------

## 为什么要分开？

两者分离可以明确区分问题出在哪个阶段。

例如：

### 情况一：检索失败

```text
Query

↓

Retrieval（错误）
↓

Evidence（错误）
↓

Answer（错误）
```

原因在于**召回阶段**，属于 Retrieval 问题。

------

### 情况二：检索正确，但引用错误

```text
Query

↓

Retrieval（正确）
↓

Evidence（遗漏关键文档）
↓

Answer（错误）
```

说明问题出在**证据筛选或组织阶段**，而不是检索本身。

------

### 情况三：证据正确，但回答错误

```text
Retrieval（正确）

↓

Evidence（正确）

↓

LLM 回答（幻觉）
```

说明是生成阶段没有正确利用证据。

如果只记录 `retrieval` 或只记录 `evidence`，都无法准确定位是哪一环出了问题。

------

## 对评估器的影响

- **RetrievalEvaluator** 主要消费 `retrieval`，依据 `retrieved_docs` 评估召回的覆盖率、相关性等。
- **evidence** 则用于评估最终证据是否足以支撑回答，例如 `evidence_accuracy`、引用准确性，以及判断回答是否存在幻觉（Hallucination）。

------

## 为什么不能只记录 evidence？

如果只记录 `evidence`，评估器只能看到**最终使用了哪些证据**，却无法知道：

- 是否遗漏了更相关的文档；
- 检索阶段是否召回充分；
- 被过滤掉的文档是否更优。

因此无法评估 **Coverage** 和 **Relevance**，也无法区分是“没检索到”还是“检索到了但没用”。

------

### 总结

- **`retrieval` = 检索阶段**：记录查询及召回的候选文档（`retrieved_docs`），用于评估召回质量。
- **`evidence` = 生成前阶段**：记录最终送入 LLM 的证据池，用于评估证据引用和回答可靠性。
- 两者分离能够将问题定位到**召回**、**证据筛选**或**生成利用**三个不同环节，从而提升评估的可解释性和诊断能力。



## 代码依据

- `app/evaluators/retrieval_evaluator.py`
- `app/wiki_agent/evaluation.py`
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
