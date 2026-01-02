# CircuitForge ⚡

AI-powered electronic circuit generator from natural language descriptions.

## Setup

```bash
# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Run

```bash
source venv/bin/activate
streamlit run app.py
```

Open http://localhost:8501 in your browser.

## Usage

1. Describe your circuit in plain English (e.g. "9V battery with 1k resistor in series")
2. Click **Generate**
3. View the circuit diagram and SPICE netlist
4. Download as SVG if needed

## Tech Stack

- Streamlit
- Hugging Face Transformers (Remiwe/nl_to_spice model)
- Schemdraw
