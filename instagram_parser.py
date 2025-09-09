# instagram_parser.py
#
# Description:
# This module contains functions for loading and parsing the official
# Instagram data export file (`saved_collections.json`).

import json
import logging
from typing import List, Dict, Any, Optional

import config

def load_saved_collections(path: str) -> Optional[Dict[str, Any]]:
    """Loads the saved collections JSON file from the given path."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logging.error(f"Input file not found at: {path}")
        return None
    except json.JSONDecodeError:
        logging.error(f"Error decoding JSON from {path}. The file might be corrupt.")
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred while reading {path}: {e}")
        return None

def extract_food_posts(data: Dict[str, Any]) -> List[Dict[str, str]]:
    """Extracts posts from the specified food collection based on the export file structure."""
    food_posts = []
    in_target_collection = False

    for item in data.get('saved_saved_collections', []):
        if item.get('title') == 'Collection':
            collection_name = item.get('string_map_data', {}).get('Name', {}).get('value')
            if collection_name == config.COLLECTION_NAME:
                in_target_collection = True
            elif in_target_collection:
                logging.info(f"Finished extracting from '{config.COLLECTION_NAME}'.")
                break
        elif in_target_collection:
            post_data = item.get('string_map_data', {})
            name_data = post_data.get('Name', {})
            url = name_data.get('href')

            if url and ("/reel/" in url or "/p/" in url):
                food_posts.append({
                    "url": url,
                    "username": name_data.get('value'),
                    "added_time": post_data.get('Added Time', {}).get('timestamp')
                })

    if not food_posts:
        logging.warning(f"Could not find collection '{config.COLLECTION_NAME}' or it contains no posts.")
    else:
        logging.info(f"Extracted {len(food_posts)} posts from the '{config.COLLECTION_NAME}' collection.")

    return food_posts
