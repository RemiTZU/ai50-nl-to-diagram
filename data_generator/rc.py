# # data_generator/rc.py
# import random

# def generate(n_samples):
#     samples = []

#     for _ in range(n_samples):
#         topo = random.choice([
#             "basic",        # 单 RC
#             "with_load",    # RC + 并联负载
#             "divider",      # RC + 分压输出
#             "two_stage"     # 两级 RC
#         ])

#         V = random.choice(["3.3", "5", "12"])
#         R = random.choice(["1k", "4.7k", "10k", "22k"])
#         C = random.choice(["100n", "1u", "10u"])

#         # =========================
#         # 拓扑 A：基础 RC
#         # =========================
#         if topo == "basic":
#             nl = (
#                 f"A simple RC low-pass filter powered by a {V}V source. "
#                 f"It consists of a {R} resistor followed by a {C} capacitor."
#             )

#             spice = f"""V1 in 0 DC {V}
# R1 in out {R}
# C1 out 0 {C}
# .end"""

#         # =========================
#         # 拓扑 B：RC + 并联负载
#         # =========================
#         elif topo == "with_load":
#             RL = random.choice(["4.7k", "10k", "22k"])

#             nl = (
#                 f"An RC low-pass filter with a parallel load resistor, "
#                 f"powered by a {V}V source. "
#                 f"The circuit uses a {R} resistor, a {C} capacitor, "
#                 f"and a {RL} load resistor at the output."
#             )

#             spice = f"""V1 in 0 DC {V}
# R1 in out {R}
# C1 out 0 {C}
# RL out 0 {RL}
# .end"""

#         # =========================
#         # 拓扑 C：RC + 分压输出
#         # =========================
#         elif topo == "divider":
#             R2 = random.choice(["1k", "4.7k", "10k"])

#             nl = (
#                 f"An RC low-pass filter with a resistive voltage divider at the output, "
#                 f"powered by a {V}V supply. "
#                 f"The divider consists of {R} and {R2} resistors, "
#                 f"and the filter capacitor is {C}."
#             )

#             spice = f"""V1 in 0 DC {V}
# R1 in n1 {R}
# R2 n1 0 {R2}
# C1 n1 0 {C}
# .end"""

#         # =========================
#         # 拓扑 D：两级 RC
#         # =========================
#         elif topo == "two_stage":
#             R2 = random.choice(["4.7k", "10k", "22k"])
#             C2 = random.choice(["100n", "1u"])

#             nl = (
#                 f"A two-stage RC low-pass filter powered by a {V}V source. "
#                 f"The first stage uses a {R} resistor and a {C} capacitor, "
#                 f"followed by a second stage using a {R2} resistor and a {C2} capacitor."
#             )

#             spice = f"""V1 in 0 DC {V}
# R1 in n1 {R}
# C1 n1 0 {C}
# R2 n1 out {R2}
# C2 out 0 {C2}
# .end"""

#         samples.append((nl, spice))

#     return samples
# data_generator/rc.py
import random

def _choice(vals, rng):
    return rng.choice(vals)

def _kOhm(rng):
    return _choice(["1k", "2.2k", "4.7k", "10k", "22k", "47k", "100k"], rng)

def _cap(rng):
    return _choice(["10n", "47n", "100n", "220n", "470n", "1u", "2.2u", "10u"], rng)

def _volt(rng):
    return _choice(["3.3", "5", "9", "12"], rng)

def _mk_nodes(depth):
    # in -> n1 -> n2 -> ... -> out
    if depth == 1:
        return ["in", "out"]
    mids = [f"n{i}" for i in range(1, depth)]
    return ["in"] + mids + ["out"]

def _nl_header(ordering, depth, has_load, tap, ladder):
    # ordering: "LP" (R then C) or "HP" (C then R)
    ftype = "low-pass" if ordering == "LP" else "high-pass"
    stage_txt = "single-stage" if depth == 1 else f"{depth}-stage"
    parts = [f"A {stage_txt} RC {ftype} filter"]
    if ladder:
        parts.append("implemented as an RC ladder network")
    if tap != "out":
        parts.append(f"with the output taken at {tap}")
    if has_load:
        parts.append("and a resistive load at the output")
    return " ".join(parts) + "."

def _nl_params(V, ordering, depth, Rs, Cs, loadR, ladder):
    # Keep it structured & unambiguous (good for training)
    ftype = "low-pass" if ordering == "LP" else "high-pass"
    s = [f"It is powered by a {V}V DC source."]
    s.append(f"The filter type is {ftype}.")
    if ladder:
        s.append(f"The network has {depth} stage(s) connected in cascade.")
    else:
        s.append(f"The filter has {depth} stage(s).")

    # Mention elements by stage
    for i in range(depth):
        s.append(f"Stage {i+1} uses R{i+1}={Rs[i]} and C{i+1}={Cs[i]}.")
    if loadR is not None:
        s.append(f"The load resistor is RL={loadR}.")
    return " ".join(s)

def _spice_lp(nodes, Rs, Cs, loadR=None, tap_node="out"):
    # Low-pass: series R then shunt C to ground at each stage node
    lines = []
    lines.append(f"V1 in 0 DC {{V}}")  # placeholder V replaced later
    # stages
    for i in range(len(Rs)):
        n_left = nodes[i]
        n_right = nodes[i+1]
        lines.append(f"R{i+1} {n_left} {n_right} {Rs[i]}")
        # shunt capacitor at the stage node (right node)
        lines.append(f"C{i+1} {n_right} 0 {Cs[i]}")
    # load at tap node
    if loadR is not None:
        lines.append(f"RL {tap_node} 0 {loadR}")
    lines.append(".end")
    return lines

def _spice_hp(nodes, Rs, Cs, loadR=None, tap_node="out"):
    # High-pass: series C then shunt R to ground at each stage node
    lines = []
    lines.append(f"V1 in 0 DC {{V}}")
    for i in range(len(Rs)):
        n_left = nodes[i]
        n_right = nodes[i+1]
        lines.append(f"C{i+1} {n_left} {n_right} {Cs[i]}")
        # shunt resistor at the stage node (right node)
        lines.append(f"R{i+1} {n_right} 0 {Rs[i]}")
    if loadR is not None:
        lines.append(f"RL {tap_node} 0 {loadR}")
    lines.append(".end")
    return lines

def generate(n_samples, seed=42):
    """
    Returns list of (input_text, output_text).
    Produces 20+ topology families by combining:
      - ordering: LP/HP
      - depth: 1..3
      - ladder: True/False (textual variation + mild structural placement)
      - load: None / RL at tap node
      - tap: output taken at out / n1 / n2 (when available)
    """
    rng = random.Random(seed)
    samples = []

    for _ in range(n_samples):
        ordering = rng.choice(["LP", "HP"])         # low-pass vs high-pass
        depth = rng.choice([1, 2, 3])               # stages
        ladder = rng.choice([True, False])          # textual+struct flavor
        has_load = rng.choice([True, False])        # include RL sometimes

        V = _volt(rng)
        Rs = [_kOhm(rng) for _ in range(depth)]
        Cs = [_cap(rng) for _ in range(depth)]
        loadR = _kOhm(rng) if has_load else None

        nodes = _mk_nodes(depth)  # ["in", "out"] or ["in","n1","out"] or ["in","n1","n2","out"]

        # tap choices: take output at out or an intermediate node
        possible_taps = ["out"]
        if depth >= 2:
            possible_taps.append("n1")
        if depth >= 3:
            possible_taps.append("n2")
        tap_node = rng.choice(possible_taps)

        # NL
        nl = _nl_header(ordering, depth, has_load, tap_node, ladder) + " " + _nl_params(V, ordering, depth, Rs, Cs, loadR, ladder)

        # SPICE (structure depends on ordering & depth)
        if ordering == "LP":
            lines = _spice_lp(nodes, Rs, Cs, loadR=loadR, tap_node=tap_node)
        else:
            lines = _spice_hp(nodes, Rs, Cs, loadR=loadR, tap_node=tap_node)

        # Replace placeholder V
        lines[0] = lines[0].format(V=V)
        spice = "\n".join(lines)

        samples.append((nl, spice))

    return samples
