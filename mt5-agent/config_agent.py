"""
============================================================
config_agent.py — إعدادات MT5 Agent
============================================================
قم بتعديل هذا الملف بإعداداتك
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── إعدادات السحابة ─────────────────────────────────────────
# الـ token الذي أخذته من صفحة "ربط MT5" في الموقع
AGENT_TOKEN = os.getenv("AGENT_TOKEN", "ضع_agent_token_هنا")

# رابط موقعك (بعد النشر على Vercel)
CLOUD_URL = os.getenv("CLOUD_URL", "https://your-app.vercel.app")

# ── إعدادات MT5 ──────────────────────────────────────────────
MT5_LOGIN    = int(os.getenv("MT5_LOGIN", "0"))
MT5_PASSWORD = os.getenv("MT5_PASSWORD", "")
MT5_SERVER   = os.getenv("MT5_SERVER", "ICMarkets-Demo")
