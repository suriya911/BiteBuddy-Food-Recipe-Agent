from pydantic import BaseModel, Field


class UserProfile(BaseModel):
    preferred_cuisines: list[str] = Field(default_factory=list)
    diet: str | None = None
    allergies: list[str] = Field(default_factory=list)
    disliked_ingredients: list[str] = Field(default_factory=list)
    excluded_ingredients: list[str] = Field(default_factory=list)
    available_ingredients: list[str] = Field(default_factory=list)
    max_cooking_time_minutes: int | None = None


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str = Field(
        min_length=1,
        description="Free-form user query typed into the chat input.",
    )
    history: list[ChatMessage] = Field(default_factory=list)
    profile: UserProfile = Field(default_factory=UserProfile)
    session_id: str | None = None


class PreferenceSnapshot(BaseModel):
    cuisines: list[str] = Field(default_factory=list)
    diet: str | None = None
    allergies: list[str] = Field(default_factory=list)
    excluded_ingredients: list[str] = Field(default_factory=list)
    available_ingredients: list[str] = Field(default_factory=list)
    max_cooking_time_minutes: int | None = None


class AgentInput(BaseModel):
    raw_query: str
    normalized_query: str
    query_tokens: list[str] = Field(default_factory=list)
    retrieval_query: str
    detected_preferences: PreferenceSnapshot
    profile: UserProfile
    should_retrieve_recipes: bool = True
    should_answer_general_food_question: bool = False


class RecipeMatch(BaseModel):
    recipe_id: str
    title: str
    cuisine: str | None = None
    cuisines: list[str] = Field(default_factory=list)
    diet: str | None = None
    total_time_minutes: int | None = None
    ingredients: list[str] = Field(default_factory=list)
    score: float
    match_reasons: list[str] = Field(default_factory=list)


class RetrievalTrace(BaseModel):
    total_recipes: int
    metadata_matches: int
    vector_matches: int
    fallback_applied: bool = False
    fallback_reason: str | None = None


class AgentConflict(BaseModel):
    type: str
    message: str


class IngredientSubstitution(BaseModel):
    ingredient: str
    substitutes: list[str] = Field(default_factory=list)


class AgentReply(BaseModel):
    reply: str
    agent_input: AgentInput
    session_id: str
    recipe_matches: list[RecipeMatch] = Field(default_factory=list)
    retrieval_trace: RetrievalTrace | None = None
    conflicts: list[AgentConflict] = Field(default_factory=list)
    substitution_suggestions: list[IngredientSubstitution] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
