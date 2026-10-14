from typing import Literal, Optional
from pydantic import BaseModel, Field, model_validator

Unit = Literal[
    "g", "kg", "oz", "lb",                       # weight
    "ml", "l", "tsp", "tbsp", "cup", "fl_oz",    # volume
    "each", "clove", "can", "bunch", "pinch", "dash", "slice", "stick",
]

SourceType = Literal["description", "linked_recipe", "transcript",
                     "user_caption", "audio_stt", "frame_ocr"]

# Field descriptions are sent to the LLM as part of the JSON schema, so they double as extraction instructions.

class Quantity(BaseModel):
    min: Optional[float] = Field(
        None, description="Lower bound as a decimal. '2-3 cloves' -> 2. Exact amounts: min == max. "
                          "Null when the line has no number.")
    max: Optional[float] = Field(None, description="Upper bound as a decimal. '2-3 cloves' -> 3.")
    unit: Optional[Unit] = Field(
        None, description="Unit exactly as written; never convert or estimate weights ('1 tsp' stays tsp). "
                          "If the line gives two amounts, use the first and ignore the equivalent: "
                          "'2 cups (480mL)' -> 2 cup, '500g/ 1lb' -> 500 g. Counts of whole items are 'each', "
                          "including count words: '2 eggs', '5-7 pods', '1-2 pieces', '5 pc', '3 numbers'. "
                          "'bundle' is 'bunch'. Any other unit not allowed ('sprig', 'quart'): keep min/max, "
                          "unit=null, and put just the unit word in qualitative ('3.5 quarts' -> 3.5, 'quarts').")
    qualitative: Optional[str] = Field(
        None, description="Non-numeric amount, verbatim: 'to taste', 'for frying', 'to garnish', 'small "
                          "bunch'; or a unit word not in the allowed units: 'sprigs'.")

class Ingredient(BaseModel):
    raw_text: str = Field(description="The source line, verbatim.")
    name: str = Field(description="Canonical shoppable item, e.g. 'garlic', 'kosher salt'. "
                                  "No amount, size or prep. If 'X or Y', the first option.")
    quantity: Quantity
    preparation: Optional[str] = Field(None, description="Prep that is not shopping-relevant: 'minced'.")
    optional: bool = Field(False, description="True if the line says optional, garnish, or 'if you like'.")
    component: Optional[str] = Field(
        None, description="Part of the recipe it belongs to ('sauce', 'marinade', 'topping'), from section "
                          "headings or context. Null if unclear.")
    sources: list[SourceType] = Field(description="Leave empty; the caller fills it.")
    confidence: float = Field(ge=0, le=1, description="How sure you are of this parse. Clean lines ~0.98.")

# Field order is generation order: long lists go last, so the model doesn't lose track of
# nesting after them (gpt-oss-20b put top-level fields inside `recipe` when they came after it).

class Recipe(BaseModel):
    title: str
    servings: Optional[int] = Field(None, description="Only if the text states it, else null.")
    equipment: list[str] = []        # optional: "air fryer"
    ingredients: list[Ingredient] = Field(
        description="Every ingredient in the text, in order: one entry per ingredient line, including "
                    "lines without amounts ('Salt to taste'). A line naming several items ('Cilantro, mint, "
                    "lemon juice to garnish') gives one entry per item. Skip headings, instructions and "
                    "lines that only refer back to earlier ingredients. Don't merge or invent.")

class ExtractionResult(BaseModel):
    status: Literal["ok", "partial", "not_a_recipe"] = Field(
        description="'ok' if ingredients were parsed; 'not_a_recipe' (recipe null) if the text is not an "
                    "ingredient list.")
    missing: list[str] = Field([], description="What the text lacked: 'quantities for 3 items', 'servings'.")
    notes: Optional[str] = None      # e.g. "transcript and caption disagree on sugar"
    recipe: Optional[Recipe] = None

    @model_validator(mode="after")
    def recipe_required_when_ok(self):
        if self.status != "not_a_recipe" and not self.recipe:
            raise ValueError("recipe required unless not_a_recipe")
        return self
