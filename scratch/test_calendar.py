import os
import requests
import json
from datetime import datetime

FINNHUB_API_KEY = "d7dfofhr01qggoeo6ajgd7dfofhr01qggoeo6ak0"

def test_fetch():
    today = datetime.now().strftime("%Y-%m-%d")
    url = "https://finnhub.io/api/v1/calendar/economic"
    params = {
        "from": today,
        "to": today,
        "token": FINNHUB_API_KEY
    }
    
    print(f"Fetching from {today} to {today}...")
    resp = requests.get(url, params=params)
    print("Status:", resp.status_code)
    if resp.status_code == 200:
        data = resp.json()
        print("Keys:", data.keys())
        calendar = data.get("economicCalendar", [])
        print(f"Fetched {len(calendar)} events")
        if calendar:
            print("First event example:")
            print(json.dumps(calendar[0], indent=2))
        else:
            # Let's try fetching a wider range if today is empty
            print("Today calendar is empty, trying last week range...")
            params["from"] = "2026-06-15"
            params["to"] = "2026-06-21"
            resp2 = requests.get(url, params=params)
            if resp2.status_code == 200:
                calendar2 = resp2.json().get("economicCalendar", [])
                print(f"Fetched {len(calendar2)} events for range")
                if calendar2:
                    print(json.dumps(calendar2[0], indent=2))
    else:
        print(resp.text)

if __name__ == "__main__":
    test_fetch()
