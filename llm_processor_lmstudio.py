# llm_processor_lmstudio.py
#
# Description:
# This module handles all interactions with the LM Studio local server.
# It uses the native `lmstudio-python` library and its powerful structured
# output feature, which directly leverages Pydantic models for guaranteed
# clean, parsed JSON.

import logging
import time
import lmstudio as lms
from pydantic import ValidationError

from models import Recipe
import config

# System prompt is slightly simplified as the SDK handles the JSON enforcement.
LMSTUDIO_PROMPT_TEMPLATE = """
You are a precise recipe parser that converts social media captions into structured data.
Your response MUST conform to the provided schema.

Based on the schema, perform the following actions:
1.  **Title**: Create a clear, German title for the dish. If the original title is in English, keep it.
2.  **Categories**: Assign categories: Meal type (e.g., Breakfast, Main Course, Dessert), temperature (warm, cold), and optionally dietary style (e.g., vegan, high-protein).
3.  **Times & Servings**: Extract prep time, cook time, and the number of servings if mentioned.
4.  **Ingredients**:
    -   Group ingredients logically (e.g., "For the dough", "For the filling").
    -   If there are no logical groups, create a single group titled "Zutaten".
    -   Extract the ingredient name and the **full quantity** (e.g., "300g", "1/2", "1 TL") into the `quantity` field.
5.  **Steps**: List the instructions as a clear, numbered list of steps. Each step should be a complete sentence.
6.  **Nutrition**: Extract calories, protein, carbohydrates (KH), and fat. If not provided, omit the field.
7.  **Notes**: Add any additional tips or remarks into a list of notes.
"""

def process_caption_with_llm(caption: str, url: str, model_name: str) -> tuple[Recipe | None, float | None]:
    """
    Sends the caption to the LM Studio server and gets a structured Recipe
    object back using the native lmstudio-python structured output feature.
    Returns a tuple of (Recipe object, processing_time_in_seconds).
    """
    start_time = time.time()
    try:
        # The client automatically finds the server on the default port.
        with lms.Client() as client:
            logging.info(f"Sending caption to LM Studio ({model_name})...")

            # BUG FIX: Use the correct `.model()` method to get the model by identifier, as per the documentation.
            try:
                model = client.llm.model(model_name)
                logging.debug(f"Successfully got model handle for: {model_name}")
            except Exception as load_error:
                logging.error(f"Failed to get model '{model_name}' in LM Studio: {load_error}")
                logging.error("Please ensure the model is downloaded and correctly named in your LM Studio library.")
                return None, None

            full_prompt = (
                f"{LMSTUDIO_PROMPT_TEMPLATE}\n\n"
                f"---\nHere is the caption text:\n{caption}\n---"
            )

            # Pass the Pydantic class directly for structured output.
            prediction = model.respond(
                full_prompt,
                response_format=Recipe,
            )

            parsed_data = prediction.parsed
            if not parsed_data:
                logging.error(f"LM Studio response for {url} was empty.")
                return None, None

            validated_recipe = Recipe(**parsed_data)
            validated_recipe.source_url = url

            end_time = time.time()
            processing_time = end_time - start_time

            logging.info(
                f"Successfully processed with LM Studio {model_name} in {processing_time:.2f}s: '{validated_recipe.title}'")
            return validated_recipe, processing_time

    except ValidationError as e:
        logging.error(f"LM Studio output failed Pydantic validation for url {url}: {e}")
        return None, None
    except Exception as e:
        logging.error(f"An unexpected error occurred while processing with LM Studio for url {url}: {e}")
        return None, None

