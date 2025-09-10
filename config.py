# config.py
#
# Description:
# This file contains all the configuration settings for the application.
# By keeping them in one place, it's easy to adjust paths, model names,
# and other parameters without changing the core logic of the application.

import os

# --- File Paths ---
INSTAGRAM_JSON_PATH = "saved_collections.json"
PROGRESS_JSON_PATH = "processing_progress.json"
FINAL_JSON_PATH = "samsung_food_recipes.json"

# --- Instagram Settings ---
COLLECTION_NAME = "Food"
# Instagram login credentials
# Set these directly or preferably via environment variables for security
# How to set environment variables:
# Windows: set INSTAGRAM_USERNAME=your_username
# macOS/Linux: export INSTAGRAM_USERNAME=your_username
INSTAGRAM_USERNAME = os.environ.get("INSTAGRAM_USERNAME", "_josh_99_")
INSTAGRAM_PASSWORD = os.environ.get("INSTAGRAM_PASSWORD", "")  # Not needed if session is saved

# --- LLM Provider Settings ---
# Choose your LLM provider: "local", "google", or "lmstudio".
LLM_PROVIDER = "lmstudio"  # Options: "local", "google", "lmstudio"

# --- Google Gemini API Settings ---
# IMPORTANT: It's recommended to set your Google API key as an environment
# variable for security. The script will use the environment variable
# `GOOGLE_API_KEY` if it exists, otherwise it will use the value below.
# How to set an environment variable:
# macOS/Linux: export GOOGLE_API_KEY="your_api_key_here"
# Windows: set GOOGLE_API_KEY="your_api_key_here"
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")

# --- LLM Model Settings ---
# Define the models to use for each provider. The script will use the
# list corresponding to the selected LLM_PROVIDER.
LLM_MODELS = {
    "local": [
        "phi3:mini",
        "llama3"
    ],
    "google": [
        "gemini-1.5-flash-latest",
    ],
    "lmstudio": [
        "google/gemma-3-4b",
        "google/gemma-3n-e4b",
        "phi-4-mini-instruct",
        "phi-3-mini-4k-instruct",
        "microsoft/phi-4-mini-reasoning",
    ]
}

# --- GitHub Pages Settings ---
DOCS_DIR = "docs"

# --- Force Rerun Settings ---
FORCE_REFETCH_CAPTIONS = False
FORCE_REPROCESS_LLM = True
FORCE_REGENERATE_HTML = True
