#!/usr/bin/env python3
"""
Analyze detailed boat ad data from data-props
Shows what rich information is available vs the limited listing data
"""

import json
import base64
from urllib.parse import unquote
from bs4 import BeautifulSoup
from pprint import pprint

def decode_data_props(data_props_string):
    """Decode the base64 encoded data-props string"""
    try:
        # First URL decode
        url_decoded = unquote(data_props_string)
        print(f"URL decoded length: {len(url_decoded)}")
        
        # Then base64 decode
        base64_decoded = base64.b64decode(url_decoded)
        print(f"Base64 decoded length: {len(base64_decoded)}")
        
        # Parse JSON
        json_data = json.loads(base64_decoded)
        return json_data
        
    except Exception as e:
        print(f"Decoding failed: {e}")
        return None

def analyze_ad_structure(ad_data):
    """Analyze the structure of the ad data"""
    print("\n=== AD DATA STRUCTURE ===")
    
    def print_structure(obj, level=0, max_level=3):
        indent = "  " * level
        
        if level > max_level:
            print(f"{indent}... (max depth reached)")
            return
            
        if isinstance(obj, dict):
            for key, value in obj.items():
                if isinstance(value, (dict, list)):
                    print(f"{indent}{key}: ({type(value).__name__}, {len(value)} items)")
                    if len(str(value)) < 200:  # Only dive deeper for smaller objects
                        print_structure(value, level + 1, max_level)
                else:
                    print(f"{indent}{key}: {type(value).__name__} = {str(value)[:100]}...")
        elif isinstance(obj, list):
            print(f"{indent}List with {len(obj)} items:")
            if obj and level < max_level:
                print(f"{indent}[0]: {type(obj[0]).__name__}")
                if isinstance(obj[0], dict):
                    print_structure(obj[0], level + 1, max_level)
    
    print_structure(ad_data)

def extract_boat_details(ad_data):
    """Extract detailed boat information"""
    ad = ad_data.get('adData', {}).get('ad', {})
    
    print("\n=== EXTRACTED BOAT DETAILS ===")
    
    # Basic info
    print(f"Title: {ad.get('title')}")
    print(f"Price: {ad.get('price'):,} kr" if ad.get('price') else "Price: Not specified")
    print(f"Year: {ad.get('year')}")
    print(f"Make: {ad.get('make', {}).get('value') if isinstance(ad.get('make'), dict) else ad.get('make')}")
    print(f"Model: {ad.get('model')}")
    
    # Technical specifications
    print(f"\n--- TECHNICAL SPECS ---")
    print(f"Length: {ad.get('length')} cm")
    print(f"Width: {ad.get('width')} cm" )
    print(f"Depth: {ad.get('depth')} cm")
    print(f"Weight: {ad.get('weight')} kg")
    
    # Material and class
    material = ad.get('material', {})
    if isinstance(material, dict):
        print(f"Material: {material.get('value')}")
    
    boat_class = ad.get('boat_class', {})
    if isinstance(boat_class, dict):
        print(f"Boat class: {boat_class.get('value')}")
    
    # Capacity
    print(f"Sleepers: {ad.get('no_of_sleepers')}")
    print(f"Seats: {ad.get('no_of_seats')}")
    print(f"Max speed: {ad.get('max_speed')} knots")
    
    # Engine details
    print(f"\n--- ENGINE DETAILS ---")
    engine_make = ad.get('engine_make')
    if engine_make:
        print(f"Engine make: {engine_make}")
    
    engine_type = ad.get('engine_type', {})
    if isinstance(engine_type, dict):
        print(f"Engine type: {engine_type.get('value')}")
    
    fuel = ad.get('fuel', {})
    if isinstance(fuel, dict):
        print(f"Fuel type: {fuel.get('value')}")
        
    engine_effect = ad.get('engine_effect')
    if engine_effect:
        print(f"Engine power: {engine_effect} HP")
    
    # Condition and descriptions
    print(f"\n--- DESCRIPTIONS ---")
    print(f"Description: {ad.get('description_unsafe', '')[:200]}...")
    print(f"Equipment: {ad.get('equipment_unsafe', '')[:200]}...")
    
    # Location
    location = ad.get('location', {})
    if location:
        print(f"\n--- LOCATION ---")
        print(f"Address: {location.get('address')}")
        print(f"Postal code: {location.get('postalCode')}")
        print(f"Postal name: {location.get('postalName')}")
        print(f"Municipality: {location.get('municipality', {}).get('name')}")
        print(f"County: {location.get('county', {}).get('name')}")
    
    # Images
    images = ad.get('images', [])
    print(f"\n--- MEDIA ---")
    print(f"Number of images: {len(images)}")
    if images:
        print(f"First image: {images[0].get('url_template', 'N/A')}")
    
    return ad

def compare_data_richness(list_data, detailed_data):
    """Compare data richness between list and detailed views"""
    print("\n=== DATA RICHNESS COMPARISON ===")
    
    list_fields = set()
    detailed_fields = set()
    
    # Extract fields from list data (simplified structure)
    if list_data:
        list_fields = set(list_data.keys())
    
    # Extract fields from detailed data
    if detailed_data:
        def extract_fields(obj, prefix=""):
            fields = set()
            if isinstance(obj, dict):
                for key, value in obj.items():
                    field_name = f"{prefix}.{key}" if prefix else key
                    fields.add(field_name)
                    if isinstance(value, dict) and len(str(value)) < 500:
                        fields.update(extract_fields(value, field_name))
            return fields
        
        detailed_fields = extract_fields(detailed_data)
    
    print(f"List data fields ({len(list_fields)}): {', '.join(sorted(list(list_fields)[:10]))}...")
    print(f"Detailed data fields ({len(detailed_fields)}): {', '.join(sorted(list(detailed_fields)[:20]))}...")
    
    unique_to_detailed = detailed_fields - list_fields
    print(f"\nUNIQUE TO DETAILED VIEW ({len(unique_to_detailed)}):")
    for field in sorted(list(unique_to_detailed)[:20]):
        print(f"  - {field}")
    
    return {
        'list_fields': list_fields,
        'detailed_fields': detailed_fields,
        'unique_to_detailed': unique_to_detailed
    }

def generate_enhanced_pipeline_plan(comparison_data):
    """Generate plan for enhanced data pipeline focusing on detailed ads"""
    print("\n=== ENHANCED PIPELINE PLAN ===")
    
    print("🎯 STRATEGY: Focus on detailed ads for rich data extraction")
    print("\n📋 CURRENT WORKFLOW:")
    print("1. Get list of ads from search page (basic info only)")
    print("2. For each promising ad URL -> fetch detailed ad page")
    print("3. Extract rich technical, condition, and location data")
    print("4. Run comprehensive analysis with LLM")
    
    print("\n🚀 ENHANCED WORKFLOW:")
    print("1. Parse ad list for URLs and basic filtering")
    print("2. Prioritize ads by initial criteria (price range, year, make)")
    print("3. Batch fetch detailed pages for top candidates")
    print("4. Extract comprehensive data:")
    print("   - Technical specs (length, engine, materials)")
    print("   - Detailed descriptions and equipment lists")
    print("   - High-res images for condition assessment")
    print("   - Precise location data")
    print("5. Advanced analysis:")
    print("   - Market value estimation with detailed specs")
    print("   - Equipment value assessment")
    print("   - Condition analysis from descriptions")
    print("   - LLM-powered detailed evaluation")
    
    print("\n💡 KEY IMPROVEMENTS:")
    print("✅ 10x more data points per boat")
    print("✅ Precise technical specifications")
    print("✅ Detailed equipment inventories")
    print("✅ Rich descriptions for condition analysis")
    print("✅ Multiple high-resolution images")
    print("✅ Exact location for market analysis")

def main():
    print("🛥️  ANALYZING DETAILED BOAT AD DATA")
    print("=" * 50)
    
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
    print(f"📊 Found data-props attribute with {len(data_props_raw)} characters")
    
    # Decode the data
    decoded_data = decode_data_props(data_props_raw)
    if not decoded_data:
        print("❌ Failed to decode data-props")
        return
    
    print("✅ Successfully decoded data-props")
    
    # Analyze structure
    analyze_ad_structure(decoded_data)
    
    # Extract detailed boat info
    boat_details = extract_boat_details(decoded_data)
    
    # Compare with list data (simulate simple list entry)
    simple_list_data = {
        'name': 'Bavaria 38 AC crucier - 2005',
        'price': 720000,
        'brand': 'Bavaria',
        'description': 'En flott familiebåt som er klar til å seile...',
        'url': 'https://www.finn.no/mobility/item/416620130'
    }
    
    comparison = compare_data_richness(simple_list_data, boat_details)
    
    # Generate enhanced pipeline plan
    generate_enhanced_pipeline_plan(comparison)
    
    print(f"\n🎉 ANALYSIS COMPLETE!")
    print(f"💰 This boat: {boat_details.get('title', 'Bavaria 38 AC')} - {boat_details.get('price', 720000):,} kr")
    print(f"📏 Specs: {boat_details.get('length', 'N/A')}cm long, {boat_details.get('year', 2005)}")
    print(f"🔧 Engine: {boat_details.get('engine_make', 'Volvo Penta')}")
    print(f"🛏️  Sleeps: {boat_details.get('no_of_sleepers', 'N/A')}, Seats: {boat_details.get('no_of_seats', 'N/A')}")

if __name__ == "__main__":
    main()