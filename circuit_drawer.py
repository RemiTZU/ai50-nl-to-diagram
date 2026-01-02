"""
CircuitForge - Circuit Drawing Module
Generates circuit diagrams from SPICE netlists using schemdraw.
"""

import schemdraw
import schemdraw.elements as elm
from typing import List, Optional, Tuple
import io
import base64
from dataclasses import dataclass

from spice_parser import parse_netlist, Component


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
    "X": elm.Dot,
}


@dataclass
class CircuitImage:
    """Container for circuit image data."""

    svg_display: str  # White lines on transparent (for dark UI)
    svg_download: str  # Black lines on white (for download)
    width: int = 800
    height: int = 600


def _draw_circuit_internal(
    netlist_text: str,
    color: str = "#000000",
    bgcolor: str = "white",
    show: bool = False,
) -> Optional[str]:
    """
    Internal function to draw circuit with specified colors.

    Args:
        netlist_text: SPICE netlist string
        color: Line/text color
        bgcolor: Background color
        show: Whether to display

    Returns:
        SVG string or None
    """
    try:
        parsed = parse_netlist(netlist_text)

        if not parsed.components:
            return None

        # Separate source from other components
        source = None
        other_components = []

        for comp in parsed.components:
            if comp.type == "V":
                source = comp
            else:
                other_components.append(comp)

        # Create drawing
        with schemdraw.Drawing(show=show) as d:
            d.config(fontsize=11, unit=3, color=color, bgcolor=bgcolor)

            # 1. Draw source (going up)
            if source:
                label = f"{source.name}\n{source.value or ''}"
                source_elem = d.add(elm.SourceV(label=label).up())
            else:
                source_elem = d.add(elm.Dot())

            # 2. Draw other components
            for i, comp in enumerate(other_components):
                element_class = ELEMENT_MAP.get(comp.type, elm.Dot)
                label = f"{comp.name}\n{comp.value or ''}"

                is_last = i == len(other_components) - 1

                if is_last and len(other_components) > 1:
                    # Last component goes down
                    d.add(element_class(label=label).down())
                else:
                    # Other components go right
                    d.add(element_class(label=label).right())

            # 3. Close the loop with a wire
            if len(other_components) > 0:
                d.add(elm.Wire().to(source_elem.start))

            # Get SVG data
            return d.get_imagedata("svg").decode("utf-8")

    except Exception as e:
        print(f"Error drawing circuit: {e}")
        return None


def draw_circuit(netlist_text: str, show: bool = False) -> Optional[CircuitImage]:
    """
    Draw a circuit diagram from a SPICE netlist.

    Creates two versions:
    - Display version: white lines on transparent (for dark UI)
    - Download version: black lines on white background

    Args:
        netlist_text: SPICE netlist string
        show: Whether to display the circuit (for debugging)

    Returns:
        CircuitImage object with both SVG versions, or None on error
    """
    # Version for display (white on transparent)
    svg_display = _draw_circuit_internal(
        netlist_text, color="#fafafa", bgcolor="transparent", show=show
    )

    if svg_display is None:
        return None

    # Version for download (black on white)
    svg_download = _draw_circuit_internal(
        netlist_text, color="#000000", bgcolor="white", show=False
    )

    return CircuitImage(
        svg_display=svg_display, svg_download=svg_download or svg_display
    )


def draw_circuit_simple(netlist_text: str) -> Optional[str]:
    """
    Simplified circuit drawing - returns display SVG string only.

    Args:
        netlist_text: SPICE netlist string

    Returns:
        SVG string or None on error
    """
    result = draw_circuit(netlist_text, show=False)
    return result.svg_display if result else None


def get_component_info(netlist_text: str) -> List[dict]:
    """
    Extract component information for display.

    Args:
        netlist_text: SPICE netlist string

    Returns:
        List of component dictionaries
    """
    parsed = parse_netlist(netlist_text)

    components = []
    for comp in parsed.components:
        components.append(
            {
                "name": comp.name,
                "type": comp.type,
                "type_name": _get_type_name(comp.type),
                "nodes": f"{comp.node1} - {comp.node2}",
                "value": comp.value or "-",
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
