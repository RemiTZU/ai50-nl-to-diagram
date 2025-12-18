import csv
import torch
import numpy as np
import re
from transformers import T5Tokenizer, T5ForConditionalGeneration, Trainer, TrainingArguments, DataCollatorForSeq2Seq
from datasets import load_dataset
from torch.utils.data import Dataset

# ==============================================================================
# 1. LA FONCTION DE VALIDATION (Celle qu'on a créée ensemble)
# ==============================================================================
VALID_PREFIXES = {"R", "C", "L", "V", "I", "D", "Q", "M", "X"}

def semantic_validate(net):
    """ Retourne 1.0 si valide, 0.0 sinon. """
    try:
        lines = str(net).strip().split("\n")
        has_power_source = False
        has_ground = False

        for line in lines:
            line = line.strip()
            if line == "" or line.startswith("*") or line.startswith("."): continue

            parts = line.split()
            if not parts: continue
            
            prefix = parts[0][0].upper()
            if prefix not in VALID_PREFIXES: return 0.0
            if len(parts) < 3: return 0.0

            node1, node2 = parts[1], parts[2]
            if node1 == "0" or node2 == "0": has_ground = True
            if prefix in ["V", "I"]: has_power_source = True

        if has_ground and has_power_source:
            return 1.0 # Valide
        return 0.0 # Invalide
        
    except:
        return 0.0

# ==============================================================================
# 2. PRÉPARATION DES DONNÉES
# ==============================================================================

# Charger les données (on splitte en train et validation pour voir les progrès)
dataset = load_dataset(
    "csv",
    data_files="results.csv",
    column_names=["input_text", "output_text"],
    delimiter=",",
    quoting=csv.QUOTE_ALL,
    split='train' 
)

# On découpe : 90% pour entrainer, 10% pour tester ta sémantique
dataset = dataset.train_test_split(test_size=0.1)

model_name = "t5-small"
tokenizer = T5Tokenizer.from_pretrained(model_name)
model = T5ForConditionalGeneration.from_pretrained(model_name)

def preprocess_function(examples):
    inputs = examples["input_text"]
    targets = examples["output_text"]
    
    model_inputs = tokenizer(inputs, max_length=512, padding="max_length", truncation=True)
    labels = tokenizer(targets, max_length=200, padding="max_length", truncation=True)
    
    # Remplacer le padding du label par -100 pour que la loss l'ignore
    labels["input_ids"] = [
        [(l if l != tokenizer.pad_token_id else -100) for l in label] for label in labels["input_ids"]
    ]
    
    model_inputs["labels"] = labels["input_ids"]
    return model_inputs

tokenized_datasets = dataset.map(preprocess_function, batched=True)

# ==============================================================================
# 3. LA MÉTRIQUE PERSONNALISÉE (C'est ici que la magie opère)
# ==============================================================================

def compute_metrics(eval_preds):
    preds, labels = eval_preds
    
    # Si preds est un tuple (cas de certains modèles), on prend le premier élément
    if isinstance(preds, tuple):
        preds = preds[0]

    # Décoder les prédictions (Transformer les IDs en texte)
    # np.where permet de gérer le -100 qu'on a mis plus haut
    decoded_preds = tokenizer.batch_decode(preds, skip_special_tokens=True)
    
    # On décode aussi les labels pour comparaison (optionnel ici mais utile pour debug)
    labels = np.where(labels != -100, labels, tokenizer.pad_token_id)
    decoded_labels = tokenizer.batch_decode(labels, skip_special_tokens=True)

    # Calcul du score sémantique
    valid_count = 0
    total_count = len(decoded_preds)
    
    for netlist in decoded_preds:
        # On nettoie un peu le texte (sauts de ligne) comme dans test.py
        # Pour faire simple ici on passe direct au validateur
        # Astuce : T5 génère parfois tout sur une ligne, le validateur risque d'être sévère
        # mais c'est bien, ça forcera le modèle à être propre.
        
        # Petit nettoyage rapide pour aider le validateur
        netlist_clean = netlist.replace(".end", "\n.end") 
        if semantic_validate(netlist_clean) == 1.0:
            valid_count += 1
            
    semantic_score = valid_count / total_count

    return {
        "semantic_accuracy": semantic_score, # Ton score personnalisé
    }

# ==============================================================================
# 4. ENTRAÎNEMENT
# ==============================================================================

training_args = TrainingArguments(
    output_dir="./spice_model_v2",
    num_train_epochs=50,             # Augmenté un peu
    per_device_train_batch_size=4,   # Augmenté un peu si tu as de la VRAM
    per_device_eval_batch_size=4,
    learning_rate=5e-5,
    logging_dir='./logs',
    logging_steps=10,
    
    # --- CONFIGURATION IMPORTANTE ---
    evaluation_strategy="epoch",     # Evaluer à chaque fin d'époque
    save_strategy="epoch",           # Sauvegarder à chaque fin d'époque
    load_best_model_at_end=True,     # A la fin, garde le MEILLEUR modèle
    metric_for_best_model="semantic_accuracy", # Le critère c'est TA validation !
    greater_is_better=True,          # On veut que le score soit haut
    predict_with_generate=True,      # Indispensable pour que compute_metrics reçoive du texte généré
)

data_collator = DataCollatorForSeq2Seq(tokenizer, model=model)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=tokenized_datasets["train"],
    eval_dataset=tokenized_datasets["test"], # On a besoin d'un set de test pour évaluer
    tokenizer=tokenizer,
    data_collator=data_collator,
    compute_metrics=compute_metrics, # On injecte ta fonction ici
)

print("Démarrage de l'entraînement avec validation sémantique...")
trainer.train()

# Sauvegarde finale
model.save_pretrained("./spice_model_validated")
tokenizer.save_pretrained("./spice_model_validated")
print("Modèle sauvegardé dans ./spice_model_validated")