"""
CircuitForge - SPICE Parser Module
Handles prompt normalization, netlist cleaning, parsing, and semantic validation.
"""

import re
from typing import Tuple, List, Optional
from dataclasses import dataclass


# Valid SPICE component prefixes
VALID_PREFIXES = {"R", "C", "L", "V", "I", "D", "Q", "M", "X", "S"}


def normalize_prompt(user_input: str) -> str:
    """
    Normalize user input to a standardized prompt format for the model.

    Handles various input styles:
    - Natural language: "A circuit with a 9V battery and 330 ohm resistor"
    - Compact: "12V 100 ohm resistor 1mH inductor"
    - Abbreviated: "9v, led, 100r"
    """
    # 1. Basic cleanup
    text = user_input.lower().replace(",", " ").replace("-", " ")

    # 2. Extract source voltage
    source_val = "12"
    source_match = re.search(r"(\d+(?:\.\d+)?)\s*v", text)
    if source_match:
        source_val = source_match.group(1)
        text = text.replace(source_match.group(0), " ")

    components = []

    # Type roots sorted by length (longer first)
    type_roots = {
        "resistor": "resistor",
        "inductor": "inductor",
        "capacitor": "capacitor",
        "diode": "diode",
        "led": "diode",
        "coil": "inductor",
        "ohm": "resistor",
        "res": "resistor",
        "cap": "capacitor",
        "ind": "inductor",
        "r": "resistor",
        "l": "inductor",
        "c": "capacitor",
        "d": "diode",
        "h": "inductor",
        "f": "capacitor",
    }
    sorted_roots = sorted(
        type_roots.items(), key=lambda item: len(item[0]), reverse=True
    )

    ignore_words = [
        "battery",
        "source",
        "generator",
        "connected",
        "with",
        "to",
        "and",
        "in",
        "series",
        "circuit",
        "a",
        "an",
        "the",
    ]

    tokens = text.split()
    buffer_val = None

    for token in tokens:
        # Remove trailing period (preserves decimals like "4.7k")
        token = token.rstrip(".")

        if not token or token in ignore_words:
            continue

        # A. Is it a value? (supports decimals)
        val_match = re.match(r"^(\d+(?:\.\d+)?)([munpk]+)?(h|f|ohm)?$", token)

        # B. Is it a component type?
        found_type = None
        if not (val_match and not val_match.group(3)):
            for root, std_name in sorted_roots:
                if root in token:
                    if len(token) > 3 and len(root) == 1 and not val_match:
                        continue
                    found_type = std_name
                    break

        # Assembly logic
        if val_match:
            val_num = val_match.group(1)
            unit_prefix = val_match.group(2) if val_match.group(2) else ""
            unit_suffix = val_match.group(3)

            if unit_suffix:
                if "h" in unit_suffix:
                    components.append(f"a {val_num}{unit_prefix}mH inductor")
                elif "f" in unit_suffix:
                    components.append(f"a {val_num}{unit_prefix}F capacitor")
                elif "ohm" in unit_suffix:
                    components.append(f"a {val_num}{unit_prefix} resistor")
                buffer_val = None
            else:
                if unit_prefix in ["u", "n", "p"]:
                    components.append(f"a {val_num}{unit_prefix}F capacitor")
                    buffer_val = None
                elif unit_prefix == "m":
                    buffer_val = f"{val_num}m"
                else:
                    buffer_val = f"{val_num}{unit_prefix}"

        elif found_type:
            if found_type == "diode":
                components.append("a diode")
                if buffer_val:
                    components.append(f"a {buffer_val} resistor")
                    buffer_val = None
            elif buffer_val:
                val_s = buffer_val
                if found_type == "inductor":
                    if not val_s.endswith("H"):
                        val_s += "H"
                elif found_type == "capacitor":
                    if not val_s.endswith("F"):
                        val_s += "F"
                components.append(f"a {val_s} {found_type}")
                buffer_val = None

    if buffer_val:
        components.append(f"a {buffer_val} resistor")

    if not components:
        return user_input  # Return original if no components detected

    comp_str = (
        ", ".join(components[:-1]) + " and " + components[-1]
        if len(components) > 1
        else components[0]
    )
    return f"A series circuit with {source_val}V source, {comp_str}."


@dataclass
class Component:
    """Represents a SPICE component."""

    name: str
    type: str
    node1: str
    node2: str
    value: Optional[str] = None
    model: Optional[str] = None
    raw_line: str = ""


@dataclass
class ParsedNetlist:
    """Parsed netlist with components and metadata."""

    components: List[Component]
    has_ground: bool
    has_power_source: bool
    raw_text: str
    cleaned_text: str


def clean_netlist(raw_output: str) -> str:
    """
    Clean the model output to ensure valid SPICE format.
    Exactly like wen.py - handles Vin, Rd, Rs and model names like D1N4148.
    """
    # 1. Clean T5 tokens
    text = raw_output.replace("</s>", "").replace("<pad>", "").strip()

    # 2. Smart segmentation
    # Pattern: SPICE letter followed by lowercase OR digit (handles Vin, R1, etc.)
    text = re.sub(r"\s+(?=[RCLVIDQM](?:[a-z]|[0-9]))", "\n", text)

    # 3. Fix .end collisions (e.g., "10u.end" -> "10u\n.end")
    text = re.sub(r"(\w)\.end", r"\1\n.end", text)

    # 4. Fix AC/DC glued to components (e.g., "47kVin" -> "47k\nVin")
    text = re.sub(r"([0-9]+[a-zA-Z]*)\s*([RCLVIDQM][a-z])", r"\1\n\2", text)

    lines = text.split("\n")
    valid_lines = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Reattach orphaned model names (e.g., "D1N4148" on its own line)
        if line.startswith("D1N") and valid_lines:
            valid_lines[-1] += " " + line
            continue

        # Skip numeric hallucinations (e.g., standalone "12")
        if line[0].isdigit():
            continue

        # Validate SPICE line format
        first_char = line[0].upper()
        if first_char in ["R", "L", "C", "V", "I", "D", "Q", "M", ".", "*"]:
            # Fix common unit typos
            line = line.replace("mmH", "mH").replace("uuF", "uF")
            valid_lines.append(line)

    return "\n".join(valid_lines)


def repair_netlist(netlist_text: str) -> str:
    """
    Repair common model errors in the netlist.
    Fixes: Inductors (L) mistakenly generated instead of Diodes (D).
    """
    text = netlist_text.replace(".end", "\n.end")

    lines = []
    tokens = text.split()
    current_line = []
    comp_start_pattern = re.compile(r"^[RCLVIDQM][0-9]+")

    for token in tokens:
        if comp_start_pattern.match(token) and current_line:
            lines.append(" ".join(current_line))
            current_line = [token]
        elif token.lower() == ".end":
            if current_line:
                lines.append(" ".join(current_line))
            current_line = []
            lines.append(".end")
        else:
            current_line.append(token)

    if current_line:
        lines.append(" ".join(current_line))

    # Repair semantic errors (L vs D confusion)
    final_lines = []
    for line in lines:
        parts = line.strip().split()
        if not parts:
            continue

        name = parts[0]
        prefix = name[0].upper()

        # Fix: Inductor (L) hallucinated instead of Diode (D)
        if prefix == "L" and len(parts) >= 4:
            val = parts[-1].upper()
            if "LED" in val or "1N" in val or "DIODE" in val:
                new_name = "D" + name[1:]  # L1 -> D1
                parts[0] = new_name
                line = " ".join(parts)

        final_lines.append(line)

    return "\n".join(final_lines)


def parse_netlist(netlist_text: str) -> ParsedNetlist:
    """
    Parse a SPICE netlist into structured components.
    """
    cleaned = clean_netlist(netlist_text)
    lines = cleaned.split("\n")

    components = []
    has_ground = False
    has_power_source = False

    for line in lines:
        line = line.strip()

        # Skip empty lines, comments, and commands
        if not line or line.startswith("*") or line.startswith("."):
            continue

        parts = line.split()
        if len(parts) < 3:
            continue

        name = parts[0]
        prefix = name[0].upper()

        if prefix not in VALID_PREFIXES:
            continue

        node1, node2 = parts[1], parts[2]
        value = parts[3] if len(parts) > 3 else None
        model = parts[4] if len(parts) > 4 else None

        component = Component(
            name=name,
            type=prefix,
            node1=node1,
            node2=node2,
            value=value,
            model=model,
            raw_line=line,
        )
        components.append(component)

        # Check for ground
        if node1 == "0" or node2 == "0":
            has_ground = True

        # Check for power source
        if prefix in {"V", "I"}:
            has_power_source = True

    return ParsedNetlist(
        components=components,
        has_ground=has_ground,
        has_power_source=has_power_source,
        raw_text=netlist_text,
        cleaned_text=cleaned,
    )


def validate_netlist(netlist: str) -> Tuple[bool, str]:
    """
    Validate the semantic correctness of a SPICE netlist.
    Exactly like semantic_validate in wen.py.
    """
    lines = str(netlist).strip().split("\n")
    has_power_source = False
    has_ground = False

    for line in lines:
        line = line.strip()

        # Skip empty lines and comments
        if line == "" or line.startswith("*"):
            continue

        parts = line.split()

        # Skip SPICE commands
        if line.startswith("."):
            continue

        # 1. Check component prefix
        if not parts:
            continue
        prefix = parts[0][0].upper()

        if prefix not in VALID_PREFIXES:
            return False, f"Invalid component prefix: {prefix} (Line: {line})"

        # 2. Check minimum parameters (Name + Node1 + Node2)
        if len(parts) < 3:
            return False, f"Not enough parameters: {line}"

        # 3. Check node format (numeric or valid identifier like 'in', 'out', 'vdd')
        node1, node2 = parts[1], parts[2]
        valid_node_pattern = r"^(\d+|[a-zA-Z_][a-zA-Z0-9_]*)$"
        if not re.match(valid_node_pattern, node1) or not re.match(
            valid_node_pattern, node2
        ):
            return False, f"Invalid node format: {line}"

        # Check for ground (node 0)
        if node1 == "0" or node2 == "0":
            has_ground = True

        # 4. Check for power source
        if prefix == "V" or prefix == "I":
            has_power_source = True

        # 5. Check value format for passive components
        if prefix in {"R", "C", "L"}:
            if len(parts) < 4:
                return False, f"Missing value for component: {line}"

            value = parts[3]
            if not re.match(r"^\d+(\.\d+)?[a-zA-Z]*$", value):
                return False, f"Invalid value format: {value}"

    # Global validations
    if not has_ground:
        return False, "No ground node (0) found"

    if not has_power_source:
        return False, "No voltage or current source found"

    return True, "Valid"


def try_fix_invalid_netlist(raw_netlist: str) -> str:
    """
    If the netlist is invalid, try to fix it by removing
    the last component line before .end (often a hallucination).
    """
    lines = raw_netlist.strip().split("\n")

    # Find .end index
    end_idx = -1
    for i, line in enumerate(lines):
        if line.strip().lower() == ".end":
            end_idx = i
            break

    if end_idx == -1:
        end_idx = len(lines)

    # Find line to remove (going backwards from .end)
    idx_to_remove = -1
    for i in range(end_idx - 1, -1, -1):
        line = lines[i].strip()
        if line and not line.startswith("*"):
            idx_to_remove = i
            break

    if idx_to_remove != -1:
        del lines[idx_to_remove]

    return "\n".join(lines)
