"""
使用 browser-use 批量添加 DeBank 地址到 CAM System
"""

import asyncio
from browser_use import Agent, Browser
from browser_use.browser.profile import ProxySettings

from browser_use_codex import ChatCodex

# DeBank Top 100 中 $500K - $5M 净值用户地址列表
ADDRESSES = [
    {"rank": 10, "name": "Octoshi", "worth": "$1.1M", "address": "0x5baac7ccda079839c9524b90df81720834fc039f"},
    {"rank": 15, "name": "0xbbbc", "worth": "$3.7M", "address": "0xbbbc35dfac3a00a03a8fde3540eca4f0e15c5e64"},
    {"rank": 16, "name": "VY100", "worth": "$616.6K", "address": "0x87f16c31e32ae543278f5194cf94862f1cb1eee0"},
    {"rank": 19, "name": "cp0x_1", "worth": "$1M", "address": "0x6f9bb7e454f5b3eb2310343f0e99269dc2bb8a1d"},
    {"rank": 26, "name": "Transhumanist", "worth": "$2.6M", "address": "0xa7888f85bd76deef3bd03d4dbcf57765a49883b3"},
    {"rank": 33, "name": "kirby", "worth": "$5M", "address": "0x6cd68e8f04490cd1a5a21cc97cc8bc15b47dc9eb"},
    {"rank": 37, "name": "nelsonmandela", "worth": "$1.2M", "address": "0x90c0bf8d71369d21f8addf0da33d21dcb0b1c384"},
    {"rank": 41, "name": "Yamete", "worth": "$677K", "address": "0x9e47fbb2a2a27b3b02e4a63b3ef5a3dc863c0223"},
    {"rank": 49, "name": "Punkk", "worth": "$766.9K", "address": "0xc69ae428f6049e78d445f053d2c1df879c59b34c"},
    {"rank": 50, "name": "vitalik", "worth": "$1.8M", "address": "0xc1e42f862d202b4a0ed552c1145735ee088f6ccf"},
    {"rank": 58, "name": "Taliba", "worth": "$1.8M", "address": "0x6595a41a2ebe230522076c544fb2de11a6666226"},
    {"rank": 61, "name": "CryptoCat", "worth": "$3.3M", "address": "0x0a5e1db3671faccd146404925bda5c59929f66c3"},
    {"rank": 66, "name": "Indodax", "worth": "$4.9M", "address": "0x11d67fa925877813b744abc0917900c2b1d6eb81"},
    {"rank": 67, "name": "ZeroPants", "worth": "$2.9M", "address": "0x614d98a57a5d879d717152de0690ed2b04562ade"},
    {"rank": 69, "name": "kimpercy", "worth": "$854.9K", "address": "0x5d2f29aa18aef827317c48bd2b4f05fa24880038"},
    {"rank": 74, "name": "henderob", "worth": "$1.8M", "address": "0x4062b997279de7213731dbe00485722a26718892"},
    {"rank": 82, "name": "polka", "worth": "$3.5M", "address": "0xb554b9856dfdbf52b98e0e4d2b981c34e20e1dab"},
    {"rank": 83, "name": "BugsBunny", "worth": "$519.6K", "address": "0xa67b426eb6de4c24ecb3f778ed3f9c09ae0699cb"},
    {"rank": 85, "name": "Admiral", "worth": "$3.6M", "address": "0x7ac34681f6aaeb691e150c43ee494177c0e2c183"},
    {"rank": 88, "name": "fulmer", "worth": "$1.9M", "address": "0xc47fae56f3702737b69ed615950c01217ec5c7c8"},
    {"rank": 93, "name": "Oprah", "worth": "$2.5M", "address": "0x156daf376cfbdd938c470a227508b0ba022c998f"},
]


async def main():
    # 先测试添加前 3 个
    test_addresses = ADDRESSES[:3]
    print(f"=== Adding {len(test_addresses)} DeBank addresses to CAM System ===\n")

    # 构建任务描述
    addresses_text = "\n".join(
        [f"- Name: DeBank-{a['name']}, Address: {a['address']}" for a in test_addresses]
    )

    task = f"""
First, go to https://fresh2.cammaster.org and login if needed:
- Username: admin
- Password: jkn5upe*hvy8vqj.ARJ

Then go to https://fresh2.cammaster.org/v3/operation/api/blockchain

Add the following blockchain addresses one by one:
{addresses_text}

For each address:
1. Click "Add Account" button
2. Fill Address field with the address
3. Click Chain field, select "All EVM"
4. Fill Account Name with the name (e.g., DeBank-Octoshi)
5. Click "Confirm" to save
6. Repeat for next address

Report success when all 3 addresses are added.
"""

    # 创建 LLM
    llm = ChatCodex(model="gpt-5.2-codex")

    # 创建 Browser with proxy and persistent profile
    browser = Browser(
        headless=False,
        proxy=ProxySettings(server="http://localhost:7890"),
        user_data_dir="/Users/tyz/.browser-use-profile",  # 持久化用户数据
        keep_alive=True,  # 保持浏览器打开
    )

    # 创建 Agent
    agent = Agent(
        task=task,
        llm=llm,
        browser=browser,
    )

    print("Starting browser automation...\n")
    print(f"Task: Add {len(ADDRESSES)} addresses to CAM Blockchain Address\n")

    try:
        result = await agent.run(max_steps=100)  # 允许更多步骤
        print(f"\nTask completed! Result: {result}")
    except Exception as e:
        print(f"Error during execution: {e}")


if __name__ == "__main__":
    asyncio.run(main())
