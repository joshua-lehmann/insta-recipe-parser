# instagram_fetcher.py
#
# Description:
# This module uses the instaloader library to efficiently fetch both captions
# and thumbnail URLs from Instagram posts in a single operation.

import re
import logging
from typing import Tuple, Optional

import instaloader
import config

# Use a dedicated logger for Instagram-related operations
logger = logging.getLogger(__name__)

# Create a global instance of Instaloader for reuse
_instaloader_instance = None


def get_instaloader_instance() -> instaloader.Instaloader:
    """
    Returns a global Instaloader instance, handling login and session persistence.
    """
    global _instaloader_instance
    if _instaloader_instance:
        logging.debug("Reusing existing Instaloader instance")
        return _instaloader_instance

    logging.debug("Creating new Instaloader instance...")
    try:
        _instaloader_instance = instaloader.Instaloader(
            sleep=True,
            quiet=True,
            download_pictures=False,
            download_videos=False,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False
        )
        logging.debug("Instaloader instance created successfully")
    except Exception as e:
        logging.error(f"Failed to create Instaloader instance: {e}")
        return None

    username = getattr(config, 'INSTAGRAM_USERNAME', '')
    password = getattr(config, 'INSTAGRAM_PASSWORD', '')

    logging.debug(f"Checking Instagram credentials...")
    logging.debug(f"Username: {'Set' if username else 'Not set'}")
    logging.debug(f"Password: {'Set' if password else 'Not set'}")

    if not username:
        logging.warning("No Instagram username provided; continuing without authentication.")
        return _instaloader_instance

    def sanitize_filename(name):
        return re.sub(r'[^a-zA-Z0-9]', '_', name) if name else "instagram_session"

    session_file = f"{sanitize_filename(username)}"
    logging.debug(f"Session file will be: {session_file}")

    try:
        logging.debug(f"Looking for existing session file: {session_file}")
        _instaloader_instance.load_session_from_file(username, session_file)
        if _instaloader_instance.test_login():
            logging.info(f"✅ Valid session found for @{username}")
            return _instaloader_instance
        else:
            logging.warning("Session file is invalid; attempting a fresh login.")
    except FileNotFoundError:
        logging.debug("No existing session file found")
    except Exception as e:
        logging.warning(f"Could not load session: {e}")

    if not password:
        logging.error("No password provided; cannot log in.")
        return _instaloader_instance

    logging.info(f"🔐 Attempting login for username: {username}")

    try:
        _instaloader_instance.login(username, password)
    except instaloader.TwoFactorAuthRequiredException:
        logging.info("🔐 Two-factor authentication required")
        logging.info("You will be prompted to enter your 2FA code...")
        try:
            print("=" * 50)
            print("TWO-FACTOR AUTHENTICATION REQUIRED")
            print("=" * 50)
            two_factor_code = input("Enter the 2FA code from your authenticator app: ").strip()
            if not two_factor_code:
                logging.error("No 2FA code entered, login aborted.")
                return _instaloader_instance
            logging.debug(f"Attempting 2FA login with code...")
            _instaloader_instance.two_factor_login(two_factor_code)
        except Exception as tfa_error:
            logging.error(f"2FA login failed: {tfa_error}")
            return _instaloader_instance
    except instaloader.BadCredentialsException:
        logging.error("❌ Login failed: Invalid username or password")
        return _instaloader_instance
    except instaloader.ConnectionException as e:
        logging.error(f"❌ Connection error during login: {e}")
        return _instaloader_instance
    except Exception as e:
        logging.error(f"❌ Unexpected error during login: {e}")
        return _instaloader_instance

    logged_in_user = _instaloader_instance.test_login()
    if logged_in_user:
        logging.info(f"✅ Login successful as @{logged_in_user}")
        try:
            logging.debug(f"Saving session to: {session_file}")
            _instaloader_instance.save_session_to_file(session_file)
            logging.debug("Session saved successfully")
        except Exception as save_error:
            logging.error(f"Failed to save session: {save_error}")

    return _instaloader_instance


def fetch_post_details(url: str) -> Tuple[Optional[str], Optional[str]]:
    """Fetches both caption and thumbnail URL from an Instagram post."""
    logging.debug(f"Fetching post details from {url}")

    try:
        L = get_instaloader_instance()
        if not L:
            logging.error("Failed to get a valid Instaloader instance.")
            return None, None

        shortcode_match = re.search(r'/(?:p|reel|reels)/([A-Za-z0-9_-]+)', url)
        if not shortcode_match:
            logging.error(f"Could not extract shortcode from URL: {url}")
            return None, None
        shortcode = shortcode_match.group(1)
        logging.debug(f"Fetching post with shortcode: {shortcode}")

        post = instaloader.Post.from_shortcode(L.context, shortcode)

        caption = post.caption if post.caption else None
        # Use video thumbnail when available; otherwise fall back to video_url for videos or the regular URL.
        thumbnail_url = getattr(post, "video_thumbnail_url", None) or (post.video_url if post.is_video else post.url)

        if caption:
            caption_preview = (caption[:70] + '...').replace('\n', ' ')
            logging.debug(f"Caption preview: {caption_preview}")
        else:
            logger.warning(f"⚠️ No caption found for {url}")

        return caption, thumbnail_url

    except instaloader.InstaloaderException as e:
        if "401" in str(e) or "login" in str(e).lower():
            logging.error(f"Authentication error fetching {url}. Your session may be invalid.")
        elif "429" in str(e) or "rate" in str(e).lower():
            logging.error(f"Rate limit exceeded fetching {url}. Try increasing the delay in main.py.")
        else:
            logging.error(f"Instagram API error for {url}: {e}")
        return None, None
    except Exception as e:
        logger.error(f"An unexpected error occurred fetching post details for {url}: {e}")
        return None, None
