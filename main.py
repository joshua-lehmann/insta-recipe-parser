# main.py
#
# Description:
# This is the main entry point for the Instagram Recipe Parser application.
# It orchestrates the entire process, dynamically choosing between local (Ollama)
# and cloud (Google Gemini) LLM providers based on the configuration.

import logging
import time
import random

import config
from utils import (
    setup_logging, load_progress, save_progress, export_to_json,
    create_validation_benchmarks
)
from instagram_parser import extract_food_posts
from instagram_fetcher import fetch_post_details
from site_generator import generate_recipe_page, generate_index_page

# --- Dynamic LLM Processor Import ---
if config.LLM_PROVIDER == "google":
    from llm_processor_gemini import process_caption_with_gemini as process_caption_with_llm
    logging.info("Using Google Gemini as the LLM provider.")
elif config.LLM_PROVIDER == "local":
    from llm_processor import process_caption_with_llm
    logging.info("Using local Ollama as the LLM provider.")
elif config.LLM_PROVIDER == "lmstudio":
    from llm_processor_lmstudio import process_caption_with_llm
    logging.info("Using LM Studio as the LLM provider.")
else:
    raise ValueError(f"Invalid LLM_PROVIDER in config: '{config.LLM_PROVIDER}'. Choose 'local', 'google', or 'lmstudio'.")

def main():
    """Main function to run the recipe processing pipeline."""
    setup_logging()

    logging.info("Starting Instagram recipe processing...")

    # Check for Instagram credentials before starting
    if not hasattr(config, 'INSTAGRAM_USERNAME') or not config.INSTAGRAM_USERNAME:
        logging.warning("No Instagram username configured in environment variables.")
        # Give user a chance to abort
        try:
            input("Press Enter to continue without authentication (or Ctrl+C to abort)...")
        except KeyboardInterrupt:
            logging.info("Process aborted by user")
            return
    elif not hasattr(config, 'INSTAGRAM_PASSWORD') or not config.INSTAGRAM_PASSWORD:
        logging.warning("Instagram username is set but password is missing.")

    progress_data = load_progress(config.PROGRESS_JSON_PATH)
    logging.debug(f"Loaded {len(progress_data)} posts from previous progress file.")

    from instagram_parser import load_saved_collections
    json_data = load_saved_collections(config.INSTAGRAM_JSON_PATH)
    if not json_data:
        logging.error("Failed to load Instagram data. Exiting.")
        return

    all_posts = extract_food_posts(json_data)
    if not all_posts:
        logging.warning("No posts found in the specified collection. Exiting.")
        return

    logging.info(f"Extracted {len(all_posts)} total posts from the '{config.COLLECTION_NAME}' collection.")

    for post in all_posts:
        if post['url'] not in progress_data:
            progress_data[post['url']] = {'url': post['url'], 'caption': None, 'thumbnail_url': None, 'recipes': {}}

    models_to_run = config.LLM_MODELS.get(config.LLM_PROVIDER, [])
    if not models_to_run:
        logging.error(f"No models defined for the '{config.LLM_PROVIDER}' provider in config.py.")
        return
    logging.debug(f"Will process recipes with the following models: {models_to_run}")

    total_posts = len(all_posts)
    for i, post in enumerate(all_posts):
        url = post['url']
        logging.info(f"Processing post {i + 1}/{total_posts}: {url}")

        post_progress = progress_data[url]

        # 1. Fetch Caption and Thumbnail
        if post_progress.get('caption') and not config.FORCE_REFETCH_CAPTIONS:
            logging.debug("--> Caption and Thumbnail found in cache. Skipping fetch.")
            caption = post_progress['caption']
        else:
            sleep_duration = random.uniform(10, 15)
            logging.debug(f"Waiting for {sleep_duration:.1f} seconds before fetching Instagram post...")
            time.sleep(sleep_duration)

            caption, thumbnail_url = fetch_post_details(url)
            if caption:
                post_progress['caption'] = caption
                post_progress['thumbnail_url'] = thumbnail_url
                save_progress(progress_data, config.PROGRESS_JSON_PATH)
            else:
                logging.warning(f"Skipping post due to failed details fetch: {url}")
                continue

        if not caption:
            logging.warning(f"No caption available for {url}, skipping LLM processing.")
            continue

        # 2. Process with each configured LLM for the selected provider
        new_recipe_generated = False
        for model_name in models_to_run:
            logging.debug(f"--- Processing with model: {model_name} ---")

            post_progress.setdefault('recipes', {})

            if model_name in post_progress['recipes'] and not config.FORCE_REPROCESS_LLM:
                logging.debug(f"--> Recipe from {model_name} found in cache. Skipping.")
                continue

            max_retries = 3
            retry_delay = 5
            recipe_data, processing_time = None, None
            for attempt in range(max_retries):
                recipe_data, processing_time = process_caption_with_llm(caption, url, model_name)
                if recipe_data:
                    break
                logging.warning(f"LLM processing failed for {model_name}. Retrying... (Attempt {attempt + 1})")
                time.sleep(retry_delay)

            if recipe_data and processing_time is not None:
                post_progress['recipes'][model_name] = {
                    'data': recipe_data.model_dump(),
                    'processing_time': processing_time
                }
                new_recipe_generated = True
            else:
                logging.error(f"Failed to structure recipe from {url} with {model_name} after {max_retries} attempts.")

        save_progress(progress_data, config.PROGRESS_JSON_PATH)

        # 3. Generate HTML page and update index if needed
        should_generate_html = config.FORCE_REGENERATE_HTML or new_recipe_generated
        if should_generate_html and post_progress.get('recipes'):
            logging.debug(f"Generating HTML page for {url}")
            generate_recipe_page(
                recipes_by_model=post_progress['recipes'],
                output_dir=config.DOCS_DIR,
                post_data=post_progress
            )

            logging.debug("Updating index.html with current progress...")
            all_processed_posts = {k: v for k, v in progress_data.items() if v.get('recipes')}
            if all_processed_posts:
                generate_index_page(all_processed_posts, config.DOCS_DIR)
        else:
            logging.debug("No new recipes generated and not forcing HTML regen. Skipping page generation.")

    logging.info("All posts have been processed.")

    # 4. Final export and final index page generation
    all_processed_posts = {k: v for k, v in progress_data.items() if v.get('recipes')}
    if all_processed_posts:
        export_to_json(list(all_processed_posts.values()), config.FINAL_JSON_PATH)
        logging.info(
            f"Successfully exported full data for {len(all_processed_posts)} recipes to {config.FINAL_JSON_PATH}")

        logging.info("Generating final index.html...")
        generate_index_page(all_processed_posts, config.DOCS_DIR)
        logging.info("Final index.html generation completed.")

        # Create validation benchmarks
        logging.info("Creating validation benchmarks for LLM model comparison...")
        create_validation_benchmarks(all_processed_posts)

    else:
        logging.info("No recipes were successfully processed to export.")


if __name__ == "__main__":
    main()
