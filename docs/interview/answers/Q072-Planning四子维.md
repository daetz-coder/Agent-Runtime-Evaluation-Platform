# Q072: Planning 的四个子维度（coverage、ordering、granularity、completeness）分别评估什么？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q072 |
| 分类 | 六维评估器深入 |
| 难度 | ★★ |

## 问题

Planning 的四个子维度（coverage、ordering、granularity、completeness）分别评估什么？

## 参考答案

Planning 评估器通过四个子维度对 Agent 的规划质量进行量化打分，每个维度 0-100 分，最终按加权平均计算 overall 分数。

**Coverage（覆盖率，权重 0.3）** 评估计划是否覆盖了用户目标的所有关键里程碑。Prompt 中明确要求考虑"分析、实现、测试、文档等阶段"（`planning_evaluator.py:33-37`）。高分示例：Agent 将一个 API 开发任务拆解为"设计接口 → 编写实现 → 编写单元测试 → 更新文档"等完整步骤链。低分示例：只列出"编写代码"，遗漏了测试和文档阶段。该维度与 completeness 的区别在于，coverage 关注"有没有这个步骤"，而 completeness 关注"这个步骤描述是否完整"。

**Ordering（顺序性，权重 0.2）** 评估步骤之间的逻辑顺序和依赖关系是否正确（`planning_evaluator.py:39-42`）。高分示例：先完成数据库 schema 设计，再编写 ORM 模型，最后编写 API 路由。低分示例：要求"先部署到生产环境，再编写测试用例"，违反了基本的开发流程依赖。LLM 评判时会检查是否存在循环依赖或逻辑矛盾。

**Granularity（粒度，权重 0.2）** 评估计划的细化程度是否适中（`planning_evaluator.py:44-48`）。Prompt 中给出了正反示例：过细如"阅读第 20 行"不好，过粗如"实现所有功能"也不好，合适的粒度如"实现 OAuth 流程"、"编写单元测试"。粒度评估的核心是步骤能否指导实际执行——既不能太抽象以至于无法操作，也不能太琐碎以至于失去计划的意义。

**Completeness（完整性，权重 0.3）** 评估计划是否覆盖了目标的所有方面，包括边界情况和明确的完成状态（`planning_evaluator.py:49-53`）。高分示例：计划中包含错误处理策略、回滚方案、验收标准。低分示例：只考虑 happy path，未考虑网络超时、权限不足等异常场景。

当 Agent 没有产生任何显式计划时，四个子维度全部返回 0 分（`planning_evaluator.py:100-108`）。

## 代码依据

- `app/evaluators/planning_evaluator.py:18-66` — PLANNING_EVALUATION_PROMPT 定义四个维度的评分标准
- `app/evaluators/planning_evaluator.py:33-37` — Coverage 评估要求：里程碑覆盖、关键步骤遗漏检查
- `app/evaluators/planning_evaluator.py:39-42` — Ordering 评估要求：步骤顺序、依赖关系
- `app/evaluators/planning_evaluator.py:44-48` — Granularity 评估要求：过细/过粗的正反示例
- `app/evaluators/planning_evaluator.py:50-53` — Completeness 评估要求：边界情况、完成状态
- `app/evaluators/planning_evaluator.py:72-77` — WEIGHTS 字典：coverage 0.3, ordering 0.2, granularity 0.2, completeness 0.3
- `app/evaluators/planning_evaluator.py:100-108` — 无计划时全部维度返回 0 分

## 回答要点

- Coverage 和 Completeness 权重最高（各 0.3），反映"做了什么"和"做得多完整"是规划质量的核心
- Ordering 和 Granularity 权重较低（各 0.2），属于辅助性质量指标
- 四个维度均由 LLM-as-Judge 打分，Prompt 中提供了 0-100 的分级标准
- 无显式计划时所有维度归零，而非给默认分数
- 覆盖率关注步骤是否"有"，完整性关注步骤描述是否"全"——两者互补但不重叠

## 常见追问

**Q: Coverage 和 Completeness 有什么区别？不会重复评估吗？**

A: Coverage 关注"计划中是否列出了所有必要步骤"，是广度维度——例如是否遗漏了测试阶段。Completeness 关注"每个步骤是否考虑了边界情况和完成标准"，是深度维度——例如测试步骤是否包含了边界条件测试和回归测试。两者分别从横向和纵向评估计划质量，权重均为 0.3，合计占总分 60%。

**Q: 如果 Agent 的计划是动态更新的，怎么评估？**

A: 评估器会同时提取初始计划和 plan_update（`planning_evaluator.py:97-98`），将动态调整记录拼接到计划文本中一并送入 LLM 评估（`planning_evaluator.py:112-114`）。这样可以评估 Agent 是否在执行过程中合理修正了计划。

## 相关题目

- [Q073](../answers/Q073-Planning无计划处理.md)
- [Q079](../answers/Q079-ToolUse三子维.md)
- [Q090](../answers/Q090-Retrieval三子维.md)
