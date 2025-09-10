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
    setup_logging()
    logging.info("Starting Instagram recipe processing...")

    progress_data = load_progress(config.PROGRESS_JSON_PATH)
    json_data = load_saved_collections(config.INSTAGRAM_JSON_PATH)
    if not json_data:
        logging.error("Failed to load Instagram data. Exiting.")
        return

    all_posts = extract_food_posts(json_data)
    if not all_posts:
        logging.warning("No posts found in the specified collection. Exiting.")
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
                recipe_data, processing_time = None, None
                # Always clean the caption first
                cleaned_caption = None
                if caption:
                    # Import the preprocessing function directly to use it here
                    from llm_processor_lmstudio import preprocess_caption
                    cleaned_caption = preprocess_caption(caption)
                    if config.SAVE_CLEANED_CAPTIONS and not post_progress.get('cleaned_caption'):
                        post_progress['cleaned_caption'] = cleaned_caption
                        logging.debug(f"Saved cleaned caption for post {current_post_num}")

                # Use the cleaned caption for processing
                processing_caption = cleaned_caption if cleaned_caption else caption

                for attempt in range(max_retries):
                    recipe_data, processing_time, _ = process_caption_with_llm(processing_caption, url, model_name)
                    if recipe_data:
                        break
                    logging.warning(f"LLM processing failed for {model_name}. Retrying... (Attempt {attempt + 1})")
                    time.sleep(retry_delay)

                if recipe_data and processing_time is not None:
                    timestamp = time.strftime('%Y-%m-%d_%H-%M-%S')
                    new_result = {
                        'data': recipe_data.model_dump(),
                        'processing_time': processing_time,
                        'timestamp': timestamp
                    }

                    recipes = post_progress.setdefault('recipes', {})

                    if config.FORCE_REPROCESS_LLM and model_name in recipes:
                        # Move current to history and set new as current
                        if 'current' not in recipes[model_name]:
                            # Convert old format to new versioned format
                            old_data = recipes[model_name]
                            recipes[model_name] = {
                                'current': old_data,
                                'history': []
                            }

                        # Move current to history
                        current_result = recipes[model_name]['current']

                        # Make sure the current result has a timestamp (could be missing in older data)
                        if 'timestamp' not in current_result:
                            old_timestamp = time.strftime('%Y-%m-%d_%H-%M-%S', 
                                                         time.localtime(time.time() - 3600))  # 1 hour ago
                            current_result['timestamp'] = old_timestamp
                            logging.debug(f"Added missing timestamp {old_timestamp} to previous version")

                        recipes[model_name]['history'].insert(0, current_result)
                        recipes[model_name]['current'] = new_result

                        logging.info(f"Added new version for {model_name}. Total versions: {len(recipes[model_name]['history']) + 1}")
                    else:
                        # Either not forcing reprocess or first time processing
                        if model_name not in recipes:
                            recipes[model_name] = {
                                'current': new_result,
                                'history': []
                            }
                        else:
                            # Update current without creating history
                            recipes[model_name]['current'] = new_result

                    # Save progress after each model completes
                    save_progress(progress_data, config.PROGRESS_JSON_PATH)
                else:
                    logging.error(f"Failed to structure recipe from {url} with {model_name} after {max_retries} attempts.")

        # Generate pages
        logging.info(f"--- Batch {batch_start // batch_size + 1} complete. Generating site pages. ---")
        for post in batch_of_posts:
            if progress_data[post['url']].get('recipes'):
                post_data = progress_data[post['url']]
                # Get URL version parameter if any
                requested_version = 'current'  # Default to current version

                generate_recipe_page(
                    recipes_by_model=post_data['recipes'],
                    output_dir=config.DOCS_DIR,
                    post_data=post_data,
                    requested_version=requested_version
                )

        all_processed = {k: v for k, v in progress_data.items() if v.get('recipes')}
        if all_processed:
            generate_index_page(all_processed, config.DOCS_DIR)

        # Generate validation benchmarks for the current batch
        batch_processed = {post['url']: progress_data[post['url']] 
                          for post in batch_of_posts 
                          if progress_data[post['url']].get('recipes')}
        if batch_processed:
            create_validation_benchmarks(batch_processed, config.VALIDATION_OUTPUT_DIR, count=config.PROCESSING_BATCH_SIZE)

    logging.info("All post processing has been completed.")

    all_processed_posts = {k: v for k, v in progress_data.items() if v.get('recipes')}
    if all_processed_posts:
        export_to_json(list(all_processed_posts.values()), config.FINAL_JSON_PATH)
        create_validation_benchmarks(all_processed_posts, config.VALIDATION_OUTPUT_DIR, count=config.PROCESSING_BATCH_SIZE)


if __name__ == "__main__":
    main()
