"""
评估器 Benchmark — 测量不同 trajectory 规模下的耗时与 token 消耗。

用法:
    python -m tests.benchmark_evaluators

需要 .env 中配置了 DEEPSEEK_API_KEY。
"""

import asyncio
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from datetime import datetime, timezone
from typing import Any, Dict, List


def _make_trajectory(num_steps: int, has_replan: bool = True) -> List[Dict[str, Any]]:
    """生成指定步数的模拟 trajectory。"""
    steps = []
    steps.append(
        {
            "step_number": 1,
            "action_type": "plan",
            "action_detail": {
                "goal": "实现用户注册与邮箱验证功能",
                "steps": [
                    {"description": "设计数据库 User 模型"},
                    {"description": "实现邮箱格式验证"},
                    {"description": "创建注册 API 端点"},
                    {"description": "编写单元测试"},
                ],
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )

    tool_calls = [
        ("search_code", {"query": "user model"}),
        ("read_file", {"file_path": "models/user.py"}),
        ("create_file", {"file_path": "services/email_verification.py", "content": "..."}),
        ("edit_file", {"file_path": "services/email_verification.py", "changes": "fix"}),
        ("run_tests", {"test_path": "tests/test_registration.py"}),
    ]

    step_num = 2
    for i in range(min(num_steps - 2, len(tool_calls) * 4)):
        idx = i % len(tool_calls)
        name, inp = tool_calls[idx]
        steps.append(
            {
                "step_number": step_num,
                "action_type": "tool_call",
                "action_detail": {"tool_name": name, "input": inp},
                "observation": f"Result from {name}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        step_num += 1
        if i % 3 == 0:
            steps.append(
                {
                    "step_number": step_num,
                    "action_type": "think",
                    "action_detail": {"thought": f"Processing step {i}..."},
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
            step_num += 1

    if has_replan:
        steps.append(
            {
                "step_number": step_num,
                "action_type": "replan",
                "action_detail": {
                    "reason": "测试失败，修复验证逻辑",
                    "new_plan": [
                        {"description": "分析失败用例"},
                        {"description": "修复 token 生成"},
                        {"description": "重新测试"},
                    ],
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    return steps


async def main():
    print("=" * 72)
    print("  评估器 Benchmark - 耗时 & 成本测量")
    print("=" * 72)

    from app.evaluators import (
        MemoryEvaluator,
        PlanningEvaluator,
        ReplanEvaluator,
        TacticalEvaluator,
        ToolUseEvaluator,
    )
    from app.models.schemas import TrajectoryStep

    evaluators_def = [
        ("Planning", PlanningEvaluator),
        ("Tactical", TacticalEvaluator),
        ("Tool Use", ToolUseEvaluator),
        ("Memory", MemoryEvaluator),
        ("Replan", ReplanEvaluator),
    ]

    scenarios = [
        ("小型 (10步)", _make_trajectory(10, has_replan=False)),
        ("中型 (25步)", _make_trajectory(25, has_replan=True)),
        ("大型 (50步)", _make_trajectory(50, has_replan=True)),
    ]

    goal = "实现用户注册与邮箱验证功能"

    for sname, raw_steps in scenarios:
        steps = [TrajectoryStep(**s) for s in raw_steps]
        print(f"\n  --- {sname} ({len(steps)} steps) ---")

        total_time = 0.0
        for dname, EvalCls in evaluators_def:
            ev = EvalCls()
            start = time.perf_counter()
            error = None
            try:
                result = await ev.evaluate(goal=goal, trajectory=steps)
                score = getattr(result, "overall", getattr(result, "score", "N/A"))
            except Exception as e:
                score = "ERR"
                error = str(e)[:60]
            elapsed = time.perf_counter() - start
            total_time += elapsed

            desc = f"score={score}" if error is None else f"ERROR: {error}"
            print(f"    {dname:<12s}  {desc:<30s}  time={elapsed:.2f}s")

        # 成本估算 (DeepSeek: ~1元/百万tokens)
        est_tokens = (2000 + len(steps) * 50) * len(evaluators_def)
        cost_yuan = est_tokens / 1_000_000 * 1.0
        cost_usd = cost_yuan / 7.2
        print(f"    {'':-<56s}")
        print(f"    {'总耗时':12s}  {total_time:.2f}s")
        print(f"    {'预估 Token':12s}  {est_tokens}")
        print(f"    {'预估成本(DS)':12s}  {cost_yuan:.4f}元 ({cost_usd:.6f}$)")
        print(f"    {'对比 GPT-4':12s}  ~{cost_yuan * 30:.4f}元 ({cost_usd * 30:.6f}$)")

    print()
    print("=" * 72)
    print("  Benchmark 完成 (实际 LLM 调用)")
    print("=" * 72)


if __name__ == "__main__":
    asyncio.run(main())
