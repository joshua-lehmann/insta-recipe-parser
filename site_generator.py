# site_generator.py
#
# Description:
# This module handles the creation of static HTML pages for GitHub Pages hosting.
# It generates individual recipe pages with a tabbed interface to compare model outputs
# and creates an index page listing all recipes with model performance statistics.

import logging
import os
import re
import json
import requests
from typing import List, Dict, Any
from datetime import datetime
from urllib.parse import urlparse

from models import Recipe


def get_stable_filename_base(url: str) -> str:
    """Creates a stable filename base from the Instagram post URL's shortcode."""
    try:
        path = urlparse(url).path
        # Path is typically /p/{shortcode}/ or /reel/{shortcode}/
        parts = [p for p in path.split('/') if p]
        if len(parts) >= 2 and parts[0] in ['p', 'reel', 'reels']:
            shortcode = parts[1]
            # Sanitize the shortcode just in case, though it should be safe
            return f"recipe-{re.sub(r'[^a-zA-Z0-9_-]', '', shortcode)}"
    except Exception as e:
        logging.warning(f"Could not parse shortcode from URL {url}: {e}. Using hash as fallback.")
    # If parsing fails, use a hash of the URL as a stable fallback
    return f"recipe-{abs(hash(url))}"


def sanitize_title(title: str) -> str:
    """Sanitizes the recipe title for safe filename usage."""
    replacements = {
        'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'ß': 'ss',
        'Ä': 'Ae', 'Ö': 'Oe', 'Ü': 'Ue',
        'é': 'e', 'è': 'e', 'ê': 'e', 'à': 'a', 'ç': 'c'
    }
    for umlaut, replacement in replacements.items():
        title = title.replace(umlaut, replacement)
    title = re.sub(r'[^\w\s-]', '', title).strip()
    title = re.sub(r'[-\s]+', '-', title).strip('-').lower()
    return title


def convert_time_to_iso8601(time_str: str) -> str:
    """Convert German time format to ISO 8601 duration format."""
    if not time_str or time_str == "Nicht angegeben": return ""
    time_str = time_str.lower()
    h = re.search(r'(\d+)\s*(?:stunden?|h)', time_str)
    m = re.search(r'(\d+)\s*(?:minuten?|min|m)', time_str)
    hours = int(h.group(1)) if h else 0
    minutes = int(m.group(1)) if m else 0
    if hours == 0 and minutes == 0: return ""
    duration = "PT"
    if hours > 0: duration += f"{hours}H"
    if minutes > 0: duration += f"{minutes}M"
    return duration


def create_json_ld(recipe: Recipe) -> dict:
    """Create schema.org compliant JSON-LD structured data for a recipe."""
    json_ld = {"@context": "https://schema.org/", "@type": "Recipe", "name": recipe.title}
    if recipe.servings: json_ld["recipeYield"] = recipe.servings
    if recipe.prep_time:
        if iso_prep := convert_time_to_iso8601(recipe.prep_time): json_ld["prepTime"] = iso_prep
    if recipe.cook_time:
        if iso_cook := convert_time_to_iso8601(recipe.cook_time): json_ld["cookTime"] = iso_cook
    if recipe.ingredients:
        json_ld["recipeIngredient"] = [f"{ing.quantity} {ing.name}".strip() for grp in recipe.ingredients for ing in
                                       grp.ingredients]
    if recipe.steps:
        json_ld["recipeInstructions"] = [{"@type": "HowToStep", "text": step} for step in recipe.steps]
    if recipe.nutrition:
        info = {"@type": "NutritionInformation"}
        if recipe.nutrition.calories: info["calories"] = recipe.nutrition.calories
        if recipe.nutrition.protein: info["proteinContent"] = recipe.nutrition.protein
        if recipe.nutrition.carbs: info["carbohydrateContent"] = recipe.nutrition.carbs
        if recipe.nutrition.fat: info["fatContent"] = recipe.nutrition.fat
        if len(info) > 1: json_ld["nutrition"] = info
    if recipe.categories: json_ld["keywords"] = ", ".join(recipe.categories)
    if recipe.thumbnail_url and recipe.thumbnail_url.startswith('http'):
        json_ld["image"] = [recipe.thumbnail_url]
    return json_ld


def clean_caption_text(caption: str) -> str:
    """Formats the raw caption text for safe HTML display."""
    return caption.replace('\\n', '\n').strip().replace('\n', '<br>') if caption else ""


def download_image(url: str, output_dir: str, filename_base: str) -> str | None:
    """Downloads an image from a URL and saves it locally using a stable filename base."""
    if not url or not url.startswith('http'): return None
    try:
        image_filename = f"{filename_base}.jpg"
        image_path = os.path.join(output_dir, "images", image_filename)
        local_image_ref = f"images/{image_filename}"
        os.makedirs(os.path.join(output_dir, "images"), exist_ok=True)
        if os.path.exists(image_path):
            logging.debug(f"Image already exists for {filename_base}, skipping download.")
            return local_image_ref
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, stream=True, timeout=15, headers=headers)
        response.raise_for_status()
        with open(image_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192): f.write(chunk)
        logging.debug(f"Successfully downloaded image to {image_path}")
        return local_image_ref
    except requests.exceptions.RequestException as e:
        logging.warning(f"Failed to download image from {url}: {e}")
        return None


def generate_recipe_page(recipes_by_model: dict, output_dir: str, post_data: dict):
    """Generate an individual HTML page for a recipe with tabs for each model."""
    if not recipes_by_model:
        logging.warning(f"No recipes provided for HTML generation of {post_data['url']}.")
        return

    os.makedirs(output_dir, exist_ok=True)

    # Use the first recipe for common metadata, but a stable ID for the filename
    first_model_name = next(iter(recipes_by_model))
    recipe_for_meta = Recipe(**recipes_by_model[first_model_name]['data'])

    filename_base = get_stable_filename_base(post_data['url'])
    filename = f"{filename_base}.html"
    filepath = os.path.join(output_dir, filename)

    local_image_path = download_image(post_data.get('thumbnail_url'), output_dir, filename_base)
    thumbnail_html = f'<div class="recipe-thumbnail"><img src="{local_image_path}" alt="Rezeptbild" loading="lazy"></div>' if local_image_path else ""

    json_ld = create_json_ld(recipe_for_meta)

    # --- Tab Generation ---
    tab_links_html = ''
    tab_contents_html = ''
    is_first_tab = True
    for model_name, result in recipes_by_model.items():
        recipe = Recipe(**result['data'])
        processing_time = result.get('processing_time')

        active_class = "active" if is_first_tab else ""
        tab_id = sanitize_title(model_name)
        tab_links_html += f'<button class="tab-link {active_class}" onclick="openTab(event, \'{tab_id}\')">{model_name}</button>'

        display_style = "display: block;" if is_first_tab else ""

        tab_contents_html += f"""
        <div id="{tab_id}" class="tab-content" style="{display_style}">
            <div class="recipe-header">
                <h1>{recipe.title}</h1>
                <div class="recipe-meta">
                    {f'<span>🍽️ {recipe.servings}</span>' if recipe.servings else ''}
                    {f'<span>⏱️ {recipe.prep_time}</span>' if recipe.prep_time and recipe.prep_time != "Nicht angegeben" else ''}
                    {f'<span>🔥 {recipe.cook_time}</span>' if recipe.cook_time and recipe.cook_time != "Nicht angegeben" else ''}
                    {f'<span><strong>🤖 Zeit:</strong> {processing_time:.2f}s</span>' if processing_time is not None else ''}
                </div>
            </div>
            <div class="content-wrapper">
                {thumbnail_html}
                <div class="ingredients-section">
                    <h2>Zutaten</h2>
                    {''.join([f'''<div class="ingredient-group">
                        {'<h3>' + g.group_title + '</h3>' if g.group_title and g.group_title.lower() != "zutaten" else ''}
                        <ul>{''.join([f'<li>{i.quantity or ""} {i.name}</li>' for i in g.ingredients])}</ul>
                    </div>''' for g in recipe.ingredients])}
                </div>
                <div class="instructions-section">
                    <h2>Zubereitung</h2>
                    <ol>{''.join([f'<li>{step}</li>' for step in recipe.steps])}</ol>
                </div>
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
        </div>
        """
        is_first_tab = False

    # --- Source Box (Common to all tabs) ---
    source_box_html = ''
    if post_data.get('url') or post_data.get('caption'):
        source_box_html = '<div class="source-link-box"><h3 style="margin: 0 0 10px 0;">📱 Original auf Instagram</h3>'
        if post_data.get('url'):
            source_box_html += f'<p style="margin: 0 0 15px 0;"><a href="{post_data["url"]}" target="_blank" rel="noopener">🔗 Link zum Reel</a></p>'
        if post_data.get('caption'):
            cleaned_caption = clean_caption_text(post_data['caption'])
            source_box_html += f'<button type="button" class="collapsible">📝 Original Caption</button><div class="caption-content"><p>{cleaned_caption}</p></div>'
        source_box_html += '</div>'

    # --- Final HTML Assembly ---
    html_content = f"""<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{recipe_for_meta.title}</title>
    <script type="application/ld+json">{json.dumps(json_ld, ensure_ascii=False, indent=4)}</script>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; line-height: 1.6; color: #333; background-color: #fdfdfd; }}
        h1 {{ font-size: 2.2em; margin-bottom: 8px; text-align: center;}} h2 {{ border-bottom: 2px solid #eee; padding-bottom: 8px; margin-top: 25px; }}
        .tabs {{ overflow: hidden; border-bottom: 2px solid #ccc; margin-bottom: 20px; display: flex; justify-content: center; gap: 5px;}}
        .tab-link {{ background-color: #f1f1f1; border: 1px solid #ccc; border-bottom: none; outline: none; cursor: pointer; padding: 12px 18px; transition: 0.3s; font-size: 1em; border-radius: 8px 8px 0 0; }}
        .tab-link:hover {{ background-color: #ddd; }}
        .tab-link.active {{ background-color: #fff; border-color: #ccc; border-bottom: 2px solid #fff; position: relative; top: 2px; }}
        .tab-content {{ display: none; padding: 6px 12px; border-top: none; }}
        .recipe-header {{ padding-bottom: 8px; margin-bottom: 8px; }}
        .recipe-meta {{ display: flex; flex-wrap: wrap; gap: 12px; margin: 10px 0 15px 0; color: #666; justify-content: center; }}
        .recipe-meta span {{ background: #f5f5f5; padding: 6px 12px; border-radius: 18px; font-size: 0.9em; }}
        ul, ol {{ padding-left: 20px; }} li {{ margin: 8px 0; }}
        .ingredient-group h3 {{ font-size: 1.1em; margin: 15px 0 8px 0; }}
        .content-wrapper {{ display: flow-root; }}
        .recipe-thumbnail {{ float: right; width: 300px; max-width: 40%; margin: 5px 0 15px 20px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); }}
        .recipe-thumbnail img {{ width: 100%; height: auto; display: block; border-radius: 12px; }}
        @media (max-width: 768px) {{ .recipe-thumbnail {{ float: none; width: 100%; max-width: 300px; margin: 15px auto; }} }}
        .nutrition-section {{ background: #f9f9f9; padding: 15px; border-radius: 10px; margin-top: 25px; }}
        .nutrition-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(110px, 1fr)); gap: 12px; margin-top: 8px; }}
        .nutrition-item {{ background: white; padding: 12px; border-radius: 6px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .back-link {{ display: inline-block; margin-bottom: 15px; color: #3498db; text-decoration: none; font-weight: bold; }}
        .source-link-box {{ margin-top: 25px; padding: 15px; background: #f8f9fa; border-left: 4px solid #e91e63; border-radius: 10px;}}
        .collapsible {{ background-color: #eee; cursor: pointer; padding: 12px; width: 100%; border: none; text-align: left; font-size: 0.95em; border-radius: 6px; font-weight: bold; }}
        .caption-content {{ padding: 0 15px; max-height: 0; overflow: hidden; transition: max-height 0.3s ease-out; background-color: #f1f1f1; }}
    </style>
</head>
<body>
    <a href="index.html" class="back-link">← Zurück zur Rezeptliste</a>
    <div class="tabs">{tab_links_html}</div>
    {tab_contents_html}
    {source_box_html}
    <script>
        function openTab(evt, tabId) {{
            document.querySelectorAll('.tab-content').forEach(tc => tc.style.display = "none");
            document.querySelectorAll('.tab-link').forEach(tl => tl.classList.remove('active'));
            document.getElementById(tabId).style.display = "block";
            evt.currentTarget.classList.add('active');
        }}
        document.querySelectorAll('.collapsible').forEach(btn => {{
            btn.addEventListener('click', function() {{
                this.classList.toggle('active');
                const content = this.nextElementSibling;
                content.style.maxHeight = content.style.maxHeight ? null : content.scrollHeight + 30 + 'px';
            }});
        }});
    </script>
</body>
</html>"""
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html_content)
    logging.info(f"Generated comparison recipe page: {filepath}")


def generate_index_page(all_progress_data: Dict[str, Any], output_dir: str):
    """Generate an index page listing all recipes and model performance stats."""
    os.makedirs(output_dir, exist_ok=True)

    # --- Calculate Model Stats ---
    model_stats = {}
    for post_data in all_progress_data.values():
        for model_name, result in post_data.get('recipes', {}).items():
            if 'processing_time' in result:
                stats = model_stats.setdefault(model_name, {'total_time': 0, 'count': 0})
                stats['total_time'] += result['processing_time']
                stats['count'] += 1

    stats_html = '<div class="stats-grid">'
    for model, data in sorted(model_stats.items()):
        avg_time = (data['total_time'] / data['count']) if data['count'] > 0 else 0
        stats_html += f'<div class="stat-card"><h3>{model}</h3><p><strong>{avg_time:.2f}s</strong> / Rezept</p><span>({data["count"]} Rezepte)</span></div>'
    stats_html += '</div>'

    # --- Generate Recipe Cards ---
    recipe_cards_html = []

    # Sort recipes by title alphabetically
    sorted_posts = sorted(all_progress_data.values(),
                          key=lambda p: next(iter(p.get('recipes', {}).values()), {}).get('data', {}).get('title',
                                                                                                          'Z').lower())

    for post_data in sorted_posts:
        if not post_data.get('recipes'): continue

        # Use the first available model's data for the card
        first_recipe_data = next(iter(post_data['recipes'].values()))['data']
        recipe = Recipe(**first_recipe_data)

        filename = get_stable_filename_base(post_data['url']) + ".html"
        card = f"""<a href="{filename}" class="recipe-card" data-title="{recipe.title.lower()}">
            <div class="card-content">
                <div class="recipe-title">{recipe.title}</div>
                <div class="recipe-meta">{''.join([f'<span class="category-tag">{cat}</span>' for cat in recipe.categories[:3]])}</div>
            </div>
        </a>"""
        recipe_cards_html.append(card)

    html_content = f"""<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Rezeptsammlung</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; background: #f4f7f6; }}
        .header, .stats-section {{ text-align: center; margin-bottom: 40px; }}
        h1 {{ font-size: 3em; color: #2c3e50; }} h2 {{ color: #34495e; }}
        .stats-grid {{ display: flex; flex-wrap: wrap; justify-content: center; gap: 20px; }}
        .stat-card {{ background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.07); min-width: 200px; }}
        .stat-card h3 {{ margin: 0 0 10px; }} .stat-card p {{ font-size: 1.5em; margin: 0; }} .stat-card span {{ font-size: 0.9em; color: #7f8c8d; }}
        .recipe-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 25px; }}
        .recipe-card {{ background: white; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.08); transition: all 0.2s; text-decoration: none; color: inherit; }}
        .recipe-card:hover {{ transform: translateY(-5px); box-shadow: 0 8px 25px rgba(0,0,0,0.12); }}
        .card-content {{ padding: 20px; }}
        .recipe-title {{ font-size: 1.2em; font-weight: bold; margin-bottom: 10px; color: #2c3e50; }}
        .recipe-meta {{ display: flex; flex-wrap: wrap; gap: 5px; }}
        .category-tag {{ background: #e8f4fd; color: #2c3e50; padding: 4px 10px; border-radius: 15px; font-size: 0.8em; }}
        #searchInput {{ padding: 12px 20px; font-size: 16px; border: 2px solid #ddd; border-radius: 25px; width: 100%; max-width: 400px; display: block; margin: 40px auto; box-sizing: border-box; }}
    </style>
</head>
<body>
    <div class="header"><h1>🍽️ Meine Rezeptsammlung</h1><p>{len(recipe_cards_html)} Rezepte • Stand: {datetime.now().strftime("%d.%m.%Y")}</p></div>
    <div class="stats-section"><h2>🤖 LLM Performance</h2>{stats_html}</div>
    <input type="text" id="searchInput" placeholder="Rezepte suchen..." onkeyup="filterRecipes()">
    <div class="recipe-grid" id="recipeGrid">{''.join(recipe_cards_html)}</div>
    <script>
        function filterRecipes() {{
            const filter = document.getElementById('searchInput').value.toLowerCase();
            document.querySelectorAll('.recipe-card').forEach(card => {{
                card.style.display = card.getAttribute('data-title').includes(filter) ? '' : 'none';
            }});
        }}
    </script>
</body>
</html>"""
    with open(os.path.join(output_dir, "index.html"), 'w', encoding='utf-8') as f:
        f.write(html_content)
    logging.info(f"Generated index page: {os.path.join(output_dir, 'index.html')}")
