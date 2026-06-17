"""
Test DeepSeek API connection
"""

import asyncio
from langchain_openai import ChatOpenAI

async def test_deepseek():
    """Test DeepSeek API"""
    print("Testing DeepSeek API connection...")

    try:
        llm = ChatOpenAI(
            model="deepseek-v4-flash",
            openai_api_key="sk-d85defcc856844689a697ee67f585899",
            openai_api_base="https://api.deepseek.com",
            temperature=0,
        )

        response = await llm.ainvoke("Hello! Please respond with 'API works!'")
        print(f"API Response: {response.content}")
        return True

    except Exception as e:
        print(f"API Error: {str(e)}")
        return False


if __name__ == "__main__":
    asyncio.run(test_deepseek())
