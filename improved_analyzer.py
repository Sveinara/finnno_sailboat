#!/usr/bin/env python3
"""
Improved Boat Analysis Pipeline
Better criteria and analysis for real-world Finn.no data
"""

import json
import pandas as pd
from pathlib import Path
import logging
from typing import List, Dict, Any
from datetime import datetime
import re

# Import our modules
from scrape_finn import parse_ad_list, parse_single_ad
from boat_analyzer import BoatAnalyzer

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ImprovedBoatAnalyzer(BoatAnalyzer):
    """Improved analyzer with better criteria for listing data"""
    
    def __init__(self):
        super().__init__()
        # Adjust market baselines for Norwegian market
        self.market_baselines = {
            'bavaria': {'base_price_per_foot': 12000, 'depreciation_per_year': 1000},
            'jeanneau': {'base_price_per_foot': 14000, 'depreciation_per_year': 1200},
            'beneteau': {'base_price_per_foot': 14000, 'depreciation_per_year': 1200},
            'benneteau': {'base_price_per_foot': 14000, 'depreciation_per_year': 1200},  # Common misspelling
            'hallberg_rassy': {'base_price_per_foot': 25000, 'depreciation_per_year': 1500},
            'nauticat': {'base_price_per_foot': 18000, 'depreciation_per_year': 1200},
            'omega': {'base_price_per_foot': 8000, 'depreciation_per_year': 800},
            'maxi': {'base_price_per_foot': 6000, 'depreciation_per_year': 600},
            'default': {'base_price_per_foot': 10000, 'depreciation_per_year': 800}
        }
    
    def _identify_red_flags(self, condition_analysis: Dict, descriptions: Dict) -> List[str]:
        """Improved red flag detection for listing data"""
        red_flags = []
        
        # From condition analysis
        negative_flags = condition_analysis.get('negative', [])
        red_flags.extend(negative_flags)
        
        # Check descriptions for critical issues
        full_text = f"{descriptions.get('main', '')} {descriptions.get('equipment', '')}".lower()
        
        # More targeted red flags for listings
        critical_flags = [
            'defekt motor', 'defekt', 'hull damage', 'osmose', 'rot', 
            'ingen papirer', 'urgent sale', 'must sell', 'divorce',
            'prosjekt', 'project', 'trenger reparasjon'
        ]
        
        for flag in critical_flags:
            if flag.lower() in full_text:
                red_flags.append(f"Mentions: {flag}")
        
        # Don't penalize short descriptions for listings (common on Finn.no)
        # Only flag if extremely short (< 20 chars)
        if len(full_text) < 20:
            red_flags.append("Extremely short description")
        
        # Check for urgency indicators
        urgency_words = ['må selges', 'kjapt', 'urgent', 'asap']
        for word in urgency_words:
            if word in full_text:
                red_flags.append(f"Urgency: {word}")
        
        return red_flags
    
    def _calculate_bargain_score(self, basic_info: Dict, technical_specs: Dict, 
                                condition_analysis: Dict, descriptions: Dict) -> float:
        """Improved bargain scoring for listing data"""
        score = 5.0  # Start neutral
        
        # Price vs estimated value (main factor)
        asking_price = basic_info.get('price')
        estimated_value = self._estimate_market_value(basic_info, technical_specs)
        
        if asking_price and estimated_value:
            price_ratio = asking_price / estimated_value
            if price_ratio < 0.5:  # 50% below market - excellent
                score += 4.0
            elif price_ratio < 0.7:  # 30% below market - very good
                score += 3.0
            elif price_ratio < 0.85:  # 15% below market - good
                score += 2.0
            elif price_ratio < 1.0:  # Below market - decent
                score += 1.0
            elif price_ratio > 1.3:  # 30% above market - poor
                score -= 2.0
            elif price_ratio > 1.5:  # 50% above market - very poor
                score -= 3.0
        
        # Condition indicators (lighter weight for listings)
        positive_flags = condition_analysis.get('positive', [])
        negative_flags = condition_analysis.get('negative', [])
        
        score += len(positive_flags) * 0.2
        score -= len(negative_flags) * 0.3
        
        # Age factor
        year = basic_info.get('year')
        if year:
            current_year = datetime.now().year
            age = current_year - year
            if age < 5:
                score += 1.0  # New boats are valuable
            elif age < 10:
                score += 0.5
            elif age > 30:
                score -= 0.5  # Very old boats need more attention
        
        # Size factor (larger boats often better value)
        length = technical_specs.get('length')
        if length:
            if length >= 35:
                score += 0.5
            elif length >= 30:
                score += 0.3
        
        return max(0, min(10, score))
    
    def _determine_risk_level(self, red_flags: List[str], bargain_score: float) -> str:
        """Improved risk assessment"""
        critical_red_flags = [flag for flag in red_flags if 'defekt' in flag.lower() or 'prosjekt' in flag.lower()]
        
        if len(critical_red_flags) >= 1:
            return "HIGH"
        elif len(red_flags) >= 2:
            return "MEDIUM"
        elif bargain_score > 8.5:  # Too good to be true
            return "HIGH"
        elif bargain_score < 3:
            return "MEDIUM"
        else:
            return "LOW"

class ImprovedSailboatPipeline:
    """Improved pipeline with better analysis"""
    
    def __init__(self, output_dir: str = "improved_analysis"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.analyzer = ImprovedBoatAnalyzer()
        
    def run_analysis(self, ad_list_file: str):
        """Run improved analysis pipeline"""
        
        logger.info("🚀 Starting Improved Sailboat Analysis Pipeline")
        
        # Parse ad listings
        ads_summary = parse_ad_list(ad_list_file)
        logger.info(f"📋 Found {len(ads_summary)} boat listings")
        
        # Analyze all listings
        analyses = []
        for i, ad in enumerate(ads_summary, 1):
            analysis = self._analyze_listing(ad)
            analyses.append(analysis)
            if i % 10 == 0:
                logger.info(f"✅ Analyzed {i}/{len(ads_summary)} listings")
        
        # Sort by bargain score
        analyses.sort(key=lambda x: x['bargain_score'], reverse=True)
        
        # Identify different categories
        excellent_bargains = [a for a in analyses if a['bargain_score'] >= 7.5 and a['risk_level'] != 'HIGH']
        good_bargains = [a for a in analyses if a['bargain_score'] >= 6.5 and a['bargain_score'] < 7.5 and a['risk_level'] != 'HIGH']
        risky_bargains = [a for a in analyses if a['bargain_score'] >= 6.0 and a['risk_level'] == 'HIGH']
        
        # Generate comprehensive report
        report_data = {
            'analysis_date': datetime.now().isoformat(),
            'total_listings': len(ads_summary),
            'excellent_bargains': excellent_bargains,
            'good_bargains': good_bargains,
            'risky_bargains': risky_bargains,
            'all_analyses': analyses
        }
        
        self._save_comprehensive_reports(report_data)
        
        logger.info("✅ Improved analysis complete!")
        return report_data
    
    def _analyze_listing(self, ad: Dict) -> Dict[str, Any]:
        """Analyze individual listing with enhanced extraction"""
        
        # Enhanced data extraction
        quick_boat_data = {
            'basic_info': {
                'title': ad.get('name', ''),
                'price': ad.get('price'),
                'make': self._extract_make(ad.get('brand', '')),
                'url': ad.get('url')
            },
            'technical_specs': {},
            'equipment': {},
            'condition_analysis': {'positive': [], 'negative': []},
            'descriptions': {'main': ad.get('description', '')}
        }
        
        # Enhanced extraction from title and description
        full_text = f"{ad.get('name', '')} {ad.get('description', '')}"
        
        # Extract year more aggressively
        year_match = re.search(r'\b(19[7-9]\d|20[0-2]\d)\b', full_text)
        if year_match:
            quick_boat_data['basic_info']['year'] = int(year_match.group())
        
        # Extract length more aggressively
        length_patterns = [
            r'\b(\d{2,3})\s*(?:fot|ft|feet|f)\b',
            r'\b(\d{2,3})\s*(?:\'|"|\s+fot)\b',
            r'\b(\d{1,2}\.\d)\s*(?:m|meter)\b'  # Convert meters to feet
        ]
        
        for pattern in length_patterns:
            length_match = re.search(pattern, full_text, re.IGNORECASE)
            if length_match:
                length = float(length_match.group(1))
                # Convert meters to feet if needed
                if 'm' in length_match.group() or 'meter' in length_match.group():
                    length = length * 3.28084
                quick_boat_data['technical_specs']['length'] = int(length)
                break
        
        # Enhanced condition analysis
        description = full_text.lower()
        
        positive_words = ['ny', 'nye', 'godt', 'utmerket', 'perfekt', 'velholdt', 'oppgradert', 'renovert']
        negative_words = ['defekt', 'skade', 'reparasjon', 'problem', 'trenger', 'prosjekt']
        
        for word in positive_words:
            if word in description:
                quick_boat_data['condition_analysis']['positive'].append(word)
        
        for word in negative_words:
            if word in description:
                quick_boat_data['condition_analysis']['negative'].append(word)
        
        # Run analysis
        analysis = self.analyzer.analyze_boat(quick_boat_data)
        
        # Calculate potential savings
        potential_savings = 0
        if analysis.estimated_market_value and quick_boat_data['basic_info']['price']:
            potential_savings = analysis.estimated_market_value - quick_boat_data['basic_info']['price']
        
        return {
            'title': ad.get('name'),
            'price': quick_boat_data['basic_info']['price'],
            'year': quick_boat_data['basic_info'].get('year'),
            'length': quick_boat_data['technical_specs'].get('length'),
            'brand': quick_boat_data['basic_info']['make'],
            'url': ad.get('url'),
            'bargain_score': analysis.bargain_score,
            'risk_level': analysis.risk_level,
            'estimated_market_value': analysis.estimated_market_value,
            'potential_savings': potential_savings,
            'red_flags': analysis.red_flags,
            'positive_indicators': analysis.positive_indicators,
            'reasoning': analysis.reasoning,
            'seller_questions': analysis.seller_questions[:7]
        }
    
    def _extract_make(self, brand_text: str) -> str:
        """Extract boat make from brand text"""
        if not brand_text:
            return ''
        
        # Remove "Seilbåt/Motorseiler" suffix
        clean_brand = brand_text.replace('Seilbåt/Motorseiler', '').strip()
        return clean_brand.lower()
    
    def _save_comprehensive_reports(self, report_data: Dict):
        """Save comprehensive reports"""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save detailed CSV
        csv_file = self.output_dir / f"detailed_analysis_{timestamp}.csv"
        df = pd.DataFrame(report_data['all_analyses'])
        df.to_csv(csv_file, index=False, encoding='utf-8-sig')
        logger.info(f"💾 Saved detailed CSV: {csv_file}")
        
        # Save comprehensive summary
        summary_file = self.output_dir / f"bargain_report_{timestamp}.txt"
        with open(summary_file, 'w', encoding='utf-8') as f:
            self._write_comprehensive_summary(f, report_data)
        logger.info(f"📊 Saved comprehensive report: {summary_file}")
        
        # Save top bargains JSON for further processing
        json_file = self.output_dir / f"top_bargains_{timestamp}.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump({
                'excellent_bargains': report_data['excellent_bargains'],
                'good_bargains': report_data['good_bargains'],
                'risky_bargains': report_data['risky_bargains']
            }, f, indent=2, ensure_ascii=False, default=str)
        logger.info(f"🔧 Saved JSON data: {json_file}")
    
    def _write_comprehensive_summary(self, f, report_data: Dict):
        """Write comprehensive analysis summary"""
        
        f.write("🛥️  COMPREHENSIVE FINN.NO SAILBOAT ANALYSIS\n")
        f.write("=" * 60 + "\n\n")
        
        f.write(f"📅 Analysis Date: {report_data['analysis_date']}\n")
        f.write(f"📊 Total Listings Analyzed: {report_data['total_listings']}\n\n")
        
        f.write("📈 SUMMARY STATISTICS:\n")
        f.write("-" * 25 + "\n")
        f.write(f"🏆 Excellent Bargains (7.5+ score, low/med risk): {len(report_data['excellent_bargains'])}\n")
        f.write(f"✅ Good Bargains (6.5-7.4 score, low/med risk): {len(report_data['good_bargains'])}\n")
        f.write(f"⚠️  Risky High-Score Deals (6.0+ score, high risk): {len(report_data['risky_bargains'])}\n\n")
        
        # Excellent bargains section
        if report_data['excellent_bargains']:
            f.write("🏆 EXCELLENT BARGAINS (PRIORITY LIST)\n")
            f.write("=" * 45 + "\n\n")
            
            for i, boat in enumerate(report_data['excellent_bargains'], 1):
                self._write_boat_details(f, boat, i)
        
        # Good bargains section
        if report_data['good_bargains']:
            f.write("\n✅ GOOD BARGAINS (WORTH INVESTIGATING)\n")
            f.write("=" * 45 + "\n\n")
            
            for i, boat in enumerate(report_data['good_bargains'], 1):
                self._write_boat_details(f, boat, i, detailed=False)
        
        # Risky bargains section
        if report_data['risky_bargains']:
            f.write("\n⚠️  RISKY HIGH-SCORE DEALS (PROCEED WITH CAUTION)\n")
            f.write("=" * 55 + "\n\n")
            
            for i, boat in enumerate(report_data['risky_bargains'], 1):
                self._write_boat_details(f, boat, i, detailed=False)
    
    def _write_boat_details(self, f, boat: Dict, index: int, detailed: bool = True):
        """Write detailed boat information"""
        
        f.write(f"{index}. {boat['title']}\n")
        f.write("   " + "=" * (len(boat['title']) + 3) + "\n")
        
        # Basic info
        f.write(f"   💰 Price: {boat['price']:,} kr\n")
        if boat['year']:
            f.write(f"   📅 Year: {boat['year']}\n")
        if boat['length']:
            f.write(f"   📏 Length: {boat['length']} ft\n")
        f.write(f"   🏭 Brand: {boat['brand']}\n")
        
        # Analysis results
        f.write(f"   ⭐ Bargain Score: {boat['bargain_score']:.1f}/10\n")
        f.write(f"   🛡️  Risk Level: {boat['risk_level']}\n")
        
        if boat['estimated_market_value']:
            f.write(f"   📈 Est. Market Value: {boat['estimated_market_value']:,} kr\n")
            if boat['potential_savings'] > 0:
                f.write(f"   💵 Potential Savings: {boat['potential_savings']:,} kr\n")
        
        f.write(f"   🔗 URL: {boat['url']}\n")
        
        if detailed:
            f.write(f"   💭 Analysis: {boat['reasoning']}\n")
            
            if boat['red_flags']:
                f.write(f"   🚩 Red Flags: {', '.join(boat['red_flags'])}\n")
            
            if boat['positive_indicators']:
                f.write(f"   ✅ Positives: {', '.join(boat['positive_indicators'])}\n")
            
            f.write(f"   ❓ Key Questions for Seller:\n")
            for j, question in enumerate(boat['seller_questions'][:5], 1):
                f.write(f"      {j}. {question}\n")
        
        f.write("\n" + "-" * 50 + "\n\n")

def main():
    """Main execution"""
    
    print("🛥️  IMPROVED SAILBOAT BARGAIN HUNTER")
    print("=" * 45)
    
    pipeline = ImprovedSailboatPipeline()
    
    ad_list_file = 'finn_seilbåt_annonseliste.txt'
    
    if not Path(ad_list_file).exists():
        logger.error(f"❌ File not found: {ad_list_file}")
        return
    
    try:
        results = pipeline.run_analysis(ad_list_file)
        
        print(f"\n🎉 IMPROVED ANALYSIS COMPLETE!")
        print(f"📊 Analyzed {results['total_listings']} listings")
        print(f"🏆 Excellent Bargains: {len(results['excellent_bargains'])}")
        print(f"✅ Good Bargains: {len(results['good_bargains'])}")
        print(f"⚠️  Risky High-Score: {len(results['risky_bargains'])}")
        
        # Show top finds
        all_good = results['excellent_bargains'] + results['good_bargains']
        if all_good:
            print(f"\n🎯 TOP FINDS:")
            for i, boat in enumerate(all_good[:5], 1):
                score_emoji = "🏆" if boat['bargain_score'] >= 7.5 else "✅"
                savings = f" (Save: {boat['potential_savings']:,} kr)" if boat['potential_savings'] > 0 else ""
                print(f"{i}. {score_emoji} {boat['title']}")
                print(f"   💰 {boat['price']:,} kr | ⭐ {boat['bargain_score']:.1f}/10{savings}")
        
        print(f"\n📁 Detailed reports saved to: improved_analysis/")
        
    except Exception as e:
        logger.error(f"❌ Analysis failed: {e}")
        raise

if __name__ == "__main__":
    main()