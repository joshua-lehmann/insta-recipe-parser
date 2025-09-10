# site_generator.py
#
# Description:
# This module handles the creation of static HTML pages for GitHub Pages hosting.
# It generates individual recipe pages with a tabbed interface to compare model outputs
# and creates an index page listing all recipes with model performance statistics.

import json
import logging
import os
import re
from datetime import datetime
from typing import Dict, Any
from urllib.parse import urlparse

import requests

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


def get_recipe_data(recipe_info, version='current'):
    """Extract recipe data from versioned or legacy format."""
    # Debug the structure of the recipe_info to understand what we're working with
    if isinstance(recipe_info, dict):
        keys = list(recipe_info.keys())
        if 'current' in keys:
            logging.debug(f"Recipe info has versioned format with keys: {keys}")
            if 'history' in keys:
                history_length = len(recipe_info.get('history', []))
                logging.debug(f"History has {history_length} items")
                if history_length > 0:
                    # Log timestamps of historical versions
                    timestamps = [item.get('timestamp') for item in recipe_info['history'] if item.get('timestamp')]
                    logging.debug(f"Available timestamps in history: {timestamps}")
        else:
            logging.debug(f"Recipe info has keys {keys} but no 'current' key")

    if isinstance(recipe_info, dict) and 'current' in recipe_info:
        # New versioned format
        if version == 'current':
            return recipe_info['current']
        else:
            # Look for specific version in history
            for hist_item in recipe_info.get('history', []):
                if hist_item.get('timestamp') == version:
                    logging.debug(f"Found version {version} in history")
                    return hist_item
            # Fallback to current if the specific version wasn't found
            logging.debug(f"Version {version} not found in history, using current")
            return recipe_info['current']
    else:
        # Legacy format
        logging.debug("Using legacy format (not versioned)")
        return recipe_info


def get_available_versions(recipe_info):
    """Get a list of all available versions for a recipe."""
    versions = []

    if isinstance(recipe_info, dict) and 'current' in recipe_info:
        # Always include current
        current_version = recipe_info['current'].get('timestamp')
        if current_version:
            versions.append(('current', current_version))

        # Add all historical versions
        for hist_item in recipe_info.get('history', []):
            if timestamp := hist_item.get('timestamp'):
                versions.append((timestamp, timestamp))

    return versions


def generate_recipe_page(recipes_by_model: dict, output_dir: str, post_data: dict, requested_version: str = 'current'):
    """
    Generate an individual HTML page for a recipe with tabs for each model.

    Args:
        recipes_by_model: Dictionary mapping model names to recipe data
        output_dir: Directory to save the HTML file
        post_data: Data about the Instagram post
        requested_version: Version to display (timestamp or 'current')
    """
    if not recipes_by_model:
        logging.warning(f"No recipes provided for HTML generation of {post_data['url']}.")
        return

    os.makedirs(output_dir, exist_ok=True)

    # Use the first recipe for common metadata, but a stable ID for the filename
    first_model_name = next(iter(recipes_by_model))
    first_recipe_data = get_recipe_data(recipes_by_model[first_model_name], requested_version)
    recipe_for_meta = Recipe(**first_recipe_data['data'])

    filename_base = get_stable_filename_base(post_data['url'])
    filename = f"{filename_base}.html"
    filepath = os.path.join(output_dir, filename)

    local_image_path = download_image(post_data.get('thumbnail_url'), output_dir, filename_base)
    thumbnail_html = f'<div class="recipe-thumbnail"><img src="{local_image_path}" alt="Rezeptbild" loading="lazy"></div>' if local_image_path else ""

    json_ld = create_json_ld(recipe_for_meta)

    # Check if any model has multiple versions and collect all timestamps
    has_versions = False
    all_versions = set(['current'])  # Always include 'current'

    # Debug information
    logging.debug(f"Checking for multiple versions in {len(recipes_by_model)} models")

    for model_name, model_info in recipes_by_model.items():
        # Debug the structure of each model's data
        if isinstance(model_info, dict):
            history_length = len(model_info.get('history', []))
            logging.debug(
                f"Model {model_name}: has 'history' key: {('history' in model_info)}, history length: {history_length}")

            if 'history' in model_info and history_length > 0:
                has_versions = True
                # Add all version timestamps from this model's history
                for hist_item in model_info.get('history', []):
                    if timestamp := hist_item.get('timestamp'):
                        all_versions.add(timestamp)
                        logging.debug(f"Added timestamp {timestamp} from model {model_name}")

    # Generate version selector if needed
    version_selector_html = ''
    sorted_versions = sorted([v for v in all_versions if v != 'current'], reverse=True)
    logging.debug(f"Found {len(sorted_versions)} historical versions: {sorted_versions}")

    # Always include the version selector, even if there's just one option
    # This will make it clear to users that versioning is supported
    if True:  # was: has_versions or getattr(config, 'FORCE_REPROCESS_LLM', False)
        options_html = '<option value="current">Latest (Current)</option>'
        # Add options for all historical versions, sorted chronologically (newest first)
        for version in sorted_versions:
            options_html += f'<option value="{version}">{version}</option>'

        version_selector_html = f'''
        <div class="version-selector">
            <label for="versionSelect">Version: </label>
            <select id="versionSelect" onchange="changeVersion()">
                {options_html}
            </select>
        </div>
        '''

    # --- Tab Generation ---
    tab_links_html = ''
    tab_contents_html = ''
    is_first_tab = True
    for model_name, model_info in recipes_by_model.items():
        # Get data for the requested version (or current if that version doesn't exist for this model)
        recipe_data = get_recipe_data(model_info, requested_version)
        recipe = Recipe(**recipe_data['data'])
        processing_time = recipe_data.get('processing_time')

        active_class = "active" if is_first_tab else ""
        tab_id = sanitize_title(model_name)
        tab_links_html += f'<button class="tab-link {active_class}" onclick="openTab(event, \'{tab_id}\')">{model_name}</button>'

        display_style = "display: block;" if is_first_tab else ""

        # Generate content for current version
        # Add data attributes for all versions of this model
        version_data_attrs = ''
        if isinstance(model_info, dict) and 'current' in model_info:
            # Current version timestamp
            current_timestamp = recipe_data.get('timestamp', '')
            if current_timestamp:
                version_data_attrs += f' data-version-current="{current_timestamp}"'

            # Add data attributes for historical versions
            for i, hist_item in enumerate(model_info.get('history', [])):
                if timestamp := hist_item.get('timestamp'):
                    version_data_attrs += f' data-version-{timestamp}="true"'

        tab_contents_html += f"""
        <div id="{tab_id}" class="tab-content" style="{display_style}" data-model="{model_name}"{version_data_attrs}>
            <div class="recipe-header">
                <h1>{recipe.title}</h1>
                <div class="recipe-meta">
                    {f'<span>🍽️ {recipe.servings}</span>' if recipe.servings else ''}
                    {f'<span>⏱️ {recipe.prep_time}</span>' if recipe.prep_time and recipe.prep_time != "Nicht angegeben" else ''}
                    {f'<span>🔥 {recipe.cook_time}</span>' if recipe.cook_time and recipe.cook_time != "Nicht angegeben" else ''}
                    {f'<span><strong>🤖 Zeit:</strong> {processing_time:.2f}s</span>' if processing_time is not None else ''}
                    {f'<span><strong>📅 Version:</strong> {recipe_data.get("timestamp", "N/A")}</span>' if recipe_data.get("timestamp") else ''}
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
                    {f'<div class="nutrition-item"><strong>{recipe.nutrition.calories}</strong><br>Kalorien</div>' if recipe.nutrition and recipe.nutrition.calories else ''}
                    {f'<div class="nutrition-item"><strong>{recipe.nutrition.protein}</strong><br>Protein</div>' if recipe.nutrition and recipe.nutrition.protein else ''}
                    {f'<div class="nutrition-item"><strong>{recipe.nutrition.carbs}</strong><br>Kohlenhydrate</div>' if recipe.nutrition and recipe.nutrition.carbs else ''}
                    {f'<div class="nutrition-item"><strong>{recipe.nutrition.fat}</strong><br>Fett</div>' if recipe.nutrition and recipe.nutrition.fat else ''}
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

        # Original caption with emojis
        if post_data.get('caption'):
            original_caption_html = clean_caption_text(post_data['caption'])
            source_box_html += f'<button type="button" class="collapsible">📝 Original Caption</button><div class="caption-content"><p>{original_caption_html}</p></div>'

        # Cleaned caption without emojis (if available)
        if post_data.get('cleaned_caption'):
            cleaned_caption_html = clean_caption_text(post_data['cleaned_caption'])
            source_box_html += f'<button type="button" class="collapsible">🧹 Cleaned Caption (Used for Processing)</button><div class="caption-content"><p>{cleaned_caption_html}</p></div>'

        source_box_html += '</div>'

    # --- Prepare Version Data for JavaScript ---
    version_data_json = {}
    for model_name, model_info in recipes_by_model.items():
        model_versions = {}

        # Current version
        current_data = get_recipe_data(model_info, 'current')
        if current_data:
            model_versions['current'] = {
                'timestamp': current_data.get('timestamp', ''),
                'title': Recipe(**current_data['data']).title,
                'processing_time': current_data.get('processing_time')
            }

        # Historical versions
        if isinstance(model_info, dict) and 'history' in model_info:
            for hist_item in model_info.get('history', []):
                if timestamp := hist_item.get('timestamp'):
                    model_versions[timestamp] = {
                        'timestamp': timestamp,
                        'title': Recipe(**hist_item['data']).title,
                        'processing_time': hist_item.get('processing_time')
                    }

        if model_versions:
            version_data_json[model_name] = model_versions

    # --- Final HTML Assembly ---
    html_content = f"""<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{recipe_for_meta.title}</title>
    <script type="application/ld+json">{json.dumps(json_ld, ensure_ascii=False, indent=4)}</script>
    <script>
        // Store version data for JavaScript usage
        const versionData = {json.dumps(version_data_json, ensure_ascii=False)};
    </script>
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
        .version-selector {{ text-align: center; margin-bottom: 15px; padding: 10px; background: #f8f9fa; border-radius: 8px; }}
        .version-selector label {{ font-weight: bold; margin-right: 10px; }}
        .version-selector select {{ padding: 5px 10px; border: 1px solid #ddd; border-radius: 4px; }}
    </style>
</head>
<body>
    <a href="index.html" class="back-link">← Zurück zur Rezeptliste</a>
    {version_selector_html}
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

        function changeVersion() {{
            const selectedVersion = document.getElementById('versionSelect').value;
            const currentUrl = new URL(window.location.href);

            // Update URL parameter
            if (selectedVersion === 'current') {{
                currentUrl.searchParams.delete('version');
            }} else {{
                currentUrl.searchParams.set('version', selectedVersion);
            }}

            // Reload the page with the new version parameter
            window.location.href = currentUrl.toString();
        }}

        // Initialize version selection on page load
        document.addEventListener('DOMContentLoaded', function() {{
            const urlParams = new URLSearchParams(window.location.search);
            const versionParam = urlParams.get('version');

            if (versionParam) {{
                const select = document.getElementById('versionSelect');
                if (select) {{
                    for (let i = 0; i < select.options.length; i++) {{
                        if (select.options[i].value === versionParam) {{
                            select.selectedIndex = i;
                            break;
                        }}
                    }}
                }}
            }}
        }});

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

    # Log more detailed information for debugging
    version_info = f" (version: {requested_version})" if requested_version != 'current' else ""
    available_versions = len(sorted_versions) + 1  # +1 for current
    logging.info(
        f"Generated comparison recipe page: {filepath}{version_info} with {available_versions} versions available")

    # Print console message about versions to make debugging easier
    if sorted_versions:
        logging.debug(f"Recipe {filepath} has {len(sorted_versions)} historical versions: {sorted_versions}")
    else:
        logging.debug(f"Recipe {filepath} has no historical versions")


def generate_index_page(all_progress_data: Dict[str, Any], output_dir: str):
    """Generate an index page listing all recipes and model performance stats."""
    os.makedirs(output_dir, exist_ok=True)

    # --- Calculate Model Stats ---
    model_stats = {}
    for post_data in all_progress_data.values():
        for model_name, model_info in post_data.get('recipes', {}).items():
            current_data = get_recipe_data(model_info, 'current')
            if 'processing_time' in current_data:
                stats = model_stats.setdefault(model_name, {'total_time': 0, 'count': 0})
                stats['total_time'] += current_data['processing_time']
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
                          key=lambda p: get_recipe_data(next(iter(p.get('recipes', {}).values()), {}))['data'].get(
                              'title', 'Z').lower())

    for post_data in sorted_posts:
        if not post_data.get('recipes'): continue

        # Use the first available model's data for the card
        first_model_info = next(iter(post_data['recipes'].values()))
        first_recipe_data = get_recipe_data(first_model_info, 'current')['data']
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
