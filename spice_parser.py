"""
CircuitForge - SPICE Parser Module
Handles netlist cleaning, parsing, and semantic validation.
"""

import re
from typing import Tuple, List, Dict, Optional
from dataclasses import dataclass


# Valid SPICE component prefixes
VALID_PREFIXES = {"R", "C", "L", "V", "I", "D", "Q", "M", "X", "S"}


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


def clean_netlist(netlist_text: str) -> str:
    """
    Clean the model output to ensure valid SPICE format (multiline).

    Args:
        netlist_text: Raw netlist string from model

    Returns:
        Cleaned netlist string
    """
    text = netlist_text.strip()

    # 1. Force newline before components
    # Pattern: Space + [Letter][Number] + [Space] + [Number]
    # This ensures we don't split model names like "D1N4148"
    text = re.sub(r"\s(?=[RCLVIDQMS][0-9]+\s+[0-9])", "\n", text)

    # 2. Force newline before .end command
    if ".end" in text.lower():
        text = re.sub(r"\.end", "\n.end", text, flags=re.IGNORECASE)

    # 3. Remove empty lines and extra whitespace
    text = re.sub(r"\n+", "\n", text)

    return text.strip()


def parse_netlist(netlist_text: str) -> ParsedNetlist:
    """
    Parse a SPICE netlist into structured components.

    Args:
        netlist_text: Netlist string

    Returns:
        ParsedNetlist object with components and metadata
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

    Args:
        netlist: Netlist string to validate

    Returns:
        Tuple of (is_valid, message)
    """
    lines = str(netlist).strip().split("\n")

    has_power_source = False
    has_ground = False
    component_count = 0

    for line in lines:
        line = line.strip()

        # Skip empty lines and comments
        if line == "" or line.startswith("*"):
            continue

        parts = line.split()

        # Skip SPICE commands (.tran, .model, .end, etc.)
        if line.startswith("."):
            continue

        if not parts:
            continue

        # 1. Check component prefix
        prefix = parts[0][0].upper()

        if prefix not in VALID_PREFIXES:
            return False, f"Invalid component prefix: {prefix} (Line: {line})"

        # 2. Check minimum parameters (Name + Node1 + Node2)
        if len(parts) < 3:
            return False, f"Not enough parameters: {line}"

        # 3. Check that nodes are numeric
        node1, node2 = parts[1], parts[2]
        if not node1.isdigit() or not node2.isdigit():
            return False, f"Nodes must be numeric: {line}"

        # Check for ground (node 0)
        if node1 == "0" or node2 == "0":
            has_ground = True

        # 4. Check for power source
        if prefix in {"V", "I"}:
            has_power_source = True

        # 5. Check value format for passive components (R, C, L only)
        if prefix in {"R", "C"}:
            if len(parts) < 4:
                return False, f"Missing value for component: {line}"

            value = parts[3]
            # Accept numbers with optional SI prefix (k, M, u, n, p, etc.)
            if not re.match(r"^\d+(\.\d+)?[a-zA-Z]*$", value):
                return False, f"Invalid value format: {value}"

        # 6. Check inductors (L) - can have value or be part of other syntax
        if prefix == "L":
            if len(parts) < 4:
                return False, f"Missing value for inductor: {line}"

        # 7. Check voltage/current sources - accept DC, AC, PULSE, etc.
        if prefix in {"V", "I"}:
            if len(parts) < 4:
                return False, f"Missing value for source: {line}"

        component_count += 1

    # Global validations
    if component_count == 0:
        return False, "No components found in netlist"

    if not has_ground:
        return False, "No ground node (0) found"

    if not has_power_source:
        return False, "No voltage or current source found"

    return True, "Valid"


def format_netlist_display(netlist: str) -> str:
    """
    Format netlist for display with proper indentation.

    Args:
        netlist: Raw netlist string

    Returns:
        Formatted netlist string
    """
    cleaned = clean_netlist(netlist)
    lines = cleaned.split("\n")
    formatted = []

    for line in lines:
        line = line.strip()
        if line.startswith("."):
            formatted.append(line)
        elif line.startswith("*"):
            formatted.append(line)
        else:
            formatted.append(f"  {line}")

    return "\n".join(formatted)
