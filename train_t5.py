import csv
import torch
from transformers import T5Tokenizer, T5ForConditionalGeneration, Trainer, TrainingArguments, DataCollatorForSeq2Seq
from datasets import load_dataset
import pandas as pd

# --- Charger les données ---
data = load_dataset(
    "csv",
    data_files="results.csv",
    column_names=["input_text", "output_text"],  # on force les noms
    delimiter=",",
    quoting=csv.QUOTE_ALL
)

print(data)

# --- Charger le modèle et le tokenizer ---
model_name = "t5-small"
tokenizer = T5Tokenizer.from_pretrained(model_name)
model = T5ForConditionalGeneration.from_pretrained(model_name)

# --- Tokenisation des données ---
train_texts = [d["input_text"] for d in data["train"]]
train_labels = [d["output_text"] for d in data["train"]]

# Retourne un dictionnaire avec 'input_ids', 'attention_mask'
inputs = tokenizer(train_texts, padding=True, truncation=True)
labels = tokenizer(train_labels, padding=True, truncation=True)

# --- Création du Dataset PyTorch compatible Trainer ---
from torch.utils.data import Dataset

class MyDataset(Dataset):
    def __init__(self, encodings, labels):
        self.encodings = encodings
        self.labels = labels

    def __len__(self):
        return len(self.labels["input_ids"])

    def __getitem__(self, idx):
        item = {key: torch.tensor(val[idx]) for key, val in self.encodings.items()}
        item["labels"] = torch.tensor(self.labels["input_ids"][idx])
        return item

train_dataset = MyDataset(inputs, labels)

# --- Data collator pour padding dynamique ---
data_collator = DataCollatorForSeq2Seq(tokenizer, model=model)

# --- Paramètres d'entraînement ---
training_args = TrainingArguments(
    output_dir="./spice_model",
    num_train_epochs=30,
    per_device_train_batch_size=2,
    learning_rate=5e-5,
    logging_dir='./logs',
    logging_steps=10,
    save_strategy="epoch",
)

# --- Initialisation du Trainer ---
trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=train_dataset,
    data_collator=data_collator,
)

# --- Lancer l'entraînement ---
trainer.train()

# --- Sauvegarder le modèle et le tokenizer ---
model.save_pretrained("./spice_model")
tokenizer.save_pretrained("./spice_model")
