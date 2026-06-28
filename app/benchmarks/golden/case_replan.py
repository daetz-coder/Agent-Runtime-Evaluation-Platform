"""
Golden Case 03 — 优秀重规划 Agent：初始计划失败后主动调整策略，最终成功。

期望分数范围：
  - planning:      75~95（初始计划合理）
  - tactical:      80~95（调整决策正确）
  - tool_use:      75~92
  - memory:        70~90（记录失败原因）
  - replan:        85~100（重规划及时且有效）
  - retrieval:     0~10
  - overall:       75~95
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
            "goal": "爬取电商网站商品列表页并提取价格",
            "steps": [
                {"description": "发送 HTTP GET 请求获取页面"},
                {"description": "用 BeautifulSoup 解析 HTML"},
                {"description": "提取商品名称和价格"},
                {"description": "保存为 CSV 文件"},
            ],
        },
        "timestamp": _ts(),
    },
    {
        "step_number": 2,
        "action_type": "tool_call",
        "action_detail": {
            "tool_name": "bash_execute",
            "input": {"command": "curl -s https://example-shop.com/products"},
        },
        "observation": "curl: (7) Failed to connect",
        "timestamp": _ts(),
    },
    {
        "step_number": 3,
        "action_type": "think",
        "action_detail": {"thought": "直接连接失败，可能是网站屏蔽了 curl。尝试用 Python requests 设置 User-Agent。"},
        "timestamp": _ts(),
    },
    {
        "step_number": 4,
        "action_type": "memory_write",
        "action_detail": {"key": "connection_issue", "value": "curl 被屏蔽，需设置 User-Agent", "source": "debugging"},
        "timestamp": _ts(),
    },
    {
        "step_number": 5,
        "action_type": "tool_call",
        "action_detail": {
            "tool_name": "python_execute",
            "input": {
                "code": "import requests\nheaders = {'User-Agent': 'Mozilla/5.0'}\nr = requests.get('https://example-shop.com/products', headers=headers, timeout=10)\nprint(r.status_code)"
            },
        },
        "observation": "403",
        "timestamp": _ts(),
    },
    {
        "step_number": 6,
        "action_type": "replan",
        "action_detail": {
            "reason": "403 禁止访问，网站有反爬机制",
            "new_plan": {
                "steps": [
                    {"description": "尝试使用 API 接口而非网页"},
                    {"description": "如果 API 不可用，尝试使用缓存数据"},
                    {"description": "兜底方案：使用公开的数据集"},
                ],
            },
        },
        "timestamp": _ts(),
    },
    {
        "step_number": 7,
        "action_type": "memory_write",
        "action_detail": {
            "key": "antiscrape",
            "value": "网站返回 403，绕过方案：API > 缓存 > 公开数据集",
            "source": "replan",
        },
        "timestamp": _ts(),
    },
    {
        "step_number": 8,
        "action_type": "tool_call",
        "action_detail": {
            "tool_name": "python_execute",
            "input": {
                "code": "r = requests.get('https://example-shop.com/api/products', headers=headers)\nprint(r.status_code, r.text[:200])"
            },
        },
        "observation": '200 [{"id":1,"name":"Product A","price":29.99},...',
        "timestamp": _ts(),
    },
    {
        "step_number": 9,
        "action_type": "think",
        "action_detail": {"thought": "API 返回成功，提取价格数据保存为 CSV。"},
        "timestamp": _ts(),
    },
    {
        "step_number": 10,
        "action_type": "tool_call",
        "action_detail": {
            "tool_name": "python_execute",
            "input": {
                "code": "import csv, json\ndata = r.json()\nwith open('products.csv', 'w', newline='') as f:\n    w = csv.DictWriter(f, fieldnames=['id','name','price'])\n    w.writeheader()\n    w.writerows(data)\nprint('Saved', len(data), 'products')"
            },
        },
        "observation": "Saved 50 products",
        "timestamp": _ts(),
    },
]

GOLDEN_REPLAN = GoldenCase(
    id="golden-replan",
    description="优秀重规划 Agent：curl 失败 → 换 Python requests → 403 → 换 API → 成功",
    goal="爬取电商网站商品列表页并提取价格保存为 CSV",
    trajectory=TRAJECTORY,
    expected_ranges={
        "planning": (70, 95),
        "tactical": (75, 95),
        "tool_use": (72, 92),
        "memory": (65, 90),
        "replan": (80, 100),
        "retrieval": (0, 10),
        "overall": (70, 95),
    },
)
