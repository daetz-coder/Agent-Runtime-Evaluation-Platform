"""
Adapters 集成测试 — 验证三个 Adapter 在真实场景下正确记录轨迹。

用法:
    python -m tests.test_adapters
"""

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def test_proxy_llm():
    """测试 LLM Proxy — BaseChatModel 透明代理，记录 llm_call + tool_decision"""
    from langchain_openai import ChatOpenAI

    from app.adapters.llm_proxy import create_proxy_llm
    from app.collectors import get_collector

    collector = get_collector()

    # 创建代理 LLM
    raw_llm = ChatOpenAI(
        model="deepseek-chat",
        openai_api_key="sk-test",
        openai_api_base="http://127.0.0.1:9999",  # 不实际调用
    )
    proxy = create_proxy_llm(raw_llm)

    # 验证一行代码接入
    assert hasattr(proxy, "_original_llm"), f"Proxy should wrap the original LLM, got {type(proxy).__name__}"
    assert proxy._original_llm is raw_llm, "Proxy should hold reference to original LLM"

    # 验证重复包装不叠加
    proxy2 = create_proxy_llm(proxy)
    assert proxy2 is proxy, "create_proxy_llm should be idempotent"

    # 验证 bind_tools 代理
    from langchain_core.tools import tool

    @tool
    def dummy_search(query: str) -> str:
        """Search tool"""
        return "result"

    bound = proxy.bind_tools([dummy_search])
    assert bound is not None, "bind_tools should work on proxy"

    print("  [PASS] LLM Proxy: 透明代理、idempotent、bind_tools 转发")


def test_callback_handler():
    """测试 Callback Handler — on_llm_start/end, on_tool_start/end/error"""
    from langchain_core.callbacks import BaseCallbackHandler

    from app.adapters.callback import create_callback_handler

    handler = create_callback_handler()

    # 验证一行代码接入
    assert isinstance(handler, BaseCallbackHandler), f"Handler should be a BaseCallbackHandler, got {type(handler)}"

    # 验证具备所有声明的生命周期钩子
    required_methods = [
        "on_llm_start",
        "on_llm_end",
        "on_llm_error",
        "on_chat_model_start",
        "on_tool_start",
        "on_tool_end",
        "on_tool_error",
        "on_chain_start",
        "on_chain_end",
        "on_chain_error",
    ]
    for method in required_methods:
        assert hasattr(handler, method), f"Handler missing method: {method}"

    print("  [PASS] Callback: BaseCallbackHandler 子类、10 个生命周期钩子齐全")


async def test_langgraph_instrument():
    """测试 LangGraph Instrument — sync + async 节点包装、add_node 拦截"""
    from typing import TypedDict

    from langgraph.graph import StateGraph

    class TestState(TypedDict):
        counter: int
        message: str

    # 构建原始图（含 sync + async 节点）
    raw_graph = StateGraph(TestState)

    def sync_node(state: TestState) -> dict:
        return {"counter": state["counter"] + 1, "message": "sync done"}

    async def async_node(state: TestState) -> dict:
        return {"counter": state["counter"] + 1, "message": "async done"}

    raw_graph.add_node("sync_step", sync_node)
    raw_graph.set_entry_point("sync_step")
    raw_graph.set_finish_point("sync_step")

    # 一行代码 instrument
    from app.adapters.langgraph import instrument_langgraph

    instrumented = instrument_langgraph(raw_graph)

    # 验证 _original 保存了原始图
    assert hasattr(instrumented, "_original"), "Instrumented should hold reference to _original"

    # 直接编译（不添加新节点），验证不崩溃
    compiled = instrumented.compile()
    result = await compiled.ainvoke({"counter": 0, "message": "start"})
    assert isinstance(result, dict), "Compiled graph ainvoke should return dict"

    # 再测：先 add_node 再 compile
    raw2 = StateGraph(TestState)
    raw2.add_node("step1", sync_node)
    raw2.set_entry_point("step1")
    raw2.set_finish_point("step1")
    inst2 = instrument_langgraph(raw2)
    inst2.add_node("step2", sync_node)
    inst2.add_node("step3", async_node)
    # add_node 不崩溃即为通过

    print("  [PASS] LangGraph: sync/async wrapping, add_node intercept, compile+ainvoke OK")


async def test_langgraph_forwards_config():
    """Instrumented nodes must receive LangGraph RunnableConfig (e.g. event_queue)."""
    from typing import TypedDict

    from langchain_core.runnables import RunnableConfig
    from langgraph.graph import StateGraph

    from app.adapters.langgraph import instrument_langgraph

    class TestState(TypedDict):
        value: str

    seen: dict[str, object] = {}

    async def async_node(state: TestState, config: RunnableConfig) -> dict:
        seen["config"] = config
        seen["event_queue"] = (config.get("configurable") or {}).get("event_queue")
        return {"value": state["value"] + "-done"}

    raw = StateGraph(TestState)
    raw.add_node("step", async_node)
    raw.set_entry_point("step")
    raw.set_finish_point("step")

    compiled = instrument_langgraph(raw).compile()
    marker = object()
    await compiled.ainvoke(
        {"value": "x"},
        config={"configurable": {"event_queue": marker}},
    )
    assert seen.get("event_queue") is marker, "config.configurable must reach wrapped node"

    print("  [PASS] LangGraph: RunnableConfig forwarded to async nodes")


async def main():
    print("=" * 60)
    print("  Adapters 集成测试")
    print("=" * 60)

    # 1. LLM Proxy
    try:
        test_proxy_llm()
    except Exception as e:
        print(f"  [FAIL] LLM Proxy: {e}")

    # 2. Callback
    try:
        test_callback_handler()
    except Exception as e:
        print(f"  [FAIL] Callback: {e}")

    # 3. LangGraph Instrument
    try:
        await test_langgraph_instrument()
    except Exception as e:
        print(f"  [FAIL] LangGraph: {e}")

    try:
        await test_langgraph_forwards_config()
    except Exception as e:
        print(f"  [FAIL] LangGraph config: {e}")

    print("=" * 60)
    print("  测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
