"""
CircuitForge - SPICE Parser
Netlist cleaning and semantic validation.
"""

import re
from typing import Tuple

# Standard SPICE component prefixes
VALID_PREFIXES = {"R", "C", "L", "V", "I", "D", "Q", "M", "X", "S"}


def clean_netlist(raw_output: str) -> str:
    """
    Clean raw T5 model output into valid SPICE format.
    Handles common issues: T5 tokens, missing line breaks, unit typos.
    """
    # Remove T5 special tokens
    text = raw_output.replace("</s>", "").replace("<pad>", "").strip()

    # Add line breaks before component names (R1, Vin, C2, etc.)
    text = re.sub(r"\s+(?=[RCLVIDQM](?:[a-z]|[0-9]))", "\n", text)

    # Fix .end stuck to values (e.g., "10u.end" -> "10u\n.end")
    text = re.sub(r"(\w)\.end", r"\1\n.end", text)

    # Fix values glued to next component (e.g., "47kVin" -> "47k\nVin")
    text = re.sub(r"([0-9]+[a-zA-Z]*)\s*([RCLVIDQM][a-z])", r"\1\n\2", text)

    lines = text.split("\n")
    valid_lines = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Reattach orphaned diode model names (D1N4148 on its own line)
        if line.startswith("D1N") and valid_lines:
            valid_lines[-1] += " " + line
            continue

        # Skip standalone numbers (model hallucinations)
        if line[0].isdigit():
            continue

        # Keep only valid SPICE lines
        first_char = line[0].upper()
        if first_char in ["R", "L", "C", "V", "I", "D", "Q", "M", ".", "*"]:
            # Fix common unit typos
            line = line.replace("mmH", "mH").replace("uuF", "uF")
            valid_lines.append(line)

    return "\n".join(valid_lines)


def validate_netlist(netlist: str) -> Tuple[bool, str]:
    """
    Validate SPICE netlist semantics.
    Checks: valid prefixes, node format, ground presence, power source.
    """
    lines = str(netlist).strip().split("\n")
    has_power_source = False
    has_ground = False

    for line in lines:
        line = line.strip()

        # Skip comments and empty lines
        if line == "" or line.startswith("*"):
            continue

        parts = line.split()

        # Skip SPICE directives (.end, .tran, etc.)
        if line.startswith("."):
            continue

        if not parts:
            continue

        prefix = parts[0][0].upper()

        if prefix not in VALID_PREFIXES:
            return False, f"Invalid component prefix: {prefix} (Line: {line})"

        # SPICE format: NAME NODE1 NODE2 [VALUE] [MODEL]
        if len(parts) < 3:
            return False, f"Not enough parameters: {line}"

        # Validate node names (numeric or alphanumeric identifiers)
        node1, node2 = parts[1], parts[2]
        valid_node_pattern = r"^(\d+|[a-zA-Z_][a-zA-Z0-9_]*)$"
        if not re.match(valid_node_pattern, node1) or not re.match(
            valid_node_pattern, node2
        ):
            return False, f"Invalid node format: {line}"

        # Track ground (node 0)
        if node1 == "0" or node2 == "0":
            has_ground = True

        # Track power sources
        if prefix == "V" or prefix == "I":
            has_power_source = True

        # Passive components need a value
        if prefix in {"R", "C", "L"}:
            if len(parts) < 4:
                return False, f"Missing value for component: {line}"

            value = parts[3]
            if not re.match(r"^\d+(\.\d+)?[a-zA-Z]*$", value):
                return False, f"Invalid value format: {value}"

    # Circuit must have ground and power source
    if not has_ground:
        return False, "No ground node (0) found"

    if not has_power_source:
        return False, "No voltage or current source found"

    return True, "Valid"
