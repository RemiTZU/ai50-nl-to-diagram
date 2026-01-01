# # circuit_generators/bjt_amp.py
# import random

# def generate(n_samples):
#     samples = []
#     for _ in range(n_samples):
#         Rc = random.choice(["2.2k", "4.7k"])
#         Re = random.choice(["470", "1k"])
#         Rb1 = random.choice(["47k", "100k"])
#         Rb2 = random.choice(["10k", "22k"])
#         V = random.choice(["9", "12"])

#         nl = (
#             f"A common-emitter BJT amplifier powered by {V}V. "
#             f"It uses a voltage divider bias and an emitter resistor."
#         )

#         spice = f"""VCC vcc 0 DC {V}
# R1 vcc base {Rb1}
# R2 base 0 {Rb2}
# Rc vcc collector {Rc}
# Re emitter 0 {Re}
# Q1 collector base emitter QNPN
# .end"""

#         samples.append((nl, spice))
#     return samples
# data_generator/bjt_amp.py
import random

def _choice(vals, rng):
    return rng.choice(vals)

def _ohm(rng):
    return _choice(
        ["220", "470", "1k", "2.2k", "4.7k", "10k", "22k", "47k", "100k"],
        rng
    )

def _kohm(rng):
    return _choice(
        ["2.2k", "4.7k", "10k", "22k", "47k", "100k", "220k"],
        rng
    )

def _cap(rng):
    return _choice(
        ["10n", "47n", "100n", "220n", "1u", "10u"],
        rng
    )

def _volt(rng):
    return _choice(["5", "9", "12"], rng)

def _nl_header(cfg):
    parts = ["A BJT amplifier circuit"]

    parts.append(
        "in a common-emitter configuration"
        if cfg["topology"] == "CE"
        else "in a common-collector configuration"
    )

    if cfg["bias"] == "divider":
        parts.append("using a voltage divider bias")
    else:
        parts.append("using a single-resistor base bias")

    if cfg["emitter_bypass"]:
        parts.append("with an emitter bypass capacitor")

    if cfg["input_coupling"]:
        parts.append("and an input coupling capacitor")

    if cfg["output_coupling"]:
        parts.append("and an output coupling capacitor")

    if cfg["feedback"]:
        parts.append("with resistive feedback from output to base")

    return " ".join(parts) + "."

def _nl_params(cfg):
    s = [f"The circuit is powered by a {cfg['V']}V DC supply."]
    s.append(f"The collector resistor is {cfg['Rc']} and the emitter resistor is {cfg['Re']}.")

    if cfg["bias"] == "divider":
        s.append(f"The base bias resistors are {cfg['Rb1']} and {cfg['Rb2']}.")
    else:
        s.append(f"The base bias resistor is {cfg['Rb']}.")

    if cfg["load"]:
        s.append(f"The load resistor is {cfg['Rl']}.")

    return " ".join(s)

def generate(n_samples, seed=123):
    rng = random.Random(seed)
    samples = []

    for _ in range(n_samples):
        # ====== 结构自由度 ======
        cfg = {
            "topology": rng.choice(["CE", "CC"]),          # 共射 / 射极跟随
            "bias": rng.choice(["divider", "single"]),    # 分压 / 单电阻
            "emitter_bypass": rng.choice([True, False]),
            "input_coupling": rng.choice([True, False]),
            "output_coupling": rng.choice([True, False]),
            "feedback": rng.choice([True, False]),
            "load": rng.choice([True, False]),
        }

        # ====== 参数 ======
        cfg["V"] = _volt(rng)
        cfg["Rc"] = _ohm(rng)
        cfg["Re"] = _ohm(rng)

        if cfg["bias"] == "divider":
            cfg["Rb1"] = _kohm(rng)
            cfg["Rb2"] = _kohm(rng)
        else:
            cfg["Rb"] = _kohm(rng)

        if cfg["load"]:
            cfg["Rl"] = _kohm(rng)

        # ====== NL ======
        nl = _nl_header(cfg) + " " + _nl_params(cfg)

        # ====== SPICE ======
        lines = []
        lines.append(f"VCC vcc 0 DC {cfg['V']}")

        # Bias network
        if cfg["bias"] == "divider":
            lines.append(f"R1 vcc base {cfg['Rb1']}")
            lines.append(f"R2 base 0 {cfg['Rb2']}")
        else:
            lines.append(f"Rb vcc base {cfg['Rb']}")

        # Input coupling
        if cfg["input_coupling"]:
            lines.append(f"CIN in base {_cap(rng)}")
        else:
            lines.append("Vin in base AC 1")

        # Transistor
        if cfg["topology"] == "CE":
            lines.append(f"Rc vcc collector {cfg['Rc']}")
            lines.append(f"Re emitter 0 {cfg['Re']}")
            lines.append("Q1 collector base emitter QNPN")
        else:  # CC (emitter follower)
            lines.append("Q1 vcc base emitter QNPN")
            lines.append(f"Re emitter 0 {cfg['Re']}")

        # Emitter bypass
        if cfg["emitter_bypass"]:
            lines.append(f"CE emitter 0 {_cap(rng)}")

        # Output coupling & load
        out_node = "collector" if cfg["topology"] == "CE" else "emitter"

        if cfg["output_coupling"]:
            lines.append(f"COUT {out_node} out {_cap(rng)}")
            if cfg["load"]:
                lines.append(f"RL out 0 {cfg['Rl']}")
        else:
            if cfg["load"]:
                lines.append(f"RL {out_node} 0 {cfg['Rl']}")

        # Feedback
        if cfg["feedback"]:
            lines.append(f"RF out base {_kohm(rng)}")

        lines.append(".end")

        spice = "\n".join(lines)
        samples.append((nl, spice))

    return samples
