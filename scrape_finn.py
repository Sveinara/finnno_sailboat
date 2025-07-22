import json
import pandas as pd
from bs4 import BeautifulSoup
import base64

def parse_ad_list(file_path):
    """Parses the ad list file to extract structured data."""
    with open(file_path, 'r', encoding='utf-8') as f:
        html_content = f.read()

    soup = BeautifulSoup(html_content, 'html.parser')
    script_tag = soup.find('script', {'id': 'seoStructuredData'})
    
    if not script_tag:
        print("Could not find the seoStructuredData script tag.")
        return []

    json_data = json.loads(script_tag.string)
    ads = json_data.get('mainEntity', {}).get('itemListElement', [])
    
    extracted_ads = []
    for ad in ads:
        item = ad.get('item', {})
        offers = item.get('offers', {})
        brand = item.get('brand', {})
        
        extracted_ads.append({
            'name': item.get('name'),
            'url': item.get('url'),
            'price': offers.get('price'),
            'brand': brand.get('name'),
            'description': item.get('description'),
            'image_url': item.get('image')
        })
        
    return extracted_ads

def parse_single_ad(file_path):
    """Parses a single ad file to extract detailed structured data."""
    with open(file_path, 'r', encoding='utf-8') as f:
        html_content = f.read()

    soup = BeautifulSoup(html_content, 'html.parser')
    data_props_div = soup.find('div', {'id': 'mobility-item-page-root'})
    
    if not data_props_div or 'data-props' not in data_props_div.attrs:
        print("Could not find the data-props div.")
        return None

    # Print the raw data-props attribute for inspection
    print("Raw data-props attribute:")
    print(data_props_div['data-props'])

    # Decode the Base64 encoded string from data-props
    try:
        decoded_props = base64.b64decode(data_props_div['data-props'])
        data_props = json.loads(decoded_props)
    except (json.JSONDecodeError, TypeError) as e:
        print(f"Failed to decode or parse JSON from data-props: {e}")
        return None
        
    ad_data = data_props.get('adData', {}).get('ad', {})
    
    return ad_data

if __name__ == '__main__':
    # 1. Parse the list of ads
    ad_list_file = 'finn_seilbåt_annonseliste.txt'
    ads_summary = parse_ad_list(ad_list_file)
    print(f"Found {len(ads_summary)} ads in the list.")

    # 2. For demonstration, parse one detailed ad
    # In a real scraper, you would loop through ads_summary and fetch each URL.
    single_ad_file = 'finn_seilbåt_enkeltannonse.txt'
    detailed_ad = parse_single_ad(single_ad_file)

    # 3. We can now combine the data. For this example, we'll just show the detailed ad data.
    if detailed_ad:
        print("\nDetailed information from a single ad:")
        # Pretty print the detailed ad JSON
        print(json.dumps(detailed_ad, indent=2, ensure_ascii=False))

    # 4. Save the summary data to a CSV file
    if ads_summary:
        df = pd.DataFrame(ads_summary)
        output_csv_path = 'seilbater_liste.csv'
        df.to_csv(output_csv_path, index=False, encoding='utf-8-sig')
        print(f"\nSaved ad summaries to {output_csv_path}") 