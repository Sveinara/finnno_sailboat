#!/usr/bin/env python3
"""
Main Boat Analysis Pipeline
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

class SailboatAnalysisPipeline:
    """Complete pipeline for analyzing sailboat listings"""
    
    def __init__(self, output_dir: str = "analysis_output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.analyzer = BoatAnalyzer()
        
    def run_full_analysis(self, ad_list_file: str, sample_detailed_ad: str = None):
        """Run the complete analysis pipeline"""
        
        logger.info("Starting Sailboat Analysis Pipeline")
        
        # Parse ad listings
        ads_summary = parse_ad_list(ad_list_file)
        logger.info(f"Found {len(ads_summary)} boat listings")
        
        # Quick analysis of all listings
        quick_analyses = []
        for ad in ads_summary:
            quick_analysis = self._quick_analyze_listing(ad)
            quick_analyses.append(quick_analysis)
        
        # Identify top bargains
        top_bargains = self._identify_top_bargains(quick_analyses)
        
        # Generate reports
        report_data = {
            'total_listings': len(ads_summary),
            'analysis_date': datetime.now().isoformat(),
            'top_bargains': top_bargains,
            'all_listings': quick_analyses
        }
        
        self._save_reports(report_data)
        
        logger.info("Analysis pipeline complete!")
        return report_data
    
    def _quick_analyze_listing(self, ad: Dict) -> Dict[str, Any]:
        """Quick analysis for listings"""
        
        # Convert ad format to analysis format
        quick_boat_data = {
            'basic_info': {
                'title': ad.get('name'),
                'price': ad.get('price'),
                'make': ad.get('brand'),
                'url': ad.get('url')
            },
            'technical_specs': {},
            'equipment': {},
            'condition_analysis': {'positive': [], 'negative': []},
            'descriptions': {'main': ad.get('description', '')}
        }
        
        # Extract info from description
        description = (ad.get('description') or '').lower()
        
        # Try to extract year
        year_match = re.search(r'\b(19|20)\d{2}\b', ad.get('name', '') + ' ' + description)
        if year_match:
            quick_boat_data['basic_info']['year'] = int(year_match.group())
        
        # Try to extract length
        length_match = re.search(r'\b(\d{2,3})\s*(?:fot|ft|feet|f)\b', ad.get('name', '') + ' ' + description)
        if length_match:
            quick_boat_data['technical_specs']['length'] = int(length_match.group(1))
        
        # Basic condition analysis
        positive_words = ['ny', 'godt', 'utmerket', 'perfekt', 'velholdt']
        negative_words = ['defekt', 'skade', 'reparasjon', 'problem']
        
        for word in positive_words:
            if word in description:
                quick_boat_data['condition_analysis']['positive'].append(word)
        
        for word in negative_words:
            if word in description:
                quick_boat_data['condition_analysis']['negative'].append(word)
        
        # Run analysis
        analysis = self.analyzer.analyze_boat(quick_boat_data)
        
        return {
            'title': ad.get('name'),
            'price': ad.get('price'),
            'brand': ad.get('brand'),
            'url': ad.get('url'),
            'bargain_score': analysis.bargain_score,
            'risk_level': analysis.risk_level,
            'estimated_market_value': analysis.estimated_market_value,
            'red_flags': analysis.red_flags,
            'positive_indicators': analysis.positive_indicators,
            'reasoning': analysis.reasoning,
            'top_seller_questions': analysis.seller_questions[:5]
        }
    
    def _identify_top_bargains(self, analyses: List[Dict]) -> List[Dict]:
        """Identify top potential bargains"""
        
        sorted_analyses = sorted(analyses, key=lambda x: x['bargain_score'], reverse=True)
        
        top_bargains = []
        for analysis in sorted_analyses:
            if (analysis['bargain_score'] >= 6.0 and 
                analysis['risk_level'] != 'HIGH' and
                len(top_bargains) < 10):
                top_bargains.append(analysis)
        
        return top_bargains
    
    def _save_reports(self, report_data: Dict):
        """Save various report formats"""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save CSV
        csv_file = self.output_dir / f"boat_analysis_{timestamp}.csv"
        df = pd.DataFrame(report_data['all_listings'])
        df.to_csv(csv_file, index=False, encoding='utf-8-sig')
        logger.info(f"Saved CSV: {csv_file}")
        
        # Save summary
        summary_file = self.output_dir / f"top_bargains_{timestamp}.txt"
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write("FINN.NO SAILBOAT ANALYSIS REPORT\n")
            f.write("=" * 40 + "\n\n")
            
            f.write(f"Analysis Date: {report_data['analysis_date']}\n")
            f.write(f"Total Listings: {report_data['total_listings']}\n")
            f.write(f"Top Bargains: {len(report_data['top_bargains'])}\n\n")
            
            f.write("TOP POTENTIAL BARGAINS:\n")
            f.write("-" * 25 + "\n\n")
            
            for i, bargain in enumerate(report_data['top_bargains'], 1):
                f.write(f"{i}. {bargain['title']}\n")
                f.write(f"   Price: {bargain['price']:,} kr\n")
                f.write(f"   Score: {bargain['bargain_score']:.1f}/10\n")
                f.write(f"   Risk: {bargain['risk_level']}\n")
                f.write(f"   URL: {bargain['url']}\n")
                f.write(f"   Reasoning: {bargain['reasoning']}\n\n")
        
        logger.info(f"Saved summary: {summary_file}")

def main():
    """Main execution"""
    
    print("SAILBOAT BARGAIN HUNTER")
    print("=" * 30)
    
    pipeline = SailboatAnalysisPipeline()
    
    ad_list_file = 'finn_seilbåt_annonseliste.txt'
    
    if not Path(ad_list_file).exists():
        logger.error(f"File not found: {ad_list_file}")
        return
    
    try:
        results = pipeline.run_full_analysis(ad_list_file)
        
        print(f"\nANALYSIS COMPLETE!")
        print(f"Analyzed {results['total_listings']} listings")
        print(f"Found {len(results['top_bargains'])} potential bargains")
        
        if results['top_bargains']:
            print(f"\nTOP 3 BARGAINS:")
            for i, bargain in enumerate(results['top_bargains'][:3], 1):
                print(f"{i}. {bargain['title']}")
                print(f"   {bargain['price']:,} kr | Score: {bargain['bargain_score']:.1f}/10")
        
    except Exception as e:
        logger.error(f"Analysis failed: {e}")

if __name__ == "__main__":
    main()