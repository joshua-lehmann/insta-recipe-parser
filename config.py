# config.py
#
# Description:
# This file contains all the configuration settings for the application.
# By keeping them in one place, it's easy to adjust paths, model names,
# and other parameters without changing the core logic of the application.

# --- File Paths ---
# The path to your Instagram data export file.
INSTAGRAM_JSON_PATH = "saved_collections.json"

# The path to the file where incremental progress is saved.
PROGRESS_JSON_PATH = "processing_progress.json"

# The path for the final, clean JSON output file.
FINAL_JSON_PATH = "samsung_food_recipes.json"

# --- Instagram Settings ---
# The exact name of the collection you want to process.
COLLECTION_NAME = "Food"


# --- LLM Settings ---
# The name of the model you want to use in Ollama.
# Recommended: "llama3" for best results in structuring data.
# Faster alternative for CPU: "phi3:mini"
LLM_MODEL = "gemma3:4b"

# --- GitHub Pages Settings ---
# Directory where HTML files will be generated for GitHub Pages
DOCS_DIR = "docs"

# --- Force Rerun Settings ---
# Set these flags to True to force regeneration of specific stages
# even if cached data exists in the progress file

# Force refetch captions from Instagram (useful when scraping logic changes)
FORCE_REFETCH_CAPTIONS = False

# Force reprocess captions with LLM (useful when model or prompt changes)
FORCE_REPROCESS_LLM = False

# Force re-extract thumbnails (useful when thumbnail extraction logic changes) 
FORCE_REEXTRACT_THUMBNAILS = True

# Force regenerate HTML pages (useful when template or styling changes)
FORCE_REGENERATE_HTML = True

