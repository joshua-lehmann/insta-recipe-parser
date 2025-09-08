# page_generator.py
#
# Description:
# This module is responsible for taking a structured Recipe object and
# creating a simple, public webpage for it using the Telegra.ph API.
# This provides a stable URL for each recipe that can be used for importing
# into services like Samsung Food.

import requests
import logging
from typing import Optional
from models import Recipe

TELEGRAPH_API_URL = "https://api.telegra.ph/createPage"


def create_telegraph_page(recipe: Recipe) -> Optional[str]:
    """
    Creates a public Telegra.ph page for a given recipe and returns the URL.
    """
    try:
        # Format the recipe data into a simple HTML structure for the page body.
        content_html = f"<h2>{recipe.title}</h2>"

        # Add metadata like servings, prep time, etc.
        meta_html = "<ul>"
        if recipe.servings:
            meta_html += f"<li><strong>Portionen:</strong> {recipe.servings}</li>"
        if recipe.prep_time:
            meta_html += f"<li><strong>Vorbereitung:</strong> {recipe.prep_time}</li>"
        if recipe.cook_time:
            meta_html += f"<li><strong>Kochzeit:</strong> {recipe.cook_time}</li>"
        meta_html += "</ul>"
        content_html += meta_html

        # Add ingredients, respecting the groups.
        for group in recipe.ingredients:
            content_html += f"<h4>{group.title}</h4>"
            content_html += "<ul>"
            for item in group.items:
                content_html += f"<li>{item.amount} {item.name}</li>"
            content_html += "</ul>"

        # Add preparation steps.
        content_html += "<h4>Zubereitung</h4>"
        content_html += "<ol>"
        for step in recipe.steps:
            content_html += f"<li>{step}</li>"
        content_html += "</ol>"

        # Add notes if they exist.
        if recipe.notes:
            content_html += "<h4>Notizen</h4>"
            content_html += "<ul>"
            for note in recipe.notes:
                content_html += f"<li>{note}</li>"
            content_html += "</ul>"

        # Add nutrition information if it exists.
        if recipe.nutrition:
            content_html += "<h4>Nährwerte (pro Portion)</h4>"
            nutrition_details = []
            if recipe.nutrition.calories:
                nutrition_details.append(f"<li><strong>Kalorien:</strong> {recipe.nutrition.calories} kcal</li>")
            if recipe.nutrition.protein:
                nutrition_details.append(f"<li><strong>Protein:</strong> {recipe.nutrition.protein} g</li>")
            if recipe.nutrition.carbs:
                nutrition_details.append(f"<li><strong>Kohlenhydrate:</strong> {recipe.nutrition.carbs} g</li>")
            if recipe.nutrition.fat:
                nutrition_details.append(f"<li><strong>Fett:</strong> {recipe.nutrition.fat} g</li>")

            if nutrition_details:
                content_html += f"<ul>{''.join(nutrition_details)}</ul>"

        # Add the source link back to Instagram.
        content_html += f"<p><a href='{recipe.source_url}'>Original Post auf Instagram</a></p>"

        # The Telegra.ph API requires the content in a specific JSON format.
        # We wrap our HTML in 'node' elements.
        content_for_api = [{"tag": "p", "children": [content_html]}]

        response = requests.post(
            TELEGRAPH_API_URL,
            json={
                "access_token": "d50da871b3383637b273b32085a53586a3479101a84f52636657a26f7bf2",
                # This is a public, anonymous token
                "title": recipe.title,
                "author_name": "Instagram Recipe Parser",
                "content": content_for_api,
                "return_content": True,
            },
            timeout=15
        )
        response.raise_for_status()
        data = response.json()

        if data.get("ok"):
            page_url = data["result"]["url"]
            logging.info(f"Successfully created Telegra.ph page for '{recipe.title}': {page_url}")
            return page_url
        else:
            logging.error(f"Failed to create Telegra.ph page: {data.get('error')}")
            return None

    except requests.exceptions.RequestException as e:
        logging.error(f"Error communicating with Telegra.ph API: {e}")
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred during page generation: {e}")
        return None

