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
    name: str = Field(..., description="Der Name der Zutat, z.B. 'Mehl' oder 'Tomaten'.")
    quantity: Optional[str] = Field(None, description="Die vollständige Mengenangabe, z.B. '500g', '1/2', '1 TL'.")

class IngredientGroup(BaseModel):
    """Represents a group of ingredients, e.g., 'Für den Teig'."""
    group_title: Optional[str] = Field(None, description="Der Titel der Zutatengruppe, z.B. 'Für die Sauce'.")
    ingredients: List[Ingredient] = Field(..., description="Eine Liste von Zutaten in dieser Gruppe.")

class Nutrition(BaseModel):
    """Represents the nutritional information for a recipe."""
    calories: Optional[str] = Field(None, description="Kalorien pro Portion in kcal.")
    protein: Optional[str] = Field(None, description="Protein pro Portion in g.")
    carbs: Optional[str] = Field(None, description="Kohlenhydrate pro Portion in g.")
    fat: Optional[str] = Field(None, description="Fett pro Portion in g.")

class Recipe(BaseModel):
    """The main model representing a complete, structured recipe."""
    title: str = Field(..., description="Ein kurzer, beschreibender deutscher Titel für das Gericht. Englisch beibehalten, wenn Originaltitel englisch ist.")
    servings: Optional[str] = Field(None, description="Anzahl der Portionen, die das Rezept ergibt, z.B. '2 Portionen'.")
    prep_time: Optional[str] = Field(None, description="Vorbereitungszeit, z.B. '15 Minuten'.")
    cook_time: Optional[str] = Field(None, description="Kochzeit, z.B. '30 Minuten'.")
    categories: List[str] = Field([], description="Eine Liste von Kategorien, z.B. ['Hauptgericht', 'warm', 'proteinreich'].")
    ingredients: List[IngredientGroup] = Field(..., description="Eine Liste von Zutatengruppen.")
    steps: List[str] = Field(..., description="Eine nummerierte Liste der Zubereitungsschritte.")
    notes: Optional[List[str]] = Field(None, description="Eine Liste mit zusätzlichen Notizen oder Tipps.")
    nutrition: Optional[Nutrition] = Field(None, description="Die Nährwertangaben pro Portion.")
    source_url: Optional[str] = Field(None, description="Die ursprüngliche Instagram-URL des Rezepts.")
    local_file: Optional[str] = Field(None, description="Der Dateiname der generierten HTML-Seite.")

