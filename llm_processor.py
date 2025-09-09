# llm_processor.py
#
# Description:
# This module handles all interactions with the local Large Language Model (LLM)
# via the Ollama API. It defines the system prompt and uses Pydantic models
# to enforce a structured JSON output from the LLM.

import ollama
import logging
import time
from pydantic import ValidationError

from models import Recipe

# Updated system prompt to match the simplified Ingredient model
LLM_PROMPT_TEMPLATE = """
Du bist ein präziser Rezept-Parser, der Social-Media-Captions in strukturiertes JSON umwandelt.
Deine Antwort MUSS ausschliesslich ein valides JSON-Objekt sein, das dem vorgegebenen Schema entspricht.
Gib keine Erklärungen oder einleitenden Text aus.

Anweisungen:
1.  **Titel**: Erstelle einen klaren, deutschen Titel für das Gericht. Wenn der Originaltitel englisch ist, behalte ihn bei.
2.  **Kategorien**: Ordne das Rezept Kategorien zu: Mahlzeitentyp (Frühstück, Hauptgericht, Dessert, Snack, Getränk), Temperatur (warm, kalt) und optional Diätstil (z.B. vegan, proteinreich).
3.  **Zeiten & Portionen**: Extrahiere Zubereitungszeit, Kochzeit und Portionsanzahl, falls erwähnt.
4.  **Zutaten**:
    -   Gruppiere Zutaten logisch (z.B. "Für den Teig", "Für die Füllung").
    -   Wenn es keine logischen Gruppen gibt, erstelle eine einzige Gruppe mit dem Titel "Zutaten".
    -   Extrahiere den Namen der Zutat und die **vollständige Mengenangabe** (z.B. "300g", "1/2", "1 TL") in das `quantity`-Feld.
5.  **Zubereitungsschritte**: Liste die Anweisungen als eine klare, nummerierte Liste von Schritten auf. Jeder Schritt sollte ein vollständiger Satz sein.
6.  **Nährwerte**:
    -   Suche nach einem Abschnitt "Nährwerte".
    -   Wenn vorhanden, extrahiere Kalorien, Protein, Kohlenhydrate (KH) und Fett.
    -   Standardisiere die Einheiten auf `kcal` für Kalorien und `g` für Makronährstoffe.
    -   Wenn keine Nährwerte angegeben sind, lasse das `nutrition`-Feld komplett weg (null). Erfinde keine Werte.
7.  **Notizen**: Füge eventuelle zusätzliche Tipps oder Hinweise in eine Liste von Notizen ein.
"""


def process_caption_with_llm(caption: str, url: str, model_name: str) -> tuple[Recipe | None, float | None]:
    """
    Sends the caption to the local LLM and attempts to parse the response
    into a structured Recipe object using a Pydantic model.
    Returns a tuple of (Recipe object, processing_time_in_seconds).
    """
    response_content = ""
    start_time = time.time()
    try:
        logging.info(f"Sending caption for {url} to LLM ({model_name})...")

        response = ollama.chat(
            model=model_name,
            messages=[
                {
                    'role': 'system',
                    'content': LLM_PROMPT_TEMPLATE,
                },
                {
                    'role': 'user',
                    'content': f"Hier ist der Caption-Text:\n\n---\n{caption}\n---",
                }
            ],
            format=Recipe.model_json_schema()
        )

        response_content = response['message']['content']

        recipe_data = Recipe.model_validate_json(response_content)
        recipe_data.source_url = url

        end_time = time.time()
        processing_time = end_time - start_time

        logging.info(f"Successfully processed with {model_name} in {processing_time:.2f}s: '{recipe_data.title}'")
        return recipe_data, processing_time

    except ValidationError as e:
        logging.error(f"LLM output failed validation for url {url} with model {model_name}: {e}")
        logging.debug(f"Invalid JSON received from {model_name}: {response_content}")
        return None, None
    except Exception as e:
        logging.error(f"An unexpected error occurred while processing with LLM {model_name} for url {url}: {e}")
        return None, None
