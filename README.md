# CircuitForge

AI-powered circuit generation from natural language descriptions.

## Overview

CircuitForge is a web application that transforms text descriptions into electronic circuit schematics. It uses a fine-tuned T5 model to generate SPICE netlists, which are then validated and rendered as circuit diagrams.

## Requirements

- Python 3.10+
- ~500MB disk space (for model download)

## Installation

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

```bash
source venv/bin/activate
streamlit run app.py
```

Open http://localhost:8501 in your browser.

1. Enter a circuit description (e.g., "A feedback circuit based on an RC network powered by a 12V DC source. The main path is a low-pass RC stage. The feedback is implemented using a resistive-capacitive feedback network, from node out to node in.")
2. Click **Generate**
3. View the circuit diagram and SPICE netlist
4. Export as SVG if needed

The model downloads automatically on first launch.

## Project Structure

```
app.py                 # Main Streamlit application
circuit_generator.py   # T5 model loading and inference
spice_parser.py        # Netlist cleaning and validation
circuit_drawer.py      # Circuit diagram rendering (Schemdraw)
history_manager.py     # Generation history persistence
styles.css             # UI styling
```

## Tech Stack

- **Streamlit** - Web interface
- **Hugging Face Transformers** - T5 model for netlist generation
- **Schemdraw** - Circuit diagram rendering
- **PyTorch** - Model backend
