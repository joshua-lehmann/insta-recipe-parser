# llm_processor_gemini.py
#
# Description:
# This module handles all interactions with the Google Gemini API.
# It uses the new google.genai library's Client interface to send requests
# and leverages the structured output feature to get clean, parsed Pydantic
# objects directly from the response.

import os
import logging
import time
from google import genai
# Correct import for the new SDK's error handling
from google.genai.errors import APIError

from models import Recipe
import config

# The system prompt instructions are prepended to the user's content.
GEMINI_PROMPT_TEMPLATE = """
You are a precise recipe parser that converts social media captions into structured JSON.
Your response MUST be exclusively a valid JSON object matching the provided schema.
Do not output any explanations, markdown formatting, or introductory text.

Based on the schema, perform the following actions:
1.  **Title**: Create a clear, German title for the dish. If the original title is in English, keep it.
2.  **Categories**: Assign categories: Meal type (e.g., Breakfast, Main Course, Dessert), temperature (warm, cold), and optionally dietary style (e.g., vegan, high-protein).
3.  **Times & Servings**: Extract prep time, cook time, and the number of servings if mentioned.
4.  **Ingredients**:
    -   Group ingredients logically (e.g., "For the dough", "For the filling").
    -   If there are no logical groups, create a single group titled "Zutaten".
    -   Extract the ingredient name and the **full quantity** (e.g., "300g", "1/2", "1 TL") into the `quantity` field.
5.  **Steps**: List the instructions as a clear, numbered list of steps. Each step should be a complete sentence.
6.  **Nutrition**:
    -   Look for a "Nährwerte" section.
    -   If present, extract calories, protein, carbohydrates (KH), and fat.
    -   Standardize units to `kcal` for calories and `g` for macronutrients.
    -   If no nutrition information is provided, omit the `nutrition` field entirely (null). Do not invent values.
7.  **Notes**: Add any additional tips or remarks into a list of notes.
"""


def process_caption_with_gemini(caption: str, url: str, model_name: str) -> tuple[Recipe | None, float | None]:
    """
    Sends the caption to the Google Gemini API and attempts to get a structured
    Recipe object back using the structured output feature.
    Returns a tuple of (Recipe object, processing_time_in_seconds).
    """
    if not config.GOOGLE_API_KEY:
        logging.error("GOOGLE_API_KEY is not set in config.py or environment variables. Skipping Gemini processing.")
        return None, None

    # The client automatically uses the GOOGLE_API_KEY or GEMINI_API_KEY env variable if the api_key is not provided.
    client = genai.Client(api_key=config.GOOGLE_API_KEY)

    start_time = time.time()
    try:
        logging.info(f"Sending caption to Google Gemini ({model_name})...")

        full_prompt = f"{GEMINI_PROMPT_TEMPLATE}\n\n---\nHere is the caption text:\n{caption}\n---"

        response = client.models.generate_content(
            model=f"models/{model_name}",
            contents=full_prompt,
            # Corrected parameter name from 'generation_config' to 'config'
            config={
                "response_mime_type": "application/json",
                "response_schema": Recipe,
            },
        )

        validated_recipe: Recipe | None = response.parsed

        if not validated_recipe:
            logging.error(
                f"Gemini response for {url} could not be parsed into a Recipe object, even though no exception was thrown.")
            logging.debug(f"Raw response text from Gemini: {response.text}")
            return None, None

        validated_recipe.source_url = url

        end_time = time.time()
        processing_time = end_time - start_time

        logging.info(
            f"Successfully processed with Gemini {model_name} in {processing_time:.2f}s: '{validated_recipe.title}'")
        return validated_recipe, processing_time

    # Catch the correct APIError from the new SDK, along with ValueError for parsing issues.
    except (APIError, ValueError) as e:
        logging.error(f"Google API call error or validation issue for url {url} with model {model_name}: {e}")
        return None, None
    except Exception as e:
        logging.error(
            f"An unexpected error occurred while processing with Gemini model {model_name} for url {url}: {e}")
        return None, None
