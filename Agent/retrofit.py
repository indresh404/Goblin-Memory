"""
retrofit.py — One-off script to heal old nodes
It loads the existing _index.json and injects empty 'keywords' and 'summary'
if they are missing, ensuring backward compatibility with new features.
"""

from obsidian import _load_index, _save_index, _rewrite_node_from_index

def heal_nodes():
    print("Healing existing nodes to include 'keywords' and 'summary'...")
    idx = _load_index()
    count = 0
    for title, meta in idx.items():
        changed = False
        if "keywords" not in meta:
            meta["keywords"] = []
            changed = True
        if "summary" not in meta:
            meta["summary"] = ""
            changed = True
        
        if changed:
            idx[title] = meta
            # We save index first so rewrite node picks up the new meta
            _save_index(idx)
            try:
                _rewrite_node_from_index(title, idx)
                count += 1
                print(f"  ✓ Upgraded node: {title}")
            except Exception as e:
                print(f"  ✗ Failed to rewrite {title}: {e}")
                
    print(f"\nDone! Upgraded {count} nodes successfully.")

if __name__ == "__main__":
    heal_nodes()
