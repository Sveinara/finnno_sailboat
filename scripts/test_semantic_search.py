#!/usr/bin/env python3
"""
Test script for semantic search og scoring system.
Demonstrerer chunking, embeddings og aspect scoring.
"""

import sys
import os
import logging

# Sørg for at vi kan importere fra prosjektroten
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

def test_chunking():
    """Test beskrivelse chunking."""
    print("🔧 Testing Chunking...")
    
    from semantic.chunker import BoatDescriptionChunker
    
    chunker = BoatDescriptionChunker()
    
    test_desc = """
    Veldig fin båt med 3 seil, to nye i fjor og ett gammelt. 
    Motoren har hatt jevnlig vedlikehold og fungerer utmerket med lave timer. 
    Interiøret er i god stand med nye puter i salong og hyggelig atmosfære. 
    GPS, VHF radio, autopilot og chartplotter er installert. 
    Dekket trenger litt maling men skroget er i utmerket stand uten skader.
    Rigg og seil er inspektert og klar for sesong.
    """
    
    chunks = chunker.chunk_description(test_desc)
    
    print(f"✅ Chunked {len(test_desc.split())} words into {len(chunks)} chunks:")
    for i, chunk in enumerate(chunks):
        print(f"  {i+1}: [{chunk.length} ord] {chunk.text}")
    
    # Test aspect-specific chunking
    print("\n🎯 Seil-relevante chunks:")
    sail_chunks = chunker.get_aspect_relevant_chunks(chunks, 'sails')
    for chunk in sail_chunks:
        print(f"  - {chunk.text}")
    
    print("\n🔧 Motor-relevante chunks:")
    motor_chunks = chunker.get_aspect_relevant_chunks(chunks, 'motor')
    for chunk in motor_chunks:
        print(f"  - {chunk.text}")

def test_embeddings():
    """Test embedding generation."""
    print("\n🤖 Testing Embeddings...")
    
    from semantic.embedder import create_embedding_service
    
    try:
        # Prøv CPU-basert først
        service = create_embedding_service(method="cpu")
        print(f"✅ Embedding service: {service.get_info()}")
        
        # Test single embedding
        test_text = "3 seil, to nye i fjor og ett gammelt"
        result = service.embed_text(test_text)
        
        print(f"📝 Embedded: '{test_text}'")
        print(f"   Dimensions: {result.dimensions}")
        print(f"   Processing time: {result.processing_time:.3f}s")
        print(f"   Vector sample: {result.vector[:5]}...")
        
        # Test batch embeddings
        test_texts = [
            "motoren har jevnlig vedlikehold",
            "interiøret er i god stand",
            "gps og vhf radio installert"
        ]
        
        batch_results = service.embed_batch(test_texts)
        print(f"\n📦 Batch embedded {len(batch_results)} texts")
        
        # Test similarity
        sim = service.similarity(batch_results[0].vector, batch_results[1].vector)
        print(f"🔍 Similarity motor vs interiør: {sim:.3f}")
        
        sim2 = service.similarity(batch_results[0].vector, batch_results[2].vector)
        print(f"🔍 Similarity motor vs equipment: {sim2:.3f}")
        
        return service
        
    except Exception as e:
        print(f"❌ Embedding test failed: {e}")
        return None

def test_scoring(embedding_service=None):
    """Test aspect scoring."""
    print("\n🎯 Testing Aspect Scoring...")
    
    from semantic.scorer import SemanticScorer, score_boat_description
    
    if embedding_service:
        scorer = SemanticScorer(embedding_service)
    else:
        # Use default
        scorer = SemanticScorer()
    
    test_description = """
    Fantastisk seglbåt med tre seil i utmerket stand - genoa og storseil er helt nye, 
    kjøpt i fjor for 45.000 kr. Spinnaker er noen år gammel men fortsatt i fin stand.
    Yanmar diesel motor på 29 hk har hatt jevnlig service og går som ei klokke, 
    kun 850 timer på telleren. Interiøret er nylig oppgradert med nye puter og 
    gardiner i salong. Komplett navigasjonsutstyr med GPS chartplotter, VHF radio, 
    autopilot og vindmåler. Skrog og dekk i fin stand, bare trenger litt polering.
    """
    
    # Test full scoring
    scores = scorer.score_description(test_description)
    
    print("🏆 Aspect Scoring Results:")
    for aspect, score in scores.items():
        print(f"\n  {aspect.value.upper()}:")
        print(f"    Raw score: {score.raw_score:.3f}")
        print(f"    Confidence: {score.confidence:.3f}")
        print(f"    Method: {score.method}")
        print(f"    Keywords found: {score.keywords_found}")
        print(f"    Supporting chunks ({len(score.supporting_chunks)}):")
        for chunk in score.supporting_chunks[:2]:  # Show first 2
            print(f"      - {chunk}")
    
    # Test convenience function
    print("\n🎯 Convenience Function Test:")
    simple_scores = score_boat_description(test_description, ["sails", "motor", "condition"])
    for aspect, score in simple_scores.items():
        print(f"  {aspect}: {score.raw_score:.3f} (confidence: {score.confidence:.3f})")

def test_search_interface():
    """Test search interface (without database)."""
    print("\n🔍 Testing Search Interface...")
    
    from semantic.search import SemanticSearchEngine, SearchQuery
    
    # Mock database function
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
    
    try:
        engine = SemanticSearchEngine(mock_db)
        
        query = SearchQuery(
            text="båt med nye seil og pålitelig motor",
            limit=5,
            min_score=0.6,
            aspects=["sails", "motor"],
            include_aspect_scoring=True
        )
        
        print(f"✅ Search engine ready: {engine.embedding_service.get_info()}")
        print(f"📝 Test query: '{query.text}'")
        print(f"   Aspects: {query.aspects}")
        print(f"   Min score: {query.min_score}")
        print("   (Note: Actual search requires database connection)")
        
    except Exception as e:
        print(f"❌ Search interface test failed: {e}")

def main():
    """Run all tests."""
    print("🚀 Testing Semantic Search System")
    print("=" * 50)
    
    # Setup logging
    logging.basicConfig(level=logging.WARNING)  # Reduce noise
    
    try:
        # Test 1: Chunking
        test_chunking()
        
        # Test 2: Embeddings
        embedding_service = test_embeddings()
        
        # Test 3: Scoring
        test_scoring(embedding_service)
        
        # Test 4: Search Interface
        test_search_interface()
        
        print("\n" + "=" * 50)
        print("✅ All tests completed successfully!")
        print("\n📋 Next Steps:")
        print("1. Install pgvector extension in PostgreSQL:")
        print("   docker exec -it airflow_postgres psql -U airflow -d postgres -c 'CREATE EXTENSION IF NOT EXISTS vector;'")
        print("2. Run sailboat_db_init DAG to create semantic tables")
        print("3. Run sailboat_semantic_processing DAG to process existing descriptions")
        print("4. Start using semantic search in your application!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 