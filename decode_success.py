#!/usr/bin/env python3
"""
Successfully decode data-props with double URL decoding
"""

import json
import base64
from urllib.parse import unquote
from bs4 import BeautifulSoup

def successful_decode():
    """Successfully decode the data-props"""
    
    # Read the detailed ad file
    with open('finn_seilbåt_enkeltannonse.txt', 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Find the data-props div
    data_props_div = soup.find('div', {'id': 'mobility-item-page-root'})
    data_props_raw = data_props_div['data-props']
    
    print(f"🔍 Original data-props length: {len(data_props_raw)}")
    
    # The key insight: it's URL encoded, then base64 encoded, then URL encoded again!
    try:
        # Step 1: First URL decode
        first_decode = unquote(data_props_raw) 
        print(f"✅ First URL decode successful: {len(first_decode)} chars")
        
        # Step 2: Base64 decode
        base64_decoded = base64.b64decode(first_decode)
        print(f"✅ Base64 decode successful: {len(base64_decoded)} bytes")
        
        # Step 3: Second URL decode (the base64 contains URL-encoded JSON!)
        second_decode = unquote(base64_decoded.decode('utf-8'))
        print(f"✅ Second URL decode successful: {len(second_decode)} chars")
        
        # Step 4: Parse JSON
        json_data = json.loads(second_decode)
        print(f"✅ JSON parse successful!")
        
        return json_data
        
    except Exception as e:
        print(f"❌ Decoding failed: {e}")
        return None

def analyze_detailed_data(json_data):
    """Analyze the rich detailed data"""
    
    if 'adData' not in json_data or 'ad' not in json_data['adData']:
        print("❌ No adData.ad found")
        return
    
    ad = json_data['adData']['ad']
    
    print(f"\n🛥️  RICH BOAT DATA ANALYSIS")
    print("=" * 50)
    
    # Basic information
    print(f"📋 BASIC INFO:")
    print(f"   Title: {ad.get('title', 'N/A')}")
    print(f"   Price: {ad.get('price', 'N/A'):,} kr" if ad.get('price') else "   Price: Not specified")
    print(f"   Year: {ad.get('year', 'N/A')}")
    
    # Make and model
    make = ad.get('make', {})
    if isinstance(make, dict):
        print(f"   Make: {make.get('value', 'N/A')} (ID: {make.get('id', 'N/A')})")
    else:
        print(f"   Make: {make}")
    print(f"   Model: {ad.get('model', 'N/A')}")
    
    # Technical specifications
    print(f"\n📏 TECHNICAL SPECS:")
    print(f"   Length: {ad.get('length', 'N/A')} cm")
    print(f"   Width: {ad.get('width', 'N/A')} cm")
    print(f"   Depth: {ad.get('depth', 'N/A')} cm")
    print(f"   Weight: {ad.get('weight', 'N/A')} kg")
    
    # Material and construction
    material = ad.get('material', {})
    if isinstance(material, dict):
        print(f"   Material: {material.get('value', 'N/A')} (ID: {material.get('id', 'N/A')})")
    
    boat_class = ad.get('boat_class', {})
    if isinstance(boat_class, dict):
        print(f"   Boat class: {boat_class.get('value', 'N/A')} (ID: {boat_class.get('id', 'N/A')})")
    
    # Capacity and performance
    print(f"\n👥 CAPACITY & PERFORMANCE:")
    print(f"   Sleepers: {ad.get('no_of_sleepers', 'N/A')}")
    print(f"   Seats: {ad.get('no_of_seats', 'N/A')}")
    print(f"   Max speed: {ad.get('max_speed', 'N/A')} knots")
    
    # Engine details
    print(f"\n🔧 ENGINE DETAILS:")
    print(f"   Engine make: {ad.get('engine_make', 'N/A')}")
    
    engine_type = ad.get('engine_type', {})
    if isinstance(engine_type, dict):
        print(f"   Engine type: {engine_type.get('value', 'N/A')} (ID: {engine_type.get('id', 'N/A')})")
    
    fuel = ad.get('fuel', {})
    if isinstance(fuel, dict):
        print(f"   Fuel type: {fuel.get('value', 'N/A')} (ID: {fuel.get('id', 'N/A')})")
    
    print(f"   Engine power: {ad.get('engine_effect', 'N/A')} HP")
    
    # Location
    location = ad.get('location', {})
    if location:
        print(f"\n📍 LOCATION:")
        print(f"   Address: {location.get('address', 'N/A')}")
        print(f"   Postal code: {location.get('postalCode', 'N/A')}")
        print(f"   Postal name: {location.get('postalName', 'N/A')}")
        
        municipality = location.get('municipality', {})
        if municipality:
            print(f"   Municipality: {municipality.get('name', 'N/A')} (ID: {municipality.get('id', 'N/A')})")
        
        county = location.get('county', {})
        if county:
            print(f"   County: {county.get('name', 'N/A')} (ID: {county.get('id', 'N/A')})")
    
    # Images
    images = ad.get('images', [])
    print(f"\n📸 MEDIA:")
    print(f"   Number of images: {len(images)}")
    if images:
        print(f"   Image URLs available with template: {images[0].get('url_template', 'N/A')}")
    
    # Descriptions (rich content!)
    print(f"\n📝 DESCRIPTIONS:")
    description = ad.get('description_unsafe', '')
    if description:
        print(f"   Main description: {description[:200]}...")
    
    equipment = ad.get('equipment_unsafe', '')
    if equipment:
        print(f"   Equipment description: {equipment[:200]}...")
    
    # Show all available fields for completeness
    print(f"\n🗂️  ALL AVAILABLE FIELDS ({len(ad.keys())}):")
    for key in sorted(ad.keys()):
        value_type = type(ad[key]).__name__
        if isinstance(ad[key], (str, int, float)):
            value_preview = str(ad[key])[:50]
        elif isinstance(ad[key], (dict, list)):
            value_preview = f"{value_type} with {len(ad[key])} items"
        else:
            value_preview = value_type
        print(f"   {key}: {value_preview}")
    
    return ad

def main():
    print("🎯 SUCCESSFULLY DECODING RICH BOAT DATA")
    print("=" * 55)
    
    # Decode the data-props
    json_data = successful_decode()
    
    if json_data:
        print(f"✅ Successfully decoded {len(str(json_data))} characters of JSON data")
        print(f"🔑 Top-level keys: {list(json_data.keys())}")
        
        # Analyze the detailed boat data
        boat_details = analyze_detailed_data(json_data)
        
        print(f"\n🎉 SUCCESS!")
        print(f"💡 The detailed ad page contains ~50x more information than the listing!")
        print(f"🚀 This rich data enables much more sophisticated analysis")
        
    else:
        print("❌ Failed to decode data")

if __name__ == "__main__":
    main()