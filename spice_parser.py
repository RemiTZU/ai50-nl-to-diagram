"""
CircuitForge - SPICE Parser Module
Handles prompt normalization, netlist cleaning, parsing, and semantic validation.
"""

import re
from typing import Tuple, List, Dict, Optional
from dataclasses import dataclass


# Valid SPICE component prefixes
VALID_PREFIXES = {"R", "C", "L", "V", "I", "D", "Q", "M", "X", "S"}

# Component type roots for prompt normalization
TYPE_ROOTS = {
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

IGNORE_WORDS = [
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


def normalize_prompt(user_input: str) -> str:
    """
    Normalize user input to a standardized prompt format for the model.

    Handles various input styles:
    - Natural language: "A circuit with a 9V battery and 330 ohm resistor"
    - Compact: "12V 100 ohm resistor 1mH inductor"
    - Abbreviated: "9v, led, 100r"

    Args:
        user_input: Raw user input string

    Returns:
        Normalized prompt string for the model
    """


def normalize_prompt(user_input):
    # 1. Nettoyage de base

    text = user_input.lower().replace(",", " ").replace("-", " ")

    # 2. Extraction Source
    source_val = "12"
    source_match = re.search(r"(\d+(?:\.\d+)?)\s*v", text)
    if source_match:
        source_val = source_match.group(1)
        text = text.replace(source_match.group(0), " ")

    components = []

    # Dictionnaire trié par longueur (IMPORTANT)
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
        # --- CORRECTIF DÉCIMALE ---
        # On enlève le point SEULEMENT s'il est à la fin du mot (ex: "10u.")
        # Cela préserve "4.7k" mais nettoie "100 ohm."
        token = token.rstrip(".")

        if not token or token in ignore_words:
            continue

        # A. Est-ce une valeur ? (Regex supporte les décimales \.\d+)
        val_match = re.match(r"^(\d+(?:\.\d+)?)([munpk]+)?(h|f|ohm)?$", token)

        # B. Est-ce un type ?
        found_type = None
        if not (val_match and not val_match.group(3)):
            for root, std_name in sorted_roots:
                if root in token:
                    if len(token) > 3 and len(root) == 1 and not val_match:
                        continue
                    found_type = std_name
                    break

        # LOGIQUE D'ASSEMBLAGE
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
        return "Error: No components detected"

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


def clean_netlist(raw_output):
    # 1. Nettoyage tokens T5
    text = raw_output.replace("</s>", "").replace("<pad>", "").strip()

    # --- ÉTAPE 1 : SEGMENTATION INTELLIGENTE ---

    # OLD (Bug): text = re.sub(r'\s+(?=[RCLVIDQM]\d+)', '\n', text)

    # NEW (Fix): On utilise un "Negative Lookahead" (?!N)
    # On coupe devant [Lettre][Chiffre] SEULEMENT SI ce n'est pas suivi d'un 'N'
    # Ça détecte "D2" mais ignore "D1N4148"
    text = re.sub(r"\s+(?=[RCLVIDQM]\d+(?!N))", "\n", text)

    # Correction du collage .end (ex: "10u.end" -> "10u\n.end")
    text = re.sub(r"(\w)\.end", r"\1\n.end", text)

    lines = text.split("\n")
    valid_lines = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # (Gardez votre logique de D1N et suppression de chiffres ici)
        if line.startswith("D1N") and valid_lines:
            valid_lines[-1] += " " + line
            continue
        if line[0].isdigit():
            continue

        # Validation Standard SPICE
        first_char = line[0].upper()
        if first_char in ["R", "L", "C", "V", "I", "D", "Q", "M", ".", "*"]:
            line = line.replace("mmH", "mH").replace("uuF", "uF")

            # === NOUVEAU PATCH ICI ===
            # Si c'est un composant (R,L,C,D...) mais qu'il a moins de 3 parties (Nom N1 N2 Val)
            # On considère que c'est une hallucination et on l'ignore.
            parts = line.split()
            if first_char in ["R", "L", "C", "D"] and len(parts) < 4:
                continue  # On saute cette ligne incomplète (ex: "R2.")
            # =========================

            valid_lines.append(line)
    if not valid_lines or valid_lines[-1].lower() != ".end":
        valid_lines.append(".end")
    # ======================================

    return "\n".join(valid_lines)


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


def repair_netlist(netlist_text: str) -> str:
    """
    Repair common model errors in the netlist.

    Fixes issues like:
    - Inductors (L) mistakenly generated instead of Diodes (D)
    - Incorrect component identification based on value/model

    Args:
        netlist_text: Netlist string to repair

    Returns:
        Repaired netlist string
    """
    # First clean the netlist
    text = netlist_text.replace(".end", "\n.end")

    lines = []
    tokens = text.split()

    current_line = []
    comp_start_pattern = re.compile(r"^[RCLVIDQM][0-9]+")

    for token in tokens:
        # If token looks like component start and we have content, start new line
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
        # Check if value looks like a diode model (1N4148, LED, D1N...)
        if prefix == "L" and len(parts) >= 4:
            val = parts[-1].upper()
            if "LED" in val or "1N" in val or "DIODE" in val:
                # Force type to Diode
                new_name = "D" + name[1:]  # L1 -> D1
                parts[0] = new_name
                line = " ".join(parts)

        final_lines.append(line)

    return "\n".join(final_lines)


def ifNotValideCircuit(raw_netlist: str) -> str:
    """
    Si la netlist est invalide, tente de la réparer en supprimant
    la dernière ligne de composant avant le .end (souvent une hallucination).
    """
    lines = raw_netlist.strip().split("\n")

    # 1. Trouver l'index de la ligne .end (insensible à la casse)
    end_idx = -1
    for i, line in enumerate(lines):
        if line.strip().lower() == ".end":
            end_idx = i
            break

    # Si pas de .end, on considère la fin du fichier comme référence
    if end_idx == -1:
        end_idx = len(lines)

    # 2. Chercher la ligne à supprimer en remontant depuis .end
    idx_to_remove = -1
    for i in range(end_idx - 1, -1, -1):
        line = lines[i].strip()
        # On cherche une ligne qui n'est ni vide, ni un commentaire (*)
        if line and not line.startswith("*"):
            idx_to_remove = i
            break

    # 3. Suppression si une ligne candidate a été trouvée
    if idx_to_remove != -1:
        print(f"Correction auto : Suppression de la ligne '{lines[idx_to_remove]}'")
        del lines[idx_to_remove]

    return "\n".join(lines)
