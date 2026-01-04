"""
CircuitForge - SPICE Parser Module
Handles netlist cleaning and semantic validation.
"""

import re
from typing import Tuple


# Valid SPICE component prefixes
VALID_PREFIXES = {"R", "C", "L", "V", "I", "D", "Q", "M", "X", "S"}


def clean_netlist(raw_output: str) -> str:
    """
    Clean the model output to ensure valid SPICE format.
    Handles Vin, Rd, Rs and model names like D1N4148.
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


def validate_netlist(netlist: str) -> Tuple[bool, str]:
    """
    Validate the semantic correctness of a SPICE netlist.
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
