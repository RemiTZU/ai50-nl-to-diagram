"""
CircuitForge - AI-Powered Electronic Circuit Generator
Main Streamlit Application
"""

import streamlit as st
import time
from typing import Optional

# Local imports
from circuit_generator import get_generator
from spice_parser import (
    clean_netlist,
    validate_netlist,
    parse_netlist,
    normalize_prompt,
    repair_netlist,
)
from circuit_drawer import draw_circuit, get_component_info
from history_manager import (
    save_generation,
    load_all_generations,
    load_generation,
    delete_generation,
    clear_all_history,
)

# =============================================================================
# Page Config
# =============================================================================

st.set_page_config(
    page_title="CircuitForge",
    page_icon="",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# =============================================================================
# Load Styles
# =============================================================================


def load_css():
    with open("styles.css", "r") as f:
        return f.read()


st.markdown(f"<style>{load_css()}</style>", unsafe_allow_html=True)

# =============================================================================
# Constants
# =============================================================================

BOLT_ICON = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>"""
BOLT_ICON_YELLOW = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#facc15"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>"""

EXAMPLES = [
    "9V battery with 1k resistor in series",
    "5V source with two resistors in series",
    "12V battery with resistor and capacitor in series",
    "Battery with 100 ohm resistor",
]

# =============================================================================
# Session State
# =============================================================================

if "generations" not in st.session_state:
    # Load history from disk on first run
    st.session_state.generations = load_all_generations()
if "current_result" not in st.session_state:
    st.session_state.current_result = None
if "model_loaded" not in st.session_state:
    st.session_state.model_loaded = False
if "is_generating" not in st.session_state:
    st.session_state.is_generating = False

# =============================================================================
# Model Loading
# =============================================================================


@st.cache_resource
def load_model():
    """Load the circuit generation model (cached)."""
    generator = get_generator()
    success = generator.load()
    return generator if success else None


# =============================================================================
# Generation Function
# =============================================================================


def generate_circuit(prompt: str) -> dict:
    """
    Generate a circuit from a text prompt.

    Returns a result dictionary with:
    - id, prompt, timestamp
    - status: 'completed' or 'error'
    - netlist: cleaned SPICE netlist
    - svg: circuit diagram SVG
    - components: list of component info
    - error: error message if failed
    """
    result = {
        "id": f"gen_{int(time.time())}",
        "prompt": prompt,
        "timestamp": time.strftime("%d %b, %H:%M"),
        "status": "error",
        "netlist": None,
        "svg_display": None,  # White on transparent (for UI)
        "svg_download": None,  # Black on white (for download)
        "components": None,
        "error": None,
    }

    try:
        # Get generator
        generator = load_model()
        if generator is None:
            result["error"] = "Failed to load model"
            return result

        # Normalize prompt for better model understanding
        normalized_prompt = normalize_prompt(prompt)

        # Generate netlist
        raw_netlist = generator.generate(normalized_prompt)

        # Clean and repair netlist
        netlist = clean_netlist(raw_netlist)
        netlist = repair_netlist(netlist)
        result["netlist"] = netlist

        # Validate
        is_valid, message = validate_netlist(netlist)
        if not is_valid:
            result["error"] = f"Validation failed: {message}"
            result["status"] = "error"
            return result

        # Draw circuit
        circuit_image = draw_circuit(netlist)
        if circuit_image:
            result["svg_display"] = circuit_image.svg_display
            result["svg_download"] = circuit_image.svg_download

        # Get component info
        result["components"] = get_component_info(netlist)

        result["status"] = "completed"

    except Exception as e:
        result["error"] = str(e)
        result["status"] = "error"

    return result


# =============================================================================
# UI Components
# =============================================================================


def render_header():
    """Render the app header with logo and title."""
    st.markdown(
        f"""
        <div class="header-container">
            <div class="app-brand">
                <div class="app-logo">{BOLT_ICON}</div>
                <div class="app-name">CircuitForge</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_empty_state(title: str, desc: str):
    """Render an empty state box."""
    st.markdown(
        f"""
        <div class="empty-box">
            <div class="empty-icon">{BOLT_ICON_YELLOW}</div>
            <div class="empty-title">{title}</div>
            <div class="empty-desc">{desc}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_result(result: dict):
    """Render the generation result."""

    # Header with prompt
    st.markdown(
        f"""
        <div class="result-box">
            <div class="result-header">{result['prompt']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if result["status"] == "error":
        st.error(f"Error: {result.get('error', 'Unknown error')}")
        if result.get("netlist"):
            with st.expander("Raw Netlist"):
                st.code(result["netlist"], language="text")
        return

    # Circuit diagram (display version - white on dark)
    if result.get("svg_display"):
        st.markdown(
            f"""
            <div style="background: #141414; border: 1px solid #262626; border-radius: 10px; padding: 1rem; margin: 1rem 0;">
                {result['svg_display']}
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Tabs for details
    tab_netlist, tab_components = st.tabs(["SPICE Netlist", "Components"])

    with tab_netlist:
        if result.get("netlist"):
            st.code(result["netlist"], language="text")

    with tab_components:
        if result.get("components"):
            for comp in result["components"]:
                st.markdown(
                    f"""
                    <div style="display: flex; gap: 1rem; padding: 0.5rem 0; border-bottom: 1px solid #262626;">
                        <span style="color: #facc15; font-weight: 600; min-width: 60px;">{comp['name']}</span>
                        <span style="color: #a3a3a3; min-width: 100px;">{comp['type_name']}</span>
                        <span style="color: #fafafa;">{comp['value']}</span>
                        <span style="color: #737373; margin-left: auto;">Nodes: {comp['nodes']}</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


def render_history_card(g: dict, idx: int):
    """Render a single history card with actions."""
    badge = "badge-ok" if g["status"] == "completed" else "badge-err"
    badge_txt = "OK" if g["status"] == "completed" else "Err"

    col_card, col_btns = st.columns([8, 2])

    with col_card:
        st.markdown(
            f"""
            <div class="hist-card">
                <div class="history-prompt">{g['prompt']}</div>
                <div class="history-meta">
                    <span class="history-time">{g['timestamp']}</span>
                    <span class="history-badge {badge}">{badge_txt}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_btns:
        btn_view, btn_x = st.columns([3, 1])

        with btn_view:
            # Check if this item is already loaded
            is_loaded = (
                st.session_state.current_result
                and st.session_state.current_result.get("id") == g["id"]
            )
            st.markdown('<div class="hist-view">', unsafe_allow_html=True)
            btn_label = "View" if is_loaded else "Load"
            if st.button(btn_label, key=f"v{idx}", use_container_width=True):
                if not is_loaded:
                    # Load full data from disk
                    full_data = load_generation(g["id"])
                    st.session_state.current_result = full_data if full_data else g
                # Flag to click Generate tab
                st.session_state.click_generate_tab = True
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

        with btn_x:
            st.markdown('<div class="hist-x">', unsafe_allow_html=True)
            if st.button("\u2715", key=f"x{idx}"):
                # Delete from disk
                delete_generation(g["id"])
                st.session_state.generations = [
                    x for x in st.session_state.generations if x["id"] != g["id"]
                ]
                if (
                    st.session_state.current_result
                    and st.session_state.current_result["id"] == g["id"]
                ):
                    st.session_state.current_result = None
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)


# =============================================================================
# Main App
# =============================================================================

render_header()

# Model loading status
generator = load_model()
if generator is None:
    st.error(
        "Failed to load the circuit generation model. Please check your installation."
    )
    st.stop()

tab_gen, tab_hist = st.tabs(["Generate", "History"])

# Auto-click Generate tab if coming from Load button
if st.session_state.get("click_generate_tab", False):
    # Increment counter to force unique script each time
    if "tab_click_counter" not in st.session_state:
        st.session_state.tab_click_counter = 0
    st.session_state.tab_click_counter += 1
    counter = st.session_state.tab_click_counter
    st.session_state.click_generate_tab = False

    import streamlit.components.v1 as components

    components.html(
        f"""
        <script>
            // Execution #{counter}
            const tabs = window.parent.document.querySelectorAll('[data-baseweb="tab"]');
            if (tabs.length > 0) {{
                tabs[0].click();
            }}
        </script>
        <!-- {counter} -->
        """,
        height=0,
    )

# =============================================================================
# Generate Tab
# =============================================================================

with tab_gen:
    # Check if generating (disable buttons)
    is_busy = st.session_state.is_generating

    left, right = st.columns([1, 1], gap="large")

    # Left Column - Input
    with left:
        st.markdown(
            '<p class="label">Describe your circuit</p>', unsafe_allow_html=True
        )

        prompt = st.text_area(
            "prompt",
            placeholder="Example: LED circuit with 9V battery and 330 ohm resistor...",
            height=140,
            label_visibility="collapsed",
            disabled=is_busy,
        )

        c1, c2 = st.columns(2)
        with c1:
            gen_btn = st.button(
                "Generating..." if is_busy else "Generate",
                use_container_width=True,
                key="gen_main",
                disabled=is_busy,
            )
        with c2:
            new_btn = st.button(
                "New",
                use_container_width=True,
                key="new_circuit",
                disabled=is_busy or not st.session_state.current_result,
                type="secondary",
            )
            if new_btn and st.session_state.current_result:
                st.session_state.current_result = None
                st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<p class="label">Quick start</p>', unsafe_allow_html=True)

        ex1, ex2 = st.columns(2)

        with ex1:
            st.markdown('<div class="btn-secondary btn-small">', unsafe_allow_html=True)
            if st.button(
                EXAMPLES[0], key="e1", use_container_width=True, disabled=is_busy
            ):
                st.session_state.run_ex = EXAMPLES[0]
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

            st.markdown('<div class="btn-secondary btn-small">', unsafe_allow_html=True)
            if st.button(
                EXAMPLES[2], key="e3", use_container_width=True, disabled=is_busy
            ):
                st.session_state.run_ex = EXAMPLES[2]
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

        with ex2:
            st.markdown('<div class="btn-secondary btn-small">', unsafe_allow_html=True)
            if st.button(
                EXAMPLES[1], key="e2", use_container_width=True, disabled=is_busy
            ):
                st.session_state.run_ex = EXAMPLES[1]
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

            st.markdown('<div class="btn-secondary btn-small">', unsafe_allow_html=True)
            if st.button(
                EXAMPLES[3], key="e4", use_container_width=True, disabled=is_busy
            ):
                st.session_state.run_ex = EXAMPLES[3]
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    # Right Column - Result
    with right:
        st.markdown('<p class="label">Result</p>', unsafe_allow_html=True)

        if st.session_state.current_result:
            r = st.session_state.current_result
            render_result(r)

            st.markdown("<br>", unsafe_allow_html=True)

            ac1, ac2 = st.columns(2)
            with ac1:
                st.markdown('<div class="btn-action">', unsafe_allow_html=True)
                if r.get("svg_download"):
                    st.download_button(
                        "\u2193  Download SVG",
                        data=r["svg_download"],  # Black on white version
                        file_name=f"circuit_{r['id']}.svg",
                        mime="image/svg+xml",
                        use_container_width=True,
                        disabled=is_busy,
                    )
                else:
                    st.button(
                        "\u2193  Download",
                        key="dl_disabled",
                        disabled=True,
                        use_container_width=True,
                    )
                st.markdown("</div>", unsafe_allow_html=True)
            with ac2:
                st.markdown('<div class="btn-action">', unsafe_allow_html=True)
                redo_btn = st.button(
                    "Generating..." if is_busy else "\u21bb  Redo",
                    key="redo",
                    use_container_width=True,
                    disabled=is_busy,
                )
                st.markdown("</div>", unsafe_allow_html=True)

            # Handle redo
            if redo_btn and not is_busy:
                st.session_state.is_generating = True
                st.rerun()
        else:
            render_empty_state("No circuit yet", "Enter a prompt and click Generate")

    # Handle generation (with loading state)
    if gen_btn and prompt.strip() and not is_busy:
        st.session_state.is_generating = True
        st.session_state.pending_prompt = prompt.strip()
        st.rerun()

    if "run_ex" in st.session_state and not is_busy:
        st.session_state.is_generating = True
        st.session_state.pending_prompt = st.session_state.run_ex
        del st.session_state.run_ex
        st.rerun()

    # Actually run generation when is_generating is True
    if st.session_state.is_generating and "pending_prompt" in st.session_state:
        with st.spinner("Generating circuit..."):
            r = generate_circuit(st.session_state.pending_prompt)
        # Save to disk
        save_generation(r)
        st.session_state.current_result = r
        st.session_state.generations.append(r)
        st.session_state.is_generating = False
        del st.session_state.pending_prompt
        st.rerun()

    # Handle redo generation
    if (
        st.session_state.is_generating
        and st.session_state.current_result
        and "pending_prompt" not in st.session_state
    ):
        with st.spinner("Regenerating circuit..."):
            r = generate_circuit(st.session_state.current_result["prompt"])
        # Save to disk
        save_generation(r)
        st.session_state.current_result = r
        st.session_state.generations.append(r)
        st.session_state.is_generating = False
        st.rerun()

# =============================================================================
# History Tab
# =============================================================================

with tab_hist:
    if st.session_state.generations:
        total = len(st.session_state.generations)
        ok_count = sum(
            1 for g in st.session_state.generations if g["status"] == "completed"
        )

        # Stats + Clear
        col_stats, col_clear = st.columns([5, 1])

        with col_stats:
            st.markdown(
                f"""
                <div class="stats-row">
                    <div class="stat-item">
                        <span class="stat-num">{total}</span>
                        <span class="stat-label">total</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-num">{ok_count}</span>
                        <span class="stat-label">success</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with col_clear:
            st.markdown('<div class="btn-clear">', unsafe_allow_html=True)
            if st.button("Clear all", use_container_width=True):
                # Clear from disk
                clear_all_history()
                st.session_state.generations = []
                st.session_state.current_result = None
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="hist-separator"></div>', unsafe_allow_html=True)

        # History items
        for idx, g in enumerate(reversed(st.session_state.generations)):
            render_history_card(g, idx)

    else:
        st.markdown("<div style='margin-top: 2rem;'>", unsafe_allow_html=True)
        render_empty_state("No history", "Generated circuits will appear here")
        st.markdown("</div>", unsafe_allow_html=True)
