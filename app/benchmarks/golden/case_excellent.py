"""
Golden Case 01 — 优秀 Agent：完整规划 + 正确工具调用 + 有效记忆 + 适时的重规划。

期望分数范围：
  - planning:      85~98（完整覆盖、逻辑清晰）
  - tactical:      85~98（每一步决策合理）
  - tool_use:      80~95（工具选择恰当、参数准确）
  - memory:        75~90（有记忆读写、信息一致）
  - replan:        70~90（遇到障碍时主动调整）
  - retrieval:     0~10（无检索操作）
  - overall:       80~95
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
            "goal": "分析公司 2024 年销售数据并生成可视化报告",
            "steps": [
                {"description": "读取销售数据 CSV"},
                {"description": "数据清洗：处理缺失值和异常值"},
                {"description": "按月份和地区聚合销售额"},
                {"description": "计算同比增长率和环比增长率"},
                {"description": "生成柱状图展示月度趋势"},
                {"description": "生成饼图展示地区分布"},
                {"description": "输出分析报告 Markdown"},
            ],
        },
        "timestamp": _ts(),
    },
    {
        "step_number": 2,
        "action_type": "tool_call",
        "action_detail": {
            "tool_name": "python_execute",
            "input": {"code": "import pandas as pd\ndf = pd.read_csv('sales_2024.csv')\ndf.head()"},
        },
        "observation": "       month  region  sales\n0  2024-01  North  125000\n1  2024-01  South   98000",
        "timestamp": _ts(),
    },
    {
        "step_number": 3,
        "action_type": "think",
        "action_detail": {"thought": "数据已加载，需要检查缺失值。注意日期列需要转换格式。"},
        "timestamp": _ts(),
    },
    {
        "step_number": 4,
        "action_type": "memory_write",
        "action_detail": {"key": "data_shape", "value": "12 months x 4 regions = 48 rows", "source": "data_inspection"},
        "timestamp": _ts(),
    },
    {
        "step_number": 5,
        "action_type": "tool_call",
        "action_detail": {"tool_name": "python_execute", "input": {"code": "df.isnull().sum()\ndf.describe()"}},
        "observation": "month      0\nregion    0\nsales     2\ndtype: int64",
        "timestamp": _ts(),
    },
    {
        "step_number": 6,
        "action_type": "memory_write",
        "action_detail": {"key": "missing_data", "value": "sales 列有 2 个缺失值，需填充", "source": "data_cleaning"},
        "timestamp": _ts(),
    },
    {
        "step_number": 7,
        "action_type": "tool_call",
        "action_detail": {
            "tool_name": "python_execute",
            "input": {"code": "df['sales'].fillna(df['sales'].median(), inplace=True)"},
        },
        "observation": "",
        "timestamp": _ts(),
    },
    {
        "step_number": 8,
        "action_type": "memory_write",
        "action_detail": {"key": "cleaning_done", "value": "缺失值已用中位数填充", "source": "data_cleaning"},
        "timestamp": _ts(),
    },
    {
        "step_number": 9,
        "action_type": "tool_call",
        "action_detail": {
            "tool_name": "python_execute",
            "input": {"code": "monthly = df.groupby('month')['sales'].sum()\nmonthly_pct = monthly.pct_change() * 100"},
        },
        "observation": "month\n2024-01   125000\n2024-02   132000\n...",
        "timestamp": _ts(),
    },
    {
        "step_number": 10,
        "action_type": "tool_call",
        "action_detail": {
            "tool_name": "python_execute",
            "input": {
                "code": "import matplotlib.pyplot as plt\nplt.figure(figsize=(12,6))\nmonthly.plot(kind='bar')\nplt.title('2024 Monthly Sales Trend')\nplt.savefig('monthly_trend.png')"
            },
        },
        "observation": "Chart saved to monthly_trend.png",
        "timestamp": _ts(),
    },
    {
        "step_number": 11,
        "action_type": "tool_call",
        "action_detail": {
            "tool_name": "python_execute",
            "input": {
                "code": "region = df.groupby('region')['sales'].sum()\nplt.pie(region, labels=region.index, autopct='%1.1f%%')\nplt.savefig('region_distribution.png')"
            },
        },
        "observation": "Chart saved to region_distribution.png",
        "timestamp": _ts(),
    },
    {
        "step_number": 12,
        "action_type": "think",
        "action_detail": {"thought": "已完成所有可视化图表生成，可以撰写分析报告了。"},
        "timestamp": _ts(),
    },
]

GOLDEN_EXCELLENT = GoldenCase(
    id="golden-excellent",
    description="优秀 Agent：完整规划 → 数据清洗 → 分析 → 可视化 → 报告",
    goal="分析公司 2024 年销售数据并生成可视化报告",
    trajectory=TRAJECTORY,
    expected_ranges={
        "planning": (85, 100),
        "tactical": (85, 100),
        "tool_use": (80, 98),
        "memory": (75, 95),
        "replan": (65, 90),
        "retrieval": (0, 10),
        "overall": (80, 98),
    },
)
