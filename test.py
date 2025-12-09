import torch
from transformers import T5Tokenizer, T5ForConditionalGeneration

# ==============================================================================
# CONFIGURATION DU MODÈLE
# ==============================================================================

# Au lieu d'un chemin local (C:\...), on met l'identifiant Hugging Face
model_id = "Remiwe/nl_to_spice"

print(f"Téléchargement/Chargement du modèle '{model_id}' depuis Hugging Face...")

# 2. Charger le Tokenizer et le Modèle
try:
    # Cela va chercher le modèle sur le cloud automatiquement
    tokenizer = T5Tokenizer.from_pretrained(model_id)
    model = T5ForConditionalGeneration.from_pretrained(model_id)
except Exception as e:
    print(f"Erreur lors du chargement : {e}")
    print("Vérifiez votre connexion internet ou que le nom du modèle est correct.")
    exit()

# Passer le modèle sur GPU s'il est disponible pour aller plus vite
device = "cuda" if torch.cuda.is_available() else "cpu"
model = model.to(device)

print("Modèle chargé avec succès !\n")

# ==============================================================================
# FONCTION DE GÉNÉRATION
# ==============================================================================

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
    outputs = model.generate(
        inputs.input_ids,
        max_length=200,
        num_beams=5, 
        early_stopping=True
    )

    # Décodage (transformer les tokens en texte)
    result = tokenizer.decode(outputs[0], skip_special_tokens=True)
    return result

# ==============================================================================
# ZONE DE TEST
# ==============================================================================

# Exemple 1 : Un circuit simple
prompt1 = "A circuit with a 9V battery connected to a 1k resistor and a LED."
print(f"Input: {prompt1}")
print(f"Output SPICE:\n{generate_spice(prompt1)}")
print("-" * 30)

# Exemple 2 : Un circuit RLC série
prompt2 = "Series RLC circuit with 12V source, 100 ohm resistor, 1mH inductor and 10uF capacitor."
print(f"Input: {prompt2}")
print(f"Output SPICE:\n{generate_spice(prompt2)}")
print("-" * 30)

# Mode interactif
while True:
    user_input = input("\nEntrez une description de circuit (ou 'q' pour quitter) : ")
    if user_input.lower() == 'q':
        break
    print("Génération en cours...")
    netlist = generate_spice(user_input)
    print("\n--- Résultat SPICE ---")
    print(netlist)
    print("----------------------")