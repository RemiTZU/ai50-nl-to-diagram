"""
CircuitForge - Configuration settings
"""

import os

# Backend API Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "")

# App Configuration
APP_NAME = "CircuitForge"
APP_DESCRIPTION = "AI-Powered Electronic Circuit Generator"
APP_VERSION = "1.0.0"

# Generation settings
MAX_HISTORY_ITEMS = 50
SUPPORTED_EXPORT_FORMATS = ["PNG", "SVG", "PDF"]
