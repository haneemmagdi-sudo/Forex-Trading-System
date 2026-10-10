import requests
import json

def test_social():
    url = "http://127.0.0.1:8000/api/news"
    print(f"Requesting news from: {url}")
    try:
        resp = requests.get(url, timeout=10)
        print("Status Code:", resp.status_code)
        if resp.status_code == 200:
            data = resp.json()
            print("Keys in response:", list(data.keys()))
            social_buzz = data.get("social_buzz", [])
            print("Social Buzz content:")
            print(json.dumps(social_buzz, indent=2, ensure_ascii=False))
        else:
            print("Response:", resp.text)
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    test_social()
