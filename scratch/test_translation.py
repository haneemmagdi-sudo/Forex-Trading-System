import asyncio
import os
import sys
from dotenv import load_dotenv

# Load env variables
load_dotenv()

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from core.news_fetcher import NewsFetcher

async def test_translation():
    print("Initializing NewsFetcher...")
    fetcher = NewsFetcher()
    print("Fetching and translating forex news...")
    news = await fetcher.fetch_forex_news(force=True)
    
    print(f"Total news items retrieved: {len(news)}")
    print("\nSample translated headlines:")
    for idx, item in enumerate(news[:5]):
        print(f"\n--- Article {idx+1} ---")
        print(f"Source: {item.source}")
        print(f"English: {item.headline}")
        print(f"Arabic : {item.headline_ar}")
        print(f"URL    : {item.url}")
        print(f"Impact : {item.impact}")

if __name__ == "__main__":
    asyncio.run(test_translation())
