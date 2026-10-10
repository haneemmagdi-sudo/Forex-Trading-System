import requests
import json

def test_endpoint():
    url = "http://127.0.0.1:8000/api/news/calendar"
    print(f"Requesting calendar from: {url}")
    try:
        resp = requests.get(url, timeout=15)
        print("Status Code:", resp.status_code)
        if resp.status_code == 200:
            data = resp.json()
            print(f"Number of events returned: {len(data)}")
            if data:
                print("First 3 events:")
                print(json.dumps(data[:3], indent=2, ensure_ascii=False))
            else:
                print("Warning: Response array is empty!")
        else:
            print("Response:", resp.text)
    except Exception as e:
        print("Error connecting to backend:", e)

if __name__ == "__main__":
    test_endpoint()
