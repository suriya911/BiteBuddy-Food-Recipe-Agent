from pydantic import BaseModel, Field


class RecipeRecord(BaseModel):
    recipe_id: str
    source: str
    source_dataset: str
    title: str
    description: str | None = None
    cuisine: str | None = None
    cuisines: list[str] = Field(default_factory=list)
    diet: str | None = None
    total_time_minutes: int | None = None
    prep_time_minutes: int | None = None
    cook_time_minutes: int | None = None
    servings: str | None = None
    ingredients: list[str] = Field(default_factory=list)
    instructions: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    rating: float | None = None
    image_url: str | None = None
    source_url: str | None = None


class RecipeDocument(BaseModel):
    recipe_id: str
    title: str
    cuisine: str | None = None
    cuisines: list[str] = Field(default_factory=list)
    diet: str | None = None
    searchable_text: str
    chunks: list[str] = Field(default_factory=list)
    metadata: dict[str, str | int | float | list[str] | None] = Field(
        default_factory=dict,
    )
