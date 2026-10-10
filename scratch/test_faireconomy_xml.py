import requests
import xml.etree.ElementTree as ET

def test_xml():
    url = "https://nfs.faireconomy.media/ff_calendar_thisweek.xml"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    print("Fetching XML...")
    resp = requests.get(url, headers=headers)
    print("Status:", resp.status_code)
    if resp.status_code == 200:
        root = ET.fromstring(resp.content)
        print("Root tag:", root.tag)
        events = list(root)
        print("Number of events:", len(events))
        if events:
            first_event = events[0]
            print("First event child tags and text:")
            for child in first_event:
                print(f"  <{child.tag}>: {child.text}")
                
            # Collect all unique tags
            all_tags = set()
            for event in events:
                for child in event:
                    all_tags.add(child.tag)
            print("All unique child tags:", all_tags)
            
            # Check for non-empty actual elements
            with_actual = []
            for event in events:
                act = event.find("actual")
                if act is not None and act.text and act.text.strip():
                    with_actual.append(event)
            print("Events with non-empty actual:", len(with_actual))
            if with_actual:
                print("Example event with actual:")
                for child in with_actual[0]:
                    print(f"  <{child.tag}>: {child.text}")
        else:
            print("No events found in XML")
    else:
        print("Failed to fetch XML")

if __name__ == "__main__":
    test_xml()
