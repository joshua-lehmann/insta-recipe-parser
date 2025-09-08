# models.py
#
# Description:
# This file defines the Pydantic data models for the application.
# These models serve as a strict schema for the data we expect from the LLM,
# ensuring data consistency and validity. It also improves code readability
# and provides auto-completion benefits in IDEs.

from typing import List, Optional
from pydantic import BaseModel, Field

class Ingredient(BaseModel):
    name: str = Field(description="Name of the ingredient in German.")
    amount: str = Field(description="Quantity of the ingredient with German units (g, ml, Stk., TL, EL).")

class IngredientGroup(BaseModel):
    title: str = Field(description="Title for the ingredient group (e.g., 'Für den Teig', 'Für die Füllung'). Use 'Zutaten' for a single, ungrouped list.")
    items: List[Ingredient] = Field(description="List of ingredients in this group.")

class Nutrition(BaseModel):
    """Represents the nutritional information for a recipe per serving."""
    calories: Optional[str] = Field(None, description="Kalorien pro Portion in kcal.")
    protein: Optional[str] = Field(None, description="Protein pro Portion in g.")
    carbs: Optional[str] = Field(None, description="Kohlenhydrate pro Portion in g.")
    fat: Optional[str] = Field(None, description="Fett pro Portion in g.")

class Recipe(BaseModel):
    title: str = Field(description="Clear, descriptive title for the dish in German. If the original caption is in English, the title can be in English.")
    categories: List[str] = Field(description="List of categories: Meal type (Frühstück, Hauptgericht, Dessert, Snack, Getränk), temperature (warm, kalt), and dietary style (vegan, etc.).")
    prep_time: Optional[str] = Field(None, description="Preparation time, if mentioned (e.g., '15 min').")
    cook_time: Optional[str] = Field(None, description="Cooking time, if mentioned (e.g., '30 min').")
    servings: Optional[str] = Field(None, description="Number of servings the recipe makes, if mentioned (e.g., '4 Portionen').")
    ingredients: List[IngredientGroup] = Field(description="A list of ingredient groups. If there are no groups, use a single group with the title 'Zutaten'.")
    steps: List[str] = Field(description="A clear, step-by-step list of preparation instructions. Each step is a complete sentence.")
    notes: Optional[List[str]] = Field(None, description="Optional tips or notes about the recipe, if mentioned.")
    nutrition: Optional[Nutrition] = Field(None, description="Nutritional information per serving. Extract only if explicitly mentioned in the caption.")
    source_url: str = Field(description="The original source URL of the recipe post.")
    telegraph_url: Optional[str] = Field(None, description="The public URL of the generated recipe page for importing.")

