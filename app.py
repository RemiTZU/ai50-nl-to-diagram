"""
CircuitForge - Main Streamlit Application
Web interface for generating circuit diagrams from natural language.
"""

import streamlit as st
import time

from circuit_generator import get_generator
from spice_parser import clean_netlist, validate_netlist
from circuit_drawer import draw_circuit, get_component_info
from history_manager import (
    save_generation,
    load_all_generations,
    load_generation,
    delete_generation,
    clear_all_history,
)

# Page config
st.set_page_config(
    page_title="CircuitForge",
    page_icon="",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def load_css():
    with open("styles.css", "r") as f:
        return f.read()


st.markdown(f"<style>{load_css()}</style>", unsafe_allow_html=True)

# Icons (inline SVG)
BOLT_ICON = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>"""
BOLT_ICON_YELLOW = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#facc15"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>"""

# Pre-defined example prompts for quick start
EXAMPLES = [
    "A 3-stage RC high-pass filter implemented as an RC ladder network with the output taken at n1. It is powered by a 12V DC source. The filter type is high-pass. The network has 3 stage(s) connected in cascade. Stage 1 uses R1=4.7k and C1=1u. Stage 2 uses R2=1k and C2=220n. Stage 3 uses R3=47k and C3=10u.",
    "A cascaded circuit composed of 3 stages powered by a 12V DC source. Stage 1 is an RC high-pass stage. Stage 2 is an RC low-pass stage. Stage 3 is a resistive divider stage. The output is taken from node n1.",
    "A feedback circuit based on an RC network powered by a 12V DC source. The main path is a low-pass RC stage. The feedback is implemented using a resistive-capacitive feedback network, from node out to node in.",
    "A 2-stage RC high-pass filter and a resistive load at the output. It is powered by a 3.3V DC source. The filter type is high-pass. The filter has 2 stage(s). Stage 1 uses R1=2.2k and C1=2.2u. Stage 2 uses R2=10k and C2=10u. The load resistor is RL=10k.",
]

# Initialize session state
if "generations" not in st.session_state:
    st.session_state.generations = load_all_generations()
if "current_result" not in st.session_state:
    st.session_state.current_result = None
if "model_loaded" not in st.session_state:
    st.session_state.model_loaded = False
if "is_generating" not in st.session_state:
    st.session_state.is_generating = False


@st.cache_resource
def load_model():
    """Load T5 model (cached to avoid reloading on each rerun)."""
    generator = get_generator()
    success = generator.load()
    return generator if success else None


def generate_circuit(prompt: str) -> dict:
    """
    Main generation pipeline: prompt -> T5 -> clean -> validate -> draw.
    Returns result dict with netlist, SVG, components, and status.
    """
    result = {
        "id": f"gen_{int(time.time())}",
        "prompt": prompt,
        "timestamp": time.strftime("%d %b, %H:%M"),
        "status": "error",
        "netlist": None,
        "svg_display": None,
        "svg_download": None,
        "components": None,
        "error": None,
    }

    try:
        generator = load_model()
        if generator is None:
            result["error"] = "Failed to load model"
            return result

        # Generate raw netlist from T5
        raw_netlist = generator.generate(prompt)

        # Clean and validate
        netlist = clean_netlist(raw_netlist)
        result["netlist"] = netlist

        is_valid, message = validate_netlist(netlist)
        if not is_valid:
            result["error"] = f"Validation failed: {message}"
            result["status"] = "error"
            return result

        # Draw circuit diagram
        circuit_image = draw_circuit(netlist)
        if circuit_image:
            result["svg_display"] = circuit_image.svg_display
            result["svg_download"] = circuit_image.svg_download

        result["components"] = get_component_info(netlist)
        result["status"] = "completed"

    except Exception as e:
        result["error"] = str(e)
        result["status"] = "error"

    return result


# UI Components


def render_header():
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
    """Display generation result: circuit diagram, netlist, and components."""
    if result["status"] == "error":
        st.error(f"Error: {result.get('error', 'Unknown error')}")
        if result.get("netlist"):
            with st.expander("Raw Netlist"):
                st.code(result["netlist"], language="text")
        return

    # Circuit diagram
    if result.get("svg_display"):
        svg_safe = result["svg_display"].replace("\n", " ")
        st.markdown(
            f"""
            <div style="background: var(--bg, #0a0a0a); border: 1px solid #262626; border-radius: 10px; padding: 1.5rem; margin: 1rem 0; display: flex; justify-content: center; align-items: center; min-height: 300px;">
                {svg_safe}
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Tabs for netlist and components
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
    """Render a history item with Load/View and Delete buttons."""
    badge = "badge-ok" if g["status"] == "completed" else "badge-err"
    badge_txt = "OK" if g["status"] == "completed" else "Err"

    col_card, col_view, col_x = st.columns([7, 1.5, 0.5], gap="small")

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

    with col_view:
        is_loaded = (
            st.session_state.current_result
            and st.session_state.current_result.get("id") == g["id"]
        )
        st.markdown('<div class="hist-view">', unsafe_allow_html=True)
        btn_label = "View" if is_loaded else "Load"
        if st.button(btn_label, key=f"v{idx}", use_container_width=True):
            if not is_loaded:
                full_data = load_generation(g["id"])
                st.session_state.current_result = full_data if full_data else g
                st.session_state.prefill_prompt = g["prompt"]
            st.session_state.click_generate_tab = True
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    with col_x:
        st.markdown('<div class="hist-x">', unsafe_allow_html=True)
        if st.button("\u2715", key=f"x{idx}"):
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


# Main App

render_header()

generator = load_model()
if generator is None:
    st.error(
        "Failed to load the circuit generation model. Please check your installation."
    )
    st.stop()

tab_gen, tab_hist = st.tabs(["Generate", "History"])

# JS hack to switch tabs programmatically (Streamlit doesn't support this natively)
if st.session_state.get("click_generate_tab", False):
    if "tab_click_counter" not in st.session_state:
        st.session_state.tab_click_counter = 0
    st.session_state.tab_click_counter += 1
    counter = st.session_state.tab_click_counter
    st.session_state.click_generate_tab = False

    import streamlit.components.v1 as components

    components.html(
        f"""
        <script>
            const tabs = window.parent.document.querySelectorAll('[data-baseweb="tab"]');
            if (tabs.length > 0) {{ tabs[0].click(); }}
        </script>
        <!-- {counter} -->
        """,
        height=0,
    )

# Generate Tab
with tab_gen:
    is_busy = st.session_state.is_generating
    left, right = st.columns([1, 1], gap="large")

    # Left column: input
    with left:
        st.markdown(
            '<p class="label">Describe your circuit</p>', unsafe_allow_html=True
        )

        # Pre-fill from quickstart or loaded history
        default_value = ""
        if "prefill_prompt" in st.session_state:
            default_value = st.session_state.prefill_prompt
        elif st.session_state.current_result:
            default_value = st.session_state.current_result.get("prompt", "")

        prompt = st.text_area(
            "prompt",
            value=default_value,
            placeholder="Example: A 2-stage RC high-pass filter powered by a 5V DC source...",
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
                st.session_state.prefill_prompt = ""
                st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<p class="label">Quick start</p>', unsafe_allow_html=True)

        # Example prompts
        with st.container():
            st.markdown('<div class="quickstart-btns">', unsafe_allow_html=True)
            for i, example in enumerate(EXAMPLES):
                display_text = (
                    f"{i+1}. {example[:180]}..."
                    if len(example) > 180
                    else f"{i+1}. {example}"
                )
                if st.button(
                    display_text,
                    key=f"e{i}",
                    use_container_width=True,
                    disabled=is_busy,
                ):
                    st.session_state.run_ex = example
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    # Right column: result
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
                        data=r["svg_download"],
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

            if redo_btn and not is_busy:
                st.session_state.is_generating = True
                st.rerun()
        else:
            render_empty_state("No circuit yet", "Enter a prompt and click Generate")

    # Handle new generation
    if gen_btn and prompt.strip() and not is_busy:
        st.session_state.is_generating = True
        st.session_state.pending_prompt = prompt.strip()
        st.rerun()

    # Handle quickstart click
    if "run_ex" in st.session_state and not is_busy:
        st.session_state.is_generating = True
        st.session_state.pending_prompt = st.session_state.run_ex
        st.session_state.prefill_prompt = st.session_state.run_ex
        del st.session_state.run_ex
        st.rerun()

    # Run generation (after rerun with is_generating=True)
    if st.session_state.is_generating and "pending_prompt" in st.session_state:
        with st.spinner("Generating circuit..."):
            r = generate_circuit(st.session_state.pending_prompt)
        save_generation(r)
        st.session_state.current_result = r
        st.session_state.generations.append(r)
        st.session_state.is_generating = False
        del st.session_state.pending_prompt
        st.rerun()

    # Handle redo (regenerate with same prompt)
    if (
        st.session_state.is_generating
        and st.session_state.current_result
        and "pending_prompt" not in st.session_state
    ):
        with st.spinner("Regenerating circuit..."):
            r = generate_circuit(st.session_state.current_result["prompt"])
        save_generation(r)
        st.session_state.current_result = r
        st.session_state.generations.append(r)
        st.session_state.is_generating = False
        st.rerun()

# History Tab
with tab_hist:
    if st.session_state.generations:
        total = len(st.session_state.generations)
        ok_count = sum(
            1 for g in st.session_state.generations if g["status"] == "completed"
        )

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
                clear_all_history()
                st.session_state.generations = []
                st.session_state.current_result = None
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="hist-separator"></div>', unsafe_allow_html=True)

        # Display history cards (newest first)
        for idx, g in enumerate(reversed(st.session_state.generations)):
            render_history_card(g, idx)

    else:
        st.markdown("<div style='margin-top: 2rem;'>", unsafe_allow_html=True)
        render_empty_state("No history", "Generated circuits will appear here")
        st.markdown("</div>", unsafe_allow_html=True)
