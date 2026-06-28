"""
Golden Case 02 — 工具滥用 Agent：没有规划、工具调用反复失败、不重试、无记忆。

期望分数范围（低分预期）：
  - planning:      5~30（几乎没有规划）
  - tactical:      10~35（决策混乱）
  - tool_use:      5~25（重复调用错误工具）
  - memory:        0~15（完全不记忆）
  - replan:        0~20（失败后不调整）
  - retrieval:     0~10
  - overall:       5~25
"""

from datetime import datetime, timezone

from app.benchmarks.golden import GoldenCase


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


TRAJECTORY = [
    {
        "step_number": 1,
        "action_type": "tool_call",
        "action_detail": {"tool_name": "bash_execute", "input": {"command": "curl http://api.example.com/data"}},
        "observation": "curl: (6) Could not resolve host",
        "timestamp": _ts(),
    },
    {
        "step_number": 2,
        "action_type": "tool_call",
        "action_detail": {"tool_name": "bash_execute", "input": {"command": "curl http://api.example.com/data"}},
        "observation": "curl: (6) Could not resolve host",
        "timestamp": _ts(),
    },
    {
        "step_number": 3,
        "action_type": "tool_call",
        "action_detail": {"tool_name": "bash_execute", "input": {"command": "wget http://api.example.com/data"}},
        "observation": "wget: bad address",
        "timestamp": _ts(),
    },
    {
        "step_number": 4,
        "action_type": "tool_call",
        "action_detail": {"tool_name": "bash_execute", "input": {"command": "ping api.example.com"}},
        "observation": "ping: unknown host",
        "timestamp": _ts(),
    },
    {
        "step_number": 5,
        "action_type": "tool_call",
        "action_detail": {
            "tool_name": "python_execute",
            "input": {"code": "import requests\nr = requests.get('http://api.example.com/data')\nprint(r.text)"},
        },
        "observation": "ConnectionError: DNS lookup failed",
        "timestamp": _ts(),
    },
    {
        "step_number": 6,
        "action_type": "failure",
        "action_detail": {"error": "无法访问 API，放弃任务"},
        "observation": "",
        "timestamp": _ts(),
    },
]

GOLDEN_TOOL_MISUSE = GoldenCase(
    id="golden-tool-misuse",
    description="工具滥用 Agent：无规划、不重试、不记忆、一直用错误工具",
    goal="从 http://api.example.com/data 获取最新销售数据",
    trajectory=TRAJECTORY,
    expected_ranges={
        "planning": (0, 30),
        "tactical": (5, 35),
        "tool_use": (0, 25),
        "memory": (0, 20),
        "replan": (0, 25),
        "retrieval": (0, 10),
        "overall": (0, 25),
    },
)
