"""
obsidian.py — Memory Goblin Core Vault Manager
Hierarchical per-project Obsidian vault with predefined sections.
Uses a JSON index for O(1) node lookup — no directory scanning.
All nodes are Obsidian-compatible Markdown with YAML frontmatter.
"""

import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from rapidfuzz import fuzz, process


# ─── Paths ────────────────────────────────────────────────────────────────────

BASE_DIR    = Path(__file__).parent.parent          # d:\AI_Brain\
VAULT_DIR   = BASE_DIR / "Memory"                   # Obsidian vault root
INDEX_FILE  = VAULT_DIR / "_index.json"             # Fast lookup index
PROJECTS_DIR = VAULT_DIR / "Projects"

for d in [VAULT_DIR, PROJECTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)


# ─── Predefined Project Sections ──────────────────────────────────────────────
# Every project gets these folders/nodes created automatically.

PREDEFINED_SECTIONS = [
    {
        "key": "Problem_Statements",
        "label": "Problem Statements",
        "description": "Core problems this project aims to solve.",
        "icon": "🎯",
    },
    {
        "key": "Features",
        "label": "Features",
        "description": "Key features and capabilities of the project.",
        "icon": "⚙️",
    },
    {
        "key": "Ideas",
        "label": "Ideas",
        "description": "Brainstormed ideas, experiments, and creative approaches.",
        "icon": "💡",
    },
    {
        "key": "Impact",
        "label": "Impact",
        "description": "Who benefits from this project and how. Social, economic, and technical impact.",
        "icon": "🌍",
    },
    {
        "key": "Technical_Stack",
        "label": "Technical Stack",
        "description": "All technologies, frameworks, and tools used.",
        "icon": "🔧",
        "sub_sections": [
            {"key": "Frontend",  "label": "Frontend",  "description": "UI frameworks, libraries, and design tools."},
            {"key": "Backend",   "label": "Backend",   "description": "Server frameworks, APIs, databases."},
            {"key": "AI_ML",     "label": "AI/ML",     "description": "Machine learning models, pipelines, and data tools."},
            {"key": "Other",     "label": "Other",     "description": "DevOps, CI/CD, monitoring, and miscellaneous tools."},
        ],
    },
    {
        "key": "Benefits",
        "label": "Benefits",
        "description": "Key advantages and value propositions.",
        "icon": "✅",
    },
    {
        "key": "Expected_Outcomes",
        "label": "Expected Outcomes",
        "description": "Measurable goals, KPIs, and success metrics.",
        "icon": "📈",
    },
    {
        "key": "Risks",
        "label": "Risks",
        "description": "Potential challenges, threats, and mitigation strategies.",
        "icon": "⚠️",
    },
    {
        "key": "Milestones",
        "label": "Milestones",
        "description": "Timeline, phases, and key delivery dates.",
        "icon": "📅",
    },
    {
        "key": "Dependencies",
        "label": "Dependencies",
        "description": "External services, APIs, teams, and prerequisites.",
        "icon": "🔗",
    },
]


# ─── Wiki Link Injector ───────────────────────────────────────────────────────

def inject_wiki_links(text: str, skip_title: str = "") -> str:
    """
    Auto-wrap any known node title mentioned in text with [[brackets]].
    Only matches exact titles that appear on their own (not as substrings
    of longer titles). Uses longest-first matching so 'A - B' matches
    before 'A'.
    """
    index = _load_index()
    if not index:
        return text

    # Sort by length descending so longer titles match first
    titles = sorted(index.keys(), key=len, reverse=True)
    already_linked = set()

    for title in titles:
        if title == skip_title:
            continue
        if title in already_linked:
            continue
        display = title.replace("_", " ")
        for variant in [re.escape(title), re.escape(display)]:
            # Only match if not already inside [[ ]] and is a standalone mention
            pattern = rf"(?<!\[)(?<!\w){variant}(?!\w)(?!\])"
            if re.search(pattern, text, flags=re.IGNORECASE):
                text = re.sub(pattern, f"[[{title}]]", text, count=1, flags=re.IGNORECASE)
                already_linked.add(title)
                break  # Only link each title once

    return text


# ─── Index ────────────────────────────────────────────────────────────────────

def _load_index() -> dict:
    if INDEX_FILE.exists():
        try:
            return json.loads(INDEX_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_index(index: dict):
    INDEX_FILE.write_text(
        json.dumps(index, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ─── Node Templates ───────────────────────────────────────────────────────────

def _build_markdown(title: str, content: str, meta: dict) -> str:
    parent_link = f"[[{meta['parent']}]]" if meta.get("parent") else "None"
    children    = meta.get("children", [])
    child_links = ", ".join(f"[[{c}]]" for c in children) or "None"
    tags_line   = ", ".join(meta.get("tags", []))
    keywords_line = ", ".join(meta.get("keywords", []))
    summary_encoded = json.dumps(meta.get("summary", ""))

    # Strip any existing h1 headings matching the title to prevent duplication
    display_title = title.replace('_', ' ')
    content = re.sub(rf'^#\s+{re.escape(title)}\s*$', '', content, flags=re.MULTILINE)
    content = re.sub(rf'^#\s+{re.escape(display_title)}\s*$', '', content, flags=re.MULTILINE)
    # Clean up multiple blank lines left by stripping
    content = re.sub(r'\n{3,}', '\n\n', content).strip()

    linked_content = inject_wiki_links(content, skip_title=title)

    return f"""---
title: {title}
type: {meta.get('type', 'note')}
parent: {meta.get('parent') or 'null'}
children: {json.dumps(children)}
tags: [{tags_line}]
keywords: [{keywords_line}]
summary: {summary_encoded}
created: {meta.get('created', _now())}
updated: {meta.get('updated', _now())}
---

# {title.replace('_', ' ')}

{linked_content}

---
## 🔗 Graph Links
- **Parent:** {parent_link}
- **Children:** {child_links}
"""


def _parse_frontmatter(raw: str) -> tuple[dict, str]:
    """Extract YAML frontmatter dict and body from raw markdown."""
    if not raw.startswith("---"):
        return {}, raw
    end = raw.find("\n---", 4)
    if end == -1:
        return {}, raw
    fm_block = raw[4:end].strip()
    body = raw[end + 4:].strip()
    meta = {}
    for line in fm_block.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            v = v.strip()
            if v.startswith("[") and v.endswith("]"):
                try:
                    v = json.loads(v)
                except Exception:
                    pass
            elif v.lower() == "null":
                v = None
            meta[k.strip()] = v
    return meta, body


# ─── CRUD ─────────────────────────────────────────────────────────────────────

def _safe_filename(title: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "_", title).strip()


def create_node(
    title: str,
    content: str,
    node_type: str = "note",
    parent: Optional[str] = None,
    children: Optional[list] = None,
    tags: Optional[list] = None,
    keywords: Optional[list] = None,
    summary: str = "",
    folder_path: Optional[Path] = None,
) -> Path:
    """Create a new Obsidian node. Returns path to created file."""
    index    = _load_index()
    children = children or []
    tags     = tags or []
    keywords = keywords or []
    now      = _now()

    # Determine save location
    if folder_path:
        folder_path.mkdir(parents=True, exist_ok=True)
        safe_title = _safe_filename(title)
        abs_path   = folder_path / f"{safe_title}.md"
        rel_path   = str(abs_path.relative_to(VAULT_DIR)).replace("\\", "/")
    else:
        safe_title = _safe_filename(title)
        abs_path   = PROJECTS_DIR / f"{safe_title}.md"
        rel_path   = f"Projects/{safe_title}.md"

    meta = {
        "type":     node_type,
        "parent":   parent,
        "children": children,
        "tags":     tags,
        "keywords": keywords,
        "summary":  summary,
        "created":  now,
        "updated":  now,
    }

    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_text(_build_markdown(title, content, meta), encoding="utf-8")

    index[title] = {**meta, "path": rel_path}
    _save_index(index)

    if parent and parent in index:
        _add_child_to_node(parent, title, index)

    return abs_path


def read_node(title: str) -> Optional[dict]:
    """Return node dict: {meta, content, path} or None."""
    index = _load_index()
    if title not in index:
        title = _fuzzy_find(title, index)
        if not title:
            return None

    entry = index[title]
    abs_path = VAULT_DIR / entry["path"]
    if not abs_path.exists():
        return None

    raw  = abs_path.read_text(encoding="utf-8")
    meta, body = _parse_frontmatter(raw)

    body = re.sub(r"\n---\n## 🔗 Graph Links.*", "", body, flags=re.DOTALL).strip()

    return {
        "title":   title,
        "meta":    entry,
        "content": body,
        "path":    abs_path,
        "raw":     raw,
    }


def update_node(title: str, new_content: str, append: bool = False,
                new_keywords: Optional[list] = None, new_summary: Optional[str] = None) -> bool:
    """Update content of an existing node. Optionally update keywords and summary."""
    index = _load_index()
    if title not in index:
        return False

    node = read_node(title)
    if not node:
        return False

    if append:
        content = node["content"] + "\n\n" + new_content
    else:
        content = new_content

    meta = index[title]
    meta["updated"] = _now()
    if new_keywords is not None:
        meta["keywords"] = new_keywords
    if new_summary is not None:
        meta["summary"] = new_summary
    index[title] = meta
    _save_index(index)

    abs_path = VAULT_DIR / meta["path"]
    abs_path.write_text(_build_markdown(title, content, meta), encoding="utf-8")
    return True


def delete_node(title: str) -> bool:
    """Delete a node and remove it from parent's children list."""
    index = _load_index()
    if title not in index:
        return False

    entry = index[title]
    abs_path = VAULT_DIR / entry["path"]
    if abs_path.exists():
        abs_path.unlink()

    parent = entry.get("parent")
    if parent and parent in index:
        index[parent]["children"] = [c for c in index[parent].get("children", []) if c != title]
        _rewrite_node_from_index(parent, index)

    del index[title]
    _save_index(index)
    return True


def add_child(parent_title: str, child_title: str) -> bool:
    """Link an existing node as a child of another."""
    index = _load_index()
    if parent_title not in index or child_title not in index:
        return False
    _add_child_to_node(parent_title, child_title, index)
    return True


def create_nodes_batch(nodes: List[Dict[str, Any]], folder_path: Optional[Path] = None) -> List[str]:
    """Create multiple nodes at once."""
    created = []
    for node_data in nodes:
        title = node_data.get("title")
        content = node_data.get("content", "")
        node_type = node_data.get("type", "feature")
        parent = node_data.get("parent")
        tags = node_data.get("tags", [])
        keywords = node_data.get("keywords", [])
        summary = node_data.get("summary", "")

        if not title:
            continue

        try:
            create_node(title, content, node_type, parent,
                        tags=tags, keywords=keywords, summary=summary,
                        folder_path=folder_path or node_data.get("folder_path"))
            created.append(title)
        except Exception as e:
            print(f"  ✗ Failed to create {title}: {e}")

    return created


# ─── Project Scaffold ─────────────────────────────────────────────────────────

def create_project_scaffold(project_name: str, description: str = "") -> Dict[str, Any]:
    """
    Create the full hierarchical folder + node structure for a project.
    Returns dict with project info and list of created node titles.
    """
    project_dir = PROJECTS_DIR / _safe_filename(project_name)
    project_dir.mkdir(parents=True, exist_ok=True)

    created_titles = []

    # 1. Root project node
    root_content = f"""## Overview
{description or 'Project description pending.'}

## Sections
This project contains the following knowledge areas:
"""
    for sec in PREDEFINED_SECTIONS:
        section_title = f"{project_name} - {sec['label']}"
        root_content += f"- {sec['icon']} [[{section_title}]]\n"

    create_node(
        title=project_name,
        content=root_content,
        node_type="project",
        tags=["project", "root"],
        keywords=[project_name.lower().replace("_", " ")],
        summary=f"Root node for {project_name}",
        folder_path=project_dir,
        children=[f"{project_name} - {sec['label']}" for sec in PREDEFINED_SECTIONS],
    )
    created_titles.append(project_name)

    # 2. Create each predefined section folder + parent node
    for sec in PREDEFINED_SECTIONS:
        section_title = f"{project_name} - {sec['label']}"
        section_dir   = project_dir / sec["key"]
        section_dir.mkdir(parents=True, exist_ok=True)

        sub_children = []

        # If section has sub_sections (e.g. Technical_Stack), create them
        if "sub_sections" in sec:
            for sub in sec["sub_sections"]:
                sub_title = f"{project_name} - {sub['label']}"
                sub_dir = section_dir / sub["key"]
                sub_dir.mkdir(parents=True, exist_ok=True)

                create_node(
                    title=sub_title,
                    content=f"## {sub['label']}\n\n{sub['description']}\n\n*Awaiting details...*",
                    node_type="section",
                    parent=section_title,
                    tags=[sec["key"].lower(), sub["key"].lower()],
                    keywords=[sub["key"].lower(), sec["key"].lower()],
                    summary=sub["description"],
                    folder_path=sub_dir,
                )
                sub_children.append(sub_title)
                created_titles.append(sub_title)

        # Section parent node
        section_content = f"## {sec['icon']} {sec['label']}\n\n{sec['description']}\n\n"
        if sub_children:
            section_content += "### Sub-sections\n"
            for sc in sub_children:
                section_content += f"- [[{sc}]]\n"
        else:
            section_content += "*Awaiting content. Use `update` or paste your project description.*\n"

        create_node(
            title=section_title,
            content=section_content,
            node_type="section",
            parent=project_name,
            children=sub_children,
            tags=[sec["key"].lower()],
            keywords=[sec["key"].lower(), project_name.lower()],
            summary=sec["description"],
            folder_path=section_dir,
        )
        created_titles.append(section_title)

    return {
        "project":  project_name,
        "created":  created_titles,
        "dir":      str(project_dir),
        "sections": [s["label"] for s in PREDEFINED_SECTIONS],
    }


def list_projects() -> List[str]:
    """Return a list of all project names (root nodes)."""
    index = _load_index()
    return [t for t, m in index.items() if m.get("type") == "project"]


def clear_project(project_name: str) -> bool:
    """Delete an entire project: all nodes and folder tree."""
    index = _load_index()

    # Collect all node titles belonging to this project
    to_delete = []
    for title, meta in index.items():
        if title == project_name:
            to_delete.append(title)
        elif title.startswith(f"{project_name} - "):
            to_delete.append(title)
        elif meta.get("parent") and (
            meta["parent"] == project_name or
            meta["parent"].startswith(f"{project_name} - ")
        ):
            to_delete.append(title)

    # Delete node files
    for title in to_delete:
        entry = index.get(title)
        if entry:
            abs_path = VAULT_DIR / entry["path"]
            if abs_path.exists():
                try:
                    abs_path.unlink()
                except Exception:
                    pass

    # Remove from index
    for title in to_delete:
        index.pop(title, None)
    _save_index(index)

    # Remove project directory
    project_dir = PROJECTS_DIR / _safe_filename(project_name)
    if project_dir.exists():
        shutil.rmtree(project_dir, ignore_errors=True)

    return len(to_delete) > 0


def clear_all_nodes():
    """Wipe all nodes and clear the index. Hard reset."""
    if PROJECTS_DIR.exists():
        shutil.rmtree(PROJECTS_DIR, ignore_errors=True)
        PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    _save_index({})


# ─── Context Builder ──────────────────────────────────────────────────────────

def get_context(title: str, depth: int = 2) -> str:
    """Build a compact context string for AI prompting."""
    visited = set()
    parts   = []

    def _collect(t: str, level: int):
        if t in visited or level > depth:
            return
        visited.add(t)
        node = read_node(t)
        if not node:
            return
        indent = "  " * level
        parts.append(f"{indent}### {'📁 ' if level == 0 else '└─ '}{t}")
        parts.append(f"{indent}{node['content'][:600]}...")
        for child in node["meta"].get("children", []):
            _collect(child, level + 1)

    _collect(title, 0)
    return "\n".join(parts) if parts else f"No node found for '{title}'"


def get_full_tree(root: Optional[str] = None) -> str:
    """Return ASCII tree of all nodes or subtree from root."""
    index = _load_index()
    if not index:
        return "📭 No nodes yet. Use `summon <project>` to create your first project!"

    lines = []

    def _tree(title: str, prefix: str = "", is_last: bool = True):
        connector = "└─ " if is_last else "├─ "
        node_type = index.get(title, {}).get("type", "note")
        emoji = {
            "project": "📁", "section": "📂", "feature": "⚙️",
            "sub-node": "📄", "note": "📝",
        }.get(node_type, "📄")
        display = title.replace("_", " ")
        lines.append(f"{prefix}{connector}{emoji} {display}")
        children = index.get(title, {}).get("children", [])
        for i, child in enumerate(children):
            ext = "   " if is_last else "│  "
            _tree(child, prefix + ext, i == len(children) - 1)

    if root:
        _tree(root)
    else:
        roots = [t for t, m in index.items() if not m.get("parent")]
        for i, r in enumerate(roots):
            _tree(r, is_last=i == len(roots) - 1)

    return "\n".join(lines) or "No nodes."


def list_all_nodes() -> list[dict]:
    """Return list of all node metadata from index (fast, no file reads)."""
    index = _load_index()
    return [{"title": t, **m} for t, m in index.items()]


def search_nodes(query: str, limit: int = 5) -> list[str]:
    """Fuzzy search node titles."""
    index = _load_index()
    if not index:
        return []
    titles = list(index.keys())
    results = process.extract(query, titles, scorer=fuzz.WRatio, limit=limit)
    return [r[0] for r in results if r[1] > 40]


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _fuzzy_find(query: str, index: dict) -> Optional[str]:
    if not index:
        return None
    titles  = list(index.keys())
    results = process.extractOne(query, titles, scorer=fuzz.WRatio)
    if results and results[1] > 60:
        return results[0]
    return None


def _add_child_to_node(parent: str, child: str, index: dict):
    if child not in index[parent].get("children", []):
        index[parent].setdefault("children", []).append(child)
    index[child]["parent"] = parent
    _save_index(index)
    _rewrite_node_from_index(parent, index)
    _rewrite_node_from_index(child, index)


def _rewrite_node_from_index(title: str, index: dict):
    """Re-render a node's markdown based on current index metadata."""
    entry = index.get(title)
    if not entry:
        return
    abs_path = VAULT_DIR / entry["path"]
    if not abs_path.exists():
        return
    raw  = abs_path.read_text(encoding="utf-8")
    _, body = _parse_frontmatter(raw)
    body = re.sub(r"\n---\n## 🔗 Graph Links.*", "", body, flags=re.DOTALL).strip()
    abs_path.write_text(_build_markdown(title, body, entry), encoding="utf-8")


# ─── Quick test ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    result = create_project_scaffold("TestProject", "A test project for validation.")
    print(f"Created {len(result['created'])} nodes:")
    for t in result['created']:
        print(f"  - {t}")
    print("\n" + get_full_tree("TestProject"))