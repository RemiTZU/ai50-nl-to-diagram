"""
CircuitForge - Circuit Generator
Loads T5 model and generates SPICE netlists from natural language.
"""

import torch
from transformers import T5Tokenizer, T5ForConditionalGeneration
from typing import Optional


class CircuitGenerator:

    def __init__(self, model_name: str = "Louis001001/t5-netlist-generator"):
        self.model_name = model_name
        self.model: Optional[T5ForConditionalGeneration] = None
        self.tokenizer: Optional[T5Tokenizer] = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self._loaded = False

    def load(self) -> bool:
        """Load model from Hugging Face (downloads on first run)."""
        if self._loaded:
            return True

        try:
            print(f"Loading model '{self.model_name}' on {self.device}...")
            self.tokenizer = T5Tokenizer.from_pretrained(self.model_name)
            self.model = T5ForConditionalGeneration.from_pretrained(self.model_name)
            self.model = self.model.to(self.device)
            self.model.eval()
            self._loaded = True
            print("Model loaded successfully!")
            return True
        except Exception as e:
            print(f"Error loading model: {e}")
            return False

    def generate(
        self,
        description: str,
        max_length: int = 256,
        num_beams: int = 5,
        repetition_penalty: float = 2.0,
        temperature: float = 0.7,
    ) -> str:
        """Generate SPICE netlist from natural language description."""
        if not self._loaded:
            if not self.load():
                raise RuntimeError("Failed to load model")

        inputs = self.tokenizer(
            description,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=512,
        ).to(self.device)

        with torch.no_grad():
            outputs = self.model.generate(
                inputs.input_ids,
                max_length=max_length,
                num_beams=num_beams,
                early_stopping=True,
                repetition_penalty=repetition_penalty,
                temperature=temperature,
                do_sample=False,
            )

        return self.tokenizer.decode(outputs[0], skip_special_tokens=True)

    @property
    def is_loaded(self) -> bool:
        return self._loaded


# Singleton instance
_generator: Optional[CircuitGenerator] = None


def get_generator() -> CircuitGenerator:
    """Get or create generator instance (singleton pattern)."""
    global _generator
    if _generator is None:
        _generator = CircuitGenerator()
    return _generator
