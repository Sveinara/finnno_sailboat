import json
import pandas as pd
from bs4 import BeautifulSoup
import base64
import re
from typing import Dict, List, Optional, Any
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def parse_ad_list(file_path):
    """Parses the ad list file to extract structured data."""
    with open(file_path, 'r', encoding='utf-8') as f:
        html_content = f.read()

    soup = BeautifulSoup(html_content, 'html.parser')
    script_tag = soup.find('script', {'id': 'seoStructuredData'})
    
    if not script_tag:
        logger.warning("Could not find the seoStructuredData script tag.")
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

def extract_technical_specs(ad_data: Dict) -> Dict[str, Any]:
    """Extract technical specifications from ad data."""
    specs = {}
    
    # Extract year
    if 'year' in ad_data:
        specs['year'] = ad_data.get('year')
    
    # Extract dimensions
    specs['length'] = ad_data.get('length')
    specs['width'] = ad_data.get('width') 
    specs['depth'] = ad_data.get('depth')
    specs['weight'] = ad_data.get('weight')
    
    # Extract motor information
    motor_info = ad_data.get('motor', {})
    if motor_info:
        specs['motor_make'] = motor_info.get('make')
        specs['motor_size'] = motor_info.get('size')
        specs['motor_type'] = motor_info.get('motor_type', {}).get('value')
        specs['fuel_type'] = motor_info.get('fuel', {}).get('value')
    
    # Extract material
    material = ad_data.get('material', {})
    if material:
        specs['material'] = material.get('value')
    
    # Extract boat class
    boat_class = ad_data.get('boat_class', {})
    if boat_class:
        specs['boat_class'] = boat_class.get('value')
    
    # Extract condition
    specs['condition'] = ad_data.get('condition')
    
    # Extract number of sleepers and seats
    specs['no_of_sleepers'] = ad_data.get('no_of_sleepers')
    specs['no_of_seats'] = ad_data.get('no_of_seats')
    
    # Extract max speed
    specs['max_speed'] = ad_data.get('max_speed')
    
    return specs

def extract_equipment_and_condition(description: str, equipment_text: str = "") -> Dict[str, Any]:
    """Extract equipment list and condition indicators from text descriptions."""
    if not description:
        description = ""
    if not equipment_text:
        equipment_text = ""
    
    full_text = f"{description} {equipment_text}".lower()
    
    # Equipment keywords to look for
    equipment_keywords = {
        'navigation': ['gps', 'kartplotter', 'radar', 'kompass', 'ais'],
        'sails': ['storseil', 'foreseil', 'genoa', 'spinnaker', 'lazy bag'],
        'comfort': ['varme', 'toalett', 'kjøkken', 'fryser', 'mikrobølgeovn'],
        'safety': ['redningsflåte', 'livbåt', 'brannslokkingsapparat', 'nødraketter'],
        'mechanical': ['vindlass', 'baugpropell', 'generator', 'inverter', 'solar'],
        'electronics': ['vhf', 'radio', 'tv', 'stereo', 'wifi']
    }
    
    found_equipment = {}
    for category, keywords in equipment_keywords.items():
        found_equipment[category] = [kw for kw in keywords if kw in full_text]
    
    # Look for condition indicators
    condition_indicators = {
        'positive': ['ny', 'nye', 'godt vedlikeholdt', 'utmerket', 'perfekt', 'renovert'],
        'neutral': ['brukt', 'normal', 'standard'],
        'negative': ['defekt', 'skade', 'trenger', 'må', 'reparasjon', 'slitt']
    }
    
    condition_flags = {}
    for sentiment, keywords in condition_indicators.items():
        condition_flags[sentiment] = [kw for kw in keywords if kw in full_text]
    
    return {
        'equipment': found_equipment,
        'condition_flags': condition_flags
    }

def parse_single_ad(file_path):
    """Parses a single ad file to extract detailed structured data."""
    with open(file_path, 'r', encoding='utf-8') as f:
        html_content = f.read()

    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Try multiple methods to extract data
    ad_data = None
    
    # Method 1: Try data-props div
    data_props_div = soup.find('div', {'id': 'mobility-item-page-root'})
    if data_props_div and 'data-props' in data_props_div.attrs:
        try:
            # Clean the base64 string
            data_props_raw = data_props_div['data-props']
            logger.info(f"Raw data-props length: {len(data_props_raw)}")
            
            # Try to decode base64
            decoded_props = base64.b64decode(data_props_raw)
            data_props = json.loads(decoded_props)
            ad_data = data_props.get('adData', {}).get('ad', {})
            logger.info("Successfully parsed ad data from data-props")
            
        except (json.JSONDecodeError, TypeError, Exception) as e:
            logger.warning(f"Failed to decode data-props: {e}")
    
    # Method 2: Try to find JSON in script tags
    if not ad_data:
        script_tags = soup.find_all('script', type='application/json')
        for script in script_tags:
            try:
                script_data = json.loads(script.string)
                if 'adData' in script_data:
                    ad_data = script_data['adData']['ad']
                    logger.info("Successfully parsed ad data from script tag")
                    break
            except:
                continue
    
    # Method 3: Extract from HTML structure if JSON fails
    if not ad_data:
        logger.info("Falling back to HTML parsing")
        ad_data = extract_from_html_structure(soup)
    
    if not ad_data:
        logger.error("Could not extract ad data from any method")
        return None
    
    # Extract technical specifications
    technical_specs = extract_technical_specs(ad_data)
    
    # Extract equipment and condition from descriptions
    description = ad_data.get('description_unsafe', '') or ad_data.get('summary', '')
    equipment_info = ad_data.get('equipment_unsafe', '')
    equipment_analysis = extract_equipment_and_condition(description, equipment_info)
    
    # Combine all data
    result = {
        'basic_info': {
            'title': ad_data.get('title'),
            'price': ad_data.get('price'),
            'year': technical_specs.get('year'),
            'make': ad_data.get('make', {}).get('value') if isinstance(ad_data.get('make'), dict) else ad_data.get('make'),
            'model': ad_data.get('model'),
            'location': ad_data.get('location', {}).get('postalName') if ad_data.get('location') else None
        },
        'technical_specs': technical_specs,
        'equipment': equipment_analysis['equipment'],
        'condition_analysis': equipment_analysis['condition_flags'],
        'descriptions': {
            'main': description,
            'equipment': equipment_info
        },
        'raw_data': ad_data  # Keep for debugging
    }
    
    return result

def extract_from_html_structure(soup):
    """Fallback method to extract data from HTML structure when JSON parsing fails."""
    data = {}
    
    # Extract title
    title_elem = soup.find('h1')
    if title_elem:
        data['title'] = title_elem.get_text(strip=True)
    
    # Extract price
    price_elem = soup.find(string=re.compile(r'kr|kroner'))
    if price_elem:
        price_match = re.search(r'(\d+(?:[\s\xa0]*\d+)*)', price_elem)
        if price_match:
            # Remove all whitespace and non-breaking spaces
            price_str = re.sub(r'[\s\xa0]+', '', price_match.group(1))
            try:
                data['price'] = int(price_str)
            except ValueError:
                logger.warning(f"Could not parse price: {price_match.group(1)}")
    
    # Extract description from various possible containers
    desc_selectors = [
        '[data-testid="description"]',
        '.import-decoration',
        '.u-word-break'
    ]
    
    for selector in desc_selectors:
        desc_elem = soup.select_one(selector)
        if desc_elem:
            data['description_unsafe'] = desc_elem.get_text(strip=True)
            break
    
    logger.info(f"Extracted from HTML: {list(data.keys())}")
    return data

if __name__ == '__main__':
    # 1. Parse the list of ads
    ad_list_file = 'finn_seilbåt_annonseliste.txt'
    ads_summary = parse_ad_list(ad_list_file)
    print(f"Found {len(ads_summary)} ads in the list.")

    # 2. Parse one detailed ad
    single_ad_file = 'finn_seilbåt_enkeltannonse.txt'
    detailed_ad = parse_single_ad(single_ad_file)

    # 3. Display results
    if detailed_ad:
        print("\n=== DETAILED AD ANALYSIS ===")
        print(f"Title: {detailed_ad['basic_info']['title']}")
        print(f"Price: {detailed_ad['basic_info']['price']:,} kr" if detailed_ad['basic_info']['price'] else "Price: Not specified")
        print(f"Year: {detailed_ad['basic_info']['year']}")
        print(f"Make: {detailed_ad['basic_info']['make']}")
        print(f"Location: {detailed_ad['basic_info']['location']}")
        
        print(f"\n=== TECHNICAL SPECS ===")
        for key, value in detailed_ad['technical_specs'].items():
            if value:
                print(f"{key}: {value}")
        
        print(f"\n=== EQUIPMENT FOUND ===")
        for category, items in detailed_ad['equipment'].items():
            if items:
                print(f"{category}: {', '.join(items)}")
        
        print(f"\n=== CONDITION INDICATORS ===")
        for sentiment, flags in detailed_ad['condition_analysis'].items():
            if flags:
                print(f"{sentiment}: {', '.join(flags)}")
    else:
        print("Failed to parse detailed ad")

    # 4. Save enhanced data
    if ads_summary:
        df = pd.DataFrame(ads_summary)
        output_csv_path = 'seilbater_liste_enhanced.csv'
        df.to_csv(output_csv_path, index=False, encoding='utf-8-sig')
        print(f"\nSaved enhanced ad summaries to {output_csv_path}") 