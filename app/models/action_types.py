"""
Action Type 常量定义

统一管理所有 trajectory 记录的 action_type，避免硬编码字符串。
"""


class ActionType:
    """轨迹记录的动作类型常量。"""

    # ── Planner 输出 ──────────────────────────────────────────
    PLAN = "plan"                      # 初始规划（milestones / steps）
    PLAN_UPDATE = "plan_update"        # 动态规划更新（milestone 完成、下一步调整）

    # ── 工具调用 ─────────────────────────────────────────────
    TOOL_CALL = "tool_call"            # 工具调用（含工具名、输入参数）
    TOOL_RESULT = "tool_result"        # 工具返回（独立记录工具输出）

    # ── 记忆读写 ─────────────────────────────────────────────
    MEMORY_WRITE = "memory_write"      # 记忆写入（存入新信息）
    MEMORY_READ = "memory_read"        # 记忆读取（检索已有信息）

    # ── 状态变化 ─────────────────────────────────────────────
    STATE_CHANGE = "state_change"      # 状态变化（含 before/after diff）

    # ── 思考与决策 ───────────────────────────────────────────
    THINK = "think"                    # 思考过程（推理、分析）
    REPLAN = "replan"                  # 重规划（修改原有计划）

    # ── 异常事件 ─────────────────────────────────────────────
    FAILURE = "failure"                # 失败/异常事件

    # ── 节点执行 ─────────────────────────────────────────────
    NODE_EXECUTE = "node_execute"      # 节点执行（LangGraph 节点）
    TOOL_DECISION = "tool_decision"    # 工具选择决策（LLM 决定调用哪个工具）

    # ── 知识检索与证据构建 ──────────────────────────────────
    RETRIEVAL = "retrieval"            # 知识库检索（retrieved_docs：检索到的文档列表）
    EVIDENCE = "evidence"              # 证据池构建（最终送给 LLM 的完整证据）

    # 所有合法类型集合（用于校验）
    ALL_TYPES = {
        PLAN, PLAN_UPDATE,
        TOOL_CALL, TOOL_RESULT,
        MEMORY_WRITE, MEMORY_READ,
        STATE_CHANGE,
        THINK, REPLAN,
        FAILURE,
        NODE_EXECUTE, TOOL_DECISION,
        RETRIEVAL, EVIDENCE,
    }
