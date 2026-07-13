"""
一致性 Benchmark — 测量评估器在不同条件下的评分稳定性。

定义：
  一致性 = 同一样本在重复评估中分数离散程度的下降比例。

测量流程：
  1. 使用无锚点 Prompt 对同一批轨迹重复评估 N 次 → 得到 baseline 方差
  2. 使用带锚点 Prompt（行为锚点）对同一批轨迹重复评估 N 次 → 得到 new 方差
  3. 一致性提升 = (baseline_σ² - new_σ²) / baseline_σ² × 100%

辅助指标：
  - ICC(2,1) — 绝对一致性相关系数（越接近 1 越好）
  - Spearman ρ — 样本间排序一致性
  - Mean Absolute Deviation — 同一样本多次评分的平均绝对差

用法：
  python -m scripts.benchmark_consistency
"""

import asyncio
import json
import math
import random
import statistics
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np


# ── 统计工具 ───────────────────────────────────────────────


def icc(data: List[List[float]]) -> float:
    """ICC(2,1) — 两因素随机效应模型，绝对一致性。

    data: shape=(subjects, raters)， subjects=样本数，raters=重复次数。
    """
    import numpy as np

    arr = np.array(data)
    n, k = arr.shape
    if n < 2 or k < 2:
        return 0.0

    # 总均值
    grand_mean = arr.mean()
    # 行均值（每个样本的均值）
    row_means = arr.mean(axis=1)
    # 列均值（每次评分的均值）
    col_means = arr.mean(axis=0)

    # 均方
    ms_within = ((arr - row_means[:, None] - col_means[None, :] + grand_mean) ** 2).sum() / ((n - 1) * (k - 1))
    ms_between = k * ((row_means - grand_mean) ** 2).sum() / (n - 1)

    if ms_within <= 0:
        return 0.0
    return (ms_between - ms_within) / (ms_between + (k - 1) * ms_within)


def spearman_rank(x: List[float], y: List[float]) -> float:
    """Spearman 秩相关系数。"""
    from scipy.stats import spearmanr
    if len(x) < 3 or len(y) < 3:
        return 0.0
    r, _ = spearmanr(x, y)
    return float(r) if not math.isnan(r) else 0.0


def mean_absolute_deviation(values: List[float]) -> float:
    """同一样本多次评分的平均绝对差。"""
    if len(values) < 2:
        return 0.0
    mean = statistics.mean(values)
    return statistics.mean(abs(v - mean) for v in values)


# ── 测试数据 ───────────────────────────────────────────────


@dataclass
class ConsistencySample:
    """一个测试样本，包含目标、轨迹和期望分数范围。"""
    goal: str
    trajectory: List[Dict[str, Any]]
    expected_range: tuple[float, float]  # (min, max) 合理分数区间


def _make_samples() -> List[ConsistencySample]:
    """构造 6 条覆盖不同质量水平的测试轨迹。"""
    now = datetime.now(timezone.utc).isoformat()

    def _tc(step, tool, inp=None, obs=None):
        return {
            "step_number": step,
            "action_type": "tool_call",
            "action_detail": {"tool_name": tool, "input": inp or {}},
            "observation": obs,
            "timestamp": now,
        }

    def _tr(step, tool, success=True, obs=None):
        return {
            "step_number": step,
            "action_type": "tool_result",
            "action_detail": {"tool_name": tool, "success": success},
            "observation": obs,
            "timestamp": now,
        }

    def _tk(step, thought):
        return {
            "step_number": step,
            "action_type": "think",
            "action_detail": {"thought": thought},
            "timestamp": now,
        }

    def _fail(step, msg="Error"):
        return {
            "step_number": step,
            "action_type": "failure",
            "action_detail": {"error_type": "RuntimeError", "error_message": msg},
            "timestamp": now,
        }

    def _plan(step, steps_list):
        return {
            "step_number": step,
            "action_type": "tool_call",
            "action_detail": {"tool_name": "plan", "input": {"goal": "...", "steps": steps_list}},
            "timestamp": now,
        }

    # ── 样本 1: 完美执行 ──
    s1 = ConsistencySample(
        goal="查询 Python 列表推导式的用法并给出示例",
        trajectory=[
            _plan(1, ["检索知识库", "生成回答"]),
            _tc(2, "retrieval", {"query": "Python list comprehension"}, obs=[{"title": "Python 文档", "path": "/docs/python"}]),
            _tr(3, "retrieval"),
            _tk(4, "基于检索结果生成回答"),
            _tc(5, "final_answer", {"session_id": "test"}, obs="列表推导式是 Python 中一种简洁的创建列表的方式..."),
            _tr(6, "final_answer"),
        ],
        expected_range=(70, 100),
    )

    # ── 样本 2: 工具选择错误 ──
    s2 = ConsistencySample(
        goal="删除数据库中的用户记录",
        trajectory=[
            _plan(1, ["查询用户", "执行删除"]),
            _tc(2, "retrieval", {"query": "delete user SQL"}),  # 应该直接调 CRUD，却去检索
            _tr(3, "retrieval"),
            _tc(4, "crud_delete", {"path": "/users/123"}, obs="Permission denied"),
            _tr(5, "crud_delete", success=False, obs="Permission denied"),
            _fail(6, "权限不足，删除失败"),
        ],
        expected_range=(30, 60),
    )

    # ── 样本 3: 无意义重复检索 ──
    s3 = ConsistencySample(
        goal="什么是 Python 装饰器",
        trajectory=[
            _plan(1, ["检索", "回答"]),
            _tc(2, "retrieval", {"query": "Python 装饰器"}, obs=[{"title": "Decorator 文档"}]),
            _tr(3, "retrieval"),
            _tc(4, "retrieval", {"query": "Python 装饰器 语法"}, obs=[]),  # 重复检索
            _tr(5, "retrieval"),
            _tc(6, "retrieval", {"query": "Python @ 符号"}, obs=[]),  # 再次重复
            _tr(7, "retrieval"),
            _tk(8, "回答"),
            _tc(9, "final_answer", obs="装饰器是..."),
            _tr(10, "final_answer"),
        ],
        expected_range=(40, 70),
    )

    # ── 样本 4: 幻觉 ──
    s4 = ConsistencySample(
        goal="FastAPI 如何实现依赖注入",
        trajectory=[
            _plan(1, ["检索知识库", "生成回答"]),
            _tc(2, "retrieval", {"query": "FastAPI dependency injection"}, obs=[]),  # 没检索到
            _tr(3, "retrieval"),
            _tk(4, "凭记忆回答"),  # 没有检索结果，开始编造
            _tc(5, "final_answer", obs="FastAPI 使用 @inject 装饰器实现依赖注入（这是错的）"),
            _tr(6, "final_answer"),
        ],
        expected_range=(20, 50),
    )

    # ── 样本 5: 失败后有效重规划 ──
    s5 = ConsistencySample(
        goal="更新知识库中关于 Milvus 的文档",
        trajectory=[
            _plan(1, ["搜索文档", "更新内容", "验证结果"]),
            _tc(2, "retrieval", {"query": "Milvus 文档"}, obs=[{"title": "Milvus 使用指南"}]),
            _tr(3, "retrieval"),
            _tc(4, "crud_update", {"path": "/docs/milvus.md"}, obs="Document not found"),
            _tr(5, "crud_update", success=False),
            _tc(6, "replan", {"reason": "文档不存在，尝试创建", "new_plan": "创建新文档", "trigger": "crud_update_failure"}),  # 有效重规划
            _tc(7, "crud_create", {"title": "Milvus 使用指南"}, obs="Created"),
            _tr(8, "crud_create", success=True),
        ],
        expected_range=(60, 90),
    )

    # ── 样本 6: 完全混乱 ──
    s6 = ConsistencySample(
        goal="帮我写一个快速排序",
        trajectory=[
            _plan(1, ["写代码", "测试", "优化"]),
            _tc(2, "retrieval", {"query": "快排算法"}, obs=[]),
            _tr(3, "retrieval"),
            _tc(4, "memory_write", {"key": "key_facts", "value": "用户要排序"}),  # 冗余
            _tc(5, "retrieval", {"query": "Python 排序"}, obs=[]),  # 空跑
            _tr(6, "retrieval"),
            _tc(7, "crud_create", {"title": "quick_sort.py"}, obs="Created"),
            _tr(8, "crud_create", success=True),
            _tc(9, "replan", {"reason": "忘记写内容", "new_plan": "重新写"}),  # 无意义重规划
            _tc(10, "crud_update", {"path": "/quick_sort.py"}, obs="Updated"),
            _tr(11, "crud_update", success=True),
        ],
        expected_range=(20, 50),
    )

    return [s1, s2, s3, s4, s5, s6]


# ── 两种 Prompt 策略 ───────────────────────────────────────


def _base_prompt(goal: str, trajectory_text: str) -> str:
    """无锚点基线版本 — 直接打分。"""
    return f"""评估以下 Agent 的执行质量。

任务目标：{goal}

执行轨迹：
{trajectory_text}

请从 0 到 100 给该 Agent 的整体表现打分。
只返回 JSON：
{{"overall": <0-100>, "feedback": "<简短理由>"}}"""


def _anchored_prompt(goal: str, trajectory_text: str) -> str:
    """带行为锚点版本 — 五档评分标准。"""
    return f"""评估以下 Agent 的执行质量。

任务目标：{goal}

执行轨迹：
{trajectory_text}

评分标准（行为锚点）：
- 100: 工具选择正确、参数完整、无冗余调用、结果被充分利用
- 75:  工具正确、有轻微参数或效率问题
- 50:  完成任务但存在明显冗余或部分错误
- 25:  主要工具选择错误、仅获得有限有效结果
- 0:   完全未使用必要工具或执行了危险操作

请先判断最接近哪个档位，再在该档位区间内微调。
只返回 JSON：
{{"overall": <0-100>, "anchor_tier": <0|25|50|75|100>, "feedback": "<简短理由>"}}"""


# ── 核心测量逻辑 ────────────────────────────────────────────


@dataclass
class EvalResult:
    """一次评估的输出。"""
    overall: float
    raw_response: str


async def _run_evaluations(
    samples: List[ConsistencySample],
    prompt_fn,
    repetitions: int = 5,
) -> Dict[str, List[float]]:
    """对每个样本运行 repetitions 次评估，返回分数列表。"""
    from app.evaluators.base import BaseEvaluator as _BE
    from app.evaluators.planning_evaluator import PlanningEvaluator
    from app.evaluators.trajectory_compressor import TrajectoryCompressor
    from app.models.schemas import TrajectoryStep

    compressor = TrajectoryCompressor()
    llm = PlanningEvaluator().llm  # 用具体评估器获取 LLM
    parse_json = _BE._parse_json_from_llm  # static method

    # 将 dict 轨迹转为 TrajectoryStep 对象
    def _to_steps(raw: List[dict]) -> List[TrajectoryStep]:
        return [TrajectoryStep(**s) for s in raw]

    results: Dict[str, List[float]] = {}

    for idx, sample in enumerate(samples):
        scores = []
        steps = _to_steps(sample.trajectory)
        traj_text = compressor.compress(steps)
        label = f"sample_{idx + 1}"

        for rep in range(repetitions):
            prompt = prompt_fn(sample.goal, traj_text)
            try:
                resp = await llm.ainvoke(prompt)
                content = resp.content if hasattr(resp, "content") else str(resp)
                parsed = parse_json(content)
                score = float(parsed.get("overall", 0)) if parsed else 0
            except Exception as e:
                print(f"  [{label}] rep {rep + 1} failed: {e}")
                score = 0
            scores.append(score)

        results[label] = scores
        print(f"  [{label}] {scores}")

    return results


async def main():
    print("=" * 72)
    print("  评估一致性 Benchmark")
    print("=" * 72)
    print()

    REPETITIONS = 5  # 每个样本重复次数

    samples = _make_samples()
    print(f"测试样本: {len(samples)} 条轨迹")
    print(f"重复次数: {REPETITIONS} 次/样本")
    print()

    # ── 阶段 1: 基线（无锚点） ──
    print("阶段 1/2: 基线评估（无行为锚点）...")
    t0 = time.perf_counter()
    base_results = await _run_evaluations(samples, _base_prompt, REPETITIONS)
    t1 = time.perf_counter()
    print(f"  耗时: {t1 - t0:.1f}s")
    print()

    # ── 阶段 2: 带锚点 ──
    print("阶段 2/2: 带行为锚点评估...")
    t0 = time.perf_counter()
    anchored_results = await _run_evaluations(samples, _anchored_prompt, REPETITIONS)
    t1 = time.perf_counter()
    print(f"  耗时: {t1 - t0:.1f}s")
    print()

    # ── 分析 ──
    print("=" * 72)
    print("  分析结果")
    print("=" * 72)

    all_base_mad: List[float] = []
    all_anchored_mad: List[float] = []
    base_by_sample: List[List[float]] = []
    anchored_by_sample: List[List[float]] = []
    base_means: List[float] = []
    anchored_means: List[float] = []

    print(f"\n{'样本':<12s} {'基线σ²':>10s} {'锚点σ²':>10s} {'基线MAD':>10s} {'锚点MAD':>10s} {'改善%':>8s}")
    print("-" * 62)

    for i, name in enumerate(base_results):
        base_scores = base_results[name]
        anc_scores = anchored_results[name]

        base_var = statistics.variance(base_scores) if len(base_scores) > 1 else 0
        anc_var = statistics.variance(anc_scores) if len(anc_scores) > 1 else 0
        base_mad = mean_absolute_deviation(base_scores)
        anc_mad = mean_absolute_deviation(anc_scores)

        improvement = ((base_var - anc_var) / base_var * 100) if base_var > 0 else 0

        all_base_mad.append(base_mad)
        all_anchored_mad.append(anc_mad)
        base_by_sample.append(base_scores)
        anchored_by_sample.append(anc_scores)
        base_means.append(statistics.mean(base_scores))
        anchored_means.append(statistics.mean(anc_scores))

        print(f"  {name:<10s} {base_var:>8.1f}  {anc_var:>8.1f}  {base_mad:>8.1f}  {anc_mad:>8.1f}  {improvement:>+6.1f}%")

    # ── 汇总指标 ──
    print()
    avg_base_mad = statistics.mean(all_base_mad)
    avg_anc_mad = statistics.mean(all_anchored_mad)
    mad_improvement = (avg_base_mad - avg_anc_mad) / avg_base_mad * 100 if avg_base_mad > 0 else 0

    # ICC(2,1)
    base_icc = icc(base_by_sample) if len(base_by_sample) >= 2 else 0
    anchored_icc = icc(anchored_by_sample) if len(anchored_by_sample) >= 2 else 0

    # Spearman 排序一致性（样本间的排序是否一致）
    base_spearman = spearman_rank(base_means, list(range(len(base_means))))
    anchored_spearman = spearman_rank(anchored_means, list(range(len(anchored_means))))

    print(f"\n{'=' * 62}")
    print(f"{'汇总指标':^60s}")
    print(f"{'=' * 62}")
    print(f"{'平均 MAD (基线)':30s} {avg_base_mad:<10.2f}")
    print(f"{'平均 MAD (锚点)':30s} {avg_anc_mad:<10.2f}")
    print(f"{'MAD 改善':30s} {mad_improvement:<+10.1f}%")
    print()
    print(f"{'ICC(2,1) (基线)':30s} {base_icc:<10.4f}")
    print(f"{'ICC(2,1) (锚点)':30s} {anchored_icc:<10.4f}")
    print(f"{'ICC 改善':30s} {(anchored_icc - base_icc):<+10.4f}")
    print()

    # 一致性改善 = 方差下降比例
    var_improvements = []
    for i in range(len(base_by_sample)):
        bv = statistics.variance(base_by_sample[i]) if len(base_by_sample[i]) > 1 else 0
        av = statistics.variance(anchored_by_sample[i]) if len(anchored_by_sample[i]) > 1 else 0
        if bv > 0:
            var_improvements.append((bv - av) / bv * 100)

    if var_improvements:
        print(f"{'各样本方差改善均值':30s} {statistics.mean(var_improvements):<+10.1f}%")
        print(f"{'各样本方差改善区间':30s} {min(var_improvements):<+5.1f}% ~ {max(var_improvements):<+5.1f}%")
    print()
    print(f"结论：一致性改善区间约为 {statistics.mean(var_improvements) - statistics.stdev(var_improvements):.0f}% ~ "
          f"{statistics.mean(var_improvements) + statistics.stdev(var_improvements):.0f}%（1σ）")


if __name__ == "__main__":
    asyncio.run(main())
