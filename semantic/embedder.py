#!/usr/bin/env python3
"""
Embedding service for semantisk søk i båtbeskrivelser.
Støtter både lokale CPU-modeller og API-baserte løsninger.
"""

import os
import time
import logging
import hashlib
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
import numpy as np

@dataclass
class EmbeddingResult:
    """Result from embedding generation."""
    vector: List[float]
    model_name: str
    dimensions: int
    processing_time: float

class EmbeddingService:
    """
    Unified embedding service med CPU og API fallback.
    Optimert for norske båtbeskrivelser.
    """
    
    def __init__(self, 
                 preferred_method: str = "cpu",  # "cpu", "openai", "sentence_transformers"
                 model_name: Optional[str] = None,
                 api_key: Optional[str] = None,
                 cache_embeddings: bool = True):
        
        self.preferred_method = preferred_method
        self.model_name = model_name
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.cache_embeddings = cache_embeddings
        
        # Embedding cache for performance
        self._cache: Dict[str, EmbeddingResult] = {}
        
        # Initialize embedding backend
        self._initialize_backend()
    
    def _initialize_backend(self):
        """Initialize the appropriate embedding backend."""
        self.backend = None
        self.fallback_backends = []
        
        if self.preferred_method == "cpu" or self.preferred_method == "sentence_transformers":
            self._init_sentence_transformers()
        elif self.preferred_method == "openai":
            self._init_openai()
        else:
            logging.warning(f"Unknown method {self.preferred_method}, falling back to CPU")
            self._init_sentence_transformers()
    
    def _init_sentence_transformers(self):
        """Initialize Sentence-Transformers (CPU-friendly)."""
        try:
            from sentence_transformers import SentenceTransformer
            
            # Default: multilingual model that works well with Norwegian
            model_name = self.model_name or 'all-MiniLM-L6-v2'
            
            logging.info(f"Loading Sentence-Transformers model: {model_name}")
            self.backend = SentenceTransformer(model_name)
            self.backend_type = "sentence_transformers"
            self.dimensions = self.backend.get_sentence_embedding_dimension()
            
            logging.info(f"✅ Sentence-Transformers ready: {model_name} ({self.dimensions}d)")
            
        except ImportError:
            logging.warning("sentence-transformers not available, trying OpenAI fallback")
            self._init_openai()
        except Exception as e:
            logging.error(f"Failed to initialize Sentence-Transformers: {e}")
            self._init_openai()
    
    def _init_openai(self):
        """Initialize OpenAI API backend."""
        if not self.api_key:
            logging.error("OpenAI API key not found. Set OPENAI_API_KEY or pass api_key parameter")
            raise ValueError("OpenAI API key required")
        
        try:
            import openai
            self.backend = openai
            self.backend_type = "openai"
            self.model_name = self.model_name or "text-embedding-ada-002"
            self.dimensions = 1536  # Ada-002 dimensions
            
            logging.info(f"✅ OpenAI API ready: {self.model_name} ({self.dimensions}d)")
            
        except ImportError:
            logging.error("openai package not available. Install with: pip install openai")
            raise
    
    def _cache_key(self, text: str) -> str:
        """Generate cache key for text."""
        text_hash = hashlib.md5(text.encode()).hexdigest()
        return f"{self.backend_type}_{self.model_name}_{text_hash}"
    
    def embed_text(self, text: str) -> EmbeddingResult:
        """
        Generate embedding for single text.
        
        Args:
            text: Input text to embed
            
        Returns:
            EmbeddingResult with vector and metadata
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")
        
        # Check cache first
        cache_key = self._cache_key(text)
        if self.cache_embeddings and cache_key in self._cache:
            logging.debug(f"Cache hit for text: {text[:50]}...")
            return self._cache[cache_key]
        
        # Generate embedding
        start_time = time.time()
        
        if self.backend_type == "sentence_transformers":
            vector = self._embed_sentence_transformers(text)
        elif self.backend_type == "openai":
            vector = self._embed_openai(text)
        else:
            raise RuntimeError("No embedding backend available")
        
        processing_time = time.time() - start_time
        
        result = EmbeddingResult(
            vector=vector,
            model_name=self.model_name,
            dimensions=len(vector),
            processing_time=processing_time
        )
        
        # Cache result
        if self.cache_embeddings:
            self._cache[cache_key] = result
        
        logging.debug(f"Generated embedding for '{text[:50]}...' in {processing_time:.3f}s")
        return result
    
    def embed_batch(self, texts: List[str], batch_size: int = 32) -> List[EmbeddingResult]:
        """
        Generate embeddings for multiple texts efficiently.
        
        Args:
            texts: List of texts to embed
            batch_size: Batch size for processing
            
        Returns:
            List of EmbeddingResult objects
        """
        if not texts:
            return []
        
        results = []
        
        # Process in batches
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            
            if self.backend_type == "sentence_transformers":
                batch_results = self._embed_batch_sentence_transformers(batch)
            elif self.backend_type == "openai":
                batch_results = self._embed_batch_openai(batch)
            else:
                # Fallback to individual processing
                batch_results = [self.embed_text(text) for text in batch]
            
            results.extend(batch_results)
            
            # Rate limiting for API calls
            if self.backend_type == "openai" and i + batch_size < len(texts):
                time.sleep(0.1)  # 100ms delay between batches
        
        return results
    
    def _embed_sentence_transformers(self, text: str) -> List[float]:
        """Generate embedding using Sentence-Transformers."""
        try:
            embedding = self.backend.encode(text, convert_to_tensor=False)
            return embedding.tolist()
        except Exception as e:
            logging.error(f"Sentence-Transformers embedding failed: {e}")
            raise
    
    def _embed_batch_sentence_transformers(self, texts: List[str]) -> List[EmbeddingResult]:
        """Generate batch embeddings using Sentence-Transformers."""
        try:
            start_time = time.time()
            embeddings = self.backend.encode(texts, convert_to_tensor=False, show_progress_bar=False)
            processing_time = time.time() - start_time
            
            results = []
            for text, embedding in zip(texts, embeddings):
                result = EmbeddingResult(
                    vector=embedding.tolist(),
                    model_name=self.model_name,
                    dimensions=len(embedding),
                    processing_time=processing_time / len(texts)  # Average per text
                )
                results.append(result)
                
                # Cache if enabled
                if self.cache_embeddings:
                    cache_key = self._cache_key(text)
                    self._cache[cache_key] = result
            
            return results
            
        except Exception as e:
            logging.error(f"Sentence-Transformers batch embedding failed: {e}")
            # Fallback to individual processing
            return [self.embed_text(text) for text in texts]
    
    def _embed_openai(self, text: str) -> List[float]:
        """Generate embedding using OpenAI API."""
        try:
            response = self.backend.Embedding.create(
                model=self.model_name,
                input=text
            )
            return response['data'][0]['embedding']
            
        except Exception as e:
            logging.error(f"OpenAI embedding failed: {e}")
            raise
    
    def _embed_batch_openai(self, texts: List[str]) -> List[EmbeddingResult]:
        """Generate batch embeddings using OpenAI API."""
        try:
            start_time = time.time()
            response = self.backend.Embedding.create(
                model=self.model_name,
                input=texts
            )
            processing_time = time.time() - start_time
            
            results = []
            for i, text in enumerate(texts):
                embedding = response['data'][i]['embedding']
                result = EmbeddingResult(
                    vector=embedding,
                    model_name=self.model_name,
                    dimensions=len(embedding),
                    processing_time=processing_time / len(texts)
                )
                results.append(result)
                
                # Cache if enabled
                if self.cache_embeddings:
                    cache_key = self._cache_key(text)
                    self._cache[cache_key] = result
            
            return results
            
        except Exception as e:
            logging.error(f"OpenAI batch embedding failed: {e}")
            # Fallback to individual processing
            return [self.embed_text(text) for text in texts]
    
    def similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        try:
            # Convert to numpy arrays
            a = np.array(vec1)
            b = np.array(vec2)
            
            # Cosine similarity
            cos_sim = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
            return float(cos_sim)
            
        except Exception as e:
            logging.error(f"Similarity calculation failed: {e}")
            return 0.0
    
    def get_info(self) -> Dict[str, Any]:
        """Get service information."""
        return {
            "backend_type": self.backend_type,
            "model_name": self.model_name,
            "dimensions": self.dimensions,
            "cache_size": len(self._cache),
            "cache_enabled": self.cache_embeddings
        }

# Factory function for easy initialization
def create_embedding_service(method: str = "auto", **kwargs) -> EmbeddingService:
    """
    Factory function to create embedding service with auto-detection.
    
    Args:
        method: "auto", "cpu", "openai", or "sentence_transformers"
        **kwargs: Additional arguments for EmbeddingService
        
    Returns:
        Configured EmbeddingService instance
    """
    if method == "auto":
        # Try CPU first (Sentence-Transformers), then OpenAI
        try:
            return EmbeddingService(preferred_method="cpu", **kwargs)
        except Exception:
            logging.info("CPU method failed, trying OpenAI...")
            return EmbeddingService(preferred_method="openai", **kwargs)
    else:
        return EmbeddingService(preferred_method=method, **kwargs)

# Test and example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Test embedding service
    service = create_embedding_service(method="auto")
    
    print(f"✅ Embedding service ready: {service.get_info()}")
    
    # Test single embedding
    test_text = "3 seil, to nye i fjor og ett gammelt"
    result = service.embed_text(test_text)
    
    print(f"Embedded '{test_text}':")
    print(f"- Dimensions: {result.dimensions}")
    print(f"- Processing time: {result.processing_time:.3f}s")
    print(f"- Vector sample: {result.vector[:5]}...")
    
    # Test batch embeddings
    test_texts = [
        "motoren har hatt jevnlig vedlikehold",
        "interiøret er i god stand",
        "gps og vhf radio er installert"
    ]
    
    batch_results = service.embed_batch(test_texts)
    print(f"\nBatch embedded {len(batch_results)} texts")
    
    # Test similarity
    sim = service.similarity(batch_results[0].vector, batch_results[1].vector)
    print(f"Similarity between text 1 and 2: {sim:.3f}") 