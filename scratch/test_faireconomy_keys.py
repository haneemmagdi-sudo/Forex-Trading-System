import requests

def test():
    url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        print("Total items:", len(data))
        
        # Check all unique keys
        all_keys = set()
        for item in data:
            all_keys.update(item.keys())
        print("Unique keys in any item:", all_keys)
        
        # Look for events that have occurred (actual value present)
        with_actual = [item for item in data if "actual" in item and item["actual"]]
        print("Number of items with non-empty actual:", len(with_actual))
        if with_actual:
            print("Example with actual:")
            import json
            print(json.dumps(with_actual[0], indent=2))
        else:
            # Print keys and values of the first 10 items
            print("First 5 items raw keys/values:")
            for i, item in enumerate(data[:5]):
                print(f"Item {i}: {item}")
    else:
        print("Failed", resp.status_code)

if __name__ == "__main__":
    test()
