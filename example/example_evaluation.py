"""
Agent Evaluation Platform — SDK 完整评估示例

演示推荐接入方式：sdk.collector 采集轨迹 → 自动触发六维评估。

运行前:
    1. 启动后端: python -m app.main
    2. 配置 .env 中的 DEEPSEEK_API_KEY（或其他 Judge 模型）

运行:
    python example_evaluation.py

环境变量（可选）:
    EVAL_API_BASE_URL=http://localhost:8000  （默认）
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from sdk.collector import ActionType, get_collector, reset_collector

BASE_URL = os.environ.get("EVAL_API_BASE_URL", "http://localhost:8000").rstrip("/")
API_V1 = f"{BASE_URL}/api/v1"

# 独立脚本走 HTTP 上报；Wiki 内嵌同进程场景才用 in-process DB
os.environ.setdefault("EVAL_INPROCESS", "false")
os.environ.setdefault("EVAL_API_BASE_URL", BASE_URL)


def _record_demo_trajectory(collector) -> None:
    """模拟一次 Agent 运行轨迹（start 已自动记录 plan 步骤）。"""
    collector.record(
        ActionType.TOOL_CALL,
        {"tool_name": "search_code", "input": {"query": "user model"}},
        observation="Found: models/user.py, models/base.py",
    )
    collector.record(
        ActionType.TOOL_CALL,
        {"tool_name": "read_file", "input": {"file_path": "models/user.py"}},
        observation="class User(Base): id, email, password_hash, is_verified",
    )
    collector.record(
        ActionType.THINK,
        {"thought": "用户模型已存在，需要添加邮箱验证字段和验证逻辑"},
    )
    collector.record(
        ActionType.TOOL_CALL,
        {"tool_name": "create_file", "input": {"file_path": "services/email_verification.py"}},
        observation="File created successfully",
    )
    collector.record(
        ActionType.TOOL_CALL,
        {"tool_name": "run_tests", "input": {"test_path": "tests/test_registration.py"}},
        observation="12 passed, 2 failed",
    )
    collector.record(
        ActionType.REPLAN,
        {
            "reason": "测试失败，需要修复邮箱验证逻辑",
            "new_plan": [
                {"description": "分析失败的测试用例"},
                {"description": "修复邮箱验证逻辑"},
                {"description": "重新运行测试"},
            ],
        },
    )
    collector.record(
        ActionType.TOOL_CALL,
        {"tool_name": "edit_file", "input": {"file_path": "services/email_verification.py"}},
        observation="File updated successfully",
    )
    collector.record(
        ActionType.TOOL_CALL,
        {"tool_name": "run_tests", "input": {"test_path": "tests/test_registration.py"}},
        observation="All 14 tests passed",
    )


def _wait_for_evaluation(task_id: str, timeout: int = 90) -> dict | None:
    """轮询评估列表，等待指定 task 的最新评估完成。"""
    deadline = time.time() + timeout
    with httpx.Client(base_url=API_V1, timeout=30.0) as client:
        while time.time() < deadline:
            resp = client.get("/evaluations/", params={"limit": 20})
            resp.raise_for_status()
            for item in resp.json():
                if item.get("task_id") != task_id:
                    continue
                if item.get("overall_score") is not None:
                    detail = client.get(f"/evaluations/{item['id']}")
                    detail.raise_for_status()
                    return detail.json()
            time.sleep(2)
    return None


def print_results(evaluation: dict) -> None:
    """打印评估结果。"""
    eval_data = evaluation.get("evaluation", {})

    print("\n" + "=" * 60)
    print("评估结果")
    print("=" * 60)

    overall = eval_data.get("overall_score", 0)
    print(f"\n综合得分: {overall:.1f}/100")

    print("\n各维度得分:")
    dimensions = [
        ("规划质量", "planning"),
        ("战术决策", "tactical"),
        ("工具使用", "tool_use"),
        ("记忆保持", "memory"),
        ("重规划", "replan"),
    ]

    for name, key in dimensions:
        score = eval_data.get(key, {}).get("overall", 0)
        bar = "█" * int(score / 5) + "░" * (20 - int(score / 5))
        print(f"  {name}: {bar} {score:.1f}/100")

    summary = eval_data.get("summary", "")
    if summary:
        print(f"\n总结: {summary}")

    recommendations = eval_data.get("recommendations", [])
    if recommendations:
        print("\n改进建议:")
        for i, rec in enumerate(recommendations, 1):
            print(f"  {i}. {rec}")

    print("\n" + "=" * 60)


async def main() -> None:
    print("Agent Evaluation Platform — SDK 评估示例")
    print("=" * 60)

    reset_collector()
    collector = get_collector()

    goal = "实现用户注册功能，包括邮箱验证"
    context = {
        "project": "Web应用",
        "language": "Python",
        "framework": "FastAPI",
        "requirements": [
            "邮箱格式验证",
            "密码强度检查",
            "发送验证邮件",
            "防止重复注册",
        ],
    }

    print("\n步骤 1: collector.start() — 创建任务并记录 plan")
    task_id = await collector.start(goal, context)
    print(f"  task_id = {task_id}")

    print("\n步骤 2: collector.record() — 记录 Agent 运行轨迹")
    _record_demo_trajectory(collector)
    print("  已记录 8 个后续步骤")

    print("\n步骤 3: collector.finish(auto_run=True) — 上报轨迹并触发评估")
    await collector.finish(auto_run=True)

    print("\n步骤 4: 等待评估完成...")
    result = _wait_for_evaluation(task_id)
    if not result:
        print("  评估超时，可能仍在后台处理")
        return

    print(f"  evaluation_id = {result.get('id')}")
    print_results(result)


if __name__ == "__main__":
    import asyncio

    try:
        asyncio.run(main())
    except httpx.ConnectError:
        print("\n连接失败！请确保后端正在运行:")
        print("  python -m app.main")
    except Exception as exc:
        print(f"\n错误: {exc}")
