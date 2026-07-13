"""
Trajectory 压缩管线

4 阶段压缩，减少 LLM Judge 的 token 消耗：
  ① Importance Filter — 保留高价值 action_type
  ② Think Summary — 长 think 步骤截断
  ③ Recent Window — 保留最近 N 步（plan/failure 锚点兜底）
  ④ Context Builder — 格式化输出
"""

from __future__ import annotations

from typing import List

from app.models.action_types import ActionType
from app.models.schemas import TrajectoryStep

# Importance Filter 保留的 action_type 集合
# 域事件已统一为 TOOL_CALL（按 tool_name 区分），所以只需保留基础设施事件
IMPORTANT_TYPES = {
    ActionType.TOOL_CALL,
    ActionType.TOOL_RESULT,
    ActionType.TOOL_DECISION,
    ActionType.FAILURE,
    ActionType.THINK,  # kept so stage 2 can truncate long observations
    ActionType.NODE_EXECUTE,
    ActionType.STATE_CHANGE,
}

# Recent Window 外也必须保留的锚点类型
ANCHOR_TYPES = {
    ActionType.FAILURE,
}

# Think 步骤 observation 截断长度
THINK_OBS_MAX_CHARS = 200


class TrajectoryCompressor:
    """Trajectory 压缩器 — 4 阶段管线。"""

    def __init__(self, recent_window: int = 30):
        self.recent_window = recent_window

    def compress(self, trajectory: List[TrajectoryStep]) -> str:
        """执行完整 4 阶段压缩，返回格式化文本。"""
        if not trajectory:
            return "No trajectory steps."

        total = len(trajectory)

        # ① Importance Filter
        steps = self._importance_filter(trajectory)

        # ② Think Summary（截断长 observation）
        steps = self._summarize_thinks(steps)

        # ③ Recent Window
        steps, omitted_count = self._recent_window(steps)

        # ④ Context Builder
        text = self._build_context(steps, total, omitted_count)
        return text

    # ── Stage ① ──────────────────────────────────────────────

    @staticmethod
    def _importance_filter(
        trajectory: List[TrajectoryStep],
    ) -> List[TrajectoryStep]:
        """保留高价值 action_type，丢弃噪声步骤。"""
        return [s for s in trajectory if s.action_type in IMPORTANT_TYPES]

    # ── Stage ② ──────────────────────────────────────────────

    @staticmethod
    def _summarize_thinks(
        steps: List[TrajectoryStep],
    ) -> List[TrajectoryStep]:
        """对 think 类型步骤的 observation 做截断（不调 LLM）。"""
        result = []
        for step in steps:
            if step.action_type == ActionType.THINK and step.observation:
                if len(step.observation) > THINK_OBS_MAX_CHARS:
                    # 创建浅拷贝避免修改原始对象
                    truncated_obs = step.observation[:THINK_OBS_MAX_CHARS] + " [... summarized]"
                    step = _copy_step_with(step, observation=truncated_obs)
            result.append(step)
        return result

    # ── Stage ③ ──────────────────────────────────────────────

    def _recent_window(
        self,
        steps: List[TrajectoryStep],
    ) -> tuple[List[TrajectoryStep], int]:
        """保留最近 N 步 + 锚点步骤（plan/failure），返回 (steps, omitted_count)。"""
        if len(steps) <= self.recent_window:
            return steps, 0

        window_start = len(steps) - self.recent_window
        recent = steps[window_start:]
        earlier = steps[:window_start]

        # 从被丢弃的前部提取锚点
        anchors = [s for s in earlier if s.action_type in ANCHOR_TYPES]

        omitted_count = len(earlier) - len(anchors)
        combined = anchors + recent
        return combined, omitted_count

    # ── Stage ④ ──────────────────────────────────────────────

    @staticmethod
    def _build_context(
        steps: List[TrajectoryStep],
        total: int,
        omitted_count: int,
    ) -> str:
        """格式化压缩后的 trajectory 文本。"""
        lines = []

        # 统计头
        header = f"[Trajectory: {total} steps total"
        if omitted_count > 0:
            header += f", {omitted_count} earlier steps omitted"
        header += f", showing {len(steps)} steps]"
        lines.append(header)
        lines.append("")

        # 格式化每个 step
        for step in steps:
            lines.append(f"Step {step.step_number} [{step.action_type}]:")
            lines.append(f"  Action: {step.action_detail}")
            if step.observation:
                lines.append(f"  Observation: {step.observation}")
            lines.append("")

        return "\n".join(lines)


def _copy_step_with(step: TrajectoryStep, **overrides) -> TrajectoryStep:
    """浅拷贝 TrajectoryStep，替换指定字段。"""
    data = {
        "step_number": step.step_number,
        "action_type": step.action_type,
        "action_detail": step.action_detail,
        "observation": step.observation,
        "timestamp": step.timestamp,
    }
    data.update(overrides)
    return TrajectoryStep(**data)
