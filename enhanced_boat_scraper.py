#!/usr/bin/env python3
"""
Enhanced Boat Scraper - Focus on Detailed Ad Pages
Extracts rich data from individual boat ad pages for comprehensive analysis
"""

import json
import base64
from urllib.parse import unquote
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import re

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EnhancedBoatScraper:
    """Enhanced scraper focusing on detailed ad data"""
    
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
    
    def parse_ad_list_for_urls(self, file_path: str) -> List[Dict]:
        """Parse ad list to get URLs for detailed scraping"""
        logger.info(f"Parsing ad list: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        soup = BeautifulSoup(html_content, 'html.parser')
        script_tag = soup.find('script', {'id': 'seoStructuredData'})

        if not script_tag:
            logger.error("Could not find seoStructuredData script tag")
            return []

        json_data = json.loads(script_tag.string)
        ads = json_data.get('mainEntity', {}).get('itemListElement', [])

        ad_urls = []
        for ad in ads:
            item = ad.get('item', {})
            offers = item.get('offers', {})
            
            url = item.get('url')
            if url and not url.startswith('http'):
                url = f"https://www.finn.no{url}"
            
            ad_urls.append({
                'url': url,
                'title': item.get('name'),
                'price': offers.get('price'),
                'brand': item.get('brand', {}).get('name') if item.get('brand') else None,
                'basic_description': item.get('description', '')
            })

        logger.info(f"Found {len(ad_urls)} ad URLs")
        return ad_urls
    
    def decode_data_props(self, data_props_string: str) -> Optional[Dict]:
        """Decode the data-props attribute with proper double URL decoding"""
        try:
            # Step 1: First URL decode (removes the outer encoding)
            first_decode = unquote(data_props_string)
            
            # Step 2: Base64 decode
            base64_decoded = base64.b64decode(first_decode)
            
            # Step 3: Second URL decode (the base64 contains URL-encoded JSON!)
            second_decode = unquote(base64_decoded.decode('utf-8'))
            
            # Step 4: Parse JSON
            json_data = json.loads(second_decode)
            
            return json_data
            
        except Exception as e:
            logger.error(f"Failed to decode data-props: {e}")
            return None
    
    def scrape_detailed_ad(self, url: str) -> Optional[Dict]:
        """Scrape detailed information from a single ad page"""
        try:
            logger.info(f"Scraping detailed ad: {url}")
            
            response = self.session.get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find the data-props div
            data_props_div = soup.find('div', {'id': 'mobility-item-page-root'})
            if not data_props_div or 'data-props' not in data_props_div.attrs:
                logger.warning(f"No data-props found in {url}")
                return None
            
            # Decode the rich data
            json_data = self.decode_data_props(data_props_div['data-props'])
            if not json_data or 'adData' not in json_data or 'ad' not in json_data['adData']:
                logger.warning(f"No valid ad data found in {url}")
                return None
            
            ad_data = json_data['adData']['ad']
            
            # Extract comprehensive boat information
            boat_info = self.extract_comprehensive_boat_data(ad_data)
            boat_info['source_url'] = url
            boat_info['scraped_at'] = datetime.now().isoformat()
            
            return boat_info
            
        except Exception as e:
            logger.error(f"Failed to scrape {url}: {e}")
            return None
    
    def extract_comprehensive_boat_data(self, ad_data: Dict) -> Dict:
        """Extract comprehensive boat information from ad data"""
        
        # Basic information
        basic_info = {
            'title': ad_data.get('title'),
            'price': ad_data.get('price'),
            'year': ad_data.get('year'),
            'condition': ad_data.get('condition'),
            'summary': ad_data.get('summary')
        }
        
        # Make and model with IDs
        make = ad_data.get('make', {})
        if isinstance(make, dict):
            basic_info['make'] = make.get('value')
            basic_info['make_id'] = make.get('id')
        else:
            basic_info['make'] = make
        
        basic_info['model'] = ad_data.get('model')
        
        # Technical specifications
        technical_specs = {
            'length': ad_data.get('length'),  # cm
            'width': ad_data.get('width'),    # cm
            'depth': ad_data.get('depth'),    # cm
            'weight': ad_data.get('weight'),  # kg
            'max_speed': ad_data.get('max_speed'),  # knots
            'sleepers': ad_data.get('no_of_sleepers'),
            'seats': ad_data.get('no_of_seats'),
            'lightnumber': ad_data.get('lightnumber')  # displacement ratio
        }
        
        # Material and classification
        material = ad_data.get('material', {})
        if isinstance(material, dict):
            technical_specs['material'] = material.get('value')
            technical_specs['material_id'] = material.get('id')
        
        boat_class = ad_data.get('boat_class', {})
        if isinstance(boat_class, dict):
            technical_specs['boat_class'] = boat_class.get('value')
            technical_specs['boat_class_id'] = boat_class.get('id')
        
        # Engine and propulsion
        motor_info = ad_data.get('motor', {})
        engine_details = {
            'motor_included': ad_data.get('motor_included'),
            'engine_make': motor_info.get('make') if motor_info else None,
            'engine_type': motor_info.get('motor_type', {}).get('value') if motor_info.get('motor_type') else None,
            'engine_size': motor_info.get('size') if motor_info else None,
            'fuel_type': motor_info.get('fuel', {}).get('value') if motor_info.get('fuel') else None
        }
        
        # Location data
        location_data = ad_data.get('location', {})
        location_info = {}
        if location_data:
            location_info = {
                'address': location_data.get('address'),
                'postal_code': location_data.get('postalCode'),
                'postal_name': location_data.get('postalName'),
                'municipality': location_data.get('municipality', {}).get('name'),
                'municipality_id': location_data.get('municipality', {}).get('id'),
                'county': location_data.get('county', {}).get('name'),
                'county_id': location_data.get('county', {}).get('id')
            }
        
        # Rich descriptions
        descriptions = {
            'main_description': ad_data.get('description_unsafe', ''),
            'equipment_description': ad_data.get('equipment_unsafe', '')
        }
        
        # Images
        images = ad_data.get('images', [])
        media_info = {
            'image_count': len(images),
            'images': images
        }
        
        # Additional metadata
        metadata = {
            'ad_view_type': ad_data.get('adViewType'),
            'ad_view_type_label': ad_data.get('adViewTypeLabel'),
            'anonymous': ad_data.get('anonymous'),
            'disposed': ad_data.get('disposed')
        }
        
        return {
            'basic_info': basic_info,
            'technical_specs': technical_specs,
            'engine_details': engine_details,
            'location_info': location_info,
            'descriptions': descriptions,
            'media_info': media_info,
            'metadata': metadata,
            'raw_ad_data': ad_data  # Keep for debugging and future expansion
        }
    
    def analyze_equipment_from_descriptions(self, descriptions: Dict) -> Dict:
        """Analyze equipment from rich descriptions"""
        full_text = f"{descriptions.get('main_description', '')} {descriptions.get('equipment_description', '')}".lower()
        
        # Equipment categories with Norwegian terms
        equipment_categories = {
            'navigation': {
                'keywords': ['gps', 'kartplotter', 'radar', 'kompass', 'ais', 'autopilot', 'vhf'],
                'found': []
            },
            'sails': {
                'keywords': ['storseil', 'foreseil', 'genoa', 'spinnaker', 'lazy bag', 'rullestorseil', 'rullegenoa'],
                'found': []
            },
            'comfort': {
                'keywords': ['varme', 'dieselvarmer', 'eberspacher', 'toalett', 'kjøkken', 'fryser', 'mikrobølgeovn', 'sprayhood'],
                'found': []
            },
            'safety': {
                'keywords': ['redningsflåte', 'livbåt', 'brannslokkingsapparat', 'nødraketter', 'epirb'],
                'found': []
            },
            'mechanical': {
                'keywords': ['vindlass', 'baugpropell', 'generator', 'inverter', 'solcellepanel', 'battery'],
                'found': []
            },
            'deck': {
                'keywords': ['bimini', 'dektent', 'cockpit', 'winch', 'reling', 'pulpit'],
                'found': []
            }
        }
        
        # Find equipment mentions
        for category, info in equipment_categories.items():
            for keyword in info['keywords']:
                if keyword in full_text:
                    info['found'].append(keyword)
        
        # Analyze condition indicators
        condition_analysis = {
            'positive': [],
            'neutral': [],
            'negative': []
        }
        
        positive_words = ['ny', 'nye', 'nytt', 'godt', 'utmerket', 'perfekt', 'velholdt', 'renovert', 'oppgradert']
        negative_words = ['defekt', 'skade', 'problem', 'reparasjon', 'slitt', 'trenger']
        
        for word in positive_words:
            if word in full_text:
                condition_analysis['positive'].append(word)
        
        for word in negative_words:
            if word in full_text:
                condition_analysis['negative'].append(word)
        
        return {
            'equipment_found': equipment_categories,
            'condition_indicators': condition_analysis,
            'description_length': len(full_text),
            'equipment_score': sum(len(cat['found']) for cat in equipment_categories.values())
        }
    
    def batch_scrape_detailed_ads(self, ad_urls: List[Dict], max_ads: int = 10, delay: float = 2.0) -> List[Dict]:
        """Batch scrape detailed ads with rate limiting"""
        logger.info(f"Starting batch scrape of {min(len(ad_urls), max_ads)} ads")
        
        detailed_boats = []
        
        for i, ad_info in enumerate(ad_urls[:max_ads], 1):
            logger.info(f"Processing ad {i}/{min(len(ad_urls), max_ads)}: {ad_info['title']}")
            
            # Scrape detailed data
            detailed_data = self.scrape_detailed_ad(ad_info['url'])
            
            if detailed_data:
                # Add equipment analysis
                equipment_analysis = self.analyze_equipment_from_descriptions(detailed_data['descriptions'])
                detailed_data['equipment_analysis'] = equipment_analysis
                
                # Add basic info from listing
                detailed_data['listing_info'] = {
                    'listing_title': ad_info['title'],
                    'listing_price': ad_info['price'],
                    'listing_brand': ad_info['brand']
                }
                
                detailed_boats.append(detailed_data)
                logger.info(f"✅ Successfully processed: {detailed_data['basic_info']['title']}")
            else:
                logger.warning(f"❌ Failed to process: {ad_info['title']}")
            
            # Rate limiting
            if i < min(len(ad_urls), max_ads):
                time.sleep(delay)
        
        logger.info(f"Completed batch scrape: {len(detailed_boats)} successful")
        return detailed_boats
    
    def save_detailed_analysis(self, boats_data: List[Dict], output_prefix: str = "detailed_boats"):
        """Save detailed analysis in multiple formats"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 1. Save full JSON data
        json_file = f"{output_prefix}_{timestamp}.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(boats_data, f, indent=2, ensure_ascii=False, default=str)
        logger.info(f"💾 Saved full JSON: {json_file}")
        
        # 2. Create flattened CSV for analysis
        flattened_data = []
        for boat in boats_data:
            flat_boat = {}
            
            # Flatten nested dictionaries
            for section, data in boat.items():
                if isinstance(data, dict) and section != 'raw_ad_data':
                    for key, value in data.items():
                        if isinstance(value, (str, int, float, bool)) or value is None:
                            flat_boat[f"{section}_{key}"] = value
                        elif isinstance(value, list) and key == 'found':
                            flat_boat[f"{section}_{key}"] = ', '.join(value) if value else ''
                        elif isinstance(value, dict):
                            for subkey, subvalue in value.items():
                                if isinstance(subvalue, (str, int, float, bool)) or subvalue is None:
                                    flat_boat[f"{section}_{key}_{subkey}"] = subvalue
                else:
                    if isinstance(data, (str, int, float, bool)) or data is None:
                        flat_boat[section] = data
            
            flattened_data.append(flat_boat)
        
        csv_file = f"{output_prefix}_{timestamp}.csv"
        df = pd.DataFrame(flattened_data)
        df.to_csv(csv_file, index=False, encoding='utf-8-sig')
        logger.info(f"📊 Saved CSV: {csv_file}")
        
        # 3. Generate summary report
        self._generate_summary_report(boats_data, f"{output_prefix}_summary_{timestamp}.txt")
        
        return {
            'json_file': json_file,
            'csv_file': csv_file,
            'boats_processed': len(boats_data)
        }
    
    def _generate_summary_report(self, boats_data: List[Dict], output_file: str):
        """Generate human-readable summary report"""
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("🛥️  DETAILED BOAT ANALYSIS SUMMARY\n")
            f.write("=" * 50 + "\n\n")
            
            f.write(f"📊 Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"🚤 Total Boats Analyzed: {len(boats_data)}\n\n")
            
            # Price statistics
            prices = [boat['basic_info']['price'] for boat in boats_data if boat['basic_info'].get('price')]
            if prices:
                f.write(f"💰 PRICE STATISTICS:\n")
                f.write(f"   Average: {sum(prices)/len(prices):,.0f} kr\n")
                f.write(f"   Median: {sorted(prices)[len(prices)//2]:,.0f} kr\n")
                f.write(f"   Range: {min(prices):,.0f} - {max(prices):,.0f} kr\n\n")
            
            # Year statistics
            years = [boat['basic_info']['year'] for boat in boats_data if boat['basic_info'].get('year')]
            if years:
                f.write(f"📅 YEAR STATISTICS:\n")
                f.write(f"   Average: {sum(years)/len(years):.0f}\n")
                f.write(f"   Range: {min(years)} - {max(years)}\n\n")
            
            # Top boats by equipment score
            equipment_scores = [(boat['basic_info']['title'], boat['equipment_analysis']['equipment_score']) 
                              for boat in boats_data]
            equipment_scores.sort(key=lambda x: x[1], reverse=True)
            
            f.write(f"🔧 TOP BOATS BY EQUIPMENT:\n")
            for i, (title, score) in enumerate(equipment_scores[:5], 1):
                f.write(f"   {i}. {title} (Score: {score})\n")
            f.write("\n")
            
            # Individual boat summaries
            f.write(f"🚤 INDIVIDUAL BOAT SUMMARIES:\n")
            f.write("-" * 30 + "\n\n")
            
            for i, boat in enumerate(boats_data, 1):
                basic = boat['basic_info']
                tech = boat['technical_specs']
                equip = boat['equipment_analysis']
                
                f.write(f"{i}. {basic.get('title', 'Unknown')}\n")
                f.write(f"   💰 Price: {basic.get('price', 'N/A'):,} kr\n" if basic.get('price') else "   💰 Price: Not specified\n")
                f.write(f"   📅 Year: {basic.get('year', 'N/A')}\n")
                f.write(f"   🏭 Make: {basic.get('make', 'N/A')}\n")
                f.write(f"   📏 Length: {tech.get('length', 'N/A')} cm\n")
                f.write(f"   🛏️  Sleeps: {tech.get('sleepers', 'N/A')}\n")
                f.write(f"   🔧 Equipment Score: {equip['equipment_score']}\n")
                f.write(f"   🔗 URL: {boat['source_url']}\n")
                f.write("\n")
        
        logger.info(f"📝 Saved summary report: {output_file}")

def main():
    """Main execution function"""
    
    print("🛥️  ENHANCED BOAT SCRAPER - DETAILED AD FOCUS")
    print("=" * 60)
    
    scraper = EnhancedBoatScraper()
    
    # 1. Parse ad list for URLs
    ad_list_file = 'finn_seilbåt_annonseliste.txt'
    ad_urls = scraper.parse_ad_list_for_urls(ad_list_file)
    
    if not ad_urls:
        print("❌ No ad URLs found")
        return
    
    print(f"📋 Found {len(ad_urls)} ad URLs from listing")
    
    # 2. Show sample for user to choose how many to process
    print(f"\n🔍 SAMPLE ADS FOUND:")
    for i, ad in enumerate(ad_urls[:5], 1):
        price_str = f"{ad['price']:,} kr" if ad['price'] else "Price TBD"
        print(f"{i}. {ad['title']} - {price_str}")
    
    # 3. Process detailed ads (limiting to reasonable number for demo)
    max_ads = min(10, len(ad_urls))  # Process up to 10 ads for demo
    print(f"\n🚀 Processing {max_ads} detailed ads...")
    
    detailed_boats = scraper.batch_scrape_detailed_ads(ad_urls, max_ads=max_ads, delay=1.0)
    
    if not detailed_boats:
        print("❌ No detailed boat data collected")
        return
    
    # 4. Save results
    print(f"\n💾 Saving results...")
    file_info = scraper.save_detailed_analysis(detailed_boats)
    
    # 5. Show summary
    print(f"\n🎉 ENHANCED SCRAPING COMPLETE!")
    print(f"✅ Successfully processed: {file_info['boats_processed']} boats")
    print(f"📄 Files generated:")
    print(f"   - JSON: {file_info['json_file']}")
    print(f"   - CSV: {file_info['csv_file']}")
    print(f"\n💡 The detailed data contains ~50x more information per boat!")
    print(f"🎯 Perfect for comprehensive market analysis and LLM evaluation")

if __name__ == "__main__":
    main()