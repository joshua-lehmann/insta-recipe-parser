# site_generator.py
#
# Description:
# This module handles the creation of static HTML pages for GitHub Pages hosting.
# It generates individual recipe pages with proper schema.org JSON-LD structured data
# and creates an index page listing all recipes.

import logging
import os
import re
import json
from typing import List
from datetime import datetime
from urllib.parse import quote

from models import Recipe


def sanitize_title(title: str) -> str:
    """
    Sanitizes the recipe title for safe filename usage.
    """
    replacements = {
        'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'ß': 'ss',
        'Ä': 'Ae', 'Ö': 'Oe', 'Ü': 'Ue',
        'é': 'e', 'è': 'e', 'ê': 'e', 'à': 'a', 'ç': 'c'
    }
    for umlaut, replacement in replacements.items():
        title = title.replace(umlaut, replacement)

    title = re.sub(r'[^\w\s-]', '', title)
    title = re.sub(r'[-\s]+', '-', title).strip('-').lower()
    return title


def convert_time_to_iso8601(time_str: str) -> str:
    """
    Convert German time format to ISO 8601 duration format.
    """
    if not time_str or time_str == "Nicht angegeben":
        return ""

    time_str = time_str.lower()
    hours, minutes = 0, 0
    hour_match = re.search(r'(\d+)\s*(?:stunden?|h)', time_str)
    if hour_match:
        hours = int(hour_match.group(1))
    minute_match = re.search(r'(\d+)\s*(?:minuten?|min|m)', time_str)
    if minute_match:
        minutes = int(minute_match.group(1))

    if hours == 0 and minutes == 0:
        return ""

    duration = "PT"
    if hours > 0:
        duration += f"{hours}H"
    if minutes > 0:
        duration += f"{minutes}M"
    return duration


def create_json_ld(recipe: Recipe) -> dict:
    """
    Create schema.org compliant JSON-LD structured data for a recipe.
    """
    json_ld = {
        "@context": "https://schema.org/",
        "@type": "Recipe",
        "name": recipe.title
    }

    if recipe.servings:
        json_ld["recipeYield"] = recipe.servings
    if recipe.prep_time:
        prep_iso = convert_time_to_iso8601(recipe.prep_time)
        if prep_iso: json_ld["prepTime"] = prep_iso
    if recipe.cook_time:
        cook_iso = convert_time_to_iso8601(recipe.cook_time)
        if cook_iso: json_ld["cookTime"] = cook_iso

    ingredients_list = [f"{ing.quantity} {ing.name}".strip() for group in recipe.ingredients for ing in
                        group.ingredients]
    if ingredients_list:
        json_ld["recipeIngredient"] = ingredients_list

    if recipe.steps:
        json_ld["recipeInstructions"] = [{"@type": "HowToStep", "text": step} for step in recipe.steps]

    if recipe.nutrition:
        nutrition_info = {"@type": "NutritionInformation"}
        if recipe.nutrition.calories: nutrition_info["calories"] = recipe.nutrition.calories
        if recipe.nutrition.protein: nutrition_info["proteinContent"] = recipe.nutrition.protein
        if recipe.nutrition.carbs: nutrition_info["carbohydrateContent"] = recipe.nutrition.carbs
        if recipe.nutrition.fat: nutrition_info["fatContent"] = recipe.nutrition.fat
        if len(nutrition_info) > 1: json_ld["nutrition"] = nutrition_info

    if recipe.categories:
        json_ld["keywords"] = ", ".join(recipe.categories)

    if recipe.thumbnail_url and recipe.thumbnail_url.startswith('http'):
        json_ld["image"] = [recipe.thumbnail_url]

    return json_ld


def clean_caption_text(caption: str) -> str:
    """
    Formats the raw caption text for safe HTML display by converting newlines.
    """
    if not caption:
        return ""
    formatted_caption = caption.replace('\\n', '\n').strip()
    return formatted_caption.replace('\n', '<br>')


def extract_thumbnail_from_instagram(url: str) -> str:
    """
    Extract thumbnail URL from Instagram reel/post.
    """
    try:
        import requests
        from bs4 import BeautifulSoup
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            logging.warning(f"Failed to fetch Instagram page ({response.status_code}): {url}")
            return ""
        soup = BeautifulSoup(response.content, 'html.parser')
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            return og_image['content']
        logging.warning(f"No thumbnail meta tag found for {url}")
        return ""
    except Exception as e:
        logging.error(f"Error extracting thumbnail from {url}: {e}")
        return ""


def ensure_output_directory(path: str):
    os.makedirs(path, exist_ok=True)


def generate_recipe_page(recipe: Recipe, output_dir: str) -> str:
    """Generate an individual HTML page for a recipe."""
    ensure_output_directory(output_dir)
    sanitized_title = sanitize_title(recipe.title)
    filename = f"{sanitized_title}.html"
    filepath = os.path.join(output_dir, filename)

    json_ld = create_json_ld(recipe)

    # Prepare the source and caption box HTML
    source_box_html = ''
    if recipe.source_url or recipe.original_caption:
        source_box_html = '<div class="source-link-box">'
        source_box_html += '<h3 style="margin: 0 0 10px 0;">📱 Original auf Instagram</h3>'
        if recipe.source_url:
            source_box_html += f'<p style="margin: 0 0 15px 0;"><a href="{recipe.source_url}" target="_blank" rel="noopener">🔗 Link zum Reel</a></p>'
        if recipe.original_caption:
            cleaned_caption = clean_caption_text(recipe.original_caption)
            source_box_html += f"""
        <button type="button" class="collapsible">📝 Original Caption anzeigen</button>
        <div class="caption-content">
            <p>{cleaned_caption}</p>
        </div>"""
        source_box_html += '</div>'

    html_content = f"""<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{recipe.title}</title>
    <script type="application/ld+json">
{json.dumps(json_ld, ensure_ascii=False, indent=8)}
    </script>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 800px; margin: 0 auto; padding: 15px; line-height: 1.5; color: #333; background-color: #fdfdfd; }}
        .recipe-header {{ padding-bottom: 8px; margin-bottom: 8px; }}
        h1 {{ font-size: 2.2em; margin-bottom: 8px; text-align: center;}}
        h2 {{ border-bottom: 2px solid #eee; padding-bottom: 8px; margin-top: 15px; margin-bottom: 15px; color: #2c3e50; }}
        .ingredients-section h2:first-of-type {{ margin-top: 10px; }}
        .recipe-meta {{ display: flex; flex-wrap: wrap; gap: 10px; margin: 10px 0 15px 0; color: #666; justify-content: center; }}
        .recipe-meta span {{ background: #f5f5f5; padding: 5px 10px; border-radius: 18px; font-size: 0.85em; }}
        ul, ol {{ padding-left: 20px; margin: 10px 0; }}
        li {{ margin: 6px 0; }}
        .ingredient-group h3 {{ color: #2c3e50; font-size: 1.1em; margin: 15px 0 8px 0; }}
        .ingredients-section, .instructions-section, .notes-section {{ margin-bottom: 20px; }}
        .nutrition-section {{ background: #f9f9f9; padding: 15px; border-radius: 10px; margin-top: 25px; }}
        .nutrition-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(110px, 1fr)); gap: 12px; margin-top: 8px; }}
        .nutrition-item {{ background: white; padding: 12px; border-radius: 6px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .back-link {{ display: inline-block; margin-bottom: 15px; color: #3498db; text-decoration: none; font-weight: bold; }}
        .back-link:hover {{ text-decoration: underline; }}
        .source-link-box {{ margin-top: 25px; padding: 15px; background: #f8f9fa; border-radius: 10px; border-left: 4px solid #e91e63; }}
        .source-link-box h3 {{ margin: 0 0 8px 0 !important; }}
        .source-link-box p {{ margin: 0 0 12px 0 !important; }}
        .source-link-box a {{ color: #e91e63; text-decoration: none; font-weight: bold; font-size: 1.05em; }}
        .collapsible {{ background-color: #eee; color: #444; cursor: pointer; padding: 12px; width: 100%; border: none; text-align: left; outline: none; font-size: 0.95em; border-radius: 6px; font-weight: bold; }}
        .collapsible:hover {{ background-color: #ddd; }}
        .collapsible.active {{ border-bottom-left-radius: 0; border-bottom-right-radius: 0; }}
        .caption-content {{ padding: 0 15px; max-height: 0; overflow: hidden; transition: max-height 0.3s ease-out; background-color: #f1f1f1; border-bottom-left-radius: 6px; border-bottom-right-radius: 6px; }}
        .caption-content p {{ margin: 15px 0; }}
        @media (max-width: 600px) {{ body {{ padding: 12px; }} h1 {{ font-size: 1.8em; }} .nutrition-grid {{ grid-template-columns: 1fr 1fr; }} }}
    </style>
</head>
<body>
    <a href="index.html" class="back-link">← Zurück zur Rezeptliste</a>

    <div class="recipe-header">
        <h1>{recipe.title}</h1>
        <div class="recipe-meta">
            {f'<span>🍽️ {recipe.servings}</span>' if recipe.servings else ''}
            {f'<span>⏱️ {recipe.prep_time}</span>' if recipe.prep_time and recipe.prep_time != "Nicht angegeben" else ''}
            {f'<span>🔥 {recipe.cook_time}</span>' if recipe.cook_time and recipe.cook_time != "Nicht angegeben" else ''}
        </div>
    </div>

    <div class="ingredients-section">
        <h2>Zutaten</h2>
        {''.join([f'''<div class="ingredient-group">
            {'<h3>' + group.group_title + '</h3>' if group.group_title and group.group_title.lower() != "zutaten" else ''}
            <ul>{''.join([f'<li>{ing.quantity or ""} {ing.name}</li>' for ing in group.ingredients])}</ul>
        </div>''' for group in recipe.ingredients])}
    </div>

    <div class="instructions-section">
        <h2>Zubereitung</h2>
        <ol>{''.join([f'<li>{step}</li>' for step in recipe.steps])}</ol>
    </div>

    {f'''<div class="notes-section">
        <h2>Notizen & Tipps</h2>
        <ul>{''.join([f'<li>{note}</li>' for note in recipe.notes])}</ul>
    </div>''' if recipe.notes else ''}

    {f'''<div class="nutrition-section">
        <h2>Nährwerte pro Portion</h2>
        <div class="nutrition-grid">
            {f'<div class="nutrition-item"><strong>{recipe.nutrition.calories}</strong><br>Kalorien</div>' if recipe.nutrition.calories else ''}
            {f'<div class="nutrition-item"><strong>{recipe.nutrition.protein}</strong><br>Protein</div>' if recipe.nutrition.protein else ''}
            {f'<div class="nutrition-item"><strong>{recipe.nutrition.carbs}</strong><br>Kohlenhydrate</div>' if recipe.nutrition.carbs else ''}
            {f'<div class="nutrition-item"><strong>{recipe.nutrition.fat}</strong><br>Fett</div>' if recipe.nutrition.fat else ''}
        </div>
    </div>''' if recipe.nutrition and any([recipe.nutrition.calories, recipe.nutrition.protein, recipe.nutrition.carbs, recipe.nutrition.fat]) else ''}

    {source_box_html}

    <script>
        document.querySelectorAll('.collapsible').forEach(button => {{
            button.addEventListener('click', function() {{
                this.classList.toggle('active');
                const content = this.nextElementSibling;
                if (content.style.maxHeight) {{
                    content.style.maxHeight = null;
                }} else {{
                    content.style.maxHeight = content.scrollHeight + 36 + 'px';
                }}
            }});
        }});
    </script>
</body>
</html>"""

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html_content)

    logging.info(f"Generated recipe page: {filepath}")
    return filename


def generate_index_page(recipes: List[Recipe], output_dir: str):
    """Generate an index page listing all recipes."""
    ensure_output_directory(output_dir)
    filepath = os.path.join(output_dir, "index.html")
    current_date = datetime.now().strftime("%d.%m.%Y")

    recipe_cards_html = []
    for recipe in sorted(recipes, key=lambda r: r.title):
        filename = sanitize_title(recipe.title) + ".html"

        card = f"""
        <a href="{filename}" class="recipe-card" data-title="{recipe.title.lower()}">
            <div class="card-content">
                <div class="recipe-title">{recipe.title}</div>
                <div class="recipe-meta">
                    {''.join([f'<span class="category-tag">{cat}</span>' for cat in recipe.categories[:3]])}
                </div>
            </div>
        </a>"""
        recipe_cards_html.append(card)

    html_content = f"""<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Rezeptsammlung</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; line-height: 1.6; color: #333; background: #f4f7f6; }}
        .header {{ text-align: center; margin-bottom: 40px; }}
        h1 {{ font-size: 3em; color: #2c3e50; }}
        .recipe-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 25px; }}
        .recipe-card {{ background: white; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.08); transition: all 0.2s ease-in-out; text-decoration: none; color: inherit; overflow: hidden; display: flex; flex-direction: column; }}
        .recipe-card:hover {{ transform: translateY(-5px); box-shadow: 0 8px 25px rgba(0,0,0,0.12); }}
        .card-content {{ padding: 20px; flex-grow: 1; }}
        .recipe-title {{ font-size: 1.2em; font-weight: bold; margin-bottom: 10px; color: #2c3e50; }}
        .recipe-meta {{ display: flex; flex-wrap: wrap; gap: 5px; }}
        .category-tag {{ background: #e8f4fd; color: #2c3e50; padding: 4px 10px; border-radius: 15px; font-size: 0.8em; }}
        #searchInput {{ padding: 12px 20px; font-size: 16px; border: 2px solid #ddd; border-radius: 25px; width: 100%; max-width: 400px; display: block; margin: 0 auto 40px auto; box-sizing: border-box; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🍽️ Meine Rezeptsammlung</h1>
        <p>{len(recipes)} Rezepte • Stand: {current_date}</p>
    </div>
    <input type="text" id="searchInput" placeholder="Rezepte suchen..." onkeyup="filterRecipes()">
    <div class="recipe-grid" id="recipeGrid">{''.join(recipe_cards_html)}</div>
    <script>
        function filterRecipes() {{
            const filter = document.getElementById('searchInput').value.toLowerCase();
            document.querySelectorAll('.recipe-card').forEach(card => {{
                const title = card.getAttribute('data-title');
                card.style.display = title.includes(filter) ? '' : 'none';
            }});
        }}
    </script>
</body>
</html>"""

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html_content)
    logging.info(f"Generated index page: {filepath}")

