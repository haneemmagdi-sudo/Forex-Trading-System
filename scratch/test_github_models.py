import os
import httpx
from dotenv import load_dotenv
import asyncio

load_dotenv()

async def test_github_models():
    github_key = os.getenv("GITHUB_MODELS_TOKEN", "")
    github_model = os.getenv("GITHUB_MODELS_MODEL", "gpt-4o-mini")
    print(f"GitHub Models Token: {github_key[:20]}...")
    print(f"GitHub Models Model: {github_model}")
    
    url = "https://models.inference.ai.azure.com/chat/completions"
    payload = {
        "model": github_model,
        "messages": [
            {"role": "system", "content": "You are a professional financial translator. Translate the given English news headline into Arabic. Output ONLY the translation, nothing else."},
            {"role": "user", "content": "The Fed keeps interest rates unchanged in debut meeting"}
        ],
        "temperature": 0.3
    }
    headers = {
        "Authorization": f"Bearer {github_key}",
        "Content-Type": "application/json"
    }
    async with httpx.AsyncClient() as client:
        res = await client.post(url, json=payload, headers=headers)
        print("GitHub Models Status:", res.status_code)
        print("GitHub Models Response Headers:", dict(res.headers))
        print("GitHub Models Response Text:", res.text)

if __name__ == "__main__":
    asyncio.run(test_github_models())
