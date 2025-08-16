#!/usr/bin/env python3
"""
Semantisk scoring system for båtannonser.
Evaluerer seil, motor, tilstand og annet utstyr basert på beskrivelsestekst.
"""

import logging
import numpy as np
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum
import re

from .chunker import TextChunk, BoatDescriptionChunker
from .embedder import EmbeddingService, create_embedding_service

class AspectType(Enum):
    """Aspekter vi scorer på."""
    SAILS = "sails"
    MOTOR = "motor" 
    CONDITION = "condition"
    EQUIPMENT = "equipment"
    INTERIOR = "interior"
    EXTERIOR = "exterior"

@dataclass
class AspectScore:
    """Score for en spesifikk aspect."""
    aspect: AspectType
    raw_score: float  # 0.0-1.0
    normalized_score: Optional[float]  # Normalisert mot dataset
    confidence: float  # Hvor sikker vi er på scoringen
    supporting_chunks: List[str]  # Chunks som bidro til score
    keywords_found: List[str]  # Relevante nøkkelord funnet
    method: str  # "embedding_similarity", "keyword_match", "llm_classification"

class SemanticScorer:
    """
    Scorer båtbeskrivelser på ulike aspekter.
    Kombinerer keyword-matching med embedding-basert semantikk.
    """
    
    def __init__(self, embedding_service: Optional[EmbeddingService] = None):
        self.embedding_service = embedding_service or create_embedding_service()
        self.chunker = BoatDescriptionChunker()
        
        # Predefinerte reference-embeddings for hver aspect
        self._reference_embeddings: Dict[AspectType, List[float]] = {}
        
        # Aspect-spesifikke nøkkelord og vekter
        self.aspect_keywords = {
            AspectType.SAILS: {
                'positive': {
                    'nye seil': 0.9, 'nytt seil': 0.9, 'nye': 0.7,
                    'god stand': 0.8, 'utmerket': 0.9, 'perfekt': 0.9,
                    'service': 0.7, 'vedlikehold': 0.6, 'oppgradert': 0.8,
                    'genoa': 0.6, 'fok': 0.6, 'storseil': 0.6, 'spinnaker': 0.7
                },
                'negative': {
                    'slitt': -0.8, 'ødelagt': -0.9, 'hull': -0.7,
                    'gammel': -0.5, 'dårlig': -0.8, 'reparert': -0.3,
                    'lappet': -0.4, 'defekt': -0.9
                }
            },
            AspectType.MOTOR: {
                'positive': {
                    'ny motor': 0.9, 'service': 0.7, 'vedlikehold': 0.8,
                    'fungerer perfekt': 0.9, 'jevnlig service': 0.8,
                    'utmerket': 0.9, 'god': 0.7, 'pålitelig': 0.8,
                    'overhalt': 0.8, 'oppgradert': 0.8, 'diesel': 0.5,
                    'lavt': 0.6, 'timer': 0.4
                },
                'negative': {
                    'problemer': -0.8, 'defekt': -0.9, 'dårlig': -0.8,
                    'lekkasje': -0.7, 'støy': -0.5, 'rust': -0.6,
                    'trenger service': -0.4, 'høy': -0.3, 'timer': 0.4
                }
            },
            AspectType.CONDITION: {
                'positive': {
                    'god stand': 0.8, 'utmerket': 0.9, 'vedlikeholdt': 0.8,
                    'renovert': 0.9, 'oppusset': 0.8, 'nylig': 0.7,
                    'perfekt': 0.9, 'fin': 0.6, 'bra': 0.6
                },
                'negative': {
                    'slitasje': -0.6, 'skader': -0.8, 'rust': -0.7,
                    'hull': -0.8, 'dårlig': -0.8, 'trenger': -0.4,
                    'reparasjon': -0.5, 'vedlikehold': -0.3
                }
            },
            AspectType.EQUIPMENT: {
                'positive': {
                    'gps': 0.7, 'radar': 0.8, 'vhf': 0.6, 'autopilot': 0.8,
                    'elektronikk': 0.6, 'instrumenter': 0.6, 'sonar': 0.7,
                    'chartplotter': 0.8, 'ais': 0.7, 'komplett': 0.8
                },
                'negative': {
                    'mangler': -0.6, 'defekt': -0.8, 'gammelt': -0.4,
                    'ikke fungerende': -0.9
                }
            }
        }
        
        # Initialize reference embeddings
        self._initialize_reference_embeddings()
    
    def _initialize_reference_embeddings(self):
        """Opprett reference embeddings for hver aspect."""
        reference_texts = {
            AspectType.SAILS: [
                "tre nye seil i utmerket stand",
                "genoa og storseil nylig service",
                "seilene er i god tilstand"
            ],
            AspectType.MOTOR: [
                "motoren har jevnlig vedlikehold og fungerer perfekt",
                "diesel motor med lav timer",
                "pålitelig motor i god drift"
            ],
            AspectType.CONDITION: [
                "båten er i utmerket stand og godt vedlikeholdt",
                "renovert og oppgradert",
                "fin tilstand uten skader"
            ],
            AspectType.EQUIPMENT: [
                "komplett med gps radar og vhf",
                "moderne elektronikk og instrumenter",
                "autopilot og chartplotter installert"
            ]
        }
        
        for aspect, texts in reference_texts.items():
            try:
                # Generate embeddings for reference texts
                embeddings = self.embedding_service.embed_batch(texts)
                # Average the embeddings to create reference
                vectors = [emb.vector for emb in embeddings]
                reference_vector = np.mean(vectors, axis=0).tolist()
                self._reference_embeddings[aspect] = reference_vector
                logging.debug(f"Created reference embedding for {aspect.value}")
            except Exception as e:
                logging.error(f"Failed to create reference embedding for {aspect.value}: {e}")
    
    def score_description(self, description: str, aspects: Optional[List[AspectType]] = None) -> Dict[AspectType, AspectScore]:
        """
        Score en beskrivelse på angitte aspekter.
        
        Args:
            description: Båtbeskrivelse å score
            aspects: Hvilke aspekter å score (default: alle)
            
        Returns:
            Dict med AspectScore for hver aspect
        """
        if not description or len(description.strip()) < 20:
            return {}
        
        if aspects is None:
            aspects = list(AspectType)
        
        # Chunk beskrivelsen
        chunks = self.chunker.chunk_description(description)
        if not chunks:
            return {}
        
        scores = {}
        
        for aspect in aspects:
            try:
                score = self._score_aspect(chunks, aspect, description)
                scores[aspect] = score
            except Exception as e:
                logging.error(f"Failed to score aspect {aspect.value}: {e}")
                # Create fallback score
                scores[aspect] = AspectScore(
                    aspect=aspect,
                    raw_score=0.0,
                    normalized_score=None,
                    confidence=0.0,
                    supporting_chunks=[],
                    keywords_found=[],
                    method="error"
                )
        
        return scores
    
    def _score_aspect(self, chunks: List[TextChunk], aspect: AspectType, full_description: str) -> AspectScore:
        """Score en spesifikk aspect basert på chunks."""
        
        # 1. Keyword-basert scoring
        keyword_score, keywords_found, supporting_chunks_kw = self._score_keywords(chunks, aspect)
        
        # 2. Embedding-basert scoring
        embedding_score, supporting_chunks_emb = self._score_embeddings(chunks, aspect)
        
        # 3. Kombiner scores
        # Vekt keyword høyere hvis vi finner tydelige keywords
        keyword_weight = 0.7 if keywords_found else 0.3
        embedding_weight = 1.0 - keyword_weight
        
        combined_score = (keyword_score * keyword_weight) + (embedding_score * embedding_weight)
        
        # 4. Beregn confidence
        confidence = self._calculate_confidence(keyword_score, embedding_score, keywords_found, supporting_chunks_kw)
        
        # 5. Combine supporting chunks
        all_supporting = list(set(supporting_chunks_kw + supporting_chunks_emb))
        
        return AspectScore(
            aspect=aspect,
            raw_score=float(np.clip(combined_score, 0.0, 1.0)),
            normalized_score=None,  # Fylles inn senere av normalize_scores
            confidence=confidence,
            supporting_chunks=all_supporting,
            keywords_found=keywords_found,
            method="hybrid"
        )
    
    def _score_keywords(self, chunks: List[TextChunk], aspect: AspectType) -> Tuple[float, List[str], List[str]]:
        """Score basert på nøkkelord-matching."""
        if aspect not in self.aspect_keywords:
            return 0.0, [], []
        
        keywords = self.aspect_keywords[aspect]
        total_score = 0.0
        found_keywords = []
        supporting_chunks = []
        
        for chunk in chunks:
            chunk_text = chunk.text.lower()
            chunk_score = 0.0
            chunk_keywords = []
            
            # Positive keywords
            for keyword, weight in keywords.get('positive', {}).items():
                if keyword in chunk_text:
                    chunk_score += weight
                    chunk_keywords.append(keyword)
            
            # Negative keywords
            for keyword, weight in keywords.get('negative', {}).items():
                if keyword in chunk_text:
                    chunk_score += weight  # Weight is already negative
                    chunk_keywords.append(f"(-) {keyword}")
            
            if chunk_keywords:
                found_keywords.extend(chunk_keywords)
                supporting_chunks.append(chunk.text)
                total_score += chunk_score
        
        # Normalize score
        if found_keywords:
            # Divide by number of chunks to avoid inflation
            normalized_score = total_score / len(chunks)
            # Clamp to reasonable range
            normalized_score = np.clip(normalized_score, -1.0, 1.0)
            # Convert to 0-1 scale
            normalized_score = (normalized_score + 1.0) / 2.0
        else:
            normalized_score = 0.5  # Neutral if no keywords found
        
        return normalized_score, found_keywords, supporting_chunks
    
    def _score_embeddings(self, chunks: List[TextChunk], aspect: AspectType) -> Tuple[float, List[str]]:
        """Score basert på semantic similarity med reference embeddings."""
        if aspect not in self._reference_embeddings:
            return 0.5, []  # Neutral score
        
        reference_embedding = self._reference_embeddings[aspect]
        
        try:
            # Get embeddings for all chunks
            chunk_texts = [chunk.text for chunk in chunks]
            chunk_embeddings = self.embedding_service.embed_batch(chunk_texts)
            
            similarities = []
            supporting_chunks = []
            
            for i, chunk_embedding in enumerate(chunk_embeddings):
                # Calculate similarity to reference
                similarity = self.embedding_service.similarity(
                    chunk_embedding.vector, 
                    reference_embedding
                )
                similarities.append(similarity)
                
                # Include chunk if similarity is high enough
                if similarity > 0.6:  # Threshold for relevance
                    supporting_chunks.append(chunk_texts[i])
            
            if similarities:
                # Use max similarity as primary signal
                max_similarity = max(similarities)
                # But also consider average to avoid outliers
                avg_similarity = np.mean(similarities)
                # Weighted combination
                final_score = (max_similarity * 0.7) + (avg_similarity * 0.3)
                
                # Convert from -1,1 to 0,1 range and apply sigmoid for better distribution
                final_score = (final_score + 1.0) / 2.0
                return final_score, supporting_chunks
            else:
                return 0.5, []
                
        except Exception as e:
            logging.error(f"Embedding scoring failed for {aspect.value}: {e}")
            return 0.5, []
    
    def _calculate_confidence(self, keyword_score: float, embedding_score: float, 
                            keywords_found: List[str], supporting_chunks: List[str]) -> float:
        """Beregn confidence score for aspect scoring."""
        
        # Base confidence on agreement between methods
        score_agreement = 1.0 - abs(keyword_score - embedding_score)
        
        # Boost confidence if we found keywords
        keyword_boost = min(len(keywords_found) * 0.1, 0.4)
        
        # Boost confidence if we have supporting evidence
        evidence_boost = min(len(supporting_chunks) * 0.05, 0.3)
        
        # Combine factors
        confidence = (score_agreement * 0.6) + keyword_boost + evidence_boost
        
        return float(np.clip(confidence, 0.0, 1.0))
    
    def normalize_scores(self, ad_scores: List[Dict[AspectType, AspectScore]], 
                        target_ad_scores: Dict[AspectType, AspectScore]) -> Dict[AspectType, AspectScore]:
        """
        Normaliser scores mot hele datasettet.
        
        Args:
            ad_scores: Scores for alle annonser i databasen
            target_ad_scores: Scores for annonsen vi normaliserer
            
        Returns:
            Oppdaterte scores med normalized_score felt
        """
        if not ad_scores:
            return target_ad_scores
        
        # Samle scores per aspect
        aspect_scores = {}
        for aspect in AspectType:
            scores = []
            for ad_score_dict in ad_scores:
                if aspect in ad_score_dict:
                    scores.append(ad_score_dict[aspect].raw_score)
            aspect_scores[aspect] = scores
        
        # Normaliser target scores
        normalized_scores = {}
        for aspect, score_obj in target_ad_scores.items():
            if aspect in aspect_scores and aspect_scores[aspect]:
                # Calculate percentile rank
                raw_score = score_obj.raw_score
                dataset_scores = aspect_scores[aspect]
                
                # Percentile normalization
                percentile = np.sum(np.array(dataset_scores) <= raw_score) / len(dataset_scores)
                
                # Create new score object with normalized value
                normalized_scores[aspect] = AspectScore(
                    aspect=score_obj.aspect,
                    raw_score=score_obj.raw_score,
                    normalized_score=float(percentile),
                    confidence=score_obj.confidence,
                    supporting_chunks=score_obj.supporting_chunks,
                    keywords_found=score_obj.keywords_found,
                    method=score_obj.method
                )
            else:
                # Keep original if no dataset
                normalized_scores[aspect] = score_obj
        
        return normalized_scores

# Convenience functions
def score_boat_description(description: str, aspects: Optional[List[str]] = None, 
                          embedding_service: Optional[EmbeddingService] = None) -> Dict[str, AspectScore]:
    """
    Convenience function for å score en båtbeskrivelse.
    
    Args:
        description: Beskrivelsestekst
        aspects: Liste av aspect-navn ("sails", "motor", etc.)
        embedding_service: Optional embedding service
        
    Returns:
        Dict med aspect-navn som nøkler og AspectScore som verdier
    """
    scorer = SemanticScorer(embedding_service)
    
    # Convert string aspects to enums
    aspect_enums = []
    if aspects:
        for aspect_str in aspects:
            try:
                aspect_enum = AspectType(aspect_str)
                aspect_enums.append(aspect_enum)
            except ValueError:
                logging.warning(f"Unknown aspect: {aspect_str}")
    else:
        aspect_enums = list(AspectType)
    
    scores = scorer.score_description(description, aspect_enums)
    
    # Convert back to string keys
    return {aspect.value: score for aspect, score in scores.items()}

# Test and example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Test scoring
    test_description = """
    Veldig fin båt med 3 seil, to nye i fjor og ett gammelt. 
    Motoren har hatt jevnlig vedlikehold og fungerer utmerket med lave timer. 
    Interiøret er i god stand med nye puter i salong. 
    GPS, VHF radio og autopilot er installert. 
    Dekket trenger litt maling men ellers i fin stand.
    """
    
    scorer = SemanticScorer()
    scores = scorer.score_description(test_description)
    
    print("🎯 Semantic scoring results:")
    for aspect, score in scores.items():
        print(f"\n{aspect.value.upper()}:")
        print(f"  Raw score: {score.raw_score:.2f}")
        print(f"  Confidence: {score.confidence:.2f}")
        print(f"  Keywords: {score.keywords_found}")
        print(f"  Supporting: {len(score.supporting_chunks)} chunks")
        for chunk in score.supporting_chunks[:2]:  # Show first 2
            print(f"    - {chunk}")
    
    # Test convenience function
    print("\n" + "="*50)
    simple_scores = score_boat_description(test_description, ["sails", "motor"])
    for aspect, score in simple_scores.items():
        print(f"{aspect}: {score.raw_score:.2f} (confidence: {score.confidence:.2f})") 