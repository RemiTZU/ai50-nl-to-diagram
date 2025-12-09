from agents import Agent, Runner
from pydantic import BaseModel
import asyncio

class TextNetlistPair(BaseModel):
    text: str
    netlist: str

class TextToNetlistOutput(BaseModel):
    pairs: list[TextNetlistPair]

class ChatGPTService:
    agent = Agent(
        name="Assistant",
        instructions=(
            "You are an expert electrical engineer specializing in SPICE simulation. "
            "Your task is to generate examples of text–netlist code pairs. "
            "Each example must include:\n"
            " - A clear and natural English description of an electrical circuit (`text` field).\n"
            " - A valid and self-contained SPICE netlist implementing that circuit (`netlist` field).\n"
            "\n"
            "### STRICT RULES FOR NETLIST GENERATION ###\n"
            "1. The first line must be a comment starting with `*` describing the circuit.\n"
            "2. The last line must be `.end` — never `.ends`, and never followed by a newline or quote.\n"
            "3. Always include the power source first (e.g., `V1 1 0 DC 5`).\n"
            "4. Use the following syntax conventions:\n"
            "   - Voltage sources: `Vx node+ node- DC value` or `Vx node+ node- AC value`\n"
            "   - Current sources: `Ix node+ node- DC value`\n"
            "   - Resistors: `Rx node1 node2 value`\n"
            "   - Capacitors: `Cx node1 node2 value`\n"
            "   - Inductors: `Lx node1 node2 value`\n"
            "   - Diodes: `Dx node1 node2 model`\n"
            "   - BJTs: `Qx collector base emitter model`\n"
            "5. Do not add unit letters to voltage values (e.g., write `DC 5`, not `DC 5V`).\n"
            "6. Use standard SI suffixes only: `k` (kilo), `m` (milli), `u` (micro), `n` (nano), `p` (pico).\n"
            "7. Use node numbers 1, 2, 3, and 0 (ground) only — no text labels or symbols.\n"
            "8. Always place the voltage source first, followed by passive components, then semiconductors.\n"
            "9. Always specify model names for diodes and transistors (e.g., `D1N4148`, `2N3904`).\n"
            "10. If transistors or diodes are used, they must have proper `.model` definitions "
            "or reference standard models (e.g., `D1N4148`, `2N3904`).\n"
            "11. Each circuit must be self-contained and runnable in SPICE — "
            "no `.subckt`, `.ends`, `.connect`, `.node`, or undefined models.\n"
            "12. Component names and directives must be uppercase (R, C, L, V, D, Q, X, `.MODEL`, `.END`).\n"
            "13. Ensure that each circuit is electrically valid (no floating nodes, no open components).\n"
            "14. Keep circuits simple and plausible: 3–6 components per example.\n"
            "15. Do not include units like 'ohm', 'farad', or 'henry' — use numeric + suffix only.\n"
            "\n"
            "### OUTPUT FORMAT ###\n"
            "The output must strictly match the `TextToNetlistOutput` schema: "
            "a list named `pairs`, where each element has:\n"
            " - `text`: a concise English description of the circuit.\n"
            " - `netlist`: the complete SPICE code, multiline, formatted as described above.\n"
            "\n"
            "Ensure formatting is exact, consistent, and ready for CSV export or SPICE simulation."
        ),
        output_type=TextToNetlistOutput,
        model="gpt-4o-mini",
    )


    async def generate_response(self, nb_results: int) -> TextToNetlistOutput:
        print(f"Generating {nb_results} text-netlist code pairs...")

        result = await Runner.run(
            self.agent,
            'Generate {nb_results} examples of text descriptions and their corresponding netlist code.'
        )

        print("Generated response:", result.final_output)

        return result.final_output