# models.py
#
# Description:
# This module defines the Pydantic data models used throughout the application.
# These models ensure that data, especially the output from the LLM, is structured
# correctly and consistently.

from typing import List, Optional
from pydantic import BaseModel, Field

class Ingredient(BaseModel):
    """Represents a single ingredient with its name and quantity."""
    name: str = Field(..., description="The name of the ingredient, e.g., 'Flour' or 'Tomatoes'.")
    quantity: Optional[str] = Field(None, description="The full quantity specification, e.g., '500g', '1/2', '1 tsp'.")

class IngredientGroup(BaseModel):
    """Represents a group of ingredients, e.g., 'For the dough'."""
    group_title: Optional[str] = Field(None, description="The title of the ingredient group, e.g., 'For the sauce'.")
    ingredients: List[Ingredient] = Field(..., description="A list of ingredients in this group.")

class Nutrition(BaseModel):
    """Represents the nutritional information for a recipe."""
    calories: Optional[str] = Field(None, description="Calories per serving in kcal.")
    protein: Optional[str] = Field(None, description="Protein per serving in g.")
    carbs: Optional[str] = Field(None, description="Carbohydrates per serving in g.")
    fat: Optional[str] = Field(None, description="Fat per serving in g.")

class Recipe(BaseModel):
    """The main model representing a complete, structured recipe."""
    title: str = Field(..., description="A short, descriptive title for the dish. Keep in original language.")
    servings: Optional[str] = Field(None, description="The number of portions the recipe yields, e.g., '2 portions'.")
    prep_time: Optional[str] = Field(None, description="Preparation time, e.g., '15 minutes'.")
    cook_time: Optional[str] = Field(None, description="Cooking time, e.g., '30 minutes'.")
    categories: List[str] = Field([], description="A list of categories, e.g., ['Main Course', 'Warm', 'High Protein'].")
    ingredients: List[IngredientGroup] = Field(..., description="A list of ingredient groups.")
    steps: List[str] = Field(..., description="A list of the preparation steps.")
    notes: Optional[List[str]] = Field(None, description="A list of additional notes or tips.")
    nutrition: Optional[Nutrition] = Field(None, description="Nutritional information per serving.")
    source_url: Optional[str] = Field(None, description="The original Instagram URL of the recipe.")
    local_file: Optional[str] = Field(None, description="The filename of the generated HTML page.")
    original_caption: Optional[str] = Field(None, description="The original Instagram caption as a backup.")
    thumbnail_url: Optional[str] = Field(None, description="URL of the preview image from the Instagram Reel.")