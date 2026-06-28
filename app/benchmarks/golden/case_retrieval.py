"""
Golden Case 04 — 检索密集型 Agent：依赖知识库检索回答问题，有幻觉检测。

期望分数范围：
  - planning:      65~85（检索为主，规划简洁）
  - tactical:      70~88
  - tool_use:      70~88
  - memory:        50~75
  - replan:        30~60（检索失败时调整）
  - retrieval:     70~95（检索质量较高）
  - overall:       60~85
"""

from datetime import datetime, timezone

from app.benchmarks.golden import GoldenCase


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


TRAJECTORY = [
    {
        "step_number": 1,
        "action_type": "plan",
        "action_detail": {
            "goal": "回答：LangGraph 中 StateGraph 和 MessageGraph 有什么区别？",
            "steps": [
                {"description": "检索 LangGraph 文档中关于 StateGraph 的部分"},
                {"description": "检索 MessageGraph 相关文档"},
                {"description": "对比两者差异并总结"},
            ],
        },
        "timestamp": _ts(),
    },
    {
        "step_number": 2,
        "action_type": "retrieval",
        "action_detail": {"query": "LangGraph StateGraph", "top_k": 3},
        "observation": "Found 3 chunks:\n1. StateGraph manages state...\n2. State schema defines...\n3. Nodes read/write state...",
        "timestamp": _ts(),
    },
    {
        "step_number": 3,
        "action_type": "retrieval",
        "action_detail": {"query": "LangGraph MessageGraph vs StateGraph", "top_k": 3},
        "observation": "Found 2 chunks:\n1. MessageGraph is a simpler StateGraph...\n2. MessageGraph uses message list as state...",
        "timestamp": _ts(),
    },
    {
        "step_number": 4,
        "action_type": "evidence",
        "action_detail": {"source": "StateGraph docs", "claim": "StateGraph requires explicit state schema definition"},
        "observation": "LangGraph docs v0.2, page 12",
        "timestamp": _ts(),
    },
    {
        "step_number": 5,
        "action_type": "evidence",
        "action_detail": {
            "source": "MessageGraph docs",
            "claim": "MessageGraph uses a list of messages as implicit state",
        },
        "observation": "LangGraph docs v0.2, page 15",
        "timestamp": _ts(),
    },
    {
        "step_number": 6,
        "action_type": "think",
        "action_detail": {
            "thought": "关键区别：1) StateGraph 需显式定义 schema，MessageGraph 隐式使用消息列表 2) StateGraph 适合复杂状态，MessageGraph 适合简单对话"
        },
        "timestamp": _ts(),
    },
    {
        "step_number": 7,
        "action_type": "memory_write",
        "action_detail": {
            "key": "langgraph_diff",
            "value": "StateGraph=显式schema / MessageGraph=隐式messages",
            "source": "retrieval_synthesis",
        },
        "timestamp": _ts(),
    },
    {
        "step_number": 8,
        "action_type": "retrieval",
        "action_detail": {"query": "LangGraph when to use MessageGraph vs StateGraph", "top_k": 2},
        "observation": "Found 1 chunk:\n1. Use MessageGraph for simple chatbot...",
        "timestamp": _ts(),
    },
    {
        "step_number": 9,
        "action_type": "think",
        "action_detail": {
            "thought": "综合检索结果：StateGraph 适用于需要精细控制状态的复杂应用；MessageGraph 适用于简单的消息对话场景。"
        },
        "timestamp": _ts(),
    },
]

GOLDEN_RETRIEVAL = GoldenCase(
    id="golden-retrieval",
    description="检索密集型 Agent：多轮检索 → 证据提取 → 综合回答",
    goal="回答：LangGraph 中 StateGraph 和 MessageGraph 有什么区别？",
    trajectory=TRAJECTORY,
    expected_ranges={
        "planning": (60, 85),
        "tactical": (65, 88),
        "tool_use": (65, 88),
        "memory": (45, 75),
        "replan": (30, 65),
        "retrieval": (70, 98),
        "overall": (60, 85),
    },
)
