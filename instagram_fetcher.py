# instagram_fetcher.py
#
# Description:
# This module uses the instaloader library to efficiently fetch both captions
# and thumbnail URLs from Instagram posts in a single operation, replacing
# the slower Selenium-based approach.

import logging
import re
from typing import Tuple, Optional

import instaloader


def fetch_post_details(url: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Fetches both caption and thumbnail URL from an Instagram post using instaloader.

    Args:
        url: Instagram post URL

    Returns:
        Tuple of (caption, thumbnail_url) or (None, None) if failed
    """
    try:
        # Initialize instaloader instance
        L = instaloader.Instaloader()

        # Extract shortcode from URL
        # Handle both /p/ and /reel/ URLs
        shortcode_match = re.search(r'/(?:p|reel)/([A-Za-z0-9_-]+)', url)
        if not shortcode_match:
            logging.error(f"Could not extract shortcode from URL: {url}")
            return None, None

        shortcode = shortcode_match.group(1)

        # Get post object
        post = instaloader.Post.from_shortcode(L.context, shortcode)

        # Extract caption and thumbnail
        caption = post.caption if post.caption else None
        thumbnail_url = post.video_thumbnail_url if hasattr(post, 'video_thumbnail_url') and post.video_thumbnail_url else None

        # For regular posts (not videos/reels), try to get the first image URL
        if not thumbnail_url and hasattr(post, 'url'):
            thumbnail_url = post.url

        if caption:
            logging.info(f"Successfully fetched post details for {url}")
        else:
            logging.warning(f"No caption found for {url}")

        return caption, thumbnail_url

    except Exception as e:
        logging.error(f"Failed to fetch post details for {url}: {e}")
        return None, None
