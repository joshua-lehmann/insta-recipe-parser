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
from lmstudio import Chat
from pydantic import ValidationError

from config import SYSTEM_PROMPT
from llm_processor import LLMProcessor, preprocess_caption
from models import Recipe


class LMStudioProcessor(LLMProcessor):
    """
    LLM processor for local models served via the LM Studio.
    """

    def process_caption(self, caption: str, url: str, model_name: str) -> tuple[Recipe | None, float | None, str | None]:
        """
        Sends the caption to the LM Studio server and gets a structured Recipe
        object back using the native lmstudio-python structured output feature.

        Returns:
            tuple: (Recipe object or None, processing time or None, cleaned caption or None)
        """
        start_time = time.time()
        try:
            cleaned_caption = preprocess_caption(caption)
            logging.debug(f"Original caption length: {len(caption)}, Cleaned caption length: {len(cleaned_caption)}")

            with lms.Client() as client:
                logging.debug(f"Sending caption to LM Studio ({model_name})...")

                # --- Load-Time Configuration (for GPU) ---
                load_config = {"gpu": {"ratio": 0.9}}
                logging.debug(f"Applying load config: gpu.ratio={load_config}")

                try:
                    # Pass the load configuration object when loading the model
                    model = client.llm.model(model_name, config=load_config)
                    logging.debug(f"Successfully got model handle for: {model_name}")
                except Exception as load_error:
                    logging.error(f"Failed to get model '{model_name}' in LM Studio: {load_error}")
                    logging.error("Please ensure the model is downloaded and correctly named in your LM Studio library.")
                    return None, None, None

                chat = Chat(SYSTEM_PROMPT)
                user_prompt = f"--- SOURCE CAPTION ---\n{cleaned_caption}\n--- END SOURCE CAPTION ---"
                chat.add_user_message(user_prompt)

                inference_config = {"cpu_threads": 10}

                logging.debug(f"Applying inference config: cpu_threads={inference_config}")

                prediction = model.respond(
                    chat,
                    response_format=Recipe,
                    config=inference_config,
                )

                parsed_data = prediction.parsed
                if not parsed_data:
                    logging.error(f"LM Studio response for {url} was empty.")
                    return None, None, None

                validated_recipe = Recipe(**parsed_data)
                validated_recipe.source_url = url

                end_time = time.time()
                processing_time = end_time - start_time

                logging.debug(
                    f"Successfully processed with LM Studio {model_name} in {processing_time:.2f}s: '{validated_recipe.title}'")
                return validated_recipe, processing_time, cleaned_caption

        except ValidationError as e:
            logging.error(f"LM Studio output failed Pydantic validation for url {url}: {e}")
            return None, None, None
        except Exception as e:
            logging.error(f"An unexpected error occurred while processing with LM Studio for url {url}: {e}")
            return None, None, None
