# caption_fetcher.py
#
# Description:
# This module is dedicated to fetching the caption from a public Instagram post.
# It uses Selenium to control a headless web browser, allowing it to
# bypass cookie and login popups that block simple HTTP requests.

import logging
from typing import Optional
import re
import time
import html

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException


def fetch_caption_from_web(url: str) -> Optional[str]:
    """
    Fetches the caption of a public Instagram post using Selenium. It now
    isolates and returns only the actual caption text, ignoring metadata.
    """
    post_url = url.replace("/reel/", "/p/")

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    chrome_options.add_argument("--lang=en-US,en;q=0.9")

    driver = None
    try:
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.get(post_url)

        wait = WebDriverWait(driver, 10)

        # 1. Handle Cookie Consent Popup
        try:
            decline_button_xpath = "//button[contains(text(), 'Decline optional cookies') or contains(text(), 'Alle optionalen Cookies ablehnen')]"
            cookie_decline_button = wait.until(EC.element_to_be_clickable((By.XPATH, decline_button_xpath)))
            cookie_decline_button.click()
            logging.info(f"Successfully declined cookies for {post_url}")
            time.sleep(2)
        except TimeoutException:
            logging.warning(f"Cookie consent popup not found for {post_url}. Proceeding.")

        # 2. Handle Login/Signup Popup
        try:
            close_button_xpath = "//*[local-name()='svg' and @aria-label='Close']/ancestor::div[@role='button']"
            login_close_button = wait.until(EC.element_to_be_clickable((By.XPATH, close_button_xpath)))
            login_close_button.click()
            logging.info(f"Successfully closed login popup for {post_url}")
            time.sleep(1)
        except TimeoutException:
            logging.warning(f"Login popup not found for {post_url}.")

        html_content = driver.page_source
        match = re.search(r'<meta property="og:description" content="([^"]*)"', html_content)

        if match:
            content = match.group(1)
            description = html.unescape(content)

            # The actual caption consistently starts after the date and ': "'
            parts = description.split(': "', 1)
            if len(parts) > 1:
                caption = parts[1]
                # Remove the trailing quote if it exists
                if caption.endswith('"'):
                    caption = caption[:-1]
                logging.info(f"Successfully extracted clean caption for {url}")
                return caption.strip()

            logging.warning(f"Could not isolate caption for {url}. The format might have changed.")
            # Return None instead of the full description with metadata
            return None

        logging.warning(f"Could not find og:description meta tag for {url}")
        return None

    except Exception as e:
        logging.error(f"An error occurred with Selenium for {post_url}: {e}")
        return None
    finally:
        if driver:
            driver.quit()

