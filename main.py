"""
Browser-Use Demo with OpenAI Codex

使用 OpenAI Codex OAuth 认证 + browser-use 进行浏览器自动化
通过自定义 LangChain wrapper 使用 ChatGPT Codex API
"""

import asyncio
from browser_use import Agent

from browser_use_codex import ChatCodex


async def main():
    print("=== Browser-Use Demo with OpenAI Codex ===\n")

    # 创建 LangChain Codex 实例
    # 使用 GPT-5.1 Codex Mini 模型（最便宜）
    llm = ChatCodex(model="gpt-5.2-codex")

    # 创建 Agent
    agent = Agent(
        task="Go to Google and search for 'browser automation with AI'",
        llm=llm,
    )

    print("Starting browser automation task...\n")

    # 运行任务
    try:
        result = await agent.run()
        print(f"\nTask completed! Result: {result}")
    except Exception as e:
        print(f"Error during execution: {e}")


if __name__ == "__main__":
    asyncio.run(main())
