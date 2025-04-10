from langchain_openai import ChatOpenAI
from browser_use import Agent, Browser
import asyncio
from dotenv import load_dotenv
load_dotenv()


async def main():
    browser = Browser()
    agent = Agent(
        task="Search for flights from DEL to BLR and return the cheapest flight price for today",
        llm=ChatOpenAI(model="gpt-4o"),
        browser=browser
    )
    await agent.run()
    await browser.close()

asyncio.run(main())