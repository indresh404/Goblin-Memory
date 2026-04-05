"""
write_file.py — Memory Goblin AI Brain Builder
Handles:
  - summon_project(): Full automated project creation with AI content
  - parse_master_prompt(): Parse structured or raw user input
  - populate_project(): AI categorizes raw text into correct nodes
  - reproduce_node(): Break large content into child sub-nodes
  - ai_update_node(): Smart node updates with keyword/summary regen
"""

import json
import time
import re
from typing import Dict, List, Optional, Any
from pathlib import Path

from ai_call import ai_json, ai, ai_fast
from obsidian import (
    create_node, get_full_tree, read_node, update_node, add_child,
    search_nodes, create_project_scaffold, PREDEFINED_SECTIONS, PROJECTS_DIR, _safe_filename,
    list_all_nodes,
)


# ─── Master Prompt Template ──────────────────────────────────────────────────

MASTER_PROMPT_TEMPLATE = """
╔══════════════════════════════════════════════════════════════╗
║  🧠 MEMORY GOBLIN — Master Prompt Template                  ║
║  Copy this template, fill it in, and paste it back!         ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  PROJECT NAME: <your project name>                           ║
║                                                              ║
║  PROBLEM:                                                    ║
║  <What problem does this solve? Who faces this problem?>     ║
║                                                              ║
║  FEATURES:                                                   ║
║  - Feature 1: <description>                                  ║
║  - Feature 2: <description>                                  ║
║  - Feature 3: <description>                                  ║
║                                                              ║
║  IDEA:                                                       ║
║  <High-level solution approach and architecture>             ║
║                                                              ║
║  IMPACT:                                                     ║
║  <Who benefits? Social/economic/technical impact>            ║
║                                                              ║
║  TECH STACK:                                                 ║
║    Frontend: <e.g. React, Next.js, Flutter>                  ║
║    Backend: <e.g. FastAPI, Node.js, Django>                  ║
║    AI/ML: <e.g. TensorFlow, LangChain, HuggingFace>         ║
║    Other: <e.g. Firebase, Redis, Docker>                     ║
║                                                              ║
║  BENEFITS:                                                   ║
║  <Key advantages and value propositions>                     ║
║                                                              ║
║  EXPECTED OUTCOMES:                                          ║
║  <Measurable goals, KPIs, success metrics>                   ║
║                                                              ║
║  RISKS:                                                      ║
║  <Potential challenges and mitigation strategies>            ║
║                                                              ║
║  MILESTONES:                                                 ║
║  <Timeline, phases, deliverables>                            ║
║                                                              ║
║  DEPENDENCIES:                                               ║
║  <External APIs, services, teams needed>                     ║
║                                                              ║
╠══════════════════════════════════════════════════════════════╣
║  💡 OR just paste your raw idea — I'll figure it out! 🧠    ║
╚══════════════════════════════════════════════════════════════╝
"""


# ─── Prompt Parser ────────────────────────────────────────────────────────────

# Maps template section headers → our section keys
SECTION_ALIASES = {
    "problem":           "Problem_Statements",
    "problem statement": "Problem_Statements",
    "problems":          "Problem_Statements",
    "feature":           "Features",
    "features":          "Features",
    "idea":              "Ideas",
    "ideas":             "Ideas",
    "impact":            "Impact",
    "tech stack":        "Technical_Stack",
    "technology":        "Technical_Stack",
    "technologies":      "Technical_Stack",
    "frontend":          "Technical_Stack/Frontend",
    "backend":           "Technical_Stack/Backend",
    "ai/ml":             "Technical_Stack/AI_ML",
    "ai":                "Technical_Stack/AI_ML",
    "ml":                "Technical_Stack/AI_ML",
    "other":             "Technical_Stack/Other",
    "benefit":           "Benefits",
    "benefits":          "Benefits",
    "expected outcome":  "Expected_Outcomes",
    "expected outcomes": "Expected_Outcomes",
    "outcomes":          "Expected_Outcomes",
    "risk":              "Risks",
    "risks":             "Risks",
    "milestone":         "Milestones",
    "milestones":        "Milestones",
    "timeline":          "Milestones",
    "dependency":        "Dependencies",
    "dependencies":      "Dependencies",
}


def parse_master_prompt(raw_text: str) -> Dict[str, str]:
    """
    Parse structured (template) or raw user input into section buckets.
    Returns dict mapping section_key -> content.
    """
    sections = {}
    current_section = None
    current_lines = []

    for line in raw_text.splitlines():
        stripped = line.strip()
        if not stripped:
            if current_section:
                current_lines.append("")
            continue

        # Check if this line is a section header
        header_match = re.match(r"^([A-Z][A-Z /]+)\s*:", stripped, re.IGNORECASE)
        if header_match:
            # Save previous section
            if current_section:
                sections[current_section] = "\n".join(current_lines).strip()
                current_lines = []

            header = header_match.group(1).strip().lower()
            rest = stripped[header_match.end():].strip()

            # Map header to section key
            section_key = SECTION_ALIASES.get(header)
            if section_key:
                current_section = section_key
                if rest:
                    current_lines.append(rest)
            elif header == "project name":
                sections["_project_name"] = rest
                current_section = None
            else:
                # Unknown header — dump into closest match
                current_section = None
                for alias, key in SECTION_ALIASES.items():
                    if alias in header:
                        current_section = key
                        if rest:
                            current_lines.append(rest)
                        break
        else:
            if current_section:
                current_lines.append(stripped)

    # Save last section
    if current_section and current_lines:
        sections[current_section] = "\n".join(current_lines).strip()

    return sections


# ─── AI Auto-Categorizer ─────────────────────────────────────────────────────

def ai_categorize_raw_text(project_name: str, raw_text: str) -> Dict[str, str]:
    """
    Use AI to auto-categorize raw text into the predefined sections.
    Returns dict mapping section_key -> generated content.
    """
    section_list = "\n".join([
        f"- {s['key']}: {s['description']}"
        for s in PREDEFINED_SECTIONS
    ])

    prompt = f"""You are structuring a project called "{project_name}".

Here is the raw project description:
---
{raw_text[:3000]}
---

Categorize this content into the following sections. Extract ALL relevant information.
If a section has no content, write "No specific details provided yet."

Sections:
{section_list}

Also split Technical_Stack into sub-sections:
- Frontend: UI frameworks, libraries
- Backend: Server frameworks, APIs, databases
- AI_ML: Machine learning, AI models
- Other: DevOps, CI/CD, misc tools

Return a JSON object with keys matching section keys exactly:
{{
  "Problem_Statements": "extracted problem content...",
  "Features": "extracted features content...",
  "Ideas": "extracted ideas content...",
  "Impact": "extracted impact content...",
  "Technical_Stack": "overview of entire tech stack...",
  "Frontend": "frontend technologies...",
  "Backend": "backend technologies...",
  "AI_ML": "AI/ML technologies...",
  "Other": "other tools...",
  "Benefits": "extracted benefits...",
  "Expected_Outcomes": "extracted outcomes...",
  "Risks": "extracted risks...",
  "Milestones": "extracted milestones...",
  "Dependencies": "extracted dependencies..."
}}

Be thorough. Extract every piece of information from the raw text."""

    result = ai_json(prompt, retries=3)

    if result and isinstance(result, dict):
        return result
    return {}


# ─── Summon Project ──────────────────────────────────────────────────────────

def summon_project(project_name: str, description: str) -> Dict[str, Any]:
    """
    Full automated project creation:
    1. Create hierarchical folder scaffold
    2. Parse or AI-categorize the description
    3. Populate all section nodes with real content
    4. Generate summaries and keywords for each node
    """
    created_nodes = []

    print(f"\n🧙 Memory Goblin is summoning '{project_name}'...")
    print("=" * 55)

    # Step 1: Create folder scaffold with empty nodes
    print("📁 Creating project scaffold...")
    scaffold = create_project_scaffold(project_name, description)
    created_nodes.extend(scaffold["created"])
    print(f"  ✓ Created {len(scaffold['created'])} scaffold nodes")

    if not description or len(description.strip()) < 20:
        print("\n💡 Scaffold created! Paste your project description to populate nodes.")
        return {
            "project": project_name,
            "created": created_nodes,
            "summary": f"Scaffold with {len(created_nodes)} empty nodes created.",
            "tree": get_full_tree(project_name),
        }

    # Step 2: Try structured parse first, then AI categorize
    print("\n🔍 Analyzing your project description...")
    parsed = parse_master_prompt(description)

    # If structured parse found very little, use AI categorization
    if len(parsed) < 3:
        print("  🤖 Using AI to auto-categorize your description...")
        parsed = ai_categorize_raw_text(project_name, description)
        time.sleep(1)

    # Step 3: Populate section nodes with categorized content
    if parsed:
        print(f"\n📝 Populating {len(parsed)} sections with content...")

        for section_key, content in parsed.items():
            if section_key.startswith("_"):
                continue
            if not content or content.strip() in ["", "No specific details provided yet."]:
                continue

            # Map to the correct node title
            if "/" in section_key:
                # Sub-section like Technical_Stack/Frontend
                parts = section_key.split("/")
                parent_key = parts[0]
                sub_key = parts[1]
                # Find the matching predefined section
                for sec in PREDEFINED_SECTIONS:
                    if sec["key"] == parent_key and "sub_sections" in sec:
                        for sub in sec["sub_sections"]:
                            if sub["key"] == sub_key:
                                node_title = f"{project_name} - {sub['label']}"
                                _populate_section_node(node_title, content, project_name)
                                break
            else:
                # Direct section match
                # Handle Frontend/Backend/AI_ML/Other as tech stack sub-sections
                if section_key in ["Frontend", "Backend", "AI_ML", "Other"]:
                    label_map = {"Frontend": "Frontend", "Backend": "Backend",
                                 "AI_ML": "AI/ML", "Other": "Other"}
                    node_title = f"{project_name} - {label_map.get(section_key, section_key)}"
                    _populate_section_node(node_title, content, project_name)
                else:
                    for sec in PREDEFINED_SECTIONS:
                        if sec["key"] == section_key:
                            node_title = f"{project_name} - {sec['label']}"
                            _populate_section_node(node_title, content, project_name)
                            break

    # Step 4: Generate summaries and keywords for all nodes
    print("\n🧠 Generating summaries and keywords...")
    _generate_metadata_for_project(project_name)

    print("\n" + "=" * 55)
    print(f"✅ Memory Goblin has summoned '{project_name}' successfully!")

    return {
        "project": project_name,
        "created": created_nodes,
        "summary": f"Created {len(created_nodes)} nodes with AI-generated content.",
        "tree": get_full_tree(project_name),
    }


def _populate_section_node(node_title: str, content: str, project_name: str):
    """Update a section node with categorized content."""
    try:
        success = update_node(node_title, content)
        if success:
            print(f"  ✓ Populated: {node_title}")
        else:
            print(f"  ⚠ Could not find node: {node_title}")
    except Exception as e:
        print(f"  ✗ Error populating {node_title}: {e}")


def _generate_metadata_for_project(project_name: str):
    """Use AI to generate summaries and keywords for all project nodes."""
    all_nodes = list_all_nodes()
    project_nodes = [n for n in all_nodes if
                     n["title"] == project_name or
                     n["title"].startswith(f"{project_name} - ")]

    for node_meta in project_nodes:
        title = node_meta["title"]
        node = read_node(title)
        if not node:
            continue

        content = node["content"]
        if len(content.strip()) < 30:
            continue

        # Generate summary + keywords using fast AI
        try:
            prompt = f"""Analyze this node content and return a JSON object:
{{
  "summary": "One sentence summary of this node",
  "keywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"]
}}

Node: {title}
Content: {content[:500]}

Return ONLY the JSON object, nothing else."""

            result = ai_json(prompt, retries=1)
            if result and isinstance(result, dict):
                summary = result.get("summary", "")
                keywords = result.get("keywords", [])
                if summary or keywords:
                    update_node(title, content,
                                new_keywords=keywords,
                                new_summary=summary)
                    print(f"  ✓ Metadata: {title}")
            time.sleep(0.5)
        except Exception as e:
            print(f"  ⚠ Metadata failed for {title}: {e}")


# ─── Reproduce Node ──────────────────────────────────────────────────────────

def reproduce_node(node_title: str, extra_instruction: str = "") -> Dict[str, Any]:
    """
    Break a large node's content into detailed child sub-nodes.
    Each sub-item gets its own node with full detail.
    """
    node = read_node(node_title)
    if not node:
        return {"error": f"Node '{node_title}' not found"}

    content = node["content"]
    parent_meta = node["meta"]

    # Determine the project folder for new sub-nodes
    node_path = Path(str(node["path"]))
    node_dir = node_path.parent

    prompt = f"""Analyze the content of '{node_title}' and break it into 3-6 detailed child sub-nodes.

Current content:
---
{content[:1500]}
---

{extra_instruction}

For each child sub-node, provide:
- A specific, actionable title
- Detailed content (2-3 paragraphs with bullet points)
- Relevant keywords

Return a JSON array:
[
  {{
    "title": "Descriptive Sub-Node Title",
    "content": "Detailed markdown content...",
    "keywords": ["kw1", "kw2", "kw3"],
    "summary": "One-line summary"
  }}
]

Make each child specific, detailed, and self-contained. Don't be generic."""

    result = ai_json(prompt, retries=3)

    created = []
    if result and isinstance(result, list):
        for child_data in result:
            if not isinstance(child_data, dict) or "title" not in child_data:
                continue

            raw_title = child_data["title"]
            # Prefix with parent for unique naming
            child_title = f"{node_title} - {raw_title}"
            child_content = child_data.get("content", "No description.")
            keywords = child_data.get("keywords", [])
            summary = child_data.get("summary", "")

            try:
                create_node(
                    title=child_title,
                    content=child_content,
                    node_type="sub-node",
                    parent=node_title,
                    tags=["auto-generated", "reproduced"],
                    keywords=keywords,
                    summary=summary,
                    folder_path=node_dir,
                )
                created.append(child_title)
                print(f"  ✓ Reproduced: {child_title}")
            except Exception as e:
                print(f"  ✗ Failed: {child_title}: {e}")

            time.sleep(0.5)

    # Update parent node with summary of children
    if created:
        parent_summary = f"\n\n## Sub-Nodes\nThis node has been broken down into:\n"
        for c in created:
            parent_summary += f"- [[{c}]]\n"
        update_node(node_title, content + parent_summary)

    return {
        "expanded": node_title,
        "created": created,
        "tree": get_full_tree(node_title),
    }


# ─── AI Update Node ──────────────────────────────────────────────────────────

def ai_update_node(title: str, instruction: str) -> bool:
    """Update a node using AI, regenerate keywords and summary."""
    node = read_node(title)
    if not node:
        return False

    prompt = f"""Current content of '{title}':
---
{node['content']}
---

Instruction: {instruction}

Provide the updated content only (markdown formatted, no code blocks wrapping it):"""

    new_content = ai(prompt, temperature=0.3)
    if not new_content:
        return False

    # Generate new metadata
    meta_prompt = f"""For this updated node content, return a JSON object:
{{
  "summary": "One sentence summary",
  "keywords": ["kw1", "kw2", "kw3", "kw4", "kw5"]
}}

Node: {title}
Content: {new_content[:500]}

Return ONLY JSON:"""

    meta_result = ai_json(meta_prompt, retries=1)
    new_keywords = None
    new_summary = None
    if meta_result and isinstance(meta_result, dict):
        new_keywords = meta_result.get("keywords")
        new_summary = meta_result.get("summary")

    return update_node(title, new_content,
                       new_keywords=new_keywords,
                       new_summary=new_summary)


# ─── Create Child Node ────────────────────────────────────────────────────────

def create_child_node(parent_title: str, child_title: str, description: str) -> Optional[str]:
    """Create a child node under an existing parent."""
    parent = read_node(parent_title)
    if not parent:
        return None

    prompt = f"""Create detailed content for '{child_title}', a sub-component of '{parent_title}'.

Description: {description}

Return ONLY the content (markdown formatted, 2-3 paragraphs)."""

    content = ai(prompt, temperature=0.3)
    if not content:
        return None

    # Determine folder from parent
    parent_path = Path(str(parent["path"]))
    folder = parent_path.parent

    create_node(
        title=child_title,
        content=content,
        node_type="sub-node",
        parent=parent_title,
        tags=["auto-generated"],
        folder_path=folder,
    )
    return child_title


# ─── Expand Node (alias for reproduce) ───────────────────────────────────────

def expand_node(node_title: str, extra_instruction: str = "") -> Dict[str, Any]:
    """Expand a node into detailed child nodes. Alias for reproduce_node."""
    return reproduce_node(node_title, extra_instruction)


# ─── Populate Project from Description ────────────────────────────────────────

def populate_project(project_name: str, raw_description: str) -> Dict[str, Any]:
    """
    Take a raw project description and populate an existing project's nodes.
    Useful when user runs summon first, then pastes description later.
    """
    # Check project exists
    node = read_node(project_name)
    if not node:
        return {"error": f"Project '{project_name}' not found. Run `summon {project_name}` first."}

    # Try structured parse
    parsed = parse_master_prompt(raw_description)

    # Fallback to AI categorization
    if len(parsed) < 3:
        print("  🤖 AI is categorizing your description...")
        parsed = ai_categorize_raw_text(project_name, raw_description)

    if not parsed:
        return {"error": "Could not parse or categorize the description."}

    populated = []
    for section_key, content in parsed.items():
        if section_key.startswith("_") or not content.strip():
            continue

        if section_key in ["Frontend", "Backend", "AI_ML", "Other"]:
            label_map = {"Frontend": "Frontend", "Backend": "Backend",
                         "AI_ML": "AI/ML", "Other": "Other"}
            node_title = f"{project_name} - {label_map.get(section_key, section_key)}"
        else:
            for sec in PREDEFINED_SECTIONS:
                if sec["key"] == section_key:
                    node_title = f"{project_name} - {sec['label']}"
                    break
            else:
                continue

        success = update_node(node_title, content)
        if success:
            populated.append(node_title)
            print(f"  ✓ Populated: {node_title}")

    # Regenerate metadata
    _generate_metadata_for_project(project_name)

    return {
        "project": project_name,
        "populated": populated,
        "tree": get_full_tree(project_name),
    }