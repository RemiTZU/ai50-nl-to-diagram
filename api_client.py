"""
CircuitForge - API Client for backend communication
This module handles all communication with the Python backend.
"""

import requests
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum
import time
from config import API_BASE_URL, API_KEY


class GenerationStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class GenerationResult:
    """Represents a circuit generation result"""

    id: str
    prompt: str
    status: GenerationStatus
    image_url: Optional[str] = None
    image_data: Optional[bytes] = None
    error_message: Optional[str] = None
    created_at: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class CircuitForgeAPI:
    """API client for CircuitForge backend"""

    def __init__(self, base_url: str = API_BASE_URL, api_key: str = API_KEY):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.session = requests.Session()
        if api_key:
            self.session.headers.update({"Authorization": f"Bearer {api_key}"})

    def generate_circuit(
        self, prompt: str, options: Optional[Dict[str, Any]] = None
    ) -> GenerationResult:
        """
        Send a prompt to generate a circuit.

        Args:
            prompt: The text description of the circuit to generate
            options: Optional generation parameters

        Returns:
            GenerationResult with the generation status and data
        """
        # TODO: Connect to actual backend
        # For now, return a mock response for UI development

        # Simulated API call structure:
        # try:
        #     response = self.session.post(
        #         f"{self.base_url}/api/generate",
        #         json={"prompt": prompt, "options": options or {}}
        #     )
        #     response.raise_for_status()
        #     data = response.json()
        #     return GenerationResult(
        #         id=data["id"],
        #         prompt=prompt,
        #         status=GenerationStatus(data["status"]),
        #         image_url=data.get("image_url"),
        #         created_at=data.get("created_at"),
        #         metadata=data.get("metadata")
        #     )
        # except requests.RequestException as e:
        #     return GenerationResult(
        #         id="error",
        #         prompt=prompt,
        #         status=GenerationStatus.ERROR,
        #         error_message=str(e)
        #     )

        # Mock response for development
        mock_id = f"gen_{int(time.time())}"
        return GenerationResult(
            id=mock_id,
            prompt=prompt,
            status=GenerationStatus.COMPLETED,
            image_url=None,
            created_at=time.strftime("%Y-%m-%d %H:%M:%S"),
            metadata={"mock": True},
        )

    def get_generation(self, generation_id: str) -> Optional[GenerationResult]:
        """
        Retrieve a specific generation by ID.

        Args:
            generation_id: The unique ID of the generation

        Returns:
            GenerationResult or None if not found
        """
        # TODO: Connect to actual backend
        # try:
        #     response = self.session.get(f"{self.base_url}/api/generations/{generation_id}")
        #     response.raise_for_status()
        #     data = response.json()
        #     return GenerationResult(
        #         id=data["id"],
        #         prompt=data["prompt"],
        #         status=GenerationStatus(data["status"]),
        #         image_url=data.get("image_url"),
        #         error_message=data.get("error_message"),
        #         created_at=data.get("created_at"),
        #         metadata=data.get("metadata")
        #     )
        # except requests.RequestException:
        #     return None
        return None

    def get_history(self, limit: int = 20, offset: int = 0) -> list[GenerationResult]:
        """
        Retrieve generation history.

        Args:
            limit: Maximum number of results to return
            offset: Number of results to skip

        Returns:
            List of GenerationResult objects
        """
        # TODO: Connect to actual backend
        # try:
        #     response = self.session.get(
        #         f"{self.base_url}/api/generations",
        #         params={"limit": limit, "offset": offset}
        #     )
        #     response.raise_for_status()
        #     data = response.json()
        #     return [
        #         GenerationResult(
        #             id=item["id"],
        #             prompt=item["prompt"],
        #             status=GenerationStatus(item["status"]),
        #             image_url=item.get("image_url"),
        #             error_message=item.get("error_message"),
        #             created_at=item.get("created_at"),
        #             metadata=item.get("metadata")
        #         )
        #         for item in data.get("generations", [])
        #     ]
        # except requests.RequestException:
        #     return []
        return []

    def delete_generation(self, generation_id: str) -> bool:
        """
        Delete a generation from history.

        Args:
            generation_id: The unique ID of the generation to delete

        Returns:
            True if deleted successfully, False otherwise
        """
        # TODO: Connect to actual backend
        # try:
        #     response = self.session.delete(f"{self.base_url}/api/generations/{generation_id}")
        #     return response.status_code == 200
        # except requests.RequestException:
        #     return False
        return True

    def health_check(self) -> bool:
        """
        Check if the backend is available.

        Returns:
            True if backend is healthy, False otherwise
        """
        # TODO: Connect to actual backend
        # try:
        #     response = self.session.get(f"{self.base_url}/health")
        #     return response.status_code == 200
        # except requests.RequestException:
        #     return False
        return False  # Return False to show "backend not connected" state


# Global API client instance
api_client = CircuitForgeAPI()
