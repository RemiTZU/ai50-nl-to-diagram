"""
CircuitForge - Circuit Drawing Module
Generates circuit diagrams from SPICE netlists using schemdraw.
Advanced layout with transistor support and feedback handling.
"""

import schemdraw
import schemdraw.elements as elm
from typing import List, Optional, Dict, Any
from collections import defaultdict
from dataclasses import dataclass


# Mapping from SPICE prefix to schemdraw element
ELEMENT_MAP = {
    "R": elm.Resistor,
    "C": elm.Capacitor,
    "L": elm.Inductor,
    "V": elm.SourceV,
    "I": elm.SourceI,
    "D": elm.Diode,
    "Q": elm.BjtNpn,
    "M": elm.NFet,
    "S": elm.Switch,
}


@dataclass
class CircuitImage:
    """Container for circuit image data."""

    svg_display: str  # White lines on transparent (for dark UI)
    svg_download: str  # Black lines on white (for download)
    width: int = 800
    height: int = 600


def _parse_components(netlist_text: str) -> List[Dict[str, Any]]:
    """
    Parse netlist into component dictionaries.
    Handles both 2-terminal and 3-terminal (transistor) components.
    """
    lines = netlist_text.strip().split("\n")
    all_components = []

    for line in lines:
        parts = line.split()
        if not parts or line.startswith("*") or line.startswith("."):
            continue
        if len(parts) < 3:
            continue

        name = parts[0]
        comp_type = name[0].upper()

        # Special handling for transistors (3+ terminals)
        if comp_type in ["Q", "M"]:
            if len(parts) >= 4:
                node1, node2, node3 = parts[1], parts[2], parts[3]
                value = parts[-1] if len(parts) > 4 else ""
                all_components.append(
                    {
                        "name": name,
                        "n1": node1,  # Collector/Drain
                        "n2": node2,  # Base/Gate
                        "n3": node3,  # Emitter/Source
                        "val": value,
                        "type": comp_type,
                    }
                )
        else:
            # 2-terminal components (R, C, L, V, I, D)
            node1, node2 = parts[1], parts[2]
            value = parts[3] if len(parts) > 3 else ""
            all_components.append(
                {
                    "name": name,
                    "n1": node1,
                    "n2": node2,
                    "val": value,
                    "type": comp_type,
                }
            )

    return all_components


def _draw_circuit_internal(
    netlist_text: str,
    color: str = "#000000",
    bgcolor: str = "white",
) -> Optional[str]:
    """
    Internal function to draw circuit with specified colors.
    Uses grid layout with intelligent component placement.
    """
    try:
        all_components = _parse_components(netlist_text)

        if not all_components:
            return None

        # Separate source and other components
        source = next((c for c in all_components if c["type"] in ["V", "I"]), None)
        components = [c for c in all_components if c["type"] not in ["V", "I"]]

        if not source:
            return None

        # Create drawing
        with schemdraw.Drawing(show=False) as d:
            d.config(fontsize=9, unit=2, color=color, bgcolor=bgcolor)

            # Step 1: Draw main source (vertical, going up, on the left)
            src_label = f"{source['name']}\n{source['val']}"
            src = d.add(
                ELEMENT_MAP[source["type"]](label=src_label)
                .up()
                .label("-", loc="bot")
                .label("+", loc="top")
            )

            # Key positions
            src_top = src.end  # + terminal
            src_bot = src.start  # - terminal (ground)

            # Step 2: Identify circuit structure
            ground = "0"
            source_pos_node = source["n1"]

            # Node position dictionary
            node_pos = {source["n2"]: src_bot, source_pos_node: src_top}

            # Track drawn components
            drawn = set()

            # Create connection graph for branch detection
            node_connections = defaultdict(list)
            for comp in components:
                node_connections[comp["n1"]].append(comp)
                if "n2" in comp:
                    node_connections[comp["n2"]].append(comp)

            # Step 3: Draw components in passes
            max_iterations = len(components) * 3
            iteration = 0

            while len(drawn) < len(components) and iteration < max_iterations:
                iteration += 1
                made_progress = False

                for comp in components:
                    if comp["name"] in drawn:
                        continue

                    # Can only draw if start node is known
                    if comp["n1"] not in node_pos:
                        continue

                    elem_class = ELEMENT_MAP.get(comp["type"], elm.Resistor)
                    label = f"{comp['name']}\n{comp['val']}"
                    start_pos = node_pos[comp["n1"]]

                    # Special handling for transistors (3 terminals)
                    if comp["type"] in ["Q", "M"] and "n3" in comp:
                        if comp["type"] == "Q":
                            elem = d.add(elm.BjtNpn(circle=True).right().at(start_pos))
                            if hasattr(elem, "emitter"):
                                node_pos[comp["n3"]] = elem.emitter
                            if hasattr(elem, "base"):
                                node_pos[comp["n2"]] = elem.base
                        else:  # MOSFET
                            elem = d.add(elm.NFet().right().at(start_pos))
                            if hasattr(elem, "source"):
                                node_pos[comp["n3"]] = elem.source
                            if hasattr(elem, "gate"):
                                node_pos[comp["n2"]] = elem.gate
                            if hasattr(elem, "drain"):
                                node_pos[comp["n1"]] = elem.drain

                        drawn.add(comp["name"])
                        made_progress = True
                        continue

                    # Orientation for 2-terminal components
                    if comp["n2"] == ground:
                        # Component to ground = vertical down
                        elem = d.add(elem_class(label=label).down().at(start_pos))

                    elif comp["n2"] not in node_pos:
                        # New node - decide horizontal or vertical
                        siblings = [
                            c
                            for c in node_connections[comp["n1"]]
                            if c["name"] not in drawn and c["name"] != comp["name"]
                        ]

                        if len(siblings) > 0:
                            # Parallel branch
                            d.push()
                            elem = d.add(elem_class(label=label).right().at(start_pos))
                            node_pos[comp["n2"]] = elem.end
                            d.pop()
                        else:
                            # Series component
                            elem = d.add(elem_class(label=label).right().at(start_pos))
                            node_pos[comp["n2"]] = elem.end

                    else:
                        # Existing node - direct connection (feedback)
                        elem = d.add(elem_class(label=label).to(node_pos[comp["n2"]]))

                    drawn.add(comp["name"])
                    made_progress = True

                if not made_progress:
                    break

            # Pass 2: Handle feedback components (missing nodes)
            remaining = [c for c in components if c["name"] not in drawn]

            if remaining:
                ref_nodes = [
                    n for n in node_pos.keys() if n != ground and n != source_pos_node
                ]

                for comp in remaining:
                    elem_class = ELEMENT_MAP.get(comp["type"], elm.Resistor)
                    label = f"{comp['name']}\n{comp['val']}"

                    if comp["n1"] not in node_pos:
                        if ref_nodes and ref_nodes[-1] in node_pos:
                            d.add(
                                elm.Line()
                                .right()
                                .at(node_pos[ref_nodes[-1]])
                                .length(0.5)
                            )
                            node_pos[comp["n1"]] = d.here

                    if comp["n1"] in node_pos:
                        if comp["n2"] in node_pos:
                            # Both nodes exist: feedback path
                            start = node_pos[comp["n1"]]
                            end = node_pos[comp["n2"]]

                            d.add(elm.Line(lw=0.5).up().at(start).length(1.5))
                            current_pos = d.here
                            d.add(elm.Line(lw=0.5).right().at(current_pos).tox(end))
                            current_pos = d.here
                            elem = d.add(
                                elem_class(label=label, lw=0.5)
                                .down()
                                .at(current_pos)
                                .length(0.7)
                            )
                            current_pos = elem.end
                            d.add(elm.Line(lw=0.5).down().at(current_pos).toy(end))
                        else:
                            elem = d.add(
                                elem_class(label=label, lw=0.5)
                                .up()
                                .at(node_pos[comp["n1"]])
                            )
                            node_pos[comp["n2"]] = elem.end

                        drawn.add(comp["name"])

            # Step 4: Close the circuit
            last_nodes = [
                n for n in node_pos.keys() if n != ground and n != source_pos_node
            ]

            if last_nodes:
                priority_nodes = ["source", "out", "drain"]
                last_node = None
                for pn in priority_nodes:
                    if pn in last_nodes:
                        last_node = pn
                        break
                if not last_node:
                    last_node = last_nodes[-1]

                if last_node in node_pos:
                    d.add(elm.Line().down().toy(src_bot))
                    d.add(elm.Line().left().tox(src_bot))

            return d.get_imagedata("svg").decode("utf-8")

    except Exception as e:
        print(f"Error drawing circuit: {e}")
        return None


def draw_circuit(netlist_text: str, show: bool = False) -> Optional[CircuitImage]:
    """
    Draw a circuit diagram from a SPICE netlist.

    Creates two versions:
    - Display version: white lines on dark background (for dark UI)
    - Download version: black lines on white background

    Args:
        netlist_text: SPICE netlist string
        show: Whether to display the circuit (for debugging)

    Returns:
        CircuitImage object with both SVG versions, or None on error
    """
    # Version for display (white on none - container provides background)
    svg_display = _draw_circuit_internal(netlist_text, color="#fafafa", bgcolor="none")

    if svg_display is None:
        return None

    # Version for download (black on white)
    svg_download = _draw_circuit_internal(
        netlist_text, color="#000000", bgcolor="white"
    )

    return CircuitImage(
        svg_display=svg_display, svg_download=svg_download or svg_display
    )


def draw_circuit_simple(netlist_text: str) -> Optional[str]:
    """
    Simplified circuit drawing - returns display SVG string only.
    """
    result = draw_circuit(netlist_text, show=False)
    return result.svg_display if result else None


def get_component_info(netlist_text: str) -> List[dict]:
    """
    Extract component information for display.
    """
    all_components = _parse_components(netlist_text)

    components = []
    for comp in all_components:
        # Get raw line for value extraction
        value = comp.get("val", "-") or "-"

        components.append(
            {
                "name": comp["name"],
                "type": comp["type"],
                "type_name": _get_type_name(comp["type"]),
                "nodes": f"{comp['n1']} - {comp.get('n2', comp.get('n3', '?'))}",
                "value": value,
            }
        )

    return components


def _get_type_name(prefix: str) -> str:
    """Get human-readable component type name."""
    names = {
        "R": "Resistor",
        "C": "Capacitor",
        "L": "Inductor",
        "V": "Voltage Source",
        "I": "Current Source",
        "D": "Diode",
        "Q": "Transistor (BJT)",
        "M": "MOSFET",
        "S": "Switch",
        "X": "Subcircuit",
    }
    return names.get(prefix, "Unknown")
