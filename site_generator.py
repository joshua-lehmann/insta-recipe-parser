# site_generator.py
#
# Description:
# This module handles the creation of static HTML pages for GitHub Pages hosting.
# It generates individual recipe pages with proper schema.org JSON-LD structured data
# and creates an index page listing all recipes.

import logging
import os
import re
from typing import List
from datetime import datetime

from models import Recipe


def sanitize_title(title: str) -> str:
    """
    Sanitizes the recipe title for safe filename usage.
    Replaces German umlauts with their ASCII equivalents and handles special characters.

    Args:
        title: The original recipe title

    Returns:
        A sanitized version of the title suitable for filenames
    """
    # Replace German umlauts with their ASCII equivalents
    replacements = {
        'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'ß': 'ss',
        'Ä': 'Ae', 'Ö': 'Oe', 'Ü': 'Ue',
        'é': 'e', 'è': 'e', 'ê': 'e', 'à': 'a', 'ç': 'c'
    }

    for umlaut, replacement in replacements.items():
        title = title.replace(umlaut, replacement)

    # Remove or replace special characters
    title = re.sub(r'[^\w\s-]', '', title)
    # Replace spaces with hyphens and convert to lowercase
    title = re.sub(r'[-\s]+', '-', title).strip('-').lower()

    return title


def convert_time_to_iso8601(time_str: str) -> str:
    """
    Convert German time format to ISO 8601 duration format.

    Args:
        time_str: Time string like "15 Minuten", "1 Stunde", "30 Min"

    Returns:
        ISO 8601 duration format like "PT15M", "PT1H", "PT30M"
    """
    if not time_str:
        return ""

    time_str = time_str.lower()

    # Extract numbers and time units
    hours = 0
    minutes = 0

    # Match hours
    hour_match = re.search(r'(\d+)\s*(?:stunden?|h)', time_str)
    if hour_match:
        hours = int(hour_match.group(1))

    # Match minutes
    minute_match = re.search(r'(\d+)\s*(?:minuten?|min|m)', time_str)
    if minute_match:
        minutes = int(minute_match.group(1))

    # Build ISO 8601 duration
    duration = "PT"
    if hours > 0:
        duration += f"{hours}H"
    if minutes > 0:
        duration += f"{minutes}M"

    return duration if len(duration) > 2 else ""


def create_json_ld(recipe: Recipe) -> dict:
    """
    Create schema.org compliant JSON-LD structured data for a recipe.

    Args:
        recipe: The recipe object

    Returns:
        Dictionary containing the JSON-LD structured data
    """
    json_ld = {
        "@context": "https://schema.org/",
        "@type": "Recipe",
        "name": recipe.title
    }

    # Add optional fields if available
    if recipe.servings:
        json_ld["recipeYield"] = recipe.servings

    if recipe.prep_time:
        prep_iso = convert_time_to_iso8601(recipe.prep_time)
        if prep_iso:
            json_ld["prepTime"] = prep_iso

    if recipe.cook_time:
        cook_iso = convert_time_to_iso8601(recipe.cook_time)
        if cook_iso:
            json_ld["cookTime"] = cook_iso

    # Add ingredients
    ingredients_list = []
    for group in recipe.ingredients:
        for ingredient in group.ingredients:
            if ingredient.quantity:
                ingredients_list.append(f"{ingredient.quantity} {ingredient.name}")
            else:
                ingredients_list.append(ingredient.name)

    if ingredients_list:
        json_ld["recipeIngredient"] = ingredients_list

    # Add instructions as HowToStep
    if recipe.steps:
        instructions = []
        for step in recipe.steps:
            instructions.append({
                "@type": "HowToStep",
                "text": step
            })
        json_ld["recipeInstructions"] = instructions

    # Add nutrition information
    if recipe.nutrition:
        nutrition_info = {"@type": "NutritionInformation"}

        if recipe.nutrition.calories:
            nutrition_info["calories"] = recipe.nutrition.calories
        if recipe.nutrition.protein:
            nutrition_info["proteinContent"] = recipe.nutrition.protein
        if recipe.nutrition.carbs:
            nutrition_info["carbohydrateContent"] = recipe.nutrition.carbs
        if recipe.nutrition.fat:
            nutrition_info["fatContent"] = recipe.nutrition.fat

        if len(nutrition_info) > 1:  # More than just @type
            json_ld["nutrition"] = nutrition_info

    # Add categories as keywords
    if recipe.categories:
        json_ld["keywords"] = ", ".join(recipe.categories)

    return json_ld


def ensure_output_directory(path: str):
    """
    Ensure the output directory exists.

    Args:
        path: Directory path to create
    """
    os.makedirs(path, exist_ok=True)


def generate_recipe_page(recipe: Recipe, output_dir: str) -> str:
    """
    Generate an individual HTML page for a recipe.

    Args:
        recipe: The recipe object
        output_dir: Directory to save the HTML file

    Returns:
        The filename of the generated HTML file
    """
    ensure_output_directory(output_dir)

    # Create safe filename
    sanitized_title = sanitize_title(recipe.title)
    filename = f"{sanitized_title}.html"
    filepath = os.path.join(output_dir, filename)

    # Generate JSON-LD structured data
    json_ld = create_json_ld(recipe)

    # Create HTML content
    html_content = f"""<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{recipe.title}</title>
    <script type="application/ld+json">
{_format_json_ld(json_ld)}
    </script>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            line-height: 1.6;
            color: #333;
        }}
        .recipe-header {{
            border-bottom: 2px solid #e0e0e0;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }}
        .recipe-meta {{
            display: flex;
            flex-wrap: wrap;
            gap: 20px;
            margin: 15px 0;
            color: #666;
        }}
        .recipe-meta span {{
            background: #f5f5f5;
            padding: 5px 10px;
            border-radius: 5px;
            font-size: 0.9em;
        }}
        .ingredients-section, .instructions-section {{
            margin: 30px 0;
        }}
        .ingredient-group {{
            margin: 20px 0;
        }}
        .ingredient-group h3 {{
            color: #2c3e50;
            font-size: 1.1em;
            margin-bottom: 10px;
        }}
        ul, ol {{
            padding-left: 20px;
        }}
        li {{
            margin: 8px 0;
        }}
        .nutrition-section {{
            background: #f9f9f9;
            padding: 20px;
            border-radius: 8px;
            margin: 30px 0;
        }}
        .nutrition-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin-top: 10px;
        }}
        .nutrition-item {{
            background: white;
            padding: 10px;
            border-radius: 5px;
            text-align: center;
        }}
        .back-link {{
            display: inline-block;
            margin-bottom: 20px;
            color: #3498db;
            text-decoration: none;
        }}
        .back-link:hover {{
            text-decoration: underline;
        }}
        @media (max-width: 600px) {{
            body {{ padding: 15px; }}
            .recipe-meta {{ gap: 10px; }}
            .nutrition-grid {{ grid-template-columns: 1fr 1fr; }}
        }}
    </style>
</head>
<body>
    <a href="index.html" class="back-link">← Zurück zur Rezeptliste</a>

    <div class="recipe-header">
        <h1>{recipe.title}</h1>
        <div class="recipe-meta">"""

    if recipe.servings:
        html_content += f'<span>🍽️ {recipe.servings}</span>'
    if recipe.prep_time:
        html_content += f'<span>⏱️ Vorbereitung: {recipe.prep_time}</span>'
    if recipe.cook_time:
        html_content += f'<span>🔥 Kochzeit: {recipe.cook_time}</span>'

    html_content += """
        </div>
    </div>

    <div class="ingredients-section">
        <h2>Zutaten</h2>"""

    for group in recipe.ingredients:
        if group.group_title and group.group_title.lower() != "zutaten":
            html_content += f'<div class="ingredient-group"><h3>{group.group_title}</h3>'
        else:
            html_content += '<div class="ingredient-group">'

        html_content += '<ul>'
        for ingredient in group.ingredients:
            quantity = ingredient.quantity + " " if ingredient.quantity else ""
            html_content += f'<li>{quantity}{ingredient.name}</li>'
        html_content += '</ul></div>'

    html_content += """
    </div>

    <div class="instructions-section">
        <h2>Zubereitung</h2>
        <ol>"""

    for step in recipe.steps:
        html_content += f'<li>{step}</li>'

    html_content += '</ol></div>'

    if recipe.notes:
        html_content += """
    <div class="notes-section">
        <h2>Notizen & Tipps</h2>
        <ul>"""
        for note in recipe.notes:
            html_content += f'<li>{note}</li>'
        html_content += '</ul></div>'

    if recipe.nutrition:
        html_content += """
    <div class="nutrition-section">
        <h2>Nährwerte pro Portion</h2>
        <div class="nutrition-grid">"""

        if recipe.nutrition.calories:
            html_content += f'<div class="nutrition-item"><strong>{recipe.nutrition.calories}</strong><br>Kalorien</div>'
        if recipe.nutrition.protein:
            html_content += f'<div class="nutrition-item"><strong>{recipe.nutrition.protein}</strong><br>Protein</div>'
        if recipe.nutrition.carbs:
            html_content += f'<div class="nutrition-item"><strong>{recipe.nutrition.carbs}</strong><br>Kohlenhydrate</div>'
        if recipe.nutrition.fat:
            html_content += f'<div class="nutrition-item"><strong>{recipe.nutrition.fat}</strong><br>Fett</div>'

        html_content += '</div></div>'

    if recipe.source_url:
        html_content += f"""
    <div style="margin-top: 40px; padding: 20px; background: #f8f9fa; border-radius: 8px; border-left: 4px solid #e91e63;">
        <h3 style="margin: 0 0 10px 0; color: #2c3e50; font-size: 1.1em;">📱 Original Instagram Reel</h3>
        <p style="margin: 0;">
            <a href="{recipe.source_url}" target="_blank" rel="noopener" 
               style="color: #e91e63; text-decoration: none; font-weight: bold; font-size: 1.1em;">
                🔗 Original Reel ansehen
            </a>
        </p>
        <p style="margin: 5px 0 0 0; color: #666; font-size: 0.9em;">
            Klicken Sie hier, um das ursprüngliche Instagram-Video zu sehen
        </p>
    </div>"""

    html_content += """
</body>
</html>"""

    # Write HTML file
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html_content)

    logging.info(f"Generated recipe page: {filepath}")
    return filename


def generate_index_page(recipes: List[Recipe], output_dir: str):
    """
    Generate an index page listing all recipes.

    Args:
        recipes: List of recipe objects
        output_dir: Directory to save the index.html file
    """
    ensure_output_directory(output_dir)

    filepath = os.path.join(output_dir, "index.html")
    current_date = datetime.now().strftime("%d.%m.%Y")

    html_content = f"""<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Rezeptsammlung</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 1000px;
            margin: 0 auto;
            padding: 20px;
            line-height: 1.6;
            color: #333;
            background: #fafafa;
        }}
        .header {{
            text-align: center;
            margin-bottom: 40px;
            padding: 30px 0;
            background: white;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .recipe-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 20px;
        }}
        .recipe-card {{
            background: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            transition: transform 0.2s, box-shadow 0.2s;
            text-decoration: none;
            color: inherit;
        }}
        .recipe-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 5px 20px rgba(0,0,0,0.15);
            text-decoration: none;
            color: inherit;
        }}
        .recipe-title {{
            font-size: 1.3em;
            font-weight: bold;
            margin-bottom: 10px;
            color: #2c3e50;
        }}
        .recipe-meta {{
            color: #666;
            font-size: 0.9em;
            margin-bottom: 15px;
        }}
        .recipe-categories {{
            display: flex;
            flex-wrap: wrap;
            gap: 5px;
        }}
        .category-tag {{
            background: #e8f4fd;
            color: #2c3e50;
            padding: 3px 8px;
            border-radius: 15px;
            font-size: 0.8em;
        }}
        .stats {{
            text-align: center;
            margin: 30px 0;
            padding: 20px;
            background: white;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .filter-section {{
            margin-bottom: 30px;
            text-align: center;
        }}
        #searchInput {{
            padding: 10px 15px;
            font-size: 16px;
            border: 2px solid #ddd;
            border-radius: 25px;
            width: 300px;
            max-width: 100%;
        }}
        @media (max-width: 600px) {{
            body {{ padding: 15px; }}
            .recipe-grid {{ grid-template-columns: 1fr; }}
            #searchInput {{ width: 100%; }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🍽️ Rezeptsammlung</h1>
        <p>Automatisch generiert aus Instagram-Posts • {len(recipes)} Rezepte • Stand: {current_date}</p>
    </div>

    <div class="filter-section">
        <input type="text" id="searchInput" placeholder="Rezepte suchen..." onkeyup="filterRecipes()">
    </div>

    <div class="stats">
        <p><strong>{len(recipes)}</strong> Rezepte verfügbar</p>
    </div>

    <div class="recipe-grid" id="recipeGrid">"""

    for recipe in recipes:
        sanitized_title = sanitize_title(recipe.title)
        filename = f"{sanitized_title}.html"

        html_content += f"""
        <a href="{filename}" class="recipe-card" data-title="{recipe.title.lower()}">
            <div class="recipe-title">{recipe.title}</div>
            <div class="recipe-meta">"""

        meta_info = []
        if recipe.servings:
            meta_info.append(f"🍽️ {recipe.servings}")
        if recipe.prep_time:
            meta_info.append(f"⏱️ {recipe.prep_time}")
        if recipe.cook_time:
            meta_info.append(f"🔥 {recipe.cook_time}")

        html_content += " • ".join(meta_info)

        html_content += """
            </div>
            <div class="recipe-categories">"""

        for category in recipe.categories[:3]:  # Show max 3 categories
            html_content += f'<span class="category-tag">{category}</span>'

        html_content += """
            </div>
        </a>"""

    html_content += """
    </div>

    <script>
        function filterRecipes() {
            const input = document.getElementById('searchInput');
            const filter = input.value.toLowerCase();
            const cards = document.getElementsByClassName('recipe-card');

            for (let i = 0; i < cards.length; i++) {
                const title = cards[i].getAttribute('data-title');
                if (title.includes(filter)) {
                    cards[i].style.display = '';
                } else {
                    cards[i].style.display = 'none';
                }
            }
        }
    </script>
</body>
</html>"""

    # Write index file
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html_content)

    logging.info(f"Generated index page: {filepath}")


def _format_json_ld(data: dict, indent: int = 8) -> str:
    """
    Format JSON-LD data with proper indentation for HTML embedding.

    Args:
        data: JSON-LD data dictionary
        indent: Number of spaces for indentation

    Returns:
        Formatted JSON-LD string
    """
    import json
    json_str = json.dumps(data, ensure_ascii=False, indent=2)
    # Add proper indentation for HTML
    lines = json_str.split('\n')
    indented_lines = [' ' * indent + line if line.strip() else line for line in lines]
    return '\n'.join(indented_lines)
