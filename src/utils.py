# utils.py
#
# Description:
# This module contains utility functions used across the application,
# such as setting up logging, loading and saving progress data, and
# exporting final results.

import json
import logging
import os
import time
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
        "127.0.0.1:", "ws://", "thread_id", "Switching Protocols",
        "AFC is enabled", "AFC remote call", "Both GOOGLE_API_KEY and GEMINI_API_KEY are set"
    ]
    noise_filter = NoiseFilter(patterns_to_silence)

    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        handler.addFilter(noise_filter)

    logging.getLogger('instaloader').setLevel(logging.WARNING)
    logging.getLogger('google.generativeai').setLevel(logging.WARNING)
    logging.getLogger('google.genai').setLevel(logging.WARNING)

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


def get_current_recipe_data(recipe_info: Dict[str, Any]) -> Dict[str, Any]:
    """Extracts the current recipe data from a potentially versioned structure."""
    if isinstance(recipe_info, dict) and 'current' in recipe_info:
        return recipe_info.get('current', {})
    # Fallback for legacy, non-versioned format
    return recipe_info


def generate_recipe_markdown(url: str, data: Dict) -> str:
    """Generate markdown content for a single recipe optimized for LLM evaluation."""
    # Get recipe title from first available model's data or use URL short code
    recipe_title = "Untitled Recipe"

    # Try to get a title from any model's data
    for model_name, recipe_info in data.get('recipes', {}).items():
        current_result = get_current_recipe_data(recipe_info)
        recipe_data = current_result.get('data', {})
        if title := recipe_data.get('title'):
            recipe_title = title
            break

    # If no title found, try to extract a short code from URL
    if recipe_title == "Untitled Recipe":
        # Extract Instagram shortcode from URL if possible
        try:
            short_code = url.rstrip('/').split('/')[-1]
            if short_code:
                recipe_title = f"Recipe_{short_code}"
        except:
            pass

    # Prefer cleaned caption if available; fallback to original caption
    cleaned_or_original_caption = data.get('cleaned_caption') or data.get('caption', 'No caption available')
    caption_heading = "Cleaned Caption" if data.get('cleaned_caption') else "Original Caption"

    markdown_content = f'''# {recipe_title}


## Original Instagram Post
**URL:** {url}

```
## {caption_heading}
{cleaned_or_original_caption}
```
'''
    for model, recipe_info in data.get('recipes', {}).items():
        current_result = get_current_recipe_data(recipe_info)
        recipe_data = current_result.get('data', {})

        markdown_content += f"\n## Parsed by Model: `{model}`\n\n"

        # --- Basic Info ---
        markdown_content += f"**Title:** {recipe_data.get('title', 'N/A')}\n"
        if servings := recipe_data.get('servings'):
            markdown_content += f"**Servings:** {servings}\n"
        if prep_time := recipe_data.get('prep_time'):
            markdown_content += f"**Prep Time:** {prep_time}\n"
        if cook_time := recipe_data.get('cook_time'):
            markdown_content += f"**Cook Time:** {cook_time}\n"

        # --- Categories ---
        if categories := recipe_data.get('categories'):
            markdown_content += f"**Categories:** {', '.join(categories)}\n"

        markdown_content += "\n"  # Add a newline for spacing

        # --- Ingredients ---
        markdown_content += "### Ingredients\n"
        ingredients_groups = recipe_data.get('ingredients', [])
        if not ingredients_groups:
            markdown_content += "- Not available\n"
        else:
            for group in ingredients_groups:
                if group_title := group.get('group_title'):
                    markdown_content += f"**{group_title}**\n"
                for ingredient in group.get('ingredients', []):
                    quantity = ingredient.get('quantity') or ""
                    name = ingredient.get('name') or "Unnamed Ingredient"
                    markdown_content += f"- {quantity} {name}".strip() + "\n"
        markdown_content += "\n"

        # --- Instructions ---
        markdown_content += "### Instructions\n"
        steps = recipe_data.get('steps', [])
        if not steps:
            markdown_content += "1. Not available\n"
        else:
            for i, step in enumerate(steps, 1):
                markdown_content += f"{i}. {step}\n"
        markdown_content += "\n"

        # --- Notes ---
        if notes := recipe_data.get('notes'):
            markdown_content += "### Notes\n"
            for note in notes:
                markdown_content += f"- {note}\n"
            markdown_content += "\n"

        # --- Nutrition ---
        if nutrition := recipe_data.get('nutrition'):
            markdown_content += "### Nutrition\n"
            has_nutrition = False
            if calories := nutrition.get('calories'):
                markdown_content += f"- **Calories:** {calories}\n"
                has_nutrition = True
            if protein := nutrition.get('protein'):
                markdown_content += f"- **Protein:** {protein}\n"
                has_nutrition = True
            if carbs := nutrition.get('carbs'):
                markdown_content += f"- **Carbs:** {carbs}\n"
                has_nutrition = True
            if fat := nutrition.get('fat'):
                markdown_content += f"- **Fat:** {fat}\n"
                has_nutrition = True
            if not has_nutrition:
                markdown_content += "- Not available\n"
            markdown_content += "\n"

    return markdown_content


def calculate_model_performance_stats(progress_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Calculate performance statistics for each model."""
    model_stats = {}

    for url, data in progress_data.items():
        recipes = data.get('recipes', {})
        for model_name, recipe_info in recipes.items():
            current_data = get_current_recipe_data(recipe_info)
            processing_time = current_data.get('processing_time')
            if processing_time is not None:
                if model_name not in model_stats:
                    model_stats[model_name] = {
                        'total_time': 0.0,
                        'count': 0,
                        'times': []
                    }
                model_stats[model_name]['total_time'] += processing_time
                model_stats[model_name]['count'] += 1
                model_stats[model_name]['times'].append(processing_time)

    # Calculate averages and other stats
    for model_name, stats in model_stats.items():
        if stats['count'] > 0:
            stats['avg_time'] = stats['total_time'] / stats['count']
            stats['min_time'] = min(stats['times'])
            stats['max_time'] = max(stats['times'])
        else:
            stats['avg_time'] = 0.0
            stats['min_time'] = 0.0
            stats['max_time'] = 0.0

    return model_stats


def update_validation_summary(progress_data: Dict[str, Any], output_dir: str):
    """Generate or update the summary.md file with model performance statistics."""
    model_stats = calculate_model_performance_stats(progress_data)

    if not model_stats:
        logging.warning("No model performance data available for summary generation.")
        return

    total_recipes = len([k for k, v in progress_data.items() if v.get('recipes')])

    summary_content = f'''# LLM Model Performance Summary

Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}

## Overview
- **Total Processed Recipes**: {total_recipes}
- **Models Evaluated**: {len(model_stats)}

## Model Performance Statistics

| Model | Recipes Processed | Avg Time (s) | Min Time (s) | Max Time (s) |
|-------|------------------|--------------|--------------|--------------|
'''

    for model_name, stats in sorted(model_stats.items()):
        summary_content += f"| {model_name} | {stats['count']} | {stats['avg_time']:.2f} | {stats['min_time']:.2f} | {stats['max_time']:.2f} |\n"

    summary_content += f'''
## Processing Efficiency

'''

    # Add efficiency rankings
    if model_stats:
        sorted_by_speed = sorted(model_stats.items(), key=lambda x: x[1]['avg_time'])
        summary_content += "### Speed Ranking (Fastest to Slowest)\n\n"
        for i, (model_name, stats) in enumerate(sorted_by_speed, 1):
            summary_content += f"{i}. **{model_name}** - {stats['avg_time']:.2f}s average\n"

    summary_content += '''
## Validation Guidelines

These benchmark files are optimized for evaluation by external powerful LLMs to score and compare model performance across different metrics including:

- Recipe structure completeness
- Ingredient parsing accuracy
- Step clarity and logical ordering
- Language quality (for German recipes)
- Data consistency and formatting
- Information extraction from Instagram captions

## Auto-Generation

This summary and benchmark files are automatically generated after each processing batch, providing real-time insights into model performance.
'''

    summary_path = os.path.join(output_dir, "summary.md")
    try:
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write(summary_content)
        logging.debug(f"Successfully updated validation summary: {summary_path}")
    except Exception as e:
        logging.error(f"Failed to write validation summary {summary_path}: {e}")


def create_validation_benchmarks(progress_data: Dict[str, Any], output_dir: str = "benchmarks", min_models: int = 2):
    """Creates markdown files for all recipes in the batch to be used for validation."""
    eligible_recipes = get_recipes_with_min_models(progress_data, min_models)
    selected_recipes = eligible_recipes

    if not selected_recipes:
        logging.warning("No recipes were eligible for creating validation benchmarks.")
        return

    # Create current version folder
    current_version = time.strftime('%Y-%m-%d_%H-%M-%S')
    version_output_dir = os.path.join(output_dir, current_version)
    os.makedirs(version_output_dir, exist_ok=True)

    # Get existing benchmark files to avoid regenerating existing ones
    existing_benchmarks = set()
    if os.path.exists(version_output_dir):
        existing_benchmarks = set(os.listdir(version_output_dir))

    for url, data in selected_recipes:
        # Extract short code from URL
        short_code = "unknown"
        try:
            short_code = url.rstrip('/').split('/')[-1]
        except:
            pass

        # Generate recipe title
        recipe_title = "untitled"

        # Try to get a title from any model's data
        for model_name, recipe_info in data.get('recipes', {}).items():
            current_result = get_current_recipe_data(recipe_info)
            recipe_data = current_result.get('data', {})
            if title := recipe_data.get('title'):
                recipe_title = title.lower().replace(' ', '_')
                break

        # Clean up the title to make it a valid filename
        recipe_title = ''.join(c if c.isalnum() or c in '_-' else '_' for c in recipe_title)
        recipe_title = recipe_title[:40]  # Limit length

        # Format: shortcode-recipe_title_comparison.md
        file_name = f"{short_code}-{recipe_title}_comparison.md"

        # Skip if benchmark already exists for this recipe in this version
        if file_name in existing_benchmarks:
            logging.debug(f"Skipping existing benchmark for {recipe_title}")
            continue

        markdown_content = generate_recipe_markdown(url, data)
        file_path = os.path.join(version_output_dir, file_name)

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            logging.debug(f"Successfully created benchmark file: {file_path}")
        except Exception as e:
            logging.error(f"Failed to write benchmark file {file_path}: {e}")

    # Update the validation summary in the version folder
    update_validation_summary(progress_data, version_output_dir)

    # Also create/update a main summary in the parent directory
    update_validation_summary(progress_data, output_dir)


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
