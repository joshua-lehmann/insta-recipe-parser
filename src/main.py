# main.py
import logging
import time
import random

import config
from utils import (
    setup_logging, load_progress, save_progress, export_to_json,
    create_validation_benchmarks
)
from instagram_parser import extract_food_posts, load_saved_collections
from instagram_fetcher import fetch_post_details
from site_generator import generate_recipe_page, generate_index_page
from llm_processor import LLMProcessor, OllamaProcessor
from llm_processor_gemini import GeminiProcessor
from llm_processor_lmstudio import LMStudioProcessor


def get_llm_processor() -> LLMProcessor:
    """
    Factory function to select and instantiate the correct LLM processor
    based on the configuration.
    """
    provider = config.LLM_PROVIDER
    if provider == "google":
        logging.info("Using Google Gemini as the LLM provider.")
        return GeminiProcessor()
    elif provider == "local":
        logging.info("Using local Ollama as the LLM provider.")
        return OllamaProcessor()
    elif provider == "lmstudio":
        logging.info("Using LM Studio as the LLM provider.")
        return LMStudioProcessor()
    else:
        raise ValueError(
            f"Invalid LLM_PROVIDER in config: '{provider}'. "
            "Choose 'local', 'google', or 'lmstudio'."
        )


def main():
    setup_logging()
    logging.info("Starting Instagram recipe processing...")

    # --- Initialize LLM Processor ---
    try:
        llm_processor = get_llm_processor()
    except ValueError as e:
        logging.error(e)
        return

    progress_data = load_progress(config.PROGRESS_JSON_PATH)
    json_data = load_saved_collections(config.INSTAGRAM_JSON_PATH)
    if not json_data:
        logging.error("Failed to load Instagram data. Exiting.")
        return

    all_posts = extract_food_posts(json_data)
    if not all_posts:
        logging.warning(f"No posts found in the specified collection '{config.COLLECTION_NAME}'. Exiting.")
        return

    logging.info(f"Found {len(all_posts)} total posts from the '{config.COLLECTION_NAME}' collection.")

    for post in all_posts:
        if post['url'] not in progress_data:
            progress_data[post['url']] = {
                'url': post['url'],
                'caption': None,
                'thumbnail_url': None,
                'recipes': {}
            }

    models_to_run = config.LLM_MODELS.get(config.LLM_PROVIDER, [])
    if not models_to_run:
        logging.error(f"No models defined for '{config.LLM_PROVIDER}' in config.py.")
        return

    logging.debug(f"Will process recipes with the following models: {models_to_run}")

    total_posts = len(all_posts)
    batch_size = config.PROCESSING_BATCH_SIZE

    for batch_start in range(0, total_posts, batch_size):
        batch_end = min(batch_start + batch_size, total_posts)
        batch_of_posts = all_posts[batch_start:batch_end]

        logging.info(
            f"--- Processing batch {batch_start // batch_size + 1}: Posts {batch_start + 1}-{batch_end} of {total_posts} ---"
        )

        # First, fetch captions
        for i, post in enumerate(batch_of_posts):
            url = post['url']
            current_post_num = batch_start + i + 1
            if not progress_data[url].get('caption') or config.FORCE_REFETCH_CAPTIONS:
                logging.info(f"Fetching details for post {current_post_num}/{total_posts}: {url}")
                time.sleep(random.uniform(5, 10))
                caption, thumbnail = fetch_post_details(url)
                progress_data[url]['caption'] = caption
                progress_data[url]['thumbnail_url'] = thumbnail
                save_progress(progress_data, config.PROGRESS_JSON_PATH)

        # Then process with LLMs
        for model_name in models_to_run:
            logging.info(f"--- Applying model '{model_name}' to the current batch ---")

            for i, post in enumerate(batch_of_posts):
                url = post['url']
                current_post_num = batch_start + i + 1
                post_progress = progress_data[url]

                if model_name in post_progress.get('recipes', {}) and not config.FORCE_REPROCESS_LLM:
                    logging.debug(f"Skipping cached result for post {current_post_num} with {model_name}.")
                    continue

                caption = post_progress.get('caption')
                if not caption:
                    logging.warning(f"No caption for post {current_post_num}, cannot process with LLM.")
                    continue

                logging.info(f"Processing post {current_post_num}/{total_posts} with {model_name}...")

                max_retries = 3
                retry_delay = 5
                recipe_data, processing_time, cleaned_caption = None, None, None

                for attempt in range(max_retries):
                    # Use the single interface to process the caption
                    recipe_data, processing_time, cleaned_caption = llm_processor.process_caption(caption, url, model_name)
                    if recipe_data:
                        break
                    logging.warning(f"LLM processing failed for {model_name}. Retrying... (Attempt {attempt + 1})")
                    time.sleep(retry_delay)

                # Save the cleaned caption if it was generated and saving is enabled
                if cleaned_caption and config.SAVE_CLEANED_CAPTIONS and not post_progress.get('cleaned_caption'):
                    post_progress['cleaned_caption'] = cleaned_caption
                    logging.debug(f"Saved cleaned caption for post {current_post_num}")

                if recipe_data and processing_time is not None:
                    timestamp = time.strftime('%Y-%m-%d_%H-%M-%S')
                    new_result = {
                        'data': recipe_data.model_dump(),
                        'processing_time': processing_time,
                        'timestamp': timestamp
                    }

                    recipes = post_progress.setdefault('recipes', {})

                    if config.FORCE_REPROCESS_LLM and model_name in recipes:
                        if 'current' not in recipes[model_name]:
                            old_data = recipes[model_name]
                            recipes[model_name] = {
                                'current': old_data,
                                'history': []
                            }

                        current_result = recipes[model_name]['current']

                        if 'timestamp' not in current_result:
                            old_timestamp = time.strftime('%Y-%m-%d_%H-%M-%S',
                                                         time.localtime(time.time() - 3600))
                            current_result['timestamp'] = old_timestamp
                            logging.debug(f"Added missing timestamp {old_timestamp} to previous version")

                        recipes[model_name]['history'].insert(0, current_result)
                        recipes[model_name]['current'] = new_result

                        logging.info(f"Added new version for {model_name}. Total versions: {len(recipes[model_name]['history']) + 1}")
                    else:
                        if model_name not in recipes:
                            recipes[model_name] = {
                                'current': new_result,
                                'history': []
                            }
                        else:
                            recipes[model_name]['current'] = new_result

                    save_progress(progress_data, config.PROGRESS_JSON_PATH)
                else:
                    logging.error(f"Failed to structure recipe from {url} with {model_name} after {max_retries} attempts.")

        # Generate pages
        logging.info(f"--- Batch {batch_start // batch_size + 1} complete. Generating site pages. ---")
        for post in batch_of_posts:
            if progress_data[post['url']].get('recipes'):
                post_data = progress_data[post['url']]
                requested_version = 'current'

                generate_recipe_page(
                    recipes_by_model=post_data['recipes'],
                    output_dir=config.DOCS_DIR,
                    post_data=post_data,
                    requested_version=requested_version
                )

        all_processed = {k: v for k, v in progress_data.items() if v.get('recipes')}
        if all_processed:
            generate_index_page(all_processed, config.DOCS_DIR)

        batch_processed = {post['url']: progress_data[post['url']]
                          for post in batch_of_posts
                          if progress_data[post['url']].get('recipes')}
        if batch_processed:
            create_validation_benchmarks(batch_processed, config.VALIDATION_OUTPUT_DIR)

    logging.info("All post processing has been completed.")

    all_processed_posts = {k: v for k, v in progress_data.items() if v.get('recipes')}
    if all_processed_posts:
        export_to_json(list(all_processed_posts.values()), config.FINAL_JSON_PATH)
        create_validation_benchmarks(all_processed_posts, config.VALIDATION_OUTPUT_DIR)


if __name__ == "__main__":
    main()
