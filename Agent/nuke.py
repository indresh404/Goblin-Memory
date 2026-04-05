#!/usr/bin/env python3
"""
🧙 Goblin's Memory - Complete Automatic Nuke System
One command to wipe EVERYTHING and start fresh.
"""

import os
import sys
import shutil
import json
import time
from pathlib import Path


class MemoryNuke:
    """Complete automatic memory wipe system"""

    def __init__(self):
        self.base_path = Path(__file__).parent.parent   # d:\AI_Brain
        self.memory_path = self.base_path / "Memory"
        self.agent_path = self.base_path / "Agent"

    def nuke_everything(self, preserve_obsidian=True):
        """
        Complete automatic wipe.
        Args:
            preserve_obsidian: Keep Obsidian settings (.obsidian/) or nuke those too.
        """
        print("💀" * 30)
        print("🧙 GOBLIN'S MEMORY - AUTOMATIC NUKE LAUNCHED")
        print("💀" * 30)
        print()

        self._wipe_memory_folder(preserve_obsidian)
        self._wipe_vector_db()
        self._wipe_indexes()
        self._wipe_projects()
        self._create_fresh_structure()
        self._create_fresh_indexes()
        self._reset_vector_memory()
        self._clear_temp_files()

        ok = self._verify_clean_state()

        print()
        print("✨" * 30)
        if ok:
            print("✅ COMPLETE AUTOMATIC NUKE SUCCESSFUL!")
        else:
            print("⚠️  NUKE COMPLETE (some checks failed — non-critical)")
        print("🧙 Goblin has total amnesia. Starting fresh...")
        print("✨" * 30)
        print()

    # ── internals ─────────────────────────────────────────────────────────

    def _wipe_memory_folder(self, preserve_obsidian: bool):
        print("🗑️  Wiping Memory folder...")
        if not self.memory_path.exists():
            print("  ℹ️  Memory folder doesn't exist — creating fresh")
            self.memory_path.mkdir(parents=True)
            return

        if preserve_obsidian:
            obsidian_path = self.memory_path / ".obsidian"
            obsidian_backup = self.base_path / ".obsidian_backup"

            if obsidian_path.exists():
                if obsidian_backup.exists():
                    shutil.rmtree(obsidian_backup)
                shutil.copytree(obsidian_path, obsidian_backup)
                print("  📦 Obsidian settings backed up")

            for item in self.memory_path.iterdir():
                if item.name == ".obsidian":
                    continue
                try:
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()
                except Exception as e:
                    print(f"  ⚠️  Could not remove {item.name}: {e}")

            print("  ✅ Memory wiped (preserved .obsidian)")

            if obsidian_backup.exists():
                obsidian_path = self.memory_path / ".obsidian"
                if not obsidian_path.exists():
                    shutil.copytree(obsidian_backup, obsidian_path)
                shutil.rmtree(obsidian_backup, ignore_errors=True)
                print("  📦 Obsidian settings restored")
        else:
            shutil.rmtree(self.memory_path)
            self.memory_path.mkdir(parents=True)
            print("  ☢️  Complete memory folder deleted (nuclear)")

    def _wipe_vector_db(self):
        print("🗄️  Wiping vector database...")
        vector_db = self.memory_path / ".vector_db"
        if vector_db.exists():
            shutil.rmtree(vector_db, ignore_errors=True)
            print("  ✅ Vector database deleted")
        else:
            print("  ℹ️  No vector database found")

    def _wipe_indexes(self):
        print("📊 Wiping indexes and caches...")
        patterns = ["_index.json", ".query_cache.json", "chat_history.md"]
        for name in patterns:
            f = self.memory_path / name
            if f.exists():
                f.unlink()
                print(f"  ✅ {name} deleted")

        cache_dir = self.memory_path / ".cache"
        if cache_dir.exists():
            shutil.rmtree(cache_dir, ignore_errors=True)
            print("  ✅ .cache/ deleted")

    def _wipe_projects(self):
        print("📁 Wiping projects...")
        projects_path = self.memory_path / "Projects"
        if projects_path.exists():
            shutil.rmtree(projects_path, ignore_errors=True)
            print("  ✅ All projects deleted")

    def _create_fresh_structure(self):
        print("🏗️  Creating fresh structure...")
        for folder in ["Projects", ".cache"]:
            (self.memory_path / folder).mkdir(parents=True, exist_ok=True)
            print(f"  ✅ {folder}/ created")

    def _create_fresh_indexes(self):
        """Create fresh files in the format that obsidian.py expects."""
        print("📝 Creating fresh indexes...")

        # _index.json — obsidian.py expects a flat dict: { "NodeTitle": {...meta...} }
        (self.memory_path / "_index.json").write_text("{}", encoding="utf-8")
        print("  ✅ _index.json created (empty)")

        # query cache
        (self.memory_path / ".query_cache.json").write_text("{}", encoding="utf-8")
        print("  ✅ .query_cache.json created")

        # response cache
        cache_dir = self.memory_path / ".cache"
        cache_dir.mkdir(exist_ok=True)
        (cache_dir / "responses.json").write_text("{}", encoding="utf-8")
        print("  ✅ .cache/responses.json created")

        # chat history
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        (self.memory_path / "chat_history.md").write_text(
            f"# Chat History\n\n*Fresh start on {ts}*\n\n", encoding="utf-8"
        )
        print("  ✅ chat_history.md created")

    def _reset_vector_memory(self):
        print("🔄 Resetting vector memory...")
        try:
            sys.path.insert(0, str(self.agent_path))
            from vector_memory import get_vector_memory
            vm = get_vector_memory()
            if vm:
                vm.clear_all()
                print("  ✅ Vector memory cleared")
            else:
                print("  ℹ️  Vector memory not available (dependencies missing)")
        except Exception as e:
            print(f"  ⚠️  Vector reset skipped: {e}")

    def _clear_temp_files(self):
        print("🧹 Clearing temp files...")
        pycache = self.agent_path / "__pycache__"
        if pycache.exists():
            shutil.rmtree(pycache, ignore_errors=True)
            print("  ✅ __pycache__ removed")

    def _verify_clean_state(self):
        print("🔍 Verifying clean state...")
        projects_dir = self.memory_path / "Projects"
        checks = {
            "Projects empty": projects_dir.exists() and len(list(projects_dir.glob("*"))) == 0,
            "No vector DB": not (self.memory_path / ".vector_db").exists(),
            "Index is {}": self._check_json_empty(self.memory_path / "_index.json"),
            "Chat history exists": (self.memory_path / "chat_history.md").exists(),
        }
        all_ok = True
        for label, passed in checks.items():
            print(f"  {'✅' if passed else '❌'} {label}")
            if not passed:
                all_ok = False
        return all_ok

    @staticmethod
    def _check_json_empty(path: Path) -> bool:
        if not path.exists():
            return False
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return isinstance(data, dict) and len(data) == 0
        except Exception:
            return False


# ── CLI entry point ──────────────────────────────────────────────────────────

def nuke_now(force: bool = False, preserve_obsidian: bool = True):
    """Callable from other modules (e.g. main.py)."""
    nuke = MemoryNuke()
    if force:
        nuke.nuke_everything(preserve_obsidian=preserve_obsidian)
    else:
        confirm = input("\nType 'NUKE' to wipe everything automatically: ")
        if confirm.strip() == "NUKE":
            preserve = input("Preserve Obsidian settings? (Y/n): ").strip().lower()
            nuke.nuke_everything(preserve_obsidian=(preserve in ("", "y", "yes")))
        else:
            print("\n❌ Nuke cancelled. Your memories are safe.")


def main():
    print("\n" + "☢️ " * 20)
    print("⚠️  GOBLIN'S MEMORY - AUTOMATIC NUKE SYSTEM ⚠️")
    print("☢️ " * 20)
    print()
    print("This will AUTOMATICALLY:")
    print("  • Delete ALL projects and nodes")
    print("  • Wipe vector database")
    print("  • Clear all indexes and caches")
    print("  • Reset chat history")
    print("  • Create fresh empty structure")
    print()

    if len(sys.argv) > 1 and sys.argv[1] == "--force":
        print("💀 FORCE NUKE — No confirmation needed")
        nuke = MemoryNuke()
        nuke.nuke_everything(preserve_obsidian=True)
    else:
        nuke_now()


if __name__ == "__main__":
    main()