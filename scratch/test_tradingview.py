import requests
import json
from datetime import datetime, timedelta

def test_tradingview():
    url = "https://economic-calendar.tradingview.com/events"
    
    # Let's get today's date range in ISO 8601 format
    now = datetime.utcnow()
    start_dt = (now - timedelta(days=1)).strftime("%Y-%m-%dT00:00:00.000Z")
    end_dt = (now + timedelta(days=1)).strftime("%Y-%m-%dT23:59:59.000Z")
    
    params = {
        "from": start_dt,
        "to": end_dt
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Origin": "https://www.tradingview.com",
        "Referer": "https://www.tradingview.com/"
    }
    
    print(f"Fetching TradingView calendar from {start_dt} to {end_dt}...")
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        print("Status Code:", resp.status_code)
        if resp.status_code == 200:
            data = resp.json()
            # The root element is often a dict with 'result' or just a list. Let's see the type and structure.
            print("Response Type:", type(data))
            if isinstance(data, dict):
                print("Keys:", list(data.keys()))
                result = data.get("result", [])
            elif isinstance(data, list):
                result = data
            else:
                result = []
                
            print(f"Total events found: {len(result)}")
            if len(result) > 0:
                print("First 3 events:")
                print(json.dumps(result[:3], indent=2, ensure_ascii=False))
        else:
            print("Response text:", resp.text)
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    test_tradingview()
