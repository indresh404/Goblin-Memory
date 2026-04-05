# test_speed.py - Benchmark response times

import time
from vector_memory import smart_search
from ai_call import ai_fast
from fast_ask import fast_ask

def test_speed():
    print("🚀 AI Brain Speed Test")
    print("=" * 40)
    
    queries = [
        "What are the main features?",
        "Who are the users?",
        "How does AI work?",
    ]
    
    for query in queries:
        print(f"\n📝 Query: {query}")
        
        # Test fast_ask
        start = time.time()
        result = fast_ask(query)
        elapsed = time.time() - start
        print(f"  ⚡ Fast mode: {elapsed:.2f}s")
        
        # Test just vector search
        start = time.time()
        results = smart_search(query, top_k=2)
        elapsed = time.time() - start
        print(f"  🔍 Vector search only: {elapsed*1000:.0f}ms")
        
        print(f"  💾 Cache used: {'Yes' if '⚡' in result else 'No'}")

if __name__ == "__main__":
    test_speed()