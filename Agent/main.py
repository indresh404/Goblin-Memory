"""
main.py — Goblin's Memory 🧙
A quirky but powerful AI agent for managing project knowledge in Obsidian.
"""

import sys
import re
import os
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

try:
    from rich.console  import Console
    from rich.panel    import Panel
    from rich.table    import Table
    from rich.markdown import Markdown
    RICH = True
except ImportError:
    RICH = False

from ai_call   import ai, ai_fast, is_ollama_running
from obsidian  import (
    read_node, get_full_tree, list_all_nodes,
    search_nodes, _load_index, create_nodes_batch,
    list_projects, clear_project, clear_all_nodes,
)
from read_file  import smart_context_for_query, append_chat_history, load_chat_history
from write_file import (
    summon_project, ai_update_node, create_child_node,
    reproduce_node, expand_node, populate_project,
    MASTER_PROMPT_TEMPLATE,
)
from vector_memory import get_vector_memory, reindex_all, smart_search
from cache_manager import get_cached_response, cache_response, clear_cache, ResponseCache

console = Console() if RICH else None
response_cache = ResponseCache()


# ─── Performance Tracker ───────────────────────────────────────────────────────

class PerformanceTracker:
    """Track execution times for all operations"""
    def __init__(self):
        self.stats = {
            "total_ops": 0,
            "total_time_ms": 0,
            "fastest_ms": float('inf'),
            "slowest_ms": 0,
            "op_times": {}
        }
        self.start_time = time.time()
    
    def track(self, op_name: str):
        """Decorator to track function execution time"""
        def decorator(func):
            def wrapper(*args, **kwargs):
                start = time.perf_counter()
                result = func(*args, **kwargs)
                elapsed_ms = (time.perf_counter() - start) * 1000
                
                self.stats["total_ops"] += 1
                self.stats["total_time_ms"] += elapsed_ms
                self.stats["fastest_ms"] = min(self.stats["fastest_ms"], elapsed_ms)
                self.stats["slowest_ms"] = max(self.stats["slowest_ms"], elapsed_ms)
                
                if op_name not in self.stats["op_times"]:
                    self.stats["op_times"][op_name] = []
                self.stats["op_times"][op_name].append(elapsed_ms)
                
                # Display timing
                if elapsed_ms < 1:
                    print_info(f"⏱️  {op_name}: {elapsed_ms:.3f}ms ✨ (Lightning!)")
                elif elapsed_ms < 100:
                    print_info(f"⏱️  {op_name}: {elapsed_ms:.2f}ms")
                else:
                    print_info(f"⏱️  {op_name}: {elapsed_ms/1000:.2f}s")
                
                return result
            return wrapper
        return decorator
    
    def show_stats(self):
        """Display performance statistics"""
        avg = self.stats["total_time_ms"] / self.stats["total_ops"] if self.stats["total_ops"] > 0 else 0
        uptime = time.time() - self.start_time
        
        if RICH:
            # Main stats table
            table = Table(title="📊 Performance Statistics", title_style="bold green")
            table.add_column("Metric", style="bold cyan")
            table.add_column("Value", style="green")
            table.add_row("Session Uptime", f"{uptime:.1f} seconds")
            table.add_row("Total Operations", str(self.stats["total_ops"]))
            table.add_row("Total Time", f"{self.stats['total_time_ms']:.2f}ms ({self.stats['total_time_ms']/1000:.2f}s)")
            table.add_row("Average Time", f"{avg:.2f}ms")
            table.add_row("Fastest", f"{self.stats['fastest_ms']:.3f}ms")
            table.add_row("Slowest", f"{self.stats['slowest_ms']:.2f}ms")
            
            # Speed rating
            if self.stats['fastest_ms'] < 1:
                rating = "🏆 EXCELLENT (<1ms)"
                rating_color = "bold green"
            elif self.stats['fastest_ms'] < 10:
                rating = "👍 GOOD (<10ms)"
                rating_color = "green"
            else:
                rating = "⚠️ OPTIMIZE (>10ms)"
                rating_color = "yellow"
            
            table.add_row("Speed Rating", f"[{rating_color}]{rating}[/{rating_color}]")
            console.print(table)
            
            # Per-operation breakdown
            if self.stats["op_times"]:
                op_table = Table(title="⏱️ Per-Operation Breakdown", title_style="bold cyan")
                op_table.add_column("Operation", style="bold magenta")
                op_table.add_column("Count", style="green", justify="right")
                op_table.add_column("Avg (ms)", style="yellow", justify="right")
                op_table.add_column("Min (ms)", style="green", justify="right")
                op_table.add_column("Max (ms)", style="red", justify="right")
                
                for op, times in sorted(self.stats["op_times"].items()):
                    op_table.add_row(
                        op,
                        str(len(times)),
                        f"{sum(times)/len(times):.2f}",
                        f"{min(times):.3f}",
                        f"{max(times):.2f}"
                    )
                console.print(op_table)
            
            # Fastest operations highlight
            fastest_ops = sorted([(op, min(times)) for op, times in self.stats["op_times"].items()], key=lambda x: x[1])[:3]
            if fastest_ops:
                highlight = Table(title="⚡ Fastest Operations", title_style="bold green")
                highlight.add_column("Operation", style="cyan")
                highlight.add_column("Time (ms)", style="green", justify="right")
                for op, t in fastest_ops:
                    highlight.add_row(op, f"{t:.3f}")
                console.print(highlight)
        else:
            print(f"\n📊 Performance Stats:")
            print(f"   Session Uptime: {uptime:.1f}s")
            print(f"   Total Ops: {self.stats['total_ops']}")
            print(f"   Total Time: {self.stats['total_time_ms']:.2f}ms")
            print(f"   Average: {avg:.2f}ms")
            print(f"   Fastest: {self.stats['fastest_ms']:.3f}ms")
            print(f"   Slowest: {self.stats['slowest_ms']:.2f}ms")
    
    def reset(self):
        """Reset performance stats"""
        self.stats = {
            "total_ops": 0,
            "total_time_ms": 0,
            "fastest_ms": float('inf'),
            "slowest_ms": 0,
            "op_times": {}
        }
        self.start_time = time.time()
        print_success("Performance stats reset!")

# Initialize tracker
perf_tracker = PerformanceTracker()


# ─── Goblin Personality ───────────────────────────────────────────────────────

GOBLIN_FACES = {
    "happy":   "🧙",
    "think":   "🧙‍♂️",
    "angry":   "👺",
    "love":    "💚",
    "sleep":   "😴",
    "magic":   "✨",
}

GREETINGS = {"hi", "hello", "hey", "hii", "helo", "sup", "yo", "howdy"}

GREETING_REPLY = """🧙 **Greetings, mortal!** I am **Goblin's Memory** — keeper of your project knowledge!

✨ **Summon Commands** (project creation):
- **`summon <project>`** → Create a full project with all sections
- **`memory_loss <project>`** → Obliterate a project from memory
- **`populate <project>`** → Feed me your project description

🔍 **Query Commands** (instant answers):
- **`fast <question>`** → ⚡ Lightning fast answers (<2s)
- **`ask <question>`** → 🧠 Detailed answers with full context

📚 **Knowledge Commands**:
- **`show <node>`** → Read a node's content
- **`show_me_your_brain`** → See my entire knowledge tree
- **`reproduce <node>`** → Break a node into detailed sub-nodes
- **`update <instruction>`** → Modify a node with AI
- **`add <Child> to <Parent>`** → Create child node
- **`search <query>`** → Semantic vector search

📊 **Performance Commands**:
- **`stats`** → Show performance timing metrics
- **`perf`** → Alias for stats
- **`reset-stats`** → Reset performance counters

💡 **Tips**:
- After `summon`, paste your project idea (structured or raw)!
- Use `fast` for quick Q&A, `ask` for deep analysis
- Type `help` for all commands

*Now tell me... what knowledge shall we hoard today?* 🧙"""


# ─── Display Helpers ──────────────────────────────────────────────────────────

def print_header():
    if RICH:
        console.print(Panel.fit(
            "[bold green]🧙 Goblin's Memory[/bold green]  [dim]Obsidian Knowledge Hoarder[/dim]\n"
            "[dim]✨ Type [bold white]summon <project>[/bold white] to begin | "
            "[bold white]help[/bold white] for commands | "
            "[bold white]stats[/bold white] for performance[/dim]",
            border_style="green"
        ))
    else:
        print("=" * 65)
        print("  🧙 Goblin's Memory — Obsidian Knowledge Hoarder")
        print("  Type 'help' for commands, 'stats' for performance")
        print("=" * 65)


def print_goblin(text: str, label: str = "Goblin's Memory", fast: bool = False):
    if fast:
        label = f"⚡ {label}" if "⚡" not in label else label
    if RICH:
        console.print(Panel(Markdown(text), title=f"[bold green]{label}[/bold green]",
                            border_style="green", padding=(1, 2)))
    else:
        print(f"\n[{label}]\n{text}\n")


def print_info(text: str):
    if RICH:
        console.print(f"[dim green]  🧙 {text}[/dim green]")
    else:
        print(f"  🧙 {text}")


def print_success(text: str):
    if RICH:
        console.print(f"[bold green]  ✅ {text}[/bold green]")
    else:
        print(f"  ✅ {text}")


def print_error(text: str):
    if RICH:
        console.print(f"[bold red]  👺 {text}[/bold red]")
    else:
        print(f"  👺 {text}")


def get_input() -> str:
    if RICH:
        return console.input("\n[bold green]You ›[/bold green] ").strip()
    else:
        return input("\nYou › ").strip()


def get_multiline_input(prompt_text: str = "Paste your content (type END on a new line to finish):") -> str:
    """Read multiple lines of input until user types END."""
    print_info(prompt_text)
    lines = []
    while True:
        try:
            line = input()
            if line.strip().upper() == "END":
                break
            lines.append(line)
        except EOFError:
            break
    return "\n".join(lines)


def spinner(label: str):
    if RICH:
        return console.status(f"[bold green]{label}[/bold green]", spinner="dots")
    else:
        import contextlib
        @contextlib.contextmanager
        def _dummy():
            print(f"  ⏳ {label}")
            yield
        return _dummy()


# ─── Command Handlers ─────────────────────────────────────────────────────────

@perf_tracker.track("summon")
def cmd_summon(args: str):
    """Create a new project with full scaffold and AI content."""
    project_name = args.strip().replace(" ", "_") if args.strip() else ""

    if not project_name:
        print_info("What shall I name this project?")
        project_name = get_input().strip().replace(" ", "_")
        if not project_name:
            print_error("No name given. Goblin goes back to sleep. 😴")
            return

    # Check if project already exists
    existing = list_projects()
    if project_name in existing:
        print_error(f"Project '{project_name}' already exists! Use `memory_loss {project_name}` first.")
        return

    print_goblin(MASTER_PROMPT_TEMPLATE, label="📋 Master Prompt")
    print_info("Paste your project description below (or press Enter for empty scaffold).")
    print_info("For multi-line input, type END on a new line when done.")

    description = get_multiline_input("Paste your project idea (raw or structured). Type END when done:")

    with spinner("🧙 Goblin's Memory is summoning your project..."):
        result = summon_project(project_name, description)

    print_success(f"Summoned '{result['project']}' with {len(result['created'])} nodes!")

    if RICH:
        console.print(Panel(result["tree"], title="[bold]🧠 Project Brain[/bold]", border_style="green"))
    else:
        print("\n" + result["tree"])

    append_chat_history("system", f"Summoned project '{result['project']}' with {len(result['created'])} nodes.")

    # Auto-index for vector search
    print_info("Indexing nodes for fast search...")
    with spinner("Building search index..."):
        reindex_all()
    print_success("Search index ready! ⚡")


@perf_tracker.track("memory_loss")
def cmd_memory_loss(args: str):
    """Delete a project or all memory."""
    target = args.strip()

    if not target:
        print_error("🧙 Choose your destruction wisely:")
        projects = list_projects()
        if projects:
            for p in projects:
                print_info(f"  📁 {p}")
            print_info("Or type 'ALL' to wipe everything.")
        else:
            print_info("No projects found. Memory is already clean!")
            return
        target = get_input()
        if not target:
            print_info("Deletion cancelled. Phew! 😅")
            return

    if target.upper() == "ALL":
        print_error("⚠️ WARNING: This will DELETE ALL nodes, ALL projects, ALL memory!")
        print_info("Type 'YES' to confirm total obliteration:")
        ans = get_input()
        if ans == "YES":
            with spinner("💀 Nuking all memory..."):
                clear_all_nodes()
                vm = get_vector_memory()
                if vm:
                    vm.clear_all()
                clear_cache()
                perf_tracker.reset()
            print_success("All memory obliterated. Goblin has amnesia now. 🧙💫")
        else:
            print_info("Cancelled. Your memories live to see another day.")
    else:
        print_error(f"⚠️ This will delete ALL nodes in project '{target}'.")
        print_info("Type 'YES' to confirm:")
        ans = get_input()
        if ans == "YES":
            with spinner(f"💀 Destroying '{target}'..."):
                cleared = clear_project(target)
                vm = get_vector_memory()
                if vm:
                    vm.clear_all()
                    reindex_all()
                clear_cache()
            if cleared:
                print_success(f"Project '{target}' has been erased from memory! 🧙💨")
            else:
                print_error(f"Could not find project '{target}'.")
        else:
            print_info("Cancelled.")


@perf_tracker.track("populate")
def cmd_populate(args: str):
    """Feed a project description to populate an existing project."""
    project_name = args.strip()
    if not project_name:
        projects = list_projects()
        if projects:
            print_info("Which project to populate?")
            for p in projects:
                print_info(f"  📁 {p}")
            project_name = get_input()
        else:
            print_error("No projects found. Use `summon` first!")
            return

    if not project_name:
        return

    print_info("Paste your project description (type END when done):")
    description = get_multiline_input()

    if not description.strip():
        print_error("No description provided.")
        return

    with spinner("🧙 Goblin is digesting your description..."):
        result = populate_project(project_name, description)

    if "error" in result:
        print_error(result["error"])
    else:
        print_success(f"Populated {len(result.get('populated', []))} sections!")
        if RICH:
            console.print(Panel(result["tree"], title="[bold]🧠 Updated Brain[/bold]", border_style="green"))

    # Re-index
    with spinner("Rebuilding search index..."):
        reindex_all()


@perf_tracker.track("fast_query")
def cmd_fast(query: str):
    """Lightning fast responses using cache and keyword index."""
    if not query:
        print_error("Please provide a question.")
        print_info("Example: fast What are the main features?")
        return

    # Tier 1: Check keyword index first
    from instant_index import instant_keyword_search
    instant_hits = instant_keyword_search(query)
    if instant_hits:
        best = next((h for h in instant_hits if h.get("summary")), None)
        if best:
            ans = f"**{best['title']}**: {best['summary']}"
            if len(instant_hits) > 1:
                ans += f"\n\n*Also related: {', '.join(h['title'] for h in instant_hits[1:4])}*"
            print_goblin(ans, label="⚡ Instant Index", fast=True)
            return

    with spinner("⚡ Thinking fast..."):
        relevant = smart_search(query, top_k=2)

        if not relevant:
            print_error("No relevant information found in my memory.")
            return

        context = "\n".join([
            f"- {r['title']}: {r['content'][:200]}"
            for r in relevant
        ])

        cached = get_cached_response(query, context)
        if cached:
            print_goblin(f"⚡ {cached}", label="⚡ Cached Answer", fast=True)
            append_chat_history("assistant", f"[cached] {cached}")
            return

        prompt = f"""Context from project memory:
{context}

Question: {query}

Answer briefly and directly (2-3 sentences max):"""

        try:
            answer = ai_fast(prompt, temperature=0.2)
            cache_response(query, context, answer)
            print_goblin(answer, label="⚡ Fast Answer", fast=True)
            append_chat_history("assistant", answer)
        except Exception as e:
            print_error(f"Error: {e}")
            print_info("Falling back to full mode...")
            cmd_ask(query)


@perf_tracker.track("ask_query")
def cmd_ask(query: str):
    """Detailed response with full context."""
    if not query:
        print_error("Please provide a question.")
        return

    with spinner("🧠 Reading all my memories..."):
        context = smart_context_for_query(query, max_nodes=3)
        history = load_chat_history(max_lines=15)

        system = """You are Goblin's Memory, a knowledgeable AI assistant with access to a project memory graph.
Answer questions using ONLY the provided context nodes.
Be specific, reference node names when relevant.
If context doesn't cover the question, say so clearly.
Maintain a slightly quirky but professional personality."""

        prompt = f"""## Project Memory Context
{context}

## Recent Chat History
{history}

## Question
{query}"""

        answer = ai(prompt, system=system, temperature=0.3)

    print_goblin(answer, label="🧠 Goblin's Memory")
    append_chat_history("user", query)
    append_chat_history("assistant", answer)


@perf_tracker.track("show_node")
def cmd_show(node_title: str):
    """Display a single node's content."""
    if not node_title:
        print_error("Provide a node title. Example: show MyProject - Features")
        return

    with spinner(f"📄 Loading '{node_title}'..."):
        node = read_node(node_title)

    if not node:
        matches = search_nodes(node_title)
        if matches:
            print_info(f"Not found. Did you mean: {', '.join(matches[:5])}?")
        else:
            print_error(f"Node '{node_title}' not found.")
        return

    meta = node["meta"]
    children_list = meta.get("children", [])
    info = (
        f"**Type:** {meta.get('type', '?')}  "
        f"**Parent:** {meta.get('parent') or 'None'}  \n"
        f"**Children:** {', '.join(children_list[:10]) or 'None'}\n"
        f"**Keywords:** {', '.join(meta.get('keywords', [])) or 'None'}\n"
        f"**Summary:** {meta.get('summary', 'N/A')}\n"
        f"**Updated:** {meta.get('updated', '?')}\n\n---\n\n"
        + node["content"]
    )
    print_goblin(info, label=f"📄 {node_title}")


@perf_tracker.track("show_brain")
def cmd_show_me_your_brain(args: str):
    """Display the full knowledge tree."""
    root = args.strip() or None
    with spinner("🧠 Unfolding my brain..."):
        tree = get_full_tree(root)

    if RICH:
        # Also show a summary table
        nodes = list_all_nodes()
        projects = [n for n in nodes if n.get("type") == "project"]
        sections = [n for n in nodes if n.get("type") == "section"]
        subnodes = [n for n in nodes if n.get("type") in ("sub-node", "feature", "note")]

        summary = (
            f"📁 **Projects:** {len(projects)}  |  "
            f"📂 **Sections:** {len(sections)}  |  "
            f"📄 **Sub-nodes:** {len(subnodes)}  |  "
            f"**Total:** {len(nodes)}\n\n"
        )
        console.print(Panel(
            summary + tree,
            title="[bold green]🧠 Goblin's Memory's Brain[/bold green]",
            border_style="green"
        ))
    else:
        print("\n" + tree + "\n")


@perf_tracker.track("reproduce")
def cmd_reproduce(args: str):
    """Break a node into detailed child sub-nodes."""
    node_title = args.strip()

    if not node_title:
        print_info("Which node should I reproduce into sub-nodes?")
        node_title = get_input()
        if not node_title:
            print_error("No node specified.")
            return

    print_info("Any extra instructions? (press Enter to skip)")
    extra = get_input()

    with spinner(f"🧬 Reproducing '{node_title}' into sub-nodes..."):
        result = reproduce_node(node_title, extra_instruction=extra)

    if "error" in result:
        matches = search_nodes(node_title)
        if matches:
            print_error(f"Node not found. Did you mean: {', '.join(matches[:5])}?")
        else:
            print_error(result["error"])
        return

    print_success(f"Created {len(result['created'])} child nodes under '{result['expanded']}'")

    # Update vector index
    if result['created']:
        vm = get_vector_memory()
        if vm:
            for child in result['created']:
                node = read_node(child)
                if node:
                    vm.index_node(child, node["content"])

    if RICH:
        console.print(Panel(result["tree"], title="[bold]🧬 Reproduced Tree[/bold]", border_style="green"))
    else:
        print("\n" + result["tree"])


@perf_tracker.track("update")
def cmd_update(args: str):
    """Update a node with AI."""
    instruction = args.strip()
    if not instruction:
        print_error("Usage: update <instruction> (e.g. update the frontend to use React)")
        return

    vm = get_vector_memory()
    if not vm:
        print_error("Vector memory not available.")
        return

    print_info(f"🔍 Searching for relevant node...")
    results = vm.search(instruction, top_k=1)
    if not results or results[0]['similarity'] < 0.2:
        print_error("No relevant node found. Be more specific.")
        return

    node_title = results[0]['title']
    print_info(f"🎯 Target: {node_title} (Score: {results[0]['similarity']:.3f})")

    with spinner(f"✏️ Updating '{node_title}'..."):
        success = ai_update_node(node_title, instruction)

    if success:
        print_success(f"'{node_title}' updated!")
        if vm:
            node = read_node(node_title)
            if node:
                vm.index_node(node_title, node["content"])
        clear_cache()
    else:
        print_error(f"Could not update '{node_title}'.")


@perf_tracker.track("add_child")
def cmd_add(args: str):
    """Add a child node to a parent."""
    match = re.match(r"(.+?)\s+to\s+(.+)", args, re.IGNORECASE)
    if not match:
        print_error("Usage: add <ChildName> to <ParentName>")
        return

    child_raw  = match.group(1).strip()
    parent_raw = match.group(2).strip()

    print_info(f"Describe '{child_raw}' (or press Enter for AI to generate):")
    description = get_input()
    if not description:
        description = f"A sub-component of {parent_raw}"

    with spinner(f"🔗 Creating '{child_raw}' under '{parent_raw}'..."):
        result = create_child_node(parent_raw, child_raw, description)

    if result:
        print_success(f"Created '{result}' as child of '{parent_raw}'.")
        vm = get_vector_memory()
        if vm:
            node = read_node(result)
            if node:
                vm.index_node(result, node["content"])
    else:
        print_error(f"Could not find parent '{parent_raw}'.")


@perf_tracker.track("search")
def cmd_search(query: str):
    """Semantic search across all nodes."""
    if not query:
        print_error("Provide a search query.")
        return

    vm = get_vector_memory()
    if vm:
        with spinner("🔍 Semantic search..."):
            results = vm.search(query, top_k=5)
        if results:
            print_success(f"Found {len(results)} relevant nodes:")
            for r in results:
                relevance = "🔥" if r['similarity'] > 0.7 else "📄"
                print_info(f"{relevance} {r['title']} (score: {r['similarity']:.3f})")
            return

    # Fallback
    with spinner("🔍 Fuzzy search..."):
        matches = search_nodes(query, limit=8)
    if not matches:
        print_info("No matches found.")
    else:
        print_success(f"Found {len(matches)} match(es):")
        for m in matches:
            print_info(m)


def cmd_list():
    """List all nodes in a table."""
    nodes = list_all_nodes()
    if not nodes:
        print_info("No nodes yet. Use `summon <project>` to create your first project!")
        return

    if RICH:
        table = Table(title="📚 All Knowledge Nodes", show_lines=True)
        table.add_column("Title",    style="bold cyan", max_width=40)
        table.add_column("Type",     style="magenta")
        table.add_column("Parent",   style="dim", max_width=30)
        table.add_column("Children", style="green")
        table.add_column("Keywords", style="yellow", max_width=25)
        for n in nodes:
            kw = ", ".join(n.get("keywords", [])[:3]) if isinstance(n.get("keywords"), list) else ""
            table.add_row(
                n["title"],
                n.get("type", "?"),
                n.get("parent") or "—",
                str(len(n.get("children", []))),
                kw,
            )
        console.print(table)
    else:
        for n in nodes:
            print(f"  {n['title']} ({n.get('type','?')}) → parent: {n.get('parent') or '—'}")


def cmd_cache_stats():
    stats = response_cache.stats()
    if RICH:
        table = Table(title="💾 Response Cache", show_lines=True)
        table.add_column("Metric", style="bold cyan")
        table.add_column("Value", style="green")
        table.add_row("Cached Responses", str(stats['size']))
        table.add_row("TTL (hours)", str(stats['ttl_hours']))
        console.print(table)
    else:
        print(f"\n💾 Cache: {stats['size']} responses, TTL: {stats['ttl_hours']}h")


def cmd_clear_cache():
    with spinner("Clearing cache..."):
        clear_cache()
    print_success("Cache cleared!")


def cmd_stats():
    """Show performance statistics"""
    perf_tracker.show_stats()


def cmd_reset_stats():
    """Reset performance statistics"""
    print_info("Reset all performance counters? (yes/no)")
    if get_input().lower() == 'yes':
        perf_tracker.reset()
        print_success("Performance statistics reset!")
    else:
        print_info("Cancelled.")


@perf_tracker.track("nuke")
def cmd_nuke():
    """Complete automatic nuke — wipe everything and start fresh."""
    print_goblin(
        "⚠️ **NUKE COMMAND RECEIVED** ⚠️\n\n"
        "This will **COMPLETELY** wipe:\n"
        "- All projects and nodes\n"
        "- Vector database\n"
        "- All indexes and caches\n"
        "- Chat history\n\n"
        "The Goblin will have **total amnesia**.\n\n"
        "Type **NUKE** to confirm:",
        label="☢️ WARNING"
    )
    confirm = get_input()
    if confirm.strip() == "NUKE":
        print_info("Launching automatic nuke sequence...")
        from nuke import MemoryNuke
        nuke = MemoryNuke()
        nuke.nuke_everything(preserve_obsidian=True)
        perf_tracker.reset()
        print_goblin(
            "🧙 Goblin has total amnesia!\n\n"
            "Use `summon <project>` to create a new project.",
            label="✅ Nuke Complete"
        )
    else:
        print_info("Nuke cancelled. Memories preserved. 😅")


def cmd_help():
    help_text = """
## ✨ Summon Commands
| Command | Description |
|---------|-------------|
| `summon <project>` | Create full project with all sections |
| `memory_loss <project>` | Delete a project (or ALL) |
| `populate <project>` | Feed description to existing project |
| `nuke` | ☢️ Complete memory wipe and fresh start |

## 🔍 Query Commands
| Command | Description |
|---------|-------------|
| `fast <question>` | ⚡ Lightning fast cached answers |
| `ask <question>` | 🧠 Detailed answers with full context |

## 📚 Knowledge Commands
| Command | Description |
|---------|-------------|
| `show <node>` | Display node content |
| `show_me_your_brain` | Full knowledge tree view |
| `reproduce <node>` | Break node into sub-nodes |
| `update <instruction>` | Smart update with AI |
| `add <Child> to <Parent>` | Create child node |
| `list` | All nodes table |
| `search <query>` | Semantic search |

## 📊 Performance Commands
| Command | Description |
|---------|-------------|
| `stats` | Show performance timing metrics |
| `perf` | Alias for stats |
| `reset-stats` | Reset performance counters |

## 💾 System
| Command | Description |
|---------|-------------|
| `cache-stats` | Cache performance |
| `clear-cache` | Reset cache |
| `help` | This help |
| `exit` | Quit |

💡 **Pro tip**: Use `fast` for quick Q&A, `reproduce` to drill deeper, `stats` to see performance!
"""
    print_goblin(help_text, label="🧙 Help")


# ─── Intent Detector ──────────────────────────────────────────────────────────

def detect_intent(user_input: str) -> tuple[str, str]:
    text = user_input.strip()
    low  = text.lower().rstrip("!.,?")

    # Greetings
    if low in GREETINGS:
        return "greeting", ""

    # Explicit commands — order matters for prefix matching
    COMMANDS = [
        "summon", "memory_loss", "populate", "nuke", "obliterate",
        "fast", "show_me_your_brain", "reproduce",
        "ask", "show", "update", "add",
        "tree", "list", "search",
        "cache-stats", "clear-cache",
        "stats", "perf", "reset-stats",
        "help", "clear", "exit", "quit",
        "start", "delete", "expand",
    ]

    for cmd in COMMANDS:
        if low == cmd or low.startswith(cmd + " "):
            args = text[len(cmd):].strip()
            return cmd, args

    # Natural language intent detection
    if any(k in low for k in ["new project", "start project", "create project", "summon"]):
        return "summon", ""

    if any(k in low for k in ["delete memory", "clear memory", "forget everything", "memory loss"]):
        return "memory_loss", ""

    if any(k in low for k in ["nuke memory", "nuke everything", "wipe everything", "obliterate", "total wipe", "reset everything"]):
        return "nuke", ""

    if any(k in low for k in ["show brain", "show all", "full tree", "graph", "structure", "overview"]):
        return "show_me_your_brain", ""

    if any(k in low for k in ["break down", "split", "reproduce", "decompose"]):
        index = _load_index()
        for title in index:
            if title.lower() in low or title.replace("_", " ").lower() in low:
                return "reproduce", title
        return "reproduce", ""

    # Default to ask
    return "ask", text


# ─── Main Loop ────────────────────────────────────────────────────────────────

def main():
    os.system("cls" if os.name == "nt" else "clear")
    print_header()

    # Check Ollama
    if is_ollama_running():
        print_info("🖥️  Ollama detected and ready")
    else:
        print_info("⚠️  Ollama not running — install from https://ollama.com")

    # Initialize vector memory
    print_info("🔮 Initializing semantic search...")
    vm = get_vector_memory()
    node_count = len(list_all_nodes())

    if vm and node_count > 0:
        stats = vm.get_stats()
        if stats.get('total_nodes', 0) < node_count:
            print_info(f"📚 Indexing {node_count} nodes...")
            with spinner("Indexing..."):
                reindex_all()
            print_success("Search index ready! ⚡")
        else:
            print_success(f"Search engine ready ({stats.get('total_nodes', 0)} nodes indexed)")

    # Show projects
    projects = list_projects()
    if projects:
        print_success(f"Projects loaded: {', '.join(projects)}")
    else:
        print_info("No projects yet. Use `summon <project_name>` to begin!")

    print_info("Type `help` for all commands | `stats` for performance metrics\n")

    DISPATCH = {
        "greeting":          lambda _: print_goblin(GREETING_REPLY, label="🧙 Goblin's Memory"),
        "summon":            lambda a: cmd_summon(a),
        "memory_loss":       lambda a: cmd_memory_loss(a),
        "populate":          lambda a: cmd_populate(a),
        "fast":              lambda a: cmd_fast(a),
        "show_me_your_brain": lambda a: cmd_show_me_your_brain(a),
        "reproduce":         lambda a: cmd_reproduce(a),
        "ask":               lambda a: cmd_ask(a),
        "show":              lambda a: cmd_show(a),
        "update":            lambda a: cmd_update(a),
        "add":               lambda a: cmd_add(a),
        "tree":              lambda a: cmd_show_me_your_brain(a),
        "list":              lambda _: cmd_list(),
        "search":            lambda a: cmd_search(a),
        "cache-stats":       lambda _: cmd_cache_stats(),
        "clear-cache":       lambda _: cmd_clear_cache(),
        "stats":             lambda _: cmd_stats(),
        "perf":              lambda _: cmd_stats(),
        "reset-stats":       lambda _: cmd_reset_stats(),
        "nuke":              lambda _: cmd_nuke(),
        "obliterate":        lambda _: cmd_nuke(),
        "help":              lambda _: cmd_help(),
        "clear":             lambda _: os.system("cls" if os.name == "nt" else "clear"),
        "exit":              lambda _: sys.exit(0),
        "quit":              lambda _: sys.exit(0),
        "start":             lambda _: cmd_summon(""),
        "delete":            lambda _: cmd_memory_loss(""),
        "expand":            lambda a: cmd_reproduce(a),
    }

    while True:
        try:
            user_input = get_input()
            if not user_input:
                continue

            cmd, args = detect_intent(user_input)
            handler = DISPATCH.get(cmd)
            if handler:
                handler(args)
            else:
                cmd_ask(user_input)

        except KeyboardInterrupt:
            print("\n\n🧙 Farewell, mortal! Your memories are safe with me. 👋")
            # Show final stats on exit
            if perf_tracker.stats["total_ops"] > 0:
                print_info("\n📊 Session Performance Summary:")
                perf_tracker.show_stats()
            sys.exit(0)
        except EOFError:
            sys.exit(0)
        except Exception as e:
            print_error(f"Unexpected goblin malfunction: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()