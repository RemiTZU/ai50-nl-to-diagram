"""
CircuitForge - Circuit Generator Module
Handles model loading and SPICE netlist generation from natural language.
"""

import torch
from transformers import T5Tokenizer, T5ForConditionalGeneration
from typing import Optional
import os


class CircuitGenerator:
    """Generates SPICE netlists from natural language descriptions."""

    def __init__(self, model_name: str = "Remiwe/T5_final"):
        """
        Initialize the circuit generator.

        Args:
            model_name: Hugging Face model name or local path
        """
        self.model_name = model_name
        self.model: Optional[T5ForConditionalGeneration] = None
        self.tokenizer: Optional[T5Tokenizer] = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self._loaded = False

    def load(self) -> bool:
        """
        Load the model and tokenizer.

        Returns:
            True if successful, False otherwise
        """
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
        max_length: int = 512,
        num_beams: int = 10,
        repetition_penalty: float = 2.5,
    ) -> str:
        """
        Generate a SPICE netlist from a text description.

        Args:
            description: Natural language circuit description
            max_length: Maximum output length (default 512 for complex circuits)
            num_beams: Number of beams for beam search (default 10 for better quality)
            repetition_penalty: Penalty for repeated tokens (default 2.5)

        Returns:
            Generated SPICE netlist string
        """
        if not self._loaded:
            if not self.load():
                raise RuntimeError("Failed to load model")

        # Tokenize input
        inputs = self.tokenizer(
            description,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=512,
        ).to(self.device)

        # Generate with improved parameters
        with torch.no_grad():
            outputs = self.model.generate(
                inputs.input_ids,
                max_length=max_length,
                num_beams=num_beams,
                early_stopping=True,
                repetition_penalty=repetition_penalty,
            )

        # Decode
        result = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        return result

    @property
    def is_loaded(self) -> bool:
        """Check if model is loaded."""
        return self._loaded


# Singleton instance for the app
_generator: Optional[CircuitGenerator] = None


def get_generator() -> CircuitGenerator:
    """Get or create the singleton generator instance."""
    global _generator
    if _generator is None:
        _generator = CircuitGenerator()
    return _generator
