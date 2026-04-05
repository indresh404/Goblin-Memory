"""
instant_index.py — Fast Keyword Search Index
Layer 1 of the Three-Tier Query System.
Maps user keywords directly to node titles + content in <1ms.

Builds an inverted index from:
  - Node titles (split into words)
  - YAML keywords
  - YAML summary words
  - Section names (Problem, Features, etc.)
"""

import json
from pathlib import Path
from typing import List, Dict, Any

from obsidian import _load_index, read_node


class InstantIndex:
    def __init__(self):
        self._cache = {}
        self._last_mtime = 0
        from obsidian import INDEX_FILE
        self.index_file = INDEX_FILE

    def _build_inverted_index(self):
        if not self.index_file.exists():
            return {}

        mtime = self.index_file.stat().st_mtime
        if mtime == self._last_mtime and self._cache:
            return self._cache

        index_data = _load_index()
        inverted = {}

        for title, meta in index_data.items():
            node_entry = {
                "title": title,
                "summary": meta.get("summary", ""),
                "type": meta.get("type", "note"),
            }

            # Collect all searchable words for this node
            words = set()

            # 1. Title words (most important)
            for w in title.lower().replace("_", " ").replace("-", " ").split():
                if len(w) > 2:
                    words.add(w)

            # 2. YAML keywords
            kw_list = meta.get("keywords", [])
            if isinstance(kw_list, list):
                for kw in kw_list:
                    if isinstance(kw, str):
                        for w in kw.lower().split():
                            if len(w) > 2:
                                words.add(w)

            # 3. Summary words
            summary = meta.get("summary", "")
            if isinstance(summary, str):
                for w in summary.lower().replace(",", " ").replace(".", " ").split():
                    if len(w) > 2:
                        words.add(w)

            # 4. Tags
            tags = meta.get("tags", [])
            if isinstance(tags, list):
                for tag in tags:
                    if isinstance(tag, str) and len(tag) > 2:
                        words.add(tag.lower())

            # Register this node under each word
            for word in words:
                if word not in inverted:
                    inverted[word] = []
                inverted[word].append(node_entry)

        self._cache = inverted
        self._last_mtime = mtime
        return self._cache

    def search(self, query: str) -> List[Dict[str, Any]]:
        """
        Tokenize query, match against inverted index.
        Returns deduplicated node entries sorted by match score.
        """
        inverted = self._build_inverted_index()
        if not inverted:
            return []

        # Tokenize query
        query_words = set()
        for w in query.lower().replace("?", "").replace(".", "").replace(",", "").replace("'", "").split():
            if len(w) > 2:
                query_words.add(w)

        matched_nodes = {}

        # Exact match
        for word in query_words:
            if word in inverted:
                for node in inverted[word]:
                    title = node["title"]
                    if title not in matched_nodes:
                        matched_nodes[title] = dict(node)
                        matched_nodes[title]["score"] = 1
                    else:
                        matched_nodes[title]["score"] += 1

        # Partial/prefix match (if exact found < 2 results)
        if len(matched_nodes) < 2:
            for word in query_words:
                for idx_word, nodes in inverted.items():
                    if idx_word.startswith(word) or word.startswith(idx_word):
                        for node in nodes:
                            title = node["title"]
                            if title not in matched_nodes:
                                matched_nodes[title] = dict(node)
                                matched_nodes[title]["score"] = 0.5
                            else:
                                matched_nodes[title]["score"] += 0.5

        results = list(matched_nodes.values())
        results.sort(key=lambda x: x["score"], reverse=True)
        return results


# Singleton
_instant_index = InstantIndex()


def instant_keyword_search(query: str) -> List[Dict[str, Any]]:
    return _instant_index.search(query)


if __name__ == "__main__":
    import sys
    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "features"
    print(f"Searching for: {query}")
    results = instant_keyword_search(query)
    if results:
        for r in results:
            print(f"  [{r['score']:.1f}] {r['title']}: {r.get('summary', 'N/A')}")
    else:
        print("  No results.")
