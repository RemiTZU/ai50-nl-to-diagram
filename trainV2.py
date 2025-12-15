import os
import csv
import torch
import numpy as np
from transformers import (
    T5Tokenizer, 
    T5ForConditionalGeneration, 
    Trainer, 
    TrainingArguments, 
    DataCollatorForSeq2Seq
)
from datasets import load_dataset
import wandb

# --- 1. Configuration Globale ---
# On définit le projet WandB ici ou via la variable d'environnement
os.environ["WANDB_PROJECT"] = "text-to-spice-asc"
os.environ["WANDB_LOG_MODEL"] = "end" # Sauvegarde le modèle sur WandB à la fin

MODEL_NAME = "t5-small"
MAX_INPUT_LENGTH = 128   # Description naturelle
MAX_TARGET_LENGTH = 1024 # Fichier ASC (souvent long)

# --- 2. Préparation des Données (Chargement & Split) ---
def load_and_process_data(file_path):
    # Chargement
    data = load_dataset(
        "csv",
        data_files=file_path,
        column_names=["input_text", "output_text"],
        delimiter=",",
        quoting=csv.QUOTE_ALL
    )
    
    # Découpage en 3 : Train (80%) / Validation (10%) / Test (10%)
    # D'abord on sépare Train et le reste
    train_testvalid = data["train"].train_test_split(test_size=0.2, seed=42)
    # Ensuite on sépare le reste en Test et Validation (50/50 du reste)
    test_valid = train_testvalid["test"].train_test_split(test_size=0.5, seed=42)
    
    # On reconstitue un DatasetDict propre
    dataset = {
        "train": train_testvalid["train"],
        "validation": test_valid["train"], # Le train du 2eme split devient validation
        "test": test_valid["test"]
    }
    
    return dataset

# Charger le dataset (remplacez par votre vrai fichier CSV)
# Si vous n'avez pas encore le fichier, commentez cette ligne pour tester
raw_datasets = load_and_process_data("results.csv") 

# --- 3. Tokenisation ---
tokenizer = T5Tokenizer.from_pretrained(MODEL_NAME)

def preprocess_function(examples):
    inputs = examples["input_text"]
    targets = examples["output_text"]
    
    model_inputs = tokenizer(inputs, max_length=MAX_INPUT_LENGTH, padding="max_length", truncation=True)
    
    with tokenizer.as_target_tokenizer():
        labels = tokenizer(targets, max_length=MAX_TARGET_LENGTH, padding="max_length", truncation=True)

    model_inputs["labels"] = labels["input_ids"]
    return model_inputs

# On applique la tokenisation sur les 3 parties
tokenized_datasets = {}
for split in ["train", "validation", "test"]:
    tokenized_datasets[split] = raw_datasets[split].map(preprocess_function, batched=True)

# --- 4. Fonction d'Initialisation du Modèle (CRUCIAL POUR SWEEPS) ---
# Le Trainer appellera cette fonction à chaque nouvelle expérience du sweep
def model_init():
    return T5ForConditionalGeneration.from_pretrained(MODEL_NAME)

# --- 5. Configuration de l'Entraînement ---
# Définition des arguments par défaut (ils seront écrasés par le Sweep si activé)
training_args = TrainingArguments(
    output_dir="./spice_model_checkpoints",
    eval_strategy="epoch",    # Évaluer à chaque fin d'époque (pour voir si ça progresse)
    save_strategy="epoch",          # Sauvegarder à chaque époque
    learning_rate=2e-5,             # Valeur par défaut
    per_device_train_batch_size=2,  # Petit batch car ASC est long
    per_device_eval_batch_size=2,
    num_train_epochs=5,             # Court par défaut pour tester
    weight_decay=0.01,
    save_total_limit=2,             # Ne garde que les 2 meilleurs checkpoints (évite de remplir le disque)
    load_best_model_at_end=True,    # À la fin, recharge le meilleur modèle trouvé selon la loss de validation
    metric_for_best_model="eval_loss",
    report_to="wandb",              # Connecte à WandB
    fp16=torch.cuda.is_available(), # Active l'accélération mixte si GPU dispo
    logging_steps=10,
)

# Data Collator
data_collator = DataCollatorForSeq2Seq(tokenizer)

# --- 6. Trainer ---
trainer = Trainer(
    model_init=model_init,          # On passe la fonction, pas le modèle instancié !
    args=training_args,
    train_dataset=tokenized_datasets["train"],
    eval_dataset=tokenized_datasets["validation"], # On utilise le set de validation ici
    tokenizer=tokenizer,
    data_collator=data_collator,
)

# --- 7. Lancement ---
if __name__ == "__main__":
    # Si on lance ce script directement, il fait un entraînement simple.
    # Pour le sweep, c'est WandB qui pilotera le script.
    print("Lancement de l'entraînement...")
    trainer.train()
    
    # Évaluation finale sur le Test Set (celui que le modèle n'a jamais vu)
    print("Évaluation finale sur le Test Set...")
    test_results = trainer.predict(tokenized_datasets["test"])
    print(test_results.metrics)
    
    # Sauvegarde finale
    trainer.save_model("./final_spice_model")