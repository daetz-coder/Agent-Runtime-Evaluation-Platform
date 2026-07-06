"""
记忆质量评估器

评估 Agent 记忆的质量：
- 保持力 (Retention)：关键事实是否被保留？
- 相关性 (Relevance)：回忆的信息是否相关？
- 一致性 (Consistency)：记忆是否与上下文一致？
"""

from typing import Any, Dict, List, Optional

from langchain_core.prompts import ChatPromptTemplate

from app.evaluators.base import BaseEvaluator
from app.evaluators.eval_schemas import MemoryEvaluationResult
from app.models.schemas import MemoryScore, TrajectoryStep

MEMORY_EVALUATION_PROMPT = """你必须用中文输出所有内容（包括 feedback、forgotten_facts、inconsistencies）。你是一位 AI Agent 记忆质量评估专家。

## 用户目标
{goal}

## 轨迹（展示记忆使用情况）
{trajectory}

## 应记住的关键事实
{key_facts}

## 上下文
{context}

## 评估标准

请从以下维度评估 Agent 的记忆能力（0-100 分），严格按照锚点评分：

### 1. 保持力 (Retention, 0-100)
Agent 是否在整个执行过程中记住关键事实？忘记影响解决方案的关键事实是重大问题。

| 分数 | 锚点表现 |
|------|----------|
| 0    | 完全没有记忆能力：重复询问已知信息、忘记刚读过的文件内容、丢失关键上下文 |
| 25   | 遗忘了超过一半的关键事实（如忘记了项目技术栈、忘记已发现的 bug 根因） |
| 50   | 保留了主要事实，但遗忘了 1-2 个关键信息（如忘记了数据库类型、忘记了 API 约束） |
| 75   | 保留了绝大部分关键事实，仅遗忘 1 个次要信息 |
| 100  | 完美保持：在整个执行过程中始终记住所有关键事实，无信息丢失 |

### 2. 相关性 (Relevance, 0-100)
Agent 回忆的信息是否相关？是否恰当地使用了回忆的信息？

| 分数 | 锚点表现 |
|------|----------|
| 0    | 回忆的信息与当前任务完全无关（如修认证时回忆数据库优化经验） |
| 25   | 大部分回忆的信息无关或未被使用，仅偶尔相关 |
| 50   | 约一半的回忆信息相关且被使用，另一半无关或未被利用 |
| 75   | 大部分回忆的信息直接相关且被恰当使用，仅 1 次回忆了不相关信息 |
| 100  | 每次回忆都精准相关：在需要时调出正确的信息，并直接应用于当前任务 |

### 3. 一致性 (Consistency, 0-100)
Agent 的记忆在整个执行过程中是否一致？是否存在矛盾？

| 分数 | 锚点表现 |
|------|----------|
| 0    | 严重矛盾：同一信息前后说法相反（如先说"用 JWT"后说"用 sessions"） |
| 25   | 多处矛盾（≥3 处），导致后续决策混乱 |
| 50   | 有 1-2 处不一致（如先说"Python 3.11"后说"Python 3.10"），但未影响决策 |
| 75   | 基本一致，仅 1 处表述模糊导致轻微歧义 |
| 100  | 完全一致：所有记忆条目前后吻合，零矛盾，信息传递准确无误 |

feedback 字段请用中文。forgotten_facts 列出被遗忘的关键事实，inconsistencies 列出记忆矛盾。

{format_instructions}
"""


class MemoryEvaluator(BaseEvaluator):
    """评估 Agent 执行过程中的记忆质量。"""

    WEIGHTS = {
        "retention": 0.45,
        "relevance": 0.30,
        "consistency": 0.25,
    }

    async def evaluate(
        self,
        goal: str,
        trajectory: List[TrajectoryStep],
        context: Optional[Dict[str, Any]] = None,
    ) -> MemoryScore:
        """
        评估记忆质量。

        Args:
            goal: 用户的原始目标
            trajectory: Agent 执行步骤列表
            context: 附加上下文（应包含 key_facts）

        Returns:
            包含详细评估结果的 MemoryScore
        """
        if not trajectory:
            return MemoryScore(
                retention=0,
                relevance=0,
                consistency=0,
                overall=0,
                feedback="No trajectory steps provided for memory evaluation.",
            )

        # 从上下文中提取关键事实
        key_facts = context.get("key_facts", []) if context else []
        if not key_facts:
            key_facts = self._infer_key_facts(goal, trajectory)

        # 提取记忆事件（显式的读/写操作）
        memory_events = self._extract_memory_events(trajectory)

        # 格式化轨迹用于评估
        trajectory_text = self._format_trajectory(trajectory)
        key_facts_text = self._format_key_facts(key_facts)

        # 追加显式记忆事件（如有）
        if memory_events:
            trajectory_text += "\n\n## Explicit Memory Events\n"
            trajectory_text += self._format_memory_events(memory_events)

        # 创建提示词 + 结构化输出链
        prompt = ChatPromptTemplate.from_template(MEMORY_EVALUATION_PROMPT)
        structured_llm = self.llm.with_structured_output(MemoryEvaluationResult)
        chain = prompt | structured_llm

        # 获取 LLM 评估结果（结构化输出 + 重试机制）
        result = await self._invoke_structured_llm(
            chain,
            {
                "goal": goal,
                "trajectory": trajectory_text,
                "key_facts": key_facts_text,
                "context": context or "No additional context provided.",
                "format_instructions": "",  # PydanticOutputParser 降级时会覆盖
            },
            schema_class=MemoryEvaluationResult,
            max_retries=3,
            prompt=prompt,
        )

        # Pydantic model 直接使用
        scores = result.model_dump() if isinstance(result, MemoryEvaluationResult) else result

        # 计算加权总分
        overall = self._calculate_weighted_score(scores, self.WEIGHTS)

        # 提取 LLM 建议（来自 forgotten_facts）
        llm_suggestions = []
        forgotten = scores.get("forgotten_facts") or []
        if isinstance(forgotten, list):
            for fact in forgotten:
                if isinstance(fact, str):
                    llm_suggestions.append(f"需关注已遗忘的关键信息：{fact}")

        return MemoryScore(
            retention=scores.get("retention", 0),
            relevance=scores.get("relevance", 0),
            consistency=scores.get("consistency", 0),
            overall=overall,
            feedback=scores.get("feedback", "Evaluation completed."),
            llm_suggestions=llm_suggestions,
        )

    def _infer_key_facts(self, goal: str, trajectory: List[TrajectoryStep]) -> List[str]:
        """从轨迹中推断应被记住的关键事实。"""
        key_facts = []

        # 在前几个步骤中查找提到的事实
        for step in trajectory[:10]:
            if step.observation:
                # 从观察结果中提取潜在的关键事实
                obs = step.observation.lower()
                if "jwt" in obs:
                    key_facts.append("Project uses JWT for authentication")
                if "react" in obs:
                    key_facts.append("Frontend uses React")
                if "python" in obs or "fastapi" in obs:
                    key_facts.append("Backend uses Python/FastAPI")
                if "database" in obs or "postgres" in obs:
                    key_facts.append("Uses PostgreSQL database")

        # 添加与目标相关的事实
        goal_lower = goal.lower()
        if "auth" in goal_lower or "login" in goal_lower:
            key_facts.append("Task involves authentication")
        if "bug" in goal_lower or "fix" in goal_lower:
            key_facts.append("Task is bug-fixing")

        return key_facts if key_facts else ["No specific key facts identified"]

    def _format_key_facts(self, key_facts: List[str]) -> str:
        """将关键事实格式化为可读文本。"""
        if not key_facts:
            return "No key facts provided"

        lines = []
        for i, fact in enumerate(key_facts, 1):
            lines.append(f"{i}. {fact}")

        return "\n".join(lines)

    def _format_memory_events(self, memory_events: List[Dict[str, Any]]) -> str:
        """将记忆事件格式化为可读文本。"""
        lines = []
        for event in memory_events:
            step = event.get("step", "?")
            event_type = event.get("type", "unknown")
            key = event.get("key", "")
            value = event.get("value", "")
            source = event.get("source", "")
            context = event.get("context", "")
            hit = event.get("hit", True)
            memory_type = event.get("memory_type", "")

            if event_type == "memory_write":
                lines.append(f"Step {step}: WRITE [{memory_type}] {key} = {str(value)[:200]}")
                if source:
                    lines.append(f"  Source: {source}")
            elif event_type == "memory_read":
                status = "HIT" if hit else "MISS"
                lines.append(f"Step {step}: READ [{status}] {key}")
                if value:
                    lines.append(f"  Value: {str(value)[:200]}")
                if context:
                    lines.append(f"  Context: {context}")
            lines.append("")

        return "\n".join(lines) if lines else "No memory events recorded"

    def _parse_scores(self, content: str) -> Dict[str, Any]:
        """将 LLM 响应解析为评分字典。"""
        parsed = self._parse_json_from_llm(content)
        if parsed is not None:
            return parsed

        return {
            "retention": 50,
            "relevance": 50,
            "consistency": 50,
            "feedback": content,
        }
