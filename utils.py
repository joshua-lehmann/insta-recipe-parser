# utils.py
#
# Description:
# This module contains utility functions used across the application,
# such as setting up logging, loading and saving progress data, and
# exporting final results.

import json
import logging
import os
import random
from typing import Dict, Any, List, Tuple


class NoiseFilter(logging.Filter):
    """A filter to suppress common, noisy log messages from libraries."""

    def __init__(self, patterns_to_suppress):
        super().__init__()
        self.patterns = patterns_to_suppress

    def filter(self, record):
        message = record.getMessage()
        return not any(p in message for p in self.patterns)


def setup_logging():
    """Configures the logging for the application."""
    log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
    numeric_level = getattr(logging, log_level, logging.INFO)

    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler("failed.log", mode='a', encoding='utf-8')],
        force=True
    )

    patterns_to_silence = [
        "HTTP Request:", "Websocket", '"client":', '"event":',
        'lmstudio-greeting', "JSON Query to graphql/query",
        "127.0.0.1:", "ws://", "thread_id", "Switching Protocols"
    ]
    noise_filter = NoiseFilter(patterns_to_silence)

    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        handler.addFilter(noise_filter)

    logging.getLogger('instaloader').setLevel(logging.WARNING)

    if not os.environ.get('INSTAGRAM_USERNAME') or not os.environ.get('INSTAGRAM_PASSWORD'):
        logging.info("Instagram credentials missing. For authentication, set environment variables.")


def load_progress(path: str) -> Dict[str, Any]:
    """Loads the progress data from a JSON file."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_progress(data: Dict[str, Any], path: str):
    """Saves the progress data to a JSON file."""
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logging.error(f"Failed to save progress to {path}: {e}")

# Aliasing save_progress as export_to_json for semantic clarity in main.py
export_to_json = save_progress


def get_recipes_with_min_models(progress_data: Dict[str, Any], min_models: int = 3) -> List[Tuple[str, Dict]]:
    """Get recipes that have been processed by at least min_models number of models."""
    eligible_recipes = []
    for url, data in progress_data.items():
        recipes = data.get('recipes', {})
        if len(recipes) >= min_models:
            eligible_recipes.append((url, data))
    return eligible_recipes


def select_random_recipes(eligible_recipes: List[Tuple[str, Dict]], count: int = 5) -> List[Tuple[str, Dict]]:
    """Select random recipes from the eligible list."""
    if len(eligible_recipes) < count:
        logging.warning(f"Only {len(eligible_recipes)} recipes available, but {count} requested. Using all available.")
        return eligible_recipes
    return random.sample(eligible_recipes, count)


def generate_recipe_markdown(url: str, data: Dict, recipe_index: int) -> str:
    """Generate markdown content for a single recipe optimized for LLM evaluation."""
    recipe_name = f"Recipe_{recipe_index:02d}"
    original_caption = data.get('caption', 'No caption available')

    markdown_content = f"""# {recipe_name}

## Original Instagram Post
**URL:** {url}

## Original Caption
```
{original_caption}
```
"""

    for model, recipe_info in data.get('recipes', {}).items():
        recipe_data = recipe_info.get('data', {})
        markdown_content += f"\n## Parsed by Model: `{model}`\n"
        markdown_content += f"**Title:** {recipe_data.get('title', 'N/A')}\n"
        markdown_content += f"**Servings:** {recipe_data.get('servings', 'N/A')}\n\n"
        markdown_content += "### Ingredients\n"
        for ingredient in recipe_data.get('ingredients', []):
            markdown_content += f"- {ingredient}\n"
        markdown_content += "\n### Instructions\n"
        for i, instruction in enumerate(recipe_data.get('instructions', []), 1):
            markdown_content += f"{i}. {instruction}\n"

    return markdown_content

def create_validation_benchmarks(progress_data: Dict[str, Any], count: int = 5, min_models: int = 3):
    """Creates markdown files for a random selection of recipes to be used for validation."""
    eligible_recipes = get_recipes_with_min_models(progress_data, min_models)
    selected_recipes = select_random_recipes(eligible_recipes, count)

    if not selected_recipes:
        logging.warning("No recipes were eligible for creating validation benchmarks.")
        return

    output_dir = "benchmarks"
    os.makedirs(output_dir, exist_ok=True)

    for i, (url, data) in enumerate(selected_recipes):
        markdown_content = generate_recipe_markdown(url, data, i + 1)
        file_path = os.path.join(output_dir, f"recipe_{i+1:02d}_comparison.md")
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            logging.info(f"Successfully created benchmark file: {file_path}")
        except Exception as e:
            logging.error(f"Failed to write benchmark file {file_path}: {e}")


def load_token(path: str) -> str | None:
    """Loads a token from a JSON file."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get("access_token")
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def save_token(token: str, path: str):
    """Saves a token to a JSON file."""
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({"access_token": token}, f, indent=4)
    except Exception as e:
        logging.error(f"Failed to save token to {path}: {e}")
