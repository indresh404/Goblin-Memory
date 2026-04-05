# fast_ask.py - Lightning fast queries bypassing full context

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from vector_memory import smart_search
from ai_call import ai_fast  # Use fast model
from cache_manager import get_cached_response, cache_response

def fast_ask(query: str) -> str:
    """Ultra-fast query - under 2 seconds"""
    
    # 1. Get top 2 relevant nodes only
    relevant = smart_search(query, top_k=2)
    
    if not relevant:
        return "No relevant information found."
    
    # 2. Build minimal context
    context = "\n".join([f"- {r['title']}: {r['content'][:200]}" for r in relevant])
    
    # 3. Check cache
    cached = get_cached_response(query, context)
    if cached:
        return f"⚡ {cached}"
    
    # 4. Fast AI call with small model
    prompt = f"""Context:
{context}

Question: {query}

Answer briefly in 1-2 sentences:"""
    
    response = ai_fast(prompt)
    
    # Cache response
    cache_response(query, context, response)
    
    return response

if __name__ == "__main__":
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        print(fast_ask(query))
    else:
        print("Usage: python fast_ask.py 'your question here'")
        