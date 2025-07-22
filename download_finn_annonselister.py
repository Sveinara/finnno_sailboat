import requests
from bs4 import BeautifulSoup
import os
import time
import json

BASE_URL = "https://www.finn.no/bap/forsale/search.html?category=93"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
SAVE_DIR = "annonselister_html"
os.makedirs(SAVE_DIR, exist_ok=True)

def get_next_page_url(soup):
    next_link = soup.find("a", {"rel": "next"})
    if next_link and next_link.has_attr("href"):
        return "https://www.finn.no" + next_link["href"]
    return None

def extract_fields_from_json(soup):
    script_tag = soup.find('script', {'id': 'seoStructuredData'})
    if not script_tag:
        print("Fant ikke seoStructuredData-script-tag på siden!")
        return set()
    try:
        json_data = json.loads(script_tag.string)
        ads = json_data.get('mainEntity', {}).get('itemListElement', [])
        if not ads:
            print("Fant ingen annonser i JSON.")
            return set()
        fields = set()
        for ad in ads:
            item = ad.get('item', {})
            fields.update(item.keys())
            if 'offers' in item and isinstance(item['offers'], dict):
                fields.update(f"offers.{k}" for k in item['offers'].keys())
            if 'brand' in item and isinstance(item['brand'], dict):
                fields.update(f"brand.{k}" for k in item['brand'].keys())
        return fields
    except Exception as e:
        print(f"Feil ved parsing av JSON: {e}")
        return set()

def main():
    url = BASE_URL
    page = 1
    all_fields = set()
    while url:
        print(f"Laster ned side {page}: {url}")
        resp = requests.get(url, headers=HEADERS)
        if resp.status_code != 200:
            print(f"Feil ved nedlasting av {url}: {resp.status_code}")
            break
        filename = os.path.join(SAVE_DIR, f"finn_seilbåt_annonseliste_{page}.html")
        with open(filename, "w", encoding="utf-8") as f:
            f.write(resp.text)
        soup = BeautifulSoup(resp.text, "html.parser")
        fields = extract_fields_from_json(soup)
        print(f"Felter funnet på side {page}: {fields}")
        all_fields.update(fields)
        next_url = get_next_page_url(soup)
        if next_url == url:
            print("Neste side er samme som nåværende, stopper.")
            break
        url = next_url
        page += 1
        time.sleep(1)  # Vær snill mot Finn.no
    print("\nAlle felter funnet i annonselister:")
    for field in sorted(all_fields):
        print(field)

if __name__ == "__main__":
    main() 