#!/usr/bin/env python3
"""
Semantisk chunking av båtbeskrivelser for PgVector søk.
Fokuserer på korte, meningsfulle segmenter for seil/motor/tilstand scoring.
"""

import re
import logging
from typing import List, Dict, Tuple
from dataclasses import dataclass

@dataclass
class TextChunk:
    text: str
    order: int
    start_pos: int
    end_pos: int
    overlap_words: int = 0
    
    @property
    def length(self) -> int:
        return len(self.text.split())

class BoatDescriptionChunker:
    """
    Intelligent chunking for båtbeskrivelser.
    Lager korte, overlappende chunks optimert for semantisk søk.
    """
    
    def __init__(self, 
                 target_chunk_size: int = 20,  # 15-25 ord per chunk
                 max_chunk_size: int = 35,
                 overlap_words: int = 7,
                 min_chunk_size: int = 8):
        self.target_chunk_size = target_chunk_size
        self.max_chunk_size = max_chunk_size
        self.overlap_words = overlap_words
        self.min_chunk_size = min_chunk_size
        
        # Nøkkelord som indikerer viktige overganger
        self.semantic_breaks = {
            'sails': ['seil', 'seil:', 'genoa', 'fok', 'storseil', 'spinnaker'],
            'motor': ['motor', 'motor:', 'maskin', 'propell', 'diesel', 'bensin', 'hk', 'hp'],
            'condition': ['tilstand', 'stand', 'vedlikehold', 'oppusset', 'renovert', 'slitasje'],
            'equipment': ['utstyr', 'instrumenter', 'elektronikk', 'gps', 'radar', 'vhf'],
            'interior': ['interiør', 'lugarer', 'køy', 'toalett', 'kjøkken', 'salong'],
            'exterior': ['dekk', 'skrog', 'rigg', 'mast', 'bom']
        }
    
    def clean_text(self, text: str) -> str:
        """Rens og normaliser tekst for chunking."""
        if not text:
            return ""
        
        # Fjern overflødig whitespace
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Fjern unødvendige tegn men behold punktum og komma
        text = re.sub(r'[^\w\sæøåÆØÅ.,!?()-]', '', text)
        
        # Normaliser til lowercase for semantisk analyse
        return text.lower()
    
    def find_sentence_boundaries(self, text: str) -> List[int]:
        """Finn setningsgrenser for naturlige chunks."""
        boundaries = [0]
        
        # Enkle setningsgrenser
        for match in re.finditer(r'[.!?]\s+', text):
            boundaries.append(match.end())
        
        # Legg til slutten
        if boundaries[-1] != len(text):
            boundaries.append(len(text))
            
        return boundaries
    
    def find_semantic_breaks(self, words: List[str]) -> List[int]:
        """Finn semantiske brudd basert på nøkkelord."""
        breaks = []
        
        for i, word in enumerate(words):
            # Sjekk om ordet indikerer en ny semantisk seksjon
            for category, keywords in self.semantic_breaks.items():
                if any(keyword in word for keyword in keywords):
                    if i > 0:  # Ikke break på første ord
                        breaks.append(i)
                    break
        
        return sorted(set(breaks))
    
    def create_overlapping_chunks(self, words: List[str], boundaries: List[int]) -> List[TextChunk]:
        """Lag overlappende chunks med semantisk bevissthet."""
        chunks = []
        start_idx = 0
        chunk_order = 0
        
        while start_idx < len(words):
            # Bestem chunk-slutt
            end_idx = min(start_idx + self.target_chunk_size, len(words))
            
            # Juster til naturlige grenser hvis mulig
            adjusted_end = self._find_natural_end(words, start_idx, end_idx, boundaries)
            
            # Lag chunk
            chunk_words = words[start_idx:adjusted_end]
            chunk_text = ' '.join(chunk_words)
            
            # Beregn overlap med forrige chunk
            overlap = min(self.overlap_words, len(chunk_words)) if chunk_order > 0 else 0
            
            chunk = TextChunk(
                text=chunk_text,
                order=chunk_order,
                start_pos=start_idx,
                end_pos=adjusted_end,
                overlap_words=overlap
            )
            
            # Bare legg til hvis chunken er lang nok
            if len(chunk_words) >= self.min_chunk_size:
                chunks.append(chunk)
                chunk_order += 1
            
            # Flytt start med overlap
            next_start = max(adjusted_end - self.overlap_words, start_idx + 1)
            if next_start >= len(words):
                break
            start_idx = next_start
        
        return chunks
    
    def _find_natural_end(self, words: List[str], start: int, target_end: int, sentence_boundaries: List[int]) -> int:
        """Finn naturlig slutt for chunk basert på setningsgrenser."""
        # Hvis vi er innenfor target range, prøv å finne setningsgrense
        for boundary in sentence_boundaries:
            if start < boundary <= target_end + 5:  # Litt fleksibilitet
                return min(boundary, len(words))
        
        # Fallback til target
        return min(target_end, len(words))
    
    def chunk_description(self, description: str) -> List[TextChunk]:
        """
        Hoved-metode: chunk en båtbeskrivelse til semantiske segmenter.
        
        Args:
            description: Rå beskrivelsestekst
            
        Returns:
            Liste av TextChunk objekter
        """
        if not description or len(description.strip()) < 20:
            return []
        
        # Rens tekst
        clean_desc = self.clean_text(description)
        words = clean_desc.split()
        
        if len(words) < self.min_chunk_size:
            # For korte tekster: én chunk
            return [TextChunk(
                text=clean_desc,
                order=0,
                start_pos=0,
                end_pos=len(words),
                overlap_words=0
            )]
        
        # Finn naturlige grenser
        sentence_boundaries = self.find_sentence_boundaries(clean_desc)
        word_boundaries = [len(clean_desc[:pos].split()) for pos in sentence_boundaries]
        
        # Lag overlappende chunks
        chunks = self.create_overlapping_chunks(words, word_boundaries)
        
        logging.debug(f"Chunked {len(words)} words into {len(chunks)} chunks")
        return chunks
    
    def get_aspect_relevant_chunks(self, chunks: List[TextChunk], aspect: str) -> List[TextChunk]:
        """
        Filtrer chunks som er relevante for en spesifikk aspect (seil, motor, etc.).
        
        Args:
            chunks: Liste av alle chunks
            aspect: 'sails', 'motor', 'condition', etc.
            
        Returns:
            Filtrerte chunks som inneholder relevante nøkkelord
        """
        if aspect not in self.semantic_breaks:
            return chunks
        
        keywords = self.semantic_breaks[aspect]
        relevant_chunks = []
        
        for chunk in chunks:
            # Sjekk om chunk inneholder relevante nøkkelord
            chunk_lower = chunk.text.lower()
            if any(keyword in chunk_lower for keyword in keywords):
                relevant_chunks.append(chunk)
        
        return relevant_chunks

# Test og eksempel-bruk
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    chunker = BoatDescriptionChunker()
    
    # Eksempel beskrivelse
    test_desc = """
    Veldig fin båt med 3 seil, to nye i fjor og ett gammelt. 
    Motoren har hatt jevnlig vedlikehold og fungerer utmerket. 
    Interiøret er i god stand med nye puter i salong. 
    GPS og VHF radio er installert. Dekket trenger litt maling.
    """
    
    chunks = chunker.chunk_description(test_desc)
    
    print(f"Totalt {len(chunks)} chunks:")
    for i, chunk in enumerate(chunks):
        print(f"{i+1}: [{chunk.length} ord] {chunk.text}")
    
    # Test aspect-filtrering
    print("\nSeil-relevante chunks:")
    sail_chunks = chunker.get_aspect_relevant_chunks(chunks, 'sails')
    for chunk in sail_chunks:
        print(f"- {chunk.text}")
    
    print("\nMotor-relevante chunks:")
    motor_chunks = chunker.get_aspect_relevant_chunks(chunks, 'motor')
    for chunk in motor_chunks:
        print(f"- {chunk.text}") 