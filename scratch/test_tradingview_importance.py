import requests
from datetime import datetime, timedelta

def test_fields():
    url = "https://economic-calendar.tradingview.com/events"
    now = datetime.utcnow()
    # Fetch a wider range (3 days ago to today) to find real events that already happened and have actual values
    start_dt = (now - timedelta(days=3)).strftime("%Y-%m-%dT00:00:00.000Z")
    end_dt = (now + timedelta(days=1)).strftime("%Y-%m-%dT23:59:59.000Z")
    
    params = {"from": start_dt, "to": end_dt}
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Origin": "https://www.tradingview.com",
        "Referer": "https://www.tradingview.com/"
    }
    
    resp = requests.get(url, params=params, headers=headers)
    if resp.status_code == 200:
        events = resp.json().get("result", [])
        print(f"Total events: {len(events)}")
        
        # Check unique importance values
        importances = set(e.get("importance") for e in events)
        print("Unique importance values:", importances)
        
        # Check events with importance >= 0 (exclude holidays (-1))
        real_events = [e for e in events if e.get("importance", -1) >= 0]
        print(f"Real events (importance >= 0): {len(real_events)}")
        
        # Check high importance events
        high_imp = [e for e in real_events if e.get("importance") == 1] # wait, is 1 high, or is 2 high?
        # Let's count how many for each importance value
        from collections import Counter
        counts = Counter(e.get("importance") for e in events)
        print("Counts by importance:", counts)
        
        # Let's look for events with non-empty actual, previous, forecast
        valid_events = [e for e in real_events if e.get("actual") is not None or e.get("forecast") is not None]
        print(f"Events with actual or forecast: {len(valid_events)}")
        if valid_events:
            print("\nExample event with actual or forecast:")
            import json
            print(json.dumps(valid_events[0], indent=2))
            
            # Let's print a few high-importance events
            high_events = [e for e in real_events if e.get("importance") == 1 or e.get("importance") == 0]
            print(f"\nExample real event:")
            print(json.dumps(real_events[0], indent=2))
    else:
        print("Error:", resp.status_code)

if __name__ == "__main__":
    test_fields()
