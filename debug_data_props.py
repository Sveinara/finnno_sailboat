#!/usr/bin/env python3
"""
Debug script to understand data-props encoding
"""

import json
import base64
from urllib.parse import unquote
from bs4 import BeautifulSoup

def debug_data_props():
    """Debug the data-props encoding step by step"""
    
    # Read the detailed ad file
    with open('finn_seilbåt_enkeltannonse.txt', 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Find the data-props div
    data_props_div = soup.find('div', {'id': 'mobility-item-page-root'})
    if not data_props_div or 'data-props' not in data_props_div.attrs:
        print("❌ Could not find data-props div")
        return
    
    data_props_raw = data_props_div['data-props']
    print(f"Raw data-props length: {len(data_props_raw)}")
    print(f"First 200 chars: {data_props_raw[:200]}")
    print(f"Last 200 chars: {data_props_raw[-200:]}")
    
    # Try different decoding approaches
    print("\n=== DECODING ATTEMPTS ===")
    
    # 1. Direct base64 decode
    try:
        direct_decode = base64.b64decode(data_props_raw)
        print(f"✅ Direct base64 decode: {len(direct_decode)} bytes")
        print(f"First 100 bytes: {direct_decode[:100]}")
        
        # Try to parse as JSON
        try:
            json_data = json.loads(direct_decode)
            print(f"✅ JSON parse successful!")
            print(f"Top level keys: {list(json_data.keys())}")
            return json_data
        except:
            print("❌ Not valid JSON after direct decode")
            
    except Exception as e:
        print(f"❌ Direct base64 decode failed: {e}")
    
    # 2. URL decode first, then base64
    try:
        url_decoded = unquote(data_props_raw)
        print(f"URL decode length: {len(url_decoded)}")
        print(f"URL decoded first 100: {url_decoded[:100]}")
        
        base64_decoded = base64.b64decode(url_decoded)
        print(f"✅ URL then base64 decode: {len(base64_decoded)} bytes")
        
        try:
            json_data = json.loads(base64_decoded)
            print(f"✅ JSON parse successful!")
            print(f"Top level keys: {list(json_data.keys())}")
            return json_data
        except:
            print("❌ Not valid JSON after URL+base64 decode")
            
    except Exception as e:
        print(f"❌ URL+base64 decode failed: {e}")
    
    # 3. Try to find JSON elsewhere in the page
    print("\n=== LOOKING FOR JSON ELSEWHERE ===")
    
    # Look for script tags with JSON
    script_tags = soup.find_all('script')
    for i, script in enumerate(script_tags):
        if script.string and len(script.string) > 1000:
            print(f"Script {i}: {len(script.string)} chars")
            try:
                json_data = json.loads(script.string)
                print(f"✅ Found JSON in script {i}!")
                print(f"Keys: {list(json_data.keys())}")
                if 'adData' in json_data:
                    print("🎯 Found adData!")
                    return json_data
            except:
                continue
    
    # Look for JSON in other attributes
    print("\n=== CHECKING OTHER ELEMENTS ===")
    all_divs = soup.find_all('div', attrs={'data-props': True})
    for div in all_divs:
        print(f"Div with data-props: id={div.get('id')}, class={div.get('class')}")
    
    return None

def extract_key_info_from_html(soup):
    """Extract what we can from HTML structure"""
    print("\n=== EXTRACTING FROM HTML STRUCTURE ===")
    
    # Look for key information in HTML
    title = soup.find('title')
    if title:
        print(f"Page title: {title.get_text()}")
    
    # Look for meta description
    meta_desc = soup.find('meta', attrs={'name': 'description'})
    if meta_desc:
        print(f"Description: {meta_desc.get('content', '')[:200]}...")
    
    # Look for any elements with boat-related text
    price_patterns = soup.find_all(string=lambda text: text and 'kr' in text.lower())
    for pattern in price_patterns[:5]:
        clean_text = pattern.strip()
        if len(clean_text) > 5 and len(clean_text) < 50:
            print(f"Price-related text: {clean_text}")

def main():
    print("🔍 DEBUGGING DATA-PROPS ENCODING")
    print("=" * 50)
    
    # Read file and parse
    with open('finn_seilbåt_enkeltannonse.txt', 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Try to decode data-props
    json_data = debug_data_props()
    
    # If we found JSON data, analyze it
    if json_data:
        print("\n=== ANALYZING FOUND JSON ===")
        if 'adData' in json_data and 'ad' in json_data['adData']:
            ad = json_data['adData']['ad']
            print(f"Title: {ad.get('title', 'N/A')}")
            print(f"Price: {ad.get('price', 'N/A')}")
            print(f"Year: {ad.get('year', 'N/A')}")
            print(f"Length: {ad.get('length', 'N/A')}")
            print(f"Engine make: {ad.get('engine_make', 'N/A')}")
            
            # Show all available fields
            print(f"\nAll available fields ({len(ad.keys())}):")
            for key in sorted(ad.keys()):
                value = str(ad[key])[:50]
                print(f"  {key}: {value}...")
    
    # Fallback to HTML parsing
    extract_key_info_from_html(soup)

if __name__ == "__main__":
    main()