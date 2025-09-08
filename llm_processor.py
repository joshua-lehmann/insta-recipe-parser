# llm_processor.py
#
# Description:
# This module handles all interactions with the local Large Language Model (LLM)
# via the Ollama API. It defines the system prompt and uses Pydantic models
# to enforce a structured JSON output from the LLM.

import ollama
import logging
from pydantic import ValidationError

from models import Recipe  # Corrected: Removed ValidationError, as it's not in models.py
from config import LLM_MODEL

# The system prompt that instructs the LLM on how to behave and what format to use.
# It is designed to be clear and specific to maximize the chances of getting a
# valid, well-structured JSON output.
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
    -   Standardisiere Mengeneinheiten auf Deutsch: `g`, `ml`, `Stk.`, `TL`, `EL`.
5.  **Zubereitungsschritte**: Liste die Anweisungen als eine klare, nummerierte Liste von Schritten auf. Jeder Schritt sollte ein vollständiger Satz sein.
6.  **Nährwerte**:
    -   Suche nach einem Abschnitt "Nährwerte".
    -   Wenn vorhanden, extrahiere Kalorien, Protein, Kohlenhydrate (KH) und Fett.
    -   Standardisiere die Einheiten auf `kcal` für Kalorien und `g` für Makronährstoffe.
    -   Wenn keine Nährwerte angegeben sind, lasse das `nutrition`-Feld komplett weg (null). Erfinde keine Werte.
7.  **Notizen**: Füge eventuelle zusätzliche Tipps oder Hinweise in eine Liste von Notizen ein.
"""


def process_caption_with_llm(caption: str, url: str) -> Recipe | None:
    """
    Sends the caption to the local LLM and attempts to parse the response
    into a structured Recipe object using a Pydantic model.
    """
    response_content = ""
    try:
        logging.info(f"Sending caption for {url} to LLM ({LLM_MODEL})...")

        response = ollama.chat(
            model=LLM_MODEL,
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
            # Corrected: Pass the actual Pydantic schema to enforce the structure.
            format=Recipe.model_json_schema()
        )

        response_content = response['message']['content']

        # Validate the JSON response against our Pydantic model.
        # This will raise a ValidationError if the LLM's output does not match the schema.
        recipe_data = Recipe.model_validate_json(response_content)

        # Manually add the source URL, as the LLM does not have this context.
        recipe_data.source_url = url

        logging.info(f"Successfully processed and validated recipe: '{recipe_data.title}'")
        return recipe_data

    except ValidationError as e:
        logging.error(f"LLM output failed validation for url {url}: {e}")
        logging.debug(f"Invalid JSON received: {response_content}")
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred while processing with LLM for url {url}: {e}")
        return None

