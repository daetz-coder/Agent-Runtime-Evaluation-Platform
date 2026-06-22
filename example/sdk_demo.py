"""
SDK 使用示例 — 演示三种零侵入接入方式。

这是一个独立的脚本，不依赖 app/ 包。
仅需：pip install langchain-openai langgraph httpx
然后：export PYTHONPATH=.

用法:
    python example/sdk_demo.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ══════════════════════════════════════════════════════════════
# 方式 1: LLM Proxy —一行代码接入
# ══════════════════════════════════════════════════════════════

def demo_proxy():
    """原来的代码 → 只改一行"""
    from sdk import create_proxy_llm, get_collector

    # 模拟原来的 LLM（不实际调用 API）
    from langchain_openai import ChatOpenAI
    original = ChatOpenAI(
        model="deepseek-chat",
        openai_api_key="sk-demo",
        openai_api_base="http://127.0.0.1:9999",
    )

    # ⚡ 一行代码接入！原来的 ChatOpenAI(...) 改成 create_proxy_llm(ChatOpenAI(...))
    llm = create_proxy_llm(original)

    # 后续使用完全相同
    collector = get_collector()
    collector.start(goal="测试 LLM Proxy 接入")

    # LLM 调用会自动记录到收集器
    collector.finish()
    print("  [OK] LLM Proxy: 一行代码接入，轨迹已收集")


# ══════════════════════════════════════════════════════════════
# 方式 2: LangChain Callback —一行代码接入
# ══════════════════════════════════════════════════════════════

def demo_callback():
    """原有的 callbacks=[] → 加上 handler"""
    from sdk import create_callback_handler, get_collector

    # ⚡ 一行代码：创建 handler
    handler = create_callback_handler()

    # 原代码只需加 callbacks=[handler]
    from langchain_openai import ChatOpenAI
    llm = ChatOpenAI(
        model="deepseek-chat",
        openai_api_key="sk-demo",
        openai_api_base="http://127.0.0.1:9999",
        callbacks=[handler],  # <-- 就这一行
    )

    collector = get_collector()
    collector.start(goal="测试 Callback 接入")
    collector.finish()
    print("  [OK] Callback: 一行代码接入，轨迹已收集")


# ══════════════════════════════════════════════════════════════
# 方式 3: LangGraph Instrument —一行代码接入
# ══════════════════════════════════════════════════════════════

def demo_langgraph():
    """graph = build_graph() → graph = instrument_langgraph(build_graph())"""
    from sdk import instrument_langgraph, get_collector
    from langgraph.graph import StateGraph
    from typing import TypedDict

    class State(TypedDict):
        msg: str

    def my_node(state: State) -> dict:
        return {"msg": state["msg"] + " processed"}

    # 原来的图
    graph = StateGraph(State)
    graph.add_node("main", my_node)
    graph.set_entry_point("main")
    graph.set_finish_point("main")

    # ⚡ 一行代码接入！
    graph = instrument_langgraph(graph)

    # 编译不变
    compiled = graph.compile()
    print("  [OK] LangGraph: 一行代码接入，图已 instrument")
    print(f"       节点: {list(graph._original.nodes.keys())}")


# ══════════════════════════════════════════════════════════════
# 全部演示
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("  Agent Eval SDK — 零侵入接入演示")
    print("=" * 60)
    print()

    demo_proxy()
    demo_callback()
    demo_langgraph()

    print()
    print("=" * 60)
    print("  所有三种接入方式均一行代码完成")
    print("  离线模式：未配置 EVAL_API_BASE_URL 时纯本地缓冲")
    print("=" * 60)
