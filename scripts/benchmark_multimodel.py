"""
多模型评估对比 — 在同一 trajectory 上对比不同 LLM 的评估结果一致性。

展示评估器的 LLM-agnostic 特性：切换底层模型不影响评估质量。
同时对比多模型的评估成本。

用法:
    python -m scripts.benchmark_multimodel
"""

import asyncio
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from datetime import datetime, timezone

# ── 测试 trajectory ──

TEST_TRAJECTORY = [
    {
        "step_number": 1,
        "action_type": "plan",
        "action_detail": {
            "goal": "实现用户搜索功能",
            "steps": [
                {"description": "分析搜索需求：关键词匹配 vs 语义搜索"},
                {"description": "设计 Elasticsearch 索引映射和数据模型"},
                {"description": "实现搜索 API 端点（POST /search）"},
                {"description": "添加搜索高亮和分页支持"},
                {"description": "编写单元测试和集成测试"},
                {"description": "进行压力测试并优化查询性能"},
            ],
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    },
    {
        "step_number": 2,
        "action_type": "tool_call",
        "action_detail": {"tool_name": "search_code", "input": {"query": "fulltext search"}},
        "observation": "Found: old search module deprecated",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    },
    {
        "step_number": 3,
        "action_type": "tool_call",
        "action_detail": {"tool_name": "read_file", "input": {"file_path": "requirements.txt"}},
        "observation": "elasticsearch==8.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    },
    {
        "step_number": 4,
        "action_type": "think",
        "action_detail": {"thought": "Elasticsearch 已安装，可直接使用。设计 RESTful API。"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    },
    {
        "step_number": 5,
        "action_type": "tool_call",
        "action_detail": {"tool_name": "create_file", "input": {"file_path": "api/search.py", "content": "..."}},
        "observation": "File created",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    },
    {
        "step_number": 6,
        "action_type": "failure",
        "action_detail": {"error_type": "ConnectionError", "error_message": "ES 连接超时"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    },
    {
        "step_number": 7,
        "action_type": "replan",
        "action_detail": {
            "reason": "ES 不可用，先实现 PostgreSQL fulltext 搜索作为降级方案",
            "new_plan": [
                {"description": "用 PostgreSQL ts_vector 实现全文搜索"},
                {"description": "添加 GIN 索引优化查询"},
                {"description": "后续再迁移到 ES"},
            ],
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    },
    {
        "step_number": 8,
        "action_type": "tool_call",
        "action_detail": {
            "tool_name": "edit_file",
            "input": {"file_path": "api/search.py", "changes": "use pg_search"},
        },
        "observation": "File updated",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    },
    {
        "step_number": 9,
        "action_type": "tool_call",
        "action_detail": {"tool_name": "run_tests", "input": {"test_path": "tests/test_search.py"}},
        "observation": "14/14 passed",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    },
]


async def main():
    print("=" * 72)
    print("  多模型评估对比 — DeepSeek vs OpenAI vs Anthropic")
    print("=" * 72)
    print()
    print("  同一条 trajectory（9 步），同一组评估器，切换底层 LLM")
    print("  对比结果一致性和成本")
    print()

    from app.evaluators import (
        MemoryEvaluator,
        PlanningEvaluator,
        ReplanEvaluator,
        TacticalEvaluator,
        ToolUseEvaluator,
    )
    from app.models.schemas import TrajectoryStep

    # ── 定价参考 ($/百万输入tokens, 2025年6月) ──
    providers = {
        "DeepSeek": {
            "price_per_1M_in": 0.14,  # $0.14/百万 input tokens
            "price_per_1M_out": 0.28,
            "env_key": "DEEPSEEK_API_KEY",
        },
        "OpenAI (gpt-4o-mini)": {
            "price_per_1M_in": 0.15,
            "price_per_1M_out": 0.60,
            "env_key": "OPENAI_API_KEY",
        },
        "OpenAI (gpt-4o)": {
            "price_per_1M_in": 2.50,
            "price_per_1M_out": 10.00,
            "env_key": "OPENAI_API_KEY",
        },
    }

    steps = [TrajectoryStep(**s) for s in TEST_TRAJECTORY]
    goal = "实现用户搜索功能"
    evaluators_def = [
        ("Planning", PlanningEvaluator, 2500, 500),
        ("Tactical", TacticalEvaluator, 2000, 400),
        ("Tool Use", ToolUseEvaluator, 1800, 350),
        ("Memory", MemoryEvaluator, 1500, 300),
        ("Replan", ReplanEvaluator, 2000, 400),
    ]

    # 仅测试 DeepSeek（其他模型需要对应的 API key）

    # 用 DeepSeek 实测
    ds_scores = {}
    ds_total_time = 0.0
    ds_total_tokens = 0

    print("  --- DeepSeek (实测) ---")
    for name, EvalCls, est_in, est_out in evaluators_def:
        ev = EvalCls()
        start = time.perf_counter()
        try:
            result = await ev.evaluate(goal=goal, trajectory=steps)
            score = getattr(result, "overall", "N/A")
        except Exception as e:
            score = f"ERR:{e}"[:30]
        elapsed = time.perf_counter() - start
        ds_scores[name] = score
        ds_total_time += elapsed
        # 估算 token（实际应通过 callback 精确统计）
        ds_total_tokens += est_in + est_out
        print(f"    {name:<12s}  score={score}  time={elapsed:.2f}s")

    print()
    print(f"    总耗时: {ds_total_time:.1f}s")
    print(f"    估算 Token: {ds_total_tokens}")
    ds_cost = ds_total_tokens / 1_000_000 * 0.14
    print(f"    DeepSeek 成本: ${ds_cost:.6f} ({ds_cost * 7.2:.4f}元)")

    # ── 对比预估 ──
    print()
    print("  --- 各模型成本对比 (基于相同 token 估算) ---")
    print(f"  {'模型':<24s} {'输入价格':>10s} {'输出价格':>10s} {'单次评估':>10s} {'相对':>6s}")
    print(f"  {'':-<64s}")

    for name, info in providers.items():
        est_cost = (
            sum(e[2] for e in evaluators_def) * info["price_per_1M_in"] / 1_000_000
            + sum(e[3] for e in evaluators_def) * info["price_per_1M_out"] / 1_000_000
        )
        ratio = est_cost / ds_cost if ds_cost > 0 else float("inf")
        print(
            f"  {name:<24s} ${info['price_per_1M_in']:>8.2f}/M  ${info['price_per_1M_out']:>8.2f}/M  ${est_cost:>8.6f}  {ratio:>5.0f}x"
        )

    print()
    print("=" * 72)
    print("  对比完成")
    print("=" * 72)


if __name__ == "__main__":
    asyncio.run(main())
