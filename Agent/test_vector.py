# test_vector.py - Test vector memory performance

from vector_memory import get_vector_memory, reindex_all, smart_search
from obsidian import list_all_nodes
import time

def test_performance():
    print("🧠 Testing Vector Memory Performance")
    print("=" * 50)
    
    # Check nodes
    nodes = list_all_nodes()
    print(f"📚 Total nodes in vault: {len(nodes)}")
    
    # Initialize vector memory
    vm = get_vector_memory()
    if not vm:
        print("❌ Vector memory not available")
        return
    
    # Index if needed
    stats = vm.get_stats()
    if stats['total_nodes'] == 0:
        print("📚 Indexing nodes...")
        start = time.time()
        reindex_all()
        elapsed = time.time() - start
        print(f"  ✓ Indexed in {elapsed:.2f} seconds")
    
    # Test search speed
    test_queries = [
        "What are the main features?",
        "How does patient management work?",
        "Tell me about AI symptom checking",
        "Database and API structure",
        "Future roadmap"
    ]
    
    print("\n🔍 Testing search speed and accuracy:")
    print("-" * 40)
    
    total_time = 0
    for query in test_queries:
        start = time.time()
        results = smart_search(query, top_k=3)
        elapsed = time.time() - start
        
        total_time += elapsed
        print(f"\n  Query: '{query}'")
        print(f"  Time: {elapsed*1000:.1f}ms")
        for r in results[:2]:
            print(f"    • {r['title']} (score: {r['similarity']:.3f})")
    
    print(f"\n📊 Average search time: {total_time/len(test_queries)*1000:.1f}ms")
    print(f"✅ Vector memory is ready for instant recall!")

if __name__ == "__main__":
    test_performance()