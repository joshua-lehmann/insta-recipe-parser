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

# --- LLM Provider Settings ---
# Choose your LLM provider: "local" for Ollama or "google" for Gemini API.
LLM_PROVIDER = "google" # Options: "local", "google"

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
        "deepseek-r1:1.5b",
        "phi3:mini",
        "llama3"
    ],
    "google": [
        "gemini-2.5-flash",
        # "gemma-3-12b-it",
        "gemini-2.5-flash-lite"
    ]
}

# --- GitHub Pages Settings ---
DOCS_DIR = "docs"

# --- Force Rerun Settings ---
FORCE_REFETCH_CAPTIONS = False
FORCE_REPROCESS_LLM = False
FORCE_REGENERATE_HTML = True

