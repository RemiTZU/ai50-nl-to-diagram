"""
CircuitForge - History Manager
Persists generation results to disk (JSON index + SVG/SPICE files).
"""

import json
import os
from typing import List, Optional

HISTORY_DIR = "history"
HISTORY_FILE = os.path.join(HISTORY_DIR, "generations.json")


def ensure_history_dir():
    """Create history directory if needed."""
    if not os.path.exists(HISTORY_DIR):
        os.makedirs(HISTORY_DIR)


def save_generation(result: dict) -> bool:
    """Save generation result: SVG files + netlist + JSON metadata."""
    try:
        ensure_history_dir()
        gen_id = result["id"]

        # Save SVG files separately (not in JSON to keep index small)
        if result.get("svg_display"):
            with open(os.path.join(HISTORY_DIR, f"{gen_id}_display.svg"), "w") as f:
                f.write(result["svg_display"])

        if result.get("svg_download"):
            with open(os.path.join(HISTORY_DIR, f"{gen_id}_download.svg"), "w") as f:
                f.write(result["svg_download"])

        if result.get("netlist"):
            with open(os.path.join(HISTORY_DIR, f"{gen_id}.spice"), "w") as f:
                f.write(result["netlist"])

        # Update JSON index (metadata only)
        history = load_history_index()

        entry = {
            "id": result["id"],
            "prompt": result["prompt"],
            "timestamp": result["timestamp"],
            "status": result["status"],
            "error": result.get("error"),
            "has_svg": bool(result.get("svg_display")),
            "has_netlist": bool(result.get("netlist")),
            "components": result.get("components"),
        }

        existing_idx = next(
            (i for i, h in enumerate(history) if h["id"] == result["id"]), None
        )
        if existing_idx is not None:
            history[existing_idx] = entry
        else:
            history.append(entry)

        with open(HISTORY_FILE, "w") as f:
            json.dump(history, f, indent=2)

        return True

    except Exception as e:
        print(f"Error saving generation: {e}")
        return False


def load_history_index() -> List[dict]:
    """Load history index (metadata only, no SVG data)."""
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading history: {e}")
    return []


def load_generation(gen_id: str) -> Optional[dict]:
    """Load full generation data including SVG and netlist files."""
    try:
        history = load_history_index()
        entry = next((h for h in history if h["id"] == gen_id), None)

        if entry is None:
            return None

        result = dict(entry)

        # Load associated files
        svg_display_path = os.path.join(HISTORY_DIR, f"{gen_id}_display.svg")
        if os.path.exists(svg_display_path):
            with open(svg_display_path, "r") as f:
                result["svg_display"] = f.read()

        svg_download_path = os.path.join(HISTORY_DIR, f"{gen_id}_download.svg")
        if os.path.exists(svg_download_path):
            with open(svg_download_path, "r") as f:
                result["svg_download"] = f.read()

        netlist_path = os.path.join(HISTORY_DIR, f"{gen_id}.spice")
        if os.path.exists(netlist_path):
            with open(netlist_path, "r") as f:
                result["netlist"] = f.read()

        return result

    except Exception as e:
        print(f"Error loading generation {gen_id}: {e}")
        return None


def delete_generation(gen_id: str) -> bool:
    """Delete generation and associated files."""
    try:
        # Remove files
        for suffix in ["_display.svg", "_download.svg", ".spice"]:
            path = os.path.join(HISTORY_DIR, f"{gen_id}{suffix}")
            if os.path.exists(path):
                os.remove(path)

        # Update index
        history = load_history_index()
        history = [h for h in history if h["id"] != gen_id]

        with open(HISTORY_FILE, "w") as f:
            json.dump(history, f, indent=2)

        return True

    except Exception as e:
        print(f"Error deleting generation {gen_id}: {e}")
        return False


def clear_all_history() -> bool:
    """Delete all history files and reset index."""
    try:
        if os.path.exists(HISTORY_DIR):
            for filename in os.listdir(HISTORY_DIR):
                filepath = os.path.join(HISTORY_DIR, filename)
                if os.path.isfile(filepath):
                    os.remove(filepath)

        with open(HISTORY_FILE, "w") as f:
            json.dump([], f)

        return True

    except Exception as e:
        print(f"Error clearing history: {e}")
        return False


def load_all_generations() -> List[dict]:
    """Load all generations with full data (for app startup)."""
    history = load_history_index()
    full_history = []

    for entry in history:
        full = load_generation(entry["id"])
        if full:
            full_history.append(full)

    return full_history
