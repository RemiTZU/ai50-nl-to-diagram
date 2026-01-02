import torch
from transformers import T5Tokenizer, T5ForConditionalGeneration
import os
import re  # Nécessaire pour la validation sémantique et le nettoyage
import schemdraw
import schemdraw.elements as elm
import matplotlib.pyplot as pltq
# ==============================================================================
# 1. CONFIGURATION ET CHARGEMENT DU MODÈLE
# ==============================================================================

# On récupère le chemin absolu du dossier où se trouve ce script
script_dir = os.path.dirname(os.path.abspath(__file__))

# On construit le chemin vers le checkpoint
checkpoint_path = os.path.join(script_dir, "spice_model", "checkpoint-1309")

print(f"Chargement du modèle depuis {checkpoint_path}...")

# Charger le Tokenizer et le Modèle
try:
    tokenizer = T5Tokenizer.from_pretrained(checkpoint_path)
    model = T5ForConditionalGeneration.from_pretrained(checkpoint_path)
except OSError:
    print("Erreur: Le chemin est introuvable. Vérifie que le dossier './spice_model/checkpoint-1309' existe bien.")
    exit()

# Passer le modèle sur GPU s'il est disponible
device = "cuda" if torch.cuda.is_available() else "cpu"
model = model.to(device)

print(f"Modèle chargé avec succès sur {device} !\n")



# ==============================================================================
# 2. FONCTIONS DE GÉNÉRATION, NETTOYAGE ET VALIDATION
# ==============================================================================

def generate_spice(text_description):
    """
    Traduit une description textuelle en Netlist SPICE brute.
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

    # Décodage
    result = tokenizer.decode(outputs[0], skip_special_tokens=True)
    return result

def clean_netlist(netlist_text):
    """
    Nettoie la sortie du modèle pour assurer un format SPICE valide (multilignes).
    """
    text = netlist_text.strip()
    
    # 1. Force le saut de ligne avant les composants, MAIS intelligemment.
    # On cherche : Espace + [Lettre][Chiffre] + [Espace] + [Chiffre]
    # Cela garantit qu'on ne coupe pas un nom de modèle comme "D1N4148"
    # Le pattern (?=...) est un "lookahead" : il vérifie la présence sans "manger" le texte
    text = re.sub(r'\s(?=[RCLVIDQM][0-9]+\s+[0-9])', '\n', text)

    # 2. Cas spécifique pour les sources/composants qui n'auraient pas été captés
    # Si le regex précédent est trop strict, on s'assure que V, I, R en début de ligne sont propres
    # (Optionnel mais sécurisant)
    
    # 3. Force le saut de ligne avant la commande .end
    if ".end" in text:
        text = text.replace(".end", "\n.end")
        
    # 4. Supprime les lignes vides et espaces superflus
    text = re.sub(r'\n+', '\n', text)
    
    return text.strip()
# --- Validation Sémantique ---
VALID_PREFIXES = {"R", "C", "L", "V", "I", "D", "Q", "M", "X"}

def semantic_validate(net):
    """
    Vérifie la cohérence sémantique de la netlist sans lancer NGSpice.
    Retourne: (True/False, raison)
    """
    lines = str(net).strip().split("\n")
    has_power_source = False
    has_ground = False

    for line in lines:
        line = line.strip()
        # Ignorer les lignes vides ou les commentaires
        if line == "" or line.startswith("*"):
            continue

        parts = line.split()

        # Ignorer les commandes SPICE (.tran, .model, etc.) pour la validation basique
        if line.startswith("."):
            continue   

        # 1. Vérifier le préfixe du composant (R, C, V...)
        if not parts: continue 
        prefix = parts[0][0].upper()    

        if prefix not in VALID_PREFIXES:
            return False, f"Préfixe de composant invalide : {prefix} (Ligne: {line})"

        # 2. Vérifier le nombre de paramètres (Nom + Noeud1 + Noeud2 minimum)
        if len(parts) < 3:
            return False, f"Pas assez de paramètres : {line}"

        # 3. Vérifier que les noeuds sont des nombres
        node1, node2 = parts[1], parts[2]
        if not node1.isdigit() or not node2.isdigit():
            return False, f"Les noeuds doivent être numériques : {line}"

        # Vérification de la masse (Ground 0)
        if node1 == "0" or node2 == "0":
            has_ground = True

        # 4. Vérifier la présence d'une source (V ou I)
        if prefix == "V" or prefix == "I":
            has_power_source = True

        # 5. Vérifier le format de la valeur (ex: 10k, 1u)
        if prefix in {"R", "C", "L"}:
            if len(parts) < 4:
                return False, f"Valeur manquante pour le composant : {line}"
            
            value = parts[3]
            if not re.match(r"^\d+(\.\d+)?[a-zA-Z]*$", value):
                return False, f"Format de valeur invalide : {value}"

    # 6. Vérifications globales
    if not has_ground:
        return False, "Erreur : Aucun noeud de masse (0) trouvé."
    
    if not has_power_source:
        return False, "Erreur : Aucune source de tension ou de courant trouvée."

    return True, "Valide"

def draw_circuit(netlist_text):
    """
    Tente de dessiner un circuit fermé (boucle) de manière heuristique.
    Stratégie : Source (Haut) -> Composants (Droite) -> Dernier (Bas) -> Fil (Retour).
    """
    print("--- Dessin du circuit (Tentative de fermeture de boucle)... ---")
    
    # Parsing rapide pour séparer la source des autres composants
    lines = netlist_text.strip().split('\n')
    components = []
    source_line = None
    
    for line in lines:
        parts = line.split()
        if not parts or line.startswith('*') or line.startswith('.'): continue
        
        # On identifie la source principale (V...)
        if parts[0].upper().startswith('V'):
            source_line = parts
        else:
            components.append(parts)

    # Configuration du dessin
    with schemdraw.Drawing(show=False) as d:
        d.config(fontsize=12)
        
        # --- 1. DESSINER LA SOURCE (Montée) ---
        if source_line:
            name = source_line[0]
            val = source_line[3] if len(source_line) > 3 else ""
            source_elt = d.add(elm.SourceV(label=f"{name}\n{val}").up())
        else:
            source_elt = d.add(elm.Dot())
        # Dictionnaire de mapping : Lettre SPICE -> Élément Schemdraw
        # On définit ici "les règles" de dessin
# Dictionnaire de mapping : Lettre SPICE -> Élément Schemdraw
        mapping = {
            'R': elm.Resistor,
            'C': elm.Capacitor,
            'L': elm.Inductor,
            'V': elm.SourceV,      # Source de tension (ex-SourceDC)
            'I': elm.SourceI,      # Source de courant
            'D': elm.Diode,
            'Q': elm.BjtNpn,       # Transistor Bipolaire NPN (Par défaut)
            'M': elm.NFet,         # MOSFET N-Channel (Remplacement de Mosfet)
            'S': elm.SwitchDpst,   # Interrupteur simple (Remplacement de Switch)
            'X': elm.Dot           # Pour les sous-circuits inconnus
        }

   # --- 3. DESSINER LES COMPOSANTS (Droite -> Bas) ---
        # On parcourt tous les composants sauf le dernier
        for i, parts in enumerate(components):
            name = parts[0]
            type_char = name[0].upper()
            val = parts[3] if len(parts) > 3 else ""
            label = f"{name}\n{val}"
            
            element_class = mapping.get(type_char, elm.Dot)
            
            # Logique pour fermer le circuit :
            # Si c'est le DERNIER composant de la liste, on le dessine vers le BAS
            is_last = (i == len(components) - 1)
            
            if is_last:
                d += element_class(label=label).down()
            else:
                d += element_class(label=label).right()

        # --- 4. FERMER LA BOUCLE (Fil de retour) ---
        # On tire un fil depuis la position actuelle jusqu'au début de la source (source_elt.start)
        # .to() permet de tracer une ligne directe vers un point précis
        d += elm.Wire().to(source_elt.start)

        # Affichage
        try:
            d.draw()
        except Exception as e:
            print(f"Erreur graphique : {e}")

# ==============================================================================
# 3. ZONE DE TEST INTERACTIVE
# ==============================================================================

def run_test(prompt):
    print(f"Input: {prompt}")
    raw_netlist = generate_spice(prompt)
    
    # --- ETAPE DE NETTOYAGE ---
    netlist = clean_netlist(raw_netlist)
    
    print("--- SPICE ---")
    print(netlist)
    
    # Appel de la validation sur la version nettoyée
    is_valid, message = semantic_validate(netlist)
    if is_valid:
        print(f"✅ Validation : {message}")
        draw_circuit(netlist)
    else:
        print(f"❌ Validation : {message}")
    print("-" * 30)

# Exemple 1 : Circuit simple
run_test("A circuit with a 9V battery connected to a 1k resistor and a LED.")

# Exemple 2 : RLC
run_test("Series RLC circuit with 12V source, 100 ohm resistor, 1mH inductor and 10uF capacitor.")
# ==============================================================================
# 5. STRESS TESTS : CIRCUITS COMPLEXES & MULTI-ETAGES
# ==============================================================================
print("\n" + "!"*50)
print("  STRESS TESTS (Circuits Longs & Complexes)")
print("  Objectif : Voir si le modèle gère > 5 composants")
print("!"*50 + "\n")

# 1. Double Filtre RC (Cascade)
# Test : Capacité à enchaîner deux structures identiques (Etage 1 -> Etage 2)
# Attendu : V1, R1, C1, R2, C2 (5 composants)
run_test(
    "Double stage RC low-pass filter with 10V source. "
    "First stage: 1k resistor and 1uF capacitor. "
    "Second stage: 10k resistor and 100nF capacitor."
)

# 2. Amplificateur Transistor avec Polarisation (Voltage Divider Bias)
# Test : Gérer 4 résistances autour d'un transistor (Pont diviseur base + R collecteur + R émetteur)
# C'est un grand classique, mais lourd pour un petit modèle.
# Attendu : V1, Q1, R1, R2, R3, R4 (6 composants)
run_test(
    "NPN transistor amplifier with voltage divider bias. "
    "12V source, 10k and 2.2k resistors for base biasing, "
    "1k collector resistor, 470 ohm emitter resistor and 2N3904 transistor."
)

# 3. Circuit Multi-Branches (Parallèle Hétérogène)
# Test : Une branche résistive (LED) + Une branche capacitive (Timer/Lissage)
# Attendu : V1, R1, D1, R2, C1
run_test(
    "Circuit with a 9V battery powering two parallel branches. "
    "Branch 1 has a 220 ohm resistor and a D1N4148 diode. "
    "Branch 2 has a 4.7k resistor and a 100uF capacitor."
)

# 4. Filtre RLC avec Charge (Load)
# Test : RLC Série classique + une résistance de charge en parallèle sur le condensateur.
# Attendu : V1, R1, L1, C1, R2 (Charge)
run_test(
    "Series RLC circuit with 12V source, 50 ohm resistor, 10mH inductor and 10uF capacitor, "
    "with a 1k load resistor connected in parallel to the capacitor."
)

# 5. Filtre en Pi (CL-C)
# Test : Structure spécifique "Condensateur - Inductance - Condensateur"
# Attendu : V1, C1, L1, C2
run_test(
    "Pi filter circuit connected to a 5V DC source, consisting of a 10uF input capacitor, "
    "a 1mH series inductor, and a 10uF output capacitor."
)
# Mode interactif
while True:
    user_input = input("\nEntrez une description de circuit (ou 'q' pour quitter) : ")
    if user_input.lower() == 'q':
        break
    
    print("Génération en cours...")
    raw_netlist = generate_spice(user_input)
    
    # --- ETAPE DE NETTOYAGE ---
    netlist = clean_netlist(raw_netlist)
    
    print("\n--- Résultat SPICE ---")
    print(netlist)
    
    # Validation
    is_valid, message = semantic_validate(netlist)
    if is_valid:
        print(f"\n✅ STATUT : NETLIST VALIDE")
        draw_circuit(netlist)
    else:
        print(f"\n❌ STATUT : NETLIST INVALIDE ({message})")
    
    print("----------------------")