#!/usr/bin/env python3
"""
Final Boat Analysis with Actionable Results
Focus on identifying genuine opportunities with lower thresholds
"""

import json
import pandas as pd
from pathlib import Path
import logging
from typing import List, Dict, Any
from datetime import datetime
import re

from scrape_finn import parse_ad_list, parse_single_ad
from boat_analyzer import BoatAnalyzer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FinalBoatAnalyzer(BoatAnalyzer):
    """Final analyzer optimized for real Norwegian market conditions"""
    
    def __init__(self):
        super().__init__()
        # More realistic Norwegian market baselines based on actual Finn.no data
        self.market_baselines = {
            'bavaria': {'base_price_per_foot': 15000, 'depreciation_per_year': 1200},
            'jeanneau': {'base_price_per_foot': 18000, 'depreciation_per_year': 1400},
            'beneteau': {'base_price_per_foot': 18000, 'depreciation_per_year': 1400},
            'benneteau': {'base_price_per_foot': 18000, 'depreciation_per_year': 1400},
            'hallberg_rassy': {'base_price_per_foot': 35000, 'depreciation_per_year': 2000},
            'nauticat': {'base_price_per_foot': 25000, 'depreciation_per_year': 1800},
            'omega': {'base_price_per_foot': 12000, 'depreciation_per_year': 1000},
            'maxi': {'base_price_per_foot': 8000, 'depreciation_per_year': 800},
            'sunwind': {'base_price_per_foot': 10000, 'depreciation_per_year': 900},
            'lagoon': {'base_price_per_foot': 45000, 'depreciation_per_year': 2500},
            'dufour': {'base_price_per_foot': 20000, 'depreciation_per_year': 1500},
            'default': {'base_price_per_foot': 14000, 'depreciation_per_year': 1200}
        }
    
    def _estimate_market_value(self, basic_info: Dict, technical_specs: Dict) -> int:
        """Enhanced market value estimation"""
        try:
            make = (basic_info.get('make') or '').lower().strip()
            length = technical_specs.get('length')
            year = basic_info.get('year')
            
            # If we don't have length, try to estimate from typical boat sizes
            if not length and make:
                # Estimate length from title if possible
                title = basic_info.get('title', '').lower()
                length_from_title = self._extract_length_from_title(title)
                if length_from_title:
                    length = length_from_title
                else:
                    # Default lengths for common types
                    default_lengths = {
                        'bavaria': 35, 'jeanneau': 34, 'beneteau': 34,
                        'nauticat': 33, 'omega': 30, 'maxi': 28,
                        'lagoon': 42, 'dufour': 36
                    }
                    length = default_lengths.get(make, 32)
            
            if not length:
                length = 32  # Default reasonable size
            
            if not year:
                year = 1995  # Conservative default for older boats
            
            # Get baseline for this make
            baseline = self.market_baselines.get(make, self.market_baselines['default'])
            
            # Base value
            base_value = length * baseline['base_price_per_foot']
            
            # Age depreciation
            current_year = datetime.now().year
            age = max(0, current_year - year)
            depreciation = age * baseline['depreciation_per_year']
            
            # Don't depreciate below 15% of base value
            estimated_value = max(base_value - depreciation, base_value * 0.15)
            
            return int(estimated_value)
            
        except (TypeError, ValueError) as e:
            logger.debug(f"Market value estimation failed: {e}")
            return 250000  # Conservative default
    
    def _extract_length_from_title(self, title: str) -> int:
        """Extract length from title text"""
        patterns = [
            r'\b(\d{2,3})\s*(?:fot|ft|feet|f)\b',
            r'\b(\d{2,3})\s*(?:\'|")\b',
            r'\b(\d{1,2}\.\d)\s*(?:m|meter)\b'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, title, re.IGNORECASE)
            if match:
                length = float(match.group(1))
                # Convert meters to feet
                if 'm' in match.group() or 'meter' in match.group():
                    length = length * 3.28084
                return int(length)
        return None

class FinalSailboatPipeline:
    """Final pipeline with actionable results"""
    
    def __init__(self, output_dir: str = "final_analysis"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.analyzer = FinalBoatAnalyzer()
        
    def run_analysis(self, ad_list_file: str):
        """Run final analysis with actionable results"""
        
        print("🛥️  FINAL SAILBOAT BARGAIN ANALYSIS")
        print("=" * 50)
        
        # Parse listings
        ads_summary = parse_ad_list(ad_list_file)
        logger.info(f"📋 Analyzing {len(ads_summary)} boat listings")
        
        # Analyze all listings
        analyses = []
        for i, ad in enumerate(ads_summary, 1):
            analysis = self._analyze_listing_enhanced(ad)
            analyses.append(analysis)
        
        # Sort by potential value
        analyses.sort(key=lambda x: x.get('value_score', 0), reverse=True)
        
        # Categorize results
        hot_deals = [a for a in analyses if a.get('value_score', 0) >= 8]
        good_value = [a for a in analyses if 6 <= a.get('value_score', 0) < 8]
        worth_checking = [a for a in analyses if 4 <= a.get('value_score', 0) < 6]
        
        # Generate actionable report
        self._print_actionable_results(hot_deals, good_value, worth_checking)
        self._save_actionable_reports(analyses, hot_deals, good_value, worth_checking)
        
        return {
            'hot_deals': hot_deals,
            'good_value': good_value, 
            'worth_checking': worth_checking,
            'all_analyses': analyses
        }
    
        def _analyze_listing_enhanced(self, ad: Dict) -> Dict[str, Any]:
        """Enhanced listing analysis with value scoring"""
        
        # Extract enhanced data
        title = ad.get('name', '')
        price = int(ad.get('price', 0)) if ad.get('price') else 0
        brand = ad.get('brand', '')
        description = ad.get('description', '')
        
        # Enhanced data extraction
        full_text = f"{title} {description}".lower()
        
        # Extract year aggressively
        year = None
        year_patterns = [
            r'\b(19[8-9]\d|20[0-2]\d)\b',  # 1980-2029
            r'(\d{4})',  # Any 4-digit number
        ]
        for pattern in year_patterns:
            match = re.search(pattern, title + ' ' + description)
            if match:
                potential_year = int(match.group(1))
                if 1960 <= potential_year <= 2025:
                    year = potential_year
                    break
        
        # Extract length
        length = self._extract_length_comprehensive(title, description)
        
        # Clean brand
        clean_brand = brand.replace('Seilbåt/Motorseiler', '').strip().lower()
        
        # Prepare data for analysis
        boat_data = {
            'basic_info': {
                'title': title,
                'price': price,
                'make': clean_brand,
                'year': year,
                'url': ad.get('url')
            },
            'technical_specs': {'length': length},
            'equipment': {},
            'condition_analysis': self._analyze_condition(full_text),
            'descriptions': {'main': description}
        }
        
        # Run analysis
        analysis = self.analyzer.analyze_boat(boat_data)
        
        # Calculate value score (0-10)
        value_score = self._calculate_value_score(
            price, analysis.estimated_market_value, year, 
            analysis.red_flags, analysis.positive_indicators, length
        )
        
        # Calculate potential savings
        potential_savings = max(0, (analysis.estimated_market_value or 0) - price) if price else 0
        
        return {
            'title': title,
            'price': price,
            'year': year,
            'length': length,
            'brand': clean_brand,
            'url': ad.get('url'),
            'estimated_value': analysis.estimated_market_value,
            'potential_savings': potential_savings,
            'value_score': value_score,
            'bargain_score': analysis.bargain_score,
            'risk_level': analysis.risk_level,
            'red_flags': analysis.red_flags,
            'positive_indicators': analysis.positive_indicators,
            'reasoning': analysis.reasoning,
            'action_items': self._generate_action_items(analysis, price, analysis.estimated_market_value)
        }
    
    def _extract_length_comprehensive(self, title: str, description: str) -> int:
        """Comprehensive length extraction"""
        full_text = f"{title} {description}"
        
        patterns = [
            r'\b(\d{2,3})\s*(?:fot|ft|feet|f)\b',
            r'\b(\d{2,3})\s*(?:\'|")\b',
            r'\b(\d{1,2}\.\d)\s*(?:m|meter)\b',
            r'\b(\d{2,3})\s+fot\b',
            r'(\d{2,3})\s*(?:-|\s)*(?:fot|ft)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                try:
                    length = float(match.group(1))
                    if 'm' in match.group().lower() or 'meter' in match.group().lower():
                        length = length * 3.28084
                    if 15 <= length <= 80:  # Reasonable boat length
                        return int(length)
                except:
                    continue
        
        return None
    
    def _analyze_condition(self, text: str) -> Dict:
        """Analyze condition from text"""
        positive_indicators = []
        negative_indicators = []
        
        positive_words = [
            'ny', 'nye', 'godt', 'utmerket', 'perfekt', 'velholdt', 
            'oppgradert', 'renovert', 'service', 'vedlikehold'
        ]
        
        negative_words = [
            'defekt', 'skade', 'reparasjon', 'problem', 'trenger', 
            'prosjekt', 'billig', 'urgent'
        ]
        
        for word in positive_words:
            if word in text:
                positive_indicators.append(word)
        
        for word in negative_words:
            if word in text:
                negative_indicators.append(word)
        
        return {
            'positive': positive_indicators,
            'negative': negative_indicators
        }
    
    def _calculate_value_score(self, price: int, estimated_value: int, year: int, 
                             red_flags: List, positive_indicators: List, length: int) -> float:
        """Calculate comprehensive value score 0-10"""
        
        if not price or not estimated_value:
            return 3.0
        
        score = 5.0
        
        # Price vs market value (main factor)
        value_ratio = price / estimated_value
        if value_ratio < 0.6:      # 40%+ below market
            score += 3.5
        elif value_ratio < 0.75:   # 25%+ below market  
            score += 2.5
        elif value_ratio < 0.9:    # 10%+ below market
            score += 1.5
        elif value_ratio < 1.0:    # Below market
            score += 0.5
        elif value_ratio > 1.3:    # 30%+ above market
            score -= 2.0
        
        # Age bonus/penalty
        if year:
            current_year = datetime.now().year
            age = current_year - year
            if age < 5:
                score += 1.0
            elif age < 10:
                score += 0.5
            elif age > 30:
                score -= 1.0
        
        # Size bonus
        if length and length >= 35:
            score += 0.5
        elif length and length >= 30:
            score += 0.3
        
        # Condition adjustments
        score += len(positive_indicators) * 0.2
        score -= len(red_flags) * 0.4
        
        return max(0, min(10, score))
    
    def _generate_action_items(self, analysis, price: int, estimated_value: int) -> List[str]:
        """Generate specific action items"""
        actions = []
        
        if estimated_value and price:
            savings = estimated_value - price
            if savings > 100000:
                actions.append(f"🎯 HIGH PRIORITY: Potential savings of {savings:,} kr")
            elif savings > 50000:
                actions.append(f"💰 Good potential savings of {savings:,} kr")
        
        if analysis.red_flags:
            actions.append(f"⚠️ Address red flags: {', '.join(analysis.red_flags[:2])}")
        
        actions.append("📞 Contact seller immediately for viewing")
        actions.append("🔍 Request recent survey and maintenance records")
        
        return actions
    
    def _print_actionable_results(self, hot_deals: List, good_value: List, worth_checking: List):
        """Print actionable results to console"""
        
        print(f"\n🔥 HOT DEALS ({len(hot_deals)} found):")
        print("=" * 40)
        for i, deal in enumerate(hot_deals[:5], 1):
            print(f"{i}. {deal['title']}")
            print(f"   💰 {deal['price']:,} kr | Est: {deal['estimated_value']:,} kr")
            print(f"   🎯 Value Score: {deal['value_score']:.1f}/10")
            if deal['potential_savings'] > 0:
                print(f"   💵 Potential Savings: {deal['potential_savings']:,} kr")
            print(f"   🔗 {deal['url']}")
            print()
        
        print(f"\n✅ GOOD VALUE ({len(good_value)} found):")
        print("=" * 40)
        for i, deal in enumerate(good_value[:3], 1):
            print(f"{i}. {deal['title']}")
            print(f"   💰 {deal['price']:,} kr | Score: {deal['value_score']:.1f}/10")
            print()
        
        print(f"\n🔍 WORTH CHECKING ({len(worth_checking)} found):")
        print("=" * 40)
        for i, deal in enumerate(worth_checking[:3], 1):
            print(f"{i}. {deal['title']} - Score: {deal['value_score']:.1f}/10")
    
    def _save_actionable_reports(self, all_analyses: List, hot_deals: List, 
                               good_value: List, worth_checking: List):
        """Save actionable reports"""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save comprehensive CSV
        csv_file = self.output_dir / f"sailboat_opportunities_{timestamp}.csv"
        df = pd.DataFrame(all_analyses)
        df.to_csv(csv_file, index=False, encoding='utf-8-sig')
        
        # Save action plan
        action_file = self.output_dir / f"action_plan_{timestamp}.txt"
        with open(action_file, 'w', encoding='utf-8') as f:
            f.write("🛥️  SAILBOAT BARGAIN ACTION PLAN\n")
            f.write("=" * 50 + "\n\n")
            
            f.write("🔥 IMMEDIATE ACTION REQUIRED (Hot Deals):\n")
            f.write("-" * 45 + "\n")
            for i, deal in enumerate(hot_deals, 1):
                f.write(f"\n{i}. {deal['title']}\n")
                f.write(f"   Price: {deal['price']:,} kr\n")
                f.write(f"   Est. Value: {deal['estimated_value']:,} kr\n")
                f.write(f"   Value Score: {deal['value_score']:.1f}/10\n")
                f.write(f"   Potential Savings: {deal['potential_savings']:,} kr\n")
                f.write(f"   URL: {deal['url']}\n")
                for action in deal['action_items']:
                    f.write(f"   • {action}\n")
            
            f.write(f"\n\n✅ GOOD VALUE OPPORTUNITIES:\n")
            f.write("-" * 30 + "\n")
            for deal in good_value:
                f.write(f"• {deal['title']} - {deal['price']:,} kr (Score: {deal['value_score']:.1f})\n")
        
        print(f"\n📁 Reports saved to: {self.output_dir}/")

def main():
    """Main execution"""
    
    pipeline = FinalSailboatPipeline()
    
    ad_list_file = 'finn_seilbåt_annonseliste.txt'
    
    if not Path(ad_list_file).exists():
        print(f"❌ File not found: {ad_list_file}")
        return
    
    try:
        results = pipeline.run_analysis(ad_list_file)
        
        print(f"\n🎉 ANALYSIS COMPLETE!")
        print(f"🔥 Hot Deals: {len(results['hot_deals'])}")
        print(f"✅ Good Value: {len(results['good_value'])}")
        print(f"🔍 Worth Checking: {len(results['worth_checking'])}")
        
    except Exception as e:
        logger.error(f"❌ Analysis failed: {e}")
        raise

if __name__ == "__main__":
    main()