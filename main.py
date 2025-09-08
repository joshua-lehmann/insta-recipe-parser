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
from page_generator import create_telegraph_page


def main():
    """Main function to run the recipe processing pipeline."""
    setup_logging()
    logging.info("Starting Instagram recipe processing...")

    progress_data = load_progress(config.PROGRESS_JSON_PATH)
    logging.info(f"Loaded {len(progress_data)} posts from previous progress file.")

    # 1. Extract all post URLs from the specified collection
    all_posts = extract_food_posts(
        config.INSTAGRAM_JSON_PATH, config.COLLECTION_NAME
    )
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

        # 2. Fetch Caption (if not already cached)
        if progress_data[url].get('caption'):
            logging.info("--> Caption found in cache. Skipping fetch.")
            caption = progress_data[url]['caption']
        else:
            caption = fetch_caption_from_web(url)
            if caption:
                progress_data[url]['caption'] = caption
                save_progress(progress_data, config.PROGRESS_JSON_PATH)
                logging.info("--> Caption fetched and progress saved.")
            else:
                logging.warning(f"Skipping post due to failed caption fetch: {url}")
                continue

        # 3. Process with LLM (if not already processed)
        if progress_data[url].get('recipe'):
            logging.info("--> Recipe found in cache. Skipping LLM processing.")
        else:
            recipe_data = process_caption_with_llm(caption, url)
            if recipe_data:
                # Convert the Pydantic object to a dictionary before saving to JSON
                progress_data[url]['recipe'] = recipe_data.model_dump()
                save_progress(progress_data, config.PROGRESS_JSON_PATH)

                # 4. Generate Telegra.ph page (if recipe was successfully created)
                telegraph_url = create_telegraph_page(recipe_data)
                if telegraph_url:
                    # Update the original object for the final export list
                    recipe_data.telegraph_url = telegraph_url
                    # And also update the dictionary version in the progress file
                    progress_data[url]['recipe'] = recipe_data.model_dump()
                    save_progress(progress_data, config.PROGRESS_JSON_PATH)
            else:
                logging.warning(f"Failed to structure recipe from: {url}")
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
    else:
        logging.info("No recipes were successfully processed to export.")


if __name__ == "__main__":
    main()

