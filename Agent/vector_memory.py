# vector_memory.py - Vector-based semantic search for AI Brain

import json
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import hashlib

# Try importing optional dependencies
try:
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False
    print("⚠️ sentence-transformers not installed. Run: pip install sentence-transformers")

try:
    import chromadb
    from chromadb.config import Settings
    HAS_CHROMADB = True
except ImportError:
    HAS_CHROMADB = False
    print("⚠️ chromadb not installed. Run: pip install chromadb")

from obsidian import list_all_nodes, read_node

# ─── Configuration ──────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
MEMORY_PATH = BASE_DIR / "Memory"
VECTOR_DB_PATH = MEMORY_PATH / ".vector_db"
CACHE_FILE = MEMORY_PATH / ".query_cache.json"

# Use lightweight model for speed (384 dimensions)
# Options: 'all-MiniLM-L6-v2' (fastest), 'all-mpnet-base-v2' (better quality)
EMBEDDING_MODEL = 'all-MiniLM-L6-v2'

class VectorMemory:
    """Semantic search engine for AI Brain nodes"""
    
    def __init__(self):
        self.model = None
        self.client = None
        self.collection = None
        self.cache = {}
        self._load_cache()
        
        if HAS_SENTENCE_TRANSFORMERS and HAS_CHROMADB:
            self._initialize()
        else:
            print("⚠️ Vector memory unavailable - missing dependencies")
    
    def _load_cache(self):
        """Load query cache from disk"""
        if CACHE_FILE.exists():
            try:
                with open(CACHE_FILE, 'r') as f:
                    self.cache = json.load(f)
            except:
                self.cache = {}
    
    def _save_cache(self):
        """Save query cache to disk"""
        try:
            with open(CACHE_FILE, 'w') as f:
                json.dump(self.cache, f, indent=2)
        except:
            pass
    
    def _initialize(self):
        """Initialize embedding model and vector database"""
        print("🔧 Initializing Vector Memory...")
        
        # Load embedding model
        self.model = SentenceTransformer(EMBEDDING_MODEL)
        print(f"  ✓ Loaded embedding model: {EMBEDDING_MODEL}")
        
        # Initialize ChromaDB
        VECTOR_DB_PATH.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(
            path=str(VECTOR_DB_PATH),
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Get or create collection
        try:
            self.collection = self.client.get_collection("ai_brain_nodes")
            print(f"  ✓ Loaded existing vector collection")
        except:
            self.collection = self.client.create_collection(
                name="ai_brain_nodes",
                metadata={"hnsw:space": "cosine"}
            )
            print(f"  ✓ Created new vector collection")
    
    def embed_text(self, text: str) -> List[float]:
        """Convert text to vector embedding"""
        if not self.model:
            return None
        if not text or len(text.strip()) < 5:
            text = "empty node"
        # Limit text length for speed (first 2000 chars usually contains key info)
        text = text[:2000]
        embedding = self.model.encode(text, normalize_embeddings=True)
        return embedding.tolist()
    
    def index_node(self, title: str, content: str, metadata: Dict = None) -> bool:
        """Add or update a node in the vector database"""
        if not self.model or not self.collection:
            return False
        
        if not content or len(content.strip()) < 10:
            content = f"{title} - AI Brain knowledge node"
        
        embedding = self.embed_text(content)
        if embedding is None:
            return False
        
        if metadata is None:
            metadata = {}
        metadata["title"] = title
        metadata["updated"] = datetime.now().isoformat()
        
        try:
            # Check if node already exists
            existing = self.collection.get(ids=[title])
            if existing['ids']:
                # Update existing
                self.collection.update(
                    ids=[title],
                    embeddings=[embedding],
                    metadatas=[metadata],
                    documents=[content[:1000]]
                )
            else:
                # Add new
                self.collection.add(
                    ids=[title],
                    embeddings=[embedding],
                    metadatas=[metadata],
                    documents=[content[:1000]]
                )
            return True
        except Exception as e:
            print(f"  ✗ Failed to index {title}: {e}")
            return False
    
    def index_all_nodes(self, verbose: bool = True) -> int:
        """Index all existing nodes in the vault"""
        if not self.model:
            if verbose:
                print("⚠️ Vector memory not available")
            return 0
        
        nodes = list_all_nodes()
        if verbose:
            print(f"\n📚 Indexing {len(nodes)} nodes...")
        
        indexed = 0
        for i, node_meta in enumerate(nodes):
            title = node_meta["title"]
            node = read_node(title)
            if node:
                content = node["content"]
                if self.index_node(title, content, {"type": node_meta.get("type", "note")}):
                    indexed += 1
                    if verbose and (i + 1) % 10 == 0:
                        print(f"  Indexed {indexed}/{len(nodes)} nodes")
        
        if verbose:
            print(f"  ✓ Successfully indexed {indexed} nodes")
        return indexed
    
    def search(self, query: str, top_k: int = 3, use_cache: bool = True) -> List[Dict[str, Any]]:
        """
        Search for relevant nodes using vector similarity.
        Returns list of nodes with relevance scores.
        """
        if not self.model or not self.collection:
            return []
        
        if not query.strip():
            return []
        
        # Check cache first
        cache_key = hashlib.md5(f"{query}:{top_k}".encode()).hexdigest()
        if use_cache and cache_key in self.cache:
            cached = self.cache[cache_key]
            # Verify cached nodes still exist
            if all(self._node_exists(r['title']) for r in cached):
                return cached
        
        # Embed the query
        query_embedding = self.embed_text(query)
        if query_embedding is None:
            return []
        
        # Search in ChromaDB
        try:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                include=["documents", "metadatas", "distances"]
            )
        except Exception as e:
            print(f"Search error: {e}")
            return []
        
        # Format results
        relevant_nodes = []
        if results['ids'] and results['ids'][0]:
            for i, node_id in enumerate(results['ids'][0]):
                distance = results['distances'][0][i] if results['distances'] else 0
                similarity = 1 - distance  # Convert distance to similarity
                
                # Only include if similarity is reasonable (>0.2)
                if similarity > 0.2:
                    node = read_node(node_id)
                    if node:
                        result = {
                            "title": node_id,
                            "content": node["content"],
                            "similarity": round(similarity, 3),
                            "type": results['metadatas'][0][i].get("type", "note") if results['metadatas'] else "note"
                        }
                        relevant_nodes.append(result)
        
        # Cache results
        if use_cache and relevant_nodes:
            self.cache[cache_key] = relevant_nodes
            self._save_cache()
        
        return relevant_nodes
    
    def _node_exists(self, title: str) -> bool:
        """Check if a node still exists"""
        node = read_node(title)
        return node is not None
    
    def delete_node(self, title: str) -> bool:
        """Remove a node from vector index"""
        if not self.collection:
            return False
        try:
            self.collection.delete(ids=[title])
            return True
        except:
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get collection statistics"""
        if not self.collection:
            return {"available": False, "total_nodes": 0}
        
        count = self.collection.count()
        return {
            "available": True,
            "total_nodes": count,
            "embedding_model": EMBEDDING_MODEL,
            "cache_size": len(self.cache),
            "collection_name": "ai_brain_nodes"
        }
    
    def clear_cache(self):
        """Clear query cache"""
        self.cache = {}
        self._save_cache()

    def clear_all(self):
        """Clear the collection completely by deleting all items"""
        if self.collection:
            try:
                # Delete collection and recreate it
                self.client.delete_collection("ai_brain_nodes")
                self.collection = self.client.create_collection(
                    name="ai_brain_nodes",
                    metadata={"hnsw:space": "cosine"}
                )
            except Exception as e:
                print(f"Error resetting vector collection: {e}")
        self.clear_cache()

# Global singleton instance
_vector_memory = None

def get_vector_memory() -> Optional[VectorMemory]:
    """Get or create vector memory instance"""
    global _vector_memory
    if _vector_memory is None and HAS_SENTENCE_TRANSFORMERS and HAS_CHROMADB:
        _vector_memory = VectorMemory()
    return _vector_memory


def smart_search(query: str, top_k: int = 3) -> List[Dict[str, Any]]:
    """Quick semantic search interface"""
    vm = get_vector_memory()
    if vm:
        return vm.search(query, top_k)
    return []


def reindex_all() -> int:
    """Rebuild the entire vector index"""
    vm = get_vector_memory()
    if vm:
        return vm.index_all_nodes()
    return 0

if __name__ == "__main__":
    # Test the vector memory
    print("Testing Vector Memory...")
    vm = get_vector_memory()
    
    if vm:
        stats = vm.get_stats()
        print(f"\n📊 Vector Memory Stats: {stats}")
        
        if stats['total_nodes'] == 0:
            print("\nNo nodes indexed. Indexing now...")
            vm.index_all_nodes()
        
        # Test search
        print("\n🔍 Testing search...")
        test_queries = [
            "healthcare features",
            "patient management",
            "AI symptom checker",
            "database schema"
        ]
        
        for query in test_queries:
            print(f"\n  Query: '{query}'")
            results = vm.search(query, top_k=2)
            for r in results:
                print(f"    • {r['title']} (score: {r['similarity']:.3f})")
    else:
        print("❌ Vector memory unavailable. Please install:")
        print("  pip install sentence-transformers chromadb")