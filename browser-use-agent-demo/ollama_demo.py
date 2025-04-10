import asyncio

from browser_use import Agent, Browser
from langchain_ollama import ChatOllama

# Initialize the model
llm = ChatOllama(model="qwen2.5:7b", num_ctx=32000)
browser = Browser()

# Create agent with the model
agent = Agent(
    task="Go to google.com and search for flights from DEL to BLR and return the cheapest flight price",
    llm=llm,
    browser=browser
)


async def main():
    await agent.run()
    await browser.close()


asyncio.run(main())
