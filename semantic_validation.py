import subprocess
import tempfile
import pandas as pd
import re

NGSPICE_PATH = r"C:\Program Files\ngspice-45.2_64\Spice64\bin\ngspice_con.exe"


def is_valid_node(node):
    # Ground
    if node == "0":
        return True
    # Numeric node
    if node.isdigit():
        return True
    # Symbolic node: in, out, n1, vdd, gate, etc.
    return re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", node) is not None


# ===========================================================
#  Semantic Validation (does not rely on ngspice; faster and smarter)
# ===========================================================

VALID_PREFIXES = {"R", "C", "L", "V", "I", "D", "Q", "M", "X"}

def semantic_validate(net):
    """
    Only perform semantic checking, without calling ngspice.
    Return: (True/False, reason)
    """

    lines = str(net).strip().split("\n")

    has_power_source = False
    has_ground = False

    for line in lines:
        line = line.strip()
        if line == "" or line.startswith("*"):
            continue

        parts = line.split()

        # Dot-commands, e.g. .end, .op, .tran, .subckt, …
        if line.startswith("."):
            continue   

        # ------------------------------
        # 1. Check whether the first letter is a valid device type.
        # ------------------------------
        prefix = parts[0][0].upper()    

        if prefix not in VALID_PREFIXES:
            return False, f"Invalid device prefix: {prefix}"

        # ------------------------------
        # 2. Check whether the number of parameters is ≥ 3 (name + node1 + node2).
        # ------------------------------
        if len(parts) < 3:
            return False, f"Too few parameters in line: {line}"

        # ------------------------------
        # 3. Check whether the nodes are digits or 0.
        # ------------------------------
        node1, node2 = parts[1], parts[2]
        # if not node1.isdigit() or not node2.isdigit():
        #     return False, f"Node names must be numbers: {line}"
        if not is_valid_node(node1) or not is_valid_node(node2):
            return False, f"Invalid node name: {line}"

        # ground
        if node1 == "0" or node2 == "0":
            has_ground = True

        # ------------------------------
        # 4. Check that there is at least one voltage source (V) or current source (I).
        # ------------------------------
        if prefix == "V" or prefix == "I":
            has_power_source = True

        # ------------------------------
        # 5. Check whether the value matches a number + unit pattern (e.g., 10k, 1u).
        # ------------------------------
        if prefix in {"R", "C", "L"}:
            if len(parts) < 4:
                return False, f"Missing value: {line}"

            value = parts[3]
            if not re.match(r"^\d+(\.\d+)?[a-zA-Z]*$", value):
                return False, f"Invalid value format: {value}"

    # ------------------------------
    # 6. No ground → invalid.
    # ------------------------------
    if not has_ground:
        return False, "No ground node (0) found"

    # ------------------------------
    # 7. No power supply → invalid.
    # ------------------------------
    if not has_power_source:
        return False, "No voltage source found"

    return True, "OK"



# ===========================================================
#  Ngspice Validation (checks whether the SPICE syntax can be parsed)
# ===========================================================
def validate_by_ngspice(net):

    net = str(net).strip()

    # --- ① Automatically append .end ---
    if ".end" not in net.lower():
        net += "\n.end"

    # --- ② Automatically append .op ---
    if ".op" not in net.lower():
        net = net.replace(".end", ".op\n.end")

    # Write a temporary file.
    with tempfile.NamedTemporaryFile(delete=False, suffix=".sp", mode="w") as f:
        f.write(net)
        fname = f.name

    # Call ngspice.
    proc = subprocess.run(
        [NGSPICE_PATH, "-b", fname],
        capture_output=True,
        text=True
    )

    errors = (proc.stdout + "\n" + proc.stderr).strip()

    # ---- Model not found → ignore (enhanced version).----
    if "could not find a valid modelname" in errors.lower():
        return True, "Missing model ignored"

    # ---- If it errors → invalid. ----
    if "error" in errors.lower():
        return False, errors

    return True, "OK"



# ===========================================================
#  Pipeline: semantic validation + ngspice validation.
# ===========================================================
df = pd.read_csv(r"C:\Users\TAN\AI50_V2\results_augmented.csv", header=None, engine='python')

for i in range(len(df)):
    net = df.iloc[i, 1]

    # ---- Step 1: semantic validation ----
    sem_ok, sem_msg = semantic_validate(net)
    if not sem_ok:
        print(i, False, "SEMANTIC ERROR:", sem_msg)
        continue

    # ---- Step 2: ngspice syntax validation ----
    spice_ok, spice_msg = validate_by_ngspice(net)
    print(i, spice_ok)
    if not spice_ok:
        print("NGSPICE ERROR:", spice_msg)
