import torch
from transformers import T5Tokenizer, T5ForConditionalGeneration
import os
# 1. Chemin vers ton checkpoint spécifique (vu dans ton image)
# Assure-toi que le chemin est correct par rapport à où tu lances le script
# --- MODIFICATION ICI ---
# On récupère le chemin absolu du dossier où se trouve ce script (test.py)
script_dir = os.path.dirname(os.path.abspath(__file__))

# On construit le chemin vers le checkpoint en partant du dossier du script
checkpoint_path = os.path.join(script_dir, "spice_model", "checkpoint-1309")
# ------------------------

print(f"Chargement du modèle depuis {checkpoint_path}...")

# 2. Charger le Tokenizer et le Modèle
try:
    tokenizer = T5Tokenizer.from_pretrained(checkpoint_path)
    model = T5ForConditionalGeneration.from_pretrained(checkpoint_path)
except OSError:
    print("Erreur: Le chemin est introuvable. Vérifie que le dossier './spice_model/checkpoint-1309' existe bien.")
    exit()

# Passer le modèle sur GPU s'il est disponible pour aller plus vite
device = "cuda" if torch.cuda.is_available() else "cpu"
model = model.to(device)

print("Modèle chargé avec succès !\n")

def generate_spice(text_description):
    """
    Traduit une description textuelle en Netlist SPICE.
    """
    # Préparation de l'entrée
    inputs = tokenizer(
        text_description, 
        return_tensors="pt", 
        padding=True, 
        truncation=True, 
        max_length=512
    ).to(device)

    # Génération
    # num_beams=5 permet une recherche plus qualitative (Beam Search)
    # max_length=200 car les netlists peuvent être longues
    outputs = model.generate(
        inputs.input_ids,
        max_length=200,
        num_beams=5, 
        early_stopping=True
    )

    # Décodage (transformer les tokens en texte)
    result = tokenizer.decode(outputs[0], skip_special_tokens=True)
    return result

# --- ZONE DE TEST ---

# Exemple 1 : Un circuit simple (proche de ton dataset)
prompt1 = "A circuit with a 9V battery connected to a 1k resistor and a LED."
print(f"Input: {prompt1}")
print(f"Output SPICE:\n{generate_spice(prompt1)}")
print("-" * 30)

# Exemple 2 : Un circuit RLC série (Test de généralisation)
prompt2 = "Series RLC circuit with 12V source, 100 ohm resistor, 1mH inductor and 10uF capacitor."
print(f"Input: {prompt2}")
print(f"Output SPICE:\n{generate_spice(prompt2)}")
print("-" * 30)

# Mode interactif pour tester toi-même
while True:
    user_input = input("\nEntrez une description de circuit (ou 'q' pour quitter) : ")
    if user_input.lower() == 'q':
        break
    print("Génération en cours...")
    netlist = generate_spice(user_input)
    print("\n--- Résultat SPICE ---")
    print(netlist)
    print("----------------------")