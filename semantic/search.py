#!/usr/bin/env python3
"""
Semantisk søkegrensesnitt for båtannonser.
Kombinerer chunk-basert similarity search med aspect scoring.
"""

import logging
import hashlib
import time
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime, timedelta

from .embedder import EmbeddingService, create_embedding_service
from .chunker import BoatDescriptionChunker
from .scorer import SemanticScorer, AspectType, AspectScore

@dataclass
class SearchResult:
    """Resultat fra semantisk søk."""
    ad_id: int
    title: str
    description: str
    similarity_score: float
    matching_chunks: List[str]
    aspect_scores: Optional[Dict[str, AspectScore]] = None
    distance: Optional[float] = None  # PgVector distance

@dataclass
class SearchQuery:
    """Strukturert søkespørring."""
    text: str
    aspects: Optional[List[str]] = None  # Filtrer på spesifikke aspekter
    min_score: float = 0.6  # Minimum similarity score
    limit: int = 10
    include_aspect_scoring: bool = False

class SemanticSearchEngine:
    """
    Semantisk søkemotor for båtannonser.
    Bruker PgVector for rask similarity search kombinert med aspect-basert scoring.
    """
    
    def __init__(self, 
                 db_connection_func=None,
                 embedding_service: Optional[EmbeddingService] = None,
                 cache_ttl_hours: int = 1):
        
        self.get_db_connection = db_connection_func
        self.embedding_service = embedding_service or create_embedding_service()
        self.chunker = BoatDescriptionChunker()
        self.scorer = SemanticScorer(self.embedding_service)
        self.cache_ttl = timedelta(hours=cache_ttl_hours)
        
        logging.info(f"✅ Semantic search engine ready with {self.embedding_service.get_info()}")
    
    def search(self, query: SearchQuery) -> List[SearchResult]:
        """
        Hovedsøkemetode.
        
        Args:
            query: SearchQuery objekt med søkeparametere
            
        Returns:
            Liste av SearchResult objekter sortert etter relevans
        """
        if not query.text or len(query.text.strip()) < 3:
            return []
        
        # 1. Sjekk cache først
        cached_results = self._get_cached_results(query)
        if cached_results is not None:
            return cached_results
        
        # 2. Generer embedding for søkespørringen
        try:
            query_embedding = self.embedding_service.embed_text(query.text)
        except Exception as e:
            logging.error(f"Failed to embed query '{query.text}': {e}")
            return []
        
        # 3. Søk i PgVector database
        similarity_results = self._vector_search(query_embedding.vector, query.limit * 2)  # Get more for filtering
        
        # 4. Filtrer og ranger resultater
        filtered_results = self._filter_and_rank_results(similarity_results, query)
        
        # 5. Legg til aspect scoring hvis ønsket
        if query.include_aspect_scoring:
            filtered_results = self._add_aspect_scores(filtered_results, query.aspects)
        
        # 6. Cache resultater
        self._cache_results(query, filtered_results)
        
        return filtered_results[:query.limit]
    
    def search_by_aspect(self, aspect: str, query_text: str, limit: int = 10) -> List[SearchResult]:
        """
        Søk spesifikt innenfor en aspect (seil, motor, etc.).
        
        Args:
            aspect: Aspect å søke i ("sails", "motor", "condition", etc.)
            query_text: Søketekst
            limit: Maksimalt antall resultater
            
        Returns:
            Liste av SearchResult objekter relevant for aspect
        """
        # Lag aspect-spesifikk søk
        enhanced_query = f"{aspect}: {query_text}"
        
        query = SearchQuery(
            text=enhanced_query,
            aspects=[aspect],
            limit=limit,
            include_aspect_scoring=True,
            min_score=0.5  # Litt lavere threshold for aspect-spesifikt søk
        )
        
        return self.search(query)
    
    def find_similar_boats(self, reference_ad_id: int, limit: int = 5) -> List[SearchResult]:
        """
        Finn lignende båter basert på en referanse-annonse.
        
        Args:
            reference_ad_id: ID til referanse-annonsen
            limit: Antall lignende båter å returnere
            
        Returns:
            Liste av lignende SearchResult objekter
        """
        # Hent referanse-beskrivelse
        ref_description = self._get_ad_description(reference_ad_id)
        if not ref_description:
            return []
        
        # Søk med referanse-beskrivelsen
        query = SearchQuery(
            text=ref_description,
            limit=limit + 1,  # +1 fordi vi filtrerer bort originalen
            min_score=0.7,  # Høyere threshold for "lignende"
            include_aspect_scoring=True
        )
        
        results = self.search(query)
        
        # Fjern original annonse fra resultater
        filtered_results = [r for r in results if r.ad_id != reference_ad_id]
        
        return filtered_results[:limit]
    
    def _vector_search(self, query_vector: List[float], limit: int) -> List[Dict[str, Any]]:
        """Utfør PgVector similarity search."""
        if not self.get_db_connection:
            logging.error("Database connection function not provided")
            return []
        
        try:
            with self.get_db_connection() as conn:
                with conn.cursor() as cur:
                    # PgVector cosine similarity search
                    sql = """
                    SELECT
                        tc.ad_id,
                        tc.chunk_text,
                        tc.chunk_order,
                        a.title,
                        a.description,
                        (tc.embedding <=> %s::vector) as distance
                    FROM sailboat.text_chunks tc
                    JOIN sailboat.ads a ON a.ad_id = tc.ad_id
                    WHERE a.active = TRUE AND a.has_embeddings = TRUE
                    ORDER BY tc.embedding <=> %s::vector
                    LIMIT %s;
                    """
                    
                    # Convert query vector to string format for PgVector
                    vector_str = '[' + ','.join(map(str, query_vector)) + ']'
                    
                    cur.execute(sql, (vector_str, vector_str, limit))
                    rows = cur.fetchall()
                    
                    # Group results by ad_id
                    ad_results = {}
                    for row in rows:
                        ad_id, chunk_text, chunk_order, title, description, distance = row
                        
                        if ad_id not in ad_results:
                            ad_results[ad_id] = {
                                'ad_id': ad_id,
                                'title': title,
                                'description': description,
                                'chunks': [],
                                'min_distance': distance,
                                'avg_distance': distance
                            }
                        
                        ad_results[ad_id]['chunks'].append({
                            'text': chunk_text,
                            'order': chunk_order,
                            'distance': distance
                        })
                        
                        # Update distance metrics
                        ad_results[ad_id]['min_distance'] = min(ad_results[ad_id]['min_distance'], distance)
                        
                        # Recalculate average
                        distances = [c['distance'] for c in ad_results[ad_id]['chunks']]
                        ad_results[ad_id]['avg_distance'] = sum(distances) / len(distances)
                    
                    return list(ad_results.values())
                    
        except Exception as e:
            logging.error(f"Vector search failed: {e}")
            return []
    
    def _filter_and_rank_results(self, similarity_results: List[Dict[str, Any]], 
                                query: SearchQuery) -> List[SearchResult]:
        """Filtrer og ranger søkeresultater."""
        filtered_results = []
        
        for result in similarity_results:
            # Konverter distance til similarity score (0-1)
            # PgVector distance: lavere = mer lignende
            max_distance = 2.0  # Cosine distance max
            similarity_score = max(0.0, 1.0 - (result['min_distance'] / max_distance))
            
            # Filtrer basert på minimum score
            if similarity_score < query.min_score:
                continue
            
            # Finn beste matching chunks
            sorted_chunks = sorted(result['chunks'], key=lambda c: c['distance'])
            matching_chunks = [c['text'] for c in sorted_chunks[:3]]  # Top 3 chunks
            
            search_result = SearchResult(
                ad_id=result['ad_id'],
                title=result['title'],
                description=result['description'],
                similarity_score=similarity_score,
                matching_chunks=matching_chunks,
                distance=result['min_distance']
            )
            
            filtered_results.append(search_result)
        
        # Sorter etter similarity score (høyest først)
        filtered_results.sort(key=lambda r: r.similarity_score, reverse=True)
        
        return filtered_results
    
    def _add_aspect_scores(self, results: List[SearchResult], 
                          target_aspects: Optional[List[str]]) -> List[SearchResult]:
        """Legg til aspect scoring for søkeresultater."""
        aspects_to_score = None
        if target_aspects:
            try:
                aspects_to_score = [AspectType(aspect) for aspect in target_aspects]
            except ValueError as e:
                logging.warning(f"Invalid aspect in {target_aspects}: {e}")
        
        for result in results:
            try:
                scores = self.scorer.score_description(result.description, aspects_to_score)
                # Convert to string keys for JSON serialization
                result.aspect_scores = {aspect.value: score for aspect, score in scores.items()}
            except Exception as e:
                logging.error(f"Aspect scoring failed for ad {result.ad_id}: {e}")
                result.aspect_scores = {}
        
        return results
    
    def _get_ad_description(self, ad_id: int) -> Optional[str]:
        """Hent beskrivelse for en spesifikk annonse."""
        if not self.get_db_connection:
            return None
        
        try:
            with self.get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT description FROM sailboat.ads WHERE ad_id = %s AND active = TRUE",
                        (ad_id,)
                    )
                    row = cur.fetchone()
                    return row[0] if row else None
        except Exception as e:
            logging.error(f"Failed to get description for ad {ad_id}: {e}")
            return None
    
    def _get_cached_results(self, query: SearchQuery) -> Optional[List[SearchResult]]:
        """Sjekk om søkeresultater finnes i cache."""
        if not self.get_db_connection:
            return None
        
        try:
            query_hash = self._hash_query(query)
            
            with self.get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT result_ad_ids, similarity_scores, expires_at
                        FROM sailboat.search_cache 
                        WHERE query_hash = %s AND expires_at > NOW()
                    """, (query_hash,))
                    
                    row = cur.fetchone()
                    if not row:
                        return None
                    
                    ad_ids, scores, expires_at = row
                    
                    # Hent annonse-detaljer
                    if ad_ids:
                        placeholders = ','.join(['%s'] * len(ad_ids))
                        cur.execute(f"""
                            SELECT ad_id, title, description 
                            FROM sailboat.ads 
                            WHERE ad_id IN ({placeholders}) AND active = TRUE
                            ORDER BY array_position(%s, ad_id)
                        """, ad_ids + [ad_ids])
                        
                        ad_rows = cur.fetchall()
                        
                        # Rekonstruer SearchResult objekter
                        results = []
                        for i, (ad_id, title, description) in enumerate(ad_rows):
                            if i < len(scores):
                                result = SearchResult(
                                    ad_id=ad_id,
                                    title=title,
                                    description=description,
                                    similarity_score=scores[i],
                                    matching_chunks=[]  # Ikke cached
                                )
                                results.append(result)
                        
                        logging.debug(f"Cache hit for query: {query.text[:50]}...")
                        return results
                    
        except Exception as e:
            logging.error(f"Cache retrieval failed: {e}")
        
        return None
    
    def _cache_results(self, query: SearchQuery, results: List[SearchResult]):
        """Cache søkeresultater."""
        if not self.get_db_connection or not results:
            return
        
        try:
            query_hash = self._hash_query(query)
            ad_ids = [r.ad_id for r in results]
            scores = [r.similarity_score for r in results]
            
            with self.get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO sailboat.search_cache 
                        (query_hash, query_text, result_ad_ids, similarity_scores, search_method, expires_at)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (query_hash) DO UPDATE SET
                            result_ad_ids = EXCLUDED.result_ad_ids,
                            similarity_scores = EXCLUDED.similarity_scores,
                            expires_at = EXCLUDED.expires_at,
                            created_at = NOW()
                    """, (
                        query_hash,
                        query.text,
                        ad_ids,
                        scores,
                        'semantic_vector',
                        datetime.now() + self.cache_ttl
                    ))
                    conn.commit()
                    
        except Exception as e:
            logging.error(f"Failed to cache results: {e}")
    
    def _hash_query(self, query: SearchQuery) -> str:
        """Generer hash for søkespørring for caching."""
        query_str = f"{query.text}|{query.aspects}|{query.min_score}|{query.limit}|{query.include_aspect_scoring}"
        return hashlib.md5(query_str.encode()).hexdigest()

# Convenience functions
def search_boats(query_text: str, limit: int = 10, min_score: float = 0.6,
                aspects: Optional[List[str]] = None, db_connection_func=None) -> List[Dict[str, Any]]:
    """
    Convenience function for å søke i båtannonser.
    
    Args:
        query_text: Søketekst
        limit: Maksimalt antall resultater
        min_score: Minimum similarity score
        aspects: Spesifikke aspekter å inkludere scoring for
        db_connection_func: Database connection function
        
    Returns:
        Liste av søkeresultater som dict
    """
    engine = SemanticSearchEngine(db_connection_func)
    
    query = SearchQuery(
        text=query_text,
        limit=limit,
        min_score=min_score,
        aspects=aspects,
        include_aspect_scoring=bool(aspects)
    )
    
    results = engine.search(query)
    
    # Convert to dict for JSON serialization
    return [
        {
            'ad_id': r.ad_id,
            'title': r.title,
            'description': r.description[:200] + '...' if len(r.description) > 200 else r.description,
            'similarity_score': round(r.similarity_score, 3),
            'matching_chunks': r.matching_chunks,
            'aspect_scores': r.aspect_scores
        }
        for r in results
    ]

# Test and example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Mock database function for testing
    def mock_db():
        class MockConnection:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def cursor(self): return self
            def fetchall(self): return []
            def fetchone(self): return None
            def execute(self, *args): pass
            def commit(self): pass
        return MockConnection()
    
    # Test search engine
    engine = SemanticSearchEngine(mock_db)
    
    # Test query
    query = SearchQuery(
        text="båt med nye seil og god motor",
        limit=5,
        include_aspect_scoring=True,
        aspects=["sails", "motor"]
    )
    
    print(f"🔍 Test query: {query.text}")
    print(f"Embedding service: {engine.embedding_service.get_info()}")
    
    # Note: Actual search won't work without real database
    print("Search engine ready for database integration!") 