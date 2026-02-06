"""
使用 browser-use 一步一步操作 1Password
每个 task 只做一件事情
"""

import asyncio
from browser_use import Agent, Browser
from browser_use.browser.profile import ProxySettings

from browser_use_codex import ChatCodex


# 定义每个步骤的任务 - 每个只做一件事
TASKS = [
    {
        "name": "Step 1: 点击搜索框",
        "task": "Click on the 'Search vaults' input field.",
    },
    {
        "name": "Step 2: 输入搜索词",
        "task": "Type '162capital' in the search box.",
    },
    {
        "name": "Step 3: 点击 vault",
        "task": "Click on 'cam-cust-162capital-readonly' from the search results.",
    },
    {
        "name": "Step 4: 点击 Share Vault",
        "task": "Click the 'Share Vault' button.",
    },
    {
        "name": "Step 5: 搜索并添加用户",
        "task": "Find the input field to add people, type 'longphee@1token.trade', then click on the first person in the search results to add them.",
    },
    {
        "name": "Step 6: 设置权限为 View Only",
        "task": "Click the three dots menu (...) next to the user's row, then click on 'Allow Editing' to uncheck/deselect it (turn it off).",
    },
    {
        "name": "Step 7: 点击 Share 按钮",
        "task": "Click the 'Share' button to confirm.",
    },
]


async def run_task(browser: Browser, llm, task_info: dict, max_steps: int = 5) -> str:
    """运行单个任务"""
    print(f"\n{'='*50}")
    print(f"🚀 {task_info['name']}")
    print(f"   任务: {task_info['task']}")
    print(f"{'='*50}")

    agent = Agent(
        task=task_info["task"],
        llm=llm,
        browser=browser,
        max_actions_per_step=1,
        max_failures=3,
    )

    result = await agent.run(max_steps=max_steps)
    print(f"✅ 完成: {task_info['name']}")
    return str(result)


async def main():
    print("=== 1Password Vault Share Automation ===\n")
    print("目标: 将 cam-cust-162capital-readonly vault 分享给 longphee@1token.trade (View 权限)\n")

    # 创建 LLM
    llm = ChatCodex(model="gpt-5.2-codex")

    # 创建 Browser - 在所有任务之间共享
    browser = Browser(
        headless=False,
        proxy=ProxySettings(server="http://localhost:7890"),
        user_data_dir="/Users/tyz/.playwright-mcp/bblittlefox2",
        keep_alive=True,
    )

    # 先导航到 vaults 页面
    print("首先导航到 1Password vaults 页面...")
    init_agent = Agent(
        task="Navigate to https://qbtrade.1password.com/vaults?limit=25&type=All",
        llm=llm,
        browser=browser,
        max_actions_per_step=1,
    )

    try:
        await init_agent.run(max_steps=3)
        print("✅ 页面已打开\n")

        # 等待用户登录 (60秒)
        print("⏳ 请在浏览器中登录 1Password...")
        print("   等待 60 秒让用户完成登录...")
        await asyncio.sleep(60)
        print("✅ 等待完成，继续执行任务\n")

        # 逐步执行每个任务 - 自动继续
        for i, task_info in enumerate(TASKS):
            try:
                result = await run_task(browser, llm, task_info)
                print(f"   结果: {result[:200]}..." if len(str(result)) > 200 else f"   结果: {result}")
            except Exception as e:
                print(f"❌ 任务失败: {e}")
                # 自动重试一次
                print("   自动重试...")
                try:
                    result = await run_task(browser, llm, task_info)
                except Exception as e2:
                    print(f"   重试也失败: {e2}, 跳过此步骤")

        print("\n=== 所有任务完成 ===")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
