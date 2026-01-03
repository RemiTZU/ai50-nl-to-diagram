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
checkpoint_path = os.path.join(script_dir, "modelColab")

print(f"Chargement du modèle depuis {checkpoint_path}...")

# Charger le Tokenizer et le Modèle
try:
    tokenizer = T5Tokenizer.from_pretrained(checkpoint_path)
    model = T5ForConditionalGeneration.from_pretrained(checkpoint_path)
except OSError:
    print("Erreur: Le chemin est introuvable. Vérifie que le dossier './modelColab' existe bien.")
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
        max_length=512,
        num_beams=10, 
        early_stopping=True,
        repetition_penalty=2.5
    )

    # Décodage
    result = tokenizer.decode(outputs[0], skip_special_tokens=True)
    return result

def normalize_prompt(user_input):
    # 1. Nettoyage de base

    text = user_input.lower().replace(',', ' ').replace('-', ' ')
    
    # 2. Extraction Source
    source_val = "12" 
    source_match = re.search(r'(\d+(?:\.\d+)?)\s*v', text)
    if source_match:
        source_val = source_match.group(1)
        text = text.replace(source_match.group(0), ' ')

    components = []
    
    # Dictionnaire trié par longueur (IMPORTANT)
    type_roots = {
        'resistor': 'resistor', 'inductor': 'inductor', 'capacitor': 'capacitor',
        'diode': 'diode', 'led': 'diode', 'coil': 'inductor',
        'ohm': 'resistor', 'res': 'resistor', 'cap': 'capacitor', 'ind': 'inductor',
        'r': 'resistor', 'l': 'inductor', 'c': 'capacitor', 'd': 'diode',
        'h': 'inductor', 'f': 'capacitor' 
    }
    sorted_roots = sorted(type_roots.items(), key=lambda item: len(item[0]), reverse=True)

    ignore_words = ['battery', 'source', 'generator', 'connected', 'with', 'to', 'and', 'in', 'series', 'circuit', 'a', 'an', 'the']

    tokens = text.split()
    buffer_val = None 
    
    for token in tokens:
        # --- CORRECTIF DÉCIMALE ---
        # On enlève le point SEULEMENT s'il est à la fin du mot (ex: "10u.")
        # Cela préserve "4.7k" mais nettoie "100 ohm."
        token = token.rstrip('.') 
        
        if not token or token in ignore_words: continue

        # A. Est-ce une valeur ? (Regex supporte les décimales \.\d+)
        val_match = re.match(r'^(\d+(?:\.\d+)?)([munpk]+)?(h|f|ohm)?$', token)
        
        # B. Est-ce un type ?
        found_type = None
        if not (val_match and not val_match.group(3)): 
            for root, std_name in sorted_roots:
                if root in token:
                    if len(token) > 3 and len(root) == 1 and not val_match: continue 
                    found_type = std_name
                    break 

        # LOGIQUE D'ASSEMBLAGE
        if val_match:
            val_num = val_match.group(1)
            unit_prefix = val_match.group(2) if val_match.group(2) else ""
            unit_suffix = val_match.group(3)

            if unit_suffix:
                if 'h' in unit_suffix: components.append(f"a {val_num}{unit_prefix}mH inductor")
                elif 'f' in unit_suffix: components.append(f"a {val_num}{unit_prefix}F capacitor")
                elif 'ohm' in unit_suffix: components.append(f"a {val_num}{unit_prefix} resistor")
                buffer_val = None
            else:
                if unit_prefix in ['u', 'n', 'p']: 
                    components.append(f"a {val_num}{unit_prefix}F capacitor")
                    buffer_val = None
                elif unit_prefix == 'm': 
                     buffer_val = f"{val_num}m" 
                else: 
                    buffer_val = f"{val_num}{unit_prefix}"

        elif found_type:
            if found_type == 'diode':
                components.append("a diode")
                if buffer_val: 
                    components.append(f"a {buffer_val} resistor")
                    buffer_val = None
            
            elif buffer_val:
                val_s = buffer_val
                if found_type == 'inductor':
                    if not val_s.endswith('H'): val_s += "H"
                elif found_type == 'capacitor':
                     if not val_s.endswith('F'): val_s += "F"
                
                components.append(f"a {val_s} {found_type}")
                buffer_val = None

    if buffer_val:
        components.append(f"a {buffer_val} resistor")

    if not components: return "Error: No components detected"
    
    comp_str = ", ".join(components[:-1]) + " and " + components[-1] if len(components) > 1 else components[0]
    return f"A series circuit with {source_val}V source, {comp_str}."
import re

def clean_netlist(raw_output):
    # 1. Nettoyage tokens T5
    text = raw_output.replace("</s>", "").replace("<pad>", "").strip()

    # --- ÉTAPE 1 : SEGMENTATION INTELLIGENTE ---
    
    # OLD (Bug): text = re.sub(r'\s+(?=[RCLVIDQM]\d+)', '\n', text)
    
    # NEW (Fix): On utilise un "Negative Lookahead" (?!N)
    # On coupe devant [Lettre][Chiffre] SEULEMENT SI ce n'est pas suivi d'un 'N'
    # Ça détecte "D2" mais ignore "D1N4148"
    text = re.sub(r'\s+(?=[RCLVIDQM]\d+(?!N))', '\n', text)

    # Correction du collage .end (ex: "10u.end" -> "10u\n.end")
    text = re.sub(r'(\w)\.end', r'\1\n.end', text)
    
    # --- ÉTAPE 2 : FILTRAGE ET RECOLLAGE ---
    lines = text.split('\n')
    valid_lines = []

    for line in lines:
        line = line.strip()
        if not line: continue
        
        # Si c'est un bout de modèle orphelin (ex: "D1N4148") qui a sauté à la ligne
        if line.startswith("D1N") and valid_lines:
            # On le recolle à la ligne précédente
            valid_lines[-1] += " " + line
            continue

        # Suppression des hallucinations numériques (ex: ligne "12")
        if line[0].isdigit(): continue

        # Validation Standard SPICE
        first_char = line[0].upper()
        if first_char in ['R', 'L', 'C', 'V', 'I', 'D', 'Q', 'M', '.', '*']:
            # Petite correction d'unités à la volée
            line = line.replace("mmH", "mH").replace("uuF", "uF")
            valid_lines.append(line)

    return "\n".join(valid_lines)
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
def clean_and_repair_netlist(netlist_text):
    """
    Nettoie la netlist et CORRIGE les erreurs courantes du modèle (ex: L vs D).
    """
    # 1. Séparation propre des lignes
    # On insère un saut de ligne avant tout composant (R, C, L, D, Q, V, I...) 
    # s'il est collé à d'autres textes ou mal formaté.
    text = netlist_text.replace(".end", "\n.end")
    
    # Regex : Cherche un motif de début de composant (ex: R1, C12, V_in) précédé d'espace ou début de ligne
    # et force un retour à la ligne avant.
    # On protège les noms de modèles (ex: D1N4148) pour ne pas les couper.
    lines = []
    tokens = text.split()
    
    current_line = []
    # Pattern pour identifier le DÉBUT d'un nouveau composant (ex: R1, V1, C2...)
    # On exclut les valeurs comme "10k" ou les modèles "2N2222" (qui commencent par un chiffre)
    comp_start_pattern = re.compile(r'^[RCLVIDQM][0-9]+')

    for token in tokens:
        # Si le token ressemble à un début de composant (ex: R1) ET qu'on a déjà du contenu, on saute une ligne
        if comp_start_pattern.match(token) and current_line:
            # Petite heuristique : Si le dernier token était "DC" ou une valeur, c'est bien une nouvelle ligne
            lines.append(" ".join(current_line))
            current_line = [token]
        elif token.lower() == ".end":
            if current_line: lines.append(" ".join(current_line))
            current_line = []
            lines.append(".end")
        else:
            current_line.append(token)
            
    if current_line: lines.append(" ".join(current_line))
    
    # 2. Réparation des erreurs sémantiques (L vs D)
    final_lines = []
    for line in lines:
        parts = line.strip().split()
        if not parts: continue
        
        name = parts[0]
        prefix = name[0].upper()
        
        # --- FIX : Inductance (L) hallucinée au lieu de Diode (D) ---
        # Si c'est un 'L', mais que la valeur est un modèle (ex: 1N4148, LED, D1N...)
        if prefix == 'L' and len(parts) >= 4:
            val = parts[-1].upper() # La valeur est souvent à la fin
            # Si la valeur ressemble à une diode (commence par 1N, contient LED ou D1N)
            if "LED" in val or "1N" in val or "DIODE" in val:
                # On force le type à Diode
                new_name = "D" + name[1:] # L1 -> D1
                parts[0] = new_name
                line = " ".join(parts)
        
        final_lines.append(line)

    return "\n".join(final_lines)
# ==============================================================================
# 3. ZONE DE TEST INTERACTIVE
# ==============================================================================

def run_test(prompt):
    print(f"Input: {prompt}")
    prompt = normalize_prompt(prompt)
    print(f"Normalized Prompt: {prompt}")
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
run_test("A circuit with a 9V battery connected to a 330 ohm resistor and a LED.")

# Exemple 2 : RLC
run_test("12V 100 ohm resistor 1mH inductor and 10uF capacitor.")

# 1. Ton exemple : Langage naturel + Vocabulaire différent ("Battery", "LED")
run_test("A circuit with a 9V battery connected to a 330 ohm resistor and a LED.")

# 2. Ton exemple : RLC compact sans virgules
run_test("12V 100 ohm resistor 1mH inductor and 10uF capacitor.")

# 3. Le pire cauchemar : Fautes de frappe ("resistr", "inductr") + Unités manquantes
run_test("5v source 4.7k resistr 10m inductr and a capacitor 10u") 
# Note: "capacitOr 10u" est inversé, mon script le gère car "10u" force la créa d'un condo

# 4. Oubli complet des noms (Juste des valeurs et unités)
run_test("24V 1k 10mH 470u")

# 5. Format "Liste de courses" brouillon
run_test("batt 9v, led, led, 100r resistor")

# 6. Mélange majuscules/minuscules et abréviations
run_test("12V Source 1K RES 10u CAP 1m COIL")

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