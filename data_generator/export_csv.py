# circuit_generators/export_csv.py
import csv
from rc import generate as rc_gen
from cascaded import generate as cascaded_gen
from feedback import generate as feedback_gen
from bjt_amp import generate as bjt_gen
from mos_amp import generate as mos_gen
import random

rng = random.Random(42)

dataset = []
dataset += rc_gen(250)
dataset += cascaded_gen(400)
dataset += feedback_gen(350)
dataset += bjt_gen(300)
dataset += mos_gen(300)

rng.shuffle(dataset)

with open("results_augmented.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f, quoting=csv.QUOTE_ALL)
    writer.writerow(["input_text", "output_text"])
    for nl, spice in dataset:
        writer.writerow([nl, spice])

print(f"Generated {len(dataset)} samples → results_augmented.csv")
