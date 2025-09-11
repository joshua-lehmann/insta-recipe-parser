# llm_processor_gemini.py
#
# Description:
# This module handles all interactions with the Google Gemini API using the
# new `google-genai` SDK. It conforms to the LLMProcessor interface.

import logging
import time

# Use the new client-centric imports, including the correct error classes
from google import genai
from google.genai import types, errors

from config import GOOGLE_API_KEY, SYSTEM_PROMPT
from llm_processor import LLMProcessor, preprocess_caption
from models import Recipe

# Set specific Google Gemini loggers to WARNING level
logging.getLogger('google.genai').setLevel(logging.WARNING)
logging.getLogger('google.generativeai').setLevel(logging.WARNING)


class GeminiProcessor(LLMProcessor):
    """
    LLM processor for the Google Gemini API using the `google-genai` SDK.
    """

    def process_caption(self, caption: str, url: str, model_name: str) -> tuple[Recipe | None, float | None, str | None]:
        """
        Sends the caption to the Google Gemini API and gets a structured
        Recipe object back using the new client-centric approach.
        """
        if not GOOGLE_API_KEY:
            logging.error("GOOGLE_API_KEY is not set. Skipping Gemini processing.")
            return None, None, None

        start_time = time.time()
        cleaned_caption = None
        try:
            client = genai.Client(api_key=GOOGLE_API_KEY)

            logging.debug(f"Sending caption to Google Gemini ({model_name})...")
            cleaned_caption = preprocess_caption(caption)

            config = types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=Recipe,
            )

            user_prompt = f"--- SOURCE CAPTION ---\n{cleaned_caption}\n--- END SOURCE CAPTION ---"

            if model_name.startswith("models/"):
                model_name = model_name.split('/', 1)[1]

            response = client.models.generate_content(
                model=model_name,
                contents=user_prompt,
                config=config,
            )

            validated_recipe: Recipe | None = response.parsed

            if not validated_recipe:
                logging.error(f"Gemini response for {url} was empty or could not be parsed into a Recipe object.")
                logging.debug(f"Raw response text from Gemini: {response.text}")
                return None, None, cleaned_caption

            validated_recipe.source_url = url

            end_time = time.time()
            processing_time = end_time - start_time

            logging.info(
                f"Successfully processed with Gemini {model_name} in {processing_time:.2f}s: '{validated_recipe.title}'")
            return validated_recipe, processing_time, cleaned_caption

        # Catch the correct, specific APIError from the google-genai SDK
        except (errors.APIError, ValueError) as e:
            logging.error(f"Google API call or validation error for url {url} with model {model_name}: {e}")
            return None, None, cleaned_caption
        except Exception as e:
            logging.error(f"An unexpected error occurred with Gemini model {model_name} for url {url}: {e}")
            return None, None, cleaned_caption
