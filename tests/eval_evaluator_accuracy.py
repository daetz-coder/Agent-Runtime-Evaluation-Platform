"""
评估器准确性验证 — 用精心设计的测试用例验证评估器是否合理。

模式:
  1. Mock 模式（默认）: 预置 trajectory，验证评估器能正确处理空/残缺等边界情况
  2. 真实 LLM 模式 (EVAL_USE_REAL_LLM=1): 调用真实 LLM 获取实际分数

用法:
    python -m tests.eval_evaluator_accuracy
    EVAL_USE_REAL_LLM=1 python -m tests.eval_evaluator_accuracy
"""

import asyncio
import sys
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from typing import Any, Dict, List
from datetime import datetime, timezone


# ── 测试场景 ──

# 场景 1: 好规划 — 覆盖完整、顺序合理
GOOD_PLAN_TRAJECTORY = [
    {"step_number": 1, "action_type": "plan", "action_detail": {
        "goal": "修复 JWT 过期 Bug",
        "steps": [
            {"description": "分析 JWT token 生成与验证流程"},
            {"description": "定位 token 过期时间设置的位置"},
            {"description": "修改 JWT 过期时间为 24h"},
            {"description": "添加 token 刷新接口"},
            {"description": "编写单元测试"},
            {"description": "运行回归测试"},
        ],
    }, "timestamp": datetime.now(timezone.utc).isoformat()},
    {"step_number": 2, "action_type": "tool_call",
     "action_detail": {"tool_name": "search_code", "input": {"query": "JWT"}},
     "observation": "Found jwt.py", "timestamp": datetime.now(timezone.utc).isoformat()},
    {"step_number": 3, "action_type": "tool_call",
     "action_detail": {"tool_name": "read_file", "input": {"file_path": "jwt.py"}},
     "observation": "JWT_ACCESS_TOKEN_EXPIRES = 3600",
     "timestamp": datetime.now(timezone.utc).isoformat()},
    {"step_number": 4, "action_type": "tool_call",
     "action_detail": {"tool_name": "edit_file", "input": {"file_path": "jwt.py", "changes": "86400"}},
     "observation": "File updated", "timestamp": datetime.now(timezone.utc).isoformat()},
    {"step_number": 5, "action_type": "tool_call",
     "action_detail": {"tool_name": "run_tests", "input": {"test_path": "tests/test_auth.py"}},
     "observation": "All 18 passed", "timestamp": datetime.now(timezone.utc).isoformat()},
]

# 场景 2: 差规划 — 缺少关键步骤
BAD_PLAN_TRAJECTORY = [
    {"step_number": 1, "action_type": "plan", "action_detail": {
        "goal": "部署到生产环境",
        "steps": [{"description": "直接部署"}],
    }, "timestamp": datetime.now(timezone.utc).isoformat()},
    {"step_number": 2, "action_type": "tool_call",
     "action_detail": {"tool_name": "deploy", "input": {"target": "production"}},
     "observation": "Failed", "timestamp": datetime.now(timezone.utc).isoformat()},
    {"step_number": 3, "action_type": "failure",
     "action_detail": {"error_type": "DeploymentError", "error_message": "部署失败"},
     "timestamp": datetime.now(timezone.utc).isoformat()},
]

# 场景 3: 重规划场景
REPLAN_TRAJECTORY = [
    {"step_number": 1, "action_type": "plan", "action_detail": {
        "goal": "实现搜索功能",
        "steps": [{"description": "设计 API"}, {"description": "实现 Elasticsearch"}, {"description": "测试"}],
    }, "timestamp": datetime.now(timezone.utc).isoformat()},
    {"step_number": 2, "action_type": "failure",
     "action_detail": {"error_type": "ResourceError", "error_message": "ES 未安装"},
     "timestamp": datetime.now(timezone.utc).isoformat()},
    {"step_number": 3, "action_type": "replan", "action_detail": {
        "reason": "ES 不可用，改用 PostgreSQL LIKE 查询",
        "new_plan": [{"description": "实现 PG 搜索"}, {"description": "添加索引"}],
    }, "timestamp": datetime.now(timezone.utc).isoformat()},
    {"step_number": 4, "action_type": "tool_call",
     "action_detail": {"tool_name": "create_file", "input": {"file_path": "services/search.py"}},
     "observation": "Created", "timestamp": datetime.now(timezone.utc).isoformat()},
]

# 场景 4: 空轨迹
EMPTY_TRAJECTORY = []

# 场景 5: 残缺轨迹（只有一行模糊规划）
INCOMPLETE_TRAJECTORY = [
    {"step_number": 1, "action_type": "plan", "action_detail": {
        "goal": "系统重构",
        "steps": [{"description": "重构"}],
    }, "timestamp": datetime.now(timezone.utc).isoformat()},
]


def _to_steps(raw: List[Dict]) -> List:
    from app.models.schemas import TrajectoryStep
    return [TrajectoryStep(**s) for s in raw]


async def main():
    print("=" * 72)
    print("  评估器准确性验证 - 可信度测试")
    print("=" * 72)

    from app.evaluators import PlanningEvaluator, ReplanEvaluator
    from langchain_openai import ChatOpenAI

    test_cases = [
        ("好规划",    _to_steps(GOOD_PLAN_TRAJECTORY),  "修复JWT过期Bug"),
        ("差规划",    _to_steps(BAD_PLAN_TRAJECTORY),   "部署到生产环境"),
        ("重规划场景", _to_steps(REPLAN_TRAJECTORY),     "实现搜索功能"),
        ("空轨迹",    _to_steps(EMPTY_TRAJECTORY),      "系统开发任务"),
        ("残缺轨迹",  _to_steps(INCOMPLETE_TRAJECTORY),  "系统重构"),
    ]

    use_real_llm = os.environ.get("EVAL_USE_REAL_LLM", "").lower() in ("1", "true", "yes")

    if not use_real_llm:
        print()
        print("  [!] Mock 模式 - 评估器遇到空/残缺 trajectory 时返回 0 分")
        print("  设定 EVAL_USE_REAL_LLM=1 获取真实 LLM 评分")
        print()

    for name, steps, goal in test_cases:
        print(f"\n  --- [{name}] ---")
        print(f"    轨迹步数: {len(steps)}")

        # Planning evaluator
        evaluator = PlanningEvaluator()
        try:
            result = await evaluator.evaluate(goal=goal, trajectory=steps)
            score = result.overall
            print(f"    Planning    score={score:.1f}")
            if not steps:
                print(f"      -> 预期: 0 (无轨迹), 实际: {score:.1f} {'[OK]' if score == 0 else '[!]'}")
        except Exception as e:
            print(f"    Planning    ERROR: {e}")

        # Replan evaluator (for scenarios with replan events)
        if name == "重规划场景":
            reval = ReplanEvaluator()
            try:
                r = await reval.evaluate(goal=goal, trajectory=steps)
                print(f"    Replan      score={r.overall:.1f}")
            except Exception as e:
                print(f"    Replan      ERROR: {e}")

    print()
    print("=" * 72)
    print("  验证完成")
    print("=" * 72)


if __name__ == "__main__":
    asyncio.run(main())
