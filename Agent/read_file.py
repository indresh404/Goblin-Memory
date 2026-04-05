# read_file.py - Updated with vector search

from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime

from obsidian import read_node, search_nodes
from vector_memory import smart_search, get_vector_memory
# read_file.py - Add to existing file

from cache_manager import get_cached_response, cache_response, clear_cache
import hashlib

def smart_context_for_query(query: str, max_nodes: int = 2) -> str:  # Reduced to 2 nodes for speed
    """
    Get relevant context using semantic vector search.
    Now returns fewer nodes for faster LLM processing.
    """
    # Try vector search first
    relevant = smart_search(query, top_k=max_nodes)
    
    if relevant:
        context_parts = []
        for node in relevant:
            # Truncate content to 300 chars for speed
            short_content = node['content'][:300]
            context_parts.append(f"""
**{node['title']}** (relevance: {node['similarity']:.2f})
{short_content}
""")
        return "\n".join(context_parts)
    
    # Fallback to fuzzy search
    matches = search_nodes(query, limit=max_nodes)
    if matches:
        context_parts = []
        for title in matches:
            node = read_node(title)
            if node:
                context_parts.append(f"**{title}**\n{node['content'][:300]}")
        return "\n\n".join(context_parts)
    
    return "No relevant nodes found."


def get_cached_or_generate(query: str, context: str, generate_func) -> str:
    """Get from cache or generate new response"""
    # Check cache
    cached = get_cached_response(query, context)
    if cached:
        return f"[⚡ Cached response]\n{cached}"
    
    # Generate new response
    response = generate_func()
    
    # Cache for future
    cache_response(query, context, response)
    
    return response

def get_node_context_with_vectors(node_titles: List[str]) -> str:
    """Get context for specific nodes using vector memory"""
    context = []
    for title in node_titles:
        node = read_node(title)
        if node:
            context.append(f"## {title}\n{node['content'][:500]}")
    return "\n\n".join(context)


def append_chat_history(role: str, content: str):
    """Append to chat history file with smart truncation"""
    history_file = Path(__file__).parent.parent / "Memory" / "chat_history.md"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Truncate long content
    if len(content) > 2000:
        content = content[:2000] + "... (truncated)"
    
    with open(history_file, "a", encoding="utf-8") as f:
        f.write(f"\n### {timestamp} - {role.upper()}\n{content}\n")


def load_chat_history(max_lines: int = 50) -> str:
    """Load recent chat history"""
    history_file = Path(__file__).parent.parent / "Memory" / "chat_history.md"
    if not history_file.exists():
        return "No chat history yet."
    
    with open(history_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    # Get last max_lines
    recent = lines[-max_lines:] if len(lines) > max_lines else lines
    return "".join(recent)


def get_vector_stats() -> dict:
    """Get vector memory statistics"""
    vm = get_vector_memory()
    if vm:
        return vm.get_stats()
    return {"available": False}