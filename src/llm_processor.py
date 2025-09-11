# llm_processor.py
#
# Description:
# This module defines the common interface for all LLM processors and provides
# shared functionality like caption preprocessing. It also contains the
# implementation for the local Ollama processor.

import logging
import re
import time
import unicodedata
from abc import ABC, abstractmethod

import ollama
from pydantic import ValidationError

from config import SYSTEM_PROMPT
from models import Recipe


def preprocess_caption(caption: str) -> str:
    """
    Cleans and standardizes the Instagram caption text to improve LLM accuracy.
    """
    cleaned_caption = unicodedata.normalize('NFKC', caption)

    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F700-\U0001F77F"  # alchemical symbols
        "\U0001F780-\U0001F7FF"  # Geometric Shapes Extended
        "\U0001F800-\U0001F8FF"  # Supplemental Arrows-C
        "\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
        "\U0001FA00-\U0001FA6F"  # Chess Symbols
        "\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "]+",
        flags=re.UNICODE,
    )
    cleaned_caption = emoji_pattern.sub(r'', cleaned_caption)
    cleaned_caption = re.sub(r'[@#]\w+', '', cleaned_caption)
    lines = cleaned_caption.split('\n')
    non_marketing_lines = []
    spam_keywords = [
        'kommentiere', 'comment', 'link in bio', 'follow for more',
        'sichere dir jetzt', 'kostenloses erstgespräch'
    ]
    for line in lines:
        if not any(keyword in line.lower() for keyword in spam_keywords):
            non_marketing_lines.append(line)
    cleaned_caption = '\n'.join(non_marketing_lines)
    cleaned_caption = re.sub(r'^[•✅🔹*–-]\s*', '- ', cleaned_caption, flags=re.MULTILINE)
    cleaned_caption = re.sub(r'\n\s*\n', '\n', cleaned_caption).strip()
    return cleaned_caption


class LLMProcessor(ABC):
    """
    Abstract base class for all LLM processors.
    Ensures a consistent interface for processing recipe captions.
    """

    @abstractmethod
    def process_caption(self, caption: str, url: str, model_name: str) -> tuple[Recipe | None, float | None, str | None]:
        """
        Processes a caption to extract a recipe.

        Args:
            caption: The raw caption text from the post.
            url: The source URL of the post.
            model_name: The specific model name to use for processing.

        Returns:
            A tuple containing:
            - A Recipe object if successful, otherwise None.
            - The processing time in seconds, or None.
            - The cleaned caption text, or None.
        """
        pass


class OllamaProcessor(LLMProcessor):
    """
    LLM processor for local models served via the Ollama API.
    """

    def process_caption(self, caption: str, url: str, model_name: str) -> tuple[Recipe | None, float | None, str | None]:
        """
        Sends the caption to the local Ollama LLM and parses the response.
        """
        response_content = ""
        start_time = time.time()
        try:
            logging.debug(f"Sending caption to Ollama ({model_name})...")
            cleaned_caption = preprocess_caption(caption)

            response = ollama.chat(
                model=model_name,
                messages=[
                    {
                        'role': 'system',
                        'content': SYSTEM_PROMPT,
                    },
                    {
                        'role': 'user',
                        'content': f"--- SOURCE CAPTION ---\n{cleaned_caption}\n--- END SOURCE CAPTION ---",
                    }
                ],
                options={
                    "temperature": 0.0
                },
                format='json'
            )

            response_content = response['message']['content']

            recipe_data = Recipe.model_validate_json(response_content)
            recipe_data.source_url = url

            end_time = time.time()
            processing_time = end_time - start_time

            logging.info(f"Successfully processed with {model_name} in {processing_time:.2f}s: '{recipe_data.title}'")
            return recipe_data, processing_time, cleaned_caption

        except ValidationError as e:
            logging.error(f"Ollama output failed validation for url {url} with model {model_name}: {e}")
            logging.debug(f"Invalid JSON received from {model_name}: {response_content}")
            return None, None, None
        except Exception as e:
            logging.error(f"An unexpected error occurred while processing with Ollama {model_name} for url {url}: {e}")
            return None, None, None
