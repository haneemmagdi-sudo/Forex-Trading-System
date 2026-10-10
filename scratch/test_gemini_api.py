import os
import httpx
from dotenv import load_dotenv

load_dotenv()

async def test_groq():
    groq_key = os.getenv("GROQ_API_KEY", "")
    print(f"Groq Key: {groq_key[:10]}...")
    url = "https://api.groq.com/openai/v1/chat/completions"
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": "You are a professional financial translator. Translate the given English news headline into Arabic. Output ONLY the translation, nothing else."},
            {"role": "user", "content": "The Fed keeps interest rates unchanged in debut meeting"}
        ],
        "temperature": 0.3
    }
    headers = {
        "Authorization": f"Bearer {groq_key}",
        "Content-Type": "application/json"
    }
    async with httpx.AsyncClient() as client:
        res = await client.post(url, json=payload, headers=headers)
        print("Groq Status:", res.status_code)
        print("Groq Response:", res.text)

import asyncio
asyncio.run(test_groq())
