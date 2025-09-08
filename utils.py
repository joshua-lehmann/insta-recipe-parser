# utils.py
#
# Description:
# This module contains utility functions used across the application,
# such as setting up logging, loading and saving progress data, and
# exporting final results.

import json
import logging
from typing import Dict, Any

def setup_logging():
    """Configures the logging for the application."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),  # Log to console
            logging.FileHandler("failed.log", mode='a', encoding='utf-8') # Log to file
        ]
    )

def load_progress(path: str) -> Dict[str, Any]:
    """Loads the progress data from a JSON file."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        logging.warning(f"Could not decode JSON from {path}. Starting fresh.")
        return {}

def save_progress(data: Dict[str, Any], path: str):
    """Saves the progress data to a JSON file."""
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logging.error(f"Failed to save progress to {path}: {e}")

def export_to_json(data: list, path: str):
    """Exports the final list of recipes to a JSON file."""
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logging.error(f"Failed to export final JSON to {path}: {e}")

