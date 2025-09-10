# llm_processor_lmstudio.py
#
# Description:
# This module handles all interactions with the LM Studio local server.
# It uses the native `lmstudio-python` library and its powerful structured
# output feature, which directly leverages Pydantic models for guaranteed
# clean, parsed JSON.

import logging
import re
import time

import lmstudio as lms
import unicodedata
from lmstudio import Chat
from pydantic import ValidationError

from models import Recipe

SYSTEM_PROMPT = """
You are a machine. Your only function is to convert social media recipe captions into structured JSON data according to the provided Pydantic schema. You must follow these rules with extreme precision and adhere strictly to the schema.

**Core Directives:**
- **Literal Extraction ONLY:** Your output must be based exclusively on the information present in the source text.
- **DO NOT HALLUCINATE:** Do not invent, infer, or add any information that is not explicitly stated. If a detail is missing, omit it.
- **DO NOT GUESS:** If you cannot determine a value for a field from the text, leave it as `null` or an empty list.
- **IGNORE NON-RECIPE TEXT:** Disregard all marketing language, calls to action (e.g., "Follow for more"), discount codes, and personal stories. Focus only on the recipe itself.

**Field-by-Field Instructions:**

1.  **Title (`title`):**
    - Extract the recipe's title. Use it directly, regardless of language.
    - If no clear title is given, create a concise, descriptive title in the original language of the recipe.

2.  **Servings (`servings`):**
    - Extract the exact number of servings mentioned (e.g., "6 Stück", "2 portions").
    - If no serving size is mentioned, this field MUST be `null`.

3.  **Ingredients (`ingredients`):**
    - **Grouping:**
        - If the caption provides clear ingredient groups (e.g., "CHICKEN CRUST", "TOPPINGS"), use these exact titles for `group_title`.
        - If there are no distinct groups, create one single group and title it "Zutaten".
        - **CRITICAL:** Do not create a new group for every single ingredient.
            - **BAD EXAMPLE (DO NOT DO THIS):** `[{"group_title": "Zutaten", "items": [{"name": "Mehl"}]}, {"group_title": "Zutaten", "items": [{"name": "Zucker"}]}]`
            - **GOOD EXAMPLE:** `[{"group_title": "Zutaten", "items": [{"name": "Mehl"}, {"name": "Zucker"}]}]`
    - **Parsing:**
        - The `name` field should contain only the name of the ingredient (e.g., "Mehl").
        - The `quantity` field should contain the corresponding amount (e.g., "280g").
        - **NEVER** merge the quantity and the name. (WRONG: `name: "280g Mehl"`, CORRECT: `name: "Mehl", quantity: "280g"`).
        - For ingredients without a quantity (like "Salz"), the `quantity` field MUST be `null`.
        - If a quantity is provided (e.g., '100g Haferflocken'), you MUST extract both the name ('Haferflocken') and the quantity ('100g').

4.  **Instructions (`steps`):**
    - Extract each preparation step into its own string in a list.
    - The steps must be a direct and literal representation of the instructions.
    - **CRITICAL:** If the caption only contains an ingredients list and no instructions, the `steps` field MUST be `null` or an empty list `[]`. DO NOT invent steps.
    - Strip any leading numbers or bullet points (e.g., '1.', '2)', '-') from the instruction text itself. The string in the list should start with the first word of the step.

5.  **Nutrition (`nutrition`):**
    - Extract the values for calories (`calories`), protein (`protein`), carbs (`carbs`), and fat (`fat`). Values must include units if provided (e.g., "42g").
    - **Handle abbreviations:** Recognize "KH" as the value for `carbs`.
    - **Handle unstructured text:** Values may appear on a single line.
        - **EXAMPLE:** For input "Nährwerte: 641 kcal 45g Protein 87g KH 10g Fett", the output should be `{"calories": "641 kcal", "protein": "45g", "carbs": "87g", "fat": "10g"}`.
    - If nutritional information is not present, the entire `nutrition` object MUST be `null`.
    - **CRITICAL: Nutritional information MUST be placed in the 'nutrition' object. DO NOT parse nutritional values (kcal, protein, etc.) as ingredients.**

6.  **All Other Fields:**
    - For `categories`, `prep_time`, `cook_time`, and `notes`, only populate them if the information is explicitly available in the caption. Otherwise, they must be `null` or an empty list.

**--- EXAMPLES ---**

**EXAMPLE 1: Complex Recipe with Ingredient Groups**

--- SOURCE CAPTION ---
was brauchen wir:

Für die Kartoffeln:
650g geschälte Kartoffeln in würfeln 
2 Tl Paprikapulver
1 Tl Rosmarin

Für das Dressing
600g Skyr-Alternative
Saft einer Zitrone
Salz/Pfeffer nach Geschmack

außerdem
400g Räuchertofu

Das Rezept:
1: Die Kartoffeln mehrmals in einer Schüssel abspülen 
2: Mit den Gewürzen vermengen und für circa 25 Minuten bei 180 Grad Umluft knusprig backen 
3: Währenddessen alle Zutaten für das Dressing verrühren.
4: Den Räuchertofu knusprig anbraten 
5: Alles zusammen vermengen.

Gesamtnährwerte: Kcal: 1834, Fett: 75g, Kohlenhydrate: 122g, Eiweiß: 145g
--- END SOURCE CAPTION ---

--- EXPECTED JSON OUTPUT ---
{
  "title": "Bratkartoffelsalat",
  "servings": null,
  "ingredients": [
    {
      "group_title": "Für die Kartoffeln",
      "items": [
        {"name": "geschälte Kartoffeln in würfeln", "quantity": "650g"},
        {"name": "Paprikapulver", "quantity": "2 Tl"},
        {"name": "Rosmarin", "quantity": "1 Tl"}
      ]
    },
    {
      "group_title": "Für das Dressing",
      "items": [
        {"name": "Skyr-Alternative", "quantity": "600g"},
        {"name": "Zitrone", "quantity": "Saft einer"},
        {"name": "Salz/Pfeffer", "quantity": "nach Geschmack"}
      ]
    },
    {
      "group_title": "außerdem",
      "items": [
        {"name": "Räuchertofu", "quantity": "400g"}
      ]
    }
  ],
  "steps": [
    "Die Kartoffeln mehrmals in einer Schüssel abspülen",
    "Mit den Gewürzen vermengen und für circa 25 Minuten bei 180 Grad Umluft knusprig backen",
    "Währenddessen alle Zutaten für das Dressing verrühren.",
    "Den Räuchertofu knusprig anbraten",
    "Alles zusammen vermengen."
  ],
  "nutrition": {
    "calories": "1834",
    "protein": "145g",
    "carbs": "122g",
    "fat": "75g"
  }
}

**EXAMPLE 2: Edge Case (Ingredients Only)**

--- SOURCE CAPTION ---
DÖNERTELLER MEALPREP⤵️
Zutaten für 3 Portionen:
-300g Reis
-200g Cherry Tomaten
-1/2 Gurke
-150g Hirtenkäse light
Nährwerte pro Portion: 641 kcal, 45g Protein, 87g KH, 10g Fett
--- END SOURCE CAPTION ---

--- EXPECTED JSON OUTPUT ---
{
  "title": "Dönerteller Mealprep",
  "servings": "3 Portionen",
  "ingredients": [
    {
      "group_title": "Zutaten",
      "items": [
        {"name": "Reis", "quantity": "300g"},
        {"name": "Cherry Tomaten", "quantity": "200g"},
        {"name": "Gurke", "quantity": "1/2"},
        {"name": "Hirtenkäse light", "quantity": "150g"}
      ]
    }
  ],
  "steps": [],
  "nutrition": {
    "calories": "641 kcal",
    "protein": "45g",
    "carbs": "87g",
    "fat": "10g"
  }
}

"""

def preprocess_caption(caption: str) -> str:
    """
    Cleans and standardizes the Instagram caption text to improve LLM accuracy.
    """
    # Normalize Unicode characters to their canonical forms (e.g., converts fancy
    # quotes and dashes to standard ASCII equivalents). This helps the model by
    # reducing character ambiguity.
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
    # Standardize various bullet point styles to a simple dash for consistency.
    cleaned_caption = re.sub(r'^[•✅🔹*–-]\s*', '- ', cleaned_caption, flags=re.MULTILINE)
    cleaned_caption = re.sub(r'\n\s*\n', '\n', cleaned_caption).strip()
    return cleaned_caption


def process_caption_with_llm(caption: str, url: str, model_name: str) -> tuple[Recipe | None, float | None, str | None]:
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

            try:
                model = client.llm.model(model_name)
                logging.debug(f"Successfully got model handle for: {model_name}")
            except Exception as load_error:
                logging.error(f"Failed to get model '{model_name}' in LM Studio: {load_error}")
                logging.error("Please ensure the model is downloaded and correctly named in your LM Studio library.")
                return None, None, None

            # **CHANGE**: Use the recommended Chat helper class to structure the prompt.
            chat = Chat(SYSTEM_PROMPT)
            user_prompt = f"--- SOURCE CAPTION ---\n{cleaned_caption}\n--- END SOURCE CAPTION ---"
            chat.add_user_message(user_prompt)

            prediction = model.respond(
                chat,  # Pass the Chat object directly
                response_format=Recipe,
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

