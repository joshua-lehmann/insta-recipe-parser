# caption_fetcher.py
#
# Description:
# This module is dedicated to fetching the caption from a public Instagram post.
# It now uses Selenium to control a headless web browser, allowing it to
# bypass cookie and login popups that block simple HTTP requests.

import logging
from typing import Optional
import re
import time

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
    Fetches the caption of a public Instagram post using Selenium to bypass
    cookie and login popups that block simple HTTP requests.
    """
    post_url = url.replace("/reel/", "/p/")

    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run browser in the background
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    chrome_options.add_argument("--lang=en-US,en;q=0.9")  # Set language to ensure button text is predictable

    driver = None
    try:
        # Use webdriver-manager to automatically handle chromedriver installation
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)

        driver.get(post_url)

        wait = WebDriverWait(driver, 10)

        # 1. Handle Cookie Consent Popup
        try:
            # This XPath finds a button whose text is either the English or German version for declining cookies.
            decline_button_xpath = "//button[contains(text(), 'Decline optional cookies') or contains(text(), 'Alle optionalen Cookies ablehnen')]"
            cookie_decline_button = wait.until(EC.element_to_be_clickable((By.XPATH, decline_button_xpath)))
            cookie_decline_button.click()
            logging.info(f"Successfully declined cookies for {post_url}")
            time.sleep(2)  # Pause to allow the next modal to appear
        except TimeoutException:
            logging.warning(f"Cookie consent popup not found for {post_url}. Proceeding anyway.")

        # 2. Handle Login/Signup Popup
        try:
            # The close button is an 'x' SVG icon within a div that has a role of 'button'
            close_button_xpath = "//*[local-name()='svg' and @aria-label='Close']/ancestor::div[@role='button']"
            login_close_button = wait.until(EC.element_to_be_clickable((By.XPATH, close_button_xpath)))
            login_close_button.click()
            logging.info(f"Successfully closed login popup for {post_url}")
            time.sleep(1)  # Pause for page to settle
        except TimeoutException:
            logging.warning(f"Login popup not found for {post_url}. It might not have appeared.")

        # Extract the page content after handling popups
        html_content = driver.page_source

        match = re.search(r'<meta property="og:description" content="([^"]*)"', html_content)

        if match:
            raw_description = match.group(1).encode('utf-8').decode('unicode_escape')
            caption_part = re.split(r'\s-\sLikes,', raw_description, 1)[0]
            caption_part = re.split(r'\s-\sKommentare,', caption_part, 1)[0]

            if ' on Instagram: "' in caption_part:
                caption = caption_part.split(' on Instagram: "', 1)[1]
                if caption.endswith('"'):
                    caption = caption[:-1]
                return caption.strip()

            return caption_part.strip()

        logging.warning(f"Could not find caption for {url} (accessed {post_url}) even after using Selenium.")
        return None

    except Exception as e:
        logging.error(f"An error occurred with Selenium for {post_url}: {e}")
        return None
    finally:
        if driver:
            driver.quit()

