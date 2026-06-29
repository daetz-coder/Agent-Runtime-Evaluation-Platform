"""
多轨迹评估分布 — 不同质量 trajectory 的评分分布、维度相关性、一致性验证。

用 6 条精心设计的不同质量 trajectory 跑全部 6 个评估器，
输出分维度统计（mean/std/min/max）和维度间 Pearson 相关性矩阵。

用法:
    python -m scripts.benchmark_score_distribution
"""

import asyncio
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from datetime import datetime, timezone
from typing import Dict, List

# ══════════════════════════════════════════════════════════
# 6 条不同质量的 trajectory
# ══════════════════════════════════════════════════════════


def _ts():
    return datetime.now(timezone.utc).isoformat()


# ── 优秀轨迹：完整规划 + 充分工具调用 + 测试通过 + 记忆使用 ──
TRAJ_EXCELLENT = [
    {
        "step_number": 1,
        "action_type": "plan",
        "action_detail": {
            "goal": "实现用户 OAuth2.0 登录",
            "steps": [
                {"description": "调研 OAuth2.0 规范，确定授权码模式"},
                {"description": "设计 User/OAuthToken 数据库模型"},
                {"description": "实现 /auth/login、/auth/callback、/auth/refresh 三个端点"},
                {"description": "集成 Google/GitHub 第三方登录"},
                {"description": "编写单元测试覆盖授权流程"},
                {"description": "添加 rate limiting 防暴力破解"},
                {"description": "编写集成测试 + 安全审计"},
            ],
        },
        "timestamp": _ts(),
    },
    {
        "step_number": 2,
        "action_type": "tool_call",
        "action_detail": {"tool_name": "search_code", "input": {"query": "OAuth"}},
        "observation": "Found: auth module skeleton",
        "timestamp": _ts(),
    },
    {
        "step_number": 3,
        "action_type": "memory_write",
        "action_detail": {
            "key": "oauth_flow",
            "value": "授权码模式: 1)请求code 2)换取token 3)刷新token",
            "source": "research",
        },
        "timestamp": _ts(),
    },
    {
        "step_number": 4,
        "action_type": "tool_call",
        "action_detail": {"tool_name": "create_file", "input": {"file_path": "models/oauth.py"}},
        "observation": "Created",
        "timestamp": _ts(),
    },
    {
        "step_number": 5,
        "action_type": "tool_call",
        "action_detail": {"tool_name": "create_file", "input": {"file_path": "api/auth.py"}},
        "observation": "Created",
        "timestamp": _ts(),
    },
    {
        "step_number": 6,
        "action_type": "think",
        "action_detail": {"thought": "OAuth 基础框架已完成，接下来实现 Google OAuth 集成"},
        "timestamp": _ts(),
    },
    {
        "step_number": 7,
        "action_type": "memory_read",
        "action_detail": {"key": "oauth_flow", "context": "implementing Google OAuth"},
        "timestamp": _ts(),
    },
    {
        "step_number": 8,
        "action_type": "tool_call",
        "action_detail": {"tool_name": "create_file", "input": {"file_path": "services/oauth_google.py"}},
        "observation": "Created with Google OAuth2 client",
        "timestamp": _ts(),
    },
    {
        "step_number": 9,
        "action_type": "tool_call",
        "action_detail": {"tool_name": "run_tests", "input": {"test_path": "tests/test_auth.py"}},
        "observation": "22/22 passed",
        "timestamp": _ts(),
    },
    {
        "step_number": 10,
        "action_type": "tool_call",
        "action_detail": {"tool_name": "run_tests", "input": {"test_path": "tests/test_integration.py"}},
        "observation": "8/8 passed",
        "timestamp": _ts(),
    },
]

# ── 良好轨迹：合理规划但工具使用有冗余 ──
TRAJ_GOOD = [
    {
        "step_number": 1,
        "action_type": "plan",
        "action_detail": {
            "goal": "添加邮件通知功能",
            "steps": [
                {"description": "集成 SMTP 邮件服务"},
                {"description": "创建邮件模板（注册确认、密码重置）"},
                {"description": "添加异步邮件队列"},
                {"description": "编写测试"},
            ],
        },
        "timestamp": _ts(),
    },
    {
        "step_number": 2,
        "action_type": "tool_call",
        "action_detail": {"tool_name": "search_code", "input": {"query": "email"}},
        "observation": "No existing email code",
        "timestamp": _ts(),
    },
    {
        "step_number": 3,
        "action_type": "tool_call",
        "action_detail": {"tool_name": "read_file", "input": {"file_path": "config/settings.py"}},
        "observation": "SMTP_HOST not configured",
        "timestamp": _ts(),
    },
    {
        "step_number": 4,
        "action_type": "tool_call",
        "action_detail": {
            "tool_name": "edit_file",
            "input": {"file_path": "config/settings.py", "changes": "add SMTP config"},
        },
        "observation": "Updated",
        "timestamp": _ts(),
    },
    {
        "step_number": 5,
        "action_type": "tool_call",
        "action_detail": {"tool_name": "create_file", "input": {"file_path": "services/email.py"}},
        "observation": "Created",
        "timestamp": _ts(),
    },
    {
        "step_number": 6,
        "action_type": "tool_call",
        "action_detail": {"tool_name": "create_file", "input": {"file_path": "templates/email/"}},
        "observation": "Created templates",
        "timestamp": _ts(),
    },
    {
        "step_number": 7,
        "action_type": "tool_call",
        "action_detail": {"tool_name": "run_tests", "input": {"test_path": "tests/test_email.py"}},
        "observation": "3/5 passed, 2 failed: template rendering error",
        "timestamp": _ts(),
    },
    {
        "step_number": 8,
        "action_type": "tool_call",
        "action_detail": {
            "tool_name": "edit_file",
            "input": {"file_path": "templates/email/confirm.html", "changes": "fix template"},
        },
        "observation": "Fixed",
        "timestamp": _ts(),
    },
    {
        "step_number": 9,
        "action_type": "tool_call",
        "action_detail": {"tool_name": "run_tests", "input": {"test_path": "tests/test_email.py"}},
        "observation": "5/5 passed",
        "timestamp": _ts(),
    },
]

# ── 中等轨迹：有规划但步骤粗糙 ──
TRAJ_MODERATE = [
    {
        "step_number": 1,
        "action_type": "plan",
        "action_detail": {
            "goal": "数据库迁移",
            "steps": [
                {"description": "备份数据库"},
                {"description": "执行迁移"},
                {"description": "验证"},
            ],
        },
        "timestamp": _ts(),
    },
    {
        "step_number": 2,
        "action_type": "tool_call",
        "action_detail": {"tool_name": "run_command", "input": {"cmd": "pg_dump"}},
        "observation": "Backup complete",
        "timestamp": _ts(),
    },
    {
        "step_number": 3,
        "action_type": "tool_call",
        "action_detail": {"tool_name": "run_command", "input": {"cmd": "alembic upgrade head"}},
        "observation": "Migration applied",
        "timestamp": _ts(),
    },
    {
        "step_number": 4,
        "action_type": "tool_call",
        "action_detail": {"tool_name": "run_command", "input": {"cmd": "python check_db.py"}},
        "observation": "All tables present",
        "timestamp": _ts(),
    },
]

# ── 差轨迹：无规划直接操作 ──
TRAJ_POOR = [
    {
        "step_number": 1,
        "action_type": "tool_call",
        "action_detail": {"tool_name": "edit_file", "input": {"file_path": "prod_config.py", "changes": "DB_HOST=..."}},
        "observation": "File changed",
        "timestamp": _ts(),
    },
    {
        "step_number": 2,
        "action_type": "tool_call",
        "action_detail": {"tool_name": "run_command", "input": {"cmd": "restart service"}},
        "observation": "Service down",
        "timestamp": _ts(),
    },
    {
        "step_number": 3,
        "action_type": "failure",
        "action_detail": {"error_type": "RuntimeError", "error_message": "DB connection refused, wrong host"},
        "timestamp": _ts(),
    },
]

# ── 空轨迹 ──
TRAJ_EMPTY = []

# ── 对抗轨迹：大量 tool_call 但无规划、无思考 ──
TRAJ_ADVERSARIAL = [
    {
        "step_number": i,
        "action_type": "tool_call",
        "action_detail": {"tool_name": f"tool_{i}", "input": {}},
        "observation": f"Output {i}",
        "timestamp": _ts(),
    }
    for i in range(1, 16)
]

ALL_TRAJECTORIES = {
    "优秀": TRAJ_EXCELLENT,
    "良好": TRAJ_GOOD,
    "中等": TRAJ_MODERATE,
    "差": TRAJ_POOR,
    "空": TRAJ_EMPTY,
    "对抗": TRAJ_ADVERSARIAL,
}

GOAL_BY_LEVEL = {
    "优秀": "实现用户 OAuth2.0 登录",
    "良好": "添加邮件通知功能",
    "中等": "数据库迁移",
    "差": "修改生产配置",
    "空": "未知任务",
    "对抗": "未知任务",
}


# ══════════════════════════════════════════════════════════
# 统计工具
# ══════════════════════════════════════════════════════════


def pearson_r(xs: List[float], ys: List[float]) -> float:
    """Pearson 相关系数。"""
    n = len(xs)
    if n < 3:
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    sx = sum((x - mx) ** 2 for x in xs) ** 0.5
    sy = sum((y - my) ** 2 for y in ys) ** 0.5
    if sx == 0 or sy == 0:
        return 0.0
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy)


# ══════════════════════════════════════════════════════════


async def main():
    print("=" * 72)
    print("  多轨迹评估分布 — 6 条轨迹 × 6 个评估器")
    print("=" * 72)

    from app.evaluators import (
        MemoryEvaluator,
        PlanningEvaluator,
        ReplanEvaluator,
        RetrievalEvaluator,
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
        ("Retrieval", RetrievalEvaluator),
    ]

    # ── 逐轨迹评估 ──
    all_scores: Dict[str, Dict[str, float]] = {}  # {level: {dim: score}}

    for level, raw_steps in ALL_TRAJECTORIES.items():
        steps = [TrajectoryStep(**s) for s in raw_steps]
        goal = GOAL_BY_LEVEL[level]
        print(f"\n  --- [{level}] {len(steps)} steps, goal={goal[:30]} ---")

        scores = {}
        for dim_name, EvalCls in evaluators_def:
            ev = EvalCls()
            start = time.perf_counter()
            try:
                result = await ev.evaluate(goal=goal, trajectory=steps)
                score = getattr(result, "overall", 0)
            except Exception:
                score = 0
            elapsed = time.perf_counter() - start
            scores[dim_name] = score
            print(f"    {dim_name:<12s} {score:>6.1f}  ({elapsed:.1f}s)")
        all_scores[level] = scores

    # ── 分维度统计 ──
    print()
    print("=" * 72)
    print("  分维度统计 (mean ± std  [min–max])")
    print("=" * 72)

    dims = [d[0] for d in evaluators_def]
    for dim in dims:
        vals = [all_scores[lvl][dim] for lvl in ALL_TRAJECTORIES]
        n = len(vals)
        mean = sum(vals) / n
        std = (sum((v - mean) ** 2 for v in vals) / n) ** 0.5
        print(f"  {dim:<12s} {mean:>5.1f} ±{std:>5.1f}  [{min(vals):>5.1f} – {max(vals):>5.1f}]")

    # ── 等级排序检查（优秀 > 良好 > 中等 > 差） ──
    print()
    print("=" * 72)
    print("  单调性检查（综合分应随质量递减）")
    print("=" * 72)
    quality_order = ["优秀", "良好", "中等", "差", "对抗", "空"]
    prev = None
    monotonic = True
    for level in quality_order:
        if level in all_scores:
            avg = sum(all_scores[level].values()) / len(dims)
            arrow = ""
            if prev is not None:
                arrow = " ✓" if avg <= prev else " ✗"
                if avg > prev:
                    monotonic = False
            print(f"  {level:<6s}  综合 {avg:5.1f}{arrow}")
            prev = avg

    # ── 维度间 Pearson 相关性矩阵 ──
    print()
    print("=" * 72)
    print("  维度间 Pearson 相关性矩阵")
    print("=" * 72)

    scores_by_dim = {dim: [all_scores[lvl][dim] for lvl in ALL_TRAJECTORIES] for dim in dims}

    # Header
    header = "  " + "".join(f"{d:>10s}" for d in dims)
    print(header)

    for d1 in dims:
        row = f"  {d1:<10s}"
        for d2 in dims:
            if d1 == d2:
                row += "     1.00 "
            else:
                r = pearson_r(scores_by_dim[d1], scores_by_dim[d2])
                row += f"{r:>9.3f} "
        print(row)

    print()
    print("=" * 72)
    if monotonic:
        print("  ✓ 评分单调递减，评估器有效区分不同质量等级")
    else:
        print("  ✗ 存在单调性违规")
    print("=" * 72)


if __name__ == "__main__":
    asyncio.run(main())
