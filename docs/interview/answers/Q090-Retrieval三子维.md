# Q090: Retrieval 的三个子维度（relevance、evidence_accuracy、coverage）如何对应 RAG 质量？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q090 |
| 分类 | 六维评估器深入 |
| 难度 | ★★ |

## 问题

Retrieval 的三个子维度（relevance、evidence_accuracy、coverage）如何对应 RAG 质量？

## 参考答案

Retrieval 评估器是六维评估体系中专门针对 RAG（检索增强生成）质量的维度，其三个子维度分别对应 RAG 管线的不同阶段。

**Relevance（相关性，权重 0.35）** 对应 RAG 的 **检索阶段（Retrieval）** 质量。它评估检索到的文档与用户问题之间的相关程度（`retrieval_evaluator.py:41-45`）。评分标准分为四档：100 分表示所有文档直接针对问题，70-90 分表示大部分相关但有少量边缘文档，40-70 分表示相关性参差不齐，0-40 分表示大部分文档不相关。在代码实现中，评估器从 trajectory 中提取 `action_type` 为 `retrieval` 或 `tool_call` 且包含 `retrieved_docs` 的步骤（`retrieval_evaluator.py:105-108`），将检索结果格式化后送入 LLM 评判。这个维度直接影响 RAG 系统中 retriever 组件的质量评估。

**Evidence Accuracy（证据准确性，权重 0.35）** 对应 RAG 的 **生成阶段（Generation）** 质量，核心是幻觉检测（`retrieval_evaluator.py:47-51`）。它评估 Agent 的最终回答是否准确引用了检索内容。100 分表示所有陈述基于检索文档、无幻觉；70-90 分表示大部分有依据但少量添油加醋；40-70 分表示部分陈述缺少检索内容支撑；0-40 分表示严重幻觉或与文档矛盾。评估器会提取 trajectory 中最后一个 `think` 或 `respond` 步骤的内容作为最终回答（`retrieval_evaluator.py:116-120`），与检索文档对比后由 LLM 判定是否存在幻觉，并通过 `hallucination_detected` 标记输出。

**Coverage（覆盖度，权重 0.30）** 对应 RAG 的 **召回质量（Recall）**（`retrieval_evaluator.py:53-57`）。它评估检索结果是否包含回答问题所需的全部信息，而非仅仅"相关"。区别在于：Relevance 检查"检索到的文档是否与问题相关"，Coverage 检查"检索到的文档是否足够回答问题"。例如，检索到 3 篇关于 Python 的文档都是相关的（Relevance 高），但缺少关于并发编程的关键信息（Coverage 低）。评估器还会输出 `missing_info` 列表（`retrieval_evaluator.py:68`），标识信息缺口。

当 trajectory 中没有检索步骤时，评估器直接返回 overall=0（`retrieval_evaluator.py:128-132`）。

## 代码依据

- `app/evaluators/retrieval_evaluator.py:26-70` — RETRIEVAL_EVAL_PROMPT 定义三个维度的评分标准
- `app/evaluators/retrieval_evaluator.py:41-45` — Relevance 评分标准：文档与查询的相关程度四档制
- `app/evaluators/retrieval_evaluator.py:47-51` — Evidence Accuracy 评分标准：幻觉检测四档制
- `app/evaluators/retrieval_evaluator.py:53-57` — Coverage 评分标准：信息充分性四档制
- `app/evaluators/retrieval_evaluator.py:88-92` — WEIGHTS 字典：relevance 0.35, evidence_accuracy 0.35, coverage 0.30
- `app/evaluators/retrieval_evaluator.py:105-108` — 从 trajectory 提取 retrieval 和 tool_call 类型的检索结果
- `app/evaluators/retrieval_evaluator.py:116-120` — 提取最终回答：最后一个 think/respond 步骤，截断至 1000 字符
- `app/evaluators/retrieval_evaluator.py:128-132` — 无检索文档时 overall=0

## 回答要点

- 三个维度分别对应 RAG 三阶段：Relevance 对应 Retrieval，Evidence Accuracy 对应 Generation，Coverage 对应 Recall
- Relevance 和 Evidence Accuracy 权重相同（各 0.35），反映"检索到"和"用对了"同等重要
- Coverage 权重略低（0.30），但通过 missing_info 列表提供了可操作的改进方向
- Evidence Accuracy 的核心是幻觉检测，输出 hallucination_detected 布尔标记
- 最终回答从 trajectory 末尾的 think/respond 步骤提取，fallback 到 observation

## 常见追问

**Q: Relevance 和 Coverage 有什么区别？文档相关不就意味着信息充分吗？**

A: 不一定。Relevance 衡量的是"相关性方向"——文档是否与问题主题相关；Coverage 衡量的是"信息充分性"——文档是否包含回答问题所需的全部信息。例如查询"Python 异步编程的优缺点"，检索到 5 篇都关于 Python 异步编程（Relevance=100），但都只讨论了优点没有讨论缺点（Coverage 可能只有 50）。两者互补，共同评估检索质量。

**Q: 评估器如何判断是否存在幻觉？**

A: 评估器将检索文档和最终回答同时送入 LLM（`retrieval_evaluator.py:143-149`），由 LLM 对比回答中的每个关键陈述是否在检索文档中有依据。如果 Agent 声称了文档中不存在的内容，或与文档内容矛盾，就会被标记为幻觉。输出中的 `hallucination_detected` 字段为 true/false（`retrieval_evaluator.py:81`）。

## 相关题目

- [Q072](../answers/Q072-Planning四子维.md)
- [Q079](../answers/Q079-ToolUse三子维.md)
- [Q098](../answers/Q098-分块策略.md)
