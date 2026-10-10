import requests
import json

def test_faireconomy():
    url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    
    print("Fetching Forex Factory calendar from Fair Economy...")
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        print("Status Code:", resp.status_code)
        if resp.status_code == 200:
            data = resp.json()
            print(f"Total events this week: {len(data)}")
            if len(data) > 0:
                print("First 3 events:")
                print(json.dumps(data[:3], indent=2, ensure_ascii=False))
        else:
            print("Response text:", resp.text)
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    test_faireconomy()
