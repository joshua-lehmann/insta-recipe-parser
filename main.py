# main.py
#
# Description:
# This is the main entry point for the Instagram Recipe Parser application.
# It orchestrates the entire process:
# 1. Loads configuration and previous progress.
# 2. Parses the Instagram data export to find recipe posts.
# 3. For each post, it fetches the caption (using Selenium to handle popups).
# 4. Sends the caption to a local LLM for structuring into a recipe format.
# 5. Generates a public Telegra.ph page for easy importing.
# 6. Saves progress incrementally and exports the final structured data.

import logging

import config
from utils import (
    setup_logging, load_progress, save_progress, export_to_json
)
from instagram_parser import extract_food_posts
from caption_fetcher import fetch_caption_from_web
from llm_processor import process_caption_with_llm
from site_generator import generate_recipe_page, generate_index_page, extract_thumbnail_from_instagram


def main():
    """Main function to run the recipe processing pipeline."""
    setup_logging()
    logging.info("Starting Instagram recipe processing...")

    progress_data = load_progress(config.PROGRESS_JSON_PATH)
    logging.info(f"Loaded {len(progress_data)} posts from previous progress file.")

    # 1. Load the Instagram data and extract all post URLs from the specified collection
    from instagram_parser import load_saved_collections

    json_data = load_saved_collections(config.INSTAGRAM_JSON_PATH)
    if not json_data:
        logging.error("Failed to load Instagram data. Exiting.")
        return

    all_posts = extract_food_posts(json_data)
    if not all_posts:
        logging.warning("No posts found in the specified collection. Exiting.")
        return

    logging.info(f"Extracted {len(all_posts)} posts from the '{config.COLLECTION_NAME}' collection.")

    # Initialize progress data for new posts
    for post in all_posts:
        if post['url'] not in progress_data:
            progress_data[post['url']] = {'url': post['url'], 'caption': None, 'recipe': None}

    logging.info(f"Found {len(progress_data)} total posts. Checking against progress file...")

    total_posts = len(all_posts)
    for i, post in enumerate(all_posts):
        url = post['url']
        logging.info(f"Processing post {i + 1}/{total_posts}: {url}")

        # 2. Fetch Caption (if not already cached or force refetch is enabled)
        if progress_data[url].get('caption') and not config.FORCE_REFETCH_CAPTIONS:
            logging.info("--> Caption found in cache. Skipping fetch.")
            caption = progress_data[url]['caption']
        else:
            if config.FORCE_REFETCH_CAPTIONS and progress_data[url].get('caption'):
                logging.info("--> Force refetch enabled. Refetching caption despite cache.")
            caption = fetch_caption_from_web(url)
            if caption:
                progress_data[url]['caption'] = caption
                save_progress(progress_data, config.PROGRESS_JSON_PATH)
                logging.info("--> Caption fetched and progress saved.")
            else:
                logging.warning(f"Skipping post due to failed caption fetch: {url}")
                continue

        # 3. Process with LLM (if not already processed or force reprocess is enabled)
        recipe_data = None
        if progress_data[url].get('recipe') and not config.FORCE_REPROCESS_LLM:
            logging.info("--> Recipe found in cache. Skipping LLM processing.")
            # Load the recipe data for potential HTML regeneration
            from models import Recipe
            recipe_data = Recipe(**progress_data[url]['recipe'])
        else:
            if config.FORCE_REPROCESS_LLM and progress_data[url].get('recipe'):
                logging.info("--> Force reprocess enabled. Reprocessing with LLM despite cache.")
            recipe_data = process_caption_with_llm(caption, url)
            if not recipe_data:
                logging.warning(f"Failed to structure recipe from: {url}")
                continue

        # At this point, recipe_data should contain either cached or newly processed recipe
        if recipe_data:
            # Add original caption (always set this, even when loading from cache)
            recipe_data.original_caption = caption

            # Handle thumbnail extraction based on force flag or missing thumbnail
            should_extract_thumbnail = (
                config.FORCE_REEXTRACT_THUMBNAILS or 
                not getattr(recipe_data, 'thumbnail_url', None) or
                config.FORCE_REPROCESS_LLM  # If we reprocessed with LLM, also re-extract thumbnail
            )

            if should_extract_thumbnail:
                # Try to extract thumbnail (non-blocking)
                try:
                    if config.FORCE_REEXTRACT_THUMBNAILS:
                        logging.info(f"Force re-extract enabled. Re-extracting thumbnail for {url}")
                    thumbnail_url = extract_thumbnail_from_instagram(url)
                    if thumbnail_url:
                        recipe_data.thumbnail_url = thumbnail_url
                        logging.info(f"Extracted thumbnail for {url}")
                    else:
                        logging.info(f"No thumbnail found for {url}")
                except Exception as e:
                    logging.warning(f"Failed to extract thumbnail for {url}: {e}")

            # Handle HTML generation based on force flag or new recipe
            should_generate_html = (
                config.FORCE_REGENERATE_HTML or
                config.FORCE_REPROCESS_LLM or
                not progress_data[url].get('recipe')  # New recipe
            )

            if should_generate_html:
                if config.FORCE_REGENERATE_HTML:
                    logging.info(f"Force regenerate HTML enabled. Regenerating page for {url}")
                # 4. Generate HTML page 
                html_filename = generate_recipe_page(recipe_data, "docs")
                if html_filename:
                    # Update the original object for the final export list
                    recipe_data.local_file = html_filename

            # Convert the Pydantic object to a dictionary before saving to JSON
            progress_data[url]['recipe'] = recipe_data.model_dump()
            save_progress(progress_data, config.PROGRESS_JSON_PATH)

            # 5. Update index page with current recipes (if any HTML was generated or forced)
            if should_generate_html:
                current_recipes = [
                    item['recipe'] for item in progress_data.values()
                    if 'recipe' in item and item.get('recipe') is not None
                ]
                if current_recipes:
                    from models import Recipe
                    recipe_objects = [Recipe(**recipe_dict) for recipe_dict in current_recipes]
                    generate_index_page(recipe_objects, "docs")
                    logging.info(f"Updated index.html with {len(recipe_objects)} recipes")
        else:
            logging.warning(f"No recipe data available for: {url}")
            continue

    logging.info("All posts have been processed.")

    # 5. Final export of all successfully structured recipes
    recipes_to_export = [
        item['recipe'] for item in progress_data.values()
        if 'recipe' in item and item.get('recipe') is not None
    ]

    if recipes_to_export:
        export_to_json(recipes_to_export, config.FINAL_JSON_PATH)
        logging.info(f"Successfully exported {len(recipes_to_export)} recipes to {config.FINAL_JSON_PATH}")

        # Final index page generation (in case no new recipes were processed this run or if forced)
        from models import Recipe
        recipe_objects = [Recipe(**recipe_dict) for recipe_dict in recipes_to_export]
        if config.FORCE_REGENERATE_HTML:
            logging.info("Force regenerate HTML enabled. Regenerating final index page.")
        generate_index_page(recipe_objects, "docs")
        logging.info("Final index.html generation completed")
    else:
        logging.info("No recipes were successfully processed to export.")


if __name__ == "__main__":
    main()

