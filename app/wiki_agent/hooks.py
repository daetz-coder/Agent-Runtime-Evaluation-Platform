"""wiki-agent 生命周期钩子 — 委托给 SDK TrajectoryCollector。

wiki-agent 业务代码通过此模块的 emit_* 函数触发评估事件。
SDK 不可用或 EVAL_ENABLED=false 时自动降级为空操作。
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# 尝试导入 SDK collector，不可用时降级为空操作
try:
    from sdk.collector import ActionType, get_collector

    def _get_collector():
        return get_collector()

    _HAS_SDK = True
except ImportError:
    _HAS_SDK = False
    logger.info("[Wiki Agent] sdk not installed — evaluation hooks disabled")

    def _get_collector():
        return None


# ── 通用层 ─────────────────────────────────────────


async def emit_trace(
    action: str,
    input: dict[str, Any] | None = None,
    output: dict[str, Any] | None = None,
    duration_ms: float | None = None,
    meta: dict[str, Any] | None = None,
) -> None:
    """通用追踪记录。"""
    collector = _get_collector()
    if collector is None or not collector.enabled:
        return
    try:
        detail: dict[str, Any] = {}
        if input:
            detail["input"] = input
        if output:
            detail["output"] = output
        if duration_ms is not None:
            detail["duration_ms"] = duration_ms
        if meta:
            detail["meta"] = meta
        collector.record(action, detail)
    except Exception as e:
        logger.debug("[Wiki Agent] emit_trace error: %s", e)


async def emit_step(name: str, detail: str = "", status: str = "ok") -> None:
    """步骤记录。"""
    collector = _get_collector()
    if collector is None or not collector.enabled:
        return
    try:
        collector.record_think(f"[{status}] {name}: {detail}" if detail else f"[{status}] {name}")
    except Exception as e:
        logger.debug("[Wiki Agent] emit_step error: %s", e)


# ── 结构化层（wiki-agent graph.py 使用）──────────────


async def emit_session_start(goal: str, session_id: str, context: dict) -> None:
    """会话开始 — 创建评估任务。"""
    collector = _get_collector()
    if collector is None or not collector.enabled:
        return
    try:
        await collector.start_async(goal, context)
        logger.debug("[Wiki Agent] eval session started for: %s", session_id)
    except Exception as e:
        logger.debug("[Wiki Agent] emit_session_start error: %s", e)


async def emit_retrieval(query: str, results: list[dict], duration_ms: float) -> None:
    """记录检索事件。"""
    collector = _get_collector()
    if collector is None or not collector.enabled:
        return
    try:
        collector.record_retrieval(query, results, duration_ms=duration_ms)
    except Exception as e:
        logger.debug("[Wiki Agent] emit_retrieval error: %s", e)


async def emit_key_facts(facts: list[str]) -> None:
    """记录从对话中提取的关键事实。"""
    collector = _get_collector()
    if collector is None or not collector.enabled:
        return
    try:
        collector.record_memory_write("key_facts", facts, source="llm_extraction", memory_type="fact")
    except Exception as e:
        logger.debug("[Wiki Agent] emit_key_facts error: %s", e)


async def emit_response(session_id: str, response: str) -> None:
    """记录最终回复。"""
    collector = _get_collector()
    if collector is None or not collector.enabled:
        return
    try:
        collector.record(
            ActionType.EVIDENCE,
            {"final_response": response[:4000], "session_id": session_id},
        )
    except Exception as e:
        logger.debug("[Wiki Agent] emit_response error: %s", e)


async def emit_session_end(session_id: str) -> None:
    """会话结束 — flush 轨迹并触发评估。"""
    collector = _get_collector()
    if collector is None or not collector.enabled:
        return
    try:
        await collector.finish_async(auto_run=True)
        logger.debug("[Wiki Agent] eval session ended for: %s", session_id)
    except Exception as e:
        logger.debug("[Wiki Agent] emit_session_end error: %s", e)
