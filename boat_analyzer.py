"""
Boat Analyzer with LLM Integration
Analyzes boats for potential bargains and generates questions for sellers
"""

import json
import re
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

@dataclass
class BoatAnalysis:
    """Structure for boat analysis results"""
    bargain_score: float  # 0-10 scale
    risk_level: str  # "LOW", "MEDIUM", "HIGH"
    red_flags: List[str]
    positive_indicators: List[str]
    seller_questions: List[str]
    estimated_market_value: Optional[int]
    reasoning: str

class BoatAnalyzer:
    """Analyzes boats using rule-based logic and prepares for LLM integration"""
    
    def __init__(self):
        # Market price estimates per boat type/age (simplified model)
        self.market_baselines = {
            'bavaria': {'base_price_per_foot': 8000, 'depreciation_per_year': 800},
            'jeanneau': {'base_price_per_foot': 9000, 'depreciation_per_year': 900},
            'beneteau': {'base_price_per_foot': 9500, 'depreciation_per_year': 950},
            'hallberg_rassy': {'base_price_per_foot': 15000, 'depreciation_per_year': 1200},
            'default': {'base_price_per_foot': 6000, 'depreciation_per_year': 600}
        }
        
        # Critical red flags that should raise alarms
        self.critical_red_flags = [
            'defekt motor', 'hull damage', 'osmose', 'rot', 'mast problems',
            'ingen papirer', 'urgent sale', 'must sell', 'divorce'
        ]
        
        # Positive value indicators
        self.value_indicators = [
            'recent survey', 'new engine', 'upgraded electronics', 'new sails',
            'recent antifouling', 'well maintained', 'complete documentation'
        ]

    def analyze_boat(self, boat_data: Dict) -> BoatAnalysis:
        """Comprehensive boat analysis"""
        
        # Extract key information
        basic_info = boat_data.get('basic_info', {})
        technical_specs = boat_data.get('technical_specs', {})
        equipment = boat_data.get('equipment', {})
        condition_analysis = boat_data.get('condition_analysis', {})
        descriptions = boat_data.get('descriptions', {})
        
        # Calculate bargain score
        bargain_score = self._calculate_bargain_score(
            basic_info, technical_specs, condition_analysis, descriptions
        )
        
        # Identify red flags
        red_flags = self._identify_red_flags(condition_analysis, descriptions)
        
        # Identify positive indicators
        positive_indicators = self._identify_positive_indicators(
            condition_analysis, descriptions, equipment
        )
        
        # Determine risk level
        risk_level = self._determine_risk_level(red_flags, bargain_score)
        
        # Generate seller questions
        seller_questions = self._generate_seller_questions(
            basic_info, technical_specs, red_flags, equipment
        )
        
        # Estimate market value
        estimated_value = self._estimate_market_value(basic_info, technical_specs)
        
        # Generate reasoning
        reasoning = self._generate_reasoning(
            bargain_score, red_flags, positive_indicators, 
            basic_info, estimated_value
        )
        
        return BoatAnalysis(
            bargain_score=bargain_score,
            risk_level=risk_level,
            red_flags=red_flags,
            positive_indicators=positive_indicators,
            seller_questions=seller_questions,
            estimated_market_value=estimated_value,
            reasoning=reasoning
        )

    def _calculate_bargain_score(self, basic_info: Dict, technical_specs: Dict, 
                                condition_analysis: Dict, descriptions: Dict) -> float:
        """Calculate bargain score (0-10, where 10 is best bargain)"""
        score = 5.0  # Start with neutral
        
        # Price vs estimated value
        asking_price = basic_info.get('price')
        estimated_value = self._estimate_market_value(basic_info, technical_specs)
        
        if asking_price and estimated_value:
            price_ratio = asking_price / estimated_value
            if price_ratio < 0.6:  # 40% below market
                score += 3.0
            elif price_ratio < 0.75:  # 25% below market
                score += 2.0
            elif price_ratio < 0.9:  # 10% below market
                score += 1.0
            elif price_ratio > 1.2:  # 20% above market
                score -= 2.0
        
        # Condition indicators
        positive_flags = condition_analysis.get('positive', [])
        negative_flags = condition_analysis.get('negative', [])
        
        score += len(positive_flags) * 0.3
        score -= len(negative_flags) * 0.5
        
        # Equipment value
        total_equipment = sum(len(items) for items in basic_info.get('equipment', {}).values())
        score += min(total_equipment * 0.1, 1.5)  # Cap equipment bonus
        
        # Age factor
        year = basic_info.get('year')
        if year:
            current_year = datetime.now().year
            age = current_year - year
            if age < 5:
                score += 0.5
            elif age > 25:
                score -= 0.5
        
        return max(0, min(10, score))  # Clamp between 0-10

    def _estimate_market_value(self, basic_info: Dict, technical_specs: Dict) -> Optional[int]:
        """Estimate market value based on boat specs"""
        try:
            make = (basic_info.get('make') or '').lower()
            length = technical_specs.get('length')
            year = basic_info.get('year')
            
            if not all([length, year]):
                return None
            
            # Get market baseline for this make
            baseline = self.market_baselines.get(make, self.market_baselines['default'])
            
            # Calculate base value
            base_value = length * baseline['base_price_per_foot']
            
            # Apply depreciation
            current_year = datetime.now().year
            age = current_year - year
            depreciation = age * baseline['depreciation_per_year']
            
            estimated_value = max(base_value - depreciation, base_value * 0.2)  # Min 20% of base
            
            return int(estimated_value)
            
        except (TypeError, ValueError):
            return None

    def _identify_red_flags(self, condition_analysis: Dict, descriptions: Dict) -> List[str]:
        """Identify potential red flags"""
        red_flags = []
        
        # From condition analysis
        negative_flags = condition_analysis.get('negative', [])
        red_flags.extend(negative_flags)
        
        # Check descriptions for critical issues
        full_text = f"{descriptions.get('main', '')} {descriptions.get('equipment', '')}".lower()
        
        for flag in self.critical_red_flags:
            if flag.lower() in full_text:
                red_flags.append(f"Mentions: {flag}")
        
        # Check for vague descriptions (potential hiding issues)
        if len(full_text) < 100:
            red_flags.append("Very short description - possibly hiding issues")
        
        # Check for urgency indicators
        urgency_words = ['må selges', 'kjapt', 'urgent', 'asap', 'moving abroad']
        for word in urgency_words:
            if word in full_text:
                red_flags.append(f"Urgency indicator: {word}")
        
        return red_flags

    def _identify_positive_indicators(self, condition_analysis: Dict, 
                                    descriptions: Dict, equipment: Dict) -> List[str]:
        """Identify positive value indicators"""
        positive_indicators = []
        
        # From condition analysis
        positive_flags = condition_analysis.get('positive', [])
        positive_indicators.extend(positive_flags)
        
        # Equipment indicators
        high_value_equipment = ['gps', 'radar', 'autopilot', 'generator', 'air conditioning']
        full_text = f"{descriptions.get('main', '')} {descriptions.get('equipment', '')}".lower()
        
        for item in high_value_equipment:
            if item in full_text:
                positive_indicators.append(f"Has {item}")
        
        # Check for recent upgrades
        upgrade_indicators = ['new', 'recent', 'upgraded', 'replaced', '2023', '2024', '2025']
        for indicator in upgrade_indicators:
            if indicator in full_text and len(full_text.split(indicator)) > 2:
                positive_indicators.append(f"Recent upgrades mentioned: {indicator}")
        
        # Documentation mentions
        if any(word in full_text for word in ['papers', 'documentation', 'survey', 'certificate']):
            positive_indicators.append("Documentation mentioned")
        
        return positive_indicators

    def _determine_risk_level(self, red_flags: List[str], bargain_score: float) -> str:
        """Determine overall risk level"""
        if len(red_flags) >= 3 or bargain_score > 8.5:
            return "HIGH"  # Too many red flags OR too good to be true
        elif len(red_flags) >= 1 or bargain_score < 3:
            return "MEDIUM"
        else:
            return "LOW"

    def _generate_seller_questions(self, basic_info: Dict, technical_specs: Dict, 
                                 red_flags: List[str], equipment: Dict) -> List[str]:
        """Generate targeted questions for the seller"""
        questions = []
        
        # Standard questions for all boats
        questions.extend([
            "Can you provide the most recent survey report?",
            "What is the service history of the engine?",
            "Are there any known issues or needed repairs?",
            "Why are you selling the boat?",
            "Can I see all documentation (registration, insurance, etc.)?"
        ])
        
        # Engine-specific questions
        motor_info = technical_specs.get('motor_make') or technical_specs.get('motor_type')
        if motor_info:
            questions.append(f"How many hours on the {motor_info} engine?")
            questions.append("When was the engine last serviced?")
        
        # Red flag specific questions
        if any('defekt' in flag.lower() for flag in red_flags):
            questions.append("Can you provide details about what exactly is defective?")
            questions.append("Do you have repair estimates for the defects?")
        
        if any('urgent' in flag.lower() for flag in red_flags):
            questions.append("What's the reason for the urgent sale?")
            questions.append("Are you flexible on timing if I need a survey?")
        
        # Equipment questions
        electronics = equipment.get('electronics', [])
        if electronics:
            questions.append(f"Are all the electronics ({', '.join(electronics)}) working?")
        
        # Age-specific questions
        year = basic_info.get('year')
        if year and (datetime.now().year - year) > 20:
            questions.extend([
                "Has the boat had any major refits or upgrades?",
                "What is the condition of the rigging and sails?",
                "Any hull repairs or osmosis treatment?"
            ])
        
        return questions[:15]  # Limit to 15 most relevant questions

    def _generate_reasoning(self, bargain_score: float, red_flags: List[str], 
                          positive_indicators: List[str], basic_info: Dict, 
                          estimated_value: Optional[int]) -> str:
        """Generate human-readable reasoning for the analysis"""
        
        asking_price = basic_info.get('price')
        
        reasoning_parts = []
        
        # Bargain score explanation
        if bargain_score >= 7:
            reasoning_parts.append(f"⭐ Excellent potential bargain (score: {bargain_score:.1f}/10)")
        elif bargain_score >= 5:
            reasoning_parts.append(f"✅ Good value potential (score: {bargain_score:.1f}/10)")
        else:
            reasoning_parts.append(f"⚠️ Below average value (score: {bargain_score:.1f}/10)")
        
        # Price analysis
        if asking_price and estimated_value:
            price_diff = ((asking_price - estimated_value) / estimated_value) * 100
            if price_diff < -15:
                reasoning_parts.append(f"💰 Asking price is {abs(price_diff):.1f}% below estimated market value")
            elif price_diff > 15:
                reasoning_parts.append(f"💸 Asking price is {price_diff:.1f}% above estimated market value")
        
        # Red flags
        if red_flags:
            reasoning_parts.append(f"🚩 {len(red_flags)} red flag(s): {', '.join(red_flags[:3])}")
        
        # Positive indicators
        if positive_indicators:
            reasoning_parts.append(f"✅ {len(positive_indicators)} positive indicator(s): {', '.join(positive_indicators[:3])}")
        
        return " | ".join(reasoning_parts)

def analyze_boat_with_llm_prompt(boat_data: Dict) -> str:
    """Generate a detailed prompt for LLM analysis"""
    
    basic_info = boat_data.get('basic_info', {})
    technical_specs = boat_data.get('technical_specs', {})
    descriptions = boat_data.get('descriptions', {})
    
    prompt = f"""
Analyze this sailboat listing for potential investment value and hidden issues:

BOAT DETAILS:
- Title: {basic_info.get('title', 'Not specified')}
- Price: {basic_info.get('price', 'Not specified')} kr
- Year: {basic_info.get('year', 'Not specified')}
- Make/Model: {basic_info.get('make', 'Not specified')} {basic_info.get('model', '')}
- Length: {technical_specs.get('length', 'Not specified')} ft
- Location: {basic_info.get('location', 'Not specified')}

DESCRIPTION:
{descriptions.get('main', 'No description available')}

TECHNICAL SPECS:
{json.dumps(technical_specs, indent=2)}

Please analyze:
1. Is this a potential bargain based on price vs typical market value?
2. What red flags do you see in the description?
3. What positive indicators suggest good value?
4. What specific questions should I ask the seller before viewing?
5. What should I inspect carefully during viewing?
6. Rate the deal on a scale of 1-10 where 10 is "excellent bargain"

Provide a structured analysis focusing on hidden costs, potential issues, and negotiation strategy.
"""
    
    return prompt

if __name__ == "__main__":
    # Example usage
    analyzer = BoatAnalyzer()
    
    # Test with sample data
    sample_boat = {
        'basic_info': {
            'title': 'Bavaria 38 AC Cruiser',
            'price': 720000,
            'year': 2005,
            'make': 'Bavaria',
            'model': '38 AC',
            'location': 'Oslo'
        },
        'technical_specs': {
            'length': 38,
            'motor_make': 'Volvo Penta',
            'motor_type': 'Innenbordsmotor',
            'fuel_type': 'Diesel'
        },
        'equipment': {
            'navigation': ['gps', 'kartplotter'],
            'mechanical': ['baugpropell']
        },
        'condition_analysis': {
            'positive': ['godt vedlikeholdt'],
            'negative': ['defekt motor']
        },
        'descriptions': {
            'main': 'En flott familiebåt som er klar til å seile. Båten ble vasket og polert og påført ny antifouling i 2025.'
        }
    }
    
    analysis = analyzer.analyze_boat(sample_boat)
    
    print("=== BOAT ANALYSIS EXAMPLE ===")
    print(f"Bargain Score: {analysis.bargain_score:.1f}/10")
    print(f"Risk Level: {analysis.risk_level}")
    print(f"Estimated Market Value: {analysis.estimated_market_value:,} kr")
    print(f"Red Flags: {analysis.red_flags}")
    print(f"Positive Indicators: {analysis.positive_indicators}")
    print(f"Reasoning: {analysis.reasoning}")
    print(f"\nTop Seller Questions:")
    for i, question in enumerate(analysis.seller_questions[:5], 1):
        print(f"{i}. {question}")