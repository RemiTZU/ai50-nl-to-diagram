# # circuit_generators/feedback.py
# import random

# def generate(n_samples):
#     samples = []
#     for _ in range(n_samples):
#         Rf = random.choice(["47k", "100k"])
#         Rin = random.choice(["4.7k", "10k"])
#         C = random.choice(["100n", "1u"])
#         V = random.choice(["5", "12"])

#         nl = (
#             f"A resistive feedback RC circuit powered by {V}V. "
#             f"The output is fed back through a {Rf} resistor."
#         )

#         spice = f"""V1 in 0 DC {V}
# R1 in n1 {Rin}
# C1 n1 0 {C}
# Rf out in {Rf}
# .end"""

#         samples.append((nl, spice))
#     return samples
# data_generator/feedback.py
import random

def _choice(vals, rng):
    return rng.choice(vals)

def _kohm(rng):
    return _choice(["1k", "2.2k", "4.7k", "10k", "22k", "47k", "100k"], rng)

def _cap(rng):
    return _choice(["10n", "47n", "100n", "220n", "1u", "10u"], rng)

def _volt(rng):
    return _choice(["3.3", "5", "9", "12"], rng)

def generate(n_samples, seed=7):
    rng = random.Random(seed)
    samples = []

    for _ in range(n_samples):
        # ======================
        # 主体电路（被反馈）
        # ======================
        depth = rng.choice([1, 2])  # 单级 / 两级 RC
        ordering = rng.choice(["LP", "HP"])

        V = _volt(rng)

        # nodes: in -> n1 -> out (depth=1)
        # nodes: in -> n1 -> n2 -> out (depth=2)
        nodes = ["in"] + [f"n{i}" for i in range(1, depth+1)] + ["out"]

        # ======================
        # 反馈结构自由度
        # ======================
        fb_type = rng.choice(["R", "C", "RC"])     # 反馈类型
        fb_from = rng.choice(nodes[1:])            # 从哪里反馈
        fb_to = rng.choice(["in", "n1"])            # 反馈到哪里（不一定是输入）

        # 防止无意义的“自己接自己”
        if fb_from == fb_to:
            fb_to = "in"

        # ======================
        # NL 描述
        # ======================
        nl_parts = [
            "A feedback circuit based on an RC network",
            f"powered by a {V}V DC source."
        ]

        nl_parts.append(
            "The main path is a low-pass RC stage."
            if ordering == "LP"
            else "The main path is a high-pass RC stage."
        )

        if depth == 2:
            nl_parts.append("The circuit uses two cascaded RC stages.")

        fb_desc = {
            "R": "a resistive feedback path",
            "C": "a capacitive feedback path",
            "RC": "a resistive-capacitive feedback network"
        }
        nl_parts.append(
            f"The feedback is implemented using {fb_desc[fb_type]}, "
            f"from node {fb_from} to node {fb_to}."
        )

        nl = " ".join(nl_parts)

        # ======================
        # SPICE
        # ======================
        lines = []
        lines.append(f"V1 in 0 DC {V}")

        # 主路径
        for i in range(depth):
            n_left = nodes[i]
            n_right = nodes[i+1]

            R = _kohm(rng)
            C = _cap(rng)

            if ordering == "LP":
                lines.append(f"R{i+1} {n_left} {n_right} {R}")
                lines.append(f"C{i+1} {n_right} 0 {C}")
            else:
                lines.append(f"C{i+1} {n_left} {n_right} {C}")
                lines.append(f"R{i+1} {n_right} 0 {R}")

        # 反馈路径
        if fb_type == "R":
            lines.append(f"Rf {fb_from} {fb_to} {_kohm(rng)}")
        elif fb_type == "C":
            lines.append(f"Cf {fb_from} {fb_to} {_cap(rng)}")
        else:  # RC
            lines.append(f"Rf {fb_from} nf {_kohm(rng)}")
            lines.append(f"Cf nf {fb_to} {_cap(rng)}")

        lines.append(".end")

        spice = "\n".join(lines)
        samples.append((nl, spice))

    return samples
